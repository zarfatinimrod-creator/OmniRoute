import json
import unittest

from aitrader.broker import PaperBroker

BTC = 74914.59
TOL = 1e-6  # cash tolerance asserted (dollars); fills are rounded to cents separately


def go(b, targets, prices, date="2026-01-02", **kw):
    return b.rebalance(targets, prices, date, band=0.0, min_trade_value=0, **kw)


class TestBrokerCrypto(unittest.TestCase):
    def test_int_step_keeps_ints(self):
        b = PaperBroker(10000, slippage_bps=10)
        f = go(b, {"AAA": 0.5}, {"AAA": 100.0})
        self.assertIsInstance(f[0]["qty"], int)
        self.assertIsInstance(b.positions["AAA"]["qty"], int)
        json.dumps(b.state)

    def test_fractional_qty_never_negative_cash(self):
        # fee 0 and slippage 0: the literal 6 dp quantity (R2)
        b = PaperBroker(100000, slippage_bps=0, qty_step=1e-6, fee_bps=0)
        f = go(b, {"BTC": 0.10}, {"BTC": BTC})
        self.assertEqual(f[0]["qty"], int(10000 / BTC * 1e6) / 1e6)  # 0.133485: 10000/74914.59 = 0.1334853
        self.assertEqual(f[0]["qty"], 0.133485)
        self.assertGreaterEqual(b.cash, -TOL)
        # with profile costs: expected qty from the formula, cash still >= 0
        b = PaperBroker(100000, slippage_bps=5, qty_step=1e-6, fee_bps=50)
        f = go(b, {"BTC": 0.10}, {"BTC": BTC})
        unit = BTC * 1.0005 * 1.005
        self.assertAlmostEqual(f[0]["qty"], int(10000 / unit * 1e6) / 1e6, places=8)
        self.assertGreaterEqual(b.cash, -TOL)
        # all-in target cannot overspend cash
        b = PaperBroker(100000, slippage_bps=5, qty_step=1e-6, fee_bps=50)
        go(b, {"BTC": 1.0}, {"BTC": BTC})
        self.assertGreaterEqual(b.cash, -TOL)

    def test_fee_charged_to_cash_and_pnl(self):
        b = PaperBroker(100000, slippage_bps=0, qty_step=1e-6, fee_bps=50)
        buy = go(b, {"BTC": 0.5}, {"BTC": 100.0})[0]
        self.assertAlmostEqual(buy["realized_pnl"], -buy["fee"], delta=0.01)
        self.assertAlmostEqual(b.positions["BTC"]["avg_cost"], 100.0)
        sell = go(b, {}, {"BTC": 110.0}, "2026-01-03")[0]
        gross = (110.0 - 100.0) * sell["qty"]
        self.assertAlmostEqual(sell["realized_pnl"], gross - sell["fee"], delta=0.01)
        self.assertAlmostEqual(b.state["fees_paid"], buy["fee"] + sell["fee"], delta=1e-3)
        self.assertAlmostEqual(b.cash, 100000 + gross - b.state["fees_paid"], delta=TOL)
        self.assertNotIn("BTC", b.positions)

    def test_dust_removed(self):
        b = PaperBroker(1000, slippage_bps=0, qty_step=1e-6)
        b.positions["X"] = {"qty": 1.0000005, "avg_cost": 10.0, "entry_date": "d", "peak_close": 10.0, "last_price": 10.0}
        b._fill("X", -1.0, 10.0, "d")
        self.assertNotIn("X", b.positions)

    def test_no_fee_keys_for_stocks(self):
        b = PaperBroker(10000, slippage_bps=5)
        f = go(b, {"AAA": 0.5}, {"AAA": 100.0})
        go(b, {}, {"AAA": 110.0}, "2026-01-03")
        self.assertNotIn("fee", f[0])
        self.assertNotIn("fees_paid", b.state)

    def test_reentry_after_catastrophe(self):
        def reset(**kw):
            b = PaperBroker(10000)
            b.state["dd_state"] = "flat"
            self.assertTrue(b.maybe_reset_peak("risk_on", "d", 1, **kw))
            return b.cash / b.state["peak_equity"] - 1
        self.assertAlmostEqual(reset(dd_halve=-1.0, dd_flat=-0.5, reentry_ref=-0.25), -0.25)
        self.assertGreater(-0.25, -0.5)
        self.assertAlmostEqual(reset(dd_halve=-0.25, dd_flat=-0.5), -0.375)
        self.assertAlmostEqual(reset(dd_halve=-1.0, dd_flat=-0.5), -0.25)  # halve <= flat: flat/2
        self.assertAlmostEqual(reset(dd_halve=-0.10, dd_flat=-0.20), -0.15)  # stock numbers unchanged

    def test_frozen_symbol_not_traded(self):
        b = PaperBroker(10000, slippage_bps=0)
        go(b, {"A": 0.5}, {"A": 100.0, "B": 100.0})
        f = go(b, {"B": 0.5}, {"A": 100.0, "B": 100.0}, "2026-01-03", frozen={"A", "B"})
        self.assertEqual(f, [])
        self.assertEqual(b.positions["A"]["qty"], 50)
        f = go(b, {"B": 0.5}, {"A": 100.0, "B": 100.0}, "2026-01-03", frozen={"A"})
        self.assertEqual([x["symbol"] for x in f], ["B"])
        self.assertEqual(b.positions["A"]["qty"], 50)


if __name__ == "__main__":
    unittest.main()
