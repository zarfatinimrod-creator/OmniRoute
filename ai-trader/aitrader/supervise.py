"""The supervisor's parent process (supervisor spec 2026-11-10, section 4): it starts the news engine, restarts it,
and keeps the uptime log. So far (Tasks 10-12): its foundations (the config, its own trading calendar, the uptime log,
the state file and its lock), the restart core, the loop that runs it, and what the loop reads in the heartbeat (a mark
a minute, `up` and `code` at a child's first looks, a hang, stale stops):

    python3 -u -m aitrader.supervise --until HH:MM [--handover] [--state-dir DIR] [--config FILE]

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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import IO
from zoneinfo import ZoneInfo

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
    - Any other end is a crash, among them a 7 (the exit row says "tree_busy"), a signal, a 0 far from --until and a
      143 nobody asked for (not in the spec's table: counted, so the trip bounds it). Started again at once after a run
      of healthy_seconds or more, else after the back-off: backoff_first_seconds, doubling up to backoff_max_seconds,
      and from the first again after a healthy run. When one more restart would pass max_restarts in
      restart_window_seconds, or max_restarts_day: a tripped row and (75, "crash_loop").
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
        child = spawn()
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


TWO_HOURS_MS = 7_200_000  # the harness's cap on a background command (spec 4.5): a fact of the platform, not a tuning
HALT_WHY = {4: "chain", 5: "calendar", 6: "book"}  # the state file's halt.why for the engine's code
SAID = {"crash_loop": "tripped"}  # the word of the last stdout line, where it is not the sup_stop row's why
AFTER = "Run python3 -m aitrader.supervise --status and do what action says."
UNTIL = re.compile(r"([01]\d|2[0-3]):[0-5]\d|24:00")
NUMBERS = ("loop_seconds", "healthy_seconds", "backoff_first_seconds", "backoff_max_seconds", "max_restarts",
           "restart_window_seconds", "max_restarts_day", "lock_wait_seconds", "planned_stop_grace_seconds",
           "end_of_day_slack_seconds", "uptime_keep_days", "long_timeout_ms", "hang_seconds", "start_grace_seconds",
           "hang_term_grace_seconds", "stops_stale_seconds")  # what main and the core read


def _holder(lock: Path):
    """The pid that a lock's holder wrote into the lock file; "unknown" when the file does not say."""
    try:
        return json.loads(lock.read_text(encoding="utf-8"))["pid"]
    except Exception:  # noqa: BLE001 - the text is a hint only
        return "unknown"


def main(argv: list[str] | None = None, *, child_cmd: list[str] | None = None, env: dict | None = None,
         clock=None, sleep=None) -> int:
    """The parent (spec 4.2): takes state/news_supervisor.lock, starts the engine (child_cmd, default
    `python3 -u -m aitrader news-live`, plus --until and --supervised <this pid>) and runs restart_core until it gives
    an answer. Returns 0 (end_of_day, closed_today), 3 (lock_held, or another parent holds the lock: it writes nothing),
    4, 5, 6 (halt), 75 (tripped), 76 (handover), 143 (signal, orphaned), 2 for a bad argument or config.
    clock() -> an aware UTC time (default now) answers the calendar questions only: the day, the session, --until and
    the `t` of a row. Ages never read it, so a test or a drill can run the parent on a session morning on any day.
    SIGTERM, SIGINT and SIGHUP, or a change of its own parent pid, end it with a planned stop of the child. Two lines go
    to stdout, the first and the last; the rest goes to .cache/supervise.log."""
    ppid = os.getppid()  # before anything else: what "orphaned" is measured against
    began = time.time()  # real time: up.sold of the first child counts the sales from here
    ap = argparse.ArgumentParser(prog="python3 -m aitrader.supervise")
    ap.add_argument("--until", required=True, help="HH:MM New York, handed to the engine (24:00 never comes)")
    ap.add_argument("--handover", action="store_true", help="hand over before the harness's 2-hour cap")
    ap.add_argument("--state-dir", type=Path, help="state in DIR and logs in DIR/.cache (drills and tests)")
    ap.add_argument("--config", type=Path, help="this config.json (drills and tests)")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:  # argparse has printed why
        return e.code if isinstance(e.code, int) else 2
    try:
        cfg = load_cfg(a.config)
        sup, cal = cfg["supervisor"], cfg["calendar"]
        if not UNTIL.fullmatch(a.until) or not all(isinstance(sup[k], (int, float)) for k in NUMBERS):
            raise ValueError("--until or a number of the supervisor block")
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"supervise: a bad argument or config ({type(e).__name__})", file=sys.stderr)
        return 2
    state_dir = a.state_dir or ROOT / "state"
    cache_dir = state_dir / ".cache" if a.state_dir else ROOT / ".cache"
    paths, pid, clock = Paths(state_dir, cache_dir), os.getpid(), clock or (lambda: datetime.now(timezone.utc))
    print(f"supervise: pid {pid}, until {a.until}, handover {'on' if a.handover else 'off'}", flush=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    lock = take_lock(paths.lock, clock())
    if lock is None:
        print(f"supervise: 3 lock_held pid {_holder(paths.lock)}. {AFTER}", flush=True)
        return 3
    log_file = open(paths.sup_log, "a", encoding="utf-8")
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
        emit("sup_start", until=a.until, handover=a.handover,
             timeout_ms=TWO_HOURS_MS if a.handover else sup["long_timeout_ms"], prev_t=prev.get("t"),
             prev_ev=prev.get("ev"), gap_s=gap, cold=not paths.heartbeat.exists())
        log(f"start: pid {pid}, until {a.until}, handover {'on' if a.handover else 'off'}")
        # A weekday of a year the calendar does not list is no closed day, though session_hours fails it closed: the
        # engine's start check refuses it with its urgent line and 5, and the parent halts on that 5 (spec 4.3).
        if session_hours(day, cal) is None and (day.weekday() >= 5 or day.year in cal.get("years", [])):
            rc, word = 0, "closed_today"
        else:
            cmd = list(child_cmd or [sys.executable, "-u", "-m", "aitrader", "news-live"])
            cmd += ["--until", a.until, "--supervised", str(pid)]

            # What the loop has seen. mark: the clock time of the last mark. down_at / ended: when the last child
            # ended, on the injected clock (the exit row's t) and on the real one (time.time(), for up.sold).
            # stale: the names of an open stale-stops episode. kid: the child that runs now (spawn sets it).
            seen = {"mark": None, "down_at": None, "ended": None, "stale": None}
            kid: dict = {}

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
                if heard:
                    return "signal"
                if os.getppid() != ppid:
                    return "orphaned"
                return look(child, ran_s)

            def look(child, ran_s):
                """One loop tick's reading of the heartbeat (spec 4.3, 4.6): the mark of a new clock minute, and for the
                running child its `up` and `code` rows, stale stops and a hang. Returns "hang" when the child is to be
                killed, else None."""
                hb, mtime = _read_beat(paths.heartbeat)
                view, now = beat_view(hb, mtime, child.pid if child else None, time.time()), clock()
                mine = view["mine"]
                if mark_due(seen["mark"], now):
                    seen["mark"] = now
                    emit("mark", now, hb=round(view["age_s"], 1) if mine else None,
                         stop=None if view["stop_age_s"] is None else round(view["stop_age_s"], 1),
                         n=len(view["held"]) if mine else None, open=view["open"], blind=view["blind"], dm=None,
                         left=None)
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
                    emit("code", now, child=child.pid, commit=code["commit"], dirty=code.get("dirty"),
                         code_changed=changed)
                    try:  # the commit outlives this parent (R1 and the next parent compare with it)
                        save_state(paths.state, {**st, "restarts_today": counts["restarts_today"]})
                    except OSError as e:
                        log(f"the state file was not written ({type(e).__name__})")
                if mine and view["age_s"] <= sup["hang_seconds"]:  # a fresh beat: what it says about the stops
                    ages = _stamp_ages(hb, view["age_s"]) if view["open"] else {}
                    names = sorted(s for s, a in ages.items() if a is None or a > sup["stops_stale_seconds"])
                    stop_s = None if view["stop_age_s"] is None else round(view["stop_age_s"], 1)
                    if names and not seen["stale"]:
                        seen["stale"] = names
                        emit("stale_stops", now, what="start", names=names, stop=stop_s)
                    elif not names and seen["stale"]:
                        emit("stale_stops", now, what="end", names=seen["stale"], stop=stop_s)
                        seen["stale"] = None
                # A hang: this child's beat is older than hang_seconds, or it has none after start_grace_seconds
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
                return None

            def up(child, hb: dict, view: dict, now: datetime) -> None:
                """The row `up` (spec 4.6): what the restart cost, at this child's first beat that has looked at its
                stops (with the market closed: its first beat)."""
                at, blind = _when(hb.get("at")), view["blind"]
                # the first look after, per held name: this child's own stamp; for a blind or unlooked name, the beat.
                # A name the child before held that this beat no longer holds was sold by the first look: the beat too.
                looks = _looks(hb)
                after = [at if s in blind or t is None or t.timestamp() < kid["started"] else t
                         for s, t in looks.items()]
                if kid["held_before"].difference(looks):
                    after.append(at)
                last = kid["last_look"] or _when(hb.get("stops_checked_at"))  # cold: the stamp the engine adopted
                blind_s = (round(open_seconds(last, max(after), cal), 1)
                           if after and None not in after and last is not None else 0)
                ref = int(seen["ended"] if seen["ended"] is not None else began)  # ruling P14: the whole second
                try:
                    sold = [r for r in read_rows(paths.trades) if r.get("side") == "SELL"
                            and (t := _when(r.get("logged_at"))) is not None and t.timestamp() >= ref]
                except OSError as e:
                    log(f"news_trades.jsonl could not be read ({type(e).__name__})")
                    sold = None
                down = seen["down_at"]
                emit("up", now, child=child.pid, down_from=None if down is None else _utc(down),
                     down_s=None if down is None else round((now - down).total_seconds(), 2), blind_s=blind_s,
                     handover_s=None, held=view["held"], blind=blind, commit=None, dirty=None, code_changed=None,
                     sold=sold)

            def stop(child, how: str) -> None:
                """A hang stop (spec 4.3): SIGTERM to the child's process group, hang_term_grace_seconds, SIGKILL to
                the group, then the row `hang`. A planned stop (spec 5.3): SIGTERM to the child's pid alone, so that a
                scorer call in flight can finish, planned_stop_grace_seconds, then SIGKILL to its process group.
                The group is signalled only while the child is not reaped: its id is still the child's."""
                if how == "hang":
                    killed = "TERM"
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        child.wait(timeout=sup["hang_term_grace_seconds"])
                    except subprocess.TimeoutExpired:
                        killed = "KILL"
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
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
                    try:
                        os.killpg(child.pid, signal.SIGKILL)  # not reaped yet, so the group is still the child's
                    except ProcessLookupError:
                        pass
                    child.wait()

            def core_emit(ev: str, **fields) -> None:
                now = clock()
                if ev == "tripped":
                    st["trips_today"] += 1
                    fields["trips_today"] = st["trips_today"]
                if ev == "exit":
                    seen.update(down_at=now, ended=time.time())
                emit(ev, now, **fields)

            def at_until() -> bool:
                return near_until(clock().astimezone(NY), a.until, sup["end_of_day_slack_seconds"])

            counts = {"restarts_today": st["restarts_today"], "stamps": []}
            rc, word = restart_core(spawn, watch, stop, at_until, core_emit, sup, counts, sleep=sleep or time.sleep)
            st["restarts_today"] = counts["restarts_today"]
            if word == "halt":
                st["halt"] = {"code": rc, "why": HALT_WHY[rc], "at": _utc(clock())}
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
        log_file.close()
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
