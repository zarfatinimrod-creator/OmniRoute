"""The news engine as a supervised process (supervisor spec, section 5): what the engine itself does about its lock."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import io
import json
import os
from unittest import mock

from aitrader import journal, news_live
from test_news_guards import _Engine


def hold(nt, sym="BBB", entry=50.0):
    """A held name on the trader's book: 10 shares, the stop at 97% of the entry."""
    nt.book.state["positions"][sym] = {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": "2026-11-09",
                                       "stop_price": round(entry * 0.97, 4)}


class Lock(_Engine):
    def test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat(self):
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("23:59", max_minutes=0.0005, prime=False), 0)
        self.assertEqual([p for p, b in self.sent if b.startswith("מנוע החדשות רץ בלי נעילה")], ["urgent"])
        self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)
        self.assertEqual(journal._path("news_engine.lock").read_text(), "")   # it holds no lock, so it signs no lock file


class TheLoopsAnswer(_Engine):
    def test_run_hands_back_what_the_loop_returned_and_the_lock_file_names_this_process(self):
        got = []
        with mock.patch.object(news_live, "_run", lambda *a, **k: got.append(k) or 7):
            self.assertEqual(news_live.run(max_minutes=0.001), 7)   # not always 0: the loop gets exit codes of its own
        self.assertEqual(got, [{"locked": True}])
        holder = json.loads(journal._path("news_engine.lock").read_text())
        self.assertEqual((holder["pid"], holder["started_at"][-6:]), (os.getpid(), "+00:00"))


class Unlocked(_Engine):
    def test_a_line_that_cannot_be_built_does_not_cost_the_book_its_only_engine(self):
        news_live.ERRORS_SAID.clear()   # what this process already put in news_errors.jsonl
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live, "owner_line", side_effect=KeyError("supervisor")), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("23:59", max_minutes=0.0005, prime=False), 0)
        self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)   # it ran, and its heartbeat still says how
        self.assertEqual([(e["where"], e["error"]) for e in journal.read("news_errors.jsonl")], [("lock_line", "KeyError")])
