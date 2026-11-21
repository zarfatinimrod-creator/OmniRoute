"""Regression tests for the 2026-11-09 adversarial code review findings."""

import copy
import unittest

import numpy as np

from aitrader.broker import PaperBroker
from aitrader.signals import compute_all
from aitrader.strategy import build_targets, precompute_aux
from test_core import cfg_for, synthetic_panel


class CorporateActions(unittest.TestCase):
    def test_split_keeps_value_and_no_phantom_loss(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.4}, {"AAA": 100.0}, "2026-01-02", band=0.0, min_trade_value=0)
        eq_before = b.equity({"AAA": 100.0})
        notes = b.apply_corporate_actions({"AAA": {"splits": [{"date": "2026-01-05", "ratio": 4.0}], "dividends": []}}, "2026-01-06")
        self.assertTrue(notes)
        self.assertEqual(b.positions["AAA"]["qty"], 160)
        self.assertAlmostEqual(b.positions["AAA"]["avg_cost"], 25.0)
        self.assertAlmostEqual(b.equity({"AAA": 25.0}), eq_before)
        # idempotent: applying the same actions again changes nothing
        b.apply_corporate_actions({"AAA": {"splits": [{"date": "2026-01-05", "ratio": 4.0}], "dividends": []}}, "2026-01-06")
        self.assertEqual(b.positions["AAA"]["qty"], 160)

    def test_dividend_credited_net_once(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-01-02", band=0.0, min_trade_value=0)
        cash0 = b.cash
        acts = {"AAA": {"splits": [], "dividends": [{"date": "2026-01-03", "amount": 1.0}]}}
        b.apply_corporate_actions(acts, "2026-01-04")
        self.assertAlmostEqual(b.cash - cash0, 50 * 1.0 * 0.75)
        b.apply_corporate_actions(acts, "2026-01-05")
        self.assertAlmostEqual(b.cash - cash0, 50 * 1.0 * 0.75)

    def test_dividend_before_entry_ignored(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-01-10", band=0.0, min_trade_value=0)
        cash0 = b.cash
        b.apply_corporate_actions({"AAA": {"splits": [], "dividends": [{"date": "2026-01-03", "amount": 1.0}]}}, "2026-01-11")
        self.assertEqual(b.cash, cash0)


class ExitsOnly(unittest.TestCase):
    def test_exits_only_never_adds_or_trims(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"A": 0.3, "B": 0.3}, {"A": 10.0, "B": 10.0}, "2026-01-02", band=0.0, min_trade_value=0)
        fills = b.rebalance({"A": 0.9}, {"A": 5.0, "B": 10.0}, "2026-01-03", band=0.0, min_trade_value=0, exits_only=True)
        self.assertEqual([(f["symbol"], f["side"]) for f in fills], [("B", "SELL")])


class RiskCaps(unittest.TestCase):
    def setUp(self):
        self.p = synthetic_panel()
        self.cfg = cfg_for(self.p)
        self.cfg["risk"]["min_score"] = -1.0

    def test_scale_up_never_breaches_caps(self):
        c = copy.deepcopy(self.cfg)
        c["risk"]["target_vol_annual"] = 5.0  # forces scale > 1
        c["risk"]["max_gross"] = 3.0
        sig = compute_all(self.p, c)
        aux = precompute_aux(self.p, c)
        for d in self.p["close"].index[300::60]:
            t, _ = build_targets(d, self.p, sig, c["prior_weights"], c, 1.0, {}, set(), aux)
            for s, w in t.items():
                cap = c["risk"]["max_etf_position_pct"] if s == "SPY" else c["risk"]["max_position_pct"]
                self.assertLessEqual(w, cap + 1e-9, s)

    def test_regime_fails_closed_without_benchmark(self):
        p = {k: v.drop(columns=["SPY"]) for k, v in self.p.items()}
        c = copy.deepcopy(self.cfg)
        sig = compute_all(p, c)
        d = p["close"].index[450]
        t, diag = build_targets(d, p, sig, c["prior_weights"], c, 1.0, {}, set(), precompute_aux(p, c))
        self.assertTrue(diag["regime"].startswith("risk_off"))

    def test_missing_vix_today_is_defensive(self):
        p = dict(self.p)
        vix = self.p["close"]["S00"].copy() * 0 + 20.0
        vix.iloc[-1] = np.nan
        p["vix"] = vix
        sig = compute_all(p, self.cfg)
        _, diag = build_targets(p["close"].index[-1], p, sig, self.cfg["prior_weights"], self.cfg, 1.0, {}, set(), precompute_aux(p, self.cfg))
        self.assertIn("defensive", diag["regime"])


if __name__ == "__main__":
    unittest.main()
