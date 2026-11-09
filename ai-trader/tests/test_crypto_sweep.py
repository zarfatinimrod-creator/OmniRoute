"""Crypto sweep (plan 2026-11-09-crypto-book-v1, Task 9; spec section 7 "Sweep", planning decision 14).

Small synthetic 3-coin panels, a temp state dir and a temp report path: never the network, never the real state.
The unit tests use a short window and 2 phases; the CLI runs the default 7 phases from 2018-01-01, split 2022-01-01.
"""

import contextlib
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from aitrader import backtest, crypto_sweep, data, journal

ROOT = Path(__file__).resolve().parent.parent
PHASES = 2


def panel3(n: int = 520, seed: int = 11) -> dict:
    """BTC, ETH and XRP on a 7-day calendar, all trending up (BTC above its 200-day line through bars 420-490)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    rets = np.array([0.0025, 0.0030, 0.0035]) + rng.normal(0.0, 1.0, (n, 3)) * np.array([0.025, 0.035, 0.045])
    close = pd.DataFrame(np.array([30000.0, 2000.0, 0.5]) * np.exp(np.cumsum(rets, axis=0)), index=idx,
                         columns=["BTC-USD", "ETH-USD", "XRP-USD"])
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.003, close.shape))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, close.shape)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, close.shape)))
    return {"open": open_, "high": high, "low": low, "close": close,
            "volume": pd.DataFrame(1e9, index=idx, columns=close.columns)}


def window(p: dict) -> tuple[str, str, str]:
    """start, split, end: 63 bars from bar 420 (signals need 395), halves of 31 and 32 bars (backtest needs 30)."""
    idx = p["close"].index
    return str(idx[420].date()), str(idx[451].date()), str(idx[482].date())


def seed_script():
    spec = importlib.util.spec_from_file_location("seed_crypto_trials", ROOT / "scripts" / "seed_crypto_trials.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def trials(state: Path) -> list[dict]:
    p = state / "crypto" / "trials.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = journal.STATE, journal.BOOK, journal._BASE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE, journal.BOOK, journal._BASE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class RealSweep(unittest.TestCase):
    """One real sweep (2 phases, 63 bars) shared by the tests that read its runs and its files."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._saved = journal.STATE, journal.BOOK, journal._BASE
        journal.STATE = cls.tmp
        seeder = seed_script()
        cls.seeded = [seeder.seed(), seeder.seed()]  # the second run must write nothing
        cls.signal_calls, cls.profiles = [], []
        real_signals, real_load = crypto_sweep.compute_all, data.load_config

        def rec_signals(panel, cfg):
            cls.signal_calls.append((tuple(panel["close"].columns), dict(cfg["prior_weights"])))
            return real_signals(panel, cfg)

        def rec_load(book=None, profile=None):
            cls.profiles.append((book, profile))
            return real_load(book, profile)

        cls.panel = panel3()
        start, split, end = window(cls.panel)
        cls.report = cls.tmp / "out" / "sweep.md"
        with mock.patch.object(crypto_sweep, "compute_all", rec_signals), mock.patch.object(data, "load_config", rec_load):
            cls.res = crypto_sweep.run_sweep(cls.panel, start, split, end, phases=PHASES, report_path=cls.report)

    @classmethod
    def tearDownClass(cls):
        journal.STATE, journal.BOOK, journal._BASE = cls._saved
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_profiles_use_own_panel_and_signals(self):
        runs = self.res["runs"]
        base_runs = [n for n, r in runs.items() if r["profile"] == "crypto_base"]
        self.assertEqual(sorted(base_runs), ["base:h1", "base:h2", "base@100", "base@50"])
        for n in base_runs:
            self.assertEqual(runs[n]["universe"], ["BTC-USD"], n)
            for ph in runs[n]["phases"]:
                self.assertNotIn("ETH-USD", ph["symbols"], n)  # crypto_base never holds ETH
        self.assertIn("ETH-USD", {s for ph in runs["cand@50"]["phases"] for s in ph["symbols"]})
        # signals recomputed on each profile's own panel: crypto_base's priors only ever see the BTC column
        trend_only = [cols for cols, pw in self.signal_calls if pw["trend"] == 1.0]
        self.assertTrue(trend_only)
        self.assertEqual(set(trend_only), {("BTC-USD",)})
        self.assertIn(("BTC-USD", "ETH-USD"), {cols for cols, _ in self.signal_calls})
        self.assertEqual(len(self.res["pass_rule"]["phases_won"]["value"].split("/")), 2)
        self.assertIn(self.res["ship"], ("crypto", "crypto_base"))

    def test_dsr_counts_seed_plus_runs(self):
        self.assertEqual(self.seeded, [145, 0])
        recs = trials(self.tmp)
        self.assertEqual(len(recs), 2)  # one seed record (never doubled), one sweep record
        seed_rows = [r for t in recs if t.get("seed") for r in t["rows"]]
        self.assertEqual(len(seed_rows), 145)
        with_sharpe = [r for r in seed_rows if r["sharpe_pp"] is not None]
        self.assertTrue(with_sharpe)
        r0 = with_sharpe[0]
        self.assertAlmostEqual(r0["sharpe_pp"], r0["sharpe"] / 365 ** 0.5, places=6)  # annualised -> per period
        self.assertTrue(any(r["benchmark"] for r in seed_rows))  # buy&hold rows: in N, not in the spread
        n_runs = sum(len(r["phases"]) for r in self.res["runs"].values())
        self.assertEqual(len(recs[1]["rows"]), n_runs)
        self.assertEqual(self.res["dsr"]["n"], 145 + n_runs)
        self.assertEqual(self.res["dsr"]["profile"], self.res["ship"])
        saved = json.loads((self.tmp / "crypto" / "dsr.json").read_text())
        self.assertEqual({k: saved[k] for k in ("profile", "value", "n")}, self.res["dsr"])
        self.assertFalse((self.tmp / "dsr.json").exists())  # the crypto book's state dir only
        self.assertFalse((self.tmp / "trials.jsonl").exists())
        text = self.report.read_text()
        self.assertIn(f"N={145 + n_runs}", text)
        self.assertIn('"profile": "crypto_base"', text)  # the printed merged configs
        self.assertNotIn("ship_profile", text)

    def test_hindsight_control_runs_without_universe_assert(self):
        ctl = self.res["runs"]["control:btc_xrp"]
        self.assertEqual(ctl["universe"], ["BTC-USD", "XRP-USD"])
        self.assertEqual(ctl["caps"]["XRP-USD"], 0.6)
        self.assertIn("XRP-USD", {s for ph in ctl["phases"] for s in ph["symbols"]})
        # never load_config'd (None: journal.use_book's default profile)
        self.assertEqual({p for _, p in self.profiles} - {"crypto", "crypto_base", None}, set())
        self.assertEqual(self.res["runs"]["final:missed_night"]["exec_lag"], 2)


def fake_run(sharpes: dict, calls: list):
    """A stand-in for crypto_sweep._run: per-name Sharpe, candidate days a little better than base days."""
    idx = pd.date_range("2024-01-01", periods=80, freq="D")
    noise = np.random.default_rng(3).normal(0.0, 0.02, len(idx))

    def run(name, cfg, panel_all, start, end, phases, exec_lag=1):
        calls.append((name, copy.deepcopy(cfg), exec_lag))
        s = sharpes.get(name, sharpes["base" if name.startswith("base") else "final"])
        day = pd.Series(noise + (0.0 if name.startswith("base") else 0.004), index=idx)
        return {"phases": [{"phase": k, "sharpe": s, "maxdd": -0.2, "cagr": 0.1, "n_fills": 1, "symbols": list(cfg["universe"])}
                           for k in range(phases)],
                "daily": pd.DataFrame({k: day for k in range(phases)}),
                "bench": {"sharpe": 0.3}}
    return run


class SweepLogic(TempState):
    SHARPES = {"base": 0.5, "final": 1.1, "cand@50": 1.0, "abl:no_eth": 1.1, "abl:no_atr_stop": 1.0, "abl:no_halve": 0.9,
               "final@50": 1.2}

    def sweep(self, sharpes, **patches):
        calls: list = []
        with contextlib.ExitStack() as st:
            for k, v in {"_run": fake_run(sharpes, calls), **patches}.items():
                st.enter_context(mock.patch.object(crypto_sweep, k, v))
            res = crypto_sweep.run_sweep(panel3(60), "2024-01-01", "2024-02-01", None, phases=7, report_path=self.tmp / "r.md")
        return res, calls

    def test_ablation_then_pass_rule_order(self):
        res, calls = self.sweep(self.SHARPES)
        names = [c[0] for c in calls]
        abl = [i for i, n in enumerate(names) if n.startswith("abl:")]
        self.assertEqual(len(abl), 3)
        self.assertLess(names.index("cand@50"), min(abl))
        fin = names.index("final@50")  # two components dropped (median delta >= 0): the combined candidate runs once more
        self.assertLess(max(abl), fin)
        for n in ("base@100", "final@100", "base:h1", "final:h1", "base:h2", "final:h2", "final:missed_night"):
            self.assertLess(fin, names.index(n), n)
        self.assertEqual(res["final_candidate"]["dropped"], ["eth", "atr_stop"])
        self.assertEqual({k: v["dropped"] for k, v in res["ablations"].items()}, {"eth": True, "atr_stop": True, "halve": False})
        cfg100 = calls[names.index("final@100")][1]
        self.assertEqual(list(cfg100["universe"]), ["BTC-USD"])
        self.assertEqual((cfg100["risk"]["atr_stop_mult"], cfg100["risk"]["dd_halve"]), (0.0, -0.25))  # halving kept
        self.assertEqual(cfg100["costs"]["fee_bps"], 100)
        self.assertEqual(calls[names.index("final:missed_night")][2], 2)
        self.assertEqual(res["dsr"]["n"], 7 * len(names))  # the combined run counts toward N (no seed in this state)
        self.assertEqual(res["ship"], "crypto")
        # one dropped component: the ablation run is the final candidate, no extra run
        res, calls = self.sweep({**self.SHARPES, "abl:no_eth": 0.9, "abl:no_atr_stop": 0.9, "abl:no_halve": 1.0})
        names = [c[0] for c in calls]
        self.assertNotIn("final@50", names)
        self.assertEqual(res["final_candidate"]["dropped"], ["halve"])
        self.assertEqual(res["final_candidate"]["run"], "abl:no_halve")
        cfg = calls[names.index("final@100")][1]["risk"]
        self.assertEqual((cfg["dd_halve"], cfg["atr_stop_mult"]), (-1.0, 3.0))
        self.assertNotIn("dd_reentry_ref", cfg)  # the broker default: dd_flat / 2 = -0.25

    def test_pass_rule_rejects_when_bootstrap_below_095(self):
        pr = crypto_sweep.pass_rule(d50=[0.1] * 7, dd_final=[-0.20] * 7, dd_base=[-0.19] * 7, p_boot=0.949,
                                    d100=[0.05] * 7, d_h1=[0.02] * 7, d_h2=[0.03] * 7)
        self.assertEqual(set(pr), {"phases_won", "p_boot", "dd_gap", "cost100", "halves"})
        self.assertFalse(pr["p_boot"]["pass"])
        self.assertTrue(all(pr[k]["pass"] for k in ("phases_won", "dd_gap", "cost100", "halves")))
        res, _ = self.sweep({**self.SHARPES, "abl:no_eth": 0.9, "abl:no_atr_stop": 0.9},
                            bootstrap_p=lambda *a, **k: 0.949)
        self.assertEqual((res["pass_rule"]["p_boot"]["pass"], res["ship"], res["dsr"]["profile"]), (False, "crypto_base", "crypto_base"))
        res, _ = self.sweep({**self.SHARPES, "abl:no_eth": 0.9, "abl:no_atr_stop": 0.9},
                            bootstrap_p=lambda *a, **k: 0.95)
        self.assertEqual((res["pass_rule"]["p_boot"]["pass"], res["ship"]), (True, "crypto"))

    def test_bootstrap_matches_power_replay_loop(self):
        rng = np.random.default_rng(5)
        idx = pd.date_range("2024-01-01", periods=400, freq="D")
        b = pd.Series(rng.normal(0.0005, 0.02, 400), index=idx)
        c = b + rng.normal(0.0004, 0.005, 400)
        dfr = pd.concat([b, c], axis=1).values  # power.py's loop, verbatim
        g = np.random.default_rng(0)
        n, L, diffs = len(dfr), 30, []
        for _ in range(2000):
            starts = g.integers(0, n - L, n // L + 1)
            x = dfr[np.concatenate([np.arange(s, s + L) for s in starts])[:n]]
            s = x.mean(0) / x.std(0) * 365 ** 0.5
            diffs.append(s[1] - s[0])
        self.assertEqual(crypto_sweep.bootstrap_p(b, c, 365), float((np.array(diffs) > 0).mean()))


class MergedConfig(unittest.TestCase):
    def test_merged_config_names_its_profile(self):  # Task 1 review: ship_profile no longer leaks into the config
        for profile in ("crypto", "crypto_base"):
            c = data.load_config("crypto", profile)
            self.assertEqual(c["profile"], profile)
            self.assertNotIn("ship_profile", c)
        self.assertEqual(data.load_config("crypto")["profile"], "crypto")  # the default: books.crypto.ship_profile
        self.assertNotIn("profile", data.load_config("stocks"))


class ExecLag(unittest.TestCase):
    def test_exec_lag_2_fills_one_bar_later(self):
        p = {k: v[["BTC-USD"]] for k, v in panel3().items()}
        cfg = data.load_config("crypto", "crypto_base")
        idx = p["close"].index
        start, end = str(idx[420].date()), str(idx[470].date())
        f1 = backtest.run(p, cfg, start, end, "prior", 7)["_fills"]
        f2 = backtest.run(p, cfg, start, end, "prior", 7, exec_lag=2)["_fills"]
        self.assertEqual(f1[0]["date"], str(idx[421].date()))  # decided at the start close, filled at the next open
        self.assertEqual(f2[0]["date"], str(idx[422].date()))  # missed night: one bar later
        slip = (cfg["costs"]["slippage_bps"] + cfg["costs"]["exec_delay_bps"]) / 1e4  # delay cost: backtest only
        for f in (f1[0], f2[0]):
            self.assertAlmostEqual(f["price"], p["open"].loc[f["date"], "BTC-USD"] * (1 + slip), places=3)
            self.assertAlmostEqual(f["fee"], f["qty"] * f["price"] * cfg["costs"]["fee_bps"] / 1e4, places=2)
            self.assertNotEqual(f["qty"], int(f["qty"]))  # qty_step 1e-6 reaches the broker
        with self.assertRaises(ValueError):
            backtest.run(p, cfg, start, end, "prior", 7, exec_lag=0)


if __name__ == "__main__":
    unittest.main()
