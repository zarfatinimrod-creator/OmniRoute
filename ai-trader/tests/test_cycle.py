"""Live-cycle timing and idempotency on synthetic data (no network)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from aitrader import cycle, journal
from test_core import cfg_for, synthetic_panel


class CycleFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state, self._root = journal.STATE, cycle.ROOT
        journal.STATE = self.tmp
        self.full = synthetic_panel(n_days=520)
        self.cfg = cfg_for(self.full)
        self.cfg["risk"]["min_score"] = -1.0  # make sure something gets bought on synthetic data
        self.patches = {
            "load_config": cycle.load_config, "load_market": cycle.load_market, "market_status": cycle.market_status,
            "earnings_on": cycle.earnings_on, "_overlays_once_per_day": cycle._overlays_once_per_day,
            "_market_opened": cycle._market_opened, "_bar_is_final": cycle._bar_is_final,
            "official_opens": cycle.official_opens,
        }
        self._send = cycle.notify.send
        cycle.notify.send = lambda *a, **k: []  # a test run must never reach the owner's phone
        cycle.official_opens = lambda syms, day: {}  # no network in tests; daily open is the fallback
        cycle.load_config = lambda: self.cfg
        cycle.market_status = lambda sym="SPY": {"is_open": False}
        cycle.earnings_on = lambda day: {}
        cycle._overlays_once_per_day = lambda cfg, ds, bench: {}
        cycle._market_opened = lambda d: True
        cycle._bar_is_final = lambda d: True
        import aitrader.report as rep

        self._rep_root = rep.ROOT
        rep.ROOT = self.tmp

    def tearDown(self):
        for k, v in self.patches.items():
            setattr(cycle, k, v)
        cycle.notify.send = self._send
        journal.STATE = self._state
        import aitrader.report as rep

        rep.ROOT = self._rep_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upto(self, n):
        p = {k: v.iloc[:n] for k, v in self.full.items()}
        cycle.load_market = lambda cfg, rng="10y", age=0.1: p
        return p

    def test_decide_then_fill_at_next_open_and_idempotent(self):
        p = self._upto(400)
        out1 = cycle.run_cycle()
        self.assertTrue(out1["decided_now"])
        self.assertEqual(out1["executed"], [])  # no later bar yet
        pend = journal.load_json("pending.json")
        self.assertEqual(pend["decision_date"], str(p["close"].index[-1].date()))
        n_dec = len(journal.read("decisions.jsonl"))

        out2 = cycle.run_cycle()  # same day again: nothing new
        self.assertFalse(out2["decided_now"])
        self.assertEqual(len(journal.read("decisions.jsonl")), n_dec)
        self.assertEqual(out2["executed"], [])

        p2 = self._upto(401)  # next session's bar appears
        out3 = cycle.run_cycle()
        self.assertTrue(out3["executed"], "pending orders must fill at the next open")
        d_exec = p2["close"].index[-1]
        slip = self.cfg["costs"]["slippage_bps"] / 1e4
        for f in out3["executed"]:
            self.assertEqual(f["date"], str(d_exec.date()))
            open_px = p2["open"].at[d_exec, f["symbol"]]
            expect = open_px * (1 + slip) if f["side"] == "BUY" else open_px * (1 - slip)
            self.assertAlmostEqual(f["price"], round(expect, 4), places=3)
        trades = len(journal.read("trades.jsonl"))
        out4 = cycle.run_cycle()  # re-run after execution: no double fill
        self.assertEqual(out4["executed"], [])
        self.assertEqual(len(journal.read("trades.jsonl")), trades)
        self.assertEqual(journal.verify_chain("trades.jsonl")[0], True)
        self.assertEqual(journal.verify_chain("decisions.jsonl")[0], True)

    def test_one_minute_open_beats_daily_open(self):
        self._upto(400)
        cycle.run_cycle()
        p2 = self._upto(401)
        name = list(journal.load_json("pending.json")["targets"])[0]
        cycle.official_opens = lambda syms, day: {name: 123.45}
        out = cycle.run_cycle()
        f = [x for x in out["executed"] if x["symbol"] == name][0]
        self.assertAlmostEqual(f["price"], round(123.45 * (1 + self.cfg["costs"]["slippage_bps"] / 1e4), 4), places=3)
        del p2

    def test_production_shaped_panel_does_not_crash(self):
        # load_market adds non-frame keys (_require_vix flag, vix Series): decide() must slice only frames/series
        p = self._upto(400)
        p["_require_vix"] = True
        p["vix"] = p["close"]["S00"] * 0 + 18.0
        out = cycle.run_cycle()
        self.assertTrue(out["decided_now"])
        prop = cycle.run_cycle(propose=True)
        self.assertIn("decision_date", prop)

    def test_propose_changes_no_state(self):
        self._upto(400)
        before = sorted(x.name for x in self.tmp.iterdir())
        prop = cycle.run_cycle(propose=True)
        self.assertIn("new_entries", prop)
        after = sorted(x.name for x in self.tmp.iterdir())
        self.assertEqual(set(after) - set(before), {"proposal.json", "earnings.json"})

    def test_overrides_only_reduce(self):
        p = self._upto(400)
        prop = cycle.run_cycle(propose=True)
        ds = prop["decision_date"]
        names = list(prop["targets"])
        self.assertTrue(names)
        journal.save_json("overrides.json", {"date": ds, "vetoes": {names[0]: "test"}, "size_mult": {names[1]: [5.0, "try to enlarge"]}})
        cycle.run_cycle()
        pend = journal.load_json("pending.json")
        self.assertNotIn(names[0], pend["targets"])
        self.assertLessEqual(pend["targets"][names[1]], prop["targets"][names[1]] + 1e-12)
        del p


if __name__ == "__main__":
    unittest.main()
