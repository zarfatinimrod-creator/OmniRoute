"""Golden outputs of the stock book, recorded before the crypto refactor.
Regenerate (only on purpose, from ai-trader/): GOLDEN_WRITE=1 python3 -m unittest discover -s tests -p test_golden_stock.py"""

import json
import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aitrader import backtest
from aitrader import report as rep
from aitrader import cycle
from golden_util import FIRST_BAR, FIXTURES, frozen_env, load_panel, run_scripted_cycle
from test_core import cfg_for, synthetic_panel

WRITE = os.environ.get("GOLDEN_WRITE") == "1"
BACKTEST_JSON = FIXTURES / "golden_stock_backtest.json"
CYCLE_DIR = FIXTURES / "golden_stock_cycle"
BACKTEST_START_BAR = 300
CYCLE_DAYS = 6


class GoldenStock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if WRITE:
            FIXTURES.mkdir(exist_ok=True)
            (FIXTURES / "stock_panel.pkl").write_bytes(pickle.dumps(synthetic_panel(n_days=520, seed=0)))
        cls.panel = load_panel()

    def test_backtest_equity_matches(self):
        p = self.panel
        res = backtest.run(p, cfg_for(p), start=str(p["close"].index[BACKTEST_START_BAR].date()), weights_mode="prior")
        eq = [round(float(x), 10) for x in res["_equity"]]
        self.assertGreater(len(eq), 100)
        if WRITE:
            BACKTEST_JSON.write_text(json.dumps(eq))
        self.assertEqual(eq, json.loads(BACKTEST_JSON.read_text()))

    def test_scripted_cycle_state_matches(self):
        got = run_scripted_cycle(CYCLE_DAYS)
        self.assertIn("trades.jsonl", got)
        if WRITE:
            CYCLE_DIR.mkdir(exist_ok=True)
            for old in CYCLE_DIR.iterdir():
                old.unlink()
            for name, data in got.items():
                (CYCLE_DIR / name).write_bytes(data)
        want = {f.name: f.read_bytes() for f in sorted(CYCLE_DIR.iterdir())}
        self.assertEqual(sorted(got), sorted(want))
        for name in want:
            self.assertEqual(got[name], want[name], name)


class DividendPeakInTheCycle(unittest.TestCase):
    """Backlog 85 end to end: run_cycle hands the panel's closes to the broker, so a dividend on a held name scales
    the saved peak_close by the feed's factor. Without the closes the peak is left where it was."""

    SYM, DIV = "S12", 1.0  # held from the first fill; its close falls on the next bars, so no new high hides the peak

    def test_run_cycle_scales_the_saved_peak_on_a_dividend(self):
        full = load_panel()
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        idx = full["close"].index
        ex_bar = FIRST_BAR + 1  # the newest bar of the third cycle
        ex_date = str(idx[ex_bar].date())

        def run(n):
            cycle.load_market = lambda c, rng="10y", age=0.1: {k: v.iloc[:n] for k, v in full.items()}
            cycle.run_cycle()

        def acts(sym):
            return {"splits": [], "dividends": [{"date": ex_date, "amount": self.DIV}] if sym == self.SYM else []}

        with tempfile.TemporaryDirectory() as tmp, frozen_env(tmp, None):
            cycle.load_config = lambda: cfg
            book = lambda: json.loads(Path(tmp, "portfolio.json").read_text())  # noqa: E731
            run(FIRST_BAR)  # decide
            run(FIRST_BAR + 1)  # fill
            before = book()
            pos = before["positions"][self.SYM]
            cycle.corporate_actions = acts
            run(FIRST_BAR + 2)
            after = book()
        adj = float(full["close"][self.SYM].iloc[ex_bar - 1])  # the feed's close of the bar before the ex-date
        want = pos["peak_close"] * adj / (adj + self.DIV)
        got = after["positions"][self.SYM]
        self.assertGreater(want, float(full["close"][self.SYM].iloc[ex_bar]))  # the mark does not set a new high
        self.assertLess(want, pos["peak_close"] - 0.5)
        self.assertAlmostEqual(got["peak_close"], want, places=9)
        self.assertEqual(got["avg_cost"], pos["avg_cost"])
        self.assertEqual(got["ca_applied_through"], ex_date)
        self.assertAlmostEqual(after["cash"] - before["cash"], pos["qty"] * self.DIV * 0.75, delta=1.0)  # + a day's cash yield


class TempDirs(unittest.TestCase):
    """The helpers every cycle test runs on remove what they make (backlog 31): on 2026-11-10 one suite run left 90
    directories in the temp dir, all from these two."""

    def test_the_helpers_leave_no_temp_dir_behind(self):
        with tempfile.TemporaryDirectory() as box, mock.patch.object(tempfile, "tempdir", box):
            self.assertIn("trades.jsonl", run_scripted_cycle(2))  # a decision and a fill: state and reports were written
            self.assertEqual(os.listdir(box), [])
            mine = Path(box, "reports")
            with frozen_env(Path(box, "state"), None):
                rep.ROOT = mine  # as test_crypto_cycle does; its tests read their reports after the block
                (mine / "x").mkdir(parents=True)
            self.assertEqual(sorted(p.name for p in Path(box).rglob("*")), ["reports", "x"])  # the caller's dir is the caller's


if __name__ == "__main__":
    unittest.main()
