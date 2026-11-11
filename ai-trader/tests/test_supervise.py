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

    def test_notify_posts_to_the_configured_address(self):                        # requests.post replaced; the topic set for this call only
        cfg = supervise.load_cfg()
        cfg["alerts"]["ntfy_base_url"] = "http://127.0.0.1:9"
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
