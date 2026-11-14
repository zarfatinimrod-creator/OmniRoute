"""Config-driven constants (plan 2026-11-09-crypto-book-v1, Task 2): the stock values reproduce today's behaviour,
the crypto values come from config."""

import copy
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aitrader import cycle, journal, metrics, strategy
from aitrader.signals import compute_all
from aitrader.strategy import build_targets, precompute_aux
from test_core import cfg_for, synthetic_panel


def _setup():
    p = synthetic_panel()
    cfg = cfg_for(p)
    return p, cfg, compute_all(p, cfg), precompute_aux(p, cfg), p["close"].index[500]


def _open_book(cfg):
    r = cfg["risk"]
    r.update({"min_score": -1.0, "max_positions": 3, "max_position_pct": 1.0, "max_sector_pct": 1.0,
              "risk_off_gross_mult": 1.0, "defensive_vix_pct": 0, "target_vol_annual": 10.0})
    return cfg


class AtrStop(unittest.TestCase):
    def test_atr_mult_zero_means_no_stop(self):
        p, cfg, sig, aux, d = _setup()
        sym = "S01"
        held = {sym: {"peak_close": float(p["close"].loc[d, sym]) * 2}}  # close far below its peak
        _, diag = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, held, set(), aux)
        self.assertEqual(diag["stopped"], [sym])  # the default 3.0 mult stops it
        cfg["risk"]["atr_stop_mult"] = 0
        _, diag = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, held, set(), aux)
        self.assertEqual(diag["stopped"], [])


class SymbolCap(unittest.TestCase):
    def test_symbol_cap_override(self):
        p, cfg, sig, aux, d = _setup()
        _open_book(cfg)
        base, _ = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
        top = max(base, key=base.get)
        self.assertGreater(base[top], 0.2)
        cfg["risk"]["max_position_pct_by_symbol"] = {top: 0.2}
        capped, _ = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
        self.assertLessEqual(capped[top], 0.2 + 1e-9)
        self.assertAlmostEqual(capped[top], 0.2, places=6)


class PeriodsPerYear(unittest.TestCase):
    def test_periods_per_year_scales_vol_target(self):
        p, cfg, sig, aux, d = _setup()
        _, stock = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
        self.assertEqual(cfg["market"]["periods_per_year"], 252)
        no_market = copy.deepcopy(cfg)
        del no_market["market"]
        _, legacy = build_targets(d, p, sig, cfg["prior_weights"], no_market, 1.0, {}, set(), aux)
        self.assertEqual(stock["ex_ante_vol_unscaled"], legacy["ex_ante_vol_unscaled"])  # stock value unchanged
        cfg["market"]["periods_per_year"] = 365
        _, crypto = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
        self.assertAlmostEqual(crypto["ex_ante_vol_unscaled"] / stock["ex_ante_vol_unscaled"], math.sqrt(365 / 252), places=2)

    def test_metrics_summary_periods(self):
        import numpy as np
        import pandas as pd
        eq = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0.001, 0.02, 400))),
                       index=pd.bdate_range("2020-01-01", periods=400))
        a, b = metrics.summary(eq), metrics.summary(eq, periods_per_year=365)
        self.assertEqual(metrics.summary(eq, periods_per_year=252), a)
        self.assertAlmostEqual(b["vol"] / a["vol"], math.sqrt(365 / 252), places=3)


class EtfGroups(unittest.TestCase):
    def test_etf_groups(self):
        self.assertEqual(strategy.etf_groups({}), strategy.ETF_SECTORS)
        self.assertEqual(strategy.etf_groups({"market": {"etf_groups": []}}), set())
        self.assertEqual(strategy.ETF_SECTORS, {"Index", "SectorETF", "Bonds", "Gold"})


class LearningFlag(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_learning_disabled_keeps_priors(self):
        p, cfg, sig, _, d = _setup()
        cfg["learning"]["enabled"] = False
        with mock.patch.object(cycle, "walk_forward_weights", side_effect=AssertionError("learner ran")):
            w = cycle._learn(sig, p["close"], cfg, "2022-01-03")
        self.assertEqual(w, cfg["prior_weights"])
        self.assertIsNone(journal.load_json("weights.json"))


if __name__ == "__main__":
    unittest.main()
