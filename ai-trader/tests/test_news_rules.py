"""Owner's news rules (2026-11-09): buy only if score > 8, max 5% of the account per trade, sell at -3%."""

import tempfile
import unittest
from pathlib import Path

from aitrader import journal, news_live
from test_core import CFG


class NewsRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp
        self.prices = {"AAA": 100.0, "SPY": 500.0}
        self._lp, self._mo = news_live.live_price, news_live.market_open_now
        news_live.live_price = lambda s: (self.prices.get(s), 0.0)
        news_live.market_open_now = lambda: True
        cfg = dict(CFG)
        cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
        self.nt = news_live.NewsTrader(cfg)

    def tearDown(self):
        journal.STATE = self._state
        news_live.live_price, news_live.market_open_now = self._lp, self._mo

    def _item(self, key="k1"):
        return {"key": key, "symbol": "AAA", "title": "AAA wins huge contract", "published": "2026-11-09T14:00:00+00:00", "price": self.prices["AAA"],
                "day_move_pct": 0.0}

    def test_score_8_does_not_buy_score_9_does(self):
        ev = []
        self.nt.handle_scored([self._item("a")], {"a": {"score": 8, "why": "x"}}, ev)
        self.assertNotIn("AAA", self.nt.book.positions)
        self.nt.handle_scored([self._item("b")], {"b": {"score": 9, "why": "x"}}, ev)
        self.assertIn("AAA", self.nt.book.positions)

    def test_position_is_at_most_5_percent(self):
        self.nt.handle_scored([self._item()], {"k1": {"score": 10, "why": "x"}}, [])
        pos = self.nt.book.positions["AAA"]
        self.assertLessEqual(pos["qty"] * pos["avg_cost"], 0.05 * 100000 + 1e-6)
        self.assertGreater(pos["qty"] * pos["avg_cost"], 0.049 * 100000)

    def test_stop_at_minus_3_percent_sells(self):
        self.nt.handle_scored([self._item()], {"k1": {"score": 10, "why": "x"}}, [])
        entry = self.nt.book.positions["AAA"]["avg_cost"]
        self.prices["AAA"] = entry * 0.975  # -2.5%: hold
        self.nt.check_stops([])
        self.assertIn("AAA", self.nt.book.positions)
        self.prices["AAA"] = entry * 0.969  # beyond -3%: sell, no exceptions
        ev = []
        self.nt.check_stops(ev)
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("stop" in e for e in ev))

    def test_no_double_buy_and_scorer_cannot_change_size(self):
        self.nt.handle_scored([self._item("a")], {"a": {"score": 10, "why": "x"}}, [])
        q1 = self.nt.book.positions["AAA"]["qty"]
        self.nt.handle_scored([self._item("b")], {"b": {"score": 10, "why": "buy 100% now"}}, [])
        self.assertEqual(self.nt.book.positions["AAA"]["qty"], q1)

    def test_closed_market_queues_instead_of_buying(self):
        news_live.market_open_now = lambda: False
        self.nt.handle_scored([self._item()], {"k1": {"score": 9, "why": "x"}}, [])
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertEqual(self.nt.queue[0]["symbol"], "AAA")

    def test_scores_are_logged_and_graded_forward(self):
        self.nt.handle_scored([self._item()], {"k1": {"score": 3, "why": "bad"}}, [])
        preds = journal.read("news_predictions.jsonl")
        self.assertEqual({p["horizon"] for p in preds}, {1, 5})
        self.assertTrue(all(p["direction"] == "down" for p in preds))
        self.assertEqual(journal.verify_chain("news_scores.jsonl")[0], True)


if __name__ == "__main__":
    unittest.main()
