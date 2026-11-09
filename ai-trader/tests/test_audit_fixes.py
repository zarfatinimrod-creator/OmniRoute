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
        self.assertEqual(g[0]["eval_date"], str(idx[5 + 5].date()))  # horizon counted from Monday

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
        self.assertEqual(g[0]["eval_date"], str(idx[6 + 5].date()))

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

    def _run_cycle_stubbed(self, load):
        sent = []
        _load, _send = cycle.load_market, cycle.notify.send
        cycle.load_market = load
        cycle.notify.send = lambda title, body, cfg, prio="default": sent.append(prio) or []
        try:
            return cycle.run_cycle(), sent
        finally:
            cycle.load_market, cycle.notify.send = _load, _send

    def test_cycle_halts_without_trading(self):
        self._break_trades()
        out, sent = self._run_cycle_stubbed(lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not load or trade")))
        self.assertIn("trades.jsonl", out["halted"])
        self.assertEqual(out["executed"], [])
        self.assertEqual(sent, ["urgent"])

    def test_broken_news_chain_does_not_halt_the_quant_book(self):
        journal.append("news_scores.jsonl", {"symbol": "AAA", "score": 9})
        journal.append("news_scores.jsonl", {"symbol": "BBB", "score": 2})
        p = self.tmp / "news_scores.jsonl"
        lines = p.read_text().splitlines()
        rec = json.loads(lines[0]); rec["score"] = 1
        p.write_text("\n".join([json.dumps(rec)] + lines[1:]) + "\n")
        self.assertEqual(journal.broken_chains(), ["news_scores.jsonl"])

        class Reached(Exception):
            pass

        def load(*a, **k):
            raise Reached()
        with self.assertRaises(Reached):  # got past the chain check to the data load
            self._run_cycle_stubbed(load)

    def test_news_engine_stops_on_its_own_broken_chain(self):
        from aitrader import news_live
        journal.append("news_trades.jsonl", {"symbol": "AAA", "qty": 1})
        journal.append("news_trades.jsonl", {"symbol": "BBB", "qty": 2})
        p = self.tmp / "news_trades.jsonl"
        lines = p.read_text().splitlines()
        rec = json.loads(lines[0]); rec["qty"] = 5
        p.write_text("\n".join([json.dumps(rec)] + lines[1:]) + "\n")
        nt = news_live.NewsTrader.__new__(news_live.NewsTrader)
        with self.assertRaises(news_live.ChainBroken):
            nt.step()

    def test_verify_exits_nonzero(self):
        self._break_trades()
        code = ("import sys; from pathlib import Path; from aitrader import journal; "
                f"journal.STATE = Path({str(self.tmp)!r}); sys.argv = ['aitrader', 'verify']; "
                "import runpy; runpy.run_module('aitrader', run_name='__main__')")
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("BROKEN", r.stdout)


class TornLineRecovery(TempState):
    def test_crash_mid_write_does_not_break_the_chain_or_swallow_the_next_record(self):
        journal.append("news_scores.jsonl", {"i": 0})
        journal.append("news_scores.jsonl", {"i": 1})
        with (self.tmp / "news_scores.jsonl").open("a") as f:
            f.write('{"i": 2, "symbol": "AA')  # killed mid-append: no closing brace, no newline
        journal.append("news_scores.jsonl", {"i": 3})
        journal.append("news_scores.jsonl", {"i": 4})
        self.assertEqual([r["i"] for r in journal.read("news_scores.jsonl")], [0, 1, 3, 4])
        self.assertEqual(journal.broken_chains(), [])

    def test_tear_inside_a_multibyte_character_is_recovered(self):
        journal.append("news_scores.jsonl", {"headline": "Apple’s “big” day"})
        with (self.tmp / "news_scores.jsonl").open("ab") as f:
            f.write('{"headline": "Nvidia’s'.encode("utf-8")[:-2])  # cut in the middle of the curly quote
        journal.append("news_scores.jsonl", {"headline": "next"})
        self.assertEqual([r["headline"] for r in journal.read("news_scores.jsonl")], ["Apple’s “big” day", "next"])
        self.assertEqual(journal.broken_chains(), [])

    def test_editing_the_last_record_is_still_detected(self):
        for i in range(3):
            journal.append("trades.jsonl", {"i": i})
        p = self.tmp / "trades.jsonl"
        lines = p.read_text().splitlines()
        p.write_text("\n".join(lines[:-1] + [lines[-1][:-5] + "junk"]) + "\n")  # complete line, broken JSON
        journal.append("trades.jsonl", {"i": 3})
        self.assertEqual(journal.broken_chains(), ["trades.jsonl"])

    def test_an_unreadable_line_in_the_middle_breaks_the_chain(self):
        for i in range(3):
            journal.append("trades.jsonl", {"i": i})
        p = self.tmp / "trades.jsonl"
        lines = p.read_text().splitlines()
        p.write_text("\n".join(lines[:1] + ["not json"] + lines[1:]) + "\n")
        self.assertEqual(journal.broken_chains(), ["trades.jsonl"])


def _nyse_panel(start="2026-11-16", periods=40):
    idx = pd.bdate_range(start, periods=periods + 5)
    idx = idx[~idx.strftime("%Y-%m-%d").isin(journal._calendar().get("holidays", []))][:periods]
    return idx, pd.DataFrame({"AAA": 100.0, "SPY": 100.0}, index=idx)


class CalendarEdges(TempState):
    def _grade_one(self, close, **row):
        journal.append("predictions.jsonl", {"symbol": "AAA", "horizon": 3, "direction": "up", "bench_price": 100.0,
                                             "status": "open", **row})
        journal.evaluate_predictions(close, "SPY")
        g = list(journal.graded().values())
        self.assertEqual(len(g), 1)
        return g[0]

    def test_session_hours_know_holidays_and_early_closes(self):
        self.assertIsNone(journal.session_hours("2026-11-26"))  # Thanksgiving
        self.assertEqual(journal.session_hours("2026-11-27"), ((9, 30), (13, 0)))  # day after: 13:00 close
        self.assertEqual(journal.session_hours("2026-11-30"), ((9, 30), (16, 0)))
        self.assertIsNone(journal.session_hours("2026-11-28"))  # Saturday

    def test_half_day_call_after_1pm_waits_for_next_session(self):
        idx, close = _nyse_panel()
        half = pd.Timestamp("2026-11-27")
        nxt = idx[idx > half][0]
        close.loc[nxt:, "AAA"] = 105.0  # after-hours news priced in at the next session
        for price in (None, 100.0):  # Yahoo says closed (price None) or a stale 13:00 quote
            with self.subTest(price=price):
                self.setUp()
                g = self._grade_one(close, date="2026-11-27", logged_at="2026-11-27T19:00:00+00:00",  # 14:00 NY
                                    source="desk", price=price)
                self.assertAlmostEqual(g["excess"], 0.0)

    def test_holiday_call_waits_for_next_session(self):
        idx, close = _nyse_panel()
        close.loc[pd.Timestamp("2026-11-27"):, "AAA"] = 105.0
        g = self._grade_one(close, date="2026-11-26", logged_at="2026-11-26T16:00:00+00:00", source="claude", price=100.0)
        self.assertAlmostEqual(g["excess"], 0.0)

    def test_audit_desk_row_price_none_premarket_grades_from_monday_close(self):
        idx, close = _nyse_panel("2026-11-02")
        mon = pd.Timestamp("2026-11-09")
        close.loc[mon:, "AAA"] = 110.0
        close.loc[idx[idx.get_loc(mon) + 3]:, "AAA"] = 121.0
        g = self._grade_one(close, date="2026-11-06", logged_at="2026-11-09T11:22:56+00:00", source="desk", price=None)
        self.assertAlmostEqual(g["excess"], 0.10)  # 110 (Monday close) -> 121
        self.assertEqual(g["eval_date"], str(idx[idx.get_loc(mon) + 3].date()))

    def test_naive_and_date_only_stamps_are_conservative(self):
        idx, close = _nyse_panel("2026-11-02")
        close.loc[pd.Timestamp("2026-11-09"):, "AAA"] = 110.0
        g = self._grade_one(close, date="2026-11-06", logged_at="2026-11-09T11:37:39", source="insider_cluster", price=100.0)
        self.assertAlmostEqual(g["excess"], 0.0)  # naive = UTC = Monday 06:37 NY: pre-open
        self.setUp()
        g = self._grade_one(close, date="2026-11-06", logged_at="2026-11-09", source="insider_cluster", price=100.0)
        self.assertAlmostEqual(g["excess"], 0.0)  # no time of day: session after the date

    def test_price_seen_before_the_open_is_not_a_live_price(self):
        idx, close = _nyse_panel("2026-11-02")
        mon = pd.Timestamp("2026-11-09")
        close.loc[mon:, "AAA"] = 110.0  # opening gap
        close.loc[idx[idx.get_loc(mon) + 1]:, "AAA"] = 120.0  # Tuesday differs, so the entry day is pinned
        g = self._grade_one(close, date="2026-11-09", logged_at="2026-11-09T14:30:20+00:00",  # 09:30:20 NY
                            price_at="2026-11-09T14:29:40+00:00", source="news_claude", price=100.0)
        self.assertAlmostEqual(g["ret"], 120.0 / 110.0 - 1, places=4)  # entry = Monday's close (110)

    def test_in_session_call_without_price_takes_that_sessions_close(self):
        idx, close = _nyse_panel("2026-11-02")
        mon = pd.Timestamp("2026-11-09")
        close.loc[mon:, "AAA"] = 110.0
        close.loc[idx[idx.get_loc(mon) + 1]:, "AAA"] = 120.0
        g = self._grade_one(close, date="2026-11-09", logged_at="2026-11-09T16:00:00+00:00", source="desk", price=None)
        self.assertAlmostEqual(g["ret"], 120.0 / 110.0 - 1, places=4)  # Monday's close, not Tuesday's

    def test_date_only_stamp_anchors_on_the_later_of_date_and_log_day(self):
        idx, close = _nyse_panel("2026-11-02")
        close.loc[pd.Timestamp("2026-11-12"):, "AAA"] = 110.0  # news priced in on the 12th
        g = self._grade_one(close, date="2026-11-06", logged_at="2026-11-12", source="insider_cluster", price=100.0)
        self.assertAlmostEqual(g["excess"], 0.0)  # entry after the 12th, never the 9th

    def test_uncovered_calendar_year_counts_as_closed(self):
        self.assertIsNone(journal.session_hours("2028-01-17"))  # MLK day 2028, not in the calendar
        self.assertFalse(journal.calendar_covers("2028-06-01"))

    def test_calendar_is_extended_before_it_runs_out(self):
        from datetime import date
        last = max(journal._calendar()["years"])
        self.assertLess(date.today(), date(last, 10, 1),
                        f"config.json calendar ends {last}: add the next year's NYSE holidays and early closes")


class UniqueNewsKeys(TempState):
    def test_two_calls_in_the_same_second_are_graded_separately(self):
        idx, close = _nyse_panel("2026-11-02")
        mon = pd.Timestamp("2026-11-09")
        close.loc[idx[idx.get_loc(mon) + 1]:, "AAA"] = 110.0  # the stock rises: the up call is right
        base = {"date": "2026-11-09", "logged_at": "2026-11-09T15:05:24+00:00", "symbol": "AAA", "horizon": 1,
                "source": "news_claude", "price": 100.0, "bench_price": 100.0, "status": "open"}
        journal.append("news_predictions.jsonl", {**base, "id": "h1", "direction": "down", "score": 2, "headline": "bad"})
        journal.append("news_predictions.jsonl", {**base, "id": "h2", "direction": "up", "score": 6, "headline": "good"})
        card = journal.evaluate_predictions(close, "SPY", "news_predictions.jsonl", "news_grades.jsonl")
        self.assertEqual(len(journal.read("news_grades.jsonl")), 2)
        self.assertEqual(card["news_claude_h1"]["hit_rate"], 0.5)

    def test_rows_without_id_use_their_headline(self):
        a = {"date": "d", "symbol": "S", "horizon": 1, "source": "news_claude", "logged_at": "t", "headline": "x", "direction": "up"}
        b = {**a, "headline": "y"}
        self.assertNotEqual(journal.pred_key(a), journal.pred_key(b))
        q = {"date": "d", "symbol": "S", "horizon": 1, "source": "quant", "logged_at": "t"}
        self.assertEqual(journal.pred_key(q), "d|S|1|quant|t")  # quant keys unchanged


class StaleQuote(TempState):
    def test_score_9_on_a_stale_quote_does_not_buy(self):
        from aitrader import news_live
        from test_core import CFG
        lp, mo = news_live.live_price, news_live.market_open_now
        news_live.live_price = lambda s: (100.0, 0.0)
        news_live.market_open_now = lambda: True
        try:
            cfg = dict(CFG)
            cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
            nt = news_live.NewsTrader(cfg)
            old = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=2)).isoformat()
            ev = []
            nt.handle_scored([{"key": "k1", "symbol": "AAA", "title": "AAA halted, big news", "published": old,
                               "price": 100.0, "price_at": old}], {"k1": {"score": 9, "why": "x"}}, ev)
        finally:
            news_live.live_price, news_live.market_open_now = lp, mo
        self.assertNotIn("AAA", nt.book.positions)
        self.assertTrue(any("not live" in e for e in ev))
        self.assertTrue(all(p["price"] is None for p in journal.read("news_predictions.jsonl")))


class NewsLoopStops(TempState):
    def test_run_alerts_and_stops_on_a_broken_chain(self):
        from aitrader import news_live
        sent, calls = [], []
        _step, _send = news_live.NewsTrader.step, news_live.notify.send

        def step(self):
            calls.append(1)
            raise news_live.ChainBroken("news hash chain broken: x - stops on open news positions are NOT being checked")
        news_live.NewsTrader.step = step
        news_live.notify.send = lambda title, body, cfg, prio="default": sent.append((prio, body)) or []
        try:
            news_live.run(until_ny="23:59", max_minutes=1, prime=False)
        finally:
            news_live.NewsTrader.step, news_live.notify.send = _step, _send
        self.assertEqual(len(calls), 1)  # stopped after the first failing step
        self.assertTrue(any(p == "urgent" and "NOT being checked" in b for p, b in sent))


if __name__ == "__main__":
    unittest.main()
