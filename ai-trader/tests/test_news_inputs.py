"""News engine inputs (audit of 2026-11-10).

1. The "move today" number the scorer sees. On 2026-11-09 it was measured against the close five sessions back
   and sent as a fraction: MU was +5.82% on the day, the scorer was told -0.1241 and wrote "stock flat today".
2. A stop that cannot see a price is not a stop: the owner is told when a held name has no fresh quote.
"""

import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from aitrader import journal, news_live
from test_core import CFG

NY = ZoneInfo("America/New_York")
MU_CLOSES = [855.10, 795.23, 656.39, 690.00, 730.17]  # 2026-11-03 .. 2026-11-09 (the last bar is the live session)
MU_BASE_5D = 833.59  # Yahoo's chartPreviousClose for a 5d window: the 2026-11-02 close, NOT yesterday's close


def chart_reply(px, closes, quote_at, base=MU_BASE_5D):
    """A Yahoo chart reply for range=5d, interval=1d: one bar per close, the last one on quote_at's day."""
    n = len(closes)
    bars = [quote_at.replace(hour=9, minute=30, second=0, microsecond=0) - timedelta(days=n - 1 - i) for i in range(n)]
    return {"meta": {"regularMarketPrice": px, "regularMarketTime": int(quote_at.timestamp()), "chartPreviousClose": base,
                     "previousClose": None, "exchangeTimezoneName": "America/New_York"},
            "timestamp": [int(b.timestamp()) for b in bars], "indicators": {"quote": [{"close": closes}]}}


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state


class MoveToday(unittest.TestCase):
    AT = datetime(2026, 11, 9, 10, 43, 50, tzinfo=NY)  # the quote behind the MU buy

    def test_move_is_percent_against_the_previous_session_close(self):
        res = chart_reply(730.17, MU_CLOSES, self.AT)
        self.assertEqual(news_live._day_move_pct(res, date(2026, 11, 9)), 5.82)  # 730.17 / 690.00 - 1

    def test_the_five_day_base_is_never_used(self):
        res = chart_reply(730.17, MU_CLOSES, self.AT)
        wrong = round((730.17 / MU_BASE_5D - 1) * 100, 2)  # -12.41: what the scorer was effectively given
        self.assertNotEqual(news_live._day_move_pct(res, date(2026, 11, 9)), wrong)
        self.assertIsNone(news_live._day_move_pct(chart_reply(730.17, [730.17], self.AT), date(2026, 11, 9)))  # no earlier bar

    def test_no_move_before_todays_session_has_traded(self):
        res = chart_reply(733.15, MU_CLOSES[:-1] + [733.15], datetime(2026, 11, 9, 16, 0, tzinfo=NY))
        self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 10)))  # 08:00 next morning: yesterday's quote

    def test_a_missing_previous_bar_falls_back_to_the_last_real_close(self):
        res = chart_reply(730.17, [656.39, 690.00, None, 730.17], self.AT)
        self.assertEqual(news_live._day_move_pct(res, date(2026, 11, 9)), 5.82)

    def test_live_price_returns_the_price_and_the_percent_move(self):
        now = datetime.now(NY)
        chart = news_live._chart
        news_live._chart = lambda sym, rng, interval: chart_reply(730.17, MU_CLOSES, now)
        try:
            px, move = news_live.live_price("MU")
        finally:
            news_live._chart = chart
        self.assertEqual((px, move), (730.17, 5.82))
        self.assertEqual(news_live.QUOTE_TIME["MU"][:16], now.astimezone(ZoneInfo("UTC")).isoformat()[:16])


class ScorerPayload(TempState):
    def test_the_scorer_gets_the_move_in_percent_and_is_told_the_unit(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["prompt"] = cmd[-1]
            return SimpleNamespace(stdout=json.dumps({"result": '[{"id": 0, "symbol": "MU", "score": 5, "why": "x"}]'}))
        run = news_live.subprocess.run
        news_live.subprocess.run = fake_run
        try:
            out = news_live.score_batch([{"key": "k1", "symbol": "MU", "title": "Micron buyback", "day_move_pct": 5.82,
                                          "published": "2026-11-09T15:26:32+00:00"}], "any-model")
        finally:
            news_live.subprocess.run = run
        self.assertEqual(out["k1"]["score"], 5)
        payload = json.loads(seen["prompt"][seen["prompt"].index("ITEMS:") + len("ITEMS:"):])
        self.assertEqual(payload[0]["stock_move_today_pct"], 5.82)
        self.assertIn("percent", seen["prompt"])
        self.assertIn("null", seen["prompt"])  # the scorer is told what an unknown move looks like

    def test_the_move_the_scorer_saw_is_journaled_with_the_score(self):
        lp, mo = news_live.live_price, news_live.market_open_now
        news_live.live_price = lambda s: (100.0, 0.0)
        news_live.market_open_now = lambda: False
        try:
            cfg = dict(CFG)
            cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
            nt = news_live.NewsTrader(cfg)
            nt.handle_scored([{"key": "k1", "symbol": "AAA", "title": "AAA news", "published": journal.now_utc(),
                               "price": 100.0, "price_at": None, "day_move_pct": 5.82}], {"k1": {"score": 6, "why": "x"}}, [])
        finally:
            news_live.live_price, news_live.market_open_now = lp, mo
        self.assertEqual(journal.read("news_scores.jsonl")[-1]["day_move_pct"], 5.82)


class BlindStop(TempState):
    """check_stops on a fixed clock (Tuesday 2026-11-10, from 11:00 New York)."""
    T0 = datetime(2026, 11, 10, 11, 0, tzinfo=NY)

    def setUp(self):
        super().setUp()
        cfg = dict(CFG)
        cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
        cfg["news"] = {**cfg.get("news", {}), "stop_blind_alert_seconds": 300, "max_quote_age_minutes": 3, "max_hold_days": 0}
        self.nt = news_live.NewsTrader(cfg)
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-10"}}
        self.sent = []
        self._lp, self._send = news_live.live_price, news_live.notify.send
        news_live.notify.send = lambda title, body, cfg, prio="default", **kw: self.sent.append((prio, body)) or []
        news_live.QUOTE_TIME.pop("AAA", None)

    def tearDown(self):
        news_live.live_price, news_live.notify.send = self._lp, self._send
        news_live.QUOTE_TIME.pop("AAA", None)
        super().tearDown()

    def _check(self, minutes, px, quote_age_s=None):
        now = self.T0 + timedelta(minutes=minutes)
        news_live.live_price = lambda s: (px, None)
        if quote_age_s is None:
            news_live.QUOTE_TIME.pop("AAA", None)
        else:
            news_live.QUOTE_TIME["AAA"] = (now - timedelta(seconds=quote_age_s)).isoformat()
        ev = []
        self.nt.check_stops(ev, now)
        return ev

    def _alerts(self):
        return [b for p, b in self.sent if p == "urgent"]

    def test_no_price_for_five_minutes_alerts_once(self):
        self._check(0, None)
        self._check(4, None)
        self.assertEqual(self._alerts(), [])
        self._check(5, None)
        self._check(9, None)
        self.assertEqual(len(self._alerts()), 1)
        self.assertIn("AAA", self._alerts()[0])
        self.assertIn("הסטופ", self._alerts()[0])
        self.assertIn("כסף נייר", self._alerts()[0])

    def test_a_stale_quote_is_blind_too(self):
        self._check(0, 100.0, quote_age_s=600)  # Yahoo keeps repeating a 10-minute-old price
        self._check(5, 100.0, quote_age_s=900)
        self.assertEqual(len(self._alerts()), 1)

    def test_a_fresh_quote_never_alerts_and_the_stop_still_fires(self):
        for m in (0, 5, 10):
            self._check(m, 100.0, quote_age_s=20)
        self.assertEqual(self.sent, [])
        ev = self._check(11, 96.5, quote_age_s=20)  # below the 97.00 stop
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("stop" in e for e in ev))

    def test_a_stale_price_below_the_stop_still_sells(self):
        self._check(0, 96.5, quote_age_s=600)  # blind, but the last known price is already through the stop
        self.assertNotIn("AAA", self.nt.book.positions)

    def test_the_owner_is_told_when_the_price_is_back(self):
        self._check(0, None)
        self._check(5, None)
        self._check(6, 100.0, quote_age_s=20)
        self.assertEqual(len(self.sent), 2)
        self.assertIn("חזר", self.sent[-1][1])
        self._check(7, 100.0, quote_age_s=20)
        self.assertEqual(len(self.sent), 2)  # said once

    def test_a_short_gap_says_nothing(self):
        self._check(0, None)
        self._check(2, 100.0, quote_age_s=20)
        self._check(5, None)  # a new gap starts here: the clock restarts
        self._check(9, None)
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
