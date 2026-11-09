"""Golden outputs of the stock book, recorded before the crypto refactor.
Regenerate (only on purpose): GOLDEN_WRITE=1 python3 -m unittest tests.test_golden_stock"""

import json
import os
import pickle
import unittest

from aitrader import backtest
from golden_util import FIXTURES, load_panel, run_scripted_cycle
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


if __name__ == "__main__":
    unittest.main()
