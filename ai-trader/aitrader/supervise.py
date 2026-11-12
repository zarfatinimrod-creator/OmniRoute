"""The supervisor's parent process (supervisor spec 2026-11-10, section 4): it starts the news engine, restarts it,
and keeps the uptime log. So far (Tasks 10-15): its foundations (the config, its own trading calendar, the uptime log,
the state file and its lock), the restart core, the loop that runs it, what the loop reads in the heartbeat (a mark
a minute, `up` and `code` at a child's first looks, a hang, stale stops), its lines to the owner (spec 8: every
restart, hang, trip, halt and gap, one line per event, through deadman.Sender), what a woken session reads
(spec 4.4: --status decides, --clear-halt and --relayed are its only two writers), and the handover by the clock
before the harness's 2-hour cap (spec 4.5: --handover, measured by the next parent's first `up`):

    python3 -u -m aitrader.supervise --until HH:MM [--handover] [--state-dir DIR] [--config FILE]
    python3 -m aitrader.supervise --status [--watchdog] [--state-dir DIR] [--config FILE]
    python3 -m aitrader.supervise --relayed ID... [--state-dir DIR] [--config FILE]
    python3 -m aitrader.supervise --clear-halt [--config FILE]
    python3 -m aitrader.supervise --net-check [--config FILE]

Standard library only, and never aitrader.journal, notify or news_live (they bring pandas and requests): the parent
must start in a moment and keep running when what broke is the engine's own imports. It reads config.json itself.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import IO
from zoneinfo import ZoneInfo

from . import deadman, ownerlines

ROOT = Path(__file__).resolve().parent.parent  # ai-trader/: config.json, state/, .cache/
KEPT_ACROSS_DAYS = ("halt", "reported_through", "last_commit")  # what a state file of another New York day keeps
NY = ZoneInfo("America/New_York")


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


def closed_day(day: date, cal: dict) -> bool:
    """No session today and no engine to start (the parent's closed_today, --status' closed_today): a weekend or a
    holiday. A weekday of a year the calendar does not list is no closed day, though session_hours fails it closed: the
    engine's start check refuses it with its urgent line and 5, and the parent halts on that 5 (spec 4.3)."""
    return session_hours(day, cal) is None and (day.weekday() >= 5 or day.year in cal.get("years", []))


class Paths:
    """Where the parent's files are. state_dir: its lock and state file, the dead-man's and the relay's files, the
    uptime log, and the engine's files it reads (the heartbeat, the engine's lock, the trade journal, the book).
    cache_dir: the parent's log and the engine's. --state-dir DIR (main) is Paths(DIR, DIR / ".cache"); the default is
    ai-trader's state/ and .cache/."""

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
        self.book = state_dir / "news_book.json"
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
    if now.utcoffset() is None:  # a naive time cannot be compared with the rows' aware ones: every row would stay
        raise ValueError("prune_rows needs an aware time")
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
    does, for the start it refuses; "a+" leaves that text alone while a refused start reads it. The text is a hint
    only: it stays after the holder has ended (--status reads the lock itself). Any other failure of the lock call is
    raised. The file is not inherited by the child (Python opens it non-inheritable)."""
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


PLANNED = {"handover": 76, "signal": 143, "orphaned": 143}  # watch's stop orders, and the code the parent ends with
HALTS = (4, 5, 6)  # a broken chain, a calendar that does not cover today, an unreadable book: no restart (spec 4.3)


def restart_core(spawn, watch, stop, near_until, emit, pol, counts, *, mono=time.monotonic,
                 sleep=time.sleep) -> tuple[int, str]:
    """Starts the child, reads how it ended by the table of spec 4.3, starts it again or gives up, and returns the
    parent's (code, word). No network, no file and no wall clock in it: all of that comes in.
    spawn() -> a child (.pid; .poll() is None while it runs, a negative code is a signal, as subprocess.Popen gives).
    watch(child or None, ran_s) -> None, "hang", "handover", "signal" or "orphaned": asked every loop_seconds while a
    child runs, and while the core waits to start one. stop(child, "planned" | "hang") returns once the child has ended.
    near_until() -> whether a 0 now is the end of the day. emit(ev, **fields): the rows start, exit and tripped.
    pol: the supervisor block. counts {"restarts_today", "stamps"} (the monotonic times of the restarts) is changed in
    place.
    - 0 near --until: (0, "end_of_day"). 4, 5, 6: (code, "halt"), no restart.
    - 3, another engine holds the book: started again after the back-off, not counted, for lock_wait_seconds from the
      first refusal; then (3, "lock_held").
    - Any other end is a crash, among them a 7 (the exit row says "tree_busy"), a signal, a 0 far from --until, a
      143 nobody asked for (not in the spec's table: counted, so the trip bounds it) and a spawn that raises (no child:
      the exit row has child and rc null and why "spawn <class>"; ruling 36 c). Started again at once after a run of
      healthy_seconds or more, else after the back-off: backoff_first_seconds, doubling up to backoff_max_seconds, and
      from the first again after a healthy run, or after lock refusals (their waits double the same delay; ruling 36
      d). When one more restart would pass max_restarts in restart_window_seconds, or max_restarts_day: a tripped row
      and (75, "crash_loop").
    - watch says "hang": stop(child, "hang"), then a crash. "handover", "signal" or "orphaned": stop(child, "planned")
      and (76, "handover") or (143, the word); while the core waits to start a child, the same answer, and no start."""
    delay = pol["backoff_first_seconds"]  # the wait after the next quick crash
    wait, refused_at = 0, None
    while True:
        end = mono() + wait
        while True:  # the wait before a start; watch is asked at least once, so a stop order never costs a start
            order = watch(None, 0.0)
            if order in PLANNED:
                return PLANNED[order], order
            left = end - mono()
            if left <= 0:
                break
            sleep(min(pol["loop_seconds"], left))
        try:
            child = spawn()
        except (OSError, ValueError, subprocess.SubprocessError) as e:  # no memory, no such program: no child, a crash
            ran, rc, why = 0.0, None, f"spawn {type(e).__name__}"
            emit("exit", child=None, rc=None, signal=None, ran_s=ran, why=why)
        else:
            emit("start", child=child.pid, n=counts["restarts_today"] + 1, backoff_s=wait)
            t0, why = mono(), "exit"
            while (rc := child.poll()) is None:
                order = watch(child, mono() - t0)
                if order == "hang" or order in PLANNED:
                    why = "hang" if order == "hang" else "planned"
                    stop(child, why)
                    rc = child.poll()
                    break
                sleep(pol["loop_seconds"])
            ran = mono() - t0
            why = "tree_busy" if why == "exit" and rc == 7 else why
            signalled = rc is not None and rc < 0
            emit("exit", child=child.pid, rc=None if signalled else rc, signal=-rc if signalled else None,
                 ran_s=round(ran, 1), why=why)
        if why == "planned":
            return PLANNED[order], order
        if why == "exit" and rc == 0 and near_until():
            return 0, "end_of_day"
        if why == "exit" and rc in HALTS:
            return rc, "halt"
        if why == "exit" and rc == 3:
            now = mono()
            refused_at = now if refused_at is None else refused_at
            if now - refused_at >= pol["lock_wait_seconds"]:
                return 3, "lock_held"
            wait = min(delay, refused_at + pol["lock_wait_seconds"] - now)  # the last try falls inside the wait
            delay = min(delay * 2, pol["backoff_max_seconds"])
            continue
        if refused_at is not None:  # the lock refusals are over: this crash backs off from the first value, not 2^N s
            delay = pol["backoff_first_seconds"]
        refused_at, now = None, mono()
        counts["stamps"][:] = [s for s in counts["stamps"] if now - s < pol["restart_window_seconds"]]
        if len(counts["stamps"]) >= pol["max_restarts"]:
            emit("tripped", restarts=len(counts["stamps"]), window_s=pol["restart_window_seconds"])
            return 75, "crash_loop"
        if counts["restarts_today"] >= pol["max_restarts_day"]:  # the day's limit: the restarts of the whole day
            emit("tripped", restarts=counts["restarts_today"], window_s=None)
            return 75, "crash_loop"
        counts["stamps"].append(now)
        counts["restarts_today"] += 1
        if ran >= pol["healthy_seconds"]:
            wait, delay = 0, pol["backoff_first_seconds"]
        else:
            wait, delay = delay, min(delay * 2, pol["backoff_max_seconds"])


def near_until(now_ny: datetime, until: str, slack_s: float) -> bool:
    """Whether a 0 from the engine now is the end of the day: now_ny (New York) is at or after today's `until` less
    slack_s. One-sided: the engine reads the clock only at the top of a round, so a last step with scorer calls can
    end minutes after --until, and that 0 is still the end of the day, not a crash and a trip after the close. "24:00"
    is the midnight that ends the day."""
    h, m = (int(x) for x in until.split(":"))
    midnight = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    return now_ny >= midnight + timedelta(hours=h, minutes=m, seconds=-slack_s)


def handover_due(started_ny: datetime, now_ny: datetime, times: list[str], min_leg_minutes: int,
                 max_leg_minutes: int) -> bool:
    """Whether a parent started at started_ny hands over now (spec 4.5; both New York): from the first tick at or after
    a listed time ("HH:MM", today) that lies min_leg_minutes or more after the start (a closer one is skipped), and
    once the parent has run max_leg_minutes, whatever the clock says (the backstop before the 2-hour cap)."""
    def at(hm: str) -> datetime:
        h, m = (int(x) for x in hm.split(":"))
        return now_ny.replace(hour=h, minute=m, second=0, microsecond=0)
    return (now_ny - started_ny >= timedelta(minutes=max_leg_minutes)
            or any(started_ny + timedelta(minutes=min_leg_minutes) <= at(hm) <= now_ny for hm in times))


def open_seconds(a: datetime, b: datetime, cal: dict) -> float:
    """The seconds of [a, b] that fall inside regular sessions (session_hours on each New York date from a's to b's):
    a weekend or a holiday adds nothing and an early close ends at 13:00. 0 when b is not after a."""
    total, day = 0.0, a.astimezone(NY).date()
    while day <= b.astimezone(NY).date():
        hours = session_hours(day, cal)
        if hours:
            (oh, om), (ch, cm) = hours
            lo = max(a, datetime(day.year, day.month, day.day, oh, om, tzinfo=NY))
            hi = min(b, datetime(day.year, day.month, day.day, ch, cm, tzinfo=NY))
            total += max(0.0, (hi - lo).total_seconds())
        day += timedelta(days=1)
    return total


def _when(text) -> datetime | None:
    """An ISO-8601 time with its zone; None for anything else."""
    try:
        t = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return t if t.utcoffset() is not None else None


def _held(hb: dict) -> dict:
    held = hb.get("held")
    return held if isinstance(held, dict) else {}


def _looks(hb: dict) -> dict:
    """Each held name's last stop look in a beat: its own checked_at, else the beat's stops_checked_at (until a process
    has looked itself, the look the run before it left; spec 5.5); None when neither can be read."""
    kept = _when(hb.get("stops_checked_at"))
    return {sym: _when(v.get("checked_at") if isinstance(v, dict) else None) or kept for sym, v in _held(hb).items()}


def _stamp_ages(hb: dict, age_s: float | None) -> dict:
    """Each held name's stop-look age now (ruling P16): the beat's `at` less its stamp, plus the beat's own age, so that
    it keeps growing through a long call that writes no beat. None when a time or the age is not known."""
    at = _when(hb.get("at"))
    return {sym: None if None in (at, t, age_s) else (at - t).total_seconds() + age_s for sym, t in _looks(hb).items()}


def beat_view(hb: dict | None, mtime: float | None, child_pid: int | None, now: float) -> dict:
    """What the parent reads in the heartbeat (spec 4.3, 4.6). now = time.time(): age_s is now less the file's mtime,
    never the injected clock. mine: the beat is this child's; a beat of another pid, or none, is no beat (Review
    Focus 1), and then the rest is empty. stop_age_s: the age of the oldest per-name stamp now (ruling P16); None when
    nothing is held or a held name's stamp cannot be read. held: {symbol: stop}."""
    mine = child_pid is not None and isinstance(hb, dict) and hb.get("pid") == child_pid
    view = {"mine": mine, "age_s": None if mtime is None else now - mtime, "stop_age_s": None, "held": {},
            "open": None, "blind": [], "phase": None}
    if not mine:
        return view
    ages = list(_stamp_ages(hb, view["age_s"]).values())
    blind = hb.get("blind")
    view.update(stop_age_s=max(ages) if ages and None not in ages else None,
                held={sym: v.get("stop") if isinstance(v, dict) else None for sym, v in _held(hb).items()},
                open=bool(hb.get("market_open")), blind=list(blind) if isinstance(blind, list) else [],
                phase=hb.get("phase"))
    return view


def first_look_done(hb: dict | None, child_pid: int, started: float) -> bool:
    """This child has looked at its stops (spec 4.6, `up`): the beat is its own, past "boot", and every held name has a
    checked_at at or after `started` (time.time() at the start) or is in the beat's blind list. A held name with no
    live quote keeps an old checked_at for hours: without the blind half no `up` would come at all."""
    if not isinstance(hb, dict) or hb.get("pid") != child_pid or hb.get("phase") == "boot":
        return False
    blind = hb.get("blind") if isinstance(hb.get("blind"), list) else []
    for sym, v in _held(hb).items():
        t = _when(v.get("checked_at") if isinstance(v, dict) else None)
        if sym not in blind and (t is None or t.timestamp() < started):
            return False
    return True


def mark_due(last_mark: datetime | None, now: datetime) -> bool:
    """A mark is due at the first loop tick inside a clock minute that has none (spec 4.6)."""
    return last_mark is None or now.replace(second=0, microsecond=0) != last_mark.replace(second=0, microsecond=0)


TITLE = "AI Trader - מפקח"  # every line of the parent's own (the spec fixes only the dead-man's title)
COUNTED = ("R1", "R2", "R6")  # the lines max_alerts_per_hour counts (spec 8)
HELD_BACK = ("R1", "R2")  # of those, the ones held back over the count


def _hour(now: datetime) -> str:
    """The clock hour of `now`, as the state file's alerts.hour keeps it."""
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


def may_send(st: dict, line_id: str, now: datetime, cap: int) -> bool:
    """Whether a line goes out now (spec 8). R1, R2 and R6 count against `cap` lines in the clock hour of `now`, kept in
    the state file's `alerts` {"hour", "sent", "capped"} so that a new parent goes on counting. R1 and R2 over the
    count are held back ("capped"). R6 is counted and never held back, and no other line is: the spec lists R6 under
    the cap and also says that urgent lines are never capped, and "stops not checked" must not wait for an hour to
    turn. A new hour starts the counts again. `alerts` is replaced whole: load_state's same-day merge is shallow."""
    old = st.get("alerts")
    a = {"hour": None, "sent": 0, "capped": 0, **(old if isinstance(old, dict) else {})}
    if a["hour"] != _hour(now):
        a = {"hour": _hour(now), "sent": 0, "capped": 0}
    go = line_id not in HELD_BACK or a["sent"] < cap
    if line_id in COUNTED:
        a = {**a, "sent": a["sent"] + 1} if go else {**a, "capped": a["capped"] + 1}
    st["alerts"] = a
    return go


def gap_line(prev: dict | None, up_at: datetime, cold: bool, cal: dict, sup: dict) -> tuple[str, dict] | None:
    """The line for the outage before a parent's first `up` (spec 8, R4 and R4b), or None. prev: the last readable row
    before this sup_start (or a machine pause's start as {"t", "ev": "pause"}: R4, ruling 49; up_at is then its end).
    Only when [prev.t, up_at] holds outage_report_seconds or more inside sessions (today's or earlier ones): R4 when
    prev is no sup_stop (with cold, `cold_time` is prev.t on the owner's clock: the parent never runs git, and the last
    row it can read is what git restored); R4b when it is a sup_stop whose `why` has a word in
    ownerlines.WORDS["R4b.why"]. After a sup_stop for a halt, a held lock, the end of the day or a closed day it is
    None: R5a-R5e said that the stops are not checked, and the minutes reach R11. The fields carry `m`, the line's
    minutes, for its alert row (ruling P6)."""
    t = _when(prev.get("t")) if isinstance(prev, dict) else None
    if t is None:
        return None
    s = open_seconds(t, up_at, cal)
    if s < sup["outage_report_seconds"]:
        return None
    tz = sup["owner_tz"]
    fields = {"time": ownerlines.hhmm(t, tz), "time2": ownerlines.hhmm(up_at, tz), "m": round(s / 60)}
    if prev.get("ev") != "sup_stop":
        return "R4", {**fields, **({"cold_time": fields["time"]} if cold else {})}
    why = ownerlines.WORDS["R4b.why"].get(str(prev.get("why")))
    return ("R4b", {**fields, "why": why}) if why else None


def _alert_n(row: dict) -> int:
    """The n of an alert row's id, "<kind>-<n>"; 0 when it has none."""
    try:
        return int(str(row.get("id")).rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _read_beat(path: Path) -> tuple[dict | None, float | None]:
    """The heartbeat and its file's mtime, both from one open file (a beat is replaced whole, never rewritten in place,
    so the two belong together); (None, None) when there is no file, the beat None when it is no JSON object."""
    try:
        with open(path, "rb") as f:
            data, mtime = f.read(), os.fstat(f.fileno()).st_mtime
    except OSError:
        return None, None
    try:
        hb = json.loads(data)
    except ValueError:
        return None, mtime
    return (hb if isinstance(hb, dict) else None), mtime


def _held_now(paths: Paths, child_pid: int | None) -> dict | None:
    """{symbol: stop} from the beat of the child child_pid; with no beat of its own (no child, none yet, another pid's),
    from the book as plain JSON (ruling P11: the book is tracked and holds every stop, the heartbeat is neither). None
    when neither can tell (Ruling 39): no beat of its own, and no book that reads as a book (missing, not JSON, no
    positions map, a position that is no mapping); a beat of another pid is not used, it can be days old. {} only for
    a book that reads and holds nothing. ownerlines.held_text gives the two their own words."""
    hb, mtime = _read_beat(paths.heartbeat)
    if child_pid is not None and isinstance(hb, dict) and hb.get("pid") == child_pid:
        return beat_view(hb, mtime, child_pid, time.time())["held"]
    try:
        book = json.loads(paths.book.read_text(encoding="utf-8"))
        return {sym: p.get("stop_price") for sym, p in book["positions"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):  # no book, or none that can be read
        return None


def _signal_group(pgid: int, sig: int) -> None:
    """sig to a child's process group; a group with no member left is no error. Linux keeps the group's number while the
    group has a member, also once the child that led it is reaped: only what the child started is signalled."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


TWO_HOURS_MS = 7_200_000  # the harness's cap on a background command (spec 4.5): a fact of the platform, not a tuning
HALT_WHY = {4: "chain", 5: "calendar", 6: "book"}  # the state file's halt.why for the engine's code
SAID = {"crash_loop": "tripped"}  # the word of the last stdout line, where it is not the sup_stop row's why
AFTER = "Run python3 -m aitrader.supervise --status and do what action says."
HHMM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")  # a clock time of the day: the handover times
UNTIL = re.compile(rf"{HHMM.pattern}|24:00")
NUMBERS = ("loop_seconds", "healthy_seconds", "backoff_first_seconds", "backoff_max_seconds", "max_restarts",
           "restart_window_seconds", "max_restarts_day", "lock_wait_seconds", "planned_stop_grace_seconds",
           "end_of_day_slack_seconds", "uptime_keep_days", "long_timeout_ms", "hang_seconds", "start_grace_seconds",
           "hang_term_grace_seconds", "stops_stale_seconds", "outage_report_seconds", "max_alerts_per_hour",
           "alert_retry_seconds", "alert_retry_minutes", "send_timeout_seconds", "max_line_bytes",
           "held_names_in_line", "free_text_max_chars", "min_leg_minutes",
           "max_leg_minutes", "clear_halt_check_timeout_seconds")  # what main and the core read
# above 0, or the parent refuses the config: a zero loop would spin, a zero grace would kill at once
POSITIVE = ("loop_seconds", "start_grace_seconds", "hang_term_grace_seconds", "planned_stop_grace_seconds")


def _holder(lock: Path):
    """The pid that a lock's holder wrote into the lock file; "unknown" when the file does not say."""
    try:
        return json.loads(lock.read_text(encoding="utf-8"))["pid"]
    except Exception:  # noqa: BLE001 - the text is a hint only
        return "unknown"


def _argv(pid: int) -> list[str]:
    """The command line of a live process; [] when there is none (a zombie has an empty one)."""
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


def _ppid(pid: int) -> int | None:
    """A live process's parent pid (/proc/<pid>/stat: its name in brackets may hold spaces); None when it has none."""
    try:
        return int(Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[1])
    except (OSError, ValueError, IndexError):
        return None


# A row of /proc/locks that holds an flock (a waiting row starts with "->"): "1: FLOCK  ADVISORY  WRITE <pid>
# <major>:<minor>:<inode> 0 EOF". Only the inode is compared: on an overlay filesystem /proc/locks gives another device
# than stat does. ponytail: an flock on a file of another filesystem with the same inode number, held by a process
# whose command line names the same word, would pass too; compare the device as well if that ever happens.
FLOCK_ROW = re.compile(r"^\d+:\s+FLOCK\s+\S+\s+(?:READ|WRITE)\s+(-?\d+)\s+[0-9a-f]+:[0-9a-f]+:(\d+)\s")


def _live(lock: Path, name: str) -> int | None:
    """The pid that holds the flock on the lock file when its command line names `name` (aitrader.supervise for the
    parent, news-live for the engine); else None. The lock itself decides (controller note, 12:19 UTC 2026-11-11), read
    in /proc/locks, never the text in the file: the text stays after its writer has ended, its pid can be some other
    process now (Review Focus 1), and it can name an older pid while a live holder holds the lock (take_lock keeps the
    flock when the text cannot be written). Read-only: no flock call, which even for a moment could refuse a parent
    that starts in that moment. A file or a /proc/locks that cannot be read: None."""
    try:
        ino, rows = lock.stat().st_ino, Path("/proc/locks").read_text().splitlines()
    except OSError:
        return None
    holders = [int(m[1]) for m in map(FLOCK_ROW.match, rows) if m and int(m[2]) == ino]
    return next((pid for pid in holders if name in _argv(pid)), None)


def _relayed(path: Path, day: str) -> list[str]:
    """The ids --relayed has written for the New York day `day`; [] for another day's file, or none that can be read."""
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
        return [i for i in got["ids"] if isinstance(i, str)] if got.get("day") == day else []
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def status(paths: Paths, cfg: dict, now: datetime, *, watchdog: bool = False, environ: Mapping | None = None) -> dict:
    """What a woken session does now (spec 4.4), as the JSON of --status. It reads files and /proc only: it writes
    nothing and takes no lock. A parent is alive when its lock is held (/proc/locks) by a pid whose command line names
    aitrader.supervise, and that pid is parent.pid; an engine, the same with the engine's lock and news-live.
    - action: the first row of the spec's table that applies: closed_today; after_hours (outside launch_from_ny to
      launch_until_ny, New York); none (a live parent, and the uptime log's last mark is at most parent_stale_seconds
      old: one parent runs at a time, so it is that parent's unless it has not ticked yet); replace_parent (a live
      parent, no such mark); halted; kill_stray (a live engine whose parent pid is no live
      parent; why carries its pid); wait_for_watchdog (a second trip today, the call not from a watchdog slot, and the
      log's last row no sup_stop of a handover, a signal or an orphaned parent: after a planned stop the session
      launches at once); launch.
    - unsent: today's alert lines whose latest row says sent false, past their retries (the first row is older than
      alert_retry_minutes, or no parent lives to retry them; R10 at once: the parent never retries it) and not in
      news_relayed.json. With watchdog and a halt of an earlier New York day, R5e as well, id "R5e-<today>", until it
      is relayed; its {held} from the book (ruling P11), "unknown" when no book can be read (ruling 39). On the day of
      the halt R5a-R5d have spoken.
    - launch: the command and timeout of the tracked background command: --handover and TWO_HOURS_MS until
      long_timeout_proven is true and environ's BASH_MAX_TIMEOUT_MS is at least long_timeout_ms (section 9)."""
    sup, cal = cfg["supervisor"], cfg["calendar"]
    environ = os.environ if environ is None else environ
    ny = now.astimezone(NY)
    day, today = ny.date(), ny.date().isoformat()
    st = load_state(paths.state, today)
    try:
        rows = read_rows(paths.uptime)
    except OSError:  # a log that cannot be read: no rows, as for none
        rows = []
    parent, engine = _live(paths.lock, "aitrader.supervise"), _live(paths.engine_lock, "news-live")
    mark = next((r for r in reversed(rows) if r.get("ev") == "mark"), {})
    mark_t = _when(mark.get("t"))
    mark_age = None if mark_t is None else (now - mark_t).total_seconds()
    halt = st.get("halt")
    code, cause, at = (halt.get(k) for k in ("code", "why", "at")) if isinstance(halt, dict) else (halt, None, None)
    last = rows[-1] if rows else {}
    hm = ny.strftime("%H:%M")
    if closed_day(day, cal):
        action, why = "closed_today", "not a session day"
    elif not sup["launch_from_ny"] <= hm < sup["launch_until_ny"]:
        action, why = "after_hours", f"outside {sup['launch_from_ny']} to {sup['launch_until_ny']} New York"
    elif parent is not None and mark_age is not None and mark_age <= sup["parent_stale_seconds"]:
        action, why = "none", f"a live parent, pid {parent}"
    elif parent is not None:
        action, why = "replace_parent", f"the parent, pid {parent}, has no mark in {sup['parent_stale_seconds']} s"
    elif halt:
        action, why = "halted", f"halt {code} ({cause}) since {at}"
    elif engine is not None and _ppid(engine) != parent:
        action, why = "kill_stray", f"engine pid {engine} runs without a live parent"
    elif st["trips_today"] >= 2 and not watchdog and not (last.get("ev") == "sup_stop" and last.get("why") in PLANNED):
        action, why = "wait_for_watchdog", "a second trip today: the next watchdog slot launches"
    else:
        action, why = "launch", "no live parent"

    relayed, first, latest = _relayed(paths.relayed, today), {}, {}
    for r in rows:
        t = _when(r.get("t"))
        if r.get("ev") == "alert" and isinstance(r.get("id"), str) and t is not None and t.astimezone(NY).date() == day:
            first.setdefault(r["id"], t)
            latest[r["id"]] = r
    unsent = [{"id": i, "kind": r.get("kind"), "text": r.get("text")} for i, r in latest.items()
              if r.get("sent") is False and i not in relayed
              and (r.get("kind") == "R10" or parent is None
                   or (now - first[i]).total_seconds() > sup["alert_retry_minutes"] * 60)]
    halted_at, r5e = _when(at), f"R5e-{today}"
    if watchdog and halted_at is not None and halted_at.astimezone(NY).date() < day and r5e not in relayed:
        try:
            text = ownerlines.render("R5e", max_bytes=sup["max_line_bytes"], free_chars=sup["free_text_max_chars"],
                                     date=halted_at.astimezone(ZoneInfo(sup["owner_tz"])).strftime("%d.%m"),
                                     why=ownerlines.WORDS["R5e.why"][code],
                                     held=ownerlines.held_text(_held_now(paths, None), sup["held_names_in_line"]))
            unsent.append({"id": r5e, "kind": "R5e", "text": text})
        except (KeyError, ValueError, TypeError):  # a halt code no engine gives, or a book stop that is no number
            pass

    hb, mtime = _read_beat(paths.heartbeat)
    view = beat_view(hb, mtime, hb.get("pid") if hb else None, time.time())
    built = hb.get("code") if hb and isinstance(hb.get("code"), dict) else {}
    try:
        allowed = int(environ.get("BASH_MAX_TIMEOUT_MS", ""))
    except (TypeError, ValueError):  # missing, or no number
        allowed = 0
    long = sup["long_timeout_proven"] is True and allowed >= sup["long_timeout_ms"]

    def rounded(s: float | None) -> int | None:
        return None if s is None else round(s)
    return {"action": action, "why": why, "ny_time": ny.strftime("%H:%M:%S"), "session_day": not closed_day(day, cal),
            "parent": {"alive": parent is not None, "pid": parent, "mark_age_s": rounded(mark_age)},
            "engine": {"hb_age_s": rounded(view["age_s"]), "stop_age_s": rounded(view["stop_age_s"]),
                       "held": len(view["held"]) if view["mine"] else None, "commit": built.get("commit"),
                       "dirty": built.get("dirty")},
            "today": {"restarts": st["restarts_today"], "trips": st["trips_today"], "halt": halt},
            "deadman_ok": mark.get("dm"), "ntfy_left": mark.get("left"), "unsent": unsent,
            "launch": {"command": f"cd ai-trader && exec python3 -u -m aitrader.supervise --until {sup['until_ny']}"
                                  + ("" if long else " --handover"),
                       "timeout_ms": sup["long_timeout_ms"] if long else TWO_HOURS_MS}}


def relay(paths: Paths, ids: list[str], now: datetime) -> int:
    """--relayed ID...: these lines went out through the Claude app, so --status lists them no more. The one writer of
    state/news_relayed.json, {"day", "ids"}; a new New York day starts an empty list."""
    day = now.astimezone(NY).date().isoformat()
    try:
        save_state(paths.relayed, {"day": day, "ids": list(dict.fromkeys(_relayed(paths.relayed, day) + ids))})
    except OSError as e:
        print(f"supervise: news_relayed.json was not written ({type(e).__name__})", file=sys.stderr)
        return 1
    print(f"supervise: relayed {' '.join(ids)}", flush=True)
    return 0


def clear_halt(paths: Paths, now: datetime, check: list[str], env: Mapping | None, timeout: float) -> int:
    """--clear-halt (spec 4.4): with a live parent, nothing (3). Else the engine's start checks run read-only (check +
    --check: `news-live --check`) and their output is printed; on 0 the halt is cleared under the parent's lock (0),
    else it stays (1). A check that has not answered within `timeout` seconds is killed and the halt stays (1;
    Ruling 41): a woken session must never hang on it."""
    parent = _live(paths.lock, "aitrader.supervise")
    if parent is not None:
        print(f"supervise: a live parent, pid {parent}: the halt stays", flush=True)
        return 3
    try:
        done = subprocess.run([*check, "--check"], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"supervise: the check did not answer within {timeout} s: the halt stays", flush=True)
        return 1
    except OSError as e:
        print(f"supervise: the check did not run ({type(e).__name__}): the halt stays", flush=True)
        return 1
    print(done.stdout, end="", flush=True)
    if done.returncode != 0:
        print(f"supervise: the check answered {done.returncode}: the halt stays", flush=True)
        return 1
    try:
        lock = take_lock(paths.lock, now)
        if lock is None:
            print(f"supervise: a parent, pid {_holder(paths.lock)}, took the lock: the halt stays", flush=True)
            return 3
        try:
            st = load_state(paths.state, now.astimezone(NY).date().isoformat())
            st.pop("load_error", None)  # ruling P18(c): never saved
            save_state(paths.state, {**st, "halt": None})
        finally:
            lock.close()
    except OSError as e:
        print(f"supervise: the halt was not cleared ({type(e).__name__})", flush=True)
        return 1
    print("supervise: the halt is cleared", flush=True)
    return 0


def main(argv: list[str] | None = None, *, child_cmd: list[str] | None = None, env: dict | None = None,
         clock=None, sleep=None) -> int:
    """The parent (spec 4.2): takes state/news_supervisor.lock, starts the engine (child_cmd, default
    `python3 -u -m aitrader news-live`, plus --until and --supervised <this pid>) and runs restart_core until it gives
    an answer. Returns 0 (end_of_day, closed_today), 3 (lock_held, or another parent holds the lock: it writes nothing),
    4, 5, 6 (halt), 75 (tripped), 76 (handover), 143 (signal, orphaned), 2 for a bad argument or config.
    clock() -> an aware UTC time (default now) answers the calendar questions only: the day, the session, --until, the
    handover times and the `t` of a row. Ages never read it, so a test or a drill can run the parent on a session
    morning on any day. SIGTERM, SIGINT and SIGHUP, or a change of its own parent pid, end it with a planned stop of the
    child; with --handover, so does handover_due, and the state file keeps {"at", "last_look"} for the next parent's
    first `up` (its handover_s). An episode a planned end cuts short gets its R1 then (ruling 37). Two lines go
    to stdout, the first and the last; the rest goes to .cache/supervise.log. The owner's lines (spec 8) go to
    alerts.ntfy_base_url with the topic of env (default os.environ), through a worker thread that the loop never waits
    for. --net-check asks ntfy's health once, prints what came back and returns 0 only on 200 (spec 6, "Not verified":
    that urllib reaches ntfy through the session's proxy and CA bundle).
    The forms of a woken session (spec 4.4) run no loop and need no --until: --status [--watchdog] prints status() as
    JSON and returns 0, and writes nothing; --relayed ID... (relay) and --clear-halt (clear_halt: it runs child_cmd,
    default `python3 -m aitrader news-live`, with --check, and clears the halt under the parent's lock) are its only
    two writers. They are one at a time, and --watchdog goes with --status only (else 2, argparse's refusal; ruling
    41). news-live --check reads ai-trader's state/ and takes no --state-dir, so --clear-halt with any other
    --state-dir clears nothing and returns 1 before the check (ruling 41)."""
    ppid = os.getppid()  # before anything else: what "orphaned" is measured against
    began = time.time()  # real time: up.sold of the first child counts the sales from here
    ap = argparse.ArgumentParser(prog="python3 -m aitrader.supervise")
    ap.add_argument("--until", help="HH:MM New York, handed to the engine (24:00 never comes); required but with"
                    " --net-check, --status, --clear-halt and --relayed")
    ap.add_argument("--handover", action="store_true", help="hand over before the harness's 2-hour cap")
    ap.add_argument("--state-dir", type=Path, help="state in DIR and logs in DIR/.cache (drills and tests)")
    ap.add_argument("--config", type=Path, help="this config.json (drills and tests)")
    ap.add_argument("--net-check", action="store_true", help="ask ntfy's health once; exit 0 only on 200")
    form = ap.add_mutually_exclusive_group()  # a woken session's forms, one at a time (Ruling 41)
    form.add_argument("--status", action="store_true", help="read-only: what a woken session does now, as JSON")
    form.add_argument("--clear-halt", action="store_true", help="clear the halt once news-live --check exits 0")
    form.add_argument("--relayed", nargs="+", metavar="ID", help="these unsent lines went out through the Claude app")
    ap.add_argument("--watchdog", action="store_true", help="with --status: the call is a watchdog slot's")
    try:
        a = ap.parse_args(argv)
        if a.watchdog and not a.status:
            ap.error("argument --watchdog: only with --status")
        once = a.net_check or a.status or a.clear_halt or bool(a.relayed)  # one answer, no loop and no --until
        if a.until is None and not once:
            ap.error("the following arguments are required: --until")
    except SystemExit as e:  # argparse has printed why
        return e.code if isinstance(e.code, int) else 2
    environ = os.environ if env is None else env
    try:
        cfg = load_cfg(a.config)
        sup, cal, base = cfg["supervisor"], cfg["calendar"], cfg["alerts"]["ntfy_base_url"]
        if a.net_check:  # nothing is published, and no topic is needed: the status, or the class of what went wrong
            got = deadman.Sender(base, None, sup["send_timeout_seconds"], env=environ, sync=True).health()
            print(f"supervise: net-check {got}", flush=True)
            return 0 if got == 200 else 1
        if not once and (not UNTIL.fullmatch(a.until)  # a bool is no number; a zero loop or grace would spin or kill
                         or any(isinstance(sup[k], bool) or not isinstance(sup[k], (int, float)) for k in NUMBERS)
                         or any(sup[k] <= 0 for k in POSITIVE)
                         or not all(HHMM.fullmatch(t) for t in sup["handover_times_ny"])):  # else the loop would raise
            raise ValueError("--until, or a number or the handover times of the supervisor block")
        if a.clear_halt and type(sup["clear_halt_check_timeout_seconds"]) not in (int, float):  # as NUMBERS: no bool
            raise ValueError("the check's timeout of the supervisor block")
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"supervise: a bad argument or config ({type(e).__name__})", file=sys.stderr)
        return 2
    state_dir = a.state_dir or ROOT / "state"
    cache_dir = state_dir / ".cache" if a.state_dir else ROOT / ".cache"
    paths, pid, clock = Paths(state_dir, cache_dir), os.getpid(), clock or (lambda: datetime.now(timezone.utc))
    if a.status:
        try:
            print(json.dumps(status(paths, cfg, clock(), watchdog=a.watchdog, environ=environ), ensure_ascii=False),
                  flush=True)
        except (KeyError, TypeError, ValueError) as e:  # a supervisor block without what --status reads
            print(f"supervise: a bad argument or config ({type(e).__name__})", file=sys.stderr)
            return 2
        return 0
    if a.relayed:
        return relay(paths, a.relayed, clock())
    if a.clear_halt:
        if state_dir.resolve() != (ROOT / "state").resolve():  # news-live --check reads ROOT's state/ only (Ruling 41)
            print(f"supervise: --clear-halt checks and clears {ROOT / 'state'} only (news-live --check has no"
                  " --state-dir): the halt stays", flush=True)
            return 1
        return clear_halt(paths, clock(), child_cmd or [sys.executable, "-m", "aitrader", "news-live"], env,
                          sup["clear_halt_check_timeout_seconds"])
    print(f"supervise: pid {pid}, until {a.until}, handover {'on' if a.handover else 'off'}", flush=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock = take_lock(paths.lock, clock())
    if lock is None:
        print(f"supervise: 3 lock_held pid {_holder(paths.lock)}. {AFTER}", flush=True)
        return 3
    log_file = open(paths.sup_log, "a", encoding="utf-8")
    topic = environ.get(cfg["alerts"].get("ntfy_topic_env", "AITRADER_NTFY_TOPIC"))
    sender = deadman.Sender(base, topic, sup["send_timeout_seconds"], env=environ)
    heard, earlier = [], {}
    if threading.current_thread() is threading.main_thread():  # Python lets no other thread set a handler
        earlier = {s: signal.signal(s, lambda signum, frame: heard.append(signum))
                   for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}

    def log(text: str) -> None:
        try:
            log_file.write(f"{_utc(clock())} {text}\n")
            log_file.flush()
        except OSError:  # a full disk: the parent goes on
            pass

    def emit(ev: str, now: datetime | None = None, **fields) -> None:
        try:
            append_row(paths.uptime, pid, ev, now or clock(), **fields)
        except OSError as e:  # spec 4.6: a log failure never stops the parent
            log(f"uptime.jsonl: a {ev} row was not written ({type(e).__name__})")

    try:
        now = clock()
        day = now.astimezone(NY).date()
        st = load_state(paths.state, day.isoformat())
        if "load_error" in st:  # ruling P18(c): the class name only; the key is never saved
            log(f"the state file could not be read ({st.pop('load_error')}): a new day's state")
        try:
            prune_rows(paths.uptime, sup["uptime_keep_days"], now)
            rows = read_rows(paths.uptime)
        except OSError as e:
            log(f"uptime.jsonl could not be read ({type(e).__name__})")
            rows = []
        prev = rows[-1] if rows else {}
        try:
            gap = round((now - datetime.fromisoformat(prev["t"])).total_seconds())
        except (KeyError, TypeError, ValueError):  # no row before this one, or no time that can be read
            gap = None
        cold = not paths.heartbeat.exists()
        emit("sup_start", now, until=a.until, handover=a.handover,
             timeout_ms=TWO_HOURS_MS if a.handover else sup["long_timeout_ms"], prev_t=prev.get("t"),
             prev_ev=prev.get("ev"), gap_s=gap, cold=cold)
        sup_t = datetime.fromisoformat(_utc(now))  # the sup_start row's t (ruling 36 g: a cold start with no stamp)
        log(f"start: pid {pid}, until {a.until}, handover {'on' if a.handover else 'off'}")
        today = [(t, r) for r in rows if (t := _when(r.get("t"))) is not None and t.astimezone(NY).date() == day]
        day_began = min((t for t, _ in today), default=now)  # R3 after the day's limit counts the minutes from here

        # What the loop has seen. mark: the clock time of the last mark. down_at / ended: when the last child ended, on
        # the injected clock (the exit row's t) and on the real one (time.time(), for up.sold). stale: the names of an
        # open stale-stops episode; r6: (its start, R6's {s}) when R6 went out. gap: what the first `up` of this parent
        # measures its outage from, until it has (R4, R4b). n: the day's last alert number (ruling P13: the log outlives
        # a parent). left: ntfy's last remainder, for the marks. last_child, codes (the exit codes since the last
        # healthy run), refused (when the lock refusals began), tripped: what the lines on the way out read. tick: the
        # last loop tick (time.time(), clock()); resumed: time.time() at the tick that ended a pause (ruling 49).
        seen = {"mark": None, "down_at": None, "ended": None, "stale": None, "r6": None,
                "gap": (prev, cold),
                "n": max((_alert_n(r) for _, r in today if r.get("ev") == "alert"), default=0),
                "left": None, "last_child": None, "codes": [], "refused": None, "tripped": {}, "tick": None,
                "resumed": None}
        # The restart episode (spec 8, R1): its falls, the `up` and `code` rows of its children, and the hang kill
        # that waits for the next `up` to be told by R2 (ruling P5).
        ep: dict = {"falls": [], "ups": [], "codes": [], "r2": None}
        pending: dict = {}  # alert id -> a line on its way: {row, payload, first, next (None: in flight), failed}
        counts = {"restarts_today": st["restarts_today"], "stamps": []}
        tz = sup["owner_tz"]

        def save() -> None:
            try:  # the counts so far: a parent that is killed keeps what it has saved
                save_state(paths.state, {**st, "restarts_today": counts["restarts_today"]})
            except OSError as e:
                log(f"the state file was not written ({type(e).__name__})")

        def row(line: dict, sent) -> dict:
            return {"id": line["id"], "kind": line["kind"], "sent": sent, "text": line["text"], **line["extra"]}

        def say(kind: str, now: datetime, extra: dict | None = None, **fields) -> None:
            """One line to the owner (spec 8), from ownerlines' table: {held} from {symbol: stop}, {sold} from trade
            rows. Its id is <kind>-<n>, n counting the day's alerts. Held back by may_send: an alert row "capped".
            With no topic nothing can ever be requested: an alert row `sent` false at once for the watchdog turn to
            relay, one log line, no retries (ruling 36 a). Else it goes to the worker, and drain writes its row when
            the outcome comes. extra: more fields of the row (R4 and R4b: `m`, ruling P6)."""
            try:
                if "held" in fields:
                    fields["held"] = ownerlines.held_text(fields["held"], sup["held_names_in_line"])
                if "sold" in fields:
                    fields["sold"] = ownerlines.sold_text([{"sym": r["symbol"], "stop": r["stop"], "fill": r["price"]}
                                                           for r in fields["sold"]], sup["held_names_in_line"])
                text = ownerlines.render(kind, max_bytes=sup["max_line_bytes"], free_chars=sup["free_text_max_chars"],
                                         **fields)
            except (KeyError, ValueError, TypeError, AttributeError) as e:  # a beat or a book it cannot be built from
                log(f"line {kind} not built ({type(e).__name__})")
                return
            seen["n"] += 1
            line = {"id": f"{kind}-{seen['n']}", "kind": kind, "text": text, "extra": extra or {}}
            go = may_send(st, kind, now, sup["max_alerts_per_hour"])
            save()  # the hour's counts survive this parent (spec 8)
            if not go:
                emit("alert", now, **row(line, "capped"))
                log(f"line {line['id']}: capped")
                return
            if not topic:
                emit("alert", now, **row(line, False))
                log(f"line {line['id']}: no topic")
                return
            pending[line["id"]] = {"row": line, "first": time.monotonic(), "next": None, "failed": False,
                                   "payload": {"title": TITLE, "message": text,
                                               "priority": deadman.PRIORITY[ownerlines.priority(kind)]}}
            sender.publish(pending[line["id"]]["payload"], line["id"])

        def drain(now: datetime, retry: bool = True) -> None:
            """The outcomes the worker brought back: an alert row `sent` true, or `sent` false at a line's first
            failure; then a try again every alert_retry_seconds for alert_retry_minutes, and a late success adds a row
            with the same id. The log gets a status code or an exception's class, never a URL or a message."""
            mono = time.monotonic()
            for r in sender.results():
                p = pending.get(r["tag"])
                if p is None:
                    continue
                seen["left"] = seen["left"] if r["left"] is None else r["left"]
                log(f"line {r['tag']}: {r['status'] or r['error'] or 'no topic'}")
                if r["ok"] or not p["failed"]:
                    emit("alert", now, **row(p["row"], r["ok"]))
                if r["ok"] or mono - p["first"] >= sup["alert_retry_minutes"] * 60:
                    del pending[r["tag"]]
                else:
                    p["failed"], p["next"] = True, mono + sup["alert_retry_seconds"]
            for tag, p in pending.items():
                if retry and p["next"] is not None and p["next"] <= mono:
                    p["next"] = None
                    sender.publish(p["payload"], tag)

        def finish() -> None:
            """On the way out: send_timeout_seconds for the lines in flight (ruling P18(b)), then a row `sent` false
            for each that had no outcome, so that the next watchdog turn relays it."""
            end = time.monotonic() + sup["send_timeout_seconds"]
            drain(clock(), retry=False)
            while any(p["next"] is None for p in pending.values()) and time.monotonic() < end:
                (sleep or time.sleep)(min(sup["loop_seconds"], max(0.0, end - time.monotonic())))
                drain(clock(), retry=False)
            for p in pending.values():
                if not p["failed"]:
                    emit("alert", clock(), **row(p["row"], False))

        if closed_day(day, cal):
            rc, word = 0, "closed_today"
        else:
            cmd = list(child_cmd or [sys.executable, "-u", "-m", "aitrader", "news-live"])
            cmd += ["--until", a.until, "--supervised", str(pid)]
            kid: dict = {}  # the child that runs now (spawn sets it)
            started_ny = now.astimezone(NY)  # what handover_due measures this parent's legs from

            def spawn() -> subprocess.Popen:
                before = _read_beat(paths.heartbeat)[0] or {}  # the engine before this one: its last look ends there
                looks = list(_looks(before).values()) or [_when(before.get("stops_checked_at"))]
                kid.update(started=time.time(), last_look=None if None in looks else min(looks),
                           held_before=set(_held(before)), up=False, code=False, hang=None, hang_said=False)
                # From the main thread: the kernel ties the child's PR_SET_PDEATHSIG to the thread that started it.
                with open(paths.engine_log, "ab") as out:  # the child keeps a descriptor of its own
                    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                            stderr=subprocess.STDOUT, start_new_session=True)

            def watch(child, ran_s):
                if counts["restarts_today"] != st["restarts_today"]:  # the core has just counted a restart: on disk at
                    st["restarts_today"] = counts["restarts_today"]  # once, so a parent killed in the back-off keeps it
                    save()                                           # (ruling 36 b)
                if heard:
                    return "signal"
                if os.getppid() != ppid:
                    return "orphaned"
                if a.handover and handover_due(started_ny, clock().astimezone(NY), sup["handover_times_ny"],
                                               sup["min_leg_minutes"], sup["max_leg_minutes"]):
                    return "handover"
                return look(child, ran_s)

            def paused(child, last: tuple, wall: float, now: datetime) -> None:
                """Ruling 49: more than hang_seconds between two of this parent's own ticks (wall: time.time()), so the
                machine paused the parent and its child together; that is no hang. One row `pause`: its start (the
                tick before, on the clock rows are written on), its seconds and the child. look judges no hang on the
                child's beat until hang_seconds after this tick. With outage_report_seconds or more of market-open
                seconds in it, R4 for it, from its start to now, built by gap_line."""
                start = _utc(last[1])
                emit("pause", now, start=start, s=round(wall - last[0], 1), child=child.pid if child else None)
                seen["resumed"] = wall
                line = gap_line({"t": start, "ev": "pause"}, now, False, cal, sup)
                if line:
                    say(line[0], now, extra={"m": line[1]["m"]}, held=_held_now(paths, child.pid if child else None),
                        **line[1])

            def look(child, ran_s):
                """One loop tick's reading of the heartbeat (spec 4.3, 4.6): the lines' outcomes, R7, the mark of a new
                clock minute, and for the running child its `up` and `code` rows, stale stops, the end of a restart
                episode and a hang, with the owner's line of each (spec 8). Returns "hang" when the child is to be
                killed, else None."""
                hb, mtime = _read_beat(paths.heartbeat)
                wall = time.time()  # the beat's age and the gap between ticks are read on it, never on clock()
                view, now = beat_view(hb, mtime, child.pid if child else None, wall), clock()
                mine = view["mine"]
                last, seen["tick"] = seen["tick"], (wall, now)
                if last is not None and wall - last[0] > sup["hang_seconds"]:
                    paused(child, last, wall, now)
                drain(now)
                hour = st["alerts"] if isinstance(st.get("alerts"), dict) else {}
                if hour.get("capped") and hour.get("hour") != _hour(now):  # an hour that had capped lines has ended
                    say("R7", now, n=hour["capped"], cap=sup["max_alerts_per_hour"], r=counts["restarts_today"])
                if mark_due(seen["mark"], now):
                    seen["mark"] = now
                    emit("mark", now, hb=round(view["age_s"], 1) if mine else None,
                         stop=None if view["stop_age_s"] is None else round(view["stop_age_s"], 1),
                         n=len(view["held"]) if mine else None, open=view["open"], blind=view["blind"], dm=None,
                         left=seen["left"])
                if child is None:
                    return None
                if mine and not kid["up"] and (not view["open"] or first_look_done(hb, child.pid, kid["started"])):
                    kid["up"] = True
                    up(child, hb, view, now)
                code = hb.get("code") if mine else None
                if not kid["code"] and isinstance(code, dict) and code.get("commit"):
                    kid["code"] = True
                    changed = st["last_commit"] is not None and code["commit"] != st["last_commit"]
                    st["last_commit"] = code["commit"]
                    save()  # the commit outlives this parent; saved before the row, so a reader of the row finds it saved
                    code_row = {"child": child.pid, "commit": code["commit"], "dirty": code.get("dirty"),
                                "code_changed": changed}
                    emit("code", now, **code_row)
                    if ep["falls"]:
                        ep["codes"].append(code_row)
                if mine and view["age_s"] <= sup["hang_seconds"]:  # a fresh beat: what it says about the stops
                    ages = _stamp_ages(hb, view["age_s"]) if view["open"] else {}
                    born = wall - kid["started"]  # ruling 48: an unknown stamp's age counts from this child's start
                    names = sorted(s for s, a in ages.items()
                                   if (born if a is None else a) > sup["stops_stale_seconds"])
                    stop_s = None if view["stop_age_s"] is None else round(view["stop_age_s"], 1)
                    if names and not seen["stale"]:
                        seen["stale"] = names
                        emit("stale_stops", now, what="start", names=names, stop=stop_s)
                        if not set(names) <= set(view["blind"]):  # else the engine's blind-quote alert owns it
                            s = round(stop_s if stop_s is not None else time.time() - kid["started"])
                            seen["r6"] = (now, s)
                            say("R6", now, s=s, names=", ".join(names), held=view["held"])
                    elif not names and seen["stale"]:
                        emit("stale_stops", now, what="end", names=seen["stale"], stop=stop_s)
                        seen["stale"] = None
                        if seen["r6"]:
                            (t, s), seen["r6"] = seen["r6"], None
                            say("R6b", now, s=round(s + (now - t).total_seconds()))
                if ep["falls"] and kid["up"] and ran_s >= sup["healthy_seconds"]:  # the episode is over: R1
                    episode_end(now)
                # A hang: this child's beat is older than hang_seconds, or it has none after start_grace_seconds. After
                # a pause of the whole machine its beat is not judged until hang_seconds after the resume (ruling 49).
                if mine and seen["resumed"] is not None and wall - seen["resumed"] < sup["hang_seconds"]:
                    return None
                if not (view["age_s"] > sup["hang_seconds"] if mine else ran_s > sup["start_grace_seconds"]):
                    kid["hang_said"] = False
                    return None
                kid["hang"] = {"hb": round(view["age_s"] if mine else ran_s, 1), "phase": view["phase"]}
                if sup.get("hang_kill_enabled") is True:
                    return "hang"
                if not kid["hang_said"]:  # the switch off: one row per hang, and nothing is signalled
                    kid["hang_said"] = True
                    emit("hang", now, child=child.pid, **kid["hang"], killed_with="none")
                    log(f"child {child.pid} hangs ({kid['hang']['hb']} s without a beat): not killed, the switch is"
                        " off")
                    say("R2", now, off=True, s=kid["hang"]["hb"], held=_held_now(paths, child.pid))
                return None

            def episode_end(now: datetime) -> None:
                """R1, once for the episode however many falls (spec 8): the time and cause of its first fall, down_s
                to its last `up`, the blind seconds of all its `up` rows, what they sold, new code, the day's restarts.
                No R1 when a hang kill was its only fall: R2 told it at the restart (ruling P5)."""
                falls, ups = ep["falls"], ep["ups"]
                if not (len(falls) == 1 and falls[0]["hang"]):
                    last, changed = ups[-1], [c for c in ep["codes"] if c["code_changed"]]
                    say("R1", now, time=ownerlines.hhmm(falls[0]["t"], tz, seconds=True),
                        cause=ownerlines.WORDS["cause"][falls[0]["cause"]],
                        down_s=round((last["t"] - falls[0]["t"]).total_seconds(), 1),
                        falls=ownerlines.PARTS["R1.falls"].format(k=len(falls)) if len(falls) > 1 else "",
                        blind_s=round(sum(u["blind_s"] for u in ups), 1), held=last["held"],
                        sold=[r for u in ups for r in u["sold"] or []],
                        code=ownerlines.PARTS["R1.code"].format(commit=changed[-1]["commit"]) if changed else "",
                        n=counts["restarts_today"])
                ep.update(falls=[], ups=[], codes=[], r2=None)

            def up(child, hb: dict, view: dict, now: datetime) -> None:
                """The row `up` (spec 4.6): what the restart cost, at this child's first beat that has looked at its
                stops (with the market closed: its first beat); after a handover, at this parent's first, also what the
                handover cost (handover_s)."""
                at, blind = _when(hb.get("at")), view["blind"]
                # the first look after, per held name: this child's own stamp; for a blind or unlooked name, the beat.
                # A name the child before held that this beat no longer holds was sold by the first look: the beat too.
                looks = _looks(hb)
                after = [at if s in blind or t is None or t.timestamp() < kid["started"] else t
                         for s, t in looks.items()]
                if kid["held_before"].difference(looks):
                    after.append(at)
                # cold: the stamp the engine adopted; with none at all, this parent's start (ruling 36 g: the time
                # before the parent is the gap R4 measures), so a name held is never shown as protected
                last = kid["last_look"] or _when(hb.get("stops_checked_at")) or sup_t
                blind_s = round(open_seconds(last, max(after), cal), 1) if after and None not in after else 0
                # The parent before handed over (spec 4.5): from its last look to this first look, beat to beat when
                # nothing is held or the market was closed. Only this parent's first `up` gets it: it is cleared and
                # saved at once.
                ho = st.get("handover")
                ho_look = _when(ho.get("last_look")) if isinstance(ho, dict) else None
                first = None if None in after else max(after, default=at)
                handover_s = None if None in (ho_look, first) else round((first - ho_look).total_seconds(), 1)
                if ho is not None:
                    st["handover"] = None
                    save()
                ref = int(seen["ended"] if seen["ended"] is not None else began)  # ruling P14: the whole second
                try:
                    sold = [r for r in read_rows(paths.trades) if r.get("side") == "SELL"
                            and (t := _when(r.get("logged_at"))) is not None and t.timestamp() >= ref]
                except OSError as e:
                    log(f"news_trades.jsonl could not be read ({type(e).__name__})")
                    sold = None
                down = seen["down_at"]
                up_row = {"child": child.pid, "down_from": None if down is None else _utc(down),
                          "down_s": None if down is None else round((now - down).total_seconds(), 2),
                          "blind_s": blind_s, "handover_s": handover_s, "held": view["held"], "blind": blind,
                          "commit": None, "dirty": None, "code_changed": None, "sold": sold}
                emit("up", now, **up_row)
                if ep["falls"]:
                    ep["ups"].append({**up_row, "t": now})
                if ep["r2"] is not None:  # ruling P5: a hang kill is told at the restart, with its time and blind_s
                    say("R2", now, s=ep["r2"], time=ownerlines.hhmm(now, tz, seconds=True), blind_s=blind_s,
                        held=view["held"])
                    ep["r2"] = None
                if seen["gap"] is not None:  # this parent's first `up`: the outage before it, if any (R4, R4b)
                    (prev_row, was_cold), seen["gap"] = seen["gap"], None
                    line = gap_line(prev_row, now, was_cold, cal, sup)
                    if line:
                        say(line[0], now, extra={"m": line[1]["m"]}, held=view["held"], **line[1])

            def stop(child, how: str) -> None:
                """A hang stop (spec 4.3): SIGTERM to the child's process group, up to hang_term_grace_seconds for the
                child to end, then SIGKILL to the group whether or not it has (what it started may ignore SIGTERM;
                ruling 36 f), then the row `hang`: killed_with "TERM" when the child ended within the grace, else
                "KILL". A planned stop (spec 5.3): SIGTERM to the child's pid alone, so that a scorer call in flight can
                finish, planned_stop_grace_seconds, then SIGKILL to its process group."""
                if how == "hang":
                    _signal_group(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=sup["hang_term_grace_seconds"])
                        killed = "TERM"
                    except subprocess.TimeoutExpired:
                        killed = "KILL"
                    _signal_group(child.pid, signal.SIGKILL)
                    child.wait()
                    emit("hang", child=child.pid, **kid["hang"], killed_with=killed)
                    log(f"child {child.pid} hangs ({kid['hang']['hb']} s without a beat): its group got SIG{killed}")
                    return
                child.send_signal(signal.SIGTERM)  # nothing, when the child has already ended
                try:
                    child.wait(timeout=sup["planned_stop_grace_seconds"])
                except subprocess.TimeoutExpired:
                    log(f"child {child.pid} did not end within {sup['planned_stop_grace_seconds']} s of SIGTERM:"
                        " SIGKILL to its process group")
                    _signal_group(child.pid, signal.SIGKILL)
                    child.wait()

            def core_emit(ev: str, **fields) -> None:
                now = clock()
                if ev == "tripped":
                    st["trips_today"] += 1
                    fields["trips_today"] = st["trips_today"]
                    seen["tripped"] = fields
                if ev == "exit":
                    seen.update(down_at=now, ended=time.time(), last_child=fields["child"])
                    refused = fields["why"] == "exit" and fields["rc"] == 3  # another engine holds the book: no fall
                    seen["refused"] = (seen["refused"] or time.monotonic()) if refused else None
                    healthy = fields["ran_s"] >= sup["healthy_seconds"]
                    seen["codes"] = [] if healthy else [*seen["codes"], fields["rc"]]
                    if not refused and fields["why"] != "planned":
                        fall(now, fields)
                emit(ev, now, **fields)

            def fall(now: datetime, fields: dict) -> None:
                """A fall of the child, for R1: its time and its cause (a code, or no child at all: "crash"; a signal or
                a hang kill: "killed"; 0 or 143: "stopped"). A hang kill waits for the next `up` to be told by R2
                (ruling P5)."""
                hang = fields["why"] == "hang"
                cause = ("killed" if hang or fields["signal"] is not None else "stopped" if fields["rc"] in (0, 143)
                         else "crash")
                ep["falls"].append({"t": now, "cause": cause, "hang": hang})
                if hang:
                    ep["r2"] = kid["hang"]["hb"]

            def at_until() -> bool:
                return near_until(clock().astimezone(NY), a.until, sup["end_of_day_slack_seconds"])

            rc, word = restart_core(spawn, watch, stop, at_until, core_emit, sup, counts, sleep=sleep or time.sleep)
            st["restarts_today"] = counts["restarts_today"]
            # Ruling 37: a planned end cuts an open episode short of its healthy run. Its R1 goes out now when a child
            # came up after the episode's last fall; else nothing more is said here (the handover gap measures it).
            if word in PLANNED and ep["ups"] and ep["ups"][-1]["t"] > ep["falls"][-1]["t"]:
                episode_end(clock())
            if word == "halt":
                st["halt"] = {"code": rc, "why": HALT_WHY[rc], "at": _utc(clock())}
            elif word == "handover":  # the next parent's first `up` measures handover_s from last_look (spec 4.5)
                # the last beat: its oldest stop look; its `at` if none held, or with the market closed, when no stop is
                # looked at and the next `up` takes its own first beat (review F2: else yesterday's adopted stamp)
                hb = _read_beat(paths.heartbeat)[0] or {}
                looks = [] if hb.get("market_open") is False else list(_looks(hb).values())
                looks = looks or [_when(hb.get("at"))]
                st["handover"] = {"at": _utc(clock()), "last_look": None if None in looks else _utc(min(looks))}
        if word == "crash_loop":  # R3, R3b at the second trip of the day, then nothing (spec 4.3; ruling P9)
            trip = seen["tripped"]
            kind = {1: "R3c" if seen["codes"] and set(seen["codes"]) == {7} else "R3", 2: "R3b"}.get(st["trips_today"])
            if kind:
                minutes = trip["window_s"] / 60 if trip.get("window_s") else (clock() - day_began).total_seconds() / 60
                say(kind, clock(), k=trip.get("restarts", 0) + 1, m=max(1, round(minutes)),
                    held=_held_now(paths, seen["last_child"]))
        elif word == "halt":
            say({4: "R5a", 5: "R5b", 6: "R5d"}[rc], clock(), held=_held_now(paths, seen["last_child"]))
        elif word == "lock_held":
            say("R5c", clock(), s=round(time.monotonic() - (seen["refused"] or time.monotonic())))
        finish()  # the lines' rows come before sup_stop: the row before the next sup_start is the sup_stop
        emit("sup_stop", why=word, rc=rc)
        try:
            save_state(paths.state, st)
        except OSError as e:
            log(f"the state file was not written ({type(e).__name__})")
        log(f"end: {rc} {word}")
        holder = f" pid {_holder(paths.engine_lock)}" if word == "lock_held" else ""
        print(f"supervise: {rc} {SAID.get(word, word)}{holder}. {AFTER}", flush=True)
        return rc
    finally:
        for s, handler in earlier.items():  # None: a handler that was not set from Python cannot be named here
            signal.signal(s, signal.SIG_DFL if handler is None else handler)
        sender.close()
        log_file.close()
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
