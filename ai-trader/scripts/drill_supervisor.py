#!/usr/bin/env python3
"""The supervisor's drills (supervisor spec 11.1; the pass marks of rollout step 2, spec 11.2), each on temporary
directories of its own with stub children: tests/helpers/dummy_child.py, tests/helpers/engine_child.py behind its
tripwire, and a NtfyStub on 127.0.0.1. Nothing here reaches the phone, the network, the model or the live state.

    python3 scripts/drill_supervisor.py DRILL... [--fast] [--rounds N]      DRILL: a b c d e f g all
    python3 scripts/drill_supervisor.py cloud DIR [--fast]
    python3 scripts/drill_supervisor.py cloud-check [--alive] DIR

A drill prints `PASS <drill> <numbers>` or `FAIL <drill> <why>` (a failed drill keeps its files and says where); the
exit code is 0 only when every drill passed. Without --fast the numbers are those of config.json; --fast scales them and
keeps their order (FAST). Each drill has its own state directories, config copies and locks. The parents' clock is moved
onto a session morning (MORNING), so a drill runs on any day; every child is started with --until 24:00, which never
comes (ruling P1, controller ruling 16).
  a  6 kill -9 of the dummy child, each more than healthy_seconds after the last and spread over more than
     restart_window_seconds; then one of the engine child holding 3 names, under a parent and a state directory of its
     own (ruling P3). Pass: every replacement beats within 1 s of its kill, the engine's first look stamps each held
     name within 3 s, no trip, one R1 per kill.
  b  kill -STOP of the child, the kill switch on. Pass: replaced within hang_seconds + 10 s, one hang row, one R2 and
     no R1 (ruling P5).
  c  a child that always exits 1. Pass: max_restarts restarts, one tripped row, one R3, the parent returns 75.
  d  kill -9 of the parent while the engine child sits in a 30 s scorer stub, and a new parent at once. Pass: nothing of
     the old tree is left, an engine beats within 5 s, no R5c.
  e  --rounds times: kill -9 at a random moment of an engine child that trades on stubs, then a start. Pass: the news
     chains verify after every kill, and wherever the kill left the book disagreeing with the journal's last row the
     next start says so (ruling P4).
  f  quote stubs of 60 s (2 s under --fast) with 3 held names (ruling P2). Pass: one stale_stops start row, one R6, no
     kill.
  g  Task 5's loop: 50 engine starts beside 20 fetch-and-merge rounds, on a temporary repository with a temporary bare
     remote. Pass: book and chains as they were, every start returned 0 or 7.
  cloud DIR                 not part of all: this process becomes a parent with the dummy child on state directory DIR,
                            in the foreground, for a session to launch as a tracked background command.
  cloud-check --alive DIR   while that parent runs (90 s after its launch): a live process holds DIR's parent lock, the
                            log has a mark row and no sup_stop.
  cloud-check DIR           after it was stopped from outside: no process of DIR left, both locks free, a new parent's
                            child beats within 30 s.
It is also run by hand, in a session whose environment may hold the owner's topic: guard() drops the phone variables
before anything else is imported or started.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

AT = Path(__file__).resolve().parents[1]  # ai-trader/
DUMMY = AT / "tests" / "helpers" / "dummy_child.py"
ENGINE = AT / "tests" / "helpers" / "engine_child.py"
PHONE_VARS = ("AITRADER_NTFY_TOPIC", "AITRADER_TELEGRAM_TOKEN", "AITRADER_TELEGRAM_CHAT")  # tests/helpers/no_phone.py's
LOCAL = "http://127.0.0.1"  # the ntfy address of every config copy here, before its port: a NtfyStub, or nobody (DEAD)
DEAD = 9  # the port of a config copy whose parent has no topic and so sends nothing (cloud): nobody listens there
TOPIC = "drill-made-up-topic"  # the parents' lines go with it to the NtfyStub; never the owner's topic
NY = ZoneInfo("America/New_York")
MORNING = datetime(2026, 11, 12, 10, 0, tzinfo=NY)  # a session morning, Thursday: the parents' clock starts here
UNTIL = "24:00"  # the end every child gets: it never comes, so the real New York clock never ends a drill
# --fast: config.json's numbers scaled, their order kept. The back-off is scaled too: at 1, 2, 4, 8 s the five quick
# crashes of drill c would never fall inside a 10 s window, and the loop would never trip. The parent's tick is scaled
# as well: at 0.5 s a dead engine is seen up to 0.5 s late and a new one takes about 0.45 s to beat, which leaves the
# 1 s mark of drill a to chance (0.57 to 0.91 s measured); the real numbers keep 0.5 s.
FAST = {"healthy_seconds": 2, "restart_window_seconds": 10, "hang_seconds": 4, "stops_stale_seconds": 3,
        "backoff_first_seconds": 0.1, "backoff_max_seconds": 2, "loop_seconds": 0.05}
# The pass marks of rollout step 2 (spec 11.2) and the sizes of the drills (spec 11.1; rulings P2, P3).
BEAT_S = 1  # a restart's first heartbeat, from the kill
LOOK_S = 3  # and its first stop look
HANG_EXTRA_S = 10  # the frozen child replaced within hang_seconds + this
ENGINE_UP_S = 5  # d: an engine beat within this of the parent's kill
CLOUD_BEAT_S = 30  # cloud-check: a new parent's child beats within this
TRIPPED_RC = 75  # what a parent that tripped returns
KILLS = 6  # a: the kills of the dummy child
HELD = {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0}  # a, f: three names, each bought at 100 with its stop at 97
SCORER_S = 30  # d: the scorer stub the engine sits in
QUOTE_S = {False: 60, True: 2}  # f: each quote stub; under --fast shorter than hang_seconds 4 (controller's P2)
ROUNDS = 200  # e: the kills
E_SPAN_S = 4  # e: a kill comes at a moment drawn from the first this many seconds of the engine's life
E_NAMES = ("AAA", "BBB", "CCC", "DDD")  # e: the names it trades
G_STARTS, G_ROUNDS = 50, 20  # g
WAIT_S = 30  # how long a drill waits for a parent or an engine to come up before it fails
# The parent in a process of its own (argv: a JSON object with main's argv, the child's command and the clock's offset
# in seconds). Its environment holds TOPIC, so its lines go to the NtfyStub of its config copy.
PARENT = """import json, sys
from datetime import datetime, timedelta, timezone
from aitrader import supervise
a = json.loads(sys.argv[1])
offset = timedelta(seconds=a["offset_s"])
sys.exit(supervise.main(a["argv"], child_cmd=a["child_cmd"], clock=lambda: datetime.now(timezone.utc) + offset))"""


def guard(argv: list[str], environ, base_url: str) -> str | None:
    """The script's first act: the three phone variables leave `environ`. For every mode but `phone --with-owner`
    (Task 21) the script ends with exit 2 when base_url (the ntfy address of the drill's config copy) is not on host
    127.0.0.1, and None is returned. `phone --with-owner` gets the topic back, to keep in a local variable only;
    `phone` without the flag is refused."""
    topic = environ.get(PHONE_VARS[0])
    for var in PHONE_VARS:
        environ.pop(var, None)
    if argv[:1] == ["phone"]:
        if "--with-owner" in argv:
            return topic
        print("drill_supervisor: phone runs only with --with-owner: refused", file=sys.stderr)
        sys.exit(2)
    if urlsplit(base_url).hostname != "127.0.0.1":
        print("drill_supervisor: the drill's ntfy address is not on 127.0.0.1: refused", file=sys.stderr)
        sys.exit(2)
    return None


class Failed(Exception):
    """A pass mark that did not hold; the text says which."""


def wait(fn, timeout: float, what: str):
    """What fn() gives as soon as it is true; Failed when that takes longer than timeout seconds."""
    end = time.monotonic() + timeout
    while True:
        got = fn()
        if got:
            return got
        if time.monotonic() >= end:
            raise Failed(f"{what}: not within {timeout:g} s")
        time.sleep(0.01)


def beat(state: Path) -> tuple[dict, float | None]:
    """The heartbeat and its mtime, from one open file; ({}, None) when there is none or it cannot be read."""
    try:
        with open(state / "news_heartbeat.json", "rb") as f:
            hb, mtime = json.loads(f.read()), os.fstat(f.fileno()).st_mtime
    except (OSError, ValueError):
        return {}, None
    return (hb if isinstance(hb, dict) else {}), mtime


def rows(state: Path, ev: str | None = None) -> list[dict]:
    """The rows of the uptime log, of one kind when ev is given."""
    return [r for r in supervise.read_rows(state / "uptime.jsonl") if ev in (None, r.get("ev"))]


def said(state: Path, kind: str) -> int:
    """How many lines of this kind reached the NtfyStub: alert ids with a row `sent` true."""
    return len({r.get("id") for r in rows(state, "alert") if r.get("kind") == kind and r.get("sent") is True})


def replaced(state: Path, old: int, t0: float, timeout: float) -> float:
    """The seconds from t0 (the kill) to the mtime of the first beat of another pid than old (spec 11.1)."""
    def new():
        hb, mtime = beat(state)
        return hb.get("pid") not in (None, old) and mtime
    return wait(new, timeout, f"a beat of a process other than {old}") - t0


def dead(pid: int) -> bool:
    """No such process, or a zombie."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0] == "Z"
    except OSError:
        return True


def argv_of(pid: int) -> list[str]:
    """A live process's command line; [] when there is none."""
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace").split("\0")
    except OSError:
        return []


def signal_child(pid: int, sig: int) -> None:
    """sig to a stub child of a drill, and never to a pid that was reused for something else."""
    if not {str(DUMMY), str(ENGINE)} & set(argv_of(pid)):
        raise Failed(f"pid {pid} of the heartbeat is no stub child of this drill: not signalled")
    os.kill(pid, sig)


def flockable(path: Path) -> bool:
    """Nobody holds an flock on the file now (the file is made when it is not there)."""
    with open(path, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


def config_copy(path: Path, fast: bool, port: int, **sup) -> Path:
    """config.json with the --fast numbers when fast, the five switches pinned false (ruling P29) unless sup says
    otherwise, sup over the supervisor block, and the parents' lines sent to 127.0.0.1:port; its path."""
    cfg = supervise.load_cfg()
    cfg["supervisor"].update({**(FAST if fast else {}), "hang_kill_enabled": False, "long_timeout_proven": False,
                              **sup})
    cfg["supervisor"]["deadman"]["enabled"] = False
    cfg["supervisor"]["watcher"].update(fire_enabled=False, notify_enabled=False)
    cfg["alerts"]["ntfy_base_url"] = f"{LOCAL}:{port}"
    path.write_text(json.dumps(cfg, ensure_ascii=False))
    return path


def write_book(state: Path, held: dict[str, float]) -> None:
    """news_book.json with {symbol: entry} held, 10 shares each and the stop at 97% of the entry, bought today (New
    York): the 5-day exit and the look back at minute bars leave such a name alone on any day."""
    from aitrader.broker import PaperBroker  # pandas: only the drills that need a book pay for it
    book = PaperBroker(float(supervise.load_cfg()["news"]["starting_cash"])).state
    today = datetime.now(NY).date().isoformat()
    book["positions"] = {sym: {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": today,
                               "stop_price": round(entry * 0.97, 4)} for sym, entry in held.items()}
    (state / "news_book.json").write_text(json.dumps(book))


def unprimed(state: Path) -> Path:
    """A seen file that is not empty: a first start does not prime, which would take the scenario's first poll for old
    news."""
    (state / "news_seen.json").write_text(json.dumps({"before-the-drill": datetime.now(timezone.utc).isoformat()}))
    return state


class Drill:
    """One drill's temporary directory, its NtfyStub, its numbers (`sup`) and the processes it started."""

    def __init__(self, name: str, fast: bool, rounds: int):
        from helpers.http_stub import NtfyStub
        self.name, self.fast, self.rounds = name, fast, rounds
        self.tmp = Path(tempfile.mkdtemp(prefix=f"drill-{name}-"))
        self.sup = {**supervise.load_cfg()["supervisor"], **(FAST if fast else {})}
        self.stub = NtfyStub()
        self.procs: list[subprocess.Popen] = []
        self.n = 0

    def path(self, stem: str, suffix: str = "") -> Path:
        self.n += 1
        return self.tmp / f"{stem}-{self.n}{suffix}"

    def state(self) -> Path:
        state = self.path("state")
        state.mkdir()
        return state

    def sent(self, state: Path) -> Path:
        """Where the engine children of this state directory write what they hand to notify.send."""
        return self.tmp / f"{state.name}.sent.jsonl"

    def popen(self, cmd: list[str], env: dict) -> subprocess.Popen:
        with open(self.path("out", ".log"), "wb") as out:  # the process keeps a descriptor of its own
            p = subprocess.Popen(cmd, cwd=AT, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        self.procs.append(p)
        return p

    def dummy(self, state: Path, script: list) -> list[str]:
        path = self.path("script", ".json")
        path.write_text(json.dumps(script))
        return [sys.executable, str(DUMMY), "--heartbeat", str(state / "news_heartbeat.json"), "--script", str(path)]

    def engine(self, state: Path, scenario: dict) -> list[str]:
        path = self.path("scenario", ".json")
        path.write_text(json.dumps(scenario))
        return [sys.executable, str(ENGINE), "--state-dir", str(state), "--scenario", str(path), "--sent",
                str(self.sent(state))]

    def parent(self, state: Path, child_cmd: list[str], **sup) -> subprocess.Popen:
        """supervise.main in a process of its own on `state`, with this child, a config copy of its own and the
        clock moved onto MORNING. It hands its --until (UNTIL) to the child."""
        config = config_copy(self.path("config", ".json"), self.fast, urlsplit(self.stub.url).port, **sup)
        spec = {"argv": ["--state-dir", str(state), "--config", str(config), "--until", UNTIL], "child_cmd": child_cmd,
                "offset_s": (MORNING - datetime.now(timezone.utc)).total_seconds()}
        return self.popen([sys.executable, "-c", PARENT, json.dumps(spec)],
                          no_phone.clean_env(**{PHONE_VARS[0]: TOPIC}))

    def bare(self, state: Path, scenario: dict, *options: str) -> subprocess.Popen:
        """The engine child with no parent (e, g), behind its tripwire."""
        return self.popen([*self.engine(state, scenario), "--until", UNTIL, *options], no_phone.clean_env())

    def stop(self, p: subprocess.Popen) -> int | None:
        """SIGTERM, a planned stop; SIGKILL when it has not ended within WAIT_S. Its code."""
        p.send_signal(signal.SIGTERM)
        try:
            return p.wait(timeout=WAIT_S)
        except subprocess.TimeoutExpired:
            p.kill()
            return p.wait()

    def end(self) -> None:
        """SIGKILL to every process this drill started that still runs; a child of a parent dies with it."""
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()

    def tripped(self) -> list[str]:
        """The calls an engine child tried that would have left the machine (its tripwire stopped each)."""
        return sorted({line for f in self.tmp.glob("*.tripwire") for line in f.read_text().split()})


def drill_a(d: Drill) -> str:
    sup = d.sup
    gap = max(sup["healthy_seconds"], sup["restart_window_seconds"] / (KILLS - 1)) + 1
    st = d.state()
    p = d.parent(st, d.dummy(st, [{"beats": -1}]))
    wait(lambda: rows(st, "up"), WAIT_S, "the first child's up")
    last, beats = time.time(), []  # a kill comes `gap` after the last one (the first: after the child came up)
    for k in range(KILLS):
        if k:  # the episode of the kill before has ended with its R1: this kill is a new one
            wait(lambda: said(st, "R1") >= k, sup["healthy_seconds"] + WAIT_S, f"R1 of kill {k}")
        time.sleep(max(0.0, last + gap - time.time()))
        old, last = beat(st)[0]["pid"], time.time()
        signal_child(old, signal.SIGKILL)
        beats.append(replaced(st, old, last, BEAT_S + WAIT_S))
    wait(lambda: said(st, "R1") >= KILLS, sup["healthy_seconds"] + WAIT_S, f"R1 of kill {KILLS}")
    d.stop(p)
    trips, r1 = len(rows(st, "tripped")), said(st, "R1")

    st2 = d.state()  # ruling P3: the engine's kill under a parent of its own, with an alert count of its own
    write_book(st2, HELD)
    p2 = d.parent(st2, d.engine(st2, {"session": "open"}))
    wait(lambda: rows(st2, "up"), WAIT_S, "the engine's up")
    time.sleep(gap)  # longer than healthy_seconds: the replacement starts at once
    old, t0 = beat(st2)[0]["pid"], time.time()
    signal_child(old, signal.SIGKILL)
    beats.append(replaced(st2, old, t0, BEAT_S + WAIT_S))

    def stamps():  # the first look of the replacement: when it began, for each held name
        hb = beat(st2)[0]
        held = hb.get("held") if hb.get("pid") not in (None, old) else None
        return (isinstance(held, dict) and set(held) == set(HELD) and all(v.get("checked_at") for v in held.values())
                and [datetime.fromisoformat(v["checked_at"]).timestamp() for v in held.values()])
    look = max(wait(stamps, LOOK_S + WAIT_S, "the replacement's first look at its 3 names")) - t0
    wait(lambda: said(st2, "R1") >= 1, sup["healthy_seconds"] + WAIT_S, "R1 of the engine's kill")
    d.stop(p2)
    trips, r1_engine = trips + len(rows(st2, "tripped")), said(st2, "R1")
    numbers = (f"kills={KILLS}+1 next_beat_max_s={max(beats):.2f} engine_beat_s={beats[-1]:.2f}"
               f" engine_look_s={look:.2f} r1={r1}+{r1_engine} tripped={trips}")
    if max(beats) >= BEAT_S:
        raise Failed(f"a replacement beat {max(beats):.2f} s after its kill (limit {BEAT_S} s): "
                     + ",".join(f"{s:.2f}" for s in beats))
    if look > LOOK_S:
        raise Failed(f"the engine's first look came {look:.2f} s after its kill (limit {LOOK_S} s)")
    if (trips, r1, r1_engine) != (0, KILLS, 1):
        raise Failed(f"want no trip and one R1 per kill: {numbers}")
    return numbers


def drill_b(d: Drill) -> str:
    sup = d.sup
    st = d.state()
    p = d.parent(st, d.dummy(st, [{"beats": -1}]), hang_kill_enabled=True)
    wait(lambda: rows(st, "up"), WAIT_S, "the child's up")
    old, t0 = beat(st)[0]["pid"], time.time()
    signal_child(old, signal.SIGSTOP)
    limit = sup["hang_seconds"] + HANG_EXTRA_S
    took = replaced(st, old, t0, limit + WAIT_S)
    wait(lambda: len(rows(st, "up")) >= 2, WAIT_S, "the replacement's up")
    time.sleep(sup["healthy_seconds"] + 2 * sup["loop_seconds"] + 1)  # an R1 of this episode would be out by now
    wait(lambda: said(st, "R2"), WAIT_S, "R2")
    d.stop(p)
    hangs, r2, r1 = rows(st, "hang"), said(st, "R2"), said(st, "R1")
    numbers = (f"replaced_s={took:.1f} limit_s={limit:g} hang={len(hangs)}"
               f" killed_with={','.join(str(h.get('killed_with')) for h in hangs)} r2={r2} r1={r1}")
    if took > limit:
        raise Failed(f"the frozen child was replaced {took:.1f} s after kill -STOP (limit {limit:g} s)")
    if (len(hangs), r2, r1) != (1, 1, 0):
        raise Failed(f"want one hang row, one R2 and no R1 (ruling P5): {numbers}")
    return numbers


def drill_c(d: Drill) -> str:
    sup = d.sup
    st = d.state()
    p = d.parent(st, d.dummy(st, [{"beats": 0, "then": "exit", "code": 1}]))
    backoffs = sum(min(sup["backoff_first_seconds"] * 2 ** i, sup["backoff_max_seconds"])
                   for i in range(sup["max_restarts"]))
    try:
        rc = p.wait(timeout=backoffs + WAIT_S)
    except subprocess.TimeoutExpired:
        raise Failed(f"the parent still runs {backoffs + WAIT_S:g} s after its start") from None
    restarts, trips, r3 = len(rows(st, "start")) - 1, len(rows(st, "tripped")), said(st, "R3")
    numbers = f"restarts={restarts} tripped={trips} r3={r3} rc={rc}"
    if (restarts, trips, r3, rc) != (sup["max_restarts"], 1, 1, TRIPPED_RC):
        raise Failed(f"want {sup['max_restarts']} restarts, one tripped row, one R3 and {TRIPPED_RC}: {numbers}")
    return numbers


def drill_d(d: Drill) -> str:
    st = unprimed(d.state())
    scenario = {"session": "open", "polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]],
                "score_delay_s": SCORER_S}
    p = d.parent(st, d.engine(st, scenario))
    old = wait(lambda: (hb := beat(st)[0]).get("phase") == "quotes" and hb["pid"], WAIT_S,
               "the engine's call to the scorer")
    time.sleep(0.2)  # inside the scorer stub now
    t0 = time.time()
    p.kill()
    p.wait()
    # A new parent at once: the same engine, whose scorer now answers at once (it scores the headline the old engine
    # never finished, which the old engine did not mark seen)
    p2 = d.parent(st, d.engine(st, {**scenario, "score_delay_s": 0}))
    took = replaced(st, old, t0, ENGINE_UP_S + WAIT_S)
    left = [] if dead(old) else [old]  # the old parent is reaped above; its engine must be gone by the new one's beat
    wait(lambda: rows(st, "up")[-1:] and rows(st, "up")[-1].get("sup") == p2.pid, WAIT_S, "the new parent's up")
    d.stop(p2)
    r5c, refused = said(st, "R5c"), sum(r.get("rc") == 3 for r in rows(st, "exit"))
    numbers = f"engine_beat_s={took:.2f} old_tree_left={len(left)} refused={refused} r5c={r5c}"
    if left:
        raise Failed(f"processes of the old tree still run: {left}")
    if took >= ENGINE_UP_S:
        raise Failed(f"the new engine beat {took:.2f} s after the parent's kill (limit {ENGINE_UP_S} s)")
    if refused or r5c:
        raise Failed(f"the new engine was refused the book: {numbers}")
    return numbers


def e_scenario(r: int | None) -> dict:
    """Round r's engine: the session open, good news for every name at even polls (score 10: a buy) and bad news at odd
    ones (score 1: a sale), keys of its own so that no earlier round's seen file hides them, quotes at 100, no slippage
    and no loss review (a kill, not the loss rule, is what is drilled). r None: no headlines (the start that is
    judged)."""
    polls = [] if r is None else [[{"key": f"r{r}-{k}-{s}", "symbol": s, "title": f"{s} news {r}-{k}"} for s in E_NAMES]
                                  for k in range(2 * E_SPAN_S)]
    return {"session": "open", "universe": {**{s: "Tech" for s in E_NAMES}, "SPY": "Index"},
            "news": {"slippage_bps": 0, "block_buys_until_loss_reviewed": False}, "polls": polls,
            "scores": {x["key"]: 10 if k % 2 == 0 else 1 for k, poll in enumerate(polls) for x in poll}}


def disagreement(state: Path) -> dict | None:
    """{"side", "symbol"} of the journal's last readable trade row when the book disagrees with it: a BUY of a name the
    book does not hold, or a SELL of a name it still holds (the engine sells a position whole). Else None."""
    trades = [r for r in supervise.read_rows(state / "news_trades.jsonl") if isinstance(r.get("symbol"), str)]
    if not trades:
        return None
    last, held = trades[-1], json.loads((state / "news_book.json").read_text())["positions"]
    if (last.get("side") == "BUY") != (last["symbol"] in held):
        return {"side": last.get("side"), "symbol": last["symbol"]}
    return None


def drill_e(d: Drill) -> str:
    from aitrader import journal, ownerlines  # pandas: only this drill and g pay for it

    def fresh() -> Path:
        state = unprimed(d.state())
        write_book(state, {})
        return state

    def kill(p: subprocess.Popen, r: int) -> None:
        if p.poll() is not None:
            raise Failed(f"round {r}: the engine ended by itself with {p.returncode}")
        p.kill()
        p.wait()
        journal.STATE = state
        bad = [name for name in sorted(journal.NEWS_CHAINED) if not journal.verify_chain(name)[0]]
        if bad:
            raise Failed("step 2 does not land: the torn-append repair goes through rule 4 first"
                         f" (round {r}: {', '.join(bad)})")

    def mismatch_rows() -> int:
        return sum(r.get("where") == "book_mismatch" for r in supervise.read_rows(state / "news_errors.jsonl"))

    sup = supervise.load_cfg()["supervisor"]  # the engine child's own lines are rendered at config.json's sizes
    rng, state, told, mismatches, trades = random.Random(), fresh(), set(), 0, 0
    for r in range(1, d.rounds + 1):
        p = d.bare(state, e_scenario(r))
        time.sleep(rng.uniform(0, E_SPAN_S))
        kill(p, r)
        found = disagreement(state)
        if not found:
            continue  # the next round's start is this round's "then a start"
        # Ruling P4: the next start must say it. It runs to its first idle beat (E1 goes out after the first look); a
        # news_errors row "book_mismatch" or the beat's buys_blocked counts, and E1 is asked for the first time a
        # symbol mismatches. Then a fresh state directory: the mismatch blocks every buy on this one.
        mismatches += 1
        before, sent_before = mismatch_rows(), len(supervise.read_rows(d.sent(state)))
        q = d.bare(state, e_scenario(None))

        def idle():
            if q.poll() is not None:
                raise Failed(f"round {r}: the start after the kill ended with {q.returncode}")
            b = beat(state)[0]
            return b.get("pid") == q.pid and b.get("phase") == "idle" and b
        hb = wait(idle, WAIT_S, f"round {r}: the start after the kill at its first idle beat")
        if mismatch_rows() <= before and hb.get("buys_blocked") != "book_mismatch":
            raise Failed(f"round {r}: the book does not show the last {found['side']} of {found['symbol']} and the next"
                         " start did not say so")
        if found["symbol"] not in told:
            e1 = ownerlines.render("E1", max_bytes=sup["max_line_bytes"], free_chars=sup["free_text_max_chars"],
                                   side=ownerlines.WORDS["E1.side"][found["side"]], sym=found["symbol"])
            if not any(s.get("body") == e1 for s in supervise.read_rows(d.sent(state))[sent_before:]):
                raise Failed(f"round {r}: the start after a {found['side']} of {found['symbol']} that the book does not"
                             " show sent no E1")
            told.add(found["symbol"])
        kill(q, r)
        trades += len(supervise.read_rows(state / "news_trades.jsonl"))
        state = fresh()
    trades += len(supervise.read_rows(state / "news_trades.jsonl"))
    if not trades:
        raise Failed(f"no trade was made in {d.rounds} rounds: the kills landed on nothing")
    return f"rounds={d.rounds} trades={trades} mismatches={mismatches} e1={len(told)} chains=ok"


def drill_g(d: Drill) -> str:
    from aitrader import journal
    git_env = {**no_phone.clean_env(), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
               **{f"GIT_{who}_{what}": "drill" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL")}}

    def git(where: Path, *args: str) -> None:
        p = subprocess.run(["git", *args], cwd=where, env=git_env, capture_output=True, text=True, timeout=WAIT_S)
        if p.returncode:
            raise Failed(f"git {' '.join(args)} in {where.name}: exit {p.returncode}: {(p.stderr or p.stdout)[-300:]}")

    def commit(where: Path, name: str, text: str) -> None:
        (where / name).write_text(text)
        git(where, "add", "-A")
        git(where, "commit", "-m", f"{name}: {text.strip()}")

    # A temporary bare "origin", a clone of it whose ai-trader/state/ is the engine's state directory (a committed
    # book with one position and a trade journal of two rows), and a second clone that pushes what the first one then
    # fetches and merges, the way a turn of the trader session does (never a rebase). Nothing else is touched.
    origin, clone, second = d.tmp / "origin.git", d.tmp / "clone", d.tmp / "second"
    git(d.tmp, "init", "--bare", "--initial-branch=main", str(origin))
    git(d.tmp, "init", "--initial-branch=main", str(clone))
    git(clone, "remote", "add", "origin", str(origin))
    state = clone / "ai-trader" / "state"
    state.mkdir(parents=True)
    write_book(state, {"BBB": 50.0})
    journal.STATE = state
    for qty in (6, 4):  # the last row is a buy the book holds: no mismatch
        journal.append("news_trades.jsonl",
                       {"date": "2026-11-10", "symbol": "BBB", "side": "BUY", "qty": qty, "price": 50.0})
    commit(clone, "notes.txt", "one\n")
    git(clone, "push", "origin", "HEAD:main")
    git(d.tmp, "clone", str(origin), str(second))
    commit(clone, "mine.txt", "mine\n")  # each merge below is then a real one, with MERGE_HEAD for a moment
    book = (state / "news_book.json").read_bytes()
    go, failed = threading.Semaphore(0), []

    def rounds():
        try:
            for n in range(G_ROUNDS):
                if not go.acquire(timeout=WAIT_S * 2):
                    raise Failed(f"round {n} was never let go")
                commit(second, "other.txt", f"{n}\n")
                git(second, "push", "origin", "HEAD:main")
                git(clone, "fetch", "origin", "main")
                git(clone, "merge", "--no-edit", "origin/main")
        except BaseException as e:  # noqa: BLE001 - a failure of this thread is the drill's
            failed.append(f"{type(e).__name__}: {e}")
    beside = threading.Thread(target=rounds, daemon=True)
    beside.start()
    let_go, codes = {n * G_STARTS // G_ROUNDS for n in range(G_ROUNDS)}, []
    for n in range(G_STARTS):
        p = d.bare(state, {}, "--minutes", "0.002")
        if n in let_go:
            go.release()  # a round while this engine runs
        codes.append(p.wait(timeout=WAIT_S))
    beside.join(timeout=WAIT_S * 2)
    chains = {name: journal.verify_chain(name) for name in sorted(journal.NEWS_CHAINED)}
    numbers = f"starts={G_STARTS} rounds={G_ROUNDS} rc0={codes.count(0)} rc7={codes.count(7)}"
    if failed or beside.is_alive() or (clone / "other.txt").read_text() != f"{G_ROUNDS - 1}\n":
        raise Failed(f"the fetch-and-merge rounds did not all run: {failed or 'still running'}")
    if set(codes) - {0, 7} or 0 not in codes:
        raise Failed(f"every start must return 0 or 7, and one must run: {sorted(set(codes))}")
    held_before = json.loads(book)["positions"]
    if json.loads((state / "news_book.json").read_text())["positions"] != held_before:
        raise Failed("the book is not as it was")
    if not all(ok for ok, _ in chains.values()) or chains["news_trades.jsonl"] != (True, 2):
        raise Failed(f"the chains are not as they were: {chains}")
    return numbers


def drill_f(d: Drill) -> str:
    sup, quote = d.sup, QUOTE_S[d.fast]
    st = d.state()
    write_book(st, HELD)
    # The engine before this one looked at the stops just now: its stamp is adopted, so the start row comes when the
    # slow looks let it age past stops_stale_seconds. On a directory with no stamp at all the parent would count the
    # unknown stamp as stale at the boot beat, and the quote stubs would decide nothing.
    now = datetime.now(timezone.utc).isoformat()
    (st / "news_heartbeat.json").write_text(json.dumps({"at": now, "stops_checked_at": now}))
    p = d.parent(st, d.engine(st, {"session": "open", "quote_delay_s": quote}))
    wait(lambda: rows(st, "stale_stops") and said(st, "R6"), sup["stops_stale_seconds"] + WAIT_S, "stale_stops and R6")
    # One look costs len(HELD) quotes, and its stamp is when it began: the names stay stale and never turn fresh. Long
    # enough for the first look to end and for any stretch without a beat to pass hang_seconds.
    watched = len(HELD) * quote + sup["hang_seconds"]
    time.sleep(watched)
    stale = rows(st, "stale_stops")
    starts, aged = sum(r.get("what") == "start" for r in stale), stale[0].get("stop")
    r6, hangs, spawned = said(st, "R6"), len(rows(st, "hang")), len(rows(st, "start"))
    p.kill()  # not a planned stop: that would wait for the engine to finish its slow look; the engine dies with it
    p.wait()
    numbers = f"stale_start={starts} stop_s={aged} r6={r6} hang={hangs} starts={spawned} watched_s={watched:g}"
    if not isinstance(aged, (int, float)):
        raise Failed(f"the stale stops were an unknown stamp, not one the slow looks let age: {numbers}")
    if (starts, r6, hangs, spawned) != (1, 1, 0, 1):
        raise Failed(f"want one stale_stops start row, one R6 and no kill: {numbers}")
    return numbers


DRILLS = {"a": drill_a, "b": drill_b, "c": drill_c, "d": drill_d, "e": drill_e, "f": drill_f, "g": drill_g}


def run(name: str, fast: bool, rounds: int) -> bool:
    """One drill: its PASS or FAIL line. A passed drill's files are removed; a failed one's are kept and named."""
    d, passed = Drill(name, fast, rounds), False
    try:
        numbers = DRILLS[name](d)
        d.end()
        if d.tripped():
            raise Failed(f"an engine child tried to leave the machine: {', '.join(d.tripped())}")
        print(f"PASS {name} {numbers}", flush=True)
        passed = True
    except Failed as e:
        print(f"FAIL {name} {e} (files kept in {d.tmp})", flush=True)
    except Exception as e:  # noqa: BLE001 - a drill that breaks is a failed drill, and the next one still runs
        print(f"FAIL {name} {type(e).__name__}: {e} (files kept in {d.tmp})", flush=True)
    finally:
        d.end()
        d.stub.stop()
        if passed:
            shutil.rmtree(d.tmp, ignore_errors=True)
    return passed


def cloud(directory: Path, fast: bool) -> int:
    """This process becomes a parent with the dummy child on state directory `directory`, in the foreground (a
    tracked background command of the session that launches it), until it is stopped from outside. Its config copy and
    the dummy's script are written into the directory; it has no topic, so it sends nothing."""
    state = directory.resolve()
    state.mkdir(parents=True, exist_ok=True)
    script = state / "drill-script.json"
    script.write_text(json.dumps([{"beats": -1}]))
    config = config_copy(state / "drill-config.json", fast, DEAD)
    child = [sys.executable, str(DUMMY), "--heartbeat", str(state / "news_heartbeat.json"), "--script", str(script)]
    offset = MORNING - datetime.now(timezone.utc)
    return supervise.main(["--state-dir", str(state), "--config", str(config), "--until", UNTIL], child_cmd=child,
                          env=no_phone.clean_env(), clock=lambda: datetime.now(timezone.utc) + offset)


def lock_holder(lock: Path) -> int | None:
    """The pid that holds the flock on the lock file now, from /proc/locks: the lock itself decides, never the text in
    the file (controller note, 12:19 UTC 2026-11-11). None when nobody does."""
    try:
        ino, locks = lock.stat().st_ino, Path("/proc/locks").read_text().splitlines()
    except OSError:
        return None
    return next((int(m[1]) for m in map(supervise.FLOCK_ROW.match, locks) if m and int(m[2]) == ino), None)


def processes_of(state: Path, given: str) -> list[int]:
    """Live processes but this one whose command line names the directory (as given, or resolved) or a file in it."""
    names = {str(state), given.rstrip("/")}
    found = []
    for proc in Path("/proc").iterdir():
        if proc.name.isdigit() and int(proc.name) != os.getpid():
            if any(a in names or any(a.startswith(n + "/") for n in names) for a in argv_of(int(proc.name))):
                found.append(int(proc.name))
    return found


def cloud_check(given: str, alive: bool) -> int:
    state = Path(given).resolve()
    paths = supervise.Paths(state, state / ".cache")
    log = supervise.read_rows(paths.uptime)
    # the last parent's own rows: from its sup_start on (a parent before it in the same directory has its own)
    last = log[next((i for i in range(len(log) - 1, -1, -1) if log[i].get("ev") == "sup_start"), 0):]
    stops = [str(r.get("why")) for r in last if r.get("ev") == "sup_stop"]
    if alive:
        holder, marks = lock_holder(paths.lock), sum(r.get("ev") == "mark" for r in last)
        why = ((["no live process holds the parent lock"] if holder is None else [])
               + ([] if marks else ["no mark row"]) + ([f"a sup_stop row ({', '.join(stops)})"] if stops else []))
        print(f"FAIL cloud-check --alive {'; '.join(why)}" if why
              else f"PASS cloud-check --alive parent={holder} marks={marks}", flush=True)
        return 1 if why else 0
    left = processes_of(state, given)
    busy = [lock.name for lock in (paths.lock, paths.engine_lock) if not flockable(lock)]
    if left or busy:
        print(f"FAIL cloud-check processes of the directory left: {left}; locks held: {busy}", flush=True)
        return 1
    old, t0 = beat(state)[0].get("pid"), time.time()
    p = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "cloud", str(state)], cwd=AT,
                         env=no_phone.clean_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    try:
        def new():
            hb, mtime = beat(state)
            return hb.get("pid") not in (None, old) and mtime is not None and mtime >= t0 and mtime
        took = wait(new, CLOUD_BEAT_S, "a new parent's child beat") - t0
    except Failed as e:
        print(f"FAIL cloud-check {e}", flush=True)
        return 1
    finally:
        p.send_signal(signal.SIGTERM)
        try:
            p.wait(timeout=WAIT_S)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    # what the stop from outside left in the log (ruling P39), read before the relaunch added rows of its own
    print(f"PASS cloud-check sup_stop={stops[0] if stops else 'none'} new_beat_s={took:.2f}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    guard(argv, os.environ, LOCAL)  # first: no phone variable outlives this line, and every config copy is local
    global no_phone, supervise  # noqa: PLW0603 - imported only now, after the guard
    sys.path[:0] = [str(AT), str(AT / "tests")]
    from helpers import no_phone
    from aitrader import supervise
    if argv[:1] == ["cloud"]:
        ap = argparse.ArgumentParser(prog="drill_supervisor.py cloud")
        ap.add_argument("dir", type=Path)
        ap.add_argument("--fast", action="store_true")
        a = ap.parse_args(argv[1:])
        return cloud(a.dir, a.fast)
    if argv[:1] == ["cloud-check"]:
        ap = argparse.ArgumentParser(prog="drill_supervisor.py cloud-check")
        ap.add_argument("--alive", action="store_true")
        ap.add_argument("dir")
        a = ap.parse_args(argv[1:])
        return cloud_check(a.dir, a.alive)
    ap = argparse.ArgumentParser(prog="drill_supervisor.py", description=__doc__.splitlines()[0])
    ap.add_argument("drills", nargs="+", choices=[*DRILLS, "all"])
    ap.add_argument("--fast", action="store_true", help="the scaled numbers (FAST) in place of config.json's")
    ap.add_argument("--rounds", type=int, default=ROUNDS, help=f"drill e's kills (default {ROUNDS})")
    a = ap.parse_args(argv)
    names = dict.fromkeys(n for x in a.drills for n in (DRILLS if x == "all" else [x]))
    return 0 if all([run(name, a.fast, a.rounds) for name in names]) else 1


if __name__ == "__main__":
    sys.exit(main())
