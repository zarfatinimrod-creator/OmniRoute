"""Regression tests for the independent audit of the first open (2026-11-09).

1. Non-quant calls (desk / overlay / Claude) are graded from the first price that was knowable when the call
   was logged: a call logged before the open is graded from that session's close, not from the logged
   (previous) close, even when the call carries an earlier decision date.
2. A broken hash chain stops the live cycle (fail closed) and makes `verify` exit non-zero.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from aitrader import cycle, journal

ROOT = Path(__file__).resolve().parent.parent


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state


def _panel():
    idx = pd.bdate_range("2026-11-02", periods=40)  # November: New York is UTC-5
    close = pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)
    return idx, close


class PreOpenCallGradedFromSessionClose(TempState):
    def test_overlay_logged_before_open_earns_nothing_for_the_gap(self):
        idx, close = _panel()
        d_prev, d_log = idx[4], idx[5]  # decision dated Friday, call logged Monday 06:37 New York
        close.loc[d_log:, "AAA"] = 110.0  # Monday's open gap, after the filing became public
        journal.append("predictions.jsonl", {
            "date": str(d_prev.date()), "logged_at": f"{d_log.date()}T11:37:39+00:00", "symbol": "AAA", "horizon": 5,
            "source": "insider_cluster", "direction": "up", "price": 100.0, "bench_price": 100.0, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["excess"], 0.0)  # entry = Monday's close (110), not Friday's (100)

    def test_desk_call_logged_after_close_with_a_price_waits_for_next_session(self):
        idx, close = _panel()
        d = idx[5]
        close.loc[idx[6]:, "AAA"] = 110.0  # overnight jump
        journal.append("predictions.jsonl", {
            "date": str(d.date()), "logged_at": f"{d.date()}T22:00:00+00:00", "symbol": "AAA", "horizon": 5,
            "source": "desk", "direction": "up", "price": 100.0, "bench_price": 100.0, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["excess"], 0.0)

    def test_call_logged_in_session_uses_logged_price_and_counts_from_log_day(self):
        idx, close = _panel()
        d_prev, d_log = idx[4], idx[5]
        close.loc[idx[5 + 5]:, "AAA"] = 121.0  # move lands exactly 5 sessions after the log day
        journal.append("predictions.jsonl", {
            "date": str(d_prev.date()), "logged_at": f"{d_log.date()}T16:00:00+00:00", "symbol": "AAA", "horizon": 5,
            "source": "claude", "direction": "up", "price": 110.0, "bench_price": 100.0, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        self.assertAlmostEqual(g[0]["excess"], 0.10)  # 110 -> 121, horizon counted from the log day

    def test_quant_calls_still_graded_from_decision_close(self):
        idx, close = _panel()
        d = idx[5]
        close.loc[idx[6]:, "AAA"] = 110.0
        journal.append("predictions.jsonl", {
            "date": str(d.date()), "logged_at": f"{idx[6].date()}T11:00:00+00:00", "symbol": "AAA", "horizon": 5,
            "source": "quant", "direction": "up", "price": 100.0, "bench_price": 100.0, "status": "open"})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertAlmostEqual(g[0]["excess"], 0.10)


class BrokenChainFailsClosed(TempState):
    def _break_trades(self):
        journal.append("trades.jsonl", {"symbol": "AAA", "qty": 1})
        journal.append("trades.jsonl", {"symbol": "BBB", "qty": 2})
        p = self.tmp / "trades.jsonl"
        lines = p.read_text().splitlines()
        rec = json.loads(lines[0])
        rec["qty"] = 999  # tamper with history
        p.write_text("\n".join([json.dumps(rec)] + lines[1:]) + "\n")

    def test_chains_ok_reports_broken_files(self):
        self.assertEqual(journal.broken_chains(), [])
        self._break_trades()
        self.assertEqual(journal.broken_chains(), ["trades.jsonl"])

    def test_cycle_halts_without_trading(self):
        self._break_trades()
        _load = cycle.load_market
        cycle.load_market = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not load or trade"))
        try:
            out = cycle.run_cycle()
        finally:
            cycle.load_market = _load
        self.assertIn("trades.jsonl", out["halted"])
        self.assertEqual(out["executed"], [])

    def test_verify_exits_nonzero(self):
        self._break_trades()
        code = ("import sys; from pathlib import Path; from aitrader import journal; "
                f"journal.STATE = Path({str(self.tmp)!r}); sys.argv = ['aitrader', 'verify']; "
                "import runpy; runpy.run_module('aitrader', run_name='__main__')")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("BROKEN", r.stdout)


if __name__ == "__main__":
    unittest.main()
