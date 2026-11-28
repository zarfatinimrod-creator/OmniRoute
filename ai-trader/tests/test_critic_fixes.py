"""Regression tests for the quant-critic HOLD findings (2026-11-09)."""

import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from aitrader import cycle, journal
from aitrader.broker import PaperBroker
from aitrader.signals import compute_all
from aitrader.strategy import build_targets, precompute_aux
from test_core import cfg_for, synthetic_panel


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)


class OverrideCutoff(TempState):
    def test_override_logged_after_the_open_is_ignored(self):
        cutoff = cycle._open_cutoff_utc("2026-11-10")  # 09:30 NY = 14:30 UTC in November
        self.assertTrue(cutoff.startswith("2026-11-10T14:30"))
        journal.save_json("overrides.json", {"date": "2026-11-09", "vetoes": {
            "AAA": {"reason": "before open", "logged_at": "2026-11-10T14:00:00+00:00"},
            "BBB": {"reason": "after open", "logged_at": "2026-11-10T16:00:00+00:00"}}, "size_mult": {
            "CCC": [0.5, "after open", "2026-11-10T15:00:00+00:00"]}})
        t, applied = cycle._apply_overrides({"AAA": 0.1, "BBB": 0.1, "CCC": 0.1}, {}, "2026-11-09", cutoff)
        self.assertNotIn("AAA", t)
        self.assertEqual(t["BBB"], 0.1)
        self.assertEqual(t["CCC"], 0.1)
        self.assertEqual([a["symbol"] for a in applied], ["AAA"])

    def test_shrink_applied_once_from_raw_targets(self):
        journal.save_json("overrides.json", {"date": "d", "vetoes": {}, "size_mult": {"AAA": [0.5, "r", None]}})
        t1, _ = cycle._apply_overrides({"AAA": 0.08}, {}, "d")
        t2, _ = cycle._apply_overrides({"AAA": 0.08}, {}, "d")  # recomputed from raw, not compounded
        self.assertAlmostEqual(t1["AAA"], 0.04)
        self.assertAlmostEqual(t2["AAA"], 0.04)


class ForwardOnlyGrading(TempState):
    def test_claude_call_graded_from_logged_price(self):
        idx = pd.bdate_range("2026-01-01", periods=30)
        close = pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)
        close.loc[idx[1]:, "AAA"] = 110.0  # +10% jump right after the decision bar
        d0 = str(idx[0].date())
        journal.append("predictions.jsonl", {"date": d0, "logged_at": "x1", "symbol": "AAA", "horizon": 5, "source": "claude",
                                             "direction": "up", "price": 110.0, "bench_price": 100.0, "status": "open"})
        journal.append("predictions.jsonl", {"date": d0, "logged_at": "x2", "symbol": "AAA", "horizon": 5, "source": "quant",
                                             "direction": "up", "price": 100.0, "bench_price": 100.0, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = {k.split("|")[3]: v for k, v in journal.graded().items()}
        self.assertAlmostEqual(g["claude"]["excess"], 0.0)  # no credit for a move already seen
        self.assertAlmostEqual(g["quant"]["excess"], 0.10)


class OutOfHoursCall(TempState):
    def test_call_logged_when_closed_is_graded_from_next_session(self):
        idx = pd.bdate_range("2026-01-01", periods=30)
        close = pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)
        close.loc[idx[1]:, "AAA"] = 110.0  # overnight jump into session 1
        journal.append("predictions.jsonl", {"date": str(idx[0].date()), "logged_at": f"{idx[0].date()}T23:00:00+00:00",
                                             "symbol": "AAA", "horizon": 5, "source": "claude", "direction": "up",
                                             "price": None, "bench_price": None, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["excess"], 0.0)  # entry = next session close (110): the jump earns nothing


class DrawdownReentry(unittest.TestCase):
    def test_reentry_at_half_scale_after_risk_on_streak(self):
        b = PaperBroker(10000)
        b.state.update({"dd_state": "flat", "peak_equity": 20000})
        for i in range(19):
            self.assertFalse(b.maybe_reset_peak("risk_on", f"d{i}", 20, -0.10, -0.20))
        self.assertTrue(b.maybe_reset_peak("risk_on", "d19", 20, -0.10, -0.20))
        b.mark({}, "d20", cash_yield_annual=0.05)  # a day of interest must not flip it back to "normal"
        ratio = b.peak_ratio({})
        self.assertTrue(-0.20 < ratio - 1 <= -0.10)  # reads "halved", not "normal"


class LiveCooldown(unittest.TestCase):
    def test_stop_cooldown_survives_the_fill_day(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-11-02", band=0.0, min_trade_value=0)
        cool = str((pd.Timestamp("2026-11-09") + pd.offsets.BDay(10)).date())
        b.rebalance({}, {"AAA": 90.0}, "2026-11-09", band=0.0, min_trade_value=0, stopped=["AAA"], cooldown_until=cool)
        b.mark({"AAA": 90.0}, "2026-11-09")
        self.assertIn("AAA", b.state["blocked"])


class VixFailClosed(unittest.TestCase):
    def test_required_vix_missing_is_defensive(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        p["_require_vix"] = True  # production marker set by load_market; no 'vix' key = fetch failed
        sig = compute_all(p, cfg)
        _, diag = build_targets(p["close"].index[-1], p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), precompute_aux(p, cfg))
        self.assertIn("defensive(no-vix)", diag["regime"])


class SplitOnFillDay(TempState):
    def test_split_applied_before_open_fill(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-11-06", band=0.0, min_trade_value=0)
        acts = {"AAA": {"splits": [{"date": "2026-11-09", "ratio": 4.0}], "dividends": []}}
        b.apply_corporate_actions(acts, "2026-11-09")  # run_cycle does this before _execute_pending
        eq = b.equity({"AAA": 25.0})
        fills = b.rebalance({"AAA": 0.5}, {"AAA": 25.0}, "2026-11-09", band=0.02, min_trade_value=500)
        self.assertEqual(fills, [])  # no phantom 75% loss -> no top-up buy
        self.assertAlmostEqual(eq, 10000.0)


if __name__ == "__main__":
    unittest.main()


class ReduceOnlyInvariant(unittest.TestCase):
    def test_invariant_rejects_enlarging_or_adding(self):
        cycle._check_reduce_only({"A": 0.1}, {"A": 0.05})
        with self.assertRaises(RuntimeError):
            cycle._check_reduce_only({"A": 0.1}, {"A": 0.2})
        with self.assertRaises(RuntimeError):
            cycle._check_reduce_only({"A": 0.1}, {"A": 0.1, "B": 0.01})

    def test_forced_shrink_trades_inside_the_band(self):
        b = PaperBroker(100000, slippage_bps=0)
        b.rebalance({"AAA": 0.08}, {"AAA": 100.0}, "2026-01-02", band=0.0, min_trade_value=0)
        none = b.rebalance({"AAA": 0.065}, {"AAA": 100.0}, "2026-01-03", band=0.02, min_trade_value=500)
        self.assertEqual(none, [])  # ordinary drift inside the band: no trade
        fills = b.rebalance({"AAA": 0.065}, {"AAA": 100.0}, "2026-01-03", band=0.02, min_trade_value=500, force={"AAA"})
        self.assertEqual(fills[0]["side"], "SELL")
