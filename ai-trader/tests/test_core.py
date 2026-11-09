"""Core invariants. Run: cd ai-trader && python3 -m unittest discover -s tests -v"""

import copy
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from aitrader import backtest, learn
from aitrader.broker import PaperBroker
from aitrader.signals import compute_all
from aitrader.strategy import _cap_weights, build_targets, precompute_aux

CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())


def synthetic_panel(n_days=700, n_syms=30, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    syms = ["SPY"] + [f"S{i:02d}" for i in range(n_syms - 1)]
    drift = rng.normal(0.0003, 0.0004, n_syms)
    rets = rng.normal(drift, 0.015, (n_days, n_syms))
    close = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=syms)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.002, close.shape))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, close.shape)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, close.shape)))
    vol = pd.DataFrame(1e6, index=idx, columns=syms)
    return {"open": open_, "high": high, "low": low, "close": close, "volume": vol}


def cfg_for(panel):
    c = copy.deepcopy(CFG)
    c["universe"] = {s: ("Index" if s == "SPY" else f"Sec{int(s[1:]) % 6}" if s != "SPY" else "Index") for s in panel["close"].columns}
    return c


class NoLookahead(unittest.TestCase):
    def test_signals_ignore_the_future(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        cut = p["close"].index[500]
        full = compute_all(p, cfg)
        trunc = compute_all({k: v.loc[:cut] for k, v in p.items()}, cfg)
        for name in full:
            a, b = full[name].loc[cut], trunc[name].loc[cut]
            pd.testing.assert_series_equal(a, b, check_names=False, obj=name)

    def test_learning_uses_only_matured_outcomes(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        sig = compute_all(p, cfg)
        h = 20
        ic = learn.ic_table(sig, p["close"], h)
        pos = 600
        st1 = learn.signal_stats(ic, pos, h, 60)
        ic2 = ic.copy()
        ic2.iloc[pos - h + 1:] = 0.99  # rows not yet matured at pos must not matter
        st2 = learn.signal_stats(ic2, pos, h, 60)
        pd.testing.assert_frame_equal(st1, st2)

    def test_targets_ignore_the_future(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        d = p["close"].index[550]
        sig = compute_all(p, cfg)
        t1, _ = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), precompute_aux(p, cfg))
        pt = {k: v.loc[:d] for k, v in p.items()}
        sig2 = compute_all(pt, cfg)
        t2, _ = build_targets(d, pt, sig2, cfg["prior_weights"], cfg, 1.0, {}, set(), precompute_aux(pt, cfg))
        self.assertEqual(t1.keys(), t2.keys())
        for k in t1:
            self.assertAlmostEqual(t1[k], t2[k], places=10)


class Broker(unittest.TestCase):
    def test_round_trip_accounting(self):
        b = PaperBroker(10000, slippage_bps=10)
        fills = b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-01-02", band=0.0, min_trade_value=0)
        self.assertEqual(fills[0]["side"], "BUY")
        self.assertEqual(b.positions["AAA"]["qty"], 49)  # floor(5000 / 100.1)
        self.assertAlmostEqual(b.cash, 10000 - 49 * 100.1, places=6)
        b.rebalance({}, {"AAA": 110.0}, "2026-01-03", band=0.0, min_trade_value=0)
        self.assertNotIn("AAA", b.positions)
        self.assertAlmostEqual(b.cash, 10000 - 49 * 100.1 + 49 * 110 * 0.999, places=6)

    def test_never_spends_more_cash_than_it_has(self):
        b = PaperBroker(1000, slippage_bps=5)
        b.rebalance({"A": 0.9, "B": 0.9}, {"A": 10.0, "B": 10.0}, "2026-01-02", band=0.0, min_trade_value=0)
        self.assertGreaterEqual(b.cash, 0)

    def test_cash_yield_and_peak(self):
        b = PaperBroker(1000)
        b.mark({}, "2026-01-02", cash_yield_annual=0.05)
        self.assertGreater(b.cash, 1000)
        self.assertAlmostEqual(b.state["peak_equity"], b.cash)


class Portfolio(unittest.TestCase):
    def test_caps_respected(self):
        w = pd.Series({"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.1})
        caps = pd.Series(0.25, index=w.index)
        secs = pd.Series({"a": "x", "b": "x", "c": "y", "d": "z"})
        out = _cap_weights(w, caps, secs, 0.30)
        self.assertTrue((out <= caps + 1e-9).all())
        self.assertLessEqual(out[secs == "x"].sum(), 0.30 + 1e-9)

    def test_gross_never_exceeds_max(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        sig = compute_all(p, cfg)
        aux = precompute_aux(p, cfg)
        for d in p["close"].index[300::50]:
            t, _ = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
            self.assertLessEqual(sum(t.values()), cfg["risk"]["max_gross"] + 1e-9)

    def test_drawdown_breaker_goes_flat(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        sig = compute_all(p, cfg)
        t, diag = build_targets(p["close"].index[500], p, sig, cfg["prior_weights"], cfg, 0.75, {}, set())
        self.assertEqual(t, {})
        self.assertEqual(diag["dd_state"], "flat")


class TimeMachine(unittest.TestCase):
    def test_backtest_runs_and_executes_next_day(self):
        p = synthetic_panel()
        cfg = cfg_for(p)
        res = backtest.run(p, cfg, str(p["close"].index[320].date()), weights_mode="prior")
        self.assertIn("sharpe", res["strategy"])
        first_fill = res["_fills"][0]["date"]
        self.assertGreater(pd.Timestamp(first_fill), p["close"].index[320])


if __name__ == "__main__":
    unittest.main()
