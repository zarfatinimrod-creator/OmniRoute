"""The time machine tells the truth about its own uncertainty (2026-11-10).

- Every sweep row carries a seeded block-bootstrap range for Sharpe (excess of cash), CAGR and max drawdown.
- Every row carries the paired bootstrap probability that its Sharpe is above the benchmark's and above the base's.
- Every registered sweep leaves a run record beside trials.jsonl (daily returns per run, per-phase rows, panel hash,
  code commit, config hash) that a later re-run can be compared with row by row.
- The Deflated Sharpe is printed in both readings, and the registered one stays the rule.
None of it may move an existing number: the legacy columns below were recorded from the code before this change.

Synthetic panels and a temp state dir: never the network, never the phone, never a subprocess, never the real state.
"""

import contextlib
import copy
import io
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import requests

import test_crypto_sweep as tcs  # a module, not its TestCase classes: importing those would run them twice
from aitrader import backtest, crypto_sweep, data, journal, metrics, news_live, notify, report
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
SET = {"block_days": 10, "draws": 300, "seed": 3, "level": 0.95}
RANGE_COLS = ["sharpe_lo", "sharpe_hi", "cagr_lo", "cagr_hi", "maxdd_lo", "maxdd_hi", "p_gt_bench", "p_gt_base"]
FAKE_COMMIT = {"commit": "c0ffee0123", "code_dirty": False}


def series(seed: int, n: int = 600, mu: float = 0.0005, sd: float = 0.01) -> pd.Series:
    return pd.Series(np.random.default_rng(seed).normal(mu, sd, n), index=pd.bdate_range("2020-01-01", periods=n))


class Bootstrap(unittest.TestCase):
    def test_settings_come_from_config_over_defaults(self):
        self.assertEqual(set(metrics.BOOT_DEFAULTS), {"block_days", "draws", "seed", "level"})
        self.assertEqual(metrics.boot_cfg({}), metrics.BOOT_DEFAULTS)
        self.assertEqual(metrics.boot_cfg({"bootstrap": {"draws": 50}}), {**metrics.BOOT_DEFAULTS, "draws": 50})

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
        journal.append("trials.jsonl", {"logged_at": "x", "start": "s", "rows": [{"variant": "old"}] * 7})  # earlier looks
        cls.panel, cls.cfg = small_book()
        cls.cfg["bootstrap"] = SET
        cls.start = str(cls.panel["close"].index[330].date())
        cls.detail = {}
        with mock.patch.object(backtest, "_variants", few_variants), mock.patch.object(backtest, "code_commit", lambda: dict(FAKE_COMMIT)):
            cls.df = backtest.sweep(cls.panel, cls.cfg, cls.start, detail=cls.detail)
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
        calls = []

        def git(cmd, **kw):
            calls.append(cmd)
            out = "abc123def\n" if "rev-parse" in cmd else " M aitrader/backtest.py\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        with mock.patch.object(subprocess, "run", git):
            self.assertEqual(backtest.code_commit(), {"commit": "abc123def", "code_dirty": True})
        self.assertEqual([c[:3] for c in calls], [["git", "rev-parse", "HEAD"], ["git", "status", "--porcelain"]])
        for err in (FileNotFoundError("git"), subprocess.CalledProcessError(128, "git")):
            with mock.patch.object(subprocess, "run", mock.Mock(side_effect=err)):
                self.assertEqual(backtest.code_commit(), {"commit": "unknown", "code_dirty": None})

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
        self.assertIn("95% stationary block bootstrap: mean block 10 days, 300 resamples, seed 3, 89 days", text)
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

    def test_crypto_runs_get_ranges_a_report_section_and_a_record(self):
        with mock.patch.object(crypto_sweep, "_run", tcs.fake_run(tcs.SweepLogic.SHARPES, [])), \
                mock.patch.object(backtest, "code_commit", lambda: dict(FAKE_COMMIT)):
            res = crypto_sweep.run_sweep(tcs.panel3(60), "2024-01-01", "2024-02-01", None, phases=7, report_path=self.tmp / "r.md")
        for name, r in res["runs"].items():
            self.assertLess(r["range"]["sharpe_lo"], r["range"]["sharpe_hi"], name)
            self.assertIsNone(r["range"]["p_gt_bench"], name)  # the stand-in runs carry no benchmark days
            self.assertEqual(r["range"]["p_gt_base"] is None, "pair" not in r, name)
        # the stand-in candidate is its base plus a constant every day; an ablation is a copy of the candidate
        self.assertEqual(res["runs"]["cand@50"]["range"]["p_gt_base"], 1.0)
        self.assertEqual(res["runs"]["abl:no_eth"]["range"]["p_gt_base"], 0.5)
        self.assertEqual(res["runs"]["final:h1"]["range"]["p_gt_base"], 1.0)
        text = (self.tmp / "r.md").read_text()
        self.assertIn("## Ranges (95% stationary block bootstrap: mean block 30 days, 2000 resamples, seed 0)", text)
        rng = res["runs"]["cand@50"]["range"]
        self.assertIn(f"| cand@50 | {res['runs']['cand@50']['sharpe_med']:.3f} [{rng['sharpe_lo']:.3f}, {rng['sharpe_hi']:.3f}] |", text)
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


if __name__ == "__main__":
    unittest.main()
