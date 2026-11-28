"""The time machine tells the truth about its own uncertainty (2026-11-10).

- Every sweep row carries a seeded block-bootstrap range for Sharpe (excess of cash), CAGR and max drawdown.
- Every row carries the paired bootstrap probability that its Sharpe is above the benchmark's and above the base's.
- Every registered sweep leaves a run record beside trials.jsonl (daily returns per run, per-phase rows, panel hash,
  code commit, config hash) that a later re-run can be compared with row by row.
- The Deflated Sharpe is printed in both readings and on every base phase, and the registered one stays the rule.
- A window under the floor (bootstrap.min_blocks x block_days days) or a null seed gets no range, and the reason is
  printed; nothing the ranges need can cost a finished sweep its table or its registration.
- The fill-drift report compares each live fill with the open of the bar a replay fills its decision on.
None of it may move an existing number: the legacy columns below were recorded from the code before this change.

Synthetic panels and a temp state dir: never the network, never the phone, never a subprocess, never the real state.
"""

import concurrent.futures
import contextlib
import copy
import io
import json
import math
import shutil
import statistics
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import test_crypto_sweep as tcs  # a module, not its TestCase classes: importing those would run them twice
import test_dashboard_books as tdb
from aitrader import backtest, crypto_sweep, dashboard, data, journal, metrics, news_live, notify, report
from aitrader.__main__ import main
from test_core import cfg_for, synthetic_panel


def _refuse(*a, **k):
    raise AssertionError("a unit test must not reach the network, the phone or a subprocess")


_GUARDS = [mock.patch.object(notify, "send", _refuse), mock.patch.object(news_live, "live_price", _refuse),
           mock.patch.object(data, "_chart", _refuse), mock.patch.object(subprocess, "run", _refuse),
           mock.patch.object(requests.Session, "request", _refuse), mock.patch.object(requests, "get", _refuse),
           mock.patch.object(requests, "post", _refuse)]


def setUpModule():
    for g in _GUARDS:
        g.start()


def tearDownModule():
    for g in _GUARDS:
        g.stop()


RF = 0.035
RF_D = (1 + RF) ** (1 / 252) - 1
SET = {"block_days": 10, "draws": 300, "seed": 3, "level": 0.95, "min_blocks": 8}  # floor 8 x 10 = 80 days: the Sweep window has 89
RANGE_COLS = ["sharpe_lo", "sharpe_hi", "cagr_lo", "cagr_hi", "maxdd_lo", "maxdd_hi", "p_gt_bench", "p_gt_base"]
FAKE_COMMIT = {"commit": "c0ffee0123", "code_dirty": False}
ROOT = Path(backtest.__file__).resolve().parent.parent


def series(seed: int, n: int = 600, mu: float = 0.0005, sd: float = 0.01) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mu, sd, n), index=pd.bdate_range("2020-01-01", periods=n))


class Bootstrap(unittest.TestCase):
    def test_settings_come_from_config_over_defaults(self):
        self.assertEqual(set(metrics.BOOT_DEFAULTS), {"block_days", "draws", "seed", "level", "min_blocks"})
        self.assertEqual(metrics.boot_cfg({}), metrics.BOOT_DEFAULTS)
        self.assertEqual(metrics.boot_cfg({"bootstrap": {"draws": 50}}), {**metrics.BOOT_DEFAULTS, "draws": 50})

    def test_config_json_carries_the_bootstrap_and_drift_blocks(self):
        """Project rule 5: the assumptions are in config.json. Their values are the code defaults, so no number moved."""
        raw = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(raw["bootstrap"], {"block_days": 20, "draws": 2000, "seed": 0, "level": 0.95, "min_blocks": 40})
        self.assertEqual(raw["drift"], {"pause_seconds": 1.5})
        self.assertEqual((raw["bootstrap"], raw["drift"]), (metrics.BOOT_DEFAULTS, backtest.DRIFT_DEFAULTS))
        for cfg in (data.load_config("stocks"), data.load_config("crypto", "crypto"), data.load_config("crypto", "crypto_base")):
            self.assertEqual((metrics.boot_cfg(cfg), cfg["drift"]), (raw["bootstrap"], raw["drift"]))  # one block, every book

    def test_a_history_shorter_than_the_floor_is_refused_with_the_reason(self):
        """Under min_blocks x block_days days the "95%" range is too narrow to carry its label: no range at all."""
        frame = pd.DataFrame({("base", 0): series(1), ("bench", 0): series(2)})  # 600 days
        at_floor = metrics.boot_rows(frame, 0.0, 252, {**SET, "min_blocks": 60}, None, "bench")  # 60 x 10 = 600: allowed
        self.assertEqual(at_floor["settings"]["days"], 600)
        with self.assertRaises(ValueError) as cm:
            metrics.boot_rows(frame, 0.0, 252, {**SET, "min_blocks": 61}, None, "bench")
        reason = metrics.boot_error(cm.exception)  # what the report prints after "Ranges: not computed"
        for part in ("600 days", "bootstrap.min_blocks x block_days", "61 x 10 = 610"):
            self.assertIn(part, reason)
        with self.assertRaises(ValueError) as cm:  # days missing in one run do not count
            metrics.boot_rows(pd.DataFrame({("base", 0): series(1), ("late", 0): series(3).iloc[5:]}), 0.0, 252,
                              {**SET, "min_blocks": 60})
        self.assertIn("595 days", metrics.boot_error(cm.exception))
        self.assertEqual(metrics.boot_error(KeyError("x")), "KeyError")  # not a refusal: the error's name, as before

    def test_a_seed_that_is_not_a_whole_number_is_refused(self):
        """A null seed would give ranges that differ on every run with nothing in the output saying so."""
        for seed in (None, 1.5, "7", True, -1):
            with self.assertRaises(ValueError, msg=repr(seed)) as cm:
                metrics.boot_index(100, 10, 5, seed)
            self.assertIn("bootstrap.seed", metrics.boot_error(cm.exception), repr(seed))
        frame = pd.DataFrame({("base", 0): series(1)})
        with self.assertRaises(ValueError) as cm:
            metrics.boot_rows(frame, 0.0, 252, {**SET, "seed": None})
        self.assertIn("got None", metrics.boot_error(cm.exception))
        self.assertEqual(metrics.boot_index(100, 10, 5, np.int64(4)).shape, (5, 100))  # a whole number of any kind

    def test_index_is_seeded_wrapped_and_made_of_blocks(self):
        n = 500
        idx = metrics.boot_index(n, 20, 300, seed=1)
        self.assertEqual(idx.shape, (300, n))
        self.assertTrue(((idx >= 0) & (idx < n)).all())
        np.testing.assert_array_equal(idx, metrics.boot_index(n, 20, 300, seed=1))  # seeded: the same resamples again
        self.assertFalse(np.array_equal(idx, metrics.boot_index(n, 20, 300, seed=2)))
        runs_on = idx[:, 1:] == (idx[:, :-1] + 1) % n  # the next day of the same block
        self.assertAlmostEqual(1 / (1 - runs_on.mean()), 20, delta=1.0)  # mean block length = block_days
        self.assertTrue(((idx[:, :-1] == n - 1) & (idx[:, 1:] == 0)).any())  # circular: a block runs over the end
        edge = np.isin(idx, np.r_[0:10, n - 10:n]).mean()  # the first and last days are drawn as often as any other
        self.assertAlmostEqual(edge / (20 / n), 1.0, delta=0.2)

    def test_resampled_numbers_are_the_report_numbers(self):
        """Sharpe (excess of cash), CAGR and max drawdown of a resample are metrics.summary() of the same days."""
        r = np.random.default_rng(0).normal(0.0006, 0.011, (300, 2))
        idx = metrics.boot_index(300, 15, 6, seed=5)
        st = metrics.boot_stats(r, idx, RF_D, 252)
        self.assertEqual({k: v.shape for k, v in st.items()}, {"sharpe": (6, 2), "cagr": (6, 2), "maxdd": (6, 2)})
        days = pd.bdate_range("2020-01-01", periods=301)
        for i in range(6):
            for k in range(2):
                s = metrics.summary(pd.Series(np.r_[1.0, np.cumprod(1 + r[idx[i], k])], index=days), rf_annual=RF)
                self.assertAlmostEqual(st["sharpe"][i, k], s["sharpe"], delta=5.1e-4)
                self.assertAlmostEqual(st["cagr"][i, k], s["cagr"], delta=5.1e-5)
                self.assertAlmostEqual(st["maxdd"][i, k], s["max_drawdown"], delta=5.1e-5)
        cash = metrics.boot_stats(np.full((300, 1), RF_D), idx, RF_D, 252)  # an all-cash run: no variance
        self.assertEqual((cash["sharpe"].tolist(), cash["maxdd"].tolist()), ([[0.0]] * 6, [[0.0]] * 6))
        self.assertAlmostEqual(cash["cagr"][0, 0], RF, places=9)

    def test_range_covers_a_known_sharpe_about_95_times_in_100(self):
        true, n, sd = 1.0, 500, 0.01
        hits = 0
        for seed in range(200):
            r = np.random.default_rng(1000 + seed).normal(true * sd / math.sqrt(252), sd, (n, 1))
            s = metrics.boot_stats(r, metrics.boot_index(n, 10, 300, seed), 0.0, 252)["sharpe"][:, 0]
            lo, hi = np.quantile(s, [0.025, 0.975])
            hits += lo <= true <= hi
        self.assertGreaterEqual(hits, 180)  # 90%: a range that misses the truth more often is too narrow to print
        self.assertLessEqual(hits, 198)  # 99%: one that never misses is too wide to mean anything

    def test_paired_probability_reads_half_for_two_copies(self):
        base = series(1)
        frame = pd.DataFrame({("base", 0): base, ("same", 0): base, ("better", 0): base + 0.0005,
                              ("worse", 0): base - 0.0005, ("other", 0): series(2), ("bench", 0): base})
        pairs = {k: "base" for k in ("same", "better", "worse", "other")}
        rows = metrics.boot_rows(frame, 0.0, 252, SET, pairs, "bench")["rows"]
        self.assertEqual(rows["same"]["p_gt_base"], 0.5)  # a tie in every resample: never "certainly worse"
        self.assertEqual((rows["better"]["p_gt_base"], rows["worse"]["p_gt_base"]), (1.0, 0.0))
        self.assertTrue(0.02 < rows["other"]["p_gt_base"] < 0.98)
        self.assertEqual((rows["same"]["p_gt_bench"], rows["better"]["p_gt_bench"]), (0.5, 1.0))
        self.assertIsNone(rows["base"]["p_gt_base"])  # nothing to compare the base with
        self.assertIsNone(rows["bench"]["p_gt_bench"])
        self.assertEqual(metrics.p_above([1.0, -1.0, 0.0, 0.0]), 0.5)

    def test_row_is_the_median_over_phases_paired_with_the_base_at_the_same_phase(self):
        base = {k: series(10 + k) for k in range(5)}
        cols = {("base", k): s for k, s in base.items()}
        cols.update({("v", 0): base[0], ("v", 4): base[4], ("v", 8): base[3]})  # 8 % 5 = 3: the base's phase 3
        cols[("w", 1)] = base[2]  # paired with the base's phase 1, a different series: not a tie
        frame = pd.DataFrame(cols)
        out = metrics.boot_rows(frame, RF_D, 252, SET, {"v": "base", "w": "base"}, None)
        self.assertEqual([out["phases"][("v", k)]["p_gt_base"] for k in (0, 4, 8)], [0.5, 0.5, 0.5])
        self.assertEqual(out["rows"]["v"]["p_gt_base"], 0.5)
        self.assertNotEqual(out["phases"][("w", 1)]["p_gt_base"], 0.5)
        self.assertIsNone(out["rows"]["v"]["p_gt_bench"])  # no benchmark given
        st = metrics.boot_stats(frame.to_numpy(), metrics.boot_index(len(frame), 10, 300, 3), RF_D, 252)
        med = np.median(st["sharpe"][:, :5], axis=1)  # the statistic the sweep table prints: the median over phases
        lo, hi = np.quantile(med, [0.025, 0.975])
        self.assertEqual((out["rows"]["base"]["sharpe_lo"], out["rows"]["base"]["sharpe_hi"]), (round(lo, 3), round(hi, 3)))
        one = np.quantile(st["maxdd"][:, 2], [0.025, 0.975])
        self.assertEqual((out["phases"][("base", 2)]["maxdd_lo"], out["phases"][("base", 2)]["maxdd_hi"]),
                         (round(one[0], 4), round(one[1], 4)))
        self.assertEqual(out["settings"], {**SET, "days": 600, "method": "stationary bootstrap, circular"})
        self.assertEqual(metrics.boot_rows(frame, RF_D, 252, SET, {"v": "base", "w": "base"}, None), out)
        moved = metrics.boot_rows(frame, RF_D, 252, {**SET, "seed": 4}, {"v": "base", "w": "base"}, None)
        self.assertNotEqual(moved["rows"]["base"], out["rows"]["base"])


def small_book():
    p = synthetic_panel(n_days=420, n_syms=12, seed=4)
    cfg = cfg_for(p)
    cfg["risk"]["min_score"] = -1.0  # make sure something trades on synthetic data
    return p, cfg


def few_variants(cfg):
    every = cfg["risk"].get("rebalance_every_days", 5)
    return [("base", {}, "prior", every), ("costs 15bps", {"costs": {"slippage_bps": 15}}, "prior", every),
            ("daily rebalance", {}, "prior", 1), ("monthly rebalance", {}, "prior", 21)]


LEGACY_COLS = ["variant", "phases", "sharpe_med", "sharpe_min", "sharpe_max", "wins_vs_base", "d_sharpe_med", "cagr_med",
               "maxdd_med", "calmar_med", "turnover_med", "psr_med"]
# backtest.sweep on small_book() with few_variants and 7 earlier trial rows, recorded at commit 0215537a (before the
# range columns existed). The sweep must keep printing exactly this.
LEGACY = [
    ["base", 5.0, 4.024, 3.62, 4.351, "-", 0.0, 0.3348, -0.017, 18.652, 11.96, 0.989],
    ["costs 15bps", 5.0, 3.829, 3.421, 4.182, "0/5", -0.186, 0.3231, -0.0176, 17.536, 11.96, 0.986],
    ["daily rebalance", 1.0, 3.959, 3.959, 3.959, "0/1", -0.093, 0.3397, -0.0162, 20.903, 13.74, 0.989],
    ["monthly rebalance", 5.0, 2.24, 1.764, 4.217, "0/5", -1.442, 0.1795, -0.0167, 11.692, 9.81, 0.907],
    ["SPY buy&hold", None, 1.743, None, None, None, None, 0.4835, -0.0816, 5.928, None, 0.843],
    ["Equal-weight universe", None, 3.788, None, None, None, None, 0.3159, -0.0154, 20.482, None, 0.986],
    ["DSR of base (N=11 trials)", None, None, None, None, None, None, None, None, None, None, 0.937],
]


class KeepingPool(concurrent.futures.ProcessPoolExecutor):
    """The real process pool, keeping what the runs returned (Sweep.resweep reads them again)."""
    kept: list = []

    def map(self, fn, *iterables, **kw):
        KeepingPool.kept = list(super().map(fn, *iterables, **kw))
        return KeepingPool.kept


class Replay:
    """Stands in for the pool: hands back runs that were already made, so nothing is run a second time."""

    def __init__(self, results: list):
        self.results = results

    def __call__(self, *a, **k):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def map(self, fn, jobs):
        return self.results


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records"))  # NaN -> None, so rows compare with ==


def canon(x):
    return json.loads(json.dumps(x, default=str).replace("NaN", "null"))  # the same for rows read back from a file


class Sweep(unittest.TestCase):
    """One real sweep (4 variants, 16 runs, 90 days) shared by the tests that read its table, detail and record."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls._saved = journal.STATE, journal.BOOK, journal._BASE
        journal.STATE = cls.tmp
        cls.earlier = [{"logged_at": "x", "start": "s", "rows": [{"variant": "old"}] * 7}]  # earlier looks
        journal.append("trials.jsonl", cls.earlier[0])
        cls.panel, cls.cfg = small_book()
        cls.cfg["bootstrap"] = SET
        cls.start = str(cls.panel["close"].index[330].date())
        cls.detail = {}
        with mock.patch.object(backtest, "_variants", few_variants), \
                mock.patch.object(backtest, "code_commit", lambda: dict(FAKE_COMMIT)), \
                mock.patch.object(concurrent.futures, "ProcessPoolExecutor", KeepingPool):
            cls.df = backtest.sweep(cls.panel, cls.cfg, cls.start, detail=cls.detail)
        cls.results = KeepingPool.kept
        # the code is named as it was when the sweep started: a commit made while it ran must not be recorded
        with mock.patch.object(backtest, "code_commit", lambda: {"commit": "made-later", "code_dirty": True}), \
                mock.patch.object(journal, "now_utc", lambda: "2026-11-10T12:00:00+00:00"):
            cls.rec = backtest.register(cls.df, cls.detail, cls.panel, cls.cfg, cls.start)
        cls.saved = backtest.load_record(cls.tmp / cls.rec["record"])

    @classmethod
    def tearDownClass(cls):
        journal.STATE, journal.BOOK, journal._BASE = cls._saved
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def row(self, variant: str) -> dict:
        return next(r for r in records(self.df) if r["variant"] == variant)

    def resweep(self, results: list | None = None, **boot) -> tuple[pd.DataFrame, dict]:
        """backtest.sweep again over the runs of setUpClass (or `results`), with `boot` over the bootstrap settings:
        everything after the runs is computed afresh, against the same 7 earlier trial rows."""
        cfg, detail = {**self.cfg, "bootstrap": {**SET, **boot}}, {}
        with mock.patch.object(backtest, "_variants", few_variants), mock.patch.object(backtest, "compute_all", lambda p, c: None), \
                mock.patch.object(backtest, "code_commit", lambda: dict(FAKE_COMMIT)), \
                mock.patch.object(journal, "read", lambda name: self.earlier), \
                mock.patch.object(concurrent.futures, "ProcessPoolExecutor", Replay(results or self.results)):
            return backtest.sweep(self.panel, cfg, self.start, detail=detail), detail

    def legacy_only(self, df: pd.DataFrame) -> None:
        self.assertEqual(list(df.columns), LEGACY_COLS)  # no range columns at all
        self.assertEqual([[r[c] for c in LEGACY_COLS] for r in records(df)], LEGACY)  # the table and the registered DSR

    def test_replaying_the_kept_runs_gives_the_same_sweep(self):
        df, detail = self.resweep()  # the helper the refusal tests below stand on
        self.assertEqual(records(df), records(self.df))
        self.assertEqual((detail["boot"], detail["dsr"]), (self.detail["boot"], self.detail["dsr"]))

    def test_a_window_shorter_than_the_floor_gets_no_ranges_and_says_why(self):
        df, detail = self.resweep(min_blocks=40)  # 89 days against 40 blocks of 10
        self.legacy_only(df)
        self.assertNotIn("boot", detail)
        for part in ("89 days", "40 x 10 = 400"):
            self.assertIn(part, detail["ranges_error"])
        self.assertEqual(detail["dsr"], self.detail["dsr"])  # the Deflated Sharpe does not hang on the ranges
        self.assertEqual(len(detail["daily"].columns), 18)  # the run record keeps every run's days all the same
        self.assertEqual([r["sharpe"] for r in detail["phase_rows"]], [r["sharpe"] for r in self.detail["phase_rows"]])
        text = report.sweep_report(df, detail, self.rec, self.cfg)
        self.assertIn(f"## Ranges: not computed ({detail['ranges_error']})", text)
        self.assertNotIn("stationary block bootstrap", text)
        self.assertIn("## Deflated Sharpe of the base", text)

    def test_a_null_seed_is_refused_never_run_unseeded(self):
        df, detail = self.resweep(seed=None)
        self.legacy_only(df)
        self.assertNotIn("boot", detail)
        self.assertIn("bootstrap.seed", detail["ranges_error"])
        self.assertIn("got None", detail["ranges_error"])
        text = report.sweep_report(df, detail, self.rec, self.cfg)
        self.assertIn(f"## Ranges: not computed ({detail['ranges_error']})", text)
        self.assertNotIn("seed None", text)

    def test_a_failure_building_the_daily_frame_keeps_the_table_and_the_registration(self):
        broken = [{**r, "_bench_daily": None} if "_bench" in r else r for r in self.results]  # the frame cannot be built
        df, detail = self.resweep(broken)
        self.legacy_only(df)
        self.assertEqual(detail["ranges_error"], "AttributeError")  # an unexpected error is named, not explained
        self.assertNotIn("daily", detail)
        self.assertEqual(detail["dsr"]["rule"], self.detail["dsr"]["rule"])
        before = journal.read("trials.jsonl")
        try:
            with mock.patch.object(journal, "now_utc", lambda: "2026-11-10T15:00:00+00:00"):
                rec = backtest.register(df, detail, self.panel, self.cfg, self.start)
            lines = journal.read("trials.jsonl")
            self.assertEqual(len(lines), len(before) + 1)  # the finished sweep is registered: the next N counts it
            self.assertEqual(canon(lines[-1]["rows"]), records(df))
            self.assertNotIn("record", rec)
            text = report.sweep_report(df, detail, rec, self.cfg)
            self.assertIn("## Ranges: not computed (AttributeError)", text)
            self.assertIn("NOT saved", text)
        finally:
            journal.write_all("trials.jsonl", before)

    def test_existing_columns_and_the_registered_dsr_are_unchanged(self):
        self.assertEqual(list(self.df.columns), LEGACY_COLS + RANGE_COLS)  # new numbers are new columns, at the end
        self.assertEqual([[r[c] for c in LEGACY_COLS] for r in records(self.df)], LEGACY)

    def test_every_row_has_a_seeded_range_next_to_its_estimate(self):
        boot = self.detail["boot"]
        self.assertEqual(boot, {**SET, "days": 89, "method": "stationary bootstrap, circular"})  # config, not literals
        for r in records(self.df)[:-1]:
            for k, point in (("sharpe", "sharpe_med"), ("cagr", "cagr_med"), ("maxdd", "maxdd_med")):
                self.assertLess(r[f"{k}_lo"], r[f"{k}_hi"], (r["variant"], k))
                self.assertTrue(r[f"{k}_lo"] <= r[point] <= r[f"{k}_hi"], (r["variant"], k, r))
        self.assertEqual([self.row("DSR of base (N=11 trials)")[c] for c in RANGE_COLS], [None] * 8)
        # the ranges can be recomputed from the daily returns the sweep kept (the ones the run record saves)
        daily = self.detail["daily"]
        self.assertEqual(len(daily.columns), 16 + 2)
        pairs = {v: "base" for v in ("costs 15bps", "daily rebalance", "monthly rebalance")}
        again = metrics.boot_rows(daily, RF_D, 252, SET, pairs, "SPY buy&hold")
        for v in ("base", "monthly rebalance", "SPY buy&hold", "Equal-weight universe"):
            self.assertEqual({c: self.row(v)[c] for c in RANGE_COLS}, again["rows"][v], v)

    def test_paired_probabilities_against_spy_and_the_base(self):
        self.assertIsNone(self.row("base")["p_gt_base"])
        self.assertIsNone(self.row("SPY buy&hold")["p_gt_bench"])
        self.assertIsNone(self.row("Equal-weight universe")["p_gt_base"])
        for v in ("base", "costs 15bps", "daily rebalance", "monthly rebalance", "Equal-weight universe"):
            self.assertTrue(0.0 <= self.row(v)["p_gt_bench"] <= 1.0, v)
        costs, base = self.row("costs 15bps"), self.row("base")
        # paired on the same resampled days, the costlier copy of the same trades is below the base nearly always,
        # although its own range overlaps the base's almost completely
        self.assertLess(costs["p_gt_base"], 0.1)
        self.assertGreater(costs["sharpe_hi"], base["sharpe_lo"])

    def test_phase_rows_carry_their_range_and_same_phase_probability(self):
        ph = self.detail["phase_rows"]
        self.assertEqual(len(ph), 16)
        self.assertEqual(sorted(r["phase"] for r in ph if r["variant"] == "monthly rebalance"), [0, 4, 8, 12, 16])
        for r in ph:
            self.assertTrue(r["sharpe_lo"] <= r["sharpe"] <= r["sharpe_hi"], r)  # the run's own Sharpe, as before
            self.assertEqual(r["p_gt_base"] is None, r["variant"] == "base", r)
        b0 = next(r for r in ph if (r["variant"], r["phase"]) == ("base", 0))
        self.assertEqual({"trades", "cagr", "max_drawdown", "turnover_annual", "psr_vs_0"} - set(b0), set())

    def test_dsr_shows_both_readings_and_the_registered_one_is_the_rule(self):
        d = self.detail["dsr"]
        self.assertEqual((d["n"], d["n_prior_rows"], d["n_sweep"]), (11, 7, 4))
        self.assertEqual(d["rule"]["value"], self.row("DSR of base (N=11 trials)")["psr_med"])  # 0.937, as registered
        self.assertEqual((d["rule"]["rows_in_spread"], d["alt"]["rows_in_spread"]), (4, 3))
        self.assertEqual(d["alt"]["left_out"], ["costs 15bps"])  # a cost-stress row: only its costs differ
        srs = pd.DataFrame(self.detail["phase_rows"]).groupby("variant").sharpe.median() / math.sqrt(252)
        day = self.detail["daily"][("base", 0)] - RF_D
        self.assertEqual(d["rule"]["value"], round(metrics.dsr(day, 11, float(srs.std())), 3))
        self.assertEqual(d["alt"]["value"], round(metrics.dsr(day, 11, float(srs.drop("costs 15bps").std())), 3))
        self.assertAlmostEqual(d["alt"]["spread_annual"], float(srs.drop("costs 15bps").std()) * math.sqrt(252), places=3)
        self.assertNotEqual(d["alt"]["value"], d["rule"]["value"])

    def test_dsr_is_shown_on_every_base_phase_and_phase_0_stays_the_registered_one(self):
        d = self.detail["dsr"]
        srs = pd.DataFrame(self.detail["phase_rows"]).groupby("variant").sharpe.median() / math.sqrt(252)
        want = [round(metrics.dsr(self.detail["daily"][("base", k)] - RF_D, 11, float(srs.std())), 3) for k in range(5)]
        self.assertEqual(d["base_phases"], want)  # the rule's N and spread, read on each phase's own days
        self.assertEqual(d["base_phases"][0], d["rule"]["value"])  # phase 0 is the registered series
        self.assertEqual(self.row("DSR of base (N=11 trials)")["psr_med"], 0.937)  # as registered before this line existed
        self.assertGreater(max(want), min(want))  # the phases do not read the same: that is what the line shows
        self.assertEqual(self.saved["dsr"]["base_phases"], want)  # kept in the run record
        under = report.sweep_report(self.df, self.detail, self.rec, self.cfg).split("| 2. cost-stress rows left out")[1]
        self.assertIn(", ".join(f"phase {k} {x:.3f}" for k, x in enumerate(want)), under)
        self.assertIn(f"min {min(want):.3f} / median {statistics.median(want):.3f} / max {max(want):.3f}", under)
        self.assertIn("Phase 0 is the registered series", under)

    def test_registration_keeps_the_trials_line_and_adds_the_record(self):
        lines = journal.read("trials.jsonl")
        self.assertEqual(len(lines), 2)  # the earlier record and ONE line for this sweep, as before
        line = lines[-1]
        self.assertEqual((line["logged_at"], line["start"]), ("2026-11-10T12:00:00+00:00", self.start))
        self.assertEqual(canon(line["rows"]), records(self.df))
        self.assertEqual(sum(len(t["rows"]) for t in lines if "rows" in t), 7 + len(self.df))  # the next sweep's N
        path = self.tmp / "trial_runs" / f"{line['run_id']}.json.gz"
        self.assertEqual(line["record"], f"trial_runs/{path.name}")
        self.assertEqual(line["record_bytes"], path.stat().st_size)
        self.assertEqual((line["commit"], line["code_dirty"]), ("c0ffee0123", False))
        self.assertEqual(line["panel_sha256"], backtest.panel_hash(self.panel))
        self.assertEqual(canon({k: self.rec[k] for k in line}), canon(line))
        s = self.saved
        self.assertEqual((s["run_id"], s["kind"], s["start"], s["end"], s["commit"]),
                         (line["run_id"], "stock_sweep", self.start, None, "c0ffee0123"))
        self.assertEqual((s["config_sha256"], s["panel"]["sha256"]), (line["config_sha256"], line["panel_sha256"]))
        close = self.panel["close"]
        self.assertEqual((s["panel"]["first"], s["panel"]["last"], s["panel"]["days"], s["panel"]["symbols"]),
                         (str(close.index[0].date()), str(close.index[-1].date()), 420, 12))
        self.assertEqual((s["boot"], s["dsr"]), (self.detail["boot"], self.detail["dsr"]))
        self.assertEqual(canon(s["rows"]), canon(line["rows"]))
        self.assertEqual(canon(s["phase_rows"]), canon(self.detail["phase_rows"]))
        daily = self.detail["daily"]
        self.assertEqual(s["daily"]["days"], [str(d.date()) for d in daily.index])
        self.assertEqual(len(s["daily"]["series"]), 18)
        for (variant, phase), col in daily.items():  # every run's daily returns, exact to the last bit
            self.assertEqual(s["daily"]["series"][f"{variant}|{phase}"], col.tolist(), (variant, phase))

    def test_dashboard_reads_the_registered_sweep_as_before(self):
        tdb.stock_book(self.tmp)  # the page's time-machine table reads the last trials line by column name
        with mock.patch.object(dashboard, "_px", lambda s: tdb.PRICES.get(s)), mock.patch.object(dashboard, "datetime", tdb.FixedNow):
            rows = dashboard.build()
        shown = [[r["variant"], r["sharpe"], r["cagr"], r["maxdd"], r["calmar"], r["wins"]] for r in rows if r["t"] == "bt"]
        self.assertEqual(canon(shown), [[x[0], x[2], x[7], x[8], x[9], x[5]] for x in LEGACY[:-1]])
        self.assertEqual([(r["label"], r["dsr"]) for r in rows if r["t"] == "bt_dsr"], [("DSR of base (N=11 trials)", 0.937)])

    def test_panel_and_config_hashes_move_with_what_they_name(self):
        p = self.panel
        h = backtest.panel_hash(p)
        self.assertEqual(h, backtest.panel_hash({k: v.copy() for k, v in p.items()}))
        self.assertEqual(len(h), 64)
        bumped = p["close"].copy()
        bumped.iloc[200, 3] *= 1.0001  # one revised close
        self.assertNotEqual(backtest.panel_hash({**p, "close": bumped}), h)
        self.assertNotEqual(backtest.panel_hash({**p, "close": p["close"].iloc[1:]}), h)  # a slid window
        self.assertNotEqual(backtest.panel_hash({**p, "close": p["close"].rename(columns={"S03": "S99"})}), h)
        opens = p["open"].copy()
        opens.iloc[200, 3] *= 1.0001
        self.assertEqual(backtest.panel_hash({**p, "open": opens}), h)  # the closes hash, as its name says
        self.assertNotEqual(backtest.panel_hash({**p, "open": opens}, ("open", "close")), backtest.panel_hash(p, ("open", "close")))
        self.assertNotEqual(self.saved["panel"]["inputs_sha256"], h)  # every price field, not only closes
        cfg2 = copy.deepcopy(self.cfg)
        cfg2["costs"]["slippage_bps"] = 6
        self.assertNotEqual(backtest.config_hash(cfg2), backtest.config_hash(self.cfg))
        self.assertEqual(backtest.config_hash(copy.deepcopy(self.cfg)), self.saved["config_sha256"])

    def test_commit_is_unknown_outside_a_repository(self):
        calls, waits = [], []

        def git(cmd, **kw):
            calls.append(cmd)
            waits.append(kw.get("timeout"))
            out = "abc123def\n" if "rev-parse" in cmd else " M aitrader/backtest.py\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        with mock.patch.object(subprocess, "run", git):
            self.assertEqual(backtest.code_commit(), {"commit": "abc123def", "code_dirty": True})
        self.assertEqual(calls[0], ["git", "rev-parse", "HEAD"])
        self.assertEqual(calls[1], ["git", "--no-optional-locks", "status", "--porcelain", "--", "aitrader", "config.json"])
        self.assertTrue(all(w is not None and 0 < w <= 30 for w in waits), waits)  # a git that hangs cannot hang a sweep
        self.assertEqual(waits, [backtest.GIT_TIMEOUT_S] * 2)
        for err in (FileNotFoundError("git"), subprocess.CalledProcessError(128, "git"), subprocess.TimeoutExpired("git", 10),
                    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"), RuntimeError("anything else")):
            with mock.patch.object(subprocess, "run", mock.Mock(side_effect=err)):  # whatever git does, the sweep runs
                self.assertEqual(backtest.code_commit(), {"commit": "unknown", "code_dirty": None}, repr(err))

    def test_run_records_stay_out_of_git(self):
        """About 1.2 MB of gzip per registered sweep: a same-machine working file. The trials line keeps the hashes."""
        ignored = (ROOT / ".gitignore").read_text().split()
        self.assertIn("state/trial_runs/", ignored)
        self.assertIn("state/crypto/trial_runs/", ignored)
        self.assertTrue(self.rec["record"].startswith("trial_runs/"))  # where the stock record is written
        line = journal.read("trials.jsonl")[-1]
        self.assertEqual({"run_id", "panel_sha256", "config_sha256", "commit", "code_dirty"} - set(line), set())

    def test_a_rerun_is_compared_row_by_row(self):
        a = self.saved
        self.assertEqual(backtest.diff_records(a, copy.deepcopy(a)), [])  # the same run again: nothing to report
        b = copy.deepcopy(a)
        b["commit"] = "other"
        b["daily"]["series"]["base|0"][3] += 1e-6  # one day of one run moved
        del b["daily"]["series"]["daily rebalance|0"]
        diff = backtest.diff_records(a, b)
        self.assertIn({"what": "commit", "a": "c0ffee0123", "b": "other"}, diff)
        self.assertIn({"what": "run", "row": "daily rebalance|0", "only_in": "a"}, diff)
        moved = [d for d in diff if d["what"] == "daily"]
        self.assertEqual([(d["row"], d["days_differing"], d["first"]) for d in moved], [("base|0", 1, a["daily"]["days"][3])])
        self.assertAlmostEqual(moved[0]["max_abs_diff"], 1e-6, places=12)
        self.assertEqual(len(diff), 3)

    def test_a_record_that_cannot_be_written_never_costs_the_registration(self):
        before = journal.read("trials.jsonl")
        try:
            with mock.patch.object(backtest, "save_record", mock.Mock(side_effect=OSError("disk full"))), \
                    mock.patch.object(journal, "now_utc", lambda: "2026-11-10T13:00:00+00:00"):
                rec = backtest.register(self.df, self.detail, self.panel, self.cfg, self.start)
            self.assertEqual(rec["record_error"], "OSError")  # said out loud, in the trials line and the report
            self.assertEqual(len(journal.read("trials.jsonl")), len(before) + 1)
            self.assertIn("NOT saved (OSError)", report.sweep_report(self.df, self.detail, rec, self.cfg))
        finally:
            journal.write_all("trials.jsonl", before)

    def test_cli_prints_the_table_then_the_report_registers_once_and_compares(self):
        def swept(panel, cfg, start, end=None, workers=4, detail=None):
            detail.update(self.detail)
            return self.df

        before, out = journal.read("trials.jsonl"), io.StringIO()
        try:
            with mock.patch.object(backtest, "sweep", swept), mock.patch.object(data, "load_config", lambda *a: self.cfg), \
                    mock.patch.object(data, "load_market", lambda cfg, rng="10y", age=6.0: self.panel), \
                    mock.patch.object(journal, "now_utc", lambda: "2026-11-10T14:00:00+00:00"), contextlib.redirect_stdout(out):
                self.assertEqual(main(["backtest", "--start", self.start, "--sweep"]), 0)
            text = out.getvalue()
            self.assertTrue(text.startswith(self.df.to_string(index=False) + "\n"))  # the sweep table first, as before
            self.assertLess(text.index("## Ranges"), text.index("## Deflated Sharpe"))
            lines = journal.read("trials.jsonl")
            self.assertEqual(len(lines), len(before) + 1)
            self.assertIn(f"run {lines[-1]['run_id']}: state/trial_runs/{lines[-1]['run_id']}.json.gz", text)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):  # the re-registered copy of the same sweep, against the first record
                self.assertEqual(main(["backtest", "--compare", self.rec["run_id"], lines[-1]["run_id"]]), 0)
            got = json.loads(out.getvalue())
            self.assertEqual((got["a"], got["b"], got["identical"], got["differences"]),
                             (self.rec["run_id"], lines[-1]["run_id"], True, []))
            self.assertEqual(canon(journal.read("trials.jsonl")), canon(lines))  # comparing writes nothing
        finally:
            journal.write_all("trials.jsonl", before)

    def test_report_prints_ranges_probabilities_both_dsr_readings_and_the_record(self):
        text = report.sweep_report(self.df, self.detail, self.rec, self.cfg)
        base, costs = self.row("base"), self.row("costs 15bps")
        self.assertIn(f"| base | {base['sharpe_med']:.3f} [{base['sharpe_lo']:.3f}, {base['sharpe_hi']:.3f}] |", text)
        self.assertIn(f"{base['maxdd_med']:.4f} [{base['maxdd_lo']:.4f}, {base['maxdd_hi']:.4f}]", text)
        self.assertIn("## Ranges (95% stationary block bootstrap: mean block 10 days, 300 resamples, seed 3; "
                      "89 days / 10 = 8.9 blocks, floor 8)", text)
        self.assertIn("P(Sharpe > SPY)", text)
        self.assertIn(f"| {costs['p_gt_bench']:.3f} | {costs['p_gt_base']:.3f} |", text)
        self.assertIn("probabilities under resampling, not verdicts", text)
        self.assertNotIn("significan", text.lower())  # a probability, never a verdict
        d = self.detail["dsr"]
        self.assertIn(f"| {d['rule']['value']:.3f} |", text)
        self.assertIn(f"| {d['alt']['value']:.3f} |", text)
        self.assertIn("costs 15bps", text.split("Deflated Sharpe")[1])
        self.assertIn("The first reading is the rule", text)
        self.assertIn(f"state/{self.rec['record']}", text)
        self.assertIn(f"{self.rec['record_bytes']:,} bytes", text)
        self.assertIn("c0ffee0123", text)
        self.assertNotIn("DSR of base", text.split("## Deflated Sharpe")[0])  # the DSR row has no range line


class CryptoSweep(tcs.TempState):
    def setUp(self):
        super().setUp()
        tcs.seed_script().seed()  # the sweep refuses to run without the DSR seed

    def sweep(self, **boot) -> dict:
        """The crypto sweep over stand-in runs of 80 days, with `boot` over the config's bootstrap block."""
        with mock.patch.object(crypto_sweep, "_run", tcs.fake_run(tcs.SweepLogic.SHARPES, [])), \
                mock.patch.object(crypto_sweep, "boot_cfg", lambda cfg: {**metrics.boot_cfg(cfg), **boot}), \
                mock.patch.object(backtest, "code_commit", lambda: dict(FAKE_COMMIT)):
            return crypto_sweep.run_sweep(tcs.panel3(60), "2024-01-01", "2024-02-01", None, phases=7, report_path=self.tmp / "r.md")

    def test_crypto_ranges_are_refused_under_the_floor_and_the_sweep_still_decides(self):
        res = self.sweep()  # the config's floor: 40 blocks of the sweep's 30 days = 1,200 days, against 80
        self.assertNotIn("boot", res)
        for part in ("80 days", "40 x 30 = 1200"):
            self.assertIn(part, res["ranges_error"])
        self.assertFalse(any("range" in r for r in res["runs"].values()))
        text = (self.tmp / "r.md").read_text()
        self.assertIn(f"## Ranges: not computed ({res['ranges_error']})", text)
        self.assertNotIn("stationary block bootstrap", text)
        line = tcs.trials(self.tmp)[-1]  # the verdict, the registration and the record do not hang on the ranges
        self.assertEqual((res["ship"], line["ship"], len(line["rows"])), ("crypto", "crypto", 7 * len(res["runs"])))
        self.assertTrue((self.tmp / "crypto" / line["record"]).exists())
        with_ranges = self.sweep(min_blocks=1)  # registered after the first one, so only its N (and DSR) may differ
        self.assertEqual((with_ranges["ship"], with_ranges["pass_rule"]), (res["ship"], res["pass_rule"]))  # no rule reads a range

    def test_crypto_runs_get_ranges_a_report_section_and_a_record(self):
        res = self.sweep(min_blocks=1)
        for name, r in res["runs"].items():
            self.assertLess(r["range"]["sharpe_lo"], r["range"]["sharpe_hi"], name)
            self.assertIsNone(r["range"]["p_gt_bench"], name)  # the stand-in runs carry no benchmark days
            self.assertEqual(r["range"]["p_gt_base"] is None, "pair" not in r, name)
        # the stand-in candidate is its base plus a constant every day; an ablation is a copy of the candidate
        self.assertEqual(res["runs"]["cand@50"]["range"]["p_gt_base"], 1.0)
        self.assertEqual(res["runs"]["abl:no_eth"]["range"]["p_gt_base"], 0.5)
        self.assertEqual(res["runs"]["final:h1"]["range"]["p_gt_base"], 1.0)
        text = (self.tmp / "r.md").read_text()
        self.assertIn("## Ranges (95% stationary block bootstrap: mean block 30 days, 2000 resamples, seed 0; "
                      "shortest run 80 days / 30 = 2.7 blocks, floor 1)", text)
        cand = res["runs"]["cand@50"]
        self.assertIn(f"| cand@50 | {cand['sharpe_med']:.3f} [{cand['range']['sharpe_lo']:.3f}, {cand['range']['sharpe_hi']:.3f}] |", text)
        self.assertNotIn("significan", text.lower())
        recs = tcs.trials(self.tmp)
        self.assertEqual(len(recs), 2)  # the seed and ONE sweep line, as before
        line = recs[1]
        path = self.tmp / "crypto" / "trial_runs" / f"{line['run_id']}.json.gz"
        self.assertEqual((line["record"], line["record_bytes"]), (f"trial_runs/{path.name}", path.stat().st_size))
        self.assertFalse((self.tmp / "trial_runs").exists())  # the crypto book's state dir only
        saved = backtest.load_record(path)
        self.assertEqual((saved["kind"], saved["commit"], canon(saved["rows"])), ("crypto_sweep", "c0ffee0123", canon(line["rows"])))
        self.assertEqual(len(saved["daily"]["series"]), 7 * len(res["runs"]))
        self.assertEqual(len(saved["phase_rows"]), 7 * len(res["runs"]))
        self.assertIn(f"state/crypto/{line['record']}", text)
        self.assertEqual(res["record"]["run_id"], line["run_id"])

    def test_a_real_crypto_run_returns_its_benchmark_days(self):
        p = tcs.panel3()
        start, _, end = tcs.window(p)
        out = crypto_sweep._run("base", data.load_config("crypto", "crypto_base"), p, start, end, 1)
        want = p["close"]["BTC-USD"].loc[start:end].pct_change().dropna()
        pd.testing.assert_series_equal(out["bench_daily"], want, check_names=False)
        self.assertEqual(len(out["bench_daily"]), len(out["daily"]))


NY = ZoneInfo("America/New_York")


def chart(opens: dict, splits: dict | None = None) -> dict:
    """A Yahoo daily chart reply: bars stamped 09:30 New York, raw opens, split events {day: ratio}."""
    def ts(day):
        return int(pd.Timestamp(f"{day} 09:30", tz="America/New_York").timestamp())

    return {"meta": {"exchangeTimezoneName": "America/New_York"}, "timestamp": [ts(d) for d in opens],
            "indicators": {"quote": [{"open": list(opens.values())}]},
            "events": {"splits": {str(ts(d)): {"date": ts(d), "numerator": r, "denominator": 1} for d, r in (splits or {}).items()}}}


def fill(day: str, sym: str, side: str, qty: float, price: float, decided: str | None = "2026-11-06") -> dict:
    """A trades.jsonl row as the cycle writes it: filled on `day` for the decision of `decided` (None: an old row)."""
    row = {"date": day, "symbol": sym, "side": side, "qty": qty, "price": price, "value": round(qty * price, 2)}
    return row if decided is None else {**row, "decision_date": decided}


class Drift(tcs.TempState):
    """Paper versus time machine: every live fill next to the official open the time machine fills at."""

    CHARTS = {"AAA": chart({"2026-11-06": 99.0, "2026-11-09": 100.0}), "BBB": chart({"2026-11-09": 50.0}),
              "CCC": chart({"2026-11-06": 10.0}), "SPL": chart({"2026-11-09": 25.0, "2026-11-10": 26.0}, {"2026-11-10": 4.0}),
              "LATE": chart({"2026-11-06": 40.0, "2026-11-09": 50.0, "2026-11-10": 60.0})}
    AFTER = datetime(2026, 11, 10, 18, 0, tzinfo=NY)  # both sessions closed

    def setUp(self):
        super().setUp()
        self.cfg = cfg_for(synthetic_panel(n_days=5, n_syms=3))
        self.asked, self.slept = [], []
        for target, name, fake in ((data, "_chart", self.yahoo), (backtest.time, "sleep", self.slept.append)):
            patch = mock.patch.object(target, name, fake)
            patch.start()
            self.addCleanup(patch.stop)

    def yahoo(self, sym, rng, interval):
        self.asked.append((sym, rng, interval))
        if sym not in self.CHARTS:
            raise RuntimeError(f"GET failed {sym}")
        return self.CHARTS[sym]

    def test_a_fill_10bp_from_the_open_is_reported_as_10bp(self):
        slip = self.cfg["costs"]["slippage_bps"] / 1e4  # 5 bp, on both sides of the comparison
        trades = [fill("2026-11-09", "AAA", "BUY", 10, round(100.0 * (1 + slip) * 1.001, 4)),  # paid 10 bp over
                  fill("2026-11-09", "BBB", "SELL", 4, round(50.0 * (1 - slip), 4)),  # exactly the time-machine price
                  fill("2026-11-09", "BBB", "SELL", 2, round(50.0 * (1 - slip) * 0.998, 4)),  # received 20 bp less
                  fill("2026-11-09", "CCC", "BUY", 1, 10.0),  # no bar after the decision
                  fill("2026-11-09", "GONE", "BUY", 1, 5.0)]  # Yahoo does not answer for it
        out = backtest.drift(trades, self.cfg, now=self.AFTER)
        r = out["rows"]
        self.assertEqual((r[0]["official_open"], r[0]["tm_fill"], r[0]["drift_bps"], r[0]["drift_usd"]), (100.0, 100.05, 10.0, 1.0))
        self.assertEqual((r[1]["drift_bps"], r[1]["drift_usd"]), (0.0, 0.0))
        self.assertEqual((r[2]["tm_fill"], r[2]["drift_bps"], r[2]["drift_usd"]), (49.975, 20.0, 0.2))  # a worse sale is a cost
        self.assertEqual([x["running_usd"] for x in r], [1.0, 1.0, 1.2, None, None])
        self.assertEqual([x["tm_bar"] for x in r], ["2026-11-09"] * 3 + [None, None])
        self.assertEqual((r[3]["official_open"], r[3]["note"]), (None, "no daily bar after the decision of 2026-11-06"))
        self.assertEqual((r[4]["official_open"], r[4]["note"]), (None, "no data (RuntimeError)"))
        t = out["total"]
        self.assertEqual((t["fills"], t["priced"], t["drift_usd"], t["max_abs_bps"]), (5, 3, 1.2, 20.0))
        notional = 10 * 100.05 + 6 * 49.975
        self.assertEqual(t["notional"], round(notional, 2))
        self.assertAlmostEqual(t["drift_bps"], 1.2 / notional * 1e4, delta=0.02)  # dollars over notional
        # one daily-bar call per symbol over the book's history range, paced (Yahoo throttles a burst)
        self.assertEqual(self.asked, [(s, self.cfg["market"]["history"], "1d") for s in ("AAA", "BBB", "CCC", "GONE")])
        self.assertEqual(self.slept, [backtest.DRIFT_DEFAULTS["pause_seconds"]] * 3)
        self.slept.clear()
        backtest.drift(trades[:2], {**self.cfg, "drift": {"pause_seconds": 0.25}}, now=self.AFTER)
        self.assertEqual(self.slept, [0.25])

    def test_a_fill_is_compared_with_the_open_of_the_first_bar_after_its_decision(self):
        """The time machine fills a decision at the open of the next bar (exec_lag 1), whatever day the paper fill
        landed on: a fill that slipped a session is measured against the open it missed, not the one it got."""
        slip = self.cfg["costs"]["slippage_bps"] / 1e4
        trades = [fill("2026-11-09", "LATE", "BUY", 10, round(50.0 * (1 + slip), 4)),  # on the bar a replay fills on
                  fill("2026-11-10", "LATE", "BUY", 10, round(50.0 * (1 + slip) * 1.2, 4)),  # a session late, at 60
                  fill("2026-11-09", "AAA", "BUY", 1, round(100.0 * (1 + slip), 4), decided=None),  # a row without the date
                  fill("2026-11-10", "AAA", "BUY", 1, 100.0, decided="2026-11-09")]  # no bar after its decision yet
        out = backtest.drift(trades, self.cfg, now=self.AFTER)
        r = out["rows"]
        self.assertEqual([x["official_open"] for x in r], [50.0, 50.0, 100.0, None])
        self.assertEqual([x["tm_bar"] for x in r], ["2026-11-09", "2026-11-09", "2026-11-09", None])
        self.assertEqual((r[0]["drift_bps"], r[0]["note"]), (0.0, ""))
        self.assertEqual((r[1]["tm_fill"], r[1]["drift_bps"], r[1]["drift_usd"]), (50.025, 2000.0, 100.05))
        self.assertEqual(r[1]["note"], "filled 2026-11-10, not on the time-machine bar")
        self.assertEqual((r[2]["drift_bps"], r[2]["note"]), (0.0, "no decision date on the row: the open of its own day is used"))
        self.assertEqual(r[3]["note"], "no daily bar after the decision of 2026-11-09")
        self.assertEqual((out["total"]["priced"], out["total"]["drift_usd"]), (3, 100.05))
        # settled is read on the bar whose open is used: 11-09 closed long before the late fill's own session does
        early = backtest.drift(trades[1:2], self.cfg, now=datetime(2026, 11, 10, 10, 0, tzinfo=NY))
        self.assertEqual((early["total"]["priced"], early["rows"][0]["running_usd"]), (1, 100.05))
        text = report.drift_report(out, self.cfg)
        self.assertIn("| date | symbol | side | qty | paper fill | time-machine bar | its official open | time-machine fill |", text)
        self.assertIn("| 2026-11-10 | LATE | BUY | 10 | 60.0300 | 2026-11-09 | 50.0000 | 50.0250 | +2000.0 | +100.05 | +100.05 | "
                      "filled 2026-11-10, not on the time-machine bar |", text)
        self.assertIn("first daily bar after the fill's decision date", text)

    def test_the_backtest_only_delay_cost_is_on_the_time_machine_side(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["costs"].update({"slippage_bps": 5, "exec_delay_bps": 10})  # the crypto book: the paper fill has 5, the replay 15
        out = backtest.drift([fill("2026-11-09", "AAA", "BUY", 1, round(100.0 * 1.0005, 4))], cfg, now=self.AFTER)
        self.assertEqual((out["rows"][0]["tm_fill"], out["rows"][0]["drift_bps"]), (100.15, -10.0))  # paid less than assumed
        self.assertEqual(out["slippage_bps"], 15)

    def test_a_fill_before_a_split_is_compared_at_the_price_of_its_own_day(self):
        trades = [fill("2026-11-09", "SPL", "BUY", 1, 100.05), fill("2026-11-10", "SPL", "BUY", 4, 26.013, decided="2026-11-09")]
        r = backtest.drift(trades, self.cfg, now=self.AFTER)["rows"]
        self.assertEqual((r[0]["official_open"], r[0]["drift_bps"]), (100.0, 0.0))  # 25.0 after the 4:1 split of 11-10
        self.assertEqual((r[1]["official_open"], r[1]["drift_bps"]), (26.0, 0.0))

    def test_a_stock_open_counts_only_after_its_session_closed(self):
        trades = [fill("2026-11-09", "AAA", "BUY", 10, 100.15)]
        early = backtest.drift(trades, self.cfg, now=datetime(2026, 11, 9, 10, 0, tzinfo=NY))
        self.assertIsNone(early["rows"][0]["running_usd"])
        self.assertIn("not settled", early["rows"][0]["note"])
        self.assertEqual((early["rows"][0]["drift_bps"], early["total"]["priced"], early["total"]["drift_usd"]), (10.0, 0, 0.0))
        closed = backtest.drift(trades, self.cfg, now=datetime(2026, 11, 9, 16, 0, tzinfo=NY))
        self.assertEqual((closed["rows"][0]["running_usd"], closed["total"]["priced"]), (1.0, 1))
        utc = copy.deepcopy(self.cfg)
        utc["market"]["calendar"] = "utc_daily"  # a coin's daily open is its first print of the UTC day
        self.assertEqual(backtest.drift(trades, utc, now=datetime(2026, 11, 9, 10, 0, tzinfo=NY))["total"]["priced"], 1)

    def test_report_lists_every_fill_with_a_running_total(self):
        trades = [fill("2026-11-09", "AAA", "BUY", 10, 100.15), fill("2026-11-09", "BBB", "SELL", 2, 49.875),
                  fill("2026-11-09", "CCC", "BUY", 1, 10.0)]
        text = report.drift_report(backtest.drift(trades, self.cfg, now=self.AFTER), self.cfg)
        self.assertIn("| 2026-11-09 | AAA | BUY | 10 | 100.1500 | 2026-11-09 | 100.0000 | 100.0500 | +10.0 | +1.00 | +1.00 |", text)
        self.assertIn("| 2026-11-09 | BBB | SELL | 2 | 49.8750 | 2026-11-09 | 50.0000 | 49.9750 | +20.0 | +0.20 | +1.20 |", text)
        self.assertIn("| 2026-11-09 | CCC | BUY | 1 | 10.0000 | - | - | - | - | - | - | no daily bar after the decision of 2026-11-06", text)
        self.assertIn("Total: 2 of 3 fills priced", text)
        self.assertIn("+1.20", text.split("Total:")[1])
        self.assertIn("5 bp", text)  # the cost the time machine adds to the open: from the config
        self.assertIn("(no fills)", report.drift_report(backtest.drift([], self.cfg, now=self.AFTER), self.cfg))

    def test_cli_drift_is_read_only(self):
        for t in [fill("2026-11-09", "AAA", "BUY", 10, 100.15), fill("2026-11-09", "BBB", "SELL", 2, 49.875)]:
            journal.append("trades.jsonl", t)
        before = {f.name: f.read_bytes() for f in self.tmp.rglob("*") if f.is_file()}
        out = io.StringIO()
        with mock.patch.object(data, "load_config", lambda *a: self.cfg), contextlib.redirect_stdout(out):
            self.assertEqual(main(["backtest", "--drift"]), 0)
        self.assertIn("| 2026-11-09 | AAA | BUY | 10 |", out.getvalue())
        self.assertIn("Total: ", out.getvalue())
        self.assertEqual({f.name: f.read_bytes() for f in self.tmp.rglob("*") if f.is_file()}, before)  # nothing written


if __name__ == "__main__":
    unittest.main()
