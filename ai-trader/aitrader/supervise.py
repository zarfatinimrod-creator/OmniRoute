"""The supervisor's parent process (supervisor spec 2026-11-10, section 4): it starts the news engine, restarts it,
and keeps the uptime log. So far (Task 10) its foundations: the config, its own trading calendar, the uptime log, the
state file and its lock.

Standard library only, and never aitrader.journal, notify or news_live (they bring pandas and requests): the parent
must start in a moment and keep running when what broke is the engine's own imports. It reads config.json itself.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent  # ai-trader/: config.json, state/, .cache/
KEPT_ACROSS_DAYS = ("halt", "reported_through", "last_commit")  # what a state file of another New York day keeps


def load_cfg(path: Path | None = None) -> dict:
    """The whole of config.json: the one beside the package, or the copy a drill or a test passes (--config)."""
    return json.loads(Path(path or ROOT / "config.json").read_text(encoding="utf-8"))


def session_hours(day: date, cal: dict) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """NYSE regular session (open, close) in New York (hour, minute) on a date, or None when it is closed, from
    config.json's calendar block. The contract of journal.session_hours, written again because the parent may not
    import journal (pandas); a test holds the two equal on every day of 2026 and 2027 (spec 4.5). A weekend, a holiday
    or a year the calendar does not list is closed (fail closed: unknown holidays must not look like sessions); an
    early close ends at 13:00. The hours are journal.session_hours' own: the calendar block carries none."""
    d = day.isoformat()
    if day.weekday() >= 5 or day.year not in set(cal.get("years", [])) or d in set(cal.get("holidays", [])):
        return None
    return (9, 30), ((13, 0) if d in set(cal.get("early_close", [])) else (16, 0))


class Paths:
    """Where the parent's files are. state_dir: its lock and state file, the dead-man's and the relay's files, the
    uptime log, and the engine's files it reads (the heartbeat, the engine's lock, the trade journal). cache_dir: the
    parent's log and the engine's. --state-dir DIR (main) is Paths(DIR, DIR / ".cache"); the default is ai-trader's
    state/ and .cache/."""

    def __init__(self, state_dir: Path, cache_dir: Path):
        state_dir, cache_dir = Path(state_dir), Path(cache_dir)
        self.lock = state_dir / "news_supervisor.lock"
        self.state = state_dir / "news_supervisor.json"
        self.deadman = state_dir / "news_deadman.json"
        self.relayed = state_dir / "news_relayed.json"
        self.uptime = state_dir / "uptime.jsonl"
        self.heartbeat = state_dir / "news_heartbeat.json"
        self.engine_lock = state_dir / "news_engine.lock"
        self.trades = state_dir / "news_trades.jsonl"
        self.sup_log = cache_dir / "supervise.log"
        self.engine_log = cache_dir / "news_live.log"


def _utc(t: datetime) -> str:
    """UTC, ISO-8601, whole seconds."""
    return t.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def append_row(path: Path, pid: int, ev: str, now: datetime, **fields) -> dict:
    """One row of the uptime log (spec 4.6), {"t": now in UTC, whole seconds, "ev", "sup": the parent's pid, **fields},
    as one JSON line. A file whose last line was torn (a write cut short) gets a newline first: the torn piece stays a
    line of its own, which read_rows skips, and this row is whole. Returns the row."""
    row = {"t": _utc(now), "ev": ev, "sup": pid, **fields}
    try:
        with path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            torn = f.read(1) != b"\n"
    except OSError:  # no file yet, or an empty one (it cannot seek before its start): nothing is torn
        torn = False
    with path.open("a", encoding="utf-8") as f:
        f.write(("\n" if torn else "") + json.dumps(row, default=str, ensure_ascii=False) + "\n")
    return row


def read_rows(path: Path) -> list[dict]:
    """The rows of a JSON-lines file, in order; [] when there is no file. A line that does not parse as a JSON object
    (a torn write, a damaged byte) is skipped: a measurement must never stop the parent. Lines are split as bytes, so
    a line separator inside a text field cannot split a row."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return []
    rows = []
    for line in data.splitlines():
        try:
            row = json.loads(line)
        except ValueError:  # JSONDecodeError, and UnicodeDecodeError for a damaged byte
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _older(line: bytes, cutoff: datetime) -> bool:
    try:
        return datetime.fromisoformat(json.loads(line)["t"]) < cutoff
    except (ValueError, KeyError, TypeError):  # not a row, or no time that can be read: its age is not known
        return False


def prune_rows(path: Path, keep_days: int, now: datetime) -> None:
    """Drops the rows whose `t` is more than keep_days days before now (at sup_start; spec 4.6). A line whose age
    cannot be read stays, and every kept line stays as it was written. The file is rewritten only when a row goes,
    through a tmp file and a rename: a crash leaves the old file or the new one, never half of one."""
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except FileNotFoundError:
        return
    cutoff = now - timedelta(days=keep_days)
    kept = [line for line in lines if not _older(line, cutoff)]
    if len(kept) == len(lines):
        return
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(b"".join(line if line.endswith(b"\n") else line + b"\n" for line in kept))
    tmp.replace(path)


def _new_state(ny_day: str) -> dict:
    return {"day": ny_day, "restarts_today": 0, "trips_today": 0, "halt": None,
            "alerts": {"hour": None, "sent": 0, "capped": 0}, "reported_through": None, "last_commit": None,
            "handover": None}


def load_state(path: Path, ny_day: str) -> dict:
    """The parent's state file (spec 4.3) for the New York day ny_day ("YYYY-MM-DD"). It never raises:
    - no file: a new day's state;
    - a file of that day: what it holds, over a new day's state for any key it lacks;
    - a file of another day: a new day's state that keeps `halt` (until --clear-halt), `reported_through` and
      `last_commit`. The counts and the alert counts start again and `handover` is cleared: a handover nobody
      answered must not give the next morning's `up` an 18-hour handover_s;
    - a file that cannot be read as a JSON object: a new day's state with one more key, `load_error`, the class name of
      what went wrong (never its text). main writes it to the parent's log and removes it before the first save
      (ruling P18(c)). A halt in such a file is lost; the engine's start checks find its cause again."""
    st = _new_state(ny_day)
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("day") == ny_day:
            return {**st, **old}
        return {**st, **{k: old.get(k) for k in KEPT_ACROSS_DAYS}}
    except FileNotFoundError:
        return st
    except Exception as e:  # noqa: BLE001 - whatever is wrong with the file, the parent starts on a new day's state
        return {**st, "load_error": type(e).__name__}


def save_state(path: Path, st: dict) -> None:
    """The state file, written whole: a tmp file beside it, then a rename, so nobody reads half of one. Only the
    parent that holds the lock writes it (spec 4.3)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=2, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def take_lock(path: Path, now: datetime) -> IO | None:
    """The parent's lock (spec 4.2), taken as the engine takes its own (news_live.run): an flock held for the life of
    the parent and freed by the kernel however the parent ends. Returns the open file, which the caller keeps open,
    or None when another process holds the lock. The holder writes {"pid", "started_at"} into the file, as the engine
    does, for the start it refuses and for --status; "a+" leaves that text alone while a refused start reads it. The
    text is a hint only: it stays after the holder has ended. Any other failure of the lock call is raised. The file
    is not inherited by the child (Python opens it non-inheritable)."""
    f = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        f.close()
        if isinstance(e, BlockingIOError):
            return None
        raise
    try:  # one line, the holder's own
        f.truncate(0)
        f.write(json.dumps({"pid": os.getpid(), "started_at": _utc(now)}) + "\n")
        f.flush()
    except OSError:  # a full disk: the lock is held all the same, and the text was only a hint for whoever asks
        pass
    return f
