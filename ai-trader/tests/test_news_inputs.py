"""News engine inputs (audit of 2026-11-10).

1. The "move today" number the scorer sees. On 2026-11-09 it was measured against the close five sessions back
   and sent as a fraction: MU was +5.82% on the day, the scorer was told -0.1241 and wrote "stock flat today".
2. A stop that cannot see a price is not a stop: the owner is told when a held name has no fresh quote.
3. The owner's exit lever: `news-exit SYMBOL --reason TEXT` asks the engine to sell a held name at its next live quote.
4. The follow-ups of the 2026-11-10 gate (backlog 26 and 32): a bounded wait on the requests lock, the book on disk
   before a request is cleared, an unreadable requests file told to the owner, `--cancel`, a checked symbol, and a
   price that an odd or missing quote time can neither cost nor pass off as live.
"""

import contextlib
import fcntl
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import __main__ as cli
from aitrader import data, journal, news_live
from test_core import CFG

NY = ZoneInfo("America/New_York")
MU_CLOSES = [855.10, 795.23, 656.39, 690.00, 730.17]  # 2026-11-03 .. 2026-11-09 (the last bar is the live session)
MU_BASE_5D = 833.59  # Yahoo's chartPreviousClose for a 5d window: the 2026-11-02 close, NOT yesterday's close


def chart_reply(px, closes, quote_at, base=MU_BASE_5D):
    """A Yahoo chart reply for range=5d, interval=1d: one bar per close, the last one on quote_at's day and the
    earlier ones on the weekday sessions before it (a daily chart has no Saturday or Sunday bar)."""
    day, bars = quote_at.replace(hour=9, minute=30, second=0, microsecond=0), []
    for _ in closes:
        bars.insert(0, day)
        day -= timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
    return {"meta": {"regularMarketPrice": px, "regularMarketTime": int(quote_at.timestamp()), "chartPreviousClose": base,
                     "previousClose": None, "exchangeTimezoneName": "America/New_York"},
            "timestamp": [int(b.timestamp()) for b in bars], "indicators": {"quote": [{"close": closes}]}}


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp
        news_live.ERRORS_SAID.clear()  # what this process already put in news_errors.jsonl: each test starts clean

    def tearDown(self):
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)


def in_time(fn, seconds=10):
    """fn() in a thread: (whether it came back in time, the list its result lands in, the thread). A wait without
    limit must fail a test, not hang the suite; the caller frees what fn waits on and joins the thread."""
    box = []
    t = threading.Thread(target=lambda: box.append(fn()), daemon=True)
    t.start()
    t.join(seconds)
    return not t.is_alive(), box, t


def run_cli(*argv):
    """One aitrader command against the temp state dir: (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class MoveToday(TempState):  # on a temp state dir: a move that cannot be worked out is journaled
    AT = datetime(2026, 11, 9, 10, 43, 50, tzinfo=NY)  # the quote behind the MU buy

    def test_move_is_percent_against_the_previous_session_close(self):
        res = chart_reply(730.17, MU_CLOSES, self.AT)
        self.assertEqual([datetime.fromtimestamp(t, NY).strftime("%m-%d") for t in res["timestamp"]],
                         ["11-03", "11-04", "11-05", "11-06", "11-09"])  # the fixture skips the weekend, like Yahoo
        self.assertEqual(news_live._day_move_pct(res, date(2026, 11, 9)), 5.82)  # 730.17 / 690.00 - 1

    def test_the_five_day_base_is_never_used(self):
        res = chart_reply(730.17, MU_CLOSES, self.AT)
        self.assertEqual(round((730.17 / MU_BASE_5D - 1) * 100, 2), -12.41)  # what the scorer was effectively given
        self.assertEqual(news_live._day_move_pct(res, date(2026, 11, 9)), 5.82)
        self.assertIsNone(news_live._day_move_pct(chart_reply(730.17, [730.17], self.AT), date(2026, 11, 9)))  # no earlier bar

    def test_no_move_before_todays_session_has_traded(self):
        res = chart_reply(733.15, MU_CLOSES[:-1] + [733.15], datetime(2026, 11, 9, 16, 0, tzinfo=NY))
        self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 10)))  # 08:00 next morning: yesterday's quote

    def test_a_missing_previous_close_gives_no_move_never_an_older_base(self):
        for bad in (None, 0):  # Friday's close is missing: Thursday's 690.00 would turn a two-day move into "today"
            res = chart_reply(730.17, [656.39, 690.00, bad, 730.17], self.AT)
            self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 9)), bad)

    def test_a_day_missing_from_the_reply_gives_no_move_never_a_two_day_one(self):
        res = chart_reply(730.17, list(MU_CLOSES), self.AT)  # a copy: the fixture hands its list on as it is
        for part in (res["timestamp"], res["indicators"]["quote"][0]["close"]):
            del part[3]  # Friday 11-06 is not in the reply at all: the last earlier bar is Thursday's 656.39
        self.assertEqual(round((730.17 / 656.39 - 1) * 100, 2), 11.24)  # what a two-day base would have called "today"
        self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 9)))

    def test_the_session_before_a_holiday_is_the_base_after_it(self):
        at = datetime(2026, 11, 27, 10, 0, tzinfo=NY)  # Friday after Thanksgiving: the session before it is Wednesday
        res = chart_reply(101.0, [98.0, 99.0, 100.0, 101.0], at)
        stamps = res["timestamp"]
        stamps[2] = int(datetime(2026, 11, 25, 9, 30, tzinfo=NY).timestamp())  # the fixture knows weekends, not holidays
        stamps[1] = int(datetime(2026, 11, 24, 9, 30, tzinfo=NY).timestamp())
        stamps[0] = int(datetime(2026, 11, 23, 9, 30, tzinfo=NY).timestamp())
        self.assertEqual(news_live._day_move_pct(res, date(2026, 11, 27)), 1.0)
        stamps[2] = stamps[1]  # Wednesday's bar missing: Tuesday's close is not a base
        self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 27)))

    def test_a_year_the_calendar_does_not_cover_gives_no_move(self):
        at = datetime(2031, 3, 4, 10, 0, tzinfo=NY)
        self.assertIsNone(news_live._day_move_pct(chart_reply(101.0, [100.0, 101.0], at), date(2031, 3, 4)))

    def test_bars_and_closes_of_different_length_give_no_move(self):
        res = chart_reply(730.17, MU_CLOSES, self.AT)
        res["timestamp"] = res["timestamp"][1:]  # one stamp short: every close would be paired with the wrong day
        self.assertIsNone(news_live._day_move_pct(res, date(2026, 11, 9)))

    def test_a_move_that_rounds_to_zero_is_never_minus_zero(self):
        res = chart_reply(689.999, MU_CLOSES[:-1] + [689.999], self.AT)  # -0.0001%: rounds to -0.0
        self.assertEqual(json.dumps(news_live._day_move_pct(res, date(2026, 11, 9))), "0.0")  # what the scorer reads

    def test_a_broken_bar_section_never_costs_the_price(self):
        now = datetime.now(NY)
        broken = {"indicators.quote is [None]": lambda r: r["indicators"].update(quote=[None]),
                  "a null inside timestamp": lambda r: r["timestamp"].__setitem__(1, None),
                  "an unknown exchange timezone": lambda r: r["meta"].update(exchangeTimezoneName="Mars/Olympus_Mons")}
        chart = news_live._chart
        try:
            for name, break_it in broken.items():
                res = chart_reply(730.17, MU_CLOSES, now)
                break_it(res)
                news_live._chart = lambda sym, rng, interval, res=res: res
                with self.subTest(name):  # the stop needs the price; the move is only an extra for the scorer
                    self.assertEqual(news_live.live_price("MU"), (730.17, None))
        finally:
            news_live._chart = chart

    def test_live_price_returns_the_price_and_the_percent_move(self):
        now = datetime.now(NY)
        chart = news_live._chart
        news_live._chart = lambda sym, rng, interval: chart_reply(730.17, MU_CLOSES, now)
        try:
            px, move = news_live.live_price("MU")
        finally:
            news_live._chart = chart
        self.assertEqual((px, move), (730.17, 5.82))
        self.assertEqual(news_live.QUOTE_TIME["MU"][:16], now.astimezone(ZoneInfo("UTC")).isoformat()[:16])

    def _live_price(self, break_it, sym="MU"):
        """live_price on a good MU reply of this minute, after break_it has damaged it."""
        res = chart_reply(730.17, MU_CLOSES, datetime.now(NY))
        break_it(res)
        self.addCleanup(news_live.QUOTE_TIME.pop, sym, None)
        with mock.patch.object(news_live, "_chart", lambda s, rng, interval: res):
            return news_live.live_price(sym)

    def test_a_quote_time_that_is_not_a_number_never_loses_the_price(self):
        for odd in ("n/a", "2026-11-10T10:43:50", [], {"raw": 1}):
            news_live.QUOTE_TIME["MU"] = journal.now_utc()  # the stamp of an earlier, good reply
            with self.subTest(odd=odd):  # the stop needs the price whatever the time field holds
                self.assertEqual(self._live_price(lambda r: r["meta"].update(regularMarketTime=odd)), (730.17, None))
                self.assertNotIn("MU", news_live.QUOTE_TIME)  # and a price with no readable time is not dated by an old stamp

    def test_a_reply_with_no_quote_time_drops_the_old_stamp(self):
        for missing in (None, 0, "absent"):
            news_live.QUOTE_TIME["MU"] = journal.now_utc()  # a minute ago this name had a live quote
            with self.subTest(missing=missing):
                gone = (lambda r: r["meta"].pop("regularMarketTime")) if missing == "absent" else \
                    (lambda r: r["meta"].update(regularMarketTime=missing))
                self.assertEqual(self._live_price(gone)[0], 730.17)
                self.assertNotIn("MU", news_live.QUOTE_TIME)  # an undated price must never be treated as live

    def test_a_move_that_cannot_be_worked_out_is_journaled_once_per_day_per_error_type(self):
        def bad_zone(r):  # ZoneInfoNotFoundError, whatever the day
            r["meta"].update(exchangeTimezoneName="Mars/Olympus_Mons")
        for _ in range(3):  # the same fault on every poll of the day
            self.assertEqual(self._live_price(bad_zone), (730.17, None))
        rows = journal.read("news_errors.jsonl")
        self.assertEqual([(r["where"], r["error"]) for r in rows], [("day_move", "ZoneInfoNotFoundError")])
        self.assertEqual(datetime.fromisoformat(rows[0]["at"]).utcoffset(), timedelta(0))
        self._live_price(lambda r: r["timestamp"].__setitem__(1, None))  # another error type: int(None)
        self.assertEqual([r["error"] for r in journal.read("news_errors.jsonl")], ["ZoneInfoNotFoundError", "TypeError"])

        class Tomorrow(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(days=1)
        with mock.patch.object(news_live, "datetime", Tomorrow):  # a new day: the same fault is said again, once
            self._live_price(bad_zone)
            self._live_price(bad_zone)
        self.assertEqual([r["error"] for r in journal.read("news_errors.jsonl")],
                         ["ZoneInfoNotFoundError", "TypeError", "ZoneInfoNotFoundError"])


class ScorerPayload(TempState):
    def test_the_scorer_gets_the_move_in_percent_and_is_told_the_unit(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen["prompt"] = cmd[-1]
            return SimpleNamespace(stdout=json.dumps({"result": '[{"id": 0, "symbol": "MU", "score": 5, "why": "x"}]'}))
        run = news_live.subprocess.run
        news_live.subprocess.run = fake_run
        try:
            out = news_live.score_batch([{"key": "k1", "symbol": "MU", "title": "Micron buyback", "day_move_pct": 5.82,
                                          "published": "2026-11-09T15:26:32+00:00"}], "any-model")
        finally:
            news_live.subprocess.run = run
        self.assertEqual(out["k1"]["score"], 5)
        payload = json.loads(seen["prompt"][seen["prompt"].index("ITEMS:") + len("ITEMS:"):])
        self.assertEqual(payload[0]["stock_move_today_pct"], 5.82)
        self.assertIn("percent", seen["prompt"])
        self.assertIn("null", seen["prompt"])  # the scorer is told what an unknown move looks like

    def test_the_scorer_is_told_that_an_unknown_move_is_not_a_flat_stock(self):
        rule = " ".join(news_live.PROMPT.split())
        self.assertIn("null the move is not known", rule)
        for word in ("flat", "unmoved", "no move yet"):  # 2026-11-09: the scorer wrote "stock flat today" on a bad input
            self.assertIn(word, rule)

    def _handed_to_the_scorer(self, is_open):
        """The items one engine step hands to the scorer when live_price reports a +5.82% session move."""
        handed = []
        nt = news_live.NewsTrader({**CFG, "universe": {"AAA": "Tech", "SPY": "Index"}})
        item = {"key": "k1", "symbol": "AAA", "title": "AAA news", "link": "", "published": journal.now_utc()}
        with mock.patch.object(news_live, "live_price", lambda s: (100.0, 5.82)), \
                mock.patch.object(news_live, "market_open_now", lambda: is_open), \
                mock.patch.object(news_live.notify, "send", lambda *a, **kw: []), \
                mock.patch.object(nt, "poll_headlines", lambda: [item]), \
                mock.patch.object(news_live, "score_batch", lambda items, model: handed.extend(items) or {}):
            nt.step()
        return handed

    def test_outside_the_session_the_scorer_gets_no_move_today(self):
        self.assertEqual(self._handed_to_the_scorer(is_open=True)[0]["day_move_pct"], 5.82)
        # after the close the regular-session move leaves out the after-hours reaction: it is not "so far today"
        self.assertIsNone(self._handed_to_the_scorer(is_open=False)[0]["day_move_pct"])

    def test_the_move_the_scorer_saw_is_journaled_with_the_score(self):
        lp, mo = news_live.live_price, news_live.market_open_now
        news_live.live_price = lambda s: (100.0, 0.0)
        news_live.market_open_now = lambda: False
        try:
            cfg = dict(CFG)
            cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
            nt = news_live.NewsTrader(cfg)
            nt.handle_scored([{"key": "k1", "symbol": "AAA", "title": "AAA news", "published": journal.now_utc(),
                               "price": 100.0, "price_at": None, "day_move_pct": 5.82}], {"k1": {"score": 6, "why": "x"}}, [])
        finally:
            news_live.live_price, news_live.market_open_now = lp, mo
        self.assertEqual(journal.read("news_scores.jsonl")[-1]["day_move_pct"], 5.82)


class HeldOnAClock(TempState):
    """check_stops on a fixed clock (Tuesday 2026-11-10, from 11:00 New York): 5 AAA from 100.00, stop at 97.00."""
    T0 = datetime(2026, 11, 10, 11, 0, tzinfo=NY)

    def setUp(self):
        super().setUp()
        cfg = dict(CFG)
        cfg["universe"] = {"AAA": "Tech", "SPY": "Index"}
        cfg["news"] = {**cfg.get("news", {}), "stop_blind_alert_seconds": 300, "max_quote_age_minutes": 3, "max_hold_days": 0}
        self.nt = news_live.NewsTrader(cfg)
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-10"}}
        self.sent, self.delivered = [], ["ntfy"]  # delivered = what notify.send returns ([] = no channel took it)
        self._lp, self._send = news_live.live_price, news_live.notify.send
        news_live.notify.send = lambda title, body, cfg, prio="default", **kw: (self.sent.append((prio, body)),
                                                                                 list(self.delivered))[1]
        news_live.QUOTE_TIME.pop("AAA", None)

    def tearDown(self):
        news_live.live_price, news_live.notify.send = self._lp, self._send
        news_live.QUOTE_TIME.pop("AAA", None)
        super().tearDown()

    def _check(self, minutes, px, quote_age_s=None):
        """One check_stops call. px: the price every name gets, or {symbol: price} (a name left out has no price)."""
        now = self.T0 + timedelta(minutes=minutes)
        news_live.live_price = lambda s: (px.get(s) if isinstance(px, dict) else px, None)
        if quote_age_s is None:
            news_live.QUOTE_TIME.pop("AAA", None)
        else:
            news_live.QUOTE_TIME["AAA"] = (now - timedelta(seconds=quote_age_s)).isoformat()
        ev = []
        self.nt.check_stops(ev, now)
        return ev

    def _alerts(self):
        return [b for p, b in self.sent if p == "urgent"]


class BlindStop(HeldOnAClock):
    def test_no_price_for_five_minutes_alerts_once(self):
        self._check(0, None)
        self._check(4, None)
        self.assertEqual(self._alerts(), [])
        self._check(5, None)
        self._check(9, None)
        self.assertEqual(len(self._alerts()), 1)
        self.assertIn("AAA", self._alerts()[0])
        self.assertIn("הסטופ", self._alerts()[0])
        self.assertIn("כסף נייר", self._alerts()[0])
        self.assertNotIn("ניו יורק", self._alerts()[0])  # no quote was ever seen: no time to give

    def test_the_alert_says_what_the_stop_sees_and_when_the_last_quote_was(self):
        self._check(0, 100.0, quote_age_s=600)  # Yahoo keeps repeating the 10:50 price
        self._check(5, 100.0, quote_age_s=900)
        body = self._alerts()[0]
        self.assertIn("לפחות 5 דקות", body)
        self.assertIn("מ-10:50 שעון ניו יורק", body)  # the last quote's own time
        self.assertIn("מחיר ישן", body)
        self.assertIn("לא יגיב לירידה", body)
        self.assertNotIn("לא נבדק", body)  # the stop is checked every step: a stale price through it still sells

    def test_a_last_quote_from_another_day_is_given_with_its_date(self):
        self._check(0, 100.0, quote_age_s=19 * 3600)  # nothing printed since Monday's 16:00 close
        self._check(5, 100.0, quote_age_s=19 * 3600 + 300)
        self.assertIn("מ-09.11 16:00 שעון ניו יורק", self._alerts()[0])

    def test_an_alert_that_did_not_go_out_is_tried_again_after_another_window(self):
        self.delivered = []  # a configured channel took nothing (ntfy down); with none configured the log takes it (9c)
        self.enterContext(mock.patch.object(news_live.notify, "channels", lambda cfg: ["ntfy"]))
        self._check(0, None)
        self._check(5, None)  # tried, not delivered: the clock restarts
        self._check(9, None)
        self.assertEqual(len(self._alerts()), 1)
        self.delivered = ["ntfy"]
        self._check(10, None)  # a full window after the failed try
        self.assertEqual(len(self._alerts()), 2)
        self._check(15, None)
        self._check(20, None)
        self.assertEqual(len(self._alerts()), 2)  # delivered: said once

    def test_no_price_is_back_line_for_an_alert_that_never_went_out(self):
        self.delivered = []  # and a channel is configured, as above
        self.enterContext(mock.patch.object(news_live.notify, "channels", lambda cfg: ["ntfy"]))
        self._check(0, None)
        self._check(5, None)
        self._check(6, 100.0, quote_age_s=20)
        self.assertEqual([p for p, _ in self.sent], ["urgent"])  # the owner never heard it was gone
        self.assertFalse(any("חזר" in b for _, b in self.sent))

    def test_a_failing_alert_never_stops_a_sale_and_is_journaled(self):
        self.nt.book.state["positions"]["BBB"] = {"qty": 5, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5,
                                                  "entry_date": "2026-11-10"}

        def down(*a, **kw):
            raise RuntimeError("ntfy is down")
        news_live.notify.send = down
        self._check(0, {"BBB": 50.0})
        ev = self._check(5, {"BBB": 48.0})  # AAA: blind for five minutes -> the alert raises; BBB: through its stop
        self.assertNotIn("BBB", self.nt.book.positions)
        self.assertTrue(any("BBB" in e and "stop" in e for e in ev))
        self.assertEqual(journal.read("news_trades.jsonl")[-1]["symbol"], "BBB")
        err = journal.read("news_errors.jsonl")[-1]
        self.assertEqual((err["where"], err["error"], err["detail"]), ("stop_sight", "RuntimeError", "ntfy is down"))
        self.assertIn("at", err)

    def test_the_alert_window_comes_from_defaults_when_the_config_has_none(self):
        del self.nt.n["stop_blind_alert_seconds"]  # an engine object with a partial config (older tests build one)
        with mock.patch.dict(news_live.DEFAULTS, {"stop_blind_alert_seconds": 120}):
            self._check(0, None)
            self._check(2, None)
        self.assertEqual(len(self._alerts()), 1)

    def test_a_stale_quote_is_blind_too(self):
        self._check(0, 100.0, quote_age_s=600)  # Yahoo keeps repeating a 10-minute-old price
        self._check(5, 100.0, quote_age_s=900)
        self.assertEqual(len(self._alerts()), 1)

    def test_a_fresh_quote_never_alerts_and_the_stop_still_fires(self):
        for m in (0, 5, 10):
            self._check(m, 100.0, quote_age_s=20)
        self.assertEqual(self.sent, [])
        ev = self._check(11, 96.5, quote_age_s=20)  # below the 97.00 stop
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("stop" in e for e in ev))

    def test_a_stale_price_below_the_stop_still_sells(self):
        self._check(0, 96.5, quote_age_s=600)  # blind, but the last known price is already through the stop
        self.assertNotIn("AAA", self.nt.book.positions)

    def test_the_owner_is_told_when_the_price_is_back(self):
        self._check(0, None)
        self._check(5, None)
        self._check(6, 100.0, quote_age_s=20)
        self.assertEqual(len(self.sent), 2)
        self.assertIn("חזר", self.sent[-1][1])
        self.assertIn("הסטופ שוב רואה מחיר עדכני", self.sent[-1][1])  # what changed: the stop sees a fresh price again
        self.assertNotIn("נבדק", self.sent[-1][1])  # the stop was checked all along, on a stale price or none
        self._check(7, 100.0, quote_age_s=20)
        self.assertEqual(len(self.sent), 2)  # said once

    def test_a_short_gap_says_nothing(self):
        self._check(0, None)
        self._check(2, 100.0, quote_age_s=20)
        self._check(5, None)  # a new gap starts here: the clock restarts
        self._check(9, None)
        self.assertEqual(self.sent, [])


class OperatorExit(HeldOnAClock):
    """state/news_exits.json: a request sells the held name at its next live quote, and never weakens the stop."""

    def _ask(self, sym="AAA", reason="earnings tonight"):
        journal.save_json("news_exits.json", {sym: {"reason": reason, "requested_at": "2026-11-10T15:55:00+00:00"}})

    def _last_trade(self):
        t = journal.read("news_trades.jsonl")[-1]
        return t["symbol"], t["side"], t["reason"]

    def test_a_request_sells_at_the_next_live_quote(self):
        self._ask()
        ev = self._check(0, 100.0, quote_age_s=20)
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertEqual(self._last_trade(), ("AAA", "SELL", "operator exit: earnings tonight"))
        self.assertTrue(any("AAA" in e and "operator exit: earnings tonight" in e for e in ev))  # reported by step()
        self.assertEqual(journal.load_json("news_exits.json"), {})  # done: the request is gone

    def test_a_request_comes_before_the_stop(self):
        self._ask()
        self._check(0, 96.5, quote_age_s=20)  # live and through the stop: the owner's reason is the one on record
        self.assertTrue(self._last_trade()[2].startswith("operator exit:"))

    def test_a_request_comes_before_the_time_exit(self):
        self._ask()
        self.nt.n["max_hold_days"] = 1
        self.nt.book.positions["AAA"]["entry_date"] = "2026-11-02"  # held past the time exit
        self._check(0, 100.0, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("operator exit:"))

    def test_without_a_live_quote_the_request_waits_and_the_stop_still_fires(self):
        self._ask()
        save = journal.save_json

        def refused(name, obj):  # the heartbeat is the one file a look that sells nothing writes: every other save fails
            if name != "news_heartbeat.json":
                raise AssertionError("news_exits.json rewritten unchanged")
            return save(name, obj)
        with mock.patch.object(journal, "save_json", refused):
            self._check(0, 100.0, quote_age_s=600)  # a ten-minute-old price is not a price to sell at
            self._check(1, None)
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(journal.read("news_trades.jsonl"), [])
        self.assertIn("AAA", journal.load_json("news_exits.json"))
        self.assertEqual(journal.read("news_errors.jsonl"), [])  # and no rewrite was tried and swallowed
        ev = self._check(2, 96.5, quote_age_s=660)  # still stale, but through the stop: the stop fires on any price
        # the sale, and the line that says buys now wait for the review: no "dropped" line for a name that was held
        self.assertEqual([e[:4] for e in ev], ["SELL", "נמכר"])
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(self._last_trade()[2].startswith("stop "))
        self.assertEqual(journal.load_json("news_exits.json"), {})  # nothing left to exit

    def test_a_request_for_a_name_not_held_is_dropped_and_the_owner_is_told(self):
        at = "2026-11-10T15:55:00+00:00"
        journal.save_json("news_exits.json", {"ZZZ": {"reason": "typo", "requested_at": at},
                                              "aaa": {"reason": "lower case, by hand", "requested_at": at},
                                              "AAA": {"reason": "keep", "requested_at": at}})
        self.nt.n["max_hold_days"] = 5  # as in production: AAA, bought today, is also looked at by the time exit
        self.nt.book.positions["AAA"]["entry_date"] = datetime.now(NY).date().isoformat()
        ev = self._check(0, 100.0, quote_age_s=600)  # AAA: no live quote yet, so it stays held and its request stays
        self.assertEqual(ev, ["exit request for ZZZ dropped: not held", "exit request for aaa dropped: not held"])
        self.assertEqual(list(self.nt.book.positions), ["AAA"])
        self.assertEqual(list(journal.load_json("news_exits.json")), ["AAA"])
        self.assertEqual(self._check(1, 100.0, quote_age_s=660), [])  # said once

    def _file_errors(self):
        return [r for r in journal.read("news_errors.jsonl") if r.get("where") == "news_exits"]

    def test_a_malformed_file_sells_nothing_and_the_owner_is_told_once(self):
        journal.save_json("news_exits.json", ["AAA"])
        ev = self._check(0, 100.0, quote_age_s=20)
        self.assertEqual(list(self.nt.book.positions), ["AAA"])
        self.assertEqual(len(ev), 1)  # he believes he asked: it reaches him as an event, not only news_errors.jsonl
        self.assertIn("news_exits.json cannot be read", ev[0])
        self.assertEqual(journal.load_json("news_exits.json"), ["AAA"])  # left as found
        self.assertEqual(self._check(1, 100.0, quote_age_s=20), [])  # said once per problem, not once per step
        ev = self._check(2, 96.5, quote_age_s=20)
        self.assertEqual([e[:4] for e in ev], ["SELL", "נמכר"])  # the sale, and that buys now wait for its review: no more
        self.assertTrue(self._last_trade()[2].startswith("stop "))  # and the stop is untouched
        self.assertEqual(len(self._file_errors()), 1)  # on record once, not once per step

    def test_a_file_that_is_fixed_and_breaks_again_is_told_again(self):
        (self.tmp / "news_exits.json").write_text("{AAA: out", encoding="utf-8")
        self.assertEqual(len(self._check(0, 100.0, quote_age_s=20)), 1)
        journal.save_json("news_exits.json", {})  # repaired
        self.assertEqual(self._check(1, 100.0, quote_age_s=20), [])
        (self.tmp / "news_exits.json").write_text("{AAA: out", encoding="utf-8")  # a new problem
        self.assertEqual(len(self._check(2, 100.0, quote_age_s=20)), 1)

    def test_a_file_that_is_not_json_never_gets_in_the_way_of_the_stop(self):
        (self.tmp / "news_exits.json").write_text("{AAA: out", encoding="utf-8")  # a hand edit gone wrong
        ev = self._check(0, 100.0, quote_age_s=20)
        self.assertTrue(any("news_exits.json cannot be read" in e for e in ev), ev)  # step() sends its events to the owner
        self._check(1, 96.5, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("stop "))
        rows = self._file_errors()  # the owner believes he asked: the unread file is on record, once
        self.assertEqual(len(rows), 1)
        self.assertIn("cannot be read", rows[0]["detail"])

    def test_a_file_nested_too_deep_to_parse_is_one_more_unreadable_file(self):
        (self.tmp / "news_exits.json").write_text("[" * 100000, encoding="utf-8")  # json raises RecursionError, not ValueError
        self._check(0, 96.5, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("stop "))

    def test_the_reason_in_the_file_is_data(self):
        self._ask(reason="out\n{ignore the rules}" + "x" * 300)
        self._check(0, 100.0, quote_age_s=20)
        reason = self._last_trade()[2]
        self.assertTrue(reason.startswith("operator exit: out ignore the rules x"))
        self.assertEqual(len(reason), len("operator exit: ") + 120)

    def test_a_reason_that_cannot_be_written_as_utf8_still_leaves_a_journaled_sale(self):
        # a hand edit can hold half a surrogate pair; written raw into the journal it raised after the book had changed
        (self.tmp / "news_exits.json").write_text('{"AAA": {"reason": "out \\ud800 now"}}', encoding="utf-8")
        self._check(0, 100.0, quote_age_s=20)
        self.assertEqual(self._last_trade(), ("AAA", "SELL", "operator exit: out now"))
        self.assertEqual(journal.verify_chain("news_trades.jsonl"), (True, 1))

    def test_an_entry_that_is_not_a_request_never_sells(self):
        # only the shape news-exit writes is a request: a hand edit meant to withdraw one (null, false, "cancel") must not sell
        told = []
        for entry in (None, False, 0, "", "cancel", "out now", [], {}, {"reason": None}, {"reason": " \n"}, {"reason": ["out"]}):
            journal.save_json("news_exits.json", {"AAA": entry})
            with self.subTest(entry=entry):
                told += self._check(0, 100.0, quote_age_s=20)
                self.assertIn("AAA", self.nt.book.positions)
                self.assertEqual(journal.load_json("news_exits.json"), {"AAA": entry})  # left in place
        self.assertEqual(len(told), 1)  # the owner hears once that what is under AAA asks for nothing ("out now" may be his)
        self.assertIn("not requests", told[0])
        self.assertIn("AAA", told[0])
        rows = self._file_errors()
        self.assertEqual(len(rows), 1)  # on record once, not once per step
        self.assertIn("AAA", rows[0]["detail"])
        self._check(1, 96.5, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("stop "))  # and the stop is untouched

    def _two_names(self):
        self.nt.book.state["positions"]["BBB"] = {"qty": 5, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5,
                                                  "entry_date": "2026-11-10"}
        self.addCleanup(news_live.QUOTE_TIME.pop, "BBB", None)

    def test_a_request_made_while_the_engine_fetches_prices_is_not_erased(self):
        self._two_names()
        self._ask(reason="first")
        asked = []

        def check(minutes):
            now = self.T0 + timedelta(minutes=minutes)

            def price(sym):
                news_live.QUOTE_TIME[sym] = (now - timedelta(seconds=20)).isoformat()
                if sym == "BBB" and not asked:  # the owner's second request lands while the engine is in its price loop
                    asked.append(run_cli("news-exit", "BBB", "--reason", "second")[0])
                return {"AAA": 100.0, "BBB": 50.0}[sym], None
            news_live.live_price = price
            ev = []
            self.nt.check_stops(ev, now)
            return ev
        ev = check(0)
        self.assertEqual(asked, [0])
        self.assertTrue(any("AAA" in e and "operator exit: first" in e for e in ev))
        self.assertEqual(list(journal.load_json("news_exits.json")), ["BBB"])  # the engine cleared only what it finished
        ev = check(1)
        self.assertTrue(any("BBB" in e and "operator exit: second" in e for e in ev), ev)
        self.assertEqual((list(self.nt.book.positions), journal.load_json("news_exits.json")), ([], {}))

    def test_a_new_request_for_the_same_name_made_during_the_price_loop_stays_in_the_file(self):
        self._two_names()
        self._ask(reason="first")
        asked = []

        def price(sym):
            news_live.QUOTE_TIME[sym] = (self.T0 - timedelta(seconds=20)).isoformat()
            if sym == "BBB" and not asked:  # AAA is sold by now; the owner asks again, with a new reason
                asked.append(run_cli("news-exit", "AAA", "--reason", "second")[0])
            return {"AAA": 100.0, "BBB": 50.0}[sym], None
        news_live.live_price = price
        ev = []
        self.nt.check_stops(ev, self.T0)
        self.assertEqual(asked, [0])
        self.assertTrue(any("AAA" in e and "operator exit: first" in e for e in ev), ev)
        left = journal.load_json("news_exits.json")  # the engine clears the request it acted on, never a newer one
        self.assertEqual((list(left), left["AAA"]["reason"]), (["AAA"], "second"))

    def test_the_book_is_on_disk_before_the_request_is_cleared(self):
        self._ask()
        saves, save = [], journal.save_json

        def spy(name, obj):
            saves.append((name, json.loads(json.dumps(obj, default=str))))
            return save(name, obj)
        with mock.patch.object(journal, "save_json", spy):
            self._check(0, 100.0, quote_age_s=20)
        # a crash between the two writes must not bring the sold name back with its request gone. The book goes to disk
        # with the trade (the queue file is written beside it, by the same save) and the request is cleared last
        # (the look's heartbeat is written between the two, after the sale: a record of its own, not part of this order)
        self.assertEqual([name for name, _ in saves if name not in ("news_queue.json", "news_heartbeat.json")],
                         ["news_book.json", "news_exits.json"])
        self.assertEqual((saves[0][0], saves[0][1]["positions"], saves[-1][0]), ("news_book.json", {}, "news_exits.json"))

    def test_a_stop_sale_is_on_disk_at_once(self):
        self._check(0, 96.5, quote_age_s=20)  # through the stop; step() has not reached its own save yet
        self.assertEqual((journal.load_json("news_book.json") or {}).get("positions"), {})

    def test_a_book_that_cannot_be_saved_costs_no_name_its_stop_check_and_keeps_the_request(self):
        self._two_names()
        self._ask()  # the owner wants out of AAA
        save = journal.save_json

        def full(name, obj):  # the book cannot be written; the trade journal and the requests file can
            if name == "news_book.json":
                raise OSError(28, "No space left on device")
            return save(name, obj)
        with mock.patch.object(journal, "save_json", full):
            ev = self._check(0, {"AAA": 96.0, "BBB": 48.0}, quote_age_s=20)  # both through their stops, in one pass
            self.assertEqual([(t["symbol"], t["side"]) for t in journal.read("news_trades.jsonl")],
                             [("AAA", "SELL"), ("BBB", "SELL")])  # BBB is not left for the next pass, 20 seconds or more away
            # each sale and, after it, the line that buys now wait for the review of the loss
            self.assertEqual(([e[:4] for e in ev], list(self.nt.book.positions)), (["SELL", "נמכר", "SELL", "נמכר"], []))
            # the sale behind the request is not on disk: with the request gone, a restart would hold AAA with nobody asking
            self.assertIn("AAA", journal.load_json("news_exits.json"))
            self.assertEqual(self._check(1, None), [])  # the save still fails: the request stays, and nothing says "not held"
            self.assertIn("AAA", journal.load_json("news_exits.json"))
        (err,) = self._file_errors()  # on record once, not once per step
        self.assertEqual((err["error"], err["detail"]), ("OSError", "[Errno 28] No space left on device"))
        # and each sale's own failed save is on record with it (the save that follows every trade)
        self.assertEqual([r["where"] for r in journal.read("news_errors.jsonl") if r.get("where") != "news_exits"],
                         ["save_after_trade", "save_after_trade"])
        # the book can be written again: it is saved first, then the request is cleared - and AAA, held and sold on his
        # request two passes ago, is not called "not held"
        self.assertEqual(self._check(2, None), [])
        self.assertEqual(((journal.load_json("news_book.json") or {}).get("positions"), journal.load_json("news_exits.json")),
                         ({}, {}))

    def test_a_requests_lock_held_by_someone_else_never_holds_up_the_engine(self):
        self._ask()
        self.nt.n["exits_lock_wait_seconds"] = 0.2
        other = os.open(self.tmp, os.O_RDONLY)  # another writer took the lock and hung
        fcntl.flock(other, fcntl.LOCK_EX)
        try:
            came_back, box, t = in_time(lambda: self._check(0, 100.0, quote_age_s=20))
        finally:
            os.close(other)  # the lock is free: a check that is still waiting comes back now
            t.join(10)
        self.assertTrue(came_back, "check_stops waited on the requests lock without limit")
        self.assertTrue(any("AAA" in e and "operator exit:" in e for e in box[0]))  # the sale is made and reported
        self.assertEqual(self._last_trade()[:2], ("AAA", "SELL"))
        (err,) = self._file_errors()  # the clean-up that could not be done is on record
        self.assertEqual(err["error"], "TimeoutError")
        self.assertIn("AAA", journal.load_json("news_exits.json"))
        # the lock is free again: the request the engine acted on is cleared, and the sale's own line was all there is to say
        self.assertEqual(self._check(1, None), [])
        self.assertEqual(journal.load_json("news_exits.json"), {})

    def test_a_request_cleared_in_a_later_pass_than_its_sale_is_not_called_not_held(self):
        at = "2026-11-10T15:55:00+00:00"
        journal.save_json("news_exits.json", {"AAA": {"reason": "earnings tonight", "requested_at": at},
                                              "ZZZ": {"reason": "typo", "requested_at": at}})
        save = journal.save_json

        def torn(name, obj):
            if name == "news_exits.json":
                raise FileNotFoundError("news_exits.tmp")
            return save(name, obj)
        with mock.patch.object(journal, "save_json", torn):
            ev = self._check(0, 100.0, quote_age_s=20)  # AAA is sold on his request; the requests file cannot be rewritten
        self.assertEqual([e[:4] for e in ev], ["SELL", "נמכר"])  # the sale (10 bps under its cost) and the wait for its review
        self.assertIn("operator exit: earnings tonight", ev[0])
        # the file can be rewritten: both requests go. He was told of the AAA sale; "not held" is true of ZZZ only
        self.assertEqual(self._check(1, None), ["exit request for ZZZ dropped: not held"])
        self.assertEqual(journal.load_json("news_exits.json"), {})

    def test_a_new_request_for_a_name_already_sold_on_request_is_still_answered(self):
        self._ask()
        self._check(0, 100.0, quote_age_s=20)  # sold on his request, and that request is cleared
        self._ask(reason="still do not want it")  # he asks again: there is nothing left to sell, and he must hear it
        self.assertEqual(self._check(1, None), ["exit request for AAA dropped: not held"])
        self.assertEqual(journal.load_json("news_exits.json"), {})

    def test_the_engine_takes_the_lock_wait_and_retry_from_its_config(self):
        self._ask()
        self.nt.n.update(exits_lock_wait_seconds=0.2, exits_lock_retry_seconds=0.07)
        other = os.open(self.tmp, os.O_RDONLY)  # another writer took the lock and hung
        fcntl.flock(other, fcntl.LOCK_EX)
        self.addCleanup(os.close, other)
        naps, nap = [], news_live.time.sleep
        with mock.patch.object(news_live.time, "sleep", lambda seconds: (naps.append(seconds), nap(seconds))):
            self._check(0, 100.0, quote_age_s=20)
        self.assertEqual(set(naps), {0.07})
        (err,) = self._file_errors()
        self.assertEqual(err["error"], "TimeoutError")
        self.assertIn("for 0.2 s", err["detail"])

    def test_the_wait_for_the_lock_comes_from_defaults(self):
        other = os.open(self.tmp, os.O_RDONLY)
        fcntl.flock(other, fcntl.LOCK_EX)
        self.addCleanup(os.close, other)
        with mock.patch.dict(news_live.DEFAULTS, {"exits_lock_wait_seconds": 0.1, "exits_lock_retry_seconds": 0.02}):
            with self.assertRaises(TimeoutError):
                news_live.update_exits(put={"AAA": {"reason": "r", "requested_at": journal.now_utc()}}, wait=None)
        self.assertFalse((self.tmp / "news_exits.json").exists())  # nothing is written without the lock

    def test_the_requests_file_is_rewritten_only_under_its_lock(self):
        locked, save = [], journal.save_json

        def second_writer(name, obj):  # another writer arriving at this very moment: is it kept out?
            if name == "news_exits.json":
                other = os.open(self.tmp, os.O_RDONLY)  # the lock is on the state directory
                try:
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked.append(False)
                except BlockingIOError:
                    locked.append(True)
                finally:
                    os.close(other)
            return save(name, obj)
        with mock.patch.object(journal, "save_json", second_writer):
            run_cli("news-exit", "BBB", "--reason", "by mistake")
            run_cli("news-exit", "BBB", "--cancel", "--said", "cancel it")  # the command taking a request back
            run_cli("news-exit", "AAA", "--reason", "earnings tonight")  # the command's write
            self._check(0, 100.0, quote_age_s=20)  # the engine's write: the request is done
        self.assertEqual(locked, [True, True, True, True])
        self.assertEqual((list(self.nt.book.positions), journal.load_json("news_exits.json")), ([], {}))

    def test_a_requests_file_that_cannot_be_rewritten_never_costs_a_sale_its_report(self):
        self._ask()
        save = journal.save_json

        def torn(name, obj):
            if name == "news_exits.json":
                raise FileNotFoundError("news_exits.tmp")
            return save(name, obj)
        with mock.patch.object(journal, "save_json", torn):
            ev = self._check(0, 100.0, quote_age_s=20)  # must come back: step() still has the book to save and the alert to send
            self.assertEqual(self._check(1, None), [])  # the failure goes on: tried again, nothing new to say
        self.assertTrue(any("AAA" in e and "operator exit:" in e for e in ev))
        self.assertEqual(self._last_trade()[:2], ("AAA", "SELL"))
        (err,) = self._file_errors()  # on record once, not once per step
        self.assertEqual((err["error"], err["detail"]), ("FileNotFoundError", "news_exits.tmp"))
        self.assertIn("at", err)

    def test_a_request_for_a_queued_name_cancels_its_buy_at_the_open(self):
        self.nt.book.state["positions"] = {}
        self.nt.queue = [{"symbol": "AAA", "score": 9, "why": "big contract", "queued_at": "2026-11-10T01:00:00+00:00"}]
        self._ask(reason="do not want it")  # overnight the request is the only lever the owner has
        with mock.patch.object(news_live, "market_open_now", lambda: True), \
                mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}), \
                mock.patch.object(news_live, "live_price", lambda s: (100.0, None)), \
                mock.patch.object(self.nt, "poll_headlines", lambda: []):
            ev = self.nt.step()
        self.assertEqual(journal.read("news_trades.jsonl"), [])  # not bought, so nothing to sell at a loss a moment later
        self.assertEqual((list(self.nt.book.positions), self.nt.queue, self.nt.book.cash), ([], [], self.nt.n["starting_cash"]))
        self.assertTrue(any(e.startswith("AAA score 9:") and e.endswith("no buy") for e in ev), ev)
        self.assertEqual(journal.load_json("news_exits.json"), {})  # the request did its work and is gone

    def test_a_request_waits_for_a_queued_buy_that_has_no_price_yet(self):
        self.nt.book.state["positions"] = {}
        self.nt.queue = [{"symbol": "AAA", "score": 9, "why": "big contract", "queued_at": "2026-11-10T01:00:00+00:00"}]
        self._ask(reason="do not want it")
        opens = {}  # a delayed opening: no 09:30 bar and no live quote on the first step
        with mock.patch.object(news_live, "market_open_now", lambda: True), \
                mock.patch.object(news_live, "official_opens", lambda syms, day: dict(opens)), \
                mock.patch.object(news_live, "live_price", lambda s: (100.0, None)), \
                mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.assertEqual(self.nt.step(), [])
            # still queued, so the request must still be there when the price comes: dropped now, the buy would go through
            self.assertEqual([q["symbol"] for q in self.nt.queue] + list(journal.load_json("news_exits.json")), ["AAA", "AAA"])
            opens["AAA"] = 100.0
            ev = self.nt.step()
        self.assertEqual((journal.read("news_trades.jsonl"), list(self.nt.book.positions), self.nt.queue), ([], [], []))
        self.assertTrue(any(e.startswith("AAA score 9:") and e.endswith("no buy") for e in ev), ev)
        self.assertEqual(journal.load_json("news_exits.json"), {})

    def _score_9(self):
        """One fresh headline on AAA scored 9, in session, at a live 100.00: the events it produced."""
        item = {"key": "k9", "symbol": "AAA", "title": "AAA wins a contract", "published": journal.now_utc(), "price": 100.0,
                "day_move_pct": 0.0}
        ev = []
        with mock.patch.object(news_live, "market_open_now", lambda: True), \
                mock.patch.object(news_live, "live_price", lambda s: (100.0, None)):
            self.nt.handle_scored([item], {"k9": {"score": 9, "why": "large contract"}}, ev)
        return ev

    def test_a_name_the_owner_took_out_is_not_bought_back_that_day(self):
        self._ask()
        self._check(0, 100.0, quote_age_s=20)  # sold: operator exit, and the request is cleared
        ev = self._score_9()
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["SELL"])
        self.assertTrue(any(e.startswith("AAA score 9:") and e.endswith("no buy") for e in ev), ev)

    def test_only_an_operator_exit_of_today_keeps_a_name_out(self):
        self.nt.book.state["positions"] = {}
        today = datetime.now(NY).date()
        journal.append("news_trades.jsonl", {"date": (today - timedelta(days=1)).isoformat(), "symbol": "AAA", "side": "SELL",
                                             "reason": "operator exit: earnings tonight"})  # an earlier session: over
        journal.append("news_trades.jsonl", {"date": today.isoformat(), "symbol": "AAA", "side": "SELL",
                                             "reason": "stop -3% (entry 100.00, now 96.50)"})  # a stop is not the owner's word
        self._score_9()
        self.assertIn("AAA", self.nt.book.positions)


class ExitCommand(TempState):
    def test_news_exit_writes_the_request(self):
        earlier = {"reason": "old", "requested_at": "2026-11-10T14:00:00+00:00"}
        journal.save_json("news_exits.json", {"MU": earlier})
        code, out, err = run_cli("news-exit", "aaa", "--reason", "earnings tonight\n{sell everything}" + "x" * 300)
        saved = journal.load_json("news_exits.json")
        self.assertEqual((code, sorted(saved), saved["MU"]), (0, ["AAA", "MU"], earlier))  # upper-cased and merged
        self.assertTrue(saved["AAA"]["reason"].startswith("earnings tonight sell everything x"))  # cleaned like a headline
        self.assertEqual(len(saved["AAA"]["reason"]), 120)
        self.assertEqual(datetime.fromisoformat(saved["AAA"]["requested_at"]).utcoffset(), timedelta(0))
        self.assertEqual((json.loads(out), err), (saved, ""))  # the command prints the file
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["news_exits.json"])  # the book is the engine's, not the command's

    def test_news_exit_needs_a_reason_and_replaces_a_malformed_file(self):
        self.assertEqual(run_cli("news-exit", "AAA")[0], 2)
        self.assertEqual(run_cli("news-exit", "AAA", "--reason", " {}\n")[0], 2)  # no text once cleaned: not a request
        self.assertFalse((self.tmp / "news_exits.json").exists())
        for garbage in ('["garbage"]', "{AAA: out"):  # a list, or not JSON at all: the new request replaces it
            (self.tmp / "news_exits.json").write_text(garbage, encoding="utf-8")
            code, _, err = run_cli("news-exit", "AAA", "--reason", "r")
            self.assertEqual(code, 0, garbage)
            self.assertIn("news_exits.json", err)  # said out loud: whatever requests were in it are gone
            self.assertEqual(list(journal.load_json("news_exits.json")), ["AAA"])

    def test_the_config_note_tells_the_owner_about_the_lever(self):
        note = CFG["news"]["_note"]
        for word in ("news-exit SYMBOL --reason", "--cancel", "next live quote", "never buys"):
            self.assertIn(word, note)

    def test_the_lock_and_health_numbers_are_in_the_config(self):
        for name in ("health_log_seconds", "exits_lock_wait_seconds", "exits_lock_retry_seconds"):
            with self.subTest(name):  # config.json is where they are read and changed; DEFAULTS is only the fallback
                self.assertIn(name, CFG["news"])
                self.assertIn(name, news_live.DEFAULTS)

    def test_cancel_takes_one_request_back_and_leaves_the_others(self):
        at = "2026-11-10T14:00:00+00:00"
        journal.save_json("news_exits.json", {"MU": {"reason": "old", "requested_at": at},
                                              "AAA": {"reason": "by mistake", "requested_at": at}})
        code, out, err = run_cli("news-exit", "aaa", "--cancel", "--said", "cancel it")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(journal.load_json("news_exits.json"), {"MU": {"reason": "old", "requested_at": at}})
        self.assertEqual(json.loads(out), journal.load_json("news_exits.json"))  # the command prints the file

    def test_cancel_also_removes_an_entry_that_is_not_a_request(self):
        journal.save_json("news_exits.json", {"AAA": None})  # an earlier hand edit
        self.assertEqual(run_cli("news-exit", "AAA", "--cancel", "--said", "cancel it")[0], 0)
        self.assertEqual(journal.load_json("news_exits.json"), {})

    def test_cancel_with_nothing_to_cancel_says_so_and_writes_nothing(self):
        code, out, err = run_cli("news-exit", "AAA", "--cancel", "--said", "cancel it")
        self.assertEqual((code, out), (1, ""))  # not 0: the request may already have been acted on
        self.assertIn("AAA", err)
        self.assertIn("nothing was cancelled", err)
        self.assertFalse((self.tmp / "news_exits.json").exists())
        (self.tmp / "news_exits.json").write_text("{AAA: out", encoding="utf-8")
        code, _, err = run_cli("news-exit", "AAA", "--cancel", "--said", "cancel it")
        self.assertEqual(code, 1)
        self.assertIn("cannot be read", err)
        self.assertEqual((self.tmp / "news_exits.json").read_text(encoding="utf-8"), "{AAA: out")  # never replaced by a clean-up

    def test_a_request_is_either_made_or_cancelled(self):
        self.assertEqual(run_cli("news-exit", "AAA", "--reason", "r", "--cancel", "--said", "cancel it")[0], 2)
        self.assertFalse((self.tmp / "news_exits.json").exists())

    def test_a_symbol_that_is_not_a_ticker_is_refused(self):
        for bad in ("", "A B", "AAA;rm", "$(reboot)", "../../etc", "AAA\n", "ABCDEFGHIJKLM", "מיקרון"):
            with self.subTest(bad=bad):
                for how in (("--reason", "r"), ("--cancel", "--said", "cancel it")):
                    code, out, err = run_cli("news-exit", bad, *how)
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("ticker", err)
        self.assertFalse((self.tmp / "news_exits.json").exists())
        good = ("brk.b", "BF-B", "^VIX", "EURUSD=X", "ABCDEFGHIJKL", "7")
        for sym in good:
            with self.subTest(good=sym):
                self.assertEqual(run_cli("news-exit", sym, "--reason", "r")[0], 0)
        self.assertEqual(sorted(journal.load_json("news_exits.json")), sorted(s.upper() for s in good))

    def test_news_exit_gives_up_when_the_lock_stays_held(self):
        other = os.open(self.tmp, os.O_RDONLY)  # another writer took the lock and hung
        fcntl.flock(other, fcntl.LOCK_EX)
        cfg = {**CFG, "news": {**CFG["news"], "exits_lock_wait_seconds": 0.2, "exits_lock_retry_seconds": 0.02}}
        try:
            with mock.patch.object(data, "load_config", lambda *a, **kw: cfg):  # the wait is the config's, as the engine's is
                came_back, box, t = in_time(lambda: run_cli("news-exit", "AAA", "--reason", "r"))
        finally:
            os.close(other)
            t.join(10)
        self.assertTrue(came_back, "news-exit waited on the requests lock without limit")
        code, out, err = box[0]
        self.assertEqual((code, out), (1, ""))
        self.assertIn("for 0.2 s", err)
        self.assertIn("nothing was changed", err)


class ScoreCommand(TempState):
    """news-score: a check of the scorer that trades nothing. It must show the scorer what the engine would."""

    def _news_score(self, is_open):
        """One `news-score` run on one fresh AAA headline with a +5.82% session move: (the scorer's payload, stdout)."""
        prompts = []
        item = {"key": "k1", "symbol": "AAA", "title": "AAA news", "link": "", "published": journal.now_utc()}

        def claude(cmd, **kw):
            prompts.append(cmd[-1])
            return SimpleNamespace(stdout=json.dumps({"result": '[{"id": 0, "symbol": "AAA", "score": 6, "why": "x"}]'}))
        with mock.patch.object(data, "load_config", lambda *a, **kw: {**CFG, "universe": {"AAA": "Tech", "SPY": "Index"}}), \
                mock.patch.object(news_live, "fetch_headlines", lambda sym, session: [dict(item)]), \
                mock.patch.object(news_live, "live_price", lambda s: (100.0, 5.82)), \
                mock.patch.object(news_live, "market_open_now", lambda: is_open), \
                mock.patch.object(news_live.notify, "send", lambda *a, **kw: []), \
                mock.patch.object(news_live.subprocess, "run", claude):
            code, out, _ = run_cli("news-score")
        self.assertEqual(code, 0)
        return json.loads(prompts[0][prompts[0].index("ITEMS:") + len("ITEMS:"):]), out

    def test_news_score_gates_the_move_by_the_session_like_the_engine(self):
        payload, out = self._news_score(is_open=True)
        self.assertEqual(payload[0]["stock_move_today_pct"], 5.82)
        self.assertIn("move 5.82", out)
        # after the close the regular-session move leaves out the after-hours reaction: the engine sends null, so must the check
        payload, out = self._news_score(is_open=False)
        self.assertIsNone(payload[0]["stock_move_today_pct"])
        self.assertIn("move None", out)

    def test_the_check_is_a_scorer_call_like_any_other_and_goes_on_record(self):
        self._news_score(is_open=True)
        (row,) = journal.read("news_scorer_calls.jsonl")  # it cost what an engine call costs
        self.assertEqual((row["sent"], row["answered"]), (1, 1))
        self.assertEqual(row["source"], "news-score")  # and is not mistaken for one: an engine row has no "source"
        self.assertEqual(journal.read("news_scores.jsonl"), [])  # and it still scores nothing into the forward record

    def test_a_check_with_nothing_to_score_makes_no_call_and_leaves_no_row(self):
        with mock.patch.object(data, "load_config", lambda *a, **kw: {**CFG, "universe": {"AAA": "Tech", "SPY": "Index"}}), \
                mock.patch.object(news_live, "fetch_headlines", lambda sym, session: []), \
                mock.patch.object(news_live, "market_open_now", lambda: False), \
                mock.patch.object(news_live.subprocess, "run", side_effect=AssertionError("claude was called")):
            self.assertEqual(run_cli("news-score")[0], 0)
        self.assertEqual(journal.read("news_scorer_calls.jsonl"), [])  # no call: not even a row that only names its source


if __name__ == "__main__":
    unittest.main()
