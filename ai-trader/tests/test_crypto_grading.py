import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from aitrader import journal

CRYPTO = {"grading": "absolute", "calendar": "utc_daily"}
STOCK = {"grading": "excess", "calendar": "nyse"}


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)


def _panel(days=20):
    idx = pd.date_range("2026-11-02", periods=days, freq="D")  # 7 days a week, like crypto bars
    return idx, pd.DataFrame({"BTC-USD": 100.0, "SPY": 100.0}, index=idx)


def _call(date, logged_at, price, horizon=5, source="claude"):
    return {"date": date, "logged_at": logged_at, "symbol": "BTC-USD", "horizon": horizon, "source": source,
            "direction": "up", "price": price, "bench_price": 100.0, "status": "open"}


class AbsoluteGrading(TempState):
    def test_absolute_grading(self):
        idx, close = _panel()
        close.loc[idx[10]:, "BTC-USD"] = 110.0
        close.loc[idx[10]:, "SPY"] = 105.0  # the benchmark must be ignored
        journal.append("predictions.jsonl", _call(str(idx[5].date()), f"{idx[5].date()}T12:00:00+00:00", 100.0))
        journal.evaluate_predictions(close, "SPY", market=CRYPTO)
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["ret"], 0.10)
        self.assertAlmostEqual(g[0]["bench_ret"], 0.0)
        self.assertAlmostEqual(g[0]["excess"], 0.10)
        self.assertTrue(g[0]["hit"])

    def test_absolute_grading_needs_no_benchmark_column(self):
        idx, close = _panel()
        close.loc[idx[10]:, "BTC-USD"] = 90.0
        journal.append("predictions.jsonl", _call(str(idx[5].date()), f"{idx[5].date()}T12:00:00+00:00", 100.0))
        journal.evaluate_predictions(close.drop(columns="SPY"), "SPY", market=CRYPTO)
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["excess"], -0.10)
        self.assertFalse(g[0]["hit"])


class UtcSession(TempState):
    def test_utc_session_saturday_call_uses_logged_price(self):
        idx, close = _panel()
        sat = pd.Timestamp("2026-11-07")  # a Saturday
        self.assertEqual(sat.dayofweek, 5)
        pos = idx.get_loc(sat)
        close.loc[sat:, "BTC-USD"] = 120.0  # the day's close differs from the logged price
        close.loc[idx[pos + 5]:, "BTC-USD"] = 130.0
        journal.append("predictions.jsonl", _call("2026-11-06", "2026-11-07T14:00:00+00:00", 100.0))
        journal.evaluate_predictions(close, "SPY", market=CRYPTO)
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["ret"], 0.30)  # 130 / logged 100, not 130 / 120
        self.assertEqual(g[0]["eval_date"], str(idx[pos + 5].date()))  # horizon counted from the log day

    def test_utc_no_price_takes_that_days_close(self):
        idx, close = _panel()
        sat = pd.Timestamp("2026-11-07")
        pos = idx.get_loc(sat)
        close.loc[sat:, "BTC-USD"] = 120.0
        close.loc[idx[pos + 5]:, "BTC-USD"] = 150.0
        journal.append("predictions.jsonl", _call("2026-11-06", "2026-11-07T14:00:00+00:00", None))
        journal.evaluate_predictions(close, "SPY", market=CRYPTO)
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["ret"], 0.25)  # 150 / Saturday close 120

    def test_utc_day_close_not_yet_final_waits(self):
        idx, close = _panel(days=6)  # last bar is 2026-11-07
        journal.append("predictions.jsonl", _call("2026-11-08", "2026-11-08T14:00:00+00:00", None, horizon=1))
        journal.evaluate_predictions(close, "SPY", market=CRYPTO)  # Sunday's bar does not exist yet
        self.assertEqual(journal.graded(), {})

    def test_entry_bar_midnight_boundaries(self):
        idx, _ = _panel()
        p = _call("2026-11-07", "2026-11-07T00:00:00+00:00", 100.0)
        self.assertEqual(journal._entry_bar(p, idx, CRYPTO), (None, idx.get_loc(pd.Timestamp("2026-11-07"))))
        p = _call("2026-11-07", "2026-11-07T23:59:59+00:00", 100.0)
        self.assertEqual(journal._entry_bar(p, idx, CRYPTO), (None, idx.get_loc(pd.Timestamp("2026-11-07"))))


class StockUnchanged(TempState):
    def test_stock_grading_unchanged(self):
        idx = pd.bdate_range("2026-11-02", periods=40)
        close = pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)
        d_prev, d_log = idx[4], idx[5]
        close.loc[d_log:, "AAA"] = 110.0
        close.loc[idx[10]:, "SPY"] = 103.0
        rec = {"date": str(d_prev.date()), "logged_at": f"{d_log.date()}T11:37:39+00:00", "symbol": "AAA",
               "horizon": 5, "source": "insider_cluster", "direction": "up", "price": 100.0, "bench_price": 100.0,
               "status": "open"}
        outs = []
        for kw in ({}, {"market": None}, {"market": STOCK}):
            journal.STATE = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, journal.STATE, True)
            journal.append("predictions.jsonl", rec)
            journal.evaluate_predictions(close, "SPY", **kw)
            g = list(journal.graded().values())
            outs.append({k: g[0][k] for k in ("ret", "bench_ret", "excess", "eval_date", "hit")})
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[0], outs[2])
        self.assertAlmostEqual(outs[0]["bench_ret"], 0.03)


if __name__ == "__main__":
    unittest.main()
