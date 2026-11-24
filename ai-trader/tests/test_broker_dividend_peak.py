"""Backlog 85: the trailing-stop peak must follow the feed's dividend back-adjustment.

The price panel is back-adjusted on every ex-date (each close before it is multiplied by 1 - dividend / raw close
before the ex-date), so a peak_close recorded before the ex-date is in the old price basis and the live stop sat
about one dividend too high. XOM, 2026-11: peak 170.59, $1.07 on 2026-11-16, adjusted series peak 169.52."""

import copy
import json
import math
import unittest

from aitrader.broker import PaperBroker

ATR, MULT, CLOSE_1123 = 4.424, 3, 156.90
XOM_ACTS = {"XOM": {"splits": [], "dividends": [{"date": "2026-11-16", "amount": 1.07}]}}
# the feed as it looks after the ex-date: 11-13 is already adjusted (raw 170.59 - 1.07)
XOM_CLOSES = {"XOM": {"2026-11-12": 168.72, "2026-11-13": 169.52, "2026-11-16": 166.87}}


def xom(peak=170.59):
    b = PaperBroker(10000, slippage_bps=0)
    b.rebalance({"XOM": 0.16}, {"XOM": 160.0}, "2026-11-09", band=0.0, min_trade_value=0)
    b.positions["XOM"]["peak_close"] = peak
    b.positions["XOM"]["last_price"] = peak
    return b


def stopped(b):
    return CLOSE_1123 < b.positions["XOM"]["peak_close"] - MULT * ATR  # strategy.build_targets, the stop line


class DividendPeak(unittest.TestCase):
    def test_unadjusted_peak_is_the_defect(self):
        self.assertTrue(stopped(xom()))  # 170.59 - 13.27 = 157.32 > 156.90

    def test_xom_peak_follows_the_feed_and_the_stop_does_not_fire(self):
        b = xom()
        cost, cash0 = b.positions["XOM"]["avg_cost"], b.cash
        notes = b.apply_corporate_actions(XOM_ACTS, "2026-11-16", closes=XOM_CLOSES)
        p = b.positions["XOM"]
        self.assertAlmostEqual(p["peak_close"], 169.52, delta=0.02)
        self.assertFalse(stopped(b))  # 169.52 - 13.27 = 156.25 < 156.90
        self.assertEqual(p["avg_cost"], cost)  # cost basis untouched: the dividend is already credited as cash
        self.assertEqual(p["last_price"], 170.59)  # the next mark overwrites it
        self.assertAlmostEqual(b.cash - cash0, p["qty"] * 1.07 * 0.75)
        self.assertIn("peak_close 170.59 -> 169.52", notes[0])

    def test_applying_twice_changes_nothing(self):
        b = xom()
        b.apply_corporate_actions(XOM_ACTS, "2026-11-16", closes=XOM_CLOSES)
        once = copy.deepcopy(b.state)
        self.assertEqual(b.apply_corporate_actions(XOM_ACTS, "2026-11-16", closes=XOM_CLOSES), [])
        self.assertEqual(b.apply_corporate_actions(XOM_ACTS, "2026-11-23", closes=XOM_CLOSES), [])
        once["positions"]["XOM"]["ca_applied_through"] = "2026-11-23"
        self.assertEqual(b.state, once)

    def test_no_price_leaves_the_peak_and_says_so(self):
        for closes in (None, {}, {"XOM": {}}, {"XOM": {"2026-11-16": 166.87}}, {"XOM": {"2026-11-13": float("nan")}},
                       {"XOM": {"2026-11-13": 0.0}}):
            b = xom()
            cash0 = b.cash
            notes = b.apply_corporate_actions(XOM_ACTS, "2026-11-16", closes=closes)
            self.assertEqual(b.positions["XOM"]["peak_close"], 170.59, closes)
            self.assertGreater(b.cash, cash0)  # the cash is still credited
            self.assertIn("peak_close unchanged", notes[0])

    def test_two_dividends_in_one_run_compound_like_the_feed(self):
        # raw closes 100 (before a $1 ex-date on d3) and 99 (before a $2 ex-date on d5). The feed now shows
        # d2 = 100 * (1 - 1/100) * (1 - 2/99) = 97.0 and d4 = 99 - 2 = 97.0; a raw peak of 100 becomes 97.0.
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-01-01", band=0.0, min_trade_value=0)
        acts = {"AAA": {"splits": [], "dividends": [{"date": "2026-01-03", "amount": 1.0}, {"date": "2026-01-05", "amount": 2.0}]}}
        b.apply_corporate_actions(acts, "2026-01-06", closes={"AAA": {"2026-01-02": 97.0, "2026-01-04": 97.0}})
        self.assertAlmostEqual(b.positions["AAA"]["peak_close"], 97.0)

    def test_a_close_that_is_not_finite_never_makes_the_peak_nan(self):
        # inf / (inf + d) is nan, and 'px < nan - 3 * atr' is False for ever: the stop would never fire again
        for bad in (float("inf"), float("nan"), float("-inf")):
            b = xom()
            cash0 = b.cash
            notes = b.apply_corporate_actions(XOM_ACTS, "2026-11-16", closes={"XOM": {"2026-11-13": bad}})
            peak = b.positions["XOM"]["peak_close"]
            self.assertTrue(math.isfinite(peak), bad)
            self.assertEqual(peak, 170.59, bad)
            self.assertTrue(stopped(b))  # the stop still works off the old peak
            self.assertGreater(b.cash, cash0)
            self.assertIn("peak_close unchanged", notes[0])
            json.dumps(b.state, allow_nan=False)  # nothing the state file cannot hold

    def test_a_factor_outside_zero_to_one_is_refused(self):
        # an infinite dividend gives factor 0, a peak of 0 and a stop that can never fire: the peak stays
        b = xom()
        acts = {"XOM": {"splits": [], "dividends": [{"date": "2026-11-16", "amount": float("inf")}]}}
        b.apply_corporate_actions(acts, "2026-11-16", withholding=1.0, closes=XOM_CLOSES)
        self.assertEqual(b.positions["XOM"]["peak_close"], 170.59)

    def test_the_peak_is_multiplied_not_reduced_by_the_dividend(self):
        # CVX, $1.78 ex 2026-11-18: the peak (219.89) is NOT the bar before the ex-date (raw 216.13, adjusted 214.35),
        # so the feed's factor 214.35 / 216.13 gives 218.08 where 'peak - dividend' gives 218.11
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"CVX": 0.2}, {"CVX": 210.0}, "2026-11-02", band=0.0, min_trade_value=0)
        b.positions["CVX"]["peak_close"] = 219.89
        acts = {"CVX": {"splits": [], "dividends": [{"date": "2026-11-18", "amount": 1.78}]}}
        closes = {"CVX": {"2026-11-10": 218.08, "2026-11-17": 214.35, "2026-11-18": 213.90}}
        b.apply_corporate_actions(acts, "2026-11-18", closes=closes)
        self.assertAlmostEqual(b.positions["CVX"]["peak_close"], 218.08, delta=0.01)
        self.assertNotAlmostEqual(b.positions["CVX"]["peak_close"], 219.89 - 1.78, delta=0.01)

    def test_a_dividend_after_upto_is_left_for_its_own_day(self):
        # $1 ex on 01-03 (raw close before it 100, the feed now shows 99) and $2 dated 01-07, after upto = 01-05.
        # As of upto the feed has adjusted for the first one only: the peak 100 becomes 99, not 100 * 101 / 102.
        def book():
            b = PaperBroker(10000, slippage_bps=0)
            b.rebalance({"AAA": 0.5}, {"AAA": 100.0}, "2026-01-01", band=0.0, min_trade_value=0)
            return b

        first, future = {"date": "2026-01-03", "amount": 1.0}, {"date": "2026-01-07", "amount": 2.0}
        closes = {"AAA": {"2026-01-02": 99.0, "2026-01-05": 99.0}}
        alone, both = book(), book()
        alone.apply_corporate_actions({"AAA": {"splits": [], "dividends": [first]}}, "2026-01-05", closes=closes)
        acts = {"AAA": {"splits": [], "dividends": [first, future]}}
        cash0, qty = both.cash, both.positions["AAA"]["qty"]
        notes = both.apply_corporate_actions(acts, "2026-01-05", closes=closes)
        self.assertEqual(len(notes), 1)
        self.assertIn("2026-01-03", notes[0])
        self.assertAlmostEqual(both.cash - cash0, qty * 1.0 * 0.75)  # the $2 is not credited yet
        self.assertAlmostEqual(both.positions["AAA"]["peak_close"], 99.0)
        self.assertEqual(both.state, alone.state)  # the future dividend changed nothing at all
        # on its own day it is credited once and scales the peak once: the feed now shows 01-06 = 99 - 2
        closes["AAA"].update({"2026-01-02": 99.0 * 97 / 99, "2026-01-05": 97.0, "2026-01-06": 97.0})
        notes = both.apply_corporate_actions(acts, "2026-01-07", closes=closes)
        self.assertEqual(len(notes), 1)
        self.assertAlmostEqual(both.cash - cash0, qty * 3.0 * 0.75)
        self.assertAlmostEqual(both.positions["AAA"]["peak_close"], 97.0)

    def test_split_still_rescales_as_before(self):
        b = PaperBroker(10000, slippage_bps=0)
        b.rebalance({"AAA": 0.4}, {"AAA": 100.0}, "2026-01-02", band=0.0, min_trade_value=0)
        acts = {"AAA": {"splits": [{"date": "2026-01-05", "ratio": 4.0}], "dividends": []}}
        for closes in (None, {"AAA": {"2026-01-02": 25.0}}):
            c = PaperBroker(10000, slippage_bps=0, state=copy.deepcopy(b.state))
            c.apply_corporate_actions(acts, "2026-01-06", closes=closes)
            p = c.positions["AAA"]
            self.assertEqual((p["qty"], p["avg_cost"], p["peak_close"], p["last_price"]), (160, 25.0, 25.0, 25.0))


if __name__ == "__main__":
    unittest.main()
