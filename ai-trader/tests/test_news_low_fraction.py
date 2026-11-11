"""A fraction at the low end sells (the owner's decision of 2026-11-11, state/backlog.md item 62).

The scorer is asked for a whole number from 1 to 10. A fraction counts only for the bad-news exit of a held name,
compared as it is with news.sell_on_score_at_most (1.6 sells, 2.4 does not); it never buys, never queues and never
passes a second check. The scorer's reply goes through the real score_batch: only subprocess.run inside news_live is
replaced, so nothing here can reach the model.
"""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import io
import unittest
from unittest import mock

from aitrader import journal, news_live
from test_news_guards import _Engine
from test_news_measure import cli_reply, payload_of
from test_news_supervised import hold

LIVE_BBB = 49.5  # BBB's live price: above the 48.5 stop of a hold at 50.0, so only a score can sell it


class LowFraction(_Engine):
    def setUp(self):
        super().setUp()
        for target, name, stub in ((news_live.subprocess, "run", self._claude),
                                   (news_live.NewsTrader, "_quote_is_live", lambda nt, *a, **k: True)):
            p = mock.patch.object(target, name, stub)
            p.start()
            self.addCleanup(p.stop)
        self.prices["BBB"] = LIVE_BBB

    def _claude(self, cmd, **kw):
        """subprocess.run inside news_live: a scorer call is answered with the scores of self.rows, one per headline in
        the order the poll found them, in the CLI's JSON envelope. json.dumps writes nan and inf as NaN and Infinity,
        which strict JSON has not and json.loads reads. Any other command is refused."""
        if cmd[:2] != ["claude", "-p"] or "ITEMS:" not in cmd[-1]:
            raise AssertionError(f"not a scorer call: {cmd[:2]}")
        return cli_reply([{"id": p["id"], "symbol": p["symbol"], "score": r["score"], "why": "x"}
                          for p, r in zip(payload_of(cmd), self.rows)])

    def step_with(self, rows):
        """One real step: the poll finds one fresh headline per row, and the scorer answers each with its row's score."""
        self.rows = rows
        new = [{"key": f"k{i}", "symbol": r["symbol"], "title": f"{r['symbol']} news {i}", "link": "",
                "published": journal.now_utc()} for i, r in enumerate(rows)]
        with mock.patch.object(self.nt, "poll_headlines", lambda: list(new)), contextlib.redirect_stdout(io.StringIO()):
            return self.nt.step()

    def fresh_engine(self, session_open=True):
        """A new temporary state and a new trader, made by _Engine's own setUp; the stand-ins of this class stay."""
        super().tearDown()
        super().setUp()
        self.prices["BBB"] = LIVE_BBB
        news_live.market_open_now = lambda: session_open

    def fresh_engine_holding_bbb(self):
        self.fresh_engine()
        hold(self.nt)

    def test_a_fraction_at_or_under_the_line_on_a_held_name_sells_and_the_record_keeps_what_was_said(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 1.6}])
        t = journal.read("news_trades.jsonl")[-1]
        self.assertEqual((t["side"], t["symbol"], t["qty"]), ("SELL", "BBB", 10))
        row = journal.read("news_scores.jsonl")[-1]
        self.assertEqual((row["symbol"], row["score"], row["raw_score"]), ("BBB", 1, 1.6))
        self.assertNotIn("BBB", self.nt.book.positions)

    def test_the_line_is_compared_on_the_fraction_itself(self):  # sell_on_score_at_most is 2
        for raw, sells in ((2.4, False), (2.0001, False), (1.9999, True), (0.4, True)):
            with self.subTest(raw=raw):
                self.fresh_engine_holding_bbb()
                self.step_with([{"symbol": "BBB", "score": raw}])
                self.assertEqual("BBB" not in self.nt.book.positions, sells)
        self.assertEqual(journal.read("news_scores.jsonl")[-1]["score"], 1)  # 0.4 is stored as 1, never 0

    def test_a_fraction_never_buys_never_queues_and_leaves_no_score(self):
        for session_open in (True, False):  # a buy in session, a queue place outside it
            with self.subTest(session_open=session_open):
                self.fresh_engine(session_open=session_open)
                self.step_with([{"symbol": "AAA", "score": 9.5}, {"symbol": "AAA", "score": 8.6}])
                self.assertEqual(journal.read("news_trades.jsonl"), [])
                self.assertEqual(journal.load_json("news_queue.json") or [], [])
                self.assertEqual(journal.read("news_scores.jsonl"), [])

    def test_a_high_fraction_on_a_held_name_changes_nothing(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 9.5}])
        self.assertEqual((journal.read("news_trades.jsonl"), "BBB" in self.nt.book.positions), ([], True))

    def test_a_low_fraction_on_a_name_that_is_not_held_is_dropped_as_today(self):
        self.step_with([{"symbol": "AAA", "score": 1.6}])
        self.assertEqual((journal.read("news_trades.jsonl"), journal.read("news_scores.jsonl")), ([], []))

    def test_the_sale_still_needs_a_live_quote(self):  # the rule of the whole low score
        hold(self.nt)
        with mock.patch.object(news_live.NewsTrader, "_quote_is_live", lambda self, *a, **k: False):
            self.step_with([{"symbol": "BBB", "score": 1.6}])
        self.assertIn("BBB", self.nt.book.positions)

    def test_a_whole_low_score_and_everything_that_is_no_number_are_as_before(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 2}])
        row = journal.read("news_scores.jsonl")[-1]
        self.assertEqual((row["score"], "raw_score" in row, "BBB" in self.nt.book.positions), (2, False, False))
        # float("-inf") is one more than the brief lists: under the sell line, it would reach math.floor and raise
        for bad in (None, "1", "1.6", True, [1.6], {"v": 1}, float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad):
                self.fresh_engine_holding_bbb()
                self.step_with([{"symbol": "BBB", "score": bad}])
                self.assertIn("BBB", self.nt.book.positions)

    def test_the_scorer_call_row_counts_the_fractions(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 9.5}, {"symbol": "AAA", "score": 7}])
        self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 1)
        self.fresh_engine()
        self.step_with([{"symbol": "AAA", "score": 7}])
        self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 0)


if __name__ == "__main__":
    unittest.main()
