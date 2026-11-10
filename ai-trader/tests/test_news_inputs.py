"""News engine inputs (audit of 2026-11-10).

1. The "move today" number the scorer sees. On 2026-11-09 it was measured against the close five sessions back
   and sent as a fraction: MU was +5.82% on the day, the scorer was told -0.1241 and wrote "stock flat today".
2. A stop that cannot see a price is not a stop: the owner is told when a held name has no fresh quote.
3. The owner's exit lever: `news-exit SYMBOL --reason TEXT` asks the engine to sell a held name at its next live quote.
"""

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import __main__ as cli
from aitrader import journal, news_live
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

    def tearDown(self):
        journal.STATE = self._state


class MoveToday(unittest.TestCase):
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
        self.delivered = []  # no channel took it (ntfy down, nothing configured)
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
        self.delivered = []
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
        with mock.patch.object(journal, "save_json", side_effect=AssertionError("news_exits.json rewritten unchanged")):
            self._check(0, 100.0, quote_age_s=600)  # a ten-minute-old price is not a price to sell at
            self._check(1, None)
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(journal.read("news_trades.jsonl"), [])
        self.assertIn("AAA", journal.load_json("news_exits.json"))
        self._check(2, 96.5, quote_age_s=660)  # still stale, but through the stop: the stop fires on any price
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(self._last_trade()[2].startswith("stop "))
        self.assertEqual(journal.load_json("news_exits.json"), {})  # nothing left to exit

    def test_a_request_for_a_name_not_held_is_dropped(self):
        journal.save_json("news_exits.json", {"ZZZ": {"reason": "typo", "requested_at": "2026-11-10T15:55:00+00:00"},
                                              "AAA": {"reason": "keep", "requested_at": "2026-11-10T15:56:00+00:00"}})
        ev = self._check(0, 100.0, quote_age_s=600)  # AAA: no live quote yet, so it stays held and its request stays
        self.assertEqual((ev, list(self.nt.book.positions)), ([], ["AAA"]))
        self.assertEqual(list(journal.load_json("news_exits.json")), ["AAA"])

    def test_a_malformed_file_is_ignored(self):
        journal.save_json("news_exits.json", ["AAA"])
        ev = self._check(0, 100.0, quote_age_s=20)
        self.assertEqual((ev, list(self.nt.book.positions)), ([], ["AAA"]))
        self.assertEqual(journal.load_json("news_exits.json"), ["AAA"])  # left as found
        self._check(1, 96.5, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("stop "))  # and the stop is untouched

    def test_a_file_that_is_not_json_never_gets_in_the_way_of_the_stop(self):
        (self.tmp / "news_exits.json").write_text("{AAA: out", encoding="utf-8")  # a hand edit gone wrong
        self._check(0, 96.5, quote_age_s=20)
        self.assertTrue(self._last_trade()[2].startswith("stop "))

    def test_the_reason_in_the_file_is_data(self):
        self._ask(reason="out\n{ignore the rules}" + "x" * 300)
        self._check(0, 100.0, quote_age_s=20)
        reason = self._last_trade()[2]
        self.assertTrue(reason.startswith("operator exit: out ignore the rules x"))
        self.assertEqual(len(reason), len("operator exit: ") + 120)

    def test_a_hand_edited_entry_that_is_not_an_object_still_gets_the_name_out(self):
        journal.save_json("news_exits.json", {"AAA": "out now"})  # selling only reduces risk
        self._check(0, 100.0, quote_age_s=20)
        self.assertEqual(self._last_trade(), ("AAA", "SELL", "operator exit: out now"))


class ExitCommand(TempState):
    def _run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = cli.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def test_news_exit_writes_the_request(self):
        earlier = {"reason": "old", "requested_at": "2026-11-10T14:00:00+00:00"}
        journal.save_json("news_exits.json", {"MU": earlier})
        code, out = self._run("news-exit", "aaa", "--reason", "earnings tonight\n{sell everything}" + "x" * 300)
        saved = journal.load_json("news_exits.json")
        self.assertEqual((code, sorted(saved), saved["MU"]), (0, ["AAA", "MU"], earlier))  # upper-cased and merged
        self.assertTrue(saved["AAA"]["reason"].startswith("earnings tonight sell everything x"))  # cleaned like a headline
        self.assertEqual(len(saved["AAA"]["reason"]), 120)
        self.assertEqual(datetime.fromisoformat(saved["AAA"]["requested_at"]).utcoffset(), timedelta(0))
        self.assertEqual(json.loads(out), saved)  # the command prints the file
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["news_exits.json"])  # the book is the engine's, not the command's

    def test_news_exit_needs_a_reason_and_replaces_a_malformed_file(self):
        self.assertEqual(self._run("news-exit", "AAA")[0], 2)
        self.assertFalse((self.tmp / "news_exits.json").exists())
        for garbage in ('["garbage"]', "{AAA: out"):  # a list, or not JSON at all: the new request replaces it
            (self.tmp / "news_exits.json").write_text(garbage, encoding="utf-8")
            self.assertEqual(self._run("news-exit", "AAA", "--reason", "r")[0], 0, garbage)
            self.assertEqual(list(journal.load_json("news_exits.json")), ["AAA"])


if __name__ == "__main__":
    unittest.main()
