"""Regime series (plan 2026-11-09-crypto-book-v1, Task 4; planning decisions 7 and 8).

precompute_aux builds aux["regime"] once, from the benchmark close and its SMA: "offset" (stocks) is the old inline
rule, "hysteresis" (crypto) goes off below SMA*(1-band) and comes back on only above SMA*(1+band). build_targets reads
it before the no-picks return; a book with market.fill_regime_on_no_picks also fills the regime and the drawdown state
on days with no picks.
"""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from aitrader import backtest, cycle, data, journal
from aitrader.broker import PaperBroker
from aitrader.signals import compute_all
from aitrader.strategy import build_targets, precompute_aux, regime_series
from golden_util import frozen_env, load_panel
from test_core import cfg_for

ND = "risk_off(no-data)"


def crypto_panel(n: int = 500, seed: int = 7) -> dict:
    """Two coins on a 7-day calendar: a bull leg, a bear leg below the 200-day line, then a recovery."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    t = np.arange(n)[:, None]
    drift = np.where(t < 260, 0.004, np.where(t < 380, -0.006, 0.006)) * np.array([1.0, 1.2])
    rets = drift + rng.normal(0.0, 1.0, (n, 2)) * np.array([0.03, 0.04])
    close = pd.DataFrame(np.array([30000.0, 2000.0]) * np.exp(np.cumsum(rets, axis=0)), index=idx,
                         columns=["BTC-USD", "ETH-USD"])
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.003, close.shape))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, close.shape)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, close.shape)))
    return {"open": open_, "high": high, "low": low, "close": close,
            "volume": pd.DataFrame(1e9, index=idx, columns=close.columns)}


def ratio_panel(ratios: list[float], n_sma: int = 200) -> dict:
    """A one-coin BTC panel whose close / SMA(n_sma) equals ratios[k] exactly from the first valid SMA bar on."""
    c = [100.0] * (n_sma - 1)
    for q in ratios:  # SMA_t = (s + c_t) / n and c_t = q * SMA_t  =>  c_t = q * s / (n - q)
        c.append(q * sum(c[-(n_sma - 1):]) / (n_sma - q))
    close = pd.DataFrame({"BTC-USD": c}, index=pd.date_range("2024-01-01", periods=len(c), freq="D"))
    return {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": close * 0 + 1e9}


def inline_rule(bpx, sma, band: float) -> str:
    """The rule that was inline in build_targets before Task 4 (strategy.py:152-159), for one date."""
    if pd.isna(sma) or pd.isna(bpx) or bpx < sma * (1 - band):
        return "risk_off" if pd.notna(sma) and pd.notna(bpx) else ND
    return "risk_on"


def switches(regime: pd.Series) -> int:
    s = regime[regime != ND]
    return int((s != s.shift()).sum()) - 1


def with_mode(cfg: dict, mode: str) -> dict:
    c = copy.deepcopy(cfg)
    c["risk"]["regime_band_mode"] = mode
    return c


class RegimeSeries(unittest.TestCase):
    def test_offset_series_equals_inline_rule(self):
        p = load_panel()
        cfg = cfg_for(p)
        self.assertEqual(cfg["risk"]["regime_band_mode"], "offset")  # the stock book keeps today's rule
        close = p["close"].copy()
        close.iloc[505, close.columns.get_loc("SPY")] = np.nan  # a no-data day after the warm-up too
        p = {**p, "close": close}
        aux = precompute_aux(p, cfg)
        want = [inline_rule(close["SPY"].loc[d], aux["bench_sma"].loc[d], cfg["risk"]["regime_band_pct"]) for d in close.index]
        self.assertTrue(aux["regime"].index.equals(close.index))
        self.assertEqual(aux["regime"].tolist(), want)
        self.assertEqual(set(want), {"risk_on", "risk_off", ND})
        self.assertGreater(switches(aux["regime"]), 0)

    def test_hysteresis_switch_counts(self):
        """A close oscillating +-1.5% around the go-to-cash line SMA*(1-band), 10 bars each side: the offset rule
        switches at every crossing, hysteresis never comes back (that needs a close above SMA*(1+band))."""
        cfg = data.load_config("crypto", "crypto")
        line = 1 - cfg["risk"]["regime_band_pct"]
        for first, hyst in ((-1, 0), (+1, 1)):  # starting below the line: 0 switches; above it: one switch to off
            ratios = ([line * (1 + first * 0.015)] * 10 + [line * (1 - first * 0.015)] * 10) * 15
            p = ratio_panel(ratios)
            got = {m: switches(precompute_aux(p, with_mode(cfg, m))["regime"]) for m in ("offset", "hysteresis")}
            self.assertEqual(got, {"offset": 29, "hysteresis": hyst}, first)

    def test_hysteresis_thresholds_and_no_data_carry(self):
        """Planning decision 7: the first valid bar starts the state like the offset rule; off below SMA*0.98,
        back on only above SMA*1.02; a NaN close or SMA is no-data that day and the carried state is unchanged."""
        nan = np.nan
        idx = pd.date_range("2024-01-01", periods=11, freq="D")
        px = pd.Series([100, 97.9, 99, 101.9, 102.1, 98, nan, 97.9, nan, 101, 102.1], index=idx, dtype=float)
        sma = pd.Series([nan] + [100.0] * 10, index=idx)
        reg, state = regime_series(px, sma, 0.02, "hysteresis")
        off, on = "risk_off", "risk_on"
        self.assertEqual(reg.tolist(), [ND, off, off, off, on, on, ND, off, ND, off, on])
        self.assertEqual(state.tolist(), [None, "off", "off", "off", "on", "on", "on", "off", "off", "off", "on"])
        reg, _ = regime_series(px, sma, 0.02, "offset")
        self.assertEqual(reg.tolist(), [ND, off, on, on, on, on, ND, off, ND, on, on])
        with self.assertRaises(ValueError):
            regime_series(px, sma, 0.02, "bogus")

    def test_one_missing_close_is_one_no_data_day(self):
        """Hysteresis: one NaN BTC close after the warm-up (ETH still has its close, so fetch_panel keeps the row)
        is no-data on that day only. The SMA runs over valid closes, the carried state shows on that day, and every
        bar after it has a regime again."""
        p = crypto_panel()
        close = p["close"].copy()
        k = 300
        close.iloc[k, close.columns.get_loc("BTC-USD")] = np.nan
        p = {**p, "close": close}
        cfg = data.load_config("crypto", "crypto")
        aux = precompute_aux(p, cfg)
        reg, state = aux["regime"], aux["regime_state"]
        self.assertEqual([i for i in range(len(reg)) if reg.iloc[i] == ND], [*range(199), k])  # warm-up + that day
        self.assertIn(state.iloc[k - 1], ("on", "off"))
        self.assertEqual(state.iloc[k], state.iloc[k - 1])
        self.assertFalse((reg.iloc[k + 1:] == ND).any())
        valid = close["BTC-USD"].dropna()
        self.assertAlmostEqual(aux["bench_sma"].iloc[k + 1], valid.loc[:close.index[k + 1]].tail(200).mean(), places=6)
        d = close.index[k + 5]  # still causal: nothing after d changes the series up to d
        aux_t = precompute_aux({key: v.loc[:d] for key, v in p.items()}, cfg)
        pd.testing.assert_series_equal(reg.loc[:d], aux_t["regime"])
        pd.testing.assert_series_equal(aux["bench_sma"].loc[:d], aux_t["bench_sma"])

    def test_truncation_invariance(self):
        """Regime, regime state, targets and diag at t are identical when all data after t is dropped."""
        stock, coins = load_panel(), crypto_panel()
        seen = set()
        for p, cfg in ((stock, cfg_for(stock)), (coins, data.load_config("crypto", "crypto"))):
            sig, aux = compute_all(p, cfg), precompute_aux(p, cfg)
            reg = aux["regime"]
            flips = [i for i in range(201, len(reg)) if reg.iloc[i] != reg.iloc[i - 1]]
            self.assertTrue(flips, cfg["benchmark"])
            for i in sorted({*range(210, len(reg), 41), *flips[:3], *[f - 1 for f in flips[:3]], len(reg) - 1}):
                d = p["close"].index[i]
                pt = {k: v.loc[:d] for k, v in p.items()}
                aux_t = precompute_aux(pt, cfg)
                pd.testing.assert_series_equal(reg.loc[:d], aux_t["regime"])
                pd.testing.assert_series_equal(aux["regime_state"].loc[:d], aux_t["regime_state"])
                t1, d1 = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, {}, set(), aux)
                t2, d2 = build_targets(d, pt, compute_all(pt, cfg), cfg["prior_weights"], cfg, 1.0, {}, set(), aux_t)
                self.assertEqual(t1, t2, (cfg["benchmark"], d))
                self.assertEqual(d1, d2, (cfg["benchmark"], d))
                seen.add((cfg["benchmark"], d1["regime"].split("+")[0], bool(t1)))
        for bench in ("SPY", "BTC-USD"):  # not vacuous: both regimes, and the crypto book on picks and no-picks days
            self.assertTrue({"risk_on", "risk_off"} <= {r for b, r, _ in seen if b == bench}, bench)
        self.assertEqual({t for b, _, t in seen if b == "BTC-USD"}, {True, False})


class SameRegimeEverywhere(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_regime_in_main_shadow_proposal_backtest(self):
        p = crypto_panel()
        cfg = data.load_config("crypto", "crypto")
        # Same closes on both paths: next_open (Task 5) would drop each stub's newest bar (no D+1 row) and, on this
        # synthetic panel, open[D+1] != close[D]. The close-source rule has its own tests in test_data_rules.
        cfg["market"]["close_source"] = "yahoo"
        reg = precompute_aux(p, cfg)["regime"]
        flips = [i for i in range(300, len(reg)) if reg.iloc[i] != reg.iloc[i - 1]]
        self.assertTrue(flips)
        days = range(flips[0] - 2, flips[0] + 3)  # across a regime switch
        real = build_targets
        calls: dict[str, list] = {}
        bt: dict[str, str] = {}

        def rec_live(date, *a, **k):
            t, d = real(date, *a, **k)
            calls.setdefault(str(pd.Timestamp(date).date()), []).append(d["regime"])
            return t, d

        def rec_bt(date, *a, **k):
            t, d = real(date, *a, **k)
            bt[str(pd.Timestamp(date).date())] = d["regime"]
            return t, d

        with mock.patch.object(backtest, "build_targets", rec_bt):
            backtest.run(p, cfg, start=str(p["close"].index[days[0] - 40].date()), weights_mode="prior")
        live: dict[str, list] = {}
        with frozen_env(self.tmp, None), mock.patch.object(cycle, "build_targets", rec_live):
            cycle.load_config = lambda: cfg
            for i in days:
                sl = {k: v.iloc[:i + 1] for k, v in p.items()}
                cycle.load_market = lambda c, rng="10y", age=0.1, sl=sl: sl
                ds = str(p["close"].index[i].date())
                proposal = cycle.run_cycle(propose=True)
                saved = journal.load_json("proposal.json")["diag"]["regime"]  # read now: a crypto decision deletes it (Task 6)
                cycle.run_cycle()
                live[ds] = [proposal["diag"]["regime"], saved,
                            journal.load_json("portfolio.json")["regime"], journal.read("decisions.jsonl")[-1]["diag"]["regime"]]
        self.assertEqual(len({reg.iloc[i] for i in days}), 2)  # the window really holds a switch
        for i in days:
            ds = str(p["close"].index[i].date())
            self.assertEqual(len(calls[ds]), 4, ds)  # proposal main + shadow, decision main + shadow
            self.assertEqual(set(calls[ds] + live[ds]), {bt[ds]}, ds)
            self.assertEqual(bt[ds], reg.iloc[i], ds)


class NoPicksDiag(unittest.TestCase):
    def test_no_picks_day_keeps_dd_state_crypto(self):
        """Review Focus 5 / planning decision 8: on a crypto day with no picks the diag still carries the regime
        and the drawdown state, so a flat book's -50% re-entry streak keeps counting; the stock diag is unchanged."""
        p = crypto_panel()
        cfg = data.load_config("crypto", "crypto")
        cfg["risk"]["min_score"] = 9.0  # scores live in [-1, 1]: nothing is ever picked
        r = cfg["risk"]
        sig, aux = compute_all(p, cfg), precompute_aux(p, cfg)
        d = p["close"].index[230]
        targets, diag = build_targets(d, p, sig, cfg["prior_weights"], cfg, 0.45, {}, set(), aux)
        self.assertEqual(targets, {})
        self.assertEqual(diag["regime"], aux["regime"].loc[d])
        self.assertEqual(diag["regime"], "risk_on")
        self.assertEqual((diag["dd_state"], diag["drawdown"], diag["gross"]), ("flat", -0.55, 0.0))
        self.assertEqual(diag["regime_px"], round(float(p["close"]["BTC-USD"].loc[d]), 4))
        self.assertEqual(diag["regime_sma"], round(float(aux["bench_sma"].loc[d]), 4))
        self.assertEqual(diag["regime_state"], "on")

        stock = load_panel()
        scfg = cfg_for(stock)
        scfg["risk"]["min_score"] = 9.0
        sd = stock["close"].index[450]
        _, sdiag = build_targets(sd, stock, compute_all(stock, scfg), scfg["prior_weights"], scfg, 0.45, {}, set(),
                                 precompute_aux(stock, scfg))
        self.assertEqual(list(sdiag), ["date", "n_scored", "n_eligible", "stopped", "top_scores", "bottom_scores", "regime", "gross"])
        self.assertEqual((sdiag["regime"], sdiag["gross"]), ("n/a", 0.0))

        # The backtest loop (backtest.run) on a flat book through a risk-on run with no picks: the peak resets
        # after dd_reentry_days only when the no-picks diag keeps the regime and the drawdown state.
        run = aux["regime"].iloc[200:200 + r["dd_reentry_days"] + 2]
        self.assertEqual(set(run), {"risk_on"})
        for fill in (True, False):
            c = copy.deepcopy(cfg)
            c["market"]["fill_regime_on_no_picks"] = fill
            b = PaperBroker(100000)
            b.state.update({"peak_equity": 250000.0, "dd_state": "flat"})
            prev = None
            for day in run.index:
                b.maybe_reset_peak(prev or "", str(day.date()), r["dd_reentry_days"], r["dd_halve"], r["dd_flat"], r.get("dd_reentry_ref"))
                _, dg = build_targets(day, p, sig, c["prior_weights"], c, b.peak_ratio({}), b.positions, set(), aux)
                b.state["dd_state"] = dg.get("dd_state")
                prev = dg.get("regime", prev)
            self.assertEqual(b.state.get("peak_resets", []), [str(run.index[r["dd_reentry_days"]].date())] if fill else [], fill)
            self.assertEqual(b.state["dd_state"], "halved" if fill else None, fill)


if __name__ == "__main__":
    unittest.main()
