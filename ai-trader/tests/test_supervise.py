"""Real processes (supervisor spec 11.1): the news engine started as a process of its own, on a temporary state
directory, behind the stand-ins and the tripwire of tests/helpers/engine_child.py; and the supervisor's parent process
(aitrader/supervise.py) with its stand-in child, tests/helpers/dummy_child.py. Nothing here reaches the network, the
model, the live state or the owner's phone."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import fcntl
import functools
import io
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import journal, notify, ownerlines, supervise
from aitrader.broker import PaperBroker

TESTS = Path(__file__).resolve().parent
ENGINE_CHILD = TESTS / "helpers" / "engine_child.py"
DUMMY_CHILD = TESTS / "helpers" / "dummy_child.py"
NY = ZoneInfo("America/New_York")


def _lines(path: Path) -> list:
    """The whole JSON lines of a file that a live process may be writing; [] when it is not there."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text[:text.rfind("\n") + 1].splitlines() if line.strip()]


class Procs(unittest.TestCase):
    """A temporary directory with state/ in it, and what a test needs to start engine processes there and to watch
    them. tearDown kills whatever is left and fails the test when one of them tripped the wire."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.sent_file = self.tmp / "sent.jsonl"
        self._started, self._scenarios = [], 0

    def tearDown(self):
        for p in self._started:
            if p.poll() is None:
                p.kill()
        try:  # the scorer stand-in's `sleep 60`, when a scenario asked for one: only that, never a pid that was reused
            orphan = int(Path(f"{self.sent_file}.orphan").read_text())
            if Path(f"/proc/{orphan}/cmdline").read_bytes() == b"sleep\x0060\x00":
                os.kill(orphan, signal.SIGKILL)
        except (OSError, ValueError):
            pass
        for p in self._started:
            p.wait()
            p.stdout.close()
            p.stderr.close()
        tripwire = Path(f"{self.sent_file}.tripwire")
        tripped = tripwire.read_text().splitlines() if tripwire.exists() else []
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.assertEqual(tripped, [], "an engine process tried to leave the machine and the tripwire stopped it")

    def scenario(self, scenario: dict) -> str:
        """The scenario as a file of its own; its path."""
        self._scenarios += 1
        path = self.tmp / f"scenario-{self._scenarios}.json"
        path.write_text(json.dumps(scenario))
        return str(path)

    def start_engine(self, scenario: dict, *options: str) -> subprocess.Popen:
        """engine_child.py on self.state with this scenario; `options` go to news-live as they are, behind `--until
        23:59` when they name no end of their own. A start does not prime: without a seen file the engine would mark
        the scenario's first poll as old news."""
        seen = self.state / "news_seen.json"
        if not seen.exists():
            seen.write_text(json.dumps({"before-the-test": datetime.now(timezone.utc).isoformat()}))
        if not any(o.split("=")[0] == "--until" for o in options):
            # The engine ends by the real New York clock and its own default is 16:05: the gate runs this suite after
            # that, and such a start would end before its first step. With 23:59, the last minute of the day, a test
            # passes at any hour but one minute. The known ceiling: a start made between 23:59 and 00:00 New York.
            options = ("--until", "23:59", *options)
        p = subprocess.Popen([sys.executable, str(ENGINE_CHILD), "--state-dir", str(self.state), "--scenario",
                              self.scenario(scenario), "--sent", str(self.sent_file), *options],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=no_phone.clean_env())
        self._started.append(p)
        return p

    def write_book(self, held: dict[str, float]) -> None:
        """news_book.json with {symbol: entry} held: 10 shares each, the stop at 97% of the entry. Bought today (New
        York) at no recorded time: the 5-day exit and the look back at minute bars both leave such a name alone, so
        the book plays the same on whatever day and hour the test runs."""
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        book = PaperBroker(100000.0).state
        book["positions"] = {sym: {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": today,
                                   "stop_price": round(entry * 0.97, 4)} for sym, entry in held.items()}
        (self.state / "news_book.json").write_text(json.dumps(book))

    def beat(self) -> dict:
        """The engine's heartbeat; {} when there is no file."""
        try:
            return json.loads((self.state / "news_heartbeat.json").read_text())
        except FileNotFoundError:
            return {}

    def wait_beat(self) -> dict:
        return self.wait_for(self.beat)

    def rows(self, name: str) -> list:
        return _lines(self.state / name)

    def sent_rows(self) -> list:
        """What the engines handed to notify.send: {at, title, body, priority} each."""
        return _lines(self.sent_file)

    def wait_for(self, fn, timeout=5):
        """What fn() gives as soon as it is true; the test fails when that takes longer than `timeout` seconds."""
        end = time.monotonic() + timeout
        while True:
            got = fn()
            if got:
                return got
            if time.monotonic() >= end:
                ended = [f"exit {p.returncode}: {p.stderr.read()[-400:]}" for p in self._started if p.poll() is not None]
                self.fail(f"not within {timeout} s: {getattr(fn, '__name__', fn)}; engines that ended: {ended}")
            time.sleep(0.01)

    def step_done(self) -> bool:
        """The first step has ended: the heartbeat and the queue file are there and the engine is idle."""
        return ((self.state / "news_heartbeat.json").exists() and (self.state / "news_queue.json").exists()
                and self.beat().get("phase", "idle") == "idle")

    def dead(self, pid: int) -> bool:
        """No such process, or a zombie."""
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return True
        return stat.rpartition(")")[2].split()[0] == "Z"


class EngineLock(Procs):
    def test_a_second_engine_exits_3_within_2_s_names_the_holder_and_touches_no_state(self):
        a = self.start_engine({"news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(self.step_done)                  # a sleeps 30 s now: nothing of its own changes the files
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        b = self.start_engine({}, "--minutes", "5")
        self.assertEqual(b.wait(timeout=2), 3)
        self.assertEqual({p.name: p.read_bytes() for p in self.state.iterdir()}, before)
        self.assertIn(f"pid {a.pid}", b.stdout.read())
        self.assertEqual(json.loads((self.state / "news_engine.lock").read_text())["pid"], a.pid)
        self.assertEqual(self.sent_rows(), [])         # and the refused start said nothing to the owner

    def test_after_kill_9_of_the_holder_a_new_start_takes_the_lock(self):
        a = self.start_engine({"news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(self.step_done)
        a.kill()
        a.wait()
        c = self.start_engine({}, "--minutes", "0.001")
        self.assertEqual(c.wait(timeout=10), 0)
        self.assertEqual(json.loads((self.state / "news_engine.lock").read_text())["pid"], c.pid)   # one line: the last holder

    def test_the_lock_is_free_while_an_orphan_of_the_dead_engine_still_runs(self):
        a = self.start_engine({"polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]], "score_orphan": True},
                              "--minutes", "5")
        self.wait_for(lambda: self.rows("news_scores.jsonl"))
        a.kill()
        a.wait()
        self.assertFalse(self.dead(int(Path(str(self.sent_file) + ".orphan").read_text())))
        self.assertEqual(self.start_engine({}, "--minutes", "0.001").wait(timeout=10), 0)

    def test_an_open_session_with_a_queued_name_and_a_headline_reaches_nothing_outside(self):
        (self.state / "news_queue.json").write_text(json.dumps([{"symbol": "BBB", "score": 9, "why": "x", "id": "q1", "queued_at": "2026-11-12T13:00:00+00:00"}]))
        p = self.start_engine({"session": "open", "polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]]}, "--minutes", "0.002")
        self.assertEqual(p.wait(timeout=20), 0)        # 97 = the tripwire
        self.assertFalse(Path(str(self.sent_file) + ".tripwire").exists())
        # and it went where the outside calls are: the queued name was bought at a quote, the headline scored, the line sent
        self.assertEqual([(t["side"], t["symbol"]) for t in self.rows("news_trades.jsonl")], [("BUY", "BBB")])
        self.assertEqual([r["id"] for r in self.rows("news_scores.jsonl")], ["k1"])
        self.assertEqual([r["priority"] for r in self.sent_rows()], ["high"])


# Every git call of the tests below: the user's signing, hooks and identity must not be used.
GIT_ENV = {**no_phone.clean_env(), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           **{f"GIT_{who}_{what}": "test" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL")}}


class PullBesideRestarts(Procs):
    """The engine beside the trader session's git work in the same checkout (spec 5.4, check 2). A bare "origin", a
    clone whose ai-trader/state/ is the engine's state directory (a committed book with one position and a trade
    journal of two rows), and a second clone that pushes what the first one then fetches and merges."""

    def setUp(self):
        super().setUp()
        origin, self.clone, self.second = (self.tmp / name for name in ("origin.git", "clone", "second"))
        self.git(self.tmp, "init", "--bare", "--initial-branch=main", str(origin))
        self.git(self.tmp, "init", "--initial-branch=main", str(self.clone))
        self.git(self.clone, "remote", "add", "origin", str(origin))
        self.state = self.clone / "ai-trader" / "state"   # inside the checkout, as the live state directory is
        self.state.mkdir(parents=True)
        self.write_book({"BBB": 50.0})
        with mock.patch.object(journal, "STATE", self.state):
            for qty in (6, 4):                            # the last row is a buy the book holds: no mismatch
                journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "BBB", "side": "BUY", "qty": qty, "price": 50.0})
        self.commit(self.clone, "notes.txt", "one\n")
        self.git(self.clone, "push", "origin", "HEAD:main")
        self.git(self.tmp, "clone", str(origin), str(self.second))

    def git(self, where: Path, *args: str, ok: tuple = (0,)) -> subprocess.CompletedProcess:
        p = subprocess.run(["git", *args], cwd=where, env=GIT_ENV, capture_output=True, text=True, timeout=30)
        if p.returncode not in ok:
            raise AssertionError(f"git {' '.join(args)} in {where.name}: exit {p.returncode}: {(p.stderr or p.stdout)[-400:]}")
        return p

    def commit(self, where: Path, name: str, text: str) -> None:
        (where / name).write_text(text)
        self.git(where, "add", "-A")
        self.git(where, "commit", "-m", f"{name}: {text.strip()}")

    def merge(self, ok: tuple = (0,)) -> subprocess.CompletedProcess:
        """The first clone takes what origin has, the way a turn of the trader session does (never a rebase)."""
        self.git(self.clone, "fetch", "origin", "main")
        return self.git(self.clone, "merge", "--no-edit", "origin/main", ok=ok)

    def test_a_merge_left_open_refuses_the_start_with_7_and_the_book_is_untouched(self):
        self.commit(self.second, "notes.txt", "two\n")
        self.git(self.second, "push", "origin", "HEAD:main")
        self.commit(self.clone, "notes.txt", "three\n")
        self.merge(ok=(1,))                              # it stops on the conflict in notes.txt
        self.assertTrue((self.clone / ".git" / "MERGE_HEAD").exists())
        book = (self.state / "news_book.json").read_bytes()
        p = self.start_engine({}, "--minutes", "0.002")
        self.assertEqual(p.wait(timeout=10), 7)
        self.assertEqual((self.state / "news_book.json").read_bytes(), book)
        self.assertIn("[news] start refused: tree_busy (exit 7)", p.stdout.read())
        self.assertEqual((self.beat(), self.sent_rows()), ({}, []))   # no trader was built, and nobody was told
        self.git(self.clone, "merge", "--abort")
        self.assertEqual(self.start_engine({}, "--minutes", "0.002").wait(timeout=10), 0)
        self.assertEqual(self.beat()["positions"], 1)

    def test_a_restart_loop_beside_a_fetch_and_merge_leaves_book_and_chains_as_they_were(self):
        held = json.loads((self.state / "news_book.json").read_text())["positions"]
        # a commit of its own in the first clone, as the trader session has its state commits: each merge below is then
        # a real merge, which writes MERGE_HEAD for a moment, and a start that falls into that moment answers 7
        self.commit(self.clone, "mine.txt", "mine\n")
        go, failed = threading.Semaphore(0), []

        def rounds():
            try:
                for n in range(5):
                    if not go.acquire(timeout=60):
                        raise AssertionError(f"round {n} was never let go")
                    self.commit(self.second, "other.txt", f"{n}\n")
                    self.git(self.second, "push", "origin", "HEAD:main")
                    self.merge()
            except BaseException as e:  # noqa: BLE001 - a thread's failure is the test's
                failed.append(e)
        beside = threading.Thread(target=rounds, daemon=True)
        beside.start()
        codes = []
        for n in range(10):
            p = self.start_engine({}, "--minutes", "0.002")
            if n % 2 == 0:
                go.release()                             # a round at every second start, while that engine runs
            codes.append(p.wait(timeout=20))
        beside.join(timeout=60)
        self.assertEqual((failed, beside.is_alive(), (self.clone / "other.txt").read_text()), ([], False, "4\n"))
        self.assertEqual((set(codes) - {0, 7}, 0 in codes), (set(), True), codes)   # every start returned 0 or 7
        self.assertEqual(json.loads((self.state / "news_book.json").read_text())["positions"], held)
        with mock.patch.object(journal, "STATE", self.state):
            self.assertEqual(journal.verify_chain("news_trades.jsonl"), (True, 2))


class SaidBeforeTheKill(Procs):
    def test_the_line_of_a_sale_is_out_before_a_scorer_that_never_returns_and_a_kill_9(self):
        self.write_book({"BBB": 50.0})
        p = self.start_engine({"session": "open", "prices": {"BBB": [48.0]}, "score_delay_s": "never",
                               "polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]]}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "quotes")
        p.kill()
        self.assertEqual(sum("SELL 10 BBB" in r["body"] for r in self.sent_rows()), 1)


# A parent of its own for one engine (argv: the state directory, the scenario file): it starts engine_child.py with
# --supervised <its own pid>, prints the child's pid and sleeps. The engine's end is 24:00, which never comes.
PARENT = f"""import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, {str(ENGINE_CHILD)!r}, "--state-dir", sys.argv[1], "--scenario", sys.argv[2], "--sent", os.path.join(os.path.dirname(sys.argv[1]), "sent.jsonl"), "--until", "24:00", "--supervised", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(child.pid, flush=True); time.sleep(600)"""


class EngineStop(Procs):
    """A planned stop and a lost parent, on real processes (supervisor spec 5.3)."""

    def test_sigterm_in_the_sleep_exits_143_within_1_s_with_the_book_saved(self):
        p = self.start_engine({"session": "open", "news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "idle")
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=1), 143)
        self.assertIn("positions", json.loads((self.state / "news_book.json").read_text()))
        self.assertEqual(self.beat()["phase"], "stopping")

    def test_sigterm_during_a_slow_scorer_finishes_that_batch_and_leaves_the_next_unseen(self):
        polls = [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}, {"key": "k2", "symbol": "BBB", "title": "BBB two"}]]
        p = self.start_engine({"session": "open", "polls": polls, "score_delay_s": 1.5, "news": {"batch_max": 1, "poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "quotes")
        time.sleep(0.3); p.send_signal(signal.SIGTERM)
        time.sleep(0.2); p.send_signal(signal.SIGTERM)             # Review Focus 2: a second signal changes nothing
        self.assertEqual(p.wait(timeout=10), 143)
        self.assertEqual([r["id"] for r in self.rows("news_scores.jsonl")], ["k1"])
        seen = json.loads((self.state / "news_seen.json").read_text())
        self.assertEqual(("k1" in seen, "k2" in seen), (True, False))

    def test_sigterm_during_the_first_look_finishes_the_look(self):       # Review Focus 2
        self.write_book({"BBB": 50.0})                                    # BBB held; its quote takes 1.5 s
        p = self.start_engine({"session": "open", "quote_delay_s": 1.5, "news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "boot")
        p.send_signal(signal.SIGTERM)                                     # the signal goes out while the phase is "boot"
        self.assertEqual(p.wait(timeout=10), 143)
        self.assertIsNotNone(self.beat()["held"]["BBB"]["checked_at"])

    def test_kill_9_of_its_parent_takes_the_engine_with_it_and_frees_the_lock(self):
        parent = subprocess.Popen([sys.executable, "-c", PARENT, str(self.state), self.scenario({"news": {"poll_seconds": 30}})],
                                  stdout=subprocess.PIPE, text=True, env=no_phone.clean_env())
        self.addCleanup(parent.stdout.close)
        self.addCleanup(parent.wait)
        self.addCleanup(parent.kill)                               # whatever becomes of the test: the parent first,
        child = int(parent.stdout.readline())
        self.addCleanup(self.end_engine_child, child)              # then its engine, should it have outlived it
        self.wait_for(lambda: self.beat().get("pid") == child)
        parent.kill(); parent.wait()
        end = time.monotonic() + 1                                 # spec 5.3: gone within 1 s, and the lock is free
        self.wait_for(lambda: self.dead(child), timeout=1)
        # The kernel shows the engine's main thread as a zombie a moment (0.2 ms, measured) before the process's other
        # threads (numpy starts three) have let go of its open files, and the lock with them: asked until that second ends.
        self.wait_for(self.lock_is_free, timeout=max(0.0, end - time.monotonic()))

    def lock_is_free(self) -> bool:
        with open(self.state / "news_engine.lock", "a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        return True

    def end_engine_child(self, pid: int) -> None:
        """SIGKILL to an engine child that a parent of a test started, and only to that: never to a pid that was reused."""
        try:
            if str(ENGINE_CHILD).encode() in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"):
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


# One forbidden call each, in a process of its own behind the tripwire alone (argv: the tripwire's file, tests/). The
# targets cannot answer, so a tripwire that failed to stop one of them would still reach nobody.
BEHIND_THE_WIRE = ("import sys; sys.path.insert(0, sys.argv[2]); from helpers import engine_child;"
                   " engine_child.install_tripwire(sys.argv[1])\n")
OUTSIDE = {
    "requests.sessions.Session.request": "import requests; requests.post('https://outside.invalid/', json={}, timeout=1)",
    "urllib.request.urlopen": "import urllib.request as u; u.urlopen(u.Request('https://outside.invalid/x'), timeout=1)",
    "socket.create_connection": "import socket; socket.create_connection(('192.0.2.1', 9), timeout=1)",
    "subprocess.Popen git": "import subprocess; subprocess.run(['git', '--version'], capture_output=True)",
    "subprocess.Popen claude": "import subprocess; subprocess.run(['/nonexistent/claude', '-p', 'x'], capture_output=True)",
}
# What stays on this machine goes through: a local listener by all three roads, and a program that is neither.
INSIDE = """
import socket, subprocess, urllib.request, requests
port = sys.argv[3]
socket.create_connection(("127.0.0.1", int(port)), timeout=2).close()
for road, ask in (("urlopen", urllib.request.urlopen), ("requests", requests.get)):
    try:
        ask(f"http://127.0.0.1:{port}/", timeout=0.2)
    except OSError:   # the listener never answers: the call was let through and then timed out
        print(road)
subprocess.run(["sleep", "0"], check=True)
print("sleep")
"""


class Harness(Procs):
    """Every process test and drill after this one trusts the harness, so what the lock tests above do not call is
    checked here: a tripwire that has never been seen to fire is no tripwire."""

    def _behind_the_wire(self, name: str, code: str, *args: str) -> subprocess.Popen:
        p = subprocess.Popen([sys.executable, "-c", BEHIND_THE_WIRE + code, str(self.tmp / name), str(TESTS), *args],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=no_phone.clean_env())
        self._started.append(p)   # tearDown ends it, whatever becomes of the test
        return p

    def test_the_tripwire_ends_the_process_with_97_on_each_call_that_would_leave_the_machine(self):
        started = {name: self._behind_the_wire(name, code) for name, code in OUTSIDE.items()}
        for name, p in started.items():
            _, err = p.communicate(timeout=20)
            self.assertEqual((p.returncode, (self.tmp / name).read_text()), (97, name.split()[0] + "\n"), err[-400:])

    def test_the_tripwire_lets_through_what_stays_on_this_machine(self):
        with socket.create_server(("127.0.0.1", 0)) as listener:   # it takes connections and never answers
            p = self._behind_the_wire("inside", INSIDE, str(listener.getsockname()[1]))
            out, err = p.communicate(timeout=20)
        self.assertEqual((p.returncode, out.split(), (self.tmp / "inside").exists()),
                         (0, ["urlopen", "requests", "sleep"], False), err[-400:])

    def test_whatever_the_engine_child_starts_runs_behind_the_tripwire(self):
        engine = ("import socket, sys; sys.path.insert(0, sys.argv[1]); from helpers import engine_child\n"   # an engine that
                  "engine_child.cli.main = lambda argv: socket.create_connection(('192.0.2.1', 9), timeout=1)\n"  # tries to leave
                  "sys.exit(engine_child.main(sys.argv[2:]))")
        sent = self.tmp / "sent-of-its-own"   # not self.sent_file: this trip is the point, tearDown must not count it
        p = subprocess.run([sys.executable, "-c", engine, str(TESTS), "--state-dir", str(self.state), "--scenario",
                            self.scenario({}), "--sent", str(sent)],
                           capture_output=True, text=True, env=no_phone.clean_env(), timeout=20)
        self.assertEqual((p.returncode, Path(f"{sent}.tripwire").read_text()), (97, "socket.create_connection\n"), p.stderr[-400:])

    def test_a_scenario_is_played_as_written(self):
        self.write_book({"BBB": 50.0})
        (self.state / "news_queue.json").write_text(json.dumps([{"symbol": "CCC", "score": 9, "why": "x", "id": "q1"}]))
        polls = [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}], [{"key": "k2", "symbol": "AAA", "title": "AAA two"}]]
        self.start_engine({"session": "open", "universe": {"AAA": "Tech", "BBB": "Tech", "CCC": "Tech", "SPY": "Index"},
                           "news": {"slippage_bps": 0}, "opens": {"CCC": 42.0}, "polls": polls, "scores": {"k2": 7},
                           "prices": {"BBB": [51.0, 51.0, 48.0], "AAA": [10.0, 20.0]}}, "--minutes", "5")
        self.wait_for(lambda: len(self.rows("news_scores.jsonl")) == 2)      # the second poll came, a step later
        # a list per poll, a price per call, a score per key (5 for a key the scenario does not hold)
        self.assertEqual([(r["id"], r["price"], r["score"]) for r in self.rows("news_scores.jsonl")],
                         [("k1", 10.0, 5), ("k2", 20.0, 7)])
        # CCC from the queue at its official open; BBB seen at 51.00 by the first look of the start and by the look at
        # the top of the first step, and at 48.00, under its stop of 48.50, by the look at that step's end. No slippage:
        # the scenario's news keys are merged over config.json's
        self.assertEqual([(t["side"], t["symbol"], t["price"]) for t in self.rows("news_trades.jsonl")],
                         [("BUY", "CCC", 42.0), ("SELL", "BBB", 48.0)])
        self.assertEqual(sum("SELL 10 BBB" in r["body"] for r in self.sent_rows()), 1)
        beat = self.wait_beat()
        self.assertEqual((beat["positions"], beat["code"]["commit"]), (1, "abc1234"))
        self.assertIs(beat["lock"], True)              # the engine holds its lock, and its heartbeat says so

    def test_the_phone_stand_in_writes_the_line_down_and_answers_as_the_scenario_says(self):
        phone = ("import json, sys; sys.path.insert(0, sys.argv[1]); from helpers import engine_child\n"
                 "for ok in (True, False):\n"
                 "    engine_child.install({**engine_child.SCENARIO, 'send_ok': ok}, sys.argv[2])\n"
                 "    print(json.dumps(engine_child.news_live.notify.send('a title', 'a body', {}, 'urgent')))\n")
        p = subprocess.run([sys.executable, "-c", phone, str(TESTS), str(self.sent_file)],
                           capture_output=True, text=True, env=no_phone.clean_env(), timeout=20)
        self.assertEqual(p.stdout.splitlines(), ['["ntfy"]', "[]"], p.stderr[-400:])   # a channel took it; none did
        self.assertEqual([{k: v for k, v in r.items() if k != "at"} for r in self.sent_rows()],
                         [{"title": "a title", "body": "a body", "priority": "urgent"}] * 2)
        self.assertEqual([r["at"][-6:] for r in self.sent_rows()], ["+00:00"] * 2)

    def test_a_scenario_key_the_harness_does_not_know_is_refused_before_the_engine_starts(self):
        p = self.start_engine({"sesion": "open"}, "--minutes", "0.001")
        self.assertEqual(p.wait(timeout=10), 2)
        self.assertIn("sesion", p.stderr.read())
        self.assertFalse((self.state / "news_engine.lock").exists())

    def test_a_start_made_here_ends_at_23_59_new_york_unless_its_options_name_an_end(self):
        # the engine's own default is 16:05 New York: after the close a start would end before its first step
        with mock.patch.object(subprocess, "Popen") as popen:   # what start_engine would start, and no process
            for own in (("--minutes", "5"), ("--minutes", "5", "--until", "16:05"), ("--until=16:05",)):
                self.start_engine({}, *own)
        self._started.clear()                          # stand-ins: tearDown has nothing to end
        options = [c.args[0][c.args[0].index(str(self.sent_file)) + 1:] for c in popen.call_args_list]
        self.assertEqual(options, [["--until", "23:59", "--minutes", "5"], ["--minutes", "5", "--until", "16:05"],
                                   ["--until=16:05"]])

    def test_the_engine_child_hands_the_engine_its_options_as_they_came(self):
        # no end of its own: under a parent or in a drill the child ends by the clock as the real engine does
        engine = ("import json, sys; sys.path.insert(0, sys.argv[1]); from helpers import engine_child\n"
                  "engine_child.cli.main = lambda argv: print(json.dumps(argv))\n"   # the engine's command line, not run
                  "sys.exit(engine_child.main(sys.argv[2:]))")
        p = subprocess.run([sys.executable, "-c", engine, str(TESTS), "--state-dir", str(self.state), "--scenario",
                            self.scenario({}), "--sent", str(self.sent_file), "--minutes", "5"],
                           capture_output=True, text=True, env=no_phone.clean_env(), timeout=20)
        self.assertEqual((p.returncode, p.stdout), (0, '["news-live", "--minutes", "5"]\n'), p.stderr[-400:])


# Spec section 10 at its defaults: every key of the supervisor block but `slots` (Task 23), `watcher.drill_from`
# (Task 25) and the five switches, plus until_ny and free_text_max_chars, the two keys this plan adds.
SPEC = {"loop_seconds": 0.5, "healthy_seconds": 60, "backoff_first_seconds": 1, "backoff_max_seconds": 60, "max_restarts": 5,
        "restart_window_seconds": 600, "max_restarts_day": 20, "hang_seconds": 180, "start_grace_seconds": 60,
        "hang_term_grace_seconds": 5, "planned_stop_grace_seconds": 120, "lock_wait_seconds": 150,
        "stops_stale_seconds": 120, "up_hb_max_seconds": 60, "mark_gap_max_seconds": 150, "parent_stale_seconds": 180,
        "outage_report_seconds": 180, "end_of_day_slack_seconds": 60, "max_alerts_per_hour": 6, "alert_retry_seconds": 60,
        "alert_retry_minutes": 15, "send_timeout_seconds": 5, "held_names_in_line": 6, "max_line_bytes": 1200,
        "owner_tz": "Asia/Jerusalem", "launch_from_ny": "08:00", "launch_until_ny": "16:00",
        "handover_times_ny": ["09:18", "10:48", "12:28", "14:17"], "min_leg_minutes": 20, "max_leg_minutes": 110,
        "handover_target_seconds": 60, "long_timeout_ms": 32400000, "uptime_keep_days": 30,
        "receipts_keep_days": 30, "uptime_target": 0.99, "report_days": 14, "until_ny": "16:05", "free_text_max_chars": 200}
DEADMAN = {"ping_seconds": 180, "delay_seconds": 360, "handover_delay_seconds": 600, "fresh_seconds": 90,
           "retry_seconds": 30, "daily_limit_retry_after_seconds": 600, "reserve_messages": 15, "disarm_after_close_seconds": 60,
           "cancel_tries": 3, "cancel_retry_seconds": 20, "seq_margin_seconds": 20}
WATCHER = {"lookback_hours": 24, "ntfy_since": "35m", "stale_minutes": 90,
           "engine_window_ny": ["08:07", "16:01"], "quiet_hours": {"tz": "Asia/Jerusalem", "from": "23:00", "to": "08:00"},
           "max_cost_share": 0.2}
SWITCHES = [("hang_kill_enabled",), ("long_timeout_proven",), ("deadman", "enabled"), ("watcher", "fire_enabled"), ("watcher", "notify_enabled")]
SWITCHES_ON: list = []      # a rollout step that turns a switch on adds its path here, in the same commit as config.json


class Foundations(unittest.TestCase):
    """The parent's config, its own calendar, the uptime log, the state file (supervisor spec 4.3, 4.5, 4.6, 10) and the
    stand-in child its process tests start."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_the_supervisor_block_carries_the_defaults_of_spec_section_10(self):       # every key but the five switches
        cfg = supervise.load_cfg(); sup = cfg["supervisor"]
        self.assertEqual(({k: sup[k] for k in SPEC}, {k: sup["deadman"][k] for k in DEADMAN}, {k: sup["watcher"][k] for k in WATCHER}),
                         (SPEC, DEADMAN, WATCHER))
        self.assertEqual(cfg["alerts"]["ntfy_base_url"], "https://ntfy.sh")

    def test_a_switch_is_on_only_when_its_rollout_step_said_so(self):
        sup = supervise.load_cfg()["supervisor"]
        for path in SWITCHES:
            self.assertIs(functools.reduce(lambda d, k: d[k], path, sup), path in SWITCHES_ON, path)

    def test_the_owner_lines_say_the_numbers_the_config_holds(self):   # controller ruling 11: DM1, DM2 and R8 say them in words
        sup = supervise.load_cfg()["supervisor"]

        def said(line_id: str, pattern: str) -> int:
            return int(re.search(pattern, ownerlines.LINES[line_id][1]).group(1))
        self.assertEqual((sup["deadman"]["delay_seconds"], sup["deadman"]["handover_delay_seconds"], sup["long_timeout_ms"],
                          len(sup["handover_times_ny"])),
                         (said("DM1", r"יותר מ-(\d+) דקות") * 60, said("DM2", r"כבר (\d+) דקות") * 60,
                          said("R8", r"ההגדרה של (\d+) שעות") * 3600 * 1000, said("R8", r"מתוכננת (\d+) פעמים ביום")))

    def test_the_parents_calendar_equals_journal_session_hours_for_every_day_of_2026_and_2027(self):
        cal = supervise.load_cfg()["calendar"]
        for i in range(730):
            d = date(2026, 1, 1) + timedelta(days=i)
            self.assertEqual(supervise.session_hours(d, cal), journal.session_hours(d), d)
        # a weekday of the first year the calendar does not list is closed, as journal says (fail closed)
        after = next(d for d in (date(max(cal["years"]) + 1, 1, k) for k in range(2, 9)) if d.weekday() < 5)
        self.assertEqual((supervise.session_hours(after, cal), journal.session_hours(after)), (None, None))

    def test_an_append_after_a_torn_line_starts_a_new_line_and_the_reader_skips_the_torn_one(self):   # the file ends with '{"t": "x'
        path = self.tmp / "uptime.jsonl"
        path.write_text('{"t": "x')
        row = supervise.append_row(path, 4242, "mark", datetime(2026, 11, 12, 10, 0, 7, 900000, tzinfo=ZoneInfo("America/New_York")), hb=1.5)
        self.assertEqual([r["ev"] for r in supervise.read_rows(path)], ["mark"])
        self.assertEqual((supervise.read_rows(path), row),     # the row as returned and as read: t in UTC, whole seconds
                         ([row], {"t": "2026-11-12T15:00:07+00:00", "ev": "mark", "sup": 4242, "hb": 1.5}))

    def test_rows_older_than_the_keep_days_are_dropped(self):                     # rows 31 and 29 days old, keep 30
        path, now = self.tmp / "uptime.jsonl", datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
        for days in (31, 29):
            supervise.append_row(path, 4242, "mark", now - timedelta(days=days))
        supervise.prune_rows(path, 30, now)
        self.assertEqual(len(supervise.read_rows(path)), 1)
        self.assertEqual((supervise.read_rows(path)[0]["t"], sorted(p.name for p in self.tmp.iterdir())),
                         ("2026-10-14T15:00:00+00:00", ["uptime.jsonl"]))   # the younger row, and no tmp file left

    def test_a_state_file_of_another_day_keeps_the_halt_only_and_garbage_is_a_new_day(self):   # Review Focus 1 and 4
        path = self.tmp / "news_supervisor.json"
        supervise.save_state(path, {"day": "2026-11-11", "restarts_today": 7, "trips_today": 2,
                                    "halt": {"code": 4, "why": "halt", "at": "2026-11-11T15:20:00+00:00"},
                                    "alerts": {"hour": "2026-11-11T15", "sent": 6, "capped": 2},
                                    "reported_through": "2026-11-11T16:00:00+00:00", "last_commit": "aaa1111",
                                    "handover": {"at": "2026-11-11T19:17:00+00:00", "last_look": "2026-11-11T19:16:58+00:00"}})
        st = supervise.load_state(path, "2026-11-12")            # the file: day 2026-11-11, restarts_today 7, trips_today 2, a halt with code 4, a handover
        self.assertEqual((st["day"], st["restarts_today"], st["trips_today"], st["halt"]["code"], st["handover"]), ("2026-11-12", 0, 0, 4, None))
        self.assertEqual((st["alerts"], st["reported_through"], st["last_commit"]),
                         ({"hour": None, "sent": 0, "capped": 0}, "2026-11-11T16:00:00+00:00", "aaa1111"))
        path.write_text("{not json")
        self.assertEqual((supervise.load_state(path, "2026-11-12")["restarts_today"], supervise.load_state(path, "2026-11-12")["halt"]), (0, None))

    def test_a_state_file_that_does_not_parse_is_named_by_its_error_class_and_a_good_one_is_not(self):   # ruling P18(c)
        path = self.tmp / "news_supervisor.json"
        path.write_text('{"day": "2026-11-12", "restarts_today": 3, "halt": {"code": 4, "why": "halt", "at": "x"}')   # torn
        self.assertEqual(supervise.load_state(path, "2026-11-12")["load_error"], "JSONDecodeError")   # the class, never the text
        st = supervise.load_state(path, "2026-11-12")
        del st["load_error"]                                     # as main does before its first save
        supervise.save_state(path, {**st, "restarts_today": 3})
        good = supervise.load_state(path, "2026-11-12")
        self.assertEqual((good["restarts_today"], "load_error" in good), (3, False))
        path.unlink()                                            # no file: a first start, not a damaged file
        self.assertNotIn("load_error", supervise.load_state(path, "2026-11-12"))

    def test_supervise_imports_no_pandas_no_requests_and_no_engine_module(self):
        code = ("import sys, aitrader.supervise; sys.exit(1 if [m for m in ('pandas', 'requests', 'aitrader.journal',"
                " 'aitrader.notify', 'aitrader.news_live') if m in sys.modules] else 0)")
        self.assertEqual(subprocess.run([sys.executable, "-c", code], env=no_phone.clean_env()).returncode, 0)

    def test_prune_rows_refuses_a_time_without_a_zone(self):                     # ruling 30: else it would keep every row
        path = self.tmp / "uptime.jsonl"
        supervise.append_row(path, 4242, "mark", datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            supervise.prune_rows(path, 30, datetime(2026, 11, 12, 15, 0))

    def test_notify_posts_to_the_configured_address(self):                        # requests.post replaced; the topic set for this call only
        cfg = supervise.load_cfg()
        cfg["alerts"]["ntfy_base_url"] = "http://127.0.0.1:9"
        cfg.setdefault("market", {})["quiet_hours"] = None  # ruling 30: in quiet hours send would queue, not post
        posted_urls = []

        def post(url, **kw):
            posted_urls.append(url)
            return mock.Mock(ok=True)
        with mock.patch.object(notify.requests, "post", post), \
                mock.patch.dict(os.environ, {cfg["alerts"]["ntfy_topic_env"]: "t0p1c-under-test"}), \
                contextlib.redirect_stdout(io.StringIO()):     # send prints every line it sends: not into the test output
            self.assertEqual(notify.send("a title", "a body", cfg, "high"), ["ntfy"])
        self.assertEqual(posted_urls, ["http://127.0.0.1:9/"])

    def test_the_dummy_child_plays_run_n_at_start_n_and_never_ends_on_until(self):   # ruling P1 (it takes --until, ignores it)
        script, beat = self.tmp / "script.json", self.tmp / "news_heartbeat.json"
        script.write_text(json.dumps([{"beats": 0, "then": "exit", "code": 5},
                                      {"beats": 3, "every_s": 0.05, "then": "exit", "code": 6, "held": {"BBB": 48.5},
                                       "stop_age_s": [[300, 2], [7, 1]], "blind": ["BBB"], "commit": "bbb2222"}]))
        # 00:00 New York has passed at every hour of the day: a child that ended on --until would end at once with 0
        cmd = [sys.executable, str(DUMMY_CHILD), "--heartbeat", str(beat), "--script", str(script), "--until", "00:00"]
        codes = [subprocess.run(cmd, env=no_phone.clean_env(), capture_output=True, timeout=20).returncode for _ in range(3)]
        self.assertEqual((codes, Path(f"{script}.n").read_text().split()), ([5, 6, 6], ["3"]))   # the last run repeats
        hb = json.loads(beat.read_text())                        # the third beat of the third start
        at = datetime.fromisoformat(hb["at"])
        self.assertEqual((hb["phase"], hb["step"], hb["market_open"], hb["blind"], hb["code"]["commit"], hb["supervised"]),
                         ("idle", 3, True, ["BBB"], "bbb2222", False))
        self.assertEqual((hb["held"]["BBB"]["stop"], at - datetime.fromisoformat(hb["held"]["BBB"]["checked_at"])),
                         (48.5, timedelta(seconds=7)))


class RestartCore(unittest.TestCase):
    """restart_core alone (supervisor spec 4.3): fake children on a fake clock; no process, no file, no wall clock."""

    def core(self, children: list, near_until: bool = False, counts: dict | None = None, orders: dict | None = None,
             **pol) -> tuple[int, str]:
        """restart_core over fake children [(ran_s, rc), ...], started in that order, at the spec's defaults with `pol`
        over them, from fresh counts unless given. The clock starts at 0 and moves only when the core sleeps. `orders`
        maps a fake time to what watch answers from that time on. Keeps self.backoffs (the wait before each restart),
        self.counts and self.clock; self.emitted(ev) gives the rows of one kind."""
        self.clock, self.rows = 0.0, []
        self.counts = counts if counts is not None else {"restarts_today": 0, "stamps": []}
        queue, orders = list(children), orders or {}
        test = self

        class Child:
            def __init__(self, ran_s, rc):
                self.pid, self.end, self.rc = 1000 + len(children) - len(queue), test.clock + ran_s, rc

            def poll(self):
                return self.rc if test.clock >= self.end else None

        def spawn():
            self.assertTrue(queue, "a start the test did not expect")
            return Child(*queue.pop(0))

        def watch(child, ran_s):
            due = [t for t in orders if t <= self.clock]
            return orders[max(due)] if due else None

        def stop(child, how):          # the child ends at once: 143 after a planned stop, killed after a hang
            child.end, child.rc = self.clock, 143 if how == "planned" else -signal.SIGKILL

        def sleep(s):
            self.clock += s
        out = supervise.restart_core(spawn, watch, stop, lambda: near_until, lambda ev, **f: self.rows.append({"ev": ev, **f}),
                                     {**SPEC, **pol}, self.counts, mono=lambda: self.clock, sleep=sleep)
        self.backoffs = [r["backoff_s"] for r in self.emitted("start")[1:]]
        return out

    def emitted(self, ev: str) -> list[dict]:
        return [{k: v for k, v in r.items() if k != "ev"} for r in self.rows if r["ev"] == ev]

    def test_five_quick_crashes_back_off_1_2_4_8_16_and_the_sixth_trips(self):
        self.assertEqual(self.core([(0.1, 1)] * 6), (75, "crash_loop"))
        self.assertEqual((self.backoffs, self.counts["restarts_today"]), ([1, 2, 4, 8, 16], 5))

    def test_a_child_that_ran_60_s_is_restarted_at_once(self):
        self.assertEqual(self.core([(60, 1), (1, 0)], near_until=True), (0, "end_of_day"))
        self.assertEqual(self.backoffs, [0])
        self.core([(0.1, 1), (60, 1), (0.1, 1), (1, 0)], near_until=True)     # after a healthy run the doubling starts again
        self.assertEqual(self.backoffs, [1, 0, 1])

    def test_the_day_limit_trips_with_a_clear_window(self):
        self.assertEqual(self.core([(700, 1)], counts={"restarts_today": 20, "stamps": []}), (75, "crash_loop"))

    def test_the_code_table(self):
        for rc in (4, 5, 6):
            self.assertEqual(self.core([(5, rc)]), (rc, "halt"))
        self.assertEqual(self.core([(0.1, 3)] * 99), (3, "lock_held"))
        self.assertEqual((self.clock >= 150, self.counts["restarts_today"]), (True, 0))
        self.assertLess(self.clock, 152)            # the last try at the end of the 150 s, not a 60 s back-off after it
        self.assertEqual(self.core([(0.1, 7), (1, 0)], near_until=True), (0, "end_of_day"))
        self.assertEqual(self.emitted("exit")[0]["why"], "tree_busy")
        self.assertEqual(self.core([(30, 143), (1, 0)], near_until=True), (0, "end_of_day"))    # an unasked 143: one restart
        self.assertEqual(self.counts["restarts_today"], 1)
        self.assertEqual(self.core([(0.1, 0)] * 6), (75, "crash_loop"))                         # a 0 far from --until is a crash

    def test_near_until_is_one_sided(self):
        def at(hm):
            return datetime(2026, 11, 12, *map(int, hm.split(":")), tzinfo=NY)
        self.assertEqual([supervise.near_until(at(t), "16:05", 60) for t in ("16:02", "16:03", "16:04", "16:05", "16:10", "17:30")],
                         [False, False, True, True, True, True])

    def test_a_stop_order_during_a_back_off_ends_it_without_a_start(self):   # Review Focus 2: watch answers "signal" in the wait
        self.assertEqual(self.core([(0.1, 1)], backoff_first_seconds=30, orders={0.5: "signal"}), (143, "signal"))
        self.assertEqual(len(self.emitted("start")), 1)


# The parent in a process of its own (argv: a JSON object with main's argv, the child's command and the clock's offset
# in seconds): what spawn_parent starts. Its clock is the real one moved by the offset, as run_parent's is.
PARENT_WRAPPER = """import json, sys
from datetime import datetime, timedelta, timezone
from aitrader import supervise
a = json.loads(sys.argv[1])
offset = timedelta(seconds=a["offset_s"])
sys.exit(supervise.main(a["argv"], child_cmd=a["child_cmd"], clock=lambda: datetime.now(timezone.utc) + offset))"""

# Starts the command of its argv, prints that process's pid and ends when its own stdin is closed: the process it
# started then loses its parent.
HELPER = """import subprocess, sys
p = subprocess.Popen(sys.argv[1:], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(p.pid, flush=True)
sys.stdin.read()"""


# A child with a process of its own in its group (argv: where to write that process's pid): `sleep 60`, then it waits;
# SIGTERM ends it with 143.
GROUP_CHILD = """import os, signal, subprocess, sys
signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
g = subprocess.Popen(["sleep", "60"])
open(sys.argv[1] + ".tmp", "w").write(str(g.pid))
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
signal.pause()"""


def saturday() -> datetime:
    """A clock that says 2026-11-14 15:00 UTC, a Saturday: no session."""
    return datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)


def flockable(path: Path) -> bool:
    """Nobody holds an flock on the file now."""
    with open(path, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
    return True


class Parents(Procs):
    """The supervisor's parent (supervise.main) on self.state, with the dummy child unless a test names another. Its
    config is a copy of config.json with a quick loop, a quick back-off and a 1-second healthy run, and with the five
    switches pinned off (ruling P29). Its clock is the real one moved so that the test starts at 10:00 New York on
    Thursday 2026-11-12, a session day, whatever the hour: only the calendar questions read that clock."""

    QUICK = {"loop_seconds": 0.05, "backoff_first_seconds": 0.05, "healthy_seconds": 1}

    def setUp(self):
        super().setUp()
        self.offset = datetime(2026, 11, 12, 10, 0, tzinfo=NY) - datetime.now(timezone.utc)
        self._scripts = 0

    def clock(self) -> datetime:
        return datetime.now(timezone.utc) + self.offset

    def config(self, **sup) -> Path:
        """The config copy, with `sup` over its supervisor block; its path."""
        cfg = supervise.load_cfg()
        cfg["supervisor"].update({**self.QUICK, "hang_kill_enabled": False, "long_timeout_proven": False, **sup})
        cfg["supervisor"]["deadman"]["enabled"] = False
        cfg["supervisor"]["watcher"].update(fire_enabled=False, notify_enabled=False)
        path = self.tmp / "config.json"
        path.write_text(json.dumps(cfg))
        return path

    def dummy_cmd(self, script: list) -> list[str]:
        """The dummy child on this script (a file of its own, so its start count is its own)."""
        self._scripts += 1
        path = self.tmp / f"script-{self._scripts}.json"
        path.write_text(json.dumps(script))
        return [sys.executable, str(DUMMY_CHILD), "--heartbeat", str(self.state / "news_heartbeat.json"), "--script", str(path)]

    def engine_cmd(self, scenario: dict) -> list[str]:
        """engine_child.py on self.state with this scenario, behind the tripwire."""
        return [sys.executable, str(ENGINE_CHILD), "--state-dir", str(self.state), "--scenario", self.scenario(scenario),
                "--sent", str(self.sent_file)]

    def parent_argv(self, argv: tuple, sup: dict) -> list[str]:
        """main's argv: the state directory, the config copy, then argv. `--until 24:00` comes first when argv names no
        end (rulings P1 and 16): main hands its --until to the child, an engine child ends by the real New York clock,
        and 24:00 never comes, so a test runs the same at any hour. The parent's own clock is the moved one."""
        until = () if "--until" in argv else ("--until", "24:00")
        return ["--state-dir", str(self.state), "--config", str(self.config(**sup)), *until, *argv]

    def run_parent(self, script, *argv, clock=None) -> int:
        """supervise.main in this process with the dummy child on this script; its return code. Its stdout is kept in
        self.out."""
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = supervise.main(self.parent_argv(argv, {}), child_cmd=self.dummy_cmd(script), env=no_phone.clean_env(),
                                clock=clock or self.clock)
        self.out = out.getvalue()
        return rc

    def parent_cmd(self, script, *argv, child_cmd=None, **sup) -> list[str]:
        """The command of a parent in a process of its own (PARENT_WRAPPER)."""
        spec = {"argv": self.parent_argv(argv, sup), "child_cmd": child_cmd or self.dummy_cmd(script),
                "offset_s": self.offset.total_seconds()}
        return [sys.executable, "-c", PARENT_WRAPPER, json.dumps(spec)]

    def spawn_parent(self, script, *argv, child_cmd=None, **sup) -> subprocess.Popen:
        p = subprocess.Popen(self.parent_cmd(script, *argv, child_cmd=child_cmd, **sup), stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=no_phone.clean_env())
        self._started.append(p)
        return p

    def urows(self, ev: str | None = None) -> list[dict]:
        """The rows of the uptime log, of one kind when ev is given."""
        return [r for r in supervise.read_rows(self.state / "uptime.jsonl") if ev in (None, r["ev"])]

    def state_file(self) -> dict:
        return json.loads((self.state / "news_supervisor.json").read_text())

    def sup_log(self) -> str:
        return (self.state / ".cache" / "supervise.log").read_text()

    def files(self) -> dict:
        """Every file under the state directory and its bytes, but the heartbeat a running child keeps rewriting."""
        return {str(p.relative_to(self.state)): p.read_bytes() for p in sorted(self.state.rglob("*"))
                if p.is_file() and not p.name.startswith("news_heartbeat.json")}

    def kill_ours(self, pid: int) -> None:
        """SIGKILL to a parent or a child this test started that outlived it, and never to a pid that was reused."""
        try:
            argv = set(Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0"))
            if argv & {PARENT_WRAPPER.encode(), GROUP_CHILD.encode(), str(DUMMY_CHILD).encode(), str(ENGINE_CHILD).encode()}:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def kill_sleep(self, pid: int) -> None:
        """SIGKILL to the `sleep 60` that GROUP_CHILD started, and only to that: never to a pid that was reused."""
        try:
            if Path(f"/proc/{pid}/cmdline").read_bytes() == b"sleep\x0060\x00":
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


class ParentLoop(Parents):
    """The parent's loop on real processes (supervisor spec 4.2, 4.3, 4.5; section 3, rows 1, 4, 6 and 11)."""

    def test_a_killed_child_beats_again_within_1_s(self):
        self.spawn_parent([{"beats": -1}]); first = self.wait_beat()
        t0 = time.time(); os.kill(first["pid"], signal.SIGKILL)
        self.wait_for(lambda: self.beat().get("pid") not in (None, first["pid"]))
        self.assertLess((self.state / "news_heartbeat.json").stat().st_mtime - t0, 1.0)

    def test_a_child_that_always_fails_ends_with_75_after_5_restarts(self):
        self.assertEqual(self.run_parent([{"beats": 0, "then": "exit", "code": 1}]), 75)
        self.assertEqual(len(self.urows("start")), 6)
        self.assertEqual([(r["restarts"], r["trips_today"]) for r in self.urows("tripped")], [(5, 1)])
        self.assertEqual([(r["why"], r["rc"]) for r in self.urows("sup_stop")], [("crash_loop", 75)])
        self.assertEqual((self.state_file()["restarts_today"], self.state_file()["trips_today"]), (5, 1))
        self.assertEqual(self.out.splitlines(), [f"supervise: pid {os.getpid()}, until 24:00, handover off", "supervise: 75 tripped."
                                                 " Run python3 -m aitrader.supervise --status and do what action says."])

    def test_a_day_with_no_session_starts_no_child(self):                    # 2026-11-14 is a Saturday
        self.assertEqual(self.run_parent([{"beats": -1}], clock=lambda: datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)), 0)
        self.assertEqual([(r["ev"], r.get("why")) for r in self.urows()], [("sup_start", None), ("sup_stop", "closed_today")])
        self.assertFalse((self.state / "news_heartbeat.json").exists())       # no child ever beat
        first, stop = self.urows()
        self.assertEqual({k: first[k] for k in ("until", "handover", "timeout_ms", "prev_t", "prev_ev", "gap_s", "cold")},
                         {"until": "24:00", "handover": False, "timeout_ms": 32400000, "prev_t": None, "prev_ev": None,
                          "gap_s": None, "cold": True})
        self.run_parent([{"beats": -1}], "--handover", clock=saturday)         # a second parent with --handover, at once
        again = self.urows("sup_start")[1]
        self.assertEqual((again["handover"], again["timeout_ms"], again["prev_t"], again["prev_ev"], again["gap_s"]),
                         (True, 7200000, stop["t"], "sup_stop", 0))

    def test_a_second_parent_returns_3_names_the_holder_and_writes_nothing(self):   # uptime.jsonl bytes unchanged
        first = self.spawn_parent([{"beats": -1}]); self.wait_beat()
        self.wait_for(lambda: self.urows("code"))      # the first parent's rows of its child's first beats: `up`, then `code`
        before = self.files()
        second = self.spawn_parent([{"beats": -1}])
        self.assertEqual((second.wait(timeout=5), f"pid {first.pid}" in second.stdout.read()), (3, True))
        self.assertEqual(self.files(), before)

    def test_sigterm_stops_the_child_and_the_parent_ends_with_143(self):
        p = self.spawn_parent([{"beats": -1}]); self.wait_beat()           # the child beats: its SIGTERM handler is set (ruling 30)
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=5), 143)
        self.assertEqual(([(r["rc"], r["why"]) for r in self.urows("exit")], self.urows("sup_stop")[0]["why"]),
                         ([(143, "planned")], "signal"))

    def test_a_second_sigterm_while_the_child_is_finishing_changes_nothing(self):   # Review Focus 2: the run has "ignore_term" true,
        p = self.spawn_parent([{"beats": -1, "ignore_term": True}], planned_stop_grace_seconds=1); self.wait_beat()
        p.send_signal(signal.SIGTERM)
        time.sleep(0.3); p.send_signal(signal.SIGTERM)                       # inside the second the child is given to finish
        self.assertEqual((p.wait(timeout=10), len(self.urows("sup_stop"))), (143, 1))   # planned_stop_grace_seconds 1
        self.assertEqual([(r["rc"], r["signal"], r["why"]) for r in self.urows("exit")], [(None, 9, "planned")])   # the grace ran out
        self.assertIn("SIGKILL", self.sup_log())

    def test_a_parent_that_loses_its_own_parent_stops_with_orphaned(self):   # started by a helper process that then exits
        helper = subprocess.Popen([sys.executable, "-c", HELPER, *self.parent_cmd([{"beats": -1}])], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=no_phone.clean_env())
        self._started.append(helper)
        parent = int(helper.stdout.readline())
        self.addCleanup(self.kill_ours, parent)
        self.wait_beat()          # the parent runs and has read its own parent's pid; an earlier exit would make it born orphaned
        helper.stdin.close(); helper.wait(timeout=5)
        self.wait_for(lambda: self.urows("sup_stop"))
        self.assertEqual(self.urows("sup_stop")[0]["why"], "orphaned")
        self.wait_for(lambda: self.dead(parent))

    def test_kill_9_of_the_parent_leaves_no_child_and_both_locks_free(self):
        p = self.spawn_parent(None, child_cmd=self.engine_cmd({"news": {"poll_seconds": 30}}))   # the engine takes its own lock
        child_pid = self.wait_for(lambda: self.beat().get("pid"), timeout=20)
        self.addCleanup(self.kill_ours, child_pid)
        p.kill(); p.wait()
        end = time.monotonic() + 1
        self.wait_for(lambda: self.dead(child_pid), timeout=1)               # then both lock files can be flocked
        # The engine's main thread shows as a zombie a moment before its other threads let go of its files (EngineStop):
        # the locks are asked until the second ends.
        self.wait_for(lambda: flockable(self.state / "news_supervisor.lock") and flockable(self.state / "news_engine.lock"),
                      timeout=max(0.0, end - time.monotonic()))

    def test_a_child_that_ends_with_0_at_until_or_minutes_after_it_is_the_end_of_the_day(self):   # --until 10:00 and --until 09:55,
        for until in ("10:00", "09:55"):                                                          # the clock at 10:00
            with self.subTest(until=until):
                shutil.rmtree(self.state); self.state.mkdir()
                rc = self.run_parent([{"beats": 0, "then": "exit", "code": 0}], "--until", until)
                self.assertEqual((rc, self.urows("sup_stop")[0]["why"], len(self.urows("start"))), (0, "end_of_day", 1))

    def test_a_child_that_ends_with_0_two_minutes_before_until_is_restarted(self):   # --until 10:02; runs: exit 0, then beats;
        p = self.spawn_parent([{"beats": 0, "then": "exit", "code": 0}, {"beats": -1}], "--until", "10:02")
        # spawn_parent, and SIGTERM once the second start is on record and its child beats (its SIGTERM handler is set)
        self.wait_for(lambda: len(self.urows("start")) >= 2 and self.beat().get("pid") == self.urows("start")[1]["child"])
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=5), 143)
        self.assertEqual(([r["rc"] for r in self.urows("exit")][:1], len(self.urows("start")) >= 2), ([0], True))

    def test_a_planned_stop_signals_the_child_alone_and_not_its_group(self):   # spec 5.3: a scorer call in flight can finish
        pid_file = self.tmp / "grandchild.pid"
        p = self.spawn_parent(None, child_cmd=[sys.executable, "-c", GROUP_CHILD, str(pid_file)])
        grandchild = int(self.wait_for(lambda: pid_file.exists() and pid_file.read_text()))
        self.addCleanup(self.kill_sleep, grandchild)
        self.addCleanup(self.kill_ours, self.urows("start")[0]["child"])     # it does not die with its parent
        p.send_signal(signal.SIGTERM)
        self.assertEqual((p.wait(timeout=5), [(r["rc"], r["why"]) for r in self.urows("exit")]), (143, [(143, "planned")]))
        self.assertFalse(self.dead(grandchild))                                 # in the child's group, and not signalled

    # Tests added by ruling.
    def test_a_state_file_that_does_not_parse_is_named_in_the_log_and_saved_whole(self):     # ruling P18(c)
        (self.state / "news_supervisor.json").write_text('{"day": "2026-11-14", "restarts_today": 3')   # torn
        self.assertEqual(self.run_parent([{"beats": -1}], clock=saturday), 0)
        self.assertEqual((self.sup_log().count("JSONDecodeError"), "load_error" in self.state_file()), (1, False))

    def test_an_uptime_log_that_cannot_be_written_does_not_stop_the_parent(self):            # ruling 30 (spec 4.6)
        (self.state / "uptime.jsonl").mkdir()                                  # it can be neither read nor written
        self.assertEqual(self.run_parent([{"beats": 0, "then": "exit", "code": 0}], "--until", "10:00"), 0)
        self.assertEqual((self.out.splitlines()[-1].split(".")[0], self.state_file()["restarts_today"]), ("supervise: 0 end_of_day", 0))
        self.assertIn("IsADirectoryError", self.sup_log())

    def test_a_state_directory_that_does_not_exist_yet_is_made(self):                         # ruling 30: before the lock and the log
        shutil.rmtree(self.state)
        self.assertEqual(self.run_parent([{"beats": -1}], clock=saturday), 0)
        self.assertEqual(([r["ev"] for r in self.urows()], self.sup_log() != ""), (["sup_start", "sup_stop"], True))

    # Test added by the review (Task 11, F1).
    def test_a_weekday_of_a_year_the_calendar_does_not_list_starts_the_engine_and_halts_on_its_5(self):   # spec 4.3, code 5
        cal = supervise.load_cfg()["calendar"]                                 # the config copy's calendar is this one
        days = [date(max(cal["years"]) + 1, 1, k) for k in range(2, 9)]
        at = lambda d: (lambda: datetime(d.year, d.month, d.day, 15, 0, tzinfo=timezone.utc))   # 10:00 New York (EST)
        # The dummy child stands in for the engine's start check 1 (news_live.start_checks): the calendar does not cover
        # today, its urgent line, exit 5. Not "closed_today" on a weekday: that would skip the check, its line and every
        # stop look. On a weekend there is no stop to look at: still closed_today, and no child.
        refuses = [{"beats": 0, "then": "exit", "code": 5}]
        weekend = next(d for d in days if d.weekday() >= 5)
        self.assertEqual(self.run_parent(refuses, clock=at(weekend)), 0)
        weekday = next(d for d in days if d.weekday() < 5)
        self.assertEqual(self.run_parent(refuses, clock=at(weekday)), 5)
        self.assertEqual((len(self.urows("start")), [(r["why"], r["rc"]) for r in self.urows("sup_stop")]),
                         (1, [("closed_today", 0), ("halt", 5)]))
        self.assertEqual((self.state_file()["halt"]["code"], self.state_file()["halt"]["why"]), (5, "calendar"))


class Watching(Parents):
    """What the parent reads in the heartbeat and writes from it (supervisor spec 4.3, 4.6; section 3, rows 2, 3 and
    17): a mark a minute, `up` and `code` at a child's first looks, a hang, stale stops."""

    def stop_parent(self, p: subprocess.Popen, settle: float = 0.5) -> int:
        """A few more loop ticks (a row that should come once has its chance to come twice), then SIGTERM; its code."""
        time.sleep(settle)
        p.send_signal(signal.SIGTERM)
        return p.wait(timeout=10)

    def test_open_seconds_is_cut_to_the_session(self):          # Review Focus 3: 2026-11-27 closes at 13:00 New York, 18:00 UTC
        cal, utc = supervise.load_cfg()["calendar"], lambda h, m: datetime(2026, 11, 27, h, m, tzinfo=timezone.utc)
        self.assertEqual(supervise.open_seconds(utc(17, 50), utc(18, 30), cal), 600)
        self.assertEqual(supervise.open_seconds(utc(14, 0), utc(14, 40), cal), 600)      # the open is 14:30 UTC

    def test_a_frozen_child_is_killed_and_replaced(self):        # hang_seconds 2, the switch on; the run: 5 beats, then "hang"
        p = self.spawn_parent([{"beats": 5, "then": "hang"}], hang_seconds=2, hang_kill_enabled=True)
        # SIGTERM once the second child beats: it hangs too, but only 5 beats and 2 s later
        self.wait_for(lambda: len(self.urows("start")) >= 2 and self.beat().get("pid") == self.urows("start")[1]["child"],
                      timeout=10)
        self.assertEqual(self.stop_parent(p, settle=0), 143)
        self.assertEqual(([r["killed_with"] for r in self.urows("hang")], len(self.urows("start"))), (["TERM"], 2))

    def test_with_the_switch_off_a_hang_is_logged_once_and_nothing_is_signalled(self):
        p = self.spawn_parent([{"beats": 5, "then": "hang"}], hang_seconds=2)      # the switch is pinned off (Parents)
        self.wait_for(lambda: self.urows("hang"), timeout=10)
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual(([r["killed_with"] for r in self.urows("hang")], len(self.urows("start"))), (["none"], 1))

    def test_a_new_child_has_the_start_grace_for_its_first_beat(self):    # hang_seconds 1, start_grace_seconds 5, "first_after_s" 3
        p = self.spawn_parent([{"first_after_s": 3, "beats": 20, "then": "exit", "code": 0}], "--until", "10:00",
                              hang_seconds=1, start_grace_seconds=5)   # beats for 2 s, then the end of the day
        self.assertEqual(p.wait(timeout=20), 0)
        self.assertEqual(self.urows("hang"), [])

    def test_a_beat_left_by_another_pid_is_no_beat(self):        # Review Focus 1: a fresh heartbeat file with pid 1, a child that never beats
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        (self.state / "news_heartbeat.json").write_text(json.dumps(
            {"at": now, "pid": 1, "phase": "idle", "market_open": True, "held": {}, "blind": [], "stops_checked_at": now}))
        # hang_seconds 60: taken for the child's own, that beat would stay fresh for the whole test and no hang would come
        p = self.spawn_parent([{"beats": 0, "then": "hang"}], hang_seconds=60, start_grace_seconds=1)
        self.wait_for(lambda: self.urows("hang"), timeout=10)
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual(len(self.urows("hang")), 1)

    def test_stale_stops_start_once_and_end_once(self):          # BBB held; "stop_age_s" [[300, 20], [0, 1]]; stops_stale_seconds 1
        p = self.spawn_parent([{"held": {"BBB": 48.5}, "stop_age_s": [[300, 20], [0, 1]]}], stops_stale_seconds=1)
        self.wait_for(lambda: len(self.urows("stale_stops")) >= 2, timeout=10)
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual([r["what"] for r in self.urows("stale_stops")], ["start", "end"])

    def test_up_says_what_the_restart_cost(self):                # BBB held at a stop of 48.5; the child is killed once
        p = self.spawn_parent([{"held": {"BBB": 48.5}}])
        first = self.wait_for(lambda: self.urows("up"))[0]
        os.kill(first["child"], signal.SIGKILL)
        self.wait_for(lambda: len(self.urows("up")) >= 2)
        self.assertEqual(self.stop_parent(p, settle=0), 143)
        up = self.urows("up")[-1]
        self.assertEqual((up["held"], up["blind"], up["commit"], up["handover_s"], up["sold"]), ({"BBB": 48.5}, [], None, None, []))
        self.assertGreater(up["down_s"], 0)

    def test_up_is_written_while_a_held_name_is_blind(self):     # Review Focus 1: the run has BBB held, "blind": ["BBB"], "stop_age_s" 3000
        p = self.spawn_parent([{"held": {"BBB": 48.5}, "blind": ["BBB"], "stop_age_s": 3000}])
        self.wait_for(lambda: self.urows("up"))
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual([(r["held"], r["blind"]) for r in self.urows("up")], [({"BBB": 48.5}, ["BBB"])])

    def test_the_real_engine_gets_a_code_row_after_its_up_row(self):   # engine_child.py as child_cmd, session "open", BBB held
        self.write_book({"BBB": 50.0})
        p = self.spawn_parent(None, child_cmd=self.engine_cmd({"session": "open", "prices": {"BBB": 50.0}}))   # --until 24:00 (P1)
        self.wait_for(lambda: self.urows("code"), timeout=20)
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual([(r["ev"], r.get("commit")) for r in self.urows() if r["ev"] in ("up", "code")], [("up", None), ("code", "abc1234")])

    def test_code_changed_compares_with_the_child_before(self):        # dummy runs with "commit" aaa1111, aaa1111, bbb2222; killed twice
        p = self.spawn_parent([{"commit": "aaa1111"}, {"commit": "aaa1111"}, {"commit": "bbb2222"}])
        for n in (1, 2):
            os.kill(self.wait_for(lambda: len(self.urows("code")) >= n and self.urows("code")[n - 1])["child"], signal.SIGKILL)
        self.wait_for(lambda: len(self.urows("code")) >= 3)
        self.assertEqual(self.stop_parent(p, settle=0), 143)
        self.assertEqual([r["code_changed"] for r in self.urows("code")], [False, False, True])

    def test_a_mark_is_due_once_per_clock_minute(self):
        t = lambda s: datetime(2026, 11, 12, 15, 0, s, tzinfo=timezone.utc)
        self.assertEqual([supervise.mark_due(None, t(5)), supervise.mark_due(t(5), t(59)), supervise.mark_due(t(5), t(59) + timedelta(seconds=1))], [True, False, True])

    # Tests added by ruling.
    def test_the_stop_age_grows_with_the_beats_own_age(self):          # ruling P16: (at - the oldest stamp) + the beat's age
        at = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
        hb = {"at": at.isoformat(), "pid": 7, "phase": "score", "market_open": True, "blind": [],
              "held": {"AAA": {"stop": 97.0, "checked_at": (at - timedelta(seconds=30)).isoformat()},
                       "BBB": {"stop": 48.5, "checked_at": (at - timedelta(seconds=100)).isoformat()}}}
        view = supervise.beat_view(hb, 1000.0, 7, 1050.0)               # the file was written 50 s ago: one long call
        self.assertEqual(view, {"mine": True, "age_s": 50.0, "stop_age_s": 150.0, "held": {"AAA": 97.0, "BBB": 48.5},
                                "open": True, "blind": [], "phase": "score"})
        other, empty = supervise.beat_view(hb, 1000.0, 8, 1050.0), supervise.beat_view({**hb, "held": {}}, 1000.0, 7, 1050.0)
        self.assertEqual((other["mine"], other["held"], empty["stop_age_s"]), (False, {}, None))   # another pid's beat; nothing held

    def test_a_sale_in_the_second_the_parent_started_is_in_up_sold(self):   # ruling P14: logged_at against the whole second
        time.sleep(1.01 - time.time() % 1)          # just after a second turns: the parent below starts inside this second
        second = datetime.fromtimestamp(int(time.time()), timezone.utc)
        rows = [{"side": "SELL", "symbol": "AAA", "logged_at": (second - timedelta(seconds=1)).isoformat()},   # before the start
                {"side": "BUY", "symbol": "BBB", "logged_at": second.isoformat()},
                {"side": "SELL", "symbol": "BBB", "logged_at": second.isoformat()}]
        (self.state / "news_trades.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        self.assertEqual(self.run_parent([{"beats": 3, "then": "exit", "code": 0}], "--until", "10:00"), 0)
        self.assertEqual([r["symbol"] for r in self.urows("up")[0]["sold"]], ["BBB"])
        self.assertEqual(self.urows("up")[0]["sold"][0]["side"], "SELL")

    # Tests added in self-review: the mark's fields, and where blind_s is measured from and to.
    def test_a_mark_carries_the_fields_of_spec_4_6(self):           # the clock turns a minute while the child beats
        start = datetime.now(timezone.utc)
        moved = datetime(2026, 11, 12, 10, 0, 59, tzinfo=NY) - start
        script = [{"beats": 30, "held": {"BBB": 48.5}, "then": "exit", "code": 0}]      # 3 s of beats
        self.assertEqual(self.run_parent(script, "--until", "10:00", clock=lambda: datetime.now(timezone.utc) + moved), 0)
        first, second = self.urows("mark")                                # 10:00:59 with no child yet, 10:01:00 beside it
        self.assertEqual({k: first[k] for k in ("hb", "stop", "n", "open", "blind", "dm", "left")},
                         {"hb": None, "stop": None, "n": None, "open": None, "blind": [], "dm": None, "left": None})
        self.assertEqual((second["n"], second["open"], second["blind"], second["dm"], second["left"]), (1, True, [], None, None))
        self.assertLess(max(second["hb"], second["stop"]), 1.0)

    def test_blind_s_runs_from_the_last_look_before_the_start_to_the_first_look_after(self):   # spec 4.6; section 3, row 17
        last = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=40)
        (self.state / "news_heartbeat.json").write_text(json.dumps(    # what the engine before this one left
            {"at": last.isoformat(), "pid": 1, "phase": "idle", "market_open": True, "stops_checked_at": last.isoformat(),
             "held": {"BBB": {"stop": 48.5, "checked_at": last.isoformat()}}, "blind": []}))
        asked, began = [], int(time.time())
        script = [{"beats": 10, "held": {"BBB": 48.5}, "blind": ["BBB"], "stop_age_s": 3000, "then": "exit", "code": 0}]
        with mock.patch.object(supervise, "open_seconds", lambda a, b, cal: asked.append((a, b)) or 42.0):
            self.assertEqual(self.run_parent(script, "--until", "10:00"), 0)   # open_seconds reads the real calendar: not the hour here
        (a, b), = asked
        # to: BBB is blind, so the `at` of the beat that wrote `up` (a whole second of this run), not its stamp of 3000 s ago
        self.assertEqual((self.urows("up")[0]["blind_s"], a, began <= b.timestamp() <= time.time()), (42.0, last, True))

    # Tests added from the mutation pass: behaviour the brief specifies that no test above would miss.
    def test_first_look_done_wants_this_childs_own_look_at_every_held_name(self):   # spec 4.6, `up`
        at = datetime.now(timezone.utc)
        started = at.timestamp() - 1
        beat = {"pid": 7, "phase": "stops", "blind": [], "held": {"BBB": {"stop": 48.5, "checked_at": at.isoformat()}}}
        old = {**beat, "held": {"BBB": {"stop": 48.5, "checked_at": (at - timedelta(seconds=5)).isoformat()}}}   # the run before's look
        self.assertEqual([supervise.first_look_done(beat, 7, started), supervise.first_look_done(beat, 8, started),
                          supervise.first_look_done({**beat, "phase": "boot", "held": {}}, 7, started),
                          supervise.first_look_done(old, 7, started), supervise.first_look_done({**old, "blind": ["BBB"]}, 7, started),
                          supervise.first_look_done(None, 7, started)],
                         [True, False, False, False, True, False])

    def test_with_the_market_closed_up_comes_at_the_first_beat(self):        # no look is due: the old stamp does not hold it back
        p = self.spawn_parent([{"open": False, "held": {"BBB": 48.5}, "stop_age_s": 3000}])
        self.wait_for(lambda: self.urows("up"))
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual([r["held"] for r in self.urows("up")], [{"BBB": 48.5}])

    def test_a_hang_kill_reaches_the_childs_whole_group(self):    # spec 4.3: what the hung engine waits on goes with it
        pid_file = self.tmp / "grandchild.pid"
        # GROUP_CHILD never beats: a hang once the grace is over. max_restarts 0: the kill trips the parent, no second child
        p = self.spawn_parent(None, child_cmd=[sys.executable, "-c", GROUP_CHILD, str(pid_file)], hang_kill_enabled=True,
                              start_grace_seconds=1, max_restarts=0)
        grandchild = int(self.wait_for(lambda: pid_file.exists() and pid_file.read_text()))
        self.addCleanup(self.kill_sleep, grandchild)
        self.assertEqual(p.wait(timeout=15), 75)
        self.assertEqual([r["killed_with"] for r in self.urows("hang")], ["TERM"])
        self.wait_for(lambda: self.dead(grandchild), timeout=2)       # the `sleep 60` in the child's group got the SIGTERM

    def test_a_hung_child_that_ignores_sigterm_gets_sigkill_and_hb_is_its_beats_age(self):
        script = [{"first_after_s": 1, "beats": 2, "then": "hang", "ignore_term": True}]   # the hang comes 2 s after the start
        p = self.spawn_parent(script, hang_kill_enabled=True, hang_seconds=1, start_grace_seconds=5, hang_term_grace_seconds=1,
                              max_restarts=0)
        self.assertEqual(p.wait(timeout=15), 75)
        (hang,), (end,) = self.urows("hang"), self.urows("exit")
        self.assertEqual((hang["killed_with"], hang["phase"], end["rc"], end["signal"], end["why"]), ("KILL", "idle", None, 9, "hang"))
        self.assertTrue(1.0 <= hang["hb"] < 1.5 < end["ran_s"] - 1, (hang, end))   # the beat's age, not the time since the start

    def test_a_hung_child_is_a_hang_and_not_stale_stops(self):    # stale stops need a fresh beat (spec 4.3): during a hang
        p = self.spawn_parent([{"beats": 3, "then": "hang", "held": {"BBB": 48.5}}], hang_seconds=1, stops_stale_seconds=2)
        self.wait_for(lambda: self.urows("hang"), timeout=10)        # the switch is off: the child stays, its beat ages on
        self.wait_for(lambda: time.time() - (self.state / "news_heartbeat.json").stat().st_mtime > 2.5, timeout=10)
        self.assertEqual(self.stop_parent(p), 143)
        self.assertEqual(([r["killed_with"] for r in self.urows("hang")], self.urows("stale_stops")), (["none"], []))
