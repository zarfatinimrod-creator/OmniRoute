"""Guards added after the MU loss of 2026-11-10 (state/postmortems.jsonl; logs/2026-11-10-loss-postmortem.md).
Each one can only refuse a buy or bring a sale forward:
  - no buy when today's move of the stock is unknown, or when it has already risen past the limit;
  - a second, independent check before every buy and every place in the queue (a new, confirmed event);
  - no re-buy of a name that was just stopped out;
  - a stop that was traded through while nobody was watching is sold at the first live quote;
  - stops are looked at before headlines are polled and scored."""

import contextlib
import copy
import io
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import __main__ as cli
from aitrader import journal, news_live
from test_core import APPROVED, CFG

NY = ZoneInfo("America/New_York")
MU = 'Micron Will "Buy Back a Hundred Billion Dollars" of Stock at Four Times Earnings'


class _Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp
        self.prices, self.moves = {"AAA": 100.0, "BBB": 50.0, "SPY": 500.0}, {}
        self.answers, self.asked = [], []  # what the second check answers, in turn; then APPROVED
        self.rescores = []  # what the scorer says when asked again, in turn; then 10
        self._saved = (news_live.live_price, news_live.market_open_now, news_live.verify_headline, news_live.notify.send,
                       news_live.rescore_headline)
        self._bars_since = news_live.bars_since
        news_live.bars_since = lambda sym, since, now: []  # no test here reads minute bars from the network
        news_live.live_price = lambda s: (self.prices.get(s), self.moves.get(s, 0.0))
        news_live.market_open_now = lambda: True
        news_live.verify_headline = self._verify
        news_live.rescore_headline = lambda item, model, timeout=None: self.rescores.pop(0) if self.rescores else 10
        self.sent = []
        news_live.notify.send = lambda title, body, cfg, prio="default", **kw: (self.sent.append((prio, body)), ["ntfy"])[1]
        self.cfg = copy.deepcopy(CFG)
        self.cfg["universe"] = {"AAA": "Tech", "BBB": "Tech", "SPY": "Index"}
        self.cfg["news"]["max_hold_days"] = 0
        self.cfg["news"]["guards"] = "enforce"  # these classes test the guards as rules; OnTrial tests the default
        self.nt = news_live.NewsTrader(self.cfg)

    def tearDown(self):
        (news_live.live_price, news_live.market_open_now, news_live.verify_headline, news_live.notify.send,
         news_live.rescore_headline) = self._saved
        news_live.bars_since = self._bars_since
        for sym in ("AAA", "BBB"):
            news_live.QUOTE_TIME.pop(sym, None)
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _verify(self, item, model, timeout=60):
        self.asked.append((item["symbol"], model))
        return self.answers.pop(0) if self.answers else dict(APPROVED)

    def _item(self, key="k1", sym="AAA", move=0.0, **extra):
        return {"key": key, "symbol": sym, "title": f"{sym} wins a contract", "published": "2026-11-09T14:00:00+00:00",
                "price": self.prices[sym], "day_move_pct": move, **extra}

    def _score(self, item, score=9, events=None):
        ev = [] if events is None else events
        self.nt.handle_scored([item], {item["key"]: {"score": score, "why": "x"}}, ev)
        self.nt.drain_trial(wait=5)  # on trial the second check is asked in the background: its answer is in by now
        return ev

    def _checks(self):
        return journal.read("news_checks.jsonl")

    def _verdicts(self):
        return [(c["guard"], c["verdict"]) for c in self._checks()]

    def _second(self):
        """The last row the second check wrote (a buy that followed it writes its own row after)."""
        return [c for c in self._checks() if c["guard"] == "second_check"][-1]

    def _queued(self, sym="AAA"):  # the item is what handle_scored writes in the mode the engine is in
        self.nt.queue = [{"symbol": sym, "score": 9, "why": "big contract", "queued_at": journal.now_utc(), "id": "q1",
                          "second_check": "passed" if self.nt.n["guards"] == "enforce" else None}]
        ev = []
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {sym: self.prices[sym]}):
            self.nt.run_queue_at_open(ev)
        return ev

    def _stop_row(self, days_ago):
        day = (datetime.now(NY).date() - timedelta(days=days_ago)).isoformat()
        journal.append("news_trades.jsonl", {"date": day, "symbol": "AAA", "side": "SELL", "qty": 1, "price": 96.5,
                                             "realized_pnl": 0.0, "reason": "stop -3% (entry 100.00, now 96.50)"})


class MoveGuards(_Engine):
    def test_unknown_move_in_session_is_no_buy_but_the_score_is_still_on_record(self):
        ev = self._score(self._item(move=None))
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("AAA" in e and "לא ידוע" in e for e in ev), ev)
        self.assertEqual(len(journal.read("news_scores.jsonl")), 1)
        self.assertEqual({p["horizon"] for p in journal.read("news_predictions.jsonl")}, {1, 5})
        self.assertEqual([(c["guard"], c["verdict"]) for c in self._checks()],
                         [("second_check", "passed"), ("unknown_move", "refused")])

    def test_an_item_that_does_not_say_its_move_is_an_unknown_move(self):
        item = self._item()
        del item["day_move_pct"]
        self._score(item)
        self.assertEqual(self.nt.book.positions, {})

    def test_the_mu_case_a_stock_already_up_past_the_limit_is_not_chased(self):
        ev = self._score(self._item(move=5.82))  # MU on 2026-11-09: +5.82% before the headline was scored
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("5.8%" in e and "3%" in e for e in ev), ev)
        last = self._checks()[-1]
        self.assertEqual((last["guard"], last["day_move_pct"], last["limit"]), ("no_chase", 5.82, 3.0))

    def test_the_limit_is_the_line_itself_and_a_falling_stock_is_not_a_chase(self):
        self._score(self._item("a", move=3.0))
        self.assertEqual(self.nt.book.positions, {})
        self._score(self._item("b", move=2.99))
        self.assertIn("AAA", self.nt.book.positions)
        self._score(self._item("c", "BBB", move=-4.0))
        self.assertIn("BBB", self.nt.book.positions)

    def test_both_switches_can_be_turned_off_in_config(self):
        self.cfg["news"].update({"max_day_move_pct_to_buy": 0, "require_known_move": False})
        self.nt = news_live.NewsTrader(self.cfg)
        self._score(self._item("a", move=9.0))
        self._score(self._item("b", "BBB", move=None))
        self.assertEqual(set(self.nt.book.positions), {"AAA", "BBB"})

    def test_the_defaults_are_on_when_config_does_not_say(self):
        for k in ("max_day_move_pct_to_buy", "require_known_move", "verify_buys", "rebuy_cooldown_sessions", "stop_catchup"):
            self.cfg["news"].pop(k, None)
        self.nt = news_live.NewsTrader(self.cfg)
        self._score(self._item("a", move=5.82))
        self._score(self._item("b", "BBB", move=None))
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(self.asked)  # the second check ran as well

    def test_a_queued_buy_is_not_filled_into_a_gap_up_or_an_unknown_move(self):
        self.moves["AAA"] = 6.0  # opened 6% above yesterday's close
        ev = self._queued()
        self.assertEqual((self.nt.book.positions, self.nt.queue), ({}, []))
        self.assertTrue(any("6.0%" in e for e in ev), ev)
        self.moves["AAA"] = None
        ev = self._queued()
        self.assertEqual((self.nt.book.positions, self.nt.queue), ({}, []))
        self.assertTrue(any("לא ידוע" in e for e in ev), ev)
        self.moves["AAA"] = 1.0
        self._queued()
        self.assertIn("AAA", self.nt.book.positions)


class SecondCheck(_Engine):
    COMMENT = {"kind": "analyst_or_commentary", "confirmed": False, "why": "a TV guest's forecast"}

    def test_every_call_must_pass_and_the_default_is_two_calls(self):
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(self.asked, [("AAA", self.nt.n["model"])] * 2)
        self.answers = [dict(APPROVED), dict(self.COMMENT)]  # the second of two says commentary
        ev = self._score(self._item("b", "BBB"))
        self.assertNotIn("BBB", self.nt.book.positions)
        self.assertTrue(any("BBB" in e and "analyst_or_commentary" in e for e in ev), ev)
        last = self._checks()[-1]
        self.assertEqual((last["guard"], last["verdict"], len(last["answers"])), ("second_check", "refused", 2))

    def test_each_way_of_failing_the_check_is_a_refusal(self):
        bad = [dict(self.COMMENT),
               {**APPROVED, "confirmed": False},
               {**APPROVED, "confirmed": "yes"},               # only true is a confirmation
               {**APPROVED, "kind": "third_party_report"},     # a report about the company is not its announcement
               {"error": "TimeoutExpired"},
               {"kind": "company_announcement"},               # an answer with parts missing
               None]
        for i, answer in enumerate(bad):
            self.answers = [answer, dict(APPROVED)]
            ev = self._score(self._item(f"k{i}"))
            self.assertEqual(self.nt.book.positions, {}, answer)
            self.assertTrue(any("AAA" in e and "לא קונים" in e for e in ev), (answer, ev))

    def test_the_same_scorer_asked_again_must_still_be_above_the_line(self):
        for i, again in enumerate((8, 7, None, "9", True)):    # the 9 was the top of the spread, or no answer came
            self.rescores = [again]
            ev = self._score(self._item(f"k{i}"))
            self.assertEqual(self.nt.book.positions, {}, again)
            self.assertTrue(any("AAA" in e and "לא קונים" in e for e in ev), (again, ev))
            self.assertEqual(self._checks()[-1]["rescore"], again)
        self.rescores = [9]
        self._score(self._item("ok"))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual((self._second()["verdict"], self._second()["rescore"]), ("passed", 9))

    def test_a_rescorer_that_raises_is_a_refusal_and_the_rescore_has_its_own_switch(self):
        def boom(item, model, timeout=None):
            raise RuntimeError("scorer down")
        news_live.rescore_headline = boom
        self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.nt.n["verify_rescore"] = False
        self._score(self._item("b"))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertIsNone(self._second()["rescore"])

    def test_a_checker_that_raises_is_a_refusal_not_a_crash(self):
        def boom(item, model, timeout=60):
            raise RuntimeError("scorer down")
        news_live.verify_headline = boom
        ev = self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("נכשלה" in e for e in ev), ev)

    def test_commentary_is_not_queued_for_the_open_either(self):
        news_live.market_open_now = lambda: False
        self.answers = [dict(self.COMMENT)]
        ev = self._score(self._item(move=None))
        self.assertEqual((self.nt.queue, self.nt.book.positions), ([], {}))
        self.assertTrue(any("לא קונים" in e for e in ev), ev)
        self._score(self._item("b", move=None))  # a confirmed event after the close is queued as before
        self.assertEqual([q["symbol"] for q in self.nt.queue], ["AAA"])

    def test_the_check_is_not_asked_for_scores_under_the_line_or_names_already_held(self):
        self._score(self._item(), score=8)
        self.assertEqual(self.asked, [])
        self._score(self._item("b"))
        asked = len(self.asked)
        self._score(self._item("c"))  # held now: nothing to check, nothing to buy
        self.assertEqual(len(self.asked), asked)

    def test_switch_off_and_number_of_calls_come_from_config(self):
        self.cfg["news"].update({"verify_calls": 3, "verify_model": "some-model"})
        self.nt = news_live.NewsTrader(self.cfg)
        self._score(self._item())
        self.assertEqual(self.asked, [("AAA", "some-model")] * 3)
        self.cfg["news"]["verify_buys"] = False
        self.nt = news_live.NewsTrader(self.cfg)
        self.asked.clear()
        self._score(self._item("b", "BBB"))
        self.assertEqual(self.asked, [])
        self.assertIn("BBB", self.nt.book.positions)

    def test_the_buy_is_made_at_a_quote_from_after_the_check(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())
        news_live.QUOTE_TIME["AAA"] = now.isoformat()

        def verify(i, model, timeout=60):  # while the check runs the price moves and the stock jumps
            self.prices["AAA"], self.moves["AAA"] = 101.0, 1.0
            return dict(APPROVED)
        news_live.verify_headline = verify
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self._score(item)
        self.assertAlmostEqual(self.nt.book.positions["AAA"]["avg_cost"], 101.0 * 1.001, places=6)

    def test_a_move_that_passed_the_limit_during_the_check_is_not_bought(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())

        def verify(i, model, timeout=60):
            self.prices["AAA"], self.moves["AAA"] = 104.0, 4.0
            return dict(APPROVED)
        news_live.verify_headline = verify
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            ev = self._score(item)
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("4.0%" in e for e in ev), ev)

    def test_no_live_quote_after_the_check_is_no_buy(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())
        live = iter([True, False])  # live when scored, not live any more after the check
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: next(live)):
            ev = self._score(item)
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("אין מחיר חי אחרי הבדיקה השנייה" in e for e in ev), ev)


class Checker(unittest.TestCase):
    """news_live._ask_checker with the scorer process stubbed."""

    def _ask(self, reply=None, raises=None, item=None):
        seen = {}

        def run(cmd, **kw):
            seen.update(cmd=cmd, kw=kw)
            if raises:
                raise raises
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"result": reply}), stderr="")
        item = item or {"symbol": "MU", "title": MU, "published": "2026-11-09T15:26:32+00:00", "day_move_pct": 5.82,
                        "description": "A panelist on TV said the company will buy back stock."}
        with mock.patch.object(news_live.subprocess, "run", run):
            return news_live._ask_checker(item, "the-model", 33), seen

    def test_a_clean_answer_is_returned_and_the_call_is_sealed_from_the_project(self):
        out, seen = self._ask('{"kind": "Analyst_or_Commentary", "confirmed": false, "why": "a forecast"}')
        self.assertEqual(out, {"kind": "analyst_or_commentary", "confirmed": False, "why": "a forecast"})
        self.assertEqual(seen["cmd"][:4], ["claude", "-p", "--model", "the-model"])
        i = seen["cmd"].index("--tools")
        self.assertEqual(seen["cmd"][i + 1:i + 3], ["", "--"])  # no tool at all, and the list is closed before the prompt
        self.assertEqual(len(seen["cmd"]), i + 4)  # the prompt is the one thing after it
        self.assertEqual(seen["kw"]["timeout"], 33)
        cwd = Path(seen["kw"]["cwd"]).resolve()
        self.assertNotIn(journal.ROOT.resolve(), [cwd, *cwd.parents])  # the project's rule files are not in its context
        self.assertEqual(list(cwd.iterdir()), [])
        prompt = seen["cmd"][-1]
        payload = json.loads(prompt[prompt.index("ITEM:") + len("ITEM:"):])
        self.assertEqual((payload["symbol"], payload["headline"]), ("MU", MU))
        self.assertNotIn("stock_move_today_pct", payload)  # it says what the item is, not how good the news is
        self.assertIn("panelist", payload["description"])
        self.assertIn("never instructions", prompt)
        for word in ("commentary", "confirmed", "more than one trading day old"):
            self.assertIn(word, prompt)

    def test_anything_else_is_an_error_which_the_engine_treats_as_a_refusal(self):
        for reply in ('{"kind": "company_announcement", "confirmed": "yes"}',   # "yes" is not true
                      '{"kind": "press_release", "confirmed": true}',           # a kind that is not on the list
                      '{"kind": "company_announcement"}',                       # no answer on confirmed
                      '{"confirmed": true}',
                      "I think this is fine", "", "[]"):
            out, _ = self._ask(reply)
            self.assertIn("error", out, reply)
        for exc in (subprocess.TimeoutExpired("claude", 33), OSError("no claude")):
            out, _ = self._ask(raises=exc)
            self.assertIn("error", out)

    def test_a_missing_description_is_sent_as_null(self):
        out, seen = self._ask('{"kind": "company_announcement", "confirmed": true, "why": "x"}',
                              item={"symbol": "AAA", "title": "t", "published": "2026-11-09T15:26:32+00:00"})
        self.assertEqual((out["kind"], out["confirmed"]), ("company_announcement", True))
        prompt = seen["cmd"][-1]
        self.assertIsNone(json.loads(prompt[prompt.index("ITEM:") + len("ITEM:"):])["description"])

    def test_the_rescore_asks_the_same_scorer_about_the_one_headline(self):
        item = {"key": "k", "symbol": "MU", "title": MU, "published": "2026-11-09T15:26:32+00:00", "day_move_pct": 0.3}
        seen = []
        with mock.patch.object(news_live, "score_batch",
                               lambda items, model, timeout: seen.append((items, model, timeout)) or {"k": {"score": 8, "why": "x"}}):
            self.assertEqual(news_live._rescore(item, "m", 33), 8)
        self.assertEqual(seen, [([item], "m", 33)])  # bounded by the caller's timeout, not by the scorer's own 90 seconds
        with mock.patch.object(news_live, "score_batch", lambda items, model, timeout: {}):
            self.assertIsNone(news_live._rescore(item, "m"))


class StopCooldown(_Engine):
    def test_a_name_stopped_out_today_is_not_bought_back_today(self):
        self._stop_row(0)
        ev = self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("AAA" in e and "סטופ" in e for e in ev), ev)
        self.assertEqual(self._checks()[-1]["guard"], "stop_cooldown")
        self._score(self._item("b", "BBB"))  # another name is not held back by it
        self.assertIn("BBB", self.nt.book.positions)

    def test_a_stop_from_an_earlier_week_and_a_cooldown_of_zero_do_not_block(self):
        self._stop_row(10)  # at least one session has opened since
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.nt.book.state["positions"] = {}
        self._stop_row(0)
        self.nt.n["rebuy_cooldown_sessions"] = 0
        self._score(self._item("b"))
        self.assertIn("AAA", self.nt.book.positions)

    def test_a_sale_that_was_not_a_stop_starts_no_cooldown(self):
        day = datetime.now(NY).date().isoformat()
        journal.append("news_trades.jsonl", {"date": day, "symbol": "AAA", "side": "SELL", "qty": 1, "price": 101.0,
                                             "realized_pnl": 1.0, "reason": "time exit after 5 trading days"})
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)


class CatchUpStop(_Engine):
    """Tuesday 2026-11-10, 09:38 New York: the engine comes back after the open. 5 AAA held since the day before,
    entry 100.00, stop 97.00; the price is back at 98.50."""
    NOW = datetime(2026, 11, 10, 9, 38, 30, tzinfo=NY)

    def setUp(self):
        super().setUp()
        self.nt.n["stop_catchup"] = "sell"  # the selling mode; the default, "alert", has its own tests below
        self.nt.n["stop_catchup_min_bar_share"] = 0.0  # the fixtures give only the bars that matter; the trust rule has its test
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 98.5, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09",
                                                   "news_entry": {"score": 9, "why": "x", "at": "2026-11-09T15:44:00+00:00"}}}
        self.prices["AAA"] = 98.5
        self.bars, self.asked_bars = [], []
        self._bars = news_live.bars_since
        news_live.bars_since = lambda sym, since, now: (self.asked_bars.append((sym, since, now)), self.bars)[1]

    def tearDown(self):
        news_live.bars_since = self._bars
        super().tearDown()

    def _bar(self, minute, low, close):
        return (datetime(2026, 11, 10, 9, minute, tzinfo=NY).astimezone(timezone.utc), low, close)

    def _step(self, now=None, quote_age_s=10):
        now = now or self.NOW
        if quote_age_s is None:
            news_live.QUOTE_TIME.pop("AAA", None)
        else:
            news_live.QUOTE_TIME["AAA"] = (now - timedelta(seconds=quote_age_s)).isoformat()
        ev = []
        self.nt.catch_up_stops(ev, now)
        self.nt.check_stops(ev, now)
        return ev

    def _sold(self):
        return [t for t in journal.read("news_trades.jsonl") if t["side"] == "SELL"]

    def test_the_mu_case_a_bar_that_closed_under_the_stop_sells_at_the_first_live_quote(self):
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.0, 96.3), self._bar(33, 96.2, 97.5), self._bar(37, 98.0, 98.4)]
        ev = self._step()
        self.assertEqual(self.nt.book.positions, {})
        (sale,) = self._sold()
        self.assertTrue(sale["reason"].startswith("stop -3% traded through while unwatched (low 96.00 at 09:32"), sale["reason"])
        self.assertEqual((sale["quote"], sale["stop"]), (98.5, 97.0))
        self.assertTrue(sale["quote_at"])
        self.assertTrue(any("AAA" in e and "נחצה" in e for e in ev), ev)
        (sym, since, now), = self.asked_bars
        self.assertEqual((sym, since.strftime("%H:%M"), now), ("AAA", "09:30", self.NOW))  # the whole session so far

    def test_one_low_under_the_stop_is_not_enough_but_two_are(self):
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 97.2, 97.6)]  # one print under 97.00, closed above
        self._step()
        self.assertIn("AAA", self.nt.book.positions)
        self.nt._stops_checked_at = None  # as after another restart: nothing is remembered
        self.nt._covered.clear()
        self.nt._unseen_lows.clear()
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.95, 97.6)]
        self._step()
        self.assertEqual(self.nt.book.positions, {})

    def test_two_lone_prints_in_two_stretches_are_two_prints(self):
        self.bars = [self._bar(31, 96.9, 97.4)]  # 09:31, while the engine was away
        self._step()
        self.assertIn("AAA", self.nt.book.positions)
        later = self.NOW + timedelta(minutes=10)  # away again from 09:38:30; one more print under the stop at 09:44
        self.bars = [self._bar(44, 96.8, 97.3)]
        self._step(later)
        self.assertEqual(self.nt.book.positions, {})
        self.assertIn("low 96.80 at 09:44", self._sold()[0]["reason"])

    def test_a_stretch_that_was_read_is_not_read_again_at_every_step(self):
        self.bars = [self._bar(m, 97.5, 97.8) for m in range(30, 38)]  # every minute up to 09:38 was read
        self._step(quote_age_s=None)  # no live quote for the name: only the bars can say what happened
        self._step(self.NOW + timedelta(seconds=20), quote_age_s=None)
        self._step(self.NOW + timedelta(seconds=80), quote_age_s=None)
        self.assertEqual(len(self.asked_bars), 1)
        self._step(self.NOW + timedelta(seconds=240), quote_age_s=None)  # still no quote: the new stretch is read
        # from the start of the minute the earlier read ended in: that bar was not complete then
        self.assertEqual([a[1].strftime("%H:%M:%S") for a in self.asked_bars], ["09:30:00", "09:38:00"])

    def test_bars_that_cannot_be_read_sell_nothing_and_the_owner_is_told_once(self):
        self.bars = None
        self._step()
        self.nt._stops_checked_at = None
        self._step(self.NOW + timedelta(minutes=5))
        self.assertIn("AAA", self.nt.book.positions)
        urgent = [b for p, b in self.sent if p == "urgent"]
        self.assertEqual(len(urgent), 1, urgent)
        self.assertIn("AAA", urgent[0])
        self.prices["AAA"] = 96.0  # the normal stop still works
        self._step(self.NOW + timedelta(minutes=6))
        self.assertEqual(self.nt.book.positions, {})

    def test_while_the_stops_are_being_looked_at_the_bars_are_not_read(self):
        self.bars = [self._bar(32, 96.0, 96.3)]
        self.nt._stops_checked_at = (self.NOW - timedelta(seconds=40)).astimezone(timezone.utc)
        self._step()
        self.assertEqual(self.asked_bars, [])
        self.assertIn("AAA", self.nt.book.positions)
        self._step(self.NOW + timedelta(seconds=20))  # check_stops above set the clock: still no gap
        self.assertEqual(self.asked_bars, [])

    def test_after_a_stall_only_the_bars_since_the_last_look_are_read(self):
        self.nt._stops_checked_at = datetime(2026, 11, 10, 9, 33, 10, tzinfo=NY).astimezone(timezone.utc)
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M:%S"), "09:33:00")  # the whole minute the last look fell in

    def test_the_last_look_survives_a_restart_through_the_heartbeat(self):
        journal.save_json("news_heartbeat.json", {"at": "x", "stops_checked_at": "2026-11-10T14:35:00+00:00"})
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M"), "09:35")

    def test_on_a_new_machine_the_last_look_is_the_last_point_of_the_equity_curve(self):
        journal.write_all("news_equity.jsonl", [{"at": "2026-11-10T14:31:00+00:00", "equity": 1.0, "positions": 1},
                                                {"at": "2026-11-10T14:36:00+00:00", "equity": 1.0, "positions": 1}])
        self._step()  # no heartbeat here: the file is not in git, so a replaced container starts without it
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M"), "09:36")
        self.asked_bars.clear()
        del self.nt._stops_checked_at
        self.nt._covered.clear()  # a new process again
        journal.save_json("news_heartbeat.json", {"at": "x", "stops_checked_at": "2026-11-10T14:33:00+00:00"})
        self._step(self.NOW + timedelta(minutes=1))
        self.assertEqual(self.asked_bars[0][1].strftime("%H:%M"), "09:33")  # a heartbeat, when there is one, is the word

    def test_with_nothing_to_go_by_the_whole_session_so_far_is_read(self):
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M"), "09:30")

    def test_a_position_opened_today_is_judged_only_on_bars_after_its_entry(self):
        pos = self.nt.book.state["positions"]["AAA"]
        pos["entry_date"], pos["news_entry"]["at"] = "2026-11-10", "2026-11-10T14:33:20+00:00"  # bought 09:33:20
        self.bars = []
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M"), "09:34")  # the 09:31-09:33 lows came before the entry
        self.asked_bars.clear()
        pos["news_entry"].pop("at")  # an entry of today with no time: nothing can be told apart, so nothing is read
        self.nt._stops_checked_at = None
        self._step()
        self.assertEqual(self.asked_bars, [])
        self.assertIn("AAA", self.nt.book.positions)

    def test_a_breach_waits_for_a_live_quote_and_is_then_sold(self):
        self.bars = [self._bar(32, 96.0, 96.3)]
        self._step(quote_age_s=None)  # no quote time: not live
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(self.nt.book.positions["AAA"]["stop_breach"]["low"], 96.0)
        self.bars = []
        self._step(self.NOW + timedelta(seconds=20))
        self.assertEqual(self.nt.book.positions, {})

    def test_the_default_only_tells_the_owner_and_keeps_the_normal_stop(self):
        self.assertEqual(news_live.DEFAULTS["stop_catchup"], "alert")
        self.assertEqual(CFG["news"]["stop_catchup"], "alert")
        self.nt.n["stop_catchup"] = "alert"
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.0, 96.3)]
        ev = self._step()
        self.assertIn("AAA", self.nt.book.positions)  # not sold on the memory of the breach
        self.assertEqual(self._sold(), [])
        urgent = [b for p, b in self.sent if p == "urgent"]
        self.assertEqual(len(urgent), 1)
        self.assertIn("09:32", urgent[0])
        self.assertIn("לא נמכרת לבד", urgent[0])
        self.assertIn("כתוב לי", urgent[0])  # the owner is not a programmer: he is not told to run a command
        self.assertTrue(any("נחצה" in e for e in ev), ev)
        self._step(self.NOW + timedelta(minutes=10))  # told once, not at every later gap
        self.assertEqual(len([b for p, b in self.sent if p == "urgent"]), 1)
        self.prices["AAA"] = 96.5  # and the normal stop still sells
        self._step(self.NOW + timedelta(minutes=11))
        self.assertEqual([t["reason"][:8] for t in self._sold()], ["stop -3%"])

    def test_a_mark_left_on_an_earlier_day_does_not_sell_when_the_mode_is_switched_later(self):
        pos = self.nt.book.positions["AAA"]
        pos["stop_breach"] = {"low": 96.5, "at": "09:32", "unwatched_from": "09:30", "found_at": "2026-11-05T14:40:00+00:00"}
        self._step()  # mode "sell", price back at 98.50, above the stop: the owner kept this position days ago
        self.assertIn("AAA", self.nt.book.positions)
        pos["stop_breach"]["found_at"] = journal.now_utc()  # found today: sold at the live quote, and the reason has the date
        self._step()
        self.assertEqual(self.nt.book.positions, {})
        self.assertIn(journal.now_utc()[:10], self._sold()[0]["reason"])

    def test_only_what_was_really_read_counts_as_looked_at(self):
        self.bars = []  # Yahoo has not published the minutes yet: an empty answer for a short stretch
        self.nt._stops_checked_at = datetime(2026, 11, 10, 9, 36, 0, tzinfo=NY).astimezone(timezone.utc)  # the run before
        news_live.QUOTE_TIME.pop("AAA", None)  # no live quote for the name in this run
        self.nt._look_at_stops([], now=self.NOW)  # 09:38:30
        self.assertNotIn("AAA", self.nt._covered)  # nothing was read: the stretch is still owed
        self.bars = [self._bar(36, 96.0, 96.1), self._bar(37, 96.0, 96.2)]
        # the loop's own clock moved at the look above; the name's stamp did not, so it is asked for again
        self.nt._look_at_stops([], now=self.NOW + timedelta(seconds=20))
        self.assertEqual(len(self.asked_bars), 2)
        self.assertEqual(self.nt.book.positions["AAA"]["stop_breach"]["at"], "09:36")  # found (no live quote yet to sell at)
        self.assertEqual(self.nt._covered["AAA"].astimezone(NY).strftime("%H:%M:%S"), "09:38:00")  # the end of the last bar read

    def test_what_was_kept_for_a_position_goes_with_the_position(self):
        self.nt.n["stop_catchup"] = "alert"
        self.bars = [self._bar(31, 96.9, 97.4)]  # one lone print under the stop while nobody looked
        self._step()
        self.assertEqual(len(self.nt._unseen_lows["AAA"]), 1)
        self.nt._log_trade(self.nt._sell("AAA", 98.5, "bad news score 1: x"), [])  # sold for another reason...
        self.assertEqual((self.nt._unseen_lows, self.nt._covered), ({}, {}))
        self.nt.n["block_buys_until_loss_reviewed"] = False
        self._score(self._item())  # ...and bought again: the old print is not counted against the new position
        self.assertIn("AAA", self.nt.book.positions)
        self.assertNotIn("AAA", self.nt._unseen_lows)

    def test_a_mark_of_an_earlier_day_does_not_switch_the_look_off(self):
        self.nt.n["stop_catchup"] = "alert"
        self.nt.book.positions["AAA"]["stop_breach"] = {"low": 96.5, "at": "09:32", "unwatched_from": "09:30",
                                                        "found_at": "2026-11-05T14:40:00+00:00"}
        self.bars = [self._bar(31, 96.0, 96.2)]  # today the stop is crossed again while nobody looks
        self._step()
        self.assertEqual(len(self.asked_bars), 1)
        self.assertEqual(self.nt.book.positions["AAA"]["stop_breach"]["found_at"][:10], journal.now_utc()[:10])
        self.assertEqual(len([b for p, b in self.sent if p == "urgent" and "נחצה" in b]), 1)
        self._step(self.NOW + timedelta(minutes=10))  # found today: not read and not said again
        self.assertEqual(len(self.asked_bars), 1)

    def test_the_minute_the_last_look_fell_in_is_read_too(self):
        self.nt._stops_checked_at = datetime(2026, 11, 10, 9, 33, 30, tzinfo=NY).astimezone(timezone.utc)
        self.bars = [self._bar(33, 96.0, 96.1)]  # the 09:33 bar closed under the stop after the look at 09:33:30
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M:%S"), "09:33:00")
        self.assertEqual(self.nt.book.positions, {})

    def test_a_close_under_the_stop_with_no_low_under_it_is_still_a_breach_not_a_crash(self):
        self.bars = [self._bar(31, 97.4, 96.9)]  # a bar as no real feed should send it; it must not take the look down
        self._step()
        self.assertEqual(journal.read("news_errors.jsonl"), [])
        self.assertEqual(self.nt.book.positions, {})

    def test_too_few_of_the_minutes_are_bars_nobody_sells_on(self):
        self.nt.n["stop_catchup_min_bar_share"] = 0.5  # the default: at least half the minutes of the stretch
        self.assertEqual((news_live.DEFAULTS["stop_catchup_min_bar_share"], news_live.DEFAULTS["stop_catchup_min_minutes"],
                          news_live.DEFAULTS["stop_catchup_min_lows"], news_live.DEFAULTS["stop_catchup_min_seconds"]),
                         (0.5, 4, 2, 120))
        self.bars = [self._bar(31, 96.0, 96.1), self._bar(32, 96.0, 96.2)]  # 2 of the 8 minutes since 09:30: holes
        self._step()
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(len([b for p, b in self.sent if p == "urgent" and "אי אפשר לקרוא" in b]), 1)
        self.nt._covered.clear()  # as after a restart: the stretch is read again
        self.nt._stops_checked_at = None
        self.nt._catchup_blind = set()
        self.bars = [self._bar(m, 96.0, 96.1) for m in (31, 32, 33, 34)]  # 4 of 8: enough to be believed
        self._step()
        self.assertEqual(self.nt.book.positions, {})

    def test_bars_that_break_the_look_tell_the_owner_once_like_bars_that_cannot_be_read(self):
        self.bars = [("not a bar",)]
        self._step()
        self._step(self.NOW + timedelta(minutes=5))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual({e["where"] for e in journal.read("news_errors.jsonl")}, {"catch_up_stops"})
        self.assertEqual(len([b for p, b in self.sent if p == "urgent" and "אי אפשר לקרוא" in b]), 1)

    def test_switch_off_closed_day_and_no_positions_read_nothing(self):
        self.bars = [self._bar(32, 96.0, 96.3)]
        for off in ("off", False, None, "anything else"):
            self.nt.n["stop_catchup"] = off
            self._step()
        self.nt.n["stop_catchup"] = "sell"
        self.nt.catch_up_stops([], datetime(2026, 11, 8, 10, 0, tzinfo=NY))  # a Sunday
        self.nt.book.state["positions"], held = {}, self.nt.book.state["positions"]
        self.nt.catch_up_stops([], self.NOW)
        self.assertEqual(self.asked_bars, [])
        self.assertEqual(self._sold(), [])
        self.nt.book.state["positions"] = held

    def test_a_failure_inside_is_put_on_record_and_the_normal_stop_still_gets_its_turn(self):
        def boom(sym, since, now):
            raise RuntimeError("yahoo")
        news_live.bars_since = boom
        self.prices["AAA"] = 96.0
        self._step()
        self.assertEqual(self.nt.book.positions, {})
        (err,) = journal.read("news_errors.jsonl")
        self.assertEqual((err["where"], err["error"]), ("catch_up_stops", "RuntimeError"))

    def test_it_never_buys(self):
        self.bars = [self._bar(32, 96.0, 96.3)]
        self._step()
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["SELL"])


class StopsFirst(_Engine):
    def test_a_stop_is_sold_and_saved_before_the_scorer_is_even_asked(self):
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        self.prices["AAA"] = 96.0
        item = {"key": "k", "symbol": "BBB", "title": "BBB news", "link": "", "published": journal.now_utc()}

        def scorer_down(items, model):
            raise RuntimeError("scorer hangs")
        with mock.patch.object(self.nt, "poll_headlines", lambda: [item]), \
                mock.patch.object(news_live, "score_batch", scorer_down), \
                mock.patch.object(news_live, "bars_since", lambda *a: []):
            with self.assertRaises(RuntimeError):
                self.nt.step()
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["SELL"])
        self.assertEqual(journal.load_json("news_book.json")["positions"], {})  # the book on disk matches the journal

    def test_the_live_quote_is_looked_at_before_the_minute_bars_are_read(self):
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        self.prices["AAA"] = 96.0
        order = []
        live = news_live.live_price

        def bars(sym, since, now):  # reading minute bars can take a minute: a stop must not wait behind it
            order.append("bars")
            return []
        news_live.live_price = lambda s: (order.append("quote"), live(s))[1]
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), mock.patch.object(news_live, "bars_since", bars):
            self.nt.step()
        self.assertEqual(order[0], "quote")
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertNotIn("bars", order)  # sold at the first look: nothing is left to catch up on

    def test_a_gap_is_measured_from_the_look_before_this_step_not_from_its_own_first_look(self):
        self.nt.n["stop_catchup"] = "alert"
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        self.nt._stops_checked_at = datetime.now(timezone.utc) - timedelta(minutes=10)  # the engine was away ten minutes
        asked = []
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), \
                mock.patch.object(news_live, "bars_since", lambda sym, since, now: (asked.append(since), [])[1]), \
                mock.patch.object(journal, "session_hours", lambda d: ((0, 0), (23, 59))):
            self.nt.step()
        self.assertEqual(len(asked), 1)  # the live look at the top of the step did not hide the gap
        self.assertAlmostEqual((datetime.now(NY) - asked[0]).total_seconds(), 600, delta=90)

    def test_an_early_look_that_fails_does_not_cost_the_step_its_other_work(self):
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        calls = []
        real = self.nt.check_stops

        def flaky(events, now=None):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("exits file")
            return real(events, now)
        self.prices["AAA"] = 96.0
        with mock.patch.object(self.nt, "check_stops", flaky), mock.patch.object(self.nt, "poll_headlines", lambda: []), \
                mock.patch.object(news_live, "bars_since", lambda *a: []):
            self.nt.step()
        self.assertEqual(self.nt.book.positions, {})  # the look at the end of the step sold it
        self.assertEqual(journal.read("news_errors.jsonl")[0]["where"], "early_stops")

    def test_stops_are_looked_at_between_scorer_batches(self):
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        self.nt.n["batch_max"] = 1
        items = [{"key": f"k{i}", "symbol": "BBB", "title": f"BBB news {i}", "link": "", "published": journal.now_utc()} for i in range(3)]
        seen = []

        def scorer(batch, model):
            if len(seen) == 1:
                self.prices["AAA"] = 96.0  # the price falls through the stop while the second batch is being scored
            seen.append([t["side"] for t in journal.read("news_trades.jsonl")])
            return {}
        with mock.patch.object(self.nt, "poll_headlines", lambda: items), mock.patch.object(news_live, "score_batch", scorer), \
                mock.patch.object(news_live, "bars_since", lambda *a: []):
            self.nt.step()
        self.assertEqual(seen, [[], [], ["SELL"]])  # sold before the third batch was sent, not at the end of the step

    def test_the_heartbeat_says_when_the_stops_were_last_looked_at(self):
        with mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
        beat = journal.load_json("news_heartbeat.json")
        self.assertTrue(beat["stops_checked_at"])
        self.assertLess(abs((datetime.fromisoformat(beat["stops_checked_at"]) - datetime.now(timezone.utc)).total_seconds()), 60)


class OneEngine(_Engine):
    def test_a_second_engine_on_the_same_book_does_not_start(self):
        import fcntl
        held = open(journal._path("news_engine.lock"), "w")
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with mock.patch.object(news_live, "NewsTrader", mock.Mock(side_effect=AssertionError("must not be built"))):
                self.assertEqual(news_live.run(max_minutes=0.001), 3)  # not 0: the caller must not take it for a run
                with mock.patch.object(news_live, "run", lambda until, minutes, **k: 3):
                    self.assertEqual(cli.main(["news-live", "--minutes", "1"]), 3)
        finally:
            held.close()

    def test_a_lock_that_does_not_work_at_all_does_not_leave_the_book_without_an_engine(self):
        ran = []
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live, "_run", lambda *a, **k: ran.append(a) or 0):
            self.assertEqual(news_live.run(max_minutes=0.001), 0)
        self.assertEqual(len(ran), 1)  # an engine with no lock still looks at the stops; no engine looks at nothing

    def test_the_lock_is_free_again_when_the_engine_ends(self):
        with mock.patch.object(news_live.NewsTrader, "step", lambda self: []), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None):
            self.assertEqual(news_live.run(max_minutes=0.0001, prime=False), 0)
            self.assertEqual(news_live.run(max_minutes=0.0001, prime=False), 0)  # the first one let go of the book


class Bars(unittest.TestCase):
    def _bars(self, stamps, lows, closes, since_min=30, now=(9, 38, 30)):
        res = {"timestamp": stamps, "indicators": {"quote": [{"low": lows, "close": closes}]}}
        since = datetime(2026, 11, 10, 9, since_min, tzinfo=NY)
        with mock.patch.object(news_live, "_chart", lambda sym, rng, iv: res):
            return news_live.bars_since("AAA", since, datetime(2026, 11, 10, *now, tzinfo=NY))

    def _t(self, minute, second=0):
        return int(datetime(2026, 11, 10, 9, minute, second, tzinfo=NY).timestamp())

    def test_only_completed_minutes_inside_the_window(self):
        stamps = [self._t(m) for m in range(29, 38)] + [self._t(38, 12)]  # 09:29 is before the window; the last row is live
        got = self._bars(stamps, [99.0] * 10, [99.5] * 10)
        self.assertEqual([b[0].astimezone(NY).strftime("%H:%M") for b in got], [f"09:{m}" for m in range(30, 38)])
        self.assertEqual(got[0][1:], (99.0, 99.5))

    def test_untrusted_answers_are_none(self):
        self.assertIsNone(self._bars([self._t(31)], [99.0, 98.0], [99.5]))          # arrays do not line up
        self.assertEqual(len(self._bars([self._t(31), self._t(36)], [99.0] * 2, [99.5] * 2)), 2)  # holes: the caller's rule
        with mock.patch.object(news_live, "_chart", mock.Mock(side_effect=RuntimeError("down"))):
            self.assertIsNone(news_live.bars_since("AAA", datetime(2026, 11, 10, 9, 30, tzinfo=NY),
                                                   datetime(2026, 11, 10, 9, 38, tzinfo=NY)))

    def test_a_minute_with_no_trade_is_skipped_not_invented(self):
        stamps = [self._t(m) for m in range(30, 38)]
        got = self._bars(stamps, [99.0, None, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0], [99.5] * 8)
        self.assertEqual(len(got), 7)


class OnRecord(_Engine):
    def test_a_score_row_says_where_the_headline_came_from_and_which_scorer_wrote_it(self):
        self._score(self._item(link="https://finance.yahoo.com/x", description="AAA said on Monday ..."), score=6)
        row = journal.read("news_scores.jsonl")[-1]
        self.assertEqual((row["link"], row["description"]), ("https://finance.yahoo.com/x", "AAA said on Monday ..."))
        self.assertEqual((row["model"], row["prompt"]), (self.nt.n["model"], news_live.PROMPT_ID))
        self.assertEqual(len(news_live.PROMPT_ID), 12)

    def test_the_feed_description_is_read_and_cleaned(self):
        xml = ("<rss><channel><item><title>AAA &amp; Co wins</title><link>https://x/y</link>"
               "<pubDate>Mon, 09 Nov 2026 15:26:32 +0000</pubDate>"
               "<description><![CDATA[<p>A panelist said &quot;they will&quot; buy back.</p>]]></description></item>"
               "<item><title>No description</title><pubDate>Mon, 09 Nov 2026 15:27:00 +0000</pubDate></item></channel></rss>")

        class Reply:
            status_code, text = 200, xml
        session = mock.Mock()
        session.get.return_value = Reply()
        first, second = news_live.fetch_headlines("AAA", session)
        self.assertEqual(first["description"], 'A panelist said "they will" buy back.')
        self.assertEqual((first["title"], first["link"], second["description"]), ("AAA & Co wins", "https://x/y", ""))

    def test_the_record_of_the_checks_is_a_log_that_can_never_stop_the_engine_or_a_trade(self):
        self.assertNotIn("news_checks.jsonl", journal.CHAINED)  # a broken chain stops the engine, and its stops with it
        self._score(self._item(move=5.82))
        self.assertEqual(self._verdicts(), [("second_check", "passed"), ("no_chase", "refused")])
        self.assertNotIn("hash", self._checks()[0])
        (self.tmp / "news_checks.jsonl").unlink()
        (self.tmp / "news_checks.jsonl").mkdir()  # the log cannot be written at all
        ev = self._score(self._item("b", move=5.82))
        self.assertEqual(self.nt.book.positions, {})  # an enforced guard still refuses, and says so
        self.assertTrue(any("לא קונים" in e for e in ev), ev)
        self._score(self._item("c", "BBB"))
        self.assertIn("BBB", self.nt.book.positions)  # and a buy that passes is still made and journaled
        self.assertEqual([t["symbol"] for t in journal.read("news_trades.jsonl")], ["BBB"])
        self.assertEqual({e["where"] for e in journal.read("news_errors.jsonl")}, {"news_checks"})

    def test_on_trial_a_log_that_cannot_be_written_changes_nothing(self):
        self.nt.n["guards"] = "log"
        (self.tmp / "news_checks.jsonl").mkdir()
        self.answers = [{"kind": "analyst_or_commentary", "confirmed": False, "why": "x"}]
        ev = self._score(self._item(move=5.82))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["BUY"])
        self.assertFalse(any("לא קונים" in e for e in ev), ev)

    def test_a_score_row_carries_a_stamp_of_the_instruction_files_the_scorer_was_started_among(self):
        news_live._CONTEXT[:] = [0.0, None]
        first = news_live.context_id()
        self.assertRegex(first, r"^[0-9a-f]{12}$")  # the project's own CLAUDE.md is above the test's directory
        self._score(self._item())
        self.assertEqual(journal.read("news_scores.jsonl")[-1]["context"], first)
        with tempfile.TemporaryDirectory() as empty, mock.patch.object(news_live.Path, "cwd", lambda: Path(empty)):
            news_live._CONTEXT[:] = [0.0, None]
            other = news_live.context_id()
        news_live._CONTEXT[:] = [0.0, None]
        self.assertNotEqual(other, first)  # other files (or none) above the directory: another stamp

    def test_the_heartbeat_says_which_code_is_trading(self):
        calls = []

        def git(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="abc1234\n" if "rev-parse" in cmd else " M aitrader/news_live.py\n", stderr="")
        with mock.patch.object(news_live.subprocess, "run", git):
            stamp = news_live.code_stamp()
        self.assertEqual((stamp["commit"], stamp["dirty"]), ("abc1234", True))
        self.assertEqual(calls[1][:3], ["git", "status", "--porcelain"])
        with mock.patch.object(news_live.subprocess, "run", side_effect=OSError("no git")):
            self.assertEqual(news_live.code_stamp()["commit"], None)  # a record only: it never stops a start
        self.nt.code = stamp
        with mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
        self.assertEqual(journal.load_json("news_heartbeat.json")["code"]["commit"], "abc1234")



class NothingSlowBeforeASale(_Engine):
    """Found by the gate of 2026-11-10: the trial check and the catch-up each stood in front of a stop sale, and a
    trade was on the journal before the book was on disk."""

    def _held(self, sym="BBB", entry=50.0):
        self.nt.book.state["positions"][sym] = {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": "2026-11-09",
                                                "stop_price": round(entry * 0.97, 4)}

    def test_the_book_is_on_disk_as_soon_as_a_trade_is_on_the_journal(self):
        self._score(self._item())  # no step, no save by the caller
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["BUY"])
        self.assertIn("AAA", journal.load_json("news_book.json")["positions"])  # a kill now leaves no trade the book does not know
        self.prices["AAA"] = self.nt.book.positions["AAA"]["avg_cost"] * 0.96
        self.nt.check_stops([])
        self.assertEqual(journal.load_json("news_book.json")["positions"], {})  # and a sale cannot be made twice

    def test_a_book_that_cannot_be_saved_right_after_a_trade_does_not_lose_the_trade_or_its_report(self):
        with mock.patch.object(self.nt, "save", side_effect=OSError("disk full")):
            ev = self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertTrue(any(e.startswith("BUY") for e in ev), ev)
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["save_after_trade"])

    def test_on_trial_the_check_is_asked_in_the_background_and_holds_up_nothing(self):
        self.nt.n["guards"] = "log"
        gate, started = threading.Event(), threading.Event()

        def slow(item, model, timeout=60):  # the checker has not answered yet
            started.set()
            gate.wait(10)
            return dict(APPROVED)
        news_live.verify_headline = slow
        self._held()
        ev = []
        self.nt.handle_scored([self._item("a", "AAA"), self._item("c", "SPY")],
                              {"a": {"score": 9, "why": "x"}, "c": {"score": 9, "why": "x"}}, ev)
        try:
            self.assertTrue(started.wait(5))
            self.assertEqual({"AAA", "SPY"} <= set(self.nt.book.positions), True)  # both bought while the first check still runs
            self.assertEqual(len(self.nt._trial), 2)
            self.assertNotIn("second_check", [g for g, _ in self._verdicts()])  # nothing written by the background
            self.prices["BBB"] = 48.0
            self.nt.check_stops(ev)  # and a stop is not kept waiting by it
            self.assertNotIn("BBB", self.nt.book.positions)
            self.nt.drain_trial()  # nothing has come back: nothing is written, nothing is lost
            self.assertEqual(len(self.nt._trial), 2)
        finally:
            gate.set()
        self.nt.drain_trial(wait=5)
        self.assertEqual((self.nt._trial, [v for g, v in self._verdicts() if g == "second_check"]), ([], ["passed", "passed"]))

    def test_a_step_writes_down_the_trial_answers_that_have_come_back(self):
        self.nt.n["guards"] = "log"
        item = {**self._item(), "link": "", "published": journal.now_utc()}
        with mock.patch.object(self.nt, "poll_headlines", lambda: [item]), \
                mock.patch.object(news_live, "score_batch", lambda items, model: {"k1": {"score": 9, "why": "x"}}), \
                mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self.nt.step()
            self.assertTrue(all(box["done"].wait(5) for box, _, _ in self.nt._trial))  # the stub answers at once
            with mock.patch.object(self.nt, "poll_headlines", lambda: []):
                self.nt.step()
        self.assertEqual(self.nt._trial, [])
        self.assertIn(("second_check", "passed"), self._verdicts())

    def test_a_trial_answer_that_cannot_be_judged_costs_only_itself(self):
        self.nt.n["guards"] = "log"
        with mock.patch.object(self.nt, "_judge_second", side_effect=RuntimeError("boom")):
            self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["trial_check"])

    def test_enforced_the_stops_are_looked_at_right_after_the_check_and_before_the_buy(self):
        self._held()
        self.nt.n["block_buys_until_loss_reviewed"] = False  # or the stop's own loss would hold the buy back (next test)
        order = []

        def verify(item, model, timeout=60):  # while the check runs, a held name falls through its stop
            self.prices["BBB"] = 48.0
            return dict(APPROVED)
        news_live.verify_headline = verify
        real_log = self.nt._log_trade
        self.nt._log_trade = lambda f, ev: (order.append((f["side"], f["symbol"])), real_log(f, ev))[1]
        self._score(self._item())
        self.assertEqual(order, [("SELL", "BBB"), ("BUY", "AAA")])

    def test_a_stop_that_fires_during_the_enforced_check_holds_the_buy_back_for_the_review(self):
        self._held()

        def verify(item, model, timeout=60):
            self.prices["BBB"] = 48.0
            return dict(APPROVED)
        news_live.verify_headline = verify
        ev = self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})  # BBB sold at its stop; AAA not bought: a loss now waits for its review
        self.assertTrue(any("AAA" in e and "תוחקר" in e for e in ev), ev)

    def test_every_look_reads_the_live_quote_first_and_a_broken_catch_up_never_costs_it(self):
        self._held()
        self.prices["BBB"] = 48.0
        with mock.patch.object(self.nt, "catch_up_stops", side_effect=RuntimeError("bars down")):
            ev = []
            self.assertIs(self.nt._look_at_stops(ev), True)
        self.assertNotIn("BBB", self.nt.book.positions)
        self.assertEqual(journal.load_json("news_book.json")["positions"], {})  # the sale is on disk at once
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["catch_up_stops"])

    def test_a_look_between_batches_that_fails_does_not_cost_the_batches_still_to_be_scored(self):
        self._held()
        self.nt.n["guards"] = "log"  # the default: no look inside a batch
        self.nt.n["batch_max"] = 1
        items = [{**self._item("a", "AAA"), "link": "", "published": journal.now_utc()},
                 {**self._item("b", "BBB"), "link": "", "published": journal.now_utc()}]
        looks = []
        real = self.nt._look_at_stops

        def look(events, guarded=False):
            looks.append(guarded)
            if len(looks) == 2:  # the look between the two batches hits a fault
                if not guarded:
                    raise OSError("journal I/O")
                return False
            return real(events, guarded)
        with mock.patch.object(self.nt, "poll_headlines", lambda: items), \
                mock.patch.object(self.nt, "_look_at_stops", look), \
                mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True), \
                mock.patch.object(news_live, "score_batch", lambda chunk, model: {chunk[0]["key"]: {"score": 9 if chunk[0]["symbol"] == "AAA" else 1, "why": "x"}}):
            self.nt.step()
        self.assertEqual(looks, [True, True, False])  # top and between: guarded; the end reports its own failure
        self.assertNotIn("BBB", self.nt.book.positions)  # the bad news in the second batch was still scored and sold on

    def test_a_guarded_look_that_fails_says_so_and_an_unguarded_one_fails_the_step(self):
        self._held()
        with mock.patch.object(self.nt, "check_stops", side_effect=RuntimeError("quotes down")):
            self.assertIs(self.nt._look_at_stops([], guarded=True), False)
            with self.assertRaises(RuntimeError):
                self.nt._look_at_stops([])
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["early_stops"])

    def test_the_alert_for_a_failing_engine_says_the_truth_about_the_stops(self):
        for early, words in ((True, "הסטופים עדיין נבדקים"), (False, "לא נבדקים")):
            sent = []

            def step(nt, early=early):
                nt._early_look = early
                raise RuntimeError("scorer down")
            with mock.patch.object(news_live.NewsTrader, "step", step), \
                    mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \
                    mock.patch.object(news_live.time, "sleep", lambda s: None), \
                    mock.patch.object(news_live, "code_stamp", lambda: {"commit": "x", "dirty": False, "started": "now"}), \
                    mock.patch.object(news_live.notify, "send", lambda title, body, cfg, prio="default", **kw: sent.append(body) or ["x"]), \
                    mock.patch.object(news_live, "load_config", lambda: {**self.cfg, "news": {**self.cfg["news"], "alert_after_errors": 2}}):
                clock = iter([0.0] + [i * 30.0 for i in range(1, 200)])
                with mock.patch.object(news_live.time, "time", lambda: next(clock)):
                    news_live._run("23:59", 3.0, False)
            self.assertEqual(len([b for b in sent if "סיבובים ברצף" in b]), 1, sent)
            self.assertTrue(any(words in b for b in sent), (early, sent))


class QueueAndRecord(_Engine):
    def test_a_name_queued_while_the_check_was_on_trial_is_not_bought_once_it_is_enforced(self):
        self.nt.n["guards"] = "log"
        news_live.market_open_now = lambda: False
        self.answers = [{"kind": "analyst_or_commentary", "confirmed": False, "why": "x"}]
        self._score(self._item(move=None))  # queued for the open; the trial check says it would have refused
        self.assertEqual([(q["symbol"], q["second_check"], q["id"]) for q in self.nt.queue], [("AAA", None, "k1")])
        self.nt.n["guards"] = "enforce"  # the owner's answer comes overnight
        news_live.market_open_now = lambda: True
        ev = []
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}):
            self.nt.run_queue_at_open(ev)
        self.assertEqual((self.nt.book.positions, self.nt.queue), ({}, []))
        self.assertTrue(any("AAA" in e and "לפני שהבדיקה השנייה נכנסה לתוקף" in e for e in ev), ev)
        self.assertEqual(self._verdicts()[-1], ("second_check", "refused"))

    def test_a_name_that_passed_the_enforced_check_keeps_its_place(self):
        news_live.market_open_now = lambda: False
        self._score(self._item(move=None))
        self.assertEqual([q["second_check"] for q in self.nt.queue], ["passed"])
        news_live.market_open_now = lambda: True
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}):
            self.nt.run_queue_at_open([])
        self.assertIn("AAA", self.nt.book.positions)

    def test_a_queued_buy_that_fails_is_not_tried_again_at_every_step(self):
        self.nt.queue = [{"symbol": "AAA", "score": 9, "why": "w", "queued_at": journal.now_utc(), "second_check": "passed"}]
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}), \
                mock.patch.object(self.nt, "_buy", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.nt.run_queue_at_open([])
        self.assertEqual(self.nt.queue, [])  # dropping a buy is safe; a step that fails for ever is not

    def test_a_buy_that_was_not_made_for_lack_of_room_is_said_and_written(self):
        self.prices["AAA"] = 6000.0  # one share costs more than 5% of the book
        ev = self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("AAA" in e and "לא קונים" in e and "תקציב" in e for e in ev), ev)
        self.assertEqual(self._verdicts()[-1], ("no_room", "refused"))
        self.prices["AAA"] = 100.0
        self.nt.n["max_gross"] = 0.04  # the book is full
        ev = self._score(self._item("b"))
        self.assertTrue(any("התיק מלא" in e for e in ev), ev)
        self.assertEqual([(c["guard"], c["id"]) for c in self._checks() if c["guard"] == "no_room"], [("no_room", "k1"), ("no_room", "b")])

    def test_every_row_of_one_headline_carries_its_id_and_a_buy_writes_its_own_row(self):
        self._score(self._item("h1", move=1.5))
        rows = self._checks()
        self.assertEqual([(c["guard"], c["verdict"], c["id"]) for c in rows], [("second_check", "passed", "h1"), ("", "bought", "h1")])
        self.assertEqual((rows[1]["price"], rows[1]["day_move_pct"]), (round(100.0 * 1.001, 4), 1.5))
        self._score(self._item("h2", "BBB", move=5.0))
        self.assertEqual([(c["guard"], c["verdict"], c["id"]) for c in self._checks()[2:]],
                         [("second_check", "passed", "h2"), ("no_chase", "refused", "h2")])


class WordsInConfig(_Engine):
    def test_a_word_the_code_does_not_know_is_read_as_the_safe_side_and_said_out_loud(self):
        for key, word, safe in (("stop_catchup", "Sell", "alert"), ("stop_catchup", True, "alert"), ("guards", "on", "log"),
                                ("guards", "ENFORCE", "log")):
            self.sent.clear()
            cfg = copy.deepcopy(self.cfg)
            cfg["news"][key] = word
            nt = news_live.NewsTrader(cfg)
            self.assertEqual(nt.n[key], safe, (key, word))
            self.assertEqual([p for p, b in self.sent if key in b], ["urgent"], (key, word))
        self.sent.clear()
        for key, word in (("stop_catchup", "off"), ("stop_catchup", "sell"), ("guards", "enforce"), ("guards", "log")):
            cfg = copy.deepcopy(self.cfg)
            cfg["news"][key] = word
            self.assertEqual(news_live.NewsTrader(cfg).n[key], word)
        self.assertEqual(self.sent, [])


class SaidWhateverHappens(_Engine):
    """Quant gate of 2026-11-10: a sale made at the top of a step was saved, and its alert was lost when anything
    further down the step raised."""

    def _held_under_its_stop(self):
        self.nt.book.state["positions"] = {"BBB": {"qty": 10, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5,
                                                   "entry_date": "2026-11-09"}}
        self.prices["BBB"] = 48.0

    def test_a_sale_at_the_top_of_a_step_is_said_even_when_the_step_then_fails(self):
        self._held_under_its_stop()
        with mock.patch.object(self.nt, "poll_headlines", side_effect=RuntimeError("feeds down")):
            with self.assertRaises(RuntimeError):
                self.nt.step()
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["SELL"])
        self.assertEqual(len([b for p, b in self.sent if "SELL 10 BBB" in b]), 1)  # the owner hears of the sale
        self.assertTrue(any(e.startswith("SELL") for e in self.nt.last_events))  # and the loop can still print it

    def test_an_alert_that_cannot_be_sent_does_not_hide_the_error_of_the_step(self):
        self._held_under_its_stop()
        news_live.notify.send = mock.Mock(side_effect=OSError("no network"))
        with mock.patch.object(self.nt, "poll_headlines", side_effect=RuntimeError("feeds down")):
            with self.assertRaises(RuntimeError):  # the step's own error, not the alert's
                self.nt.step()
        self.assertIn("step_alert", [e["where"] for e in journal.read("news_errors.jsonl")])

    def test_a_scorer_reply_in_a_shape_nobody_expected_is_a_skipped_row_not_a_failed_step(self):
        items = [{"key": "a", "symbol": "AAA", "title": "t", "published": "2026-11-10T15:00:00+00:00", "day_move_pct": 0.1},
                 {"key": "b", "symbol": "BBB", "title": "t", "published": "2026-11-10T15:00:00+00:00", "day_move_pct": 0.1}]

        def reply(result):
            return lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(result), stderr="")
        rows = [{"id": 0, "symbol": "AAA", "score": "high", "why": "x"}, {"id": 1, "symbol": "BBB", "score": 7, "why": "ok"},
                {"id": 0, "symbol": "AAA", "score": None}, "not a row", {"id": "x"},
                {"id": 0, "symbol": "AAA", "score": float("inf")}, {"id": 1e999, "symbol": "AAA", "score": 9}]
        with mock.patch.object(news_live.subprocess, "run", reply({"result": json.dumps(rows)})):
            self.assertEqual(news_live.score_batch(items, "m"), {"b": {"score": 7, "why": "ok"}})
        for envelope in ([1, 2], "text", {"result": None}, {"result": '{"not": "a list"}'}):
            with mock.patch.object(news_live.subprocess, "run", reply(envelope)):
                self.assertEqual(news_live.score_batch(items, "m"), {}, envelope)

    def test_on_trial_a_guard_that_cannot_be_worked_out_changes_nothing_and_enforced_it_refuses(self):
        journal.append("news_trades.jsonl", {"symbol": "AAA", "side": "SELL", "qty": 1, "price": 96.5, "realized_pnl": 0.0,
                                             "reason": "stop -3% (a hand-written row with no date)"})
        self.nt.n["guards"] = "log"
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)  # the buy the engine made before this guard existed is still made
        self.assertIn("stop_cooldown", [e["where"] for e in journal.read("news_errors.jsonl")])
        self.nt.book.state["positions"] = {}
        self.nt.n["guards"] = "enforce"
        ev = self._score(self._item("b"))
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("לא קונים" in e for e in ev), ev)

    def test_the_end_of_a_run_does_not_keep_the_book_locked_for_a_record(self):
        self.nt.n["guards"] = "log"
        gate = threading.Event()
        news_live.verify_headline = lambda item, model, timeout=60: (gate.wait(10), dict(APPROVED))[1]
        self.nt.handle_scored([self._item()], {"k1": {"score": 9, "why": "x"}}, [])
        try:
            t0 = time.time()
            self.nt.drain_trial(wait=0.2)  # the answer is still out: the wait is bounded, the record stays owed
            self.assertLess(time.time() - t0, 2.0)
            self.assertEqual(len(self.nt._trial), 1)
        finally:
            gate.set()
        self.nt.drain_trial(wait=5)
        self.assertEqual(self.nt._trial, [])
        self.assertEqual(news_live.DEFAULTS["verify_parallel"], 1)

    def test_a_run_that_ends_in_market_hours_does_not_wait_for_a_trial_answer(self):
        gate = threading.Event()
        news_live.verify_headline = lambda item, model, timeout=60: (gate.wait(20), dict(APPROVED))[1]
        waits = []

        def step(nt):
            if not nt._trial:  # one check goes out, and the run ends right after
                nt._ask_later(self._item(), {"score": 9, "why": "x"})
            return []
        real = news_live.NewsTrader.drain_trial
        try:
            for is_open, expected in ((True, 0), (False, self.cfg["news"]["verify_timeout_seconds"])):
                news_live.market_open_now = lambda is_open=is_open: is_open
                with mock.patch.object(news_live.NewsTrader, "step", step), \
                        mock.patch.object(news_live.NewsTrader, "drain_trial", lambda nt, wait=0.0: waits.append(wait)), \
                        mock.patch.object(news_live.time, "sleep", lambda s: None), \
                        mock.patch.object(news_live, "code_stamp", lambda: {"commit": "x", "dirty": False, "started": "now"}), \
                        mock.patch.object(news_live, "load_config", lambda: self.cfg):
                    news_live._run("23:59", 0.0005, False)
                self.assertEqual(waits[-1], expected, is_open)  # open: the lock is not kept for a record; closed: one call's time
        finally:
            gate.set()
        self.assertIs(news_live.NewsTrader.drain_trial, real)

    def test_the_trial_check_runs_on_threads_that_cannot_keep_the_engine_alive(self):
        self.nt.n["guards"] = "log"
        gate, names = threading.Event(), []

        def slow(item, model, timeout=60):
            names.append((threading.current_thread().daemon, threading.current_thread().name))
            gate.wait(10)
            return dict(APPROVED)
        news_live.verify_headline = slow
        news_live.rescore_headline = lambda item, model, timeout=None: (names.append((threading.current_thread().daemon, "r")), 10)[1]
        self.nt.handle_scored([self._item()], {"k1": {"score": 9, "why": "x"}}, [])
        try:
            deadline = time.time() + 5
            while len(names) < 3 and time.time() < deadline:
                time.sleep(0.01)
            self.assertGreaterEqual(len(names), 3)  # both looks and the rescore
            self.assertTrue(all(d for d, _ in names), names)  # every one of them on a daemon thread
            self.assertTrue(all(t.daemon for t in threading.enumerate() if t.name == "trial-check"))
        finally:
            gate.set()
        self.nt.drain_trial(wait=5)

    def test_a_trial_check_that_cannot_even_be_started_costs_only_its_record(self):
        self.nt.n["guards"] = "log"
        self.nt.book.state["positions"]["BBB"] = {"qty": 10, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5,
                                                  "entry_date": "2026-11-09"}
        with mock.patch.object(news_live.threading, "Thread", side_effect=RuntimeError("can't start new thread")):
            self.nt.handle_scored([self._item("a", "AAA"), self._item("b", "BBB")],
                                  {"a": {"score": 9, "why": "x"}, "b": {"score": 1, "why": "fraud"}}, [])
        self.assertIn("AAA", self.nt.book.positions)
        self.assertNotIn("BBB", self.nt.book.positions)  # the bad-news sale behind the buy in the same batch is still made
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["trial_check"])

    def test_a_save_in_the_middle_of_a_step_leaves_the_seen_marks_alone(self):
        self.nt.seen = {"polled-not-scored-yet": journal.now_utc()}
        self._score(self._item())  # a buy: the book goes to disk at once
        self.assertIn("AAA", journal.load_json("news_book.json")["positions"])
        self.assertIsNone(journal.load_json("news_seen.json", None))  # an engine killed now will poll that headline again
        self.prices["AAA"] = self.nt.book.positions["AAA"]["avg_cost"] * 0.96
        self.nt._look_at_stops([])
        self.assertIsNone(journal.load_json("news_seen.json", None))
        self.nt.save()  # the end of a step: now the marks are written
        self.assertEqual(list(journal.load_json("news_seen.json")), ["polled-not-scored-yet"])

    def test_the_heartbeat_stamp_is_the_oldest_look_among_the_names_still_held(self):
        now = datetime.now(timezone.utc)
        self.nt.book.state["positions"] = {
            "AAA": {"qty": 1, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0, "entry_date": "2026-11-09"},
            "BBB": {"qty": 1, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5, "entry_date": "2026-11-09"}}
        news_live.QUOTE_TIME["AAA"] = now.isoformat()  # AAA has a live quote; BBB has had none for ten minutes
        self.nt._covered["BBB"] = now - timedelta(minutes=10)
        self.nt.n["stop_catchup"] = "off"
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), \
                mock.patch.object(journal, "session_hours", lambda d: ((0, 0), (23, 59))):
            self.nt.step()
        stamp = datetime.fromisoformat(journal.load_json("news_heartbeat.json")["stops_checked_at"])
        self.assertAlmostEqual((now - stamp).total_seconds(), 600, delta=5)  # a restart reads BBB's ten minutes back

    def test_a_stretch_of_an_earlier_day_is_not_read_back_and_the_owner_is_told_once(self):
        self.nt.n["stop_catchup"] = "alert"
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 98.5, "stop_price": 97.0,
                                                   "entry_date": "2026-11-06"}}
        now = datetime(2026, 11, 10, 10, 0, tzinfo=NY)
        last = datetime(2026, 11, 9, 11, 0, tzinfo=NY).astimezone(timezone.utc)  # yesterday 11:00: five session hours unseen
        for _ in range(2):
            self.nt._covered.clear()
            self.nt.catch_up_stops([], now, last=last)
        told = [b for p, b in self.sent if p == "urgent" and "09.11 11:00" in b]
        self.assertEqual(len(told), 1, self.sent)
        self.assertIn("רק את המחירים של היום", told[0])
        for hh, mm, ss in ((16, 3, 0), (15, 59, 45), (15, 58, 40)):  # a run that reached the bell missed nothing
            self.sent.clear()
            self.nt._earlier_told = set()
            self.nt._covered.clear()
            self.nt.catch_up_stops([], now, last=datetime(2026, 11, 9, hh, mm, ss, tzinfo=NY).astimezone(timezone.utc))
            self.assertEqual([b for p, b in self.sent if "לא נבדק מאז" in b], [], (hh, mm, ss))


class OnTrial(_Engine):
    """The default. no_chase, the second check and the stop cooldown are new rules resting on one loss, so until the
    owner decides they only write down what they would have refused. The repairs refuse either way."""
    COMMENT = {"kind": "analyst_or_commentary", "confirmed": False, "why": "a TV guest's forecast"}

    def setUp(self):
        super().setUp()
        del self.cfg["news"]["guards"]  # config does not say: the default decides
        self.nt = news_live.NewsTrader(self.cfg)

    def test_the_default_is_the_trial_in_the_code_and_in_config(self):
        self.assertEqual((news_live.DEFAULTS["guards"], self.nt.n["guards"], CFG["news"]["guards"]), ("log", "log", "log"))
        self.assertEqual(set(news_live.TRIAL_GUARDS), {"no_chase", "second_check", "stop_cooldown"})

    def test_a_stock_already_up_is_bought_and_the_record_says_what_the_guard_would_have_done(self):
        ev = self._score(self._item(move=5.82))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertFalse(any("לא קונים" in e for e in ev), ev)
        row = next(c for c in self._checks() if c["guard"] == "no_chase")
        self.assertEqual((row["verdict"], row["day_move_pct"], row["limit"], row["price"]), ("would_refuse", 5.82, 3.0, 100.0))

    def test_commentary_is_bought_at_the_first_quote_and_the_check_is_asked_only_after(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())
        held_when_asked = []

        def verify(i, model, timeout=60):  # while the check runs the price moves; the buy must not have waited for it
            held_when_asked.append("AAA" in self.nt.book.positions)
            self.prices["AAA"] = 101.0
            return dict(self.COMMENT)
        news_live.verify_headline = verify
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            ev = self._score(item)
        self.assertAlmostEqual(self.nt.book.positions["AAA"]["avg_cost"], 100.0 * 1.001, places=6)
        self.assertEqual(held_when_asked, [True, True])
        self.assertFalse(any("לא קונים" in e for e in ev), ev)
        self.assertEqual(self._verdicts()[-1], ("second_check", "would_refuse"))

    def test_a_low_rescore_is_written_down_and_does_not_stop_the_buy(self):
        self.rescores = [7]
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        last = self._checks()[-1]
        self.assertEqual((last["guard"], last["verdict"], last["rescore"]), ("second_check", "would_refuse", 7))

    def test_a_name_stopped_out_today_is_bought_back_and_it_is_on_record(self):
        self._stop_row(0)
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertIn(("stop_cooldown", "would_refuse"), self._verdicts())

    def test_a_queued_buy_into_a_gap_is_filled_and_recorded(self):
        self.moves["AAA"] = 6.0
        self._queued()
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(self._verdicts(), [("no_chase", "would_refuse"), ("", "bought")])
        self.assertEqual({c["id"] for c in self._checks()}, {"q1"})  # both rows name the headline

    def test_commentary_after_the_close_is_queued_and_recorded(self):
        news_live.market_open_now = lambda: False
        self.answers = [dict(self.COMMENT)]
        self._score(self._item(move=None))
        self.assertEqual([q["symbol"] for q in self.nt.queue], ["AAA"])
        self.assertEqual(self._verdicts(), [("second_check", "would_refuse")])

    def test_the_repairs_refuse_on_trial_too(self):
        ev = self._score(self._item(move=None))  # missing data, no trade (Basic law, item 1)
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("AAA" in e and "לא ידוע" in e for e in ev), ev)
        self.assertIn(("unknown_move", "refused"), self._verdicts())

    def test_while_buys_are_held_every_guard_still_leaves_its_record(self):
        news_live.set_hold("waiting for the owner")
        ev = self._score(self._item(move=5.82))
        self.assertEqual(self.nt.book.positions, {})
        self.assertEqual(self._verdicts(), [("no_chase", "would_refuse"), ("hold", "refused"), ("second_check", "passed")])
        hold = self._checks()[1]
        self.assertEqual((hold["price"], hold["day_move_pct"]), (100.0, 5.82))  # what the buy would have paid
        said = [e for e in ev if "לא קונים" in e]
        self.assertEqual(len(said), 1)  # one line to the owner, and it is the hold's
        self.assertIn("waiting for the owner", said[0])

    def test_anything_but_the_word_enforce_is_the_trial(self):
        for word in ("ENFORCE", "on", True, None, ""):
            self.nt.n["guards"] = word
            self.nt.book.state["positions"] = {}
            self._score(self._item(f"k{word}", move=5.82))
            self.assertIn("AAA", self.nt.book.positions, word)


class Hold(_Engine):
    """news-hold: the trader session's veto on the news book. It can stop buys and nothing else."""

    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_a_hold_stops_a_buy_and_a_queued_buy_and_never_a_sale(self):
        self._score(self._item("b", "BBB"))  # bought before the hold
        news_live.set_hold("the edge is not proven yet")
        ev = self._score(self._item())
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("AAA" in e and "the edge is not proven yet" in e for e in ev), ev)
        self._queued()
        self.assertNotIn("AAA", self.nt.book.positions)
        self.prices["BBB"] = self.nt.book.positions["BBB"]["avg_cost"] * 0.96
        self.nt.check_stops([])
        self.assertNotIn("BBB", self.nt.book.positions)  # the stop sells through the hold

    def test_a_hold_and_its_release_need_a_reason_and_both_are_on_record(self):
        for nothing in ("", "   ", None):
            with self.assertRaises(ValueError):
                news_live.set_hold(nothing)
            with self.assertRaises(ValueError):
                news_live.set_hold(nothing, release=True)
        self.assertIsNone(news_live.buy_hold())
        self.assertEqual(journal.read("news_holds.jsonl"), [])
        news_live.set_hold("reason one")
        self.assertEqual(news_live.buy_hold()["reason"], "reason one")
        self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        news_live.set_hold("Nimrod: go on", release=True)
        self.assertIsNone(news_live.buy_hold())
        self._score(self._item("b"))
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual([(r["action"], r["reason"]) for r in journal.read("news_holds.jsonl")],
                         [("hold", "reason one"), ("release", "Nimrod: go on")])

    def test_a_hold_file_that_cannot_be_used_is_a_hold(self):
        for i, bad in enumerate(("{not json", "[1, 2]", '{"reason": " "}', '"x"', '{"since": "2026-11-10"}')):
            (self.tmp / "news_hold.json").write_text(bad)
            self.assertIsNotNone(news_live.buy_hold(), bad)
            self._score(self._item(f"k{i}"))
            self.assertEqual(self.nt.book.positions, {}, bad)
        for free in ("{}", "null"):
            (self.tmp / "news_hold.json").write_text(free)
            self.assertIsNone(news_live.buy_hold(), free)

    def test_the_heartbeat_says_why_buys_are_blocked(self):
        with mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
            self.assertIsNone(journal.load_json("news_heartbeat.json")["buys_blocked"])
            news_live.set_hold("x y z")
            self.nt.step()
            self.assertEqual(journal.load_json("news_heartbeat.json")["buys_blocked"], "hold")

    def test_a_ledger_that_cannot_be_read_is_in_the_heartbeat_without_filling_the_error_journal(self):
        with mock.patch.object(news_live.postmortem, "pending", side_effect=OSError("disk")), \
                mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
            self.nt.step()
            self.assertEqual(journal.load_json("news_heartbeat.json")["buys_blocked"], "loss_review")
            self.assertEqual(journal.read("news_errors.jsonl"), [])  # every 20 seconds would be 4,000 rows a day
            self._score(self._item())  # a refused buy does put it on record
        self.assertEqual(self.nt.book.positions, {})
        self.assertEqual([e["where"] for e in journal.read("news_errors.jsonl")], ["postmortem"])

    def test_the_command_sets_and_lifts_it_and_verify_and_status_show_it(self):
        code, _, err = self._run("news-hold", "--reason", "   ")
        self.assertEqual((code, news_live.buy_hold()), (2, None))
        code, out, err = self._run("news-hold", "--reason", "edge not proven")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hold"]["reason"], "edge not proven")
        self.assertIn("push", err)  # a hold that is not pushed is lost with the container
        _, out, _ = self._run("verify")
        self.assertIn("NEWS BUYS ON HOLD", out)
        self.assertIn("edge not proven", out)
        _, out, _ = self._run("news-status")
        self.assertEqual(json.loads(out)["buy_hold"]["reason"], "edge not proven")
        code, out, _ = self._run("news-hold", "--release", "--reason", "Nimrod said go")
        self.assertEqual((code, json.loads(out)["hold"], json.loads(out)["released"]), (0, None, "Nimrod said go"))
        _, out, _ = self._run("verify")
        self.assertNotIn("NEWS BUYS ON HOLD", out)
        self.assertIsNone(json.loads(self._run("news-status")[1])["buy_hold"])


class PauseSaidAtOnce(_Engine):
    def _stop_out(self):
        self._score(self._item())
        self.prices["AAA"] = self.nt.book.positions["AAA"]["avg_cost"] * 0.96
        ev = []
        self.nt.check_stops(ev)
        self.assertNotIn("AAA", self.nt.book.positions)
        return ev

    def test_a_losing_sale_tells_the_owner_that_buys_now_wait_for_the_review(self):
        ev = self._stop_out()
        self.assertEqual([e[:4] for e in ev], ["SELL", "נמכר"])
        self.assertIn("יתוחקר", ev[1])

    def test_with_the_switch_off_or_on_a_winning_sale_nothing_is_added(self):
        self.nt.n["block_buys_until_loss_reviewed"] = False
        self.assertEqual([e[:4] for e in self._stop_out()], ["SELL"])
        self.nt.n["block_buys_until_loss_reviewed"] = True
        self.prices["BBB"] = 50.0
        self._score(self._item("b", "BBB"))
        self.assertNotIn("BBB", self.nt.book.positions)  # the loss above is still waiting
        self.nt.n["block_buys_until_loss_reviewed"] = False
        self._score(self._item("c", "BBB"))
        self.nt.n["block_buys_until_loss_reviewed"] = True
        self.nt.n["max_hold_days"] = 1
        self.nt.book.positions["BBB"]["entry_date"] = "2026-01-02"
        self.prices["BBB"] = 60.0
        ev = []
        self.nt.check_stops(ev)
        self.assertNotIn("BBB", self.nt.book.positions)
        self.assertEqual([e[:4] for e in ev], ["SELL"])  # sold at a gain: no pause starts


if __name__ == "__main__":
    unittest.main()
