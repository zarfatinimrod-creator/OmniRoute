"""Pins for the loss protocol and the news-engine repairs of 2026-11-10 (commit e6a82895).

A mutation run changed one line at a time in news_live.py, postmortem.py and __main__.py (420 changes). Some changed what
the engine does and still passed the whole suite. Every method here fails on at least one of them: an unknown move
turned into "flat" on its way to the scorer, a trade changed by a guard that is only on trial, a sale held back by a
hold, a buy let through a hold or a waiting review, a stop look skipped, delayed or not saved, a loss cleared by a key
that is too short.

Each class extends the class of tests/test_news_guards.py or tests/test_postmortem.py that its methods belong in (same
name, without the "_") and uses that class's helpers. They live in a file of their own because those two files were
claimed by another session when these were written (BUILD_CLAIMS.md); fold them into their classes when the files are
free. load_tests() at the bottom runs only the methods written here, not the ones the parents have."""

import contextlib
import copy
import io
import json
import subprocess
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import test_news_guards as g
import test_postmortem as p
from aitrader import journal, news_live, postmortem
from test_core import APPROVED, CFG

NY = ZoneInfo("America/New_York")
REVIEW = p.REVIEW  # tests/test_postmortem.py has it under this name


def _checks_over(seconds=30):
    """A second check on trial is asked on a background thread named "trial-check" (news_live._ask_later), and when
    that thread gets to run it calls whatever news_live.verify_headline is by then. So no test here starts, and none
    ends, while one is out: an answer asked for in one test must not be given by another test's stand-in."""
    for t in threading.enumerate():
        if t.name == "trial-check":
            t.join(seconds)


class _ChecksOver:
    """First in the bases of every class here. The parents' own setUp and tearDown do not wait for these threads,
    and they live in the two claimed files; when the methods are folded in, the wait belongs in the parents."""

    def setUp(self):
        _checks_over()  # one that an earlier test left out must not answer into this test
        super().setUp()

    def tearDown(self):
        _checks_over()  # and this test's own are over before the parent takes its answers away
        super().tearDown()


class Hold_(_ChecksOver, g.Hold):
    def test_a_hold_holds_back_no_kind_of_sale(self):
        """The price stop has its own test (test_a_hold_stops_a_buy_and_a_queued_buy_and_never_a_sale). These are the
        other ways out of a position: a bad-news score, the owner's exit, a stop that was traded through unseen
        (selling mode) and the time exit."""
        news_live.set_hold("no buys until the owner answers")

        def held():
            self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0,
                                                       "stop_price": 97.0, "entry_date": "2026-11-09"}}

        def sold_for():
            self.assertEqual(self.nt.book.positions, {})
            return journal.read("news_trades.jsonl")[-1]["reason"]

        held()  # 1. a bad-news score
        self._score(self._item("bad"), score=1)
        self.assertTrue(sold_for().startswith("bad news score 1"), sold_for())
        self.assertTrue(news_live.postmortem.pending("news"))  # sold under its cost: from here on a review waits as well
        # one day all through: the mark of case 3 stays "found today" when the wall clock's day turns (UTC: an evening here)
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True), \
                mock.patch.object(journal, "now_utc", lambda: "2026-11-10T15:00:00+00:00"):
            held()  # 2. the owner's exit
            news_live.update_exits(put={"AAA": {"reason": "owner wants out", "requested_at": journal.now_utc()}})
            self.nt.check_stops([])
            self.assertTrue(sold_for().startswith("operator exit: owner wants out"), sold_for())
            held()  # 3. a stop that was traded through unseen, in the selling mode
            self.nt.n["stop_catchup"] = "sell"
            self.nt.book.positions["AAA"]["stop_breach"] = {"low": 96.0, "at": "09:32", "found_at": journal.now_utc()}
            self.nt.check_stops([])
            self.assertTrue(sold_for().startswith("stop -3% traded through while unwatched"), sold_for())
        held()  # 4. the time exit
        self.nt.n["max_hold_days"] = 1
        self.nt.book.positions["AAA"]["entry_date"] = "2026-01-02"
        self.nt.check_stops([])
        self.assertTrue(sold_for().startswith("time exit after"), sold_for())
        self.assertEqual(news_live.buy_hold()["reason"], "no buys until the owner answers")  # the hold was there all along

    def test_a_hold_and_a_waiting_review_stop_a_buy_outside_the_hours_too(self):
        """trade_outside_hours is off by default; when it is on the buy has no move to be judged on (_NO_MOVE),
        and the block must still be asked."""
        self.nt.n["trade_outside_hours"] = True
        news_live.market_open_now = lambda: False
        self._score(self._item("b", "BBB", move=None))
        self.assertIn("BBB", self.nt.book.positions)  # the path is alive: without a block it buys
        news_live.set_hold("no buys until the owner answers")
        ev = self._score(self._item(move=None))
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("AAA" in e and "no buys until the owner answers" in e for e in ev), ev)
        news_live.set_hold("go on", release=True)
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "SPY", "side": "SELL", "qty": 1, "price": 480.0,
                                             "realized_pnl": -20.0, "reason": "stop -3% (entry 500.00, now 480.00)"})
        self._score(self._item("c", move=None))
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertIn(("loss_review", "refused"), self._verdicts())  # the hold is lifted: it is the review that says no now

    def test_the_hold_stops_buys_also_when_the_wait_for_the_review_is_switched_off(self):
        self.nt.n["block_buys_until_loss_reviewed"] = False  # two separate switches: the hold has none
        news_live.set_hold("no buys until the owner answers")
        ev = self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.assertTrue(any("no buys until the owner answers" in e for e in ev), ev)
        self.assertIn(("hold", "refused"), self._verdicts())

    def test_only_null_or_an_empty_object_is_no_hold(self):
        for i, odd in enumerate(("[]", "false", "0", '""')):  # a damaged file: not what news-hold --release writes
            (self.tmp / "news_hold.json").write_text(odd)
            self.assertIsNotNone(news_live.buy_hold(), odd)
            self._score(self._item(f"k{i}"))
            self.assertEqual(self.nt.book.positions, {}, odd)

    def test_a_hold_file_nested_too_deep_to_parse_is_a_hold_not_a_failed_step(self):
        (self.tmp / "news_hold.json").write_text("[" * 100000, encoding="utf-8")  # json raises RecursionError, not ValueError
        self.assertIsNotNone(news_live.buy_hold())
        self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        with mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()  # the heartbeat asks at every step: it must come back
        self.assertEqual(journal.load_json("news_heartbeat.json")["buys_blocked"], "hold")

    def test_a_hold_that_could_not_be_fully_written_says_which_state_it_is_in(self):
        (self.tmp / "news_holds.jsonl").mkdir()  # the record of changes cannot be written; the hold file itself can
        for argv in (("news-hold", "--reason", "edge not proven"), ("news-hold", "--release", "--reason", "Nimrod said go")):
            code, out, err = self._run(*argv)
            self.assertEqual((code, out), (1, ""), argv)  # never a clean exit, and nothing that reads as done
            now = news_live.buy_hold()  # what the engine goes by from here on
            self.assertIn("The hold is now " + ("NOT set" if now is None else f"SET ({now['reason']})"), err, argv)
            if "--release" not in argv:
                self.assertEqual(now["reason"], "edge not proven")  # setting a hold takes effect even with no record

    def test_the_heartbeat_and_the_record_name_a_waiting_review_as_the_reason_not_a_hold(self):
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "BBB", "side": "SELL", "qty": 1, "price": 48.0,
                                             "realized_pnl": -2.0, "reason": "stop -3% (entry 50.00, now 48.00)"})
        self._score(self._item())
        self.assertEqual(self.nt.book.positions, {})
        self.assertIn(("loss_review", "refused"), self._verdicts())
        self.assertNotIn("hold", [guard for guard, _ in self._verdicts()])
        with mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
        self.assertEqual(journal.load_json("news_heartbeat.json")["buys_blocked"], "loss_review")

    def test_a_ledger_that_cannot_be_read_blocks_even_when_that_cannot_be_written_down(self):
        (self.tmp / "news_errors.jsonl").mkdir()  # the error journal cannot be written either
        with mock.patch.object(news_live.postmortem, "pending", side_effect=OSError("disk")):
            self._score(self._item())  # must come back, not raise: the rest of the step comes after it
        self.assertEqual(self.nt.book.positions, {})
        self.assertIn(("loss_review", "refused"), self._verdicts())

    def test_verify_survives_a_hold_it_cannot_judge(self):
        with mock.patch.object(news_live, "buy_hold", side_effect=RuntimeError("boom")):
            code, out, _ = self._run("verify")
        self.assertEqual(code, 0)
        self.assertIn("ALL CHAINS OK", out)
        self.assertIn("RuntimeError", out)  # said, never fatal: a session stops on verify's exit 1

    def test_verify_shows_a_hold_and_a_waiting_loss_together_and_still_does_not_stop_the_session(self):
        """Buys are on hold and the next losing sale comes before the hold is lifted (the stock and crypto books go
        on trading under a news hold). verify shows both and exits 0: exit 1 is kept for a broken chain, on which a
        session stops (skills/trader/SKILL.md, section 0)."""
        news_live.set_hold("no buys until the owner answers")
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "AAA", "side": "SELL", "qty": 5, "price": 96.5,
                                             "realized_pnl": -17.5, "reason": "stop -3% (entry 100.00, now 96.50)",
                                             "logged_at": journal.now_utc()})
        code, out, _ = self._run("verify")
        self.assertIn("ALL CHAINS OK", out)
        self.assertIn("LOSSES AWAITING REVIEW: 1 (-$17.50)", out)
        self.assertIn("NEWS BUYS ON HOLD", out)
        self.assertIn("no buys until the owner answers", out)
        self.assertEqual(code, 0)


class OnTrial_(_ChecksOver, g.OnTrial):
    def test_on_trial_the_buy_is_made_at_the_quote_the_scorer_saw_and_no_newer_quote_is_asked_for(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())
        asked, quote = [], news_live.live_price

        def newer(sym):  # what a quote asked for after the scoring would say: the stock has run to 104.00, +4%
            asked.append(sym)
            return (104.0, 4.0) if sym == "AAA" else quote(sym)
        news_live.live_price = newer
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self._score(item)
        self.assertNotIn("AAA", asked)  # only the enforced check re-quotes; on trial nothing stands between score and buy
        self.assertAlmostEqual(self.nt.book.positions["AAA"]["avg_cost"], 100.0 * 1.001, places=6)
        self.assertNotIn("no_chase", [guard for guard, _ in self._verdicts()])  # judged on the move the scorer saw (0.0)

    def test_in_the_live_loop_a_move_that_is_not_known_stays_not_known_for_the_scorer_and_for_the_buy(self):
        """The wiring from step() to the scorer and to _buy, in the default mode. "Flat" for "not known" was the
        wrong input behind the MU buy (2026-11-09), and it would also switch require_known_move off without a word."""
        item = {"key": "k1", "symbol": "AAA", "title": "AAA wins a contract", "link": "", "published": journal.now_utc()}
        self.moves["AAA"] = None  # a price, and no usable daily bars behind it: today's move is not known
        told = []

        def scorer(items, model):
            told.extend(copy.deepcopy(items))
            return {"k1": {"score": 9, "why": "x"}}
        with mock.patch.object(self.nt, "poll_headlines", lambda: [item]), mock.patch.object(news_live, "score_batch", scorer), \
                mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self.nt.step()
        self.assertEqual([(x["symbol"], x["day_move_pct"]) for x in told], [("AAA", None)])  # null to the scorer, never 0.0
        self.assertIsNone(journal.read("news_scores.jsonl")[-1]["day_move_pct"])
        self.assertEqual(self.nt.book.positions, {})  # missing data, no trade (Basic law, item 1)
        self.assertIn(("unknown_move", "refused"), self._verdicts())

    def test_the_fallbacks_in_the_code_say_what_config_says(self):
        """Numbers live in config.json; DEFAULTS is what the engine does when a key is missing from it, and a
        fallback that disagrees is a rule nobody chose. Every key, not a list kept by hand: the next key added to
        DEFAULTS is covered on the day it is added."""
        for key, fallback in news_live.DEFAULTS.items():
            self.assertIn(key, CFG["news"], key)
            self.assertEqual(fallback, CFG["news"][key], key)

    def test_with_the_check_switched_off_nothing_is_asked_on_trial_either(self):
        self.nt.n["verify_buys"] = False
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(self.asked, [])
        self.assertNotIn("second_check", [guard for guard, _ in self._verdicts()])


class SecondCheck_(_ChecksOver, g.SecondCheck):
    def test_a_move_that_is_no_longer_known_after_the_check_is_not_bought(self):
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())

        def verify(i, model, timeout=60):  # the quote asked for after the check has a price but no move
            self.moves["AAA"] = None
            return dict(APPROVED)
        news_live.verify_headline = verify
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self._score(item)
        self.assertEqual(self.nt.book.positions, {})  # the move from before the check (0.0) is not a stand-in
        self.assertIn(("unknown_move", "refused"), self._verdicts())

    def test_the_rescore_goes_to_the_scorer_itself_and_both_calls_get_the_timeout_from_config(self):
        self.cfg["news"].update({"verify_model": "some-model", "verify_timeout_seconds": 7})
        self.nt = news_live.NewsTrader(self.cfg)
        seen = {}

        def rescore(item, model, timeout=None):
            seen["rescore"] = (model, timeout)
            return 10

        def verify(item, model, timeout=60):
            seen["verify"] = (model, timeout)
            return dict(APPROVED)
        news_live.rescore_headline, news_live.verify_headline = rescore, verify
        self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        self.assertEqual(seen, {"rescore": (self.nt.n["model"], 7), "verify": ("some-model", 7)})

    def test_with_the_check_switched_off_an_enforced_buy_is_made_at_the_scored_quote(self):
        self.nt.n["verify_buys"] = False
        now = datetime.now(timezone.utc)
        item = self._item(published=(now - timedelta(minutes=5)).isoformat(), price_at=now.isoformat())
        asked, quote = [], news_live.live_price
        news_live.live_price = lambda sym: (asked.append(sym), (104.0, 1.0) if sym == "AAA" else quote(sym))[1]
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):
            self._score(item)
        self.assertAlmostEqual(self.nt.book.positions["AAA"]["avg_cost"], 100.0 * 1.001, places=6)
        self.assertNotIn("AAA", asked)  # no check was asked, so there is nothing to re-quote after

    def test_outside_the_session_the_enforced_check_is_not_followed_by_a_look_at_the_stops(self):
        self.nt.book.state["positions"]["BBB"] = {"qty": 10, "avg_cost": 50.0, "last_price": 50.0, "entry_date": "2026-11-09",
                                                  "stop_price": 48.5}
        self.prices["BBB"] = 48.0  # the day's last price is under the stop; stops are looked at in session only
        news_live.market_open_now = lambda: False
        self._score(self._item(move=None))
        self.assertEqual([q["symbol"] for q in self.nt.queue], ["AAA"])
        self.assertIn("BBB", self.nt.book.positions)
        self.assertEqual(journal.read("news_trades.jsonl"), [])

    def test_a_look_at_the_stops_that_fails_after_the_enforced_check_costs_neither_the_buy_nor_the_batch(self):
        self.nt.book.state["positions"]["BBB"] = {"qty": 10, "avg_cost": 50.0, "last_price": 50.0, "entry_date": "2026-11-09",
                                                  "stop_price": 48.5}
        with mock.patch.object(self.nt, "check_stops", side_effect=RuntimeError("quotes down")):
            self.nt.handle_scored([self._item("a"), self._item("b", "BBB")],
                                  {"a": {"score": 9, "why": "x"}, "b": {"score": 1, "why": "fraud"}}, [])
        self.assertIn("AAA", self.nt.book.positions)
        self.assertNotIn("BBB", self.nt.book.positions)  # the batch: the bad-news sale behind the buy is still made
        self.assertIn("early_stops", [e["where"] for e in journal.read("news_errors.jsonl")])

    def test_a_call_that_does_not_come_back_is_an_answer_that_fails_and_the_check_ends_on_time(self):
        """Every call has its own timeout, and the check does not rest on it: the wait for the calls has an end of
        its own, a few seconds after verify_timeout_seconds, whatever the calls are doing. A call that is still out
        then is an answer that fails, and the buy is refused."""
        # two looks and the rescore, sixty seconds each: what this test is about, whatever config.json says today
        self.nt.n.update({"verify_calls": 2, "verify_rescore": True, "verify_timeout_seconds": 60})
        clock, waits = [1000.0], []

        class NeverBack:  # a call that was started and does not answer: waiting for it uses up the time it is given
            def __init__(self, *a, **k):
                pass

            def start(self):
                pass

            def join(self, timeout=None):
                waits.append(timeout)
                clock[0] += timeout or 0.0
        with mock.patch.object(news_live.threading, "Thread", NeverBack), \
                mock.patch.object(news_live.time, "time", lambda: clock[0]):  # the engine's clock: nothing here really waits
            self._score(self._item())
        self.assertTrue(waits and None not in waits, waits)  # no call is waited for without an end
        self.assertLess(sum(waits), 2 * 60)  # one end for the three together, not one each: under two timeouts in all
        self.assertEqual(self.nt.book.positions, {})
        row = self._second()
        self.assertEqual((row["verdict"], row["answers"], row["rescore"]), ("refused", [{"error": "no answer"}] * 2, None))


class StopCooldown_(_ChecksOver, g.StopCooldown):
    def test_the_cooldown_is_one_session_and_is_counted_from_the_latest_stop(self):
        self.nt.n["rebuy_cooldown_sessions"] = 1  # one session: the day of the stop, and no longer
        at = datetime(2026, 11, 10, 11, 0, tzinfo=NY)  # a Tuesday in session; the Monday before it was a session too

        class Clock(datetime):  # the engine's clock stands at `at`: its "today" is the fixture's, at any hour of any day
            @classmethod
            def now(cls, tz=None):
                return at.astimezone(tz)

        def stop(day):
            journal.append("news_trades.jsonl", {"date": day, "symbol": "AAA", "side": "SELL", "qty": 1, "price": 96.5,
                                                 "realized_pnl": 0.0, "reason": "stop -3% (entry 100.00, now 96.50)"})
        with mock.patch.object(news_live, "datetime", Clock):
            stop("2026-11-09")  # one session has opened since it
            self._score(self._item("a"))
            self.assertIn("AAA", self.nt.book.positions)  # the day after the stop it is bought again
            self.nt.book.state["positions"] = {}
            stop("2026-11-10")  # stopped again today: the older stop must not hide this one
            self._score(self._item("b"))
            self.assertEqual(self.nt.book.positions, {})
            self.assertEqual(self._checks()[-1]["stopped"], "2026-11-10")


class CatchUpStop_(_ChecksOver, g.CatchUpStop):
    def test_a_price_exactly_at_the_stop_is_through_it(self):
        held = copy.deepcopy(self.nt.book.state["positions"])
        # the day is the fixture's all through: a breach is sold while it is "found today", and that day must not turn
        # under the test when the wall clock's does (the day is UTC's: it turns at 19:00 or 20:00 in New York)
        with mock.patch.object(journal, "now_utc", lambda: "2026-11-10T14:38:30+00:00"):
            self.bars = [self._bar(31, 97.0, 97.4), self._bar(32, 97.0, 97.6)]  # two lows at 97.00 itself
            self._step()
            self.assertEqual(self.nt.book.positions, {})  # the live stop sells at px <= stop; the look back says the same
            self.nt = news_live.NewsTrader(self.cfg)  # a new engine: nothing is remembered of the looks before
            self.nt.n.update({"stop_catchup": "sell", "stop_catchup_min_bar_share": 0.0})
            self.nt.book.state["positions"] = copy.deepcopy(held)
            self.bars = [self._bar(31, 97.0, 97.0), self._bar(32, 97.3, 97.6)]  # one bar that closed at 97.00 itself
            self._step()
        self.assertEqual(self.nt.book.positions, {})
        self.assertEqual(journal.read("news_errors.jsonl"), [])

    def test_a_last_look_written_without_a_zone_is_read_as_utc(self):
        journal.save_json("news_heartbeat.json", {"at": "x", "stops_checked_at": "2026-11-10T14:35:00"})
        self._step()
        (_, since, _), = self.asked_bars
        self.assertEqual(since.strftime("%H:%M"), "09:35")
        self.assertEqual(journal.read("news_errors.jsonl"), [])

    def test_in_the_selling_mode_a_breach_found_by_a_look_is_sold_by_that_same_look(self):
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.0, 96.3)]
        news_live.QUOTE_TIME["AAA"] = (self.NOW - timedelta(seconds=10)).isoformat()  # a live quote, ten seconds old
        with mock.patch.object(journal, "now_utc", lambda: "2026-11-10T14:38:30+00:00"):  # the fixture's own day
            self.nt._look_at_stops([], now=self.NOW)  # and its own 09:38:30, not the wall clock
        self.assertEqual(self.nt.book.positions, {})  # not left for the next look, which may be a scorer call away
        self.assertTrue(self._sold()[0]["reason"].startswith("stop -3% traded through while unwatched"))

    def test_the_alert_says_whether_it_is_known_that_nobody_was_looking(self):
        held = copy.deepcopy(self.nt.book.state["positions"])
        self.nt.n["stop_catchup"] = "alert"
        self.bars = [self._bar(32, 96.0, 96.3)]
        self._step()  # nothing on record says when the stops were last looked at
        self.assertIn("לא ידוע", self.sent[-1][1])  # "not known": the words that carry it
        journal.save_json("news_heartbeat.json", {"stops_checked_at": datetime(2026, 11, 10, 9, 31, tzinfo=NY)
                                                  .astimezone(timezone.utc).isoformat()})
        self.nt = news_live.NewsTrader(self.cfg)  # the next run finds the last look on record: 09:31
        self.nt.n.update({"stop_catchup": "alert", "stop_catchup_min_bar_share": 0.0})
        self.nt.book.state["positions"] = copy.deepcopy(held)
        self._step(self.NOW + timedelta(minutes=1))
        self.assertIn("נחצה", self.sent[-1][1])  # the same alert, of the same breach
        self.assertNotIn("לא ידוע", self.sent[-1][1])

    def test_a_breach_found_by_a_look_is_on_disk_before_the_step_goes_on_and_the_next_engine_sells_on_it(self):
        """The mark on the position is the only record of a stop that was traded through unseen: no trade row is
        written for it. A step that dies after the look (a scorer that hangs, a container that is replaced) must not
        take the mark with it: the next engine sells on it at its first live quote, also when Yahoo can no longer
        give the minute bars of that stretch."""
        self.nt.save()  # the position is on disk, as the step that bought it left it
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.0, 96.3)]
        news_live.QUOTE_TIME.pop("AAA", None)  # no live quote yet: the look finds the breach and can sell nothing
        with mock.patch.object(journal, "now_utc", lambda: "2026-11-10T14:38:30+00:00"):  # the fixture's day, for both engines
            self.nt._look_at_stops([], now=self.NOW)  # the look at the top of a step that never reaches its own save
            again = news_live.NewsTrader(self.cfg)  # the next engine: all it knows is what is on disk
            again.n["stop_catchup"] = "sell"
            self.bars = None  # the bars of that stretch cannot be read again
            later = self.NOW + timedelta(seconds=60)
            news_live.QUOTE_TIME["AAA"] = (later - timedelta(seconds=10)).isoformat()
            again._look_at_stops([], now=later)
        self.assertEqual(again.book.positions, {})
        self.assertTrue(self._sold()[0]["reason"].startswith("stop -3% traded through while unwatched (low 96.00 at 09:32"))

    def test_a_breach_the_owner_was_told_about_is_not_told_again_by_the_next_engine(self):
        self.nt.n["stop_catchup"] = "alert"  # the default
        self.nt.save()
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(32, 96.0, 96.3)]
        with mock.patch.object(journal, "now_utc", lambda: "2026-11-10T14:38:30+00:00"):  # the fixture's day, for both engines
            self.nt._look_at_stops([], now=self.NOW)  # found and said at the top of a step that never reaches its own save
            again = news_live.NewsTrader(self.cfg)
            again.n["stop_catchup_min_bar_share"] = 0.0
            again._look_at_stops([], now=self.NOW + timedelta(seconds=60))  # the same bars are still there to be read
        self.assertEqual(len([body for prio, body in self.sent if prio == "urgent" and "נחצה" in body]), 1)
        self.assertEqual(journal.load_json("news_book.json")["positions"]["AAA"]["stop_breach"]["low"], 96.0)

    def test_a_row_the_feed_sends_twice_is_one_print_not_two(self):
        self.bars = [self._bar(31, 96.9, 97.4), self._bar(31, 96.9, 97.4)]  # one touch of the stop, and its row again
        self._step()
        self.assertIn("AAA", self.nt.book.positions)  # one minute that touched the stop and came back is not a breach
        self.assertNotIn("stop_breach", self.nt.book.positions["AAA"])

    def test_minutes_yahoo_had_not_published_are_read_at_the_next_look_whatever_the_age_of_the_quote(self):
        """The MU case with Yahoo two minutes late. The engine comes back at 09:38:30 after five minutes away. The
        quote is from 09:37:25 (live by the 3-minute rule), the bars of 09:36 and 09:37 are not out yet, and the
        last row of the reply is that quote, as in every real reply. It is not a bar: what was read ends at 09:36,
        and the next look reads on from there and finds the 09:36 bar that closed under the stop."""
        self.nt.n.update({"stop_catchup": "alert", "stop_catchup_min_bar_share": 0.5})
        journal.save_json("news_heartbeat.json", {"at": "x", "stops_checked_at": "2026-11-10T14:33:00+00:00"})
        news_live.bars_since = self._bars_since  # the real reader, on a reply in Yahoo's shape

        def t(minute, second=0):
            return int(datetime(2026, 11, 10, 9, minute, second, tzinfo=NY).timestamp())

        def reply(rows):
            return {"timestamp": [r[0] for r in rows],
                    "indicators": {"quote": [{"low": [r[1] for r in rows], "close": [r[2] for r in rows]}]}}
        quote = (t(37, 25), 98.5, 98.5)
        early = [(t(33), 98.0, 98.2), (t(34), 98.0, 98.2), (t(35), 98.1, 98.3), (t(36), None, None), (t(37), None, None),
                 (t(38), None, None), quote]
        late = early[:3] + [(t(36), 96.0, 96.3), (t(37), 96.2, 98.4), (t(38), None, None), quote]
        news_live.QUOTE_TIME["AAA"] = datetime(2026, 11, 10, 9, 37, 25, tzinfo=NY).isoformat()
        with mock.patch.object(news_live, "_chart", lambda sym, rng, iv: reply(early)):
            self.nt._look_at_stops([], now=self.NOW)
        with mock.patch.object(news_live, "_chart", lambda sym, rng, iv: reply(late)):
            self.nt._look_at_stops([], now=self.NOW + timedelta(seconds=20))
        self.assertEqual(self.nt.book.positions["AAA"]["stop_breach"]["at"], "09:36")
        self.assertEqual(len([body for prio, body in self.sent if prio == "urgent" and "נחצה" in body]), 1)

    def test_the_gap_that_counts_as_not_looked_at_is_its_own_number_in_config(self):
        """A stretch is read back when the last look is older than stop_catchup_gap_seconds and at least
        stop_catchup_min_seconds of it have passed. While the gap is the smaller number the minimum decides alone;
        the gap is still a rule of its own: set above the minimum, it is the one that decides."""
        self.nt.n.update({"stop_catchup_gap_seconds": 150, "stop_catchup_min_seconds": 120})
        self.nt.catch_up_stops([], self.NOW, last=(self.NOW - timedelta(seconds=140)).astimezone(timezone.utc))
        self.assertEqual(self.asked_bars, [])  # 140 seconds since the last look: under the gap, nothing is read
        self.nt.catch_up_stops([], self.NOW, last=(self.NOW - timedelta(seconds=151)).astimezone(timezone.utc))
        self.assertEqual(len(self.asked_bars), 1)  # over it: read


class StopsFirst_(_ChecksOver, g.StopsFirst):
    def test_after_a_stalled_step_the_gap_of_a_name_with_a_live_quote_is_still_read(self):
        """Every look moves a held name's stamp to now, so the gap has to be measured on what was known before it."""
        self.nt.n["stop_catchup"] = "alert"
        self.nt.book.state["positions"] = {"AAA": {"qty": 5, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0,
                                                   "entry_date": "2026-11-09"}}
        asked = []

        def bars(sym, since, now):  # every minute of the stretch is there, all of them above the stop
            asked.append(since.astimezone(NY).strftime("%H:%M"))
            first = since.replace(second=0, microsecond=0)
            return [(first + timedelta(minutes=m), 99.0, 99.5) for m in range(int((now - first).total_seconds() // 60))]

        def look(at):  # one look of the engine, at `at`, with a quote ten seconds old
            news_live.QUOTE_TIME["AAA"] = (at - timedelta(seconds=10)).isoformat()
            self.nt._look_at_stops([], now=at)
        t0 = datetime(2026, 11, 10, 10, 0, 5, tzinfo=NY)  # a Tuesday in session: the fixture's own time, not the wall clock
        with mock.patch.object(news_live, "bars_since", bars):
            look(t0)  # the engine is running: it has looked at AAA
            del asked[:]
            look(t0 + timedelta(minutes=10))  # then a scorer call hung for ten minutes
            self.assertEqual(asked, ["10:00"])  # the live look that came first did not hide the ten minutes before it
            look(t0 + timedelta(minutes=10, seconds=20))
            self.assertEqual(asked, ["10:00"])  # and a stretch that was read is not read again
        self.assertEqual([body for prio, body in self.sent if prio == "urgent"], [])  # all of it was read: nothing to tell


class Bars_(_ChecksOver, g.Bars):
    def test_the_minute_still_trading_is_left_out_even_when_its_row_sits_on_the_minute(self):
        stamps = [self._t(m) for m in range(30, 39)]  # at 09:38:30 the 09:38 row is a bar that is still being made
        got = self._bars(stamps, [99.0] * 8 + [90.0], [99.5] * 8 + [90.0])
        self.assertEqual(got[-1][0].astimezone(NY).strftime("%H:%M"), "09:37")
        self.assertEqual(min(b[1] for b in got), 99.0)  # its low and its "close" so far are not evidence of a breach

    def test_the_quote_row_is_left_out_however_old_the_quote_is(self):
        """The last row of a Yahoo reply is the quote, stamped with the time of the last trade (MU on 2026-11-10:
        a row at 16:11:54 UTC, volume 0, after a 16:11:00 row of nulls). It is not a minute bar, also when the quote
        is more than a minute old: read as one, it would end the stretch that was read after minutes Yahoo has not
        published yet."""
        stamps = [self._t(m) for m in range(30, 36)] + [self._t(36), self._t(37), self._t(38), self._t(37, 25)]
        lows = [99.0] * 6 + [None, None, None, 99.2]  # 09:36 and 09:37 are not out yet; the quote is from 09:37:25
        got = self._bars(stamps, lows, lows)  # asked at 09:38:30
        self.assertEqual([b[0].astimezone(NY).strftime("%H:%M:%S") for b in got], [f"09:{m}:00" for m in range(30, 36)])


class OneEngine_(_ChecksOver, g.OneEngine):
    def test_while_an_engine_runs_nobody_else_can_take_the_book_not_even_to_share_it(self):
        import fcntl
        tried = []

        def step(nt):
            with open(journal._path("news_engine.lock"), "a") as other:
                for how in (fcntl.LOCK_SH, fcntl.LOCK_EX):
                    try:
                        fcntl.flock(other, how | fcntl.LOCK_NB)
                        tried.append("taken")
                    except OSError:
                        tried.append("refused")
            raise news_live.ChainBroken("one step is enough")  # ends the loop after this step, whatever the clock says
        with mock.patch.object(news_live.NewsTrader, "step", step), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "code_stamp", lambda: {"commit": "x", "dirty": False, "started": "now"}), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("24:00", 1, prime=False), 0)  # "24:00" never comes: the step is reached at any hour
        self.assertEqual(tried, ["refused", "refused"])  # the engine's own lock is exclusive


class PauseSaidAtOnce_(_ChecksOver, g.PauseSaidAtOnce):
    def test_a_sale_with_neither_gain_nor_loss_starts_no_pause_and_is_not_called_a_loss(self):
        self.cfg["news"].update({"slippage_bps": 0, "max_hold_days": 1})
        self.nt = news_live.NewsTrader(self.cfg)
        self._score(self._item())  # bought at 100.00, no slippage
        self.nt.book.positions["AAA"]["entry_date"] = "2026-01-02"
        ev = []
        self.nt.check_stops(ev)  # the time exit sells at 100.00
        self.assertEqual(journal.read("news_trades.jsonl")[-1]["realized_pnl"], 0.0)
        self.assertEqual([e[:4] for e in ev], ["SELL"])  # no "sold at a loss" line
        self._score(self._item("b", "BBB"))
        self.assertIn("BBB", self.nt.book.positions)  # nothing waits for a review: the next buy is made


class NothingSlowBeforeASale_(_ChecksOver, g.NothingSlowBeforeASale):
    def test_a_step_does_not_wait_for_a_trial_check_that_has_not_answered(self):
        """On trial the check must change no trade, not this one and not the next, and never stand between the loop
        and a stop: a step that waited for it would hold up the next look at the stops for as long as the checker
        takes (up to verify_timeout_seconds)."""
        self.nt.n["guards"] = "log"
        go = threading.Event()

        def slow(item, model, timeout=60):  # the checker has not answered yet, and does not before the test lets it
            go.wait(30)
            return dict(APPROVED)
        news_live.verify_headline = slow
        item = {**self._item(), "link": "", "published": journal.now_utc()}
        waits, drain = [], self.nt.drain_trial
        try:
            with mock.patch.object(self.nt, "poll_headlines", lambda: [item]), \
                    mock.patch.object(news_live, "score_batch", lambda items, model: {"k1": {"score": 9, "why": "x"}}), \
                    mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True), \
                    mock.patch.object(self.nt, "drain_trial", lambda wait=0.0: (waits.append(wait), drain(wait=0.0))[1]):
                self.nt.step()
            self.assertEqual(waits, [0.0])  # the time the step gives it: none. Not one second, let alone its whole timeout
            self.assertIn("AAA", self.nt.book.positions)
            self.assertNotIn("second_check", [guard for guard, _ in self._verdicts()])  # still out: nothing is written for it
        finally:
            go.set()
        self.nt.drain_trial(wait=30)
        self.assertIn(("second_check", "passed"), self._verdicts())  # and its answer is written when it has come

    def test_the_engine_says_which_code_it_started_on(self):
        real_step = news_live.NewsTrader.step

        def one_step(nt):
            real_step(nt)
            raise news_live.ChainBroken("one step is enough")  # ends the loop after this step, whatever the clock says
        with mock.patch.object(news_live.NewsTrader, "step", one_step), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "code_stamp", lambda: {"commit": "abc1234", "dirty": False, "started": "now"}), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("24:00", 1, prime=False), 0)  # through the front door; "24:00" never comes
        self.assertEqual(journal.load_json("news_heartbeat.json")["code"]["commit"], "abc1234")

    def test_what_a_failing_engine_says_of_the_stops_is_what_its_own_steps_saw(self):
        """The real step, failing round after round. alert_after_errors = 1: the first failed round is told."""
        cfg = {**self.cfg, "news": {**self.cfg["news"], "alert_after_errors": 1}}
        real_step = news_live.NewsTrader.step

        def told(poll, stops=None, open_now=lambda: True):
            rounds = []

            def step(nt):
                rounds.append(1)
                if len(rounds) > 3:
                    raise news_live.ChainBroken("three rounds are enough")  # ends the loop, whatever the clock says
                return real_step(nt)
            del self.sent[:]
            with contextlib.ExitStack() as on, contextlib.redirect_stdout(io.StringIO()):
                on.enter_context(mock.patch.object(news_live.NewsTrader, "step", step))
                on.enter_context(mock.patch.object(news_live.NewsTrader, "poll_headlines", poll))
                on.enter_context(mock.patch.object(news_live, "market_open_now", open_now))
                on.enter_context(mock.patch.object(news_live, "load_config", lambda: cfg))
                on.enter_context(mock.patch.object(news_live, "code_stamp",
                                                   lambda: {"commit": "x", "dirty": False, "started": "now"}))
                on.enter_context(mock.patch.object(news_live.time, "sleep", lambda s: None))
                if stops:
                    on.enter_context(mock.patch.object(news_live.NewsTrader, "check_stops", stops))
                self.assertEqual(news_live.run("24:00", 1, prime=False), 0)  # "24:00" never comes
            (alert,) = [body for prio, body in self.sent if "סיבובים ברצף" in body]  # told once: at the first failed round
            return alert

        def feeds_down(nt):
            raise RuntimeError("feeds down")

        def quotes_down(nt, events, now=None):
            raise RuntimeError("quotes down")
        self.assertIn("עדיין נבדקים", told(feeds_down))  # the look at the top of each round ran before the round failed
        said = told(lambda nt: [], stops=quotes_down)  # the look itself is what fails (the one at the end is not guarded)
        self.assertIn("לא נבדקים", said)
        self.assertNotIn("עדיין נבדקים", said)
        polled = []

        def after_the_bell(nt):  # one good round in the session; then the bell, and the feeds go down
            polled.append(1)
            if len(polled) > 1:
                raise RuntimeError("feeds down")
            return []
        said = told(after_the_bell, open_now=lambda: not polled)
        self.assertIn("לא נבדקים", said)  # the look of the last good round is not carried over the close
        self.assertNotIn("עדיין נבדקים", said)


class SaidWhateverHappens_(_ChecksOver, g.SaidWhateverHappens):
    def test_a_move_that_cannot_be_compared_never_fails_the_batch_and_is_no_buy_when_enforced(self):
        self.nt.n["guards"] = "log"
        self._score(self._item(move="5.8"))  # a move in a shape nobody expected (text): the batch must come back.
        # Whether the default mode may BUY on a move it cannot read is not pinned here: "no buy when today's move
        # is not known" (require_known_move, always enforced) says no, and the code today says yes.
        self.nt.book.state["positions"] = {}
        self.nt.n["guards"] = "enforce"
        self._score(self._item("b", move="5.8"))
        self.assertEqual(self.nt.book.positions, {})
        self.assertNotIn("bought", [c["verdict"] for c in self._checks() if c.get("id") == "b"])

    def test_the_loop_prints_what_a_failed_step_had_already_done(self):
        self._held_under_its_stop()
        self.nt.save()  # the run builds its own engine from the book on disk
        real_step, rounds, out = news_live.NewsTrader.step, [], io.StringIO()

        def step(nt):
            rounds.append(1)
            if len(rounds) > 1:
                raise news_live.ChainBroken("one failed round is enough")  # ends the loop, whatever the clock says
            return real_step(nt)  # the real step: it sells BBB at its top, and then the feeds fail it
        with mock.patch.object(news_live.NewsTrader, "step", step), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", side_effect=RuntimeError("feeds down")), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "code_stamp", lambda: {"commit": "x", "dirty": False, "started": "now"}), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(out):
            self.assertEqual(news_live.run("24:00", 1, prime=False), 0)  # "24:00" never comes
        self.assertIn("RuntimeError", out.getvalue())
        self.assertIn("SELL 10 BBB", out.getvalue())  # the engine's log still says what was sold
        self.assertEqual([t["side"] for t in journal.read("news_trades.jsonl")], ["SELL"])

    def test_the_heartbeat_has_no_stamp_while_a_held_name_has_had_no_quote_and_no_bars_read(self):
        at = datetime(2026, 11, 10, 9, 31, tzinfo=NY)  # a Tuesday, a minute after the bell: no completed minute to read yet
        self.nt.book.state["positions"] = {
            "AAA": {"qty": 1, "avg_cost": 100.0, "last_price": 100.0, "stop_price": 97.0, "entry_date": "2026-11-09"},
            "BBB": {"qty": 1, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5, "entry_date": "2026-11-09"}}
        news_live.QUOTE_TIME["AAA"] = (at - timedelta(seconds=10)).isoformat()  # AAA has a live quote; BBB has none
        self.nt.n["stop_catchup"] = "alert"  # with the look back at work, not switched off
        look = self.nt._look_at_stops
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), \
                mock.patch.object(self.nt, "_look_at_stops", lambda ev, guarded=False: look(ev, guarded, now=at)):
            self.nt.step()  # every look of this step is made at 09:31, whatever the wall clock says
        # not AAA's stamp: BBB was never looked at, and a restart must read its stretch back
        self.assertIsNone(journal.load_json("news_heartbeat.json")["stops_checked_at"])

    def test_the_wait_for_answers_still_out_is_one_wait_in_all_not_one_for_each(self):
        self.nt.n["guards"] = "log"
        go = threading.Event()
        news_live.verify_headline = lambda item, model, timeout=60: (go.wait(30), dict(APPROVED))[1]
        self.nt.handle_scored([self._item("a"), self._item("b", "BBB"), self._item("c", "SPY")],
                              {k: {"score": 9, "why": "x"} for k in "abc"}, [])
        clock, given = [1000.0], []

        def written():
            return [c["symbol"] for c in self._checks() if c["guard"] == "second_check"]

        class StillOut:  # an answer that has not come: waiting for it uses up the time it is given, on the test's clock
            def wait(self, timeout=None):
                given.append(timeout)
                clock[0] += timeout
                return False
        real = [box["done"] for box, _, _ in self.nt._trial]
        try:
            for box, _, _ in self.nt._trial:
                box["done"] = StillOut()
            with mock.patch.object(news_live.time, "time", lambda: clock[0]):
                self.nt.drain_trial(wait=0.4)
            self.assertEqual(len(given), 3)  # each of the three was waited for
            self.assertAlmostEqual(sum(given), 0.4)  # 0.4 seconds for the three together, not 1.2
            self.assertEqual(written(), [])  # all three still out: nothing is written for them
        finally:
            for (box, _, _), done in zip(self.nt._trial, real):
                box["done"] = done
            go.set()
        self.nt.drain_trial(wait=30)
        self.assertEqual(sorted(written()), ["AAA", "BBB", "SPY"])  # and each is written when it has come

    def test_a_trial_check_that_raised_leaves_a_row_that_says_so_and_never_one_that_reads_as_a_pass(self):
        self.nt.n["guards"] = "log"
        with mock.patch.object(self.nt, "_ask_second", side_effect=RuntimeError("boom")):
            self._score(self._item())
        self.assertIn("AAA", self.nt.book.positions)
        row = self._second()
        self.assertEqual((row["verdict"], row["answers"]), ("would_refuse", [{"error": "RuntimeError"}]))

    def test_trial_checks_wait_their_turn_when_config_says_one_at_a_time(self):
        # what this test is about, whatever config.json says today: one check at a time, two looks to a check
        self.nt.n.update({"guards": "log", "verify_parallel": 1, "verify_calls": 2})
        go, both_out, asked = threading.Event(), threading.Event(), []

        def slow(item, model, timeout=60):
            asked.append(item["symbol"])
            if len(asked) >= 2:
                both_out.set()
            go.wait(30)
            return dict(APPROVED)
        news_live.verify_headline = slow
        self.nt.handle_scored([self._item("a"), self._item("b", "BBB")], {k: {"score": 9, "why": "x"} for k in "ab"}, [])
        try:
            self.assertTrue(both_out.wait(30))  # the two looks of one headline's check have started
            self.assertFalse(self.nt._trial_gate.acquire(blocking=False))  # and that one check is all the room there is
            time.sleep(0.2)
            self.assertEqual(len(set(asked)), 1, asked)  # the other headline's check has not started: one check at a time
        finally:
            go.set()
        self.nt.drain_trial(wait=30)
        self.assertEqual(sorted(c["symbol"] for c in self._checks() if c["guard"] == "second_check"), ["AAA", "BBB"])

    def test_a_score_for_another_ticker_than_the_items_own_is_dropped(self):
        items = [{"key": "a", "symbol": "AAA", "title": "t", "published": "2026-11-10T15:00:00+00:00", "day_move_pct": 0.1},
                 {"key": "b", "symbol": "BBB", "title": "t", "published": "2026-11-10T15:00:00+00:00", "day_move_pct": 0.1}]
        rows = [{"id": 0, "symbol": "BBB", "score": 10, "why": "meant for the other one"},
                {"id": 1, "symbol": "bbb", "score": 7, "why": "ok"}]

        def reply(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"result": json.dumps(rows)}), stderr="")
        with mock.patch.object(news_live.subprocess, "run", reply):
            self.assertEqual(news_live.score_batch(items, "m"), {"b": {"score": 7, "why": "ok"}})


class QueueAndRecord_(_ChecksOver, g.QueueAndRecord):
    def test_with_the_check_switched_off_an_enforced_engine_fills_a_queued_name_that_was_never_checked(self):
        self.nt.n["verify_buys"] = False
        self.nt.queue = [{"symbol": "AAA", "score": 9, "why": "w", "queued_at": journal.now_utc(), "id": "q1", "second_check": None}]
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}):
            self.nt.run_queue_at_open([])
        self.assertIn("AAA", self.nt.book.positions)


class Ledger_(_ChecksOver, p.Ledger):
    def test_a_key_that_fits_two_fills_names_neither(self):
        journal.write_all("news_trades.jsonl", [
            {"date": "2026-11-10", "symbol": "AAA", "side": "SELL", "realized_pnl": -30.0, "hash": "aaaaaaaa" + "1" * 56},
            {"date": "2026-11-10", "symbol": "BBB", "side": "SELL", "realized_pnl": -5.0, "hash": "aaaaaaaa" + "2" * 56}])
        with self.assertRaises(ValueError):
            postmortem.record(["news:aaaaaaaa"], **REVIEW)  # eight characters of the hash, and still two fills
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 2))  # never "the first one that fits"
        postmortem.record(["news:aaaaaaaa1"], **REVIEW)  # one more character tells them apart
        self.assertEqual([x["symbol"] for x in postmortem.pending()], ["BBB"])

    def test_the_shortest_key_comes_from_config_and_no_setting_makes_the_books_name_a_key(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        h = postmortem.pending()[0]["key"].split(":")[1]
        self.assertEqual(postmortem.MIN_KEY, CFG["postmortem"]["min_key_chars"])

        def stocks_unreadable(book="stocks"):
            if book == "stocks":
                raise OSError("no config")
            return {}
        with mock.patch("aitrader.data.load_config", stocks_unreadable):
            with self.assertRaises(ValueError):
                postmortem.record(["news:" + h[:7]], **REVIEW)  # a config that cannot be read keeps the default of 8
        with mock.patch("aitrader.data.load_config", lambda book="stocks": {"postmortem": {"min_key_chars": 0}}):
            with self.assertRaises(ValueError):
                postmortem.record(["news:"], **REVIEW)  # zero in config is still at least one character of the hash
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))

    def test_the_summary_counts_reviews_not_ledger_lines(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        journal.write_all(postmortem.LEDGER, ["just a string", {"keys": [], "verdict": "fine"}])
        s = postmortem.summary()
        self.assertEqual((s["reviews"], s["by_verdict"], len(s["pending"])), (0, {}, 1))

    def test_a_journal_line_that_is_not_a_fill_is_skipped_and_the_losses_are_still_listed(self):
        journal.write_all("news_trades.jsonl", ["a stray line", 7, None, ["x"],
                                                 {"date": "2026-11-10", "symbol": "AAA", "side": "SELL", "realized_pnl": -30.0}])
        self.assertEqual([x["symbol"] for x in postmortem.pending("news")], ["AAA"])
        self.assertEqual(postmortem.summary()["losing_fills"], 1)


class Cli_(_ChecksOver, p.Cli):
    def test_news_status_lists_only_the_news_books_own_waiting_losses(self):
        import json as _json
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")  # the quant book's loss does not hold the news book
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        got = _json.loads(self._run("news-status")[1])
        self.assertEqual([(x["book"], x["symbol"]) for x in got["losses_awaiting_review"]], [("news", "AAA")])


def load_tests(loader, standard_tests, pattern):
    """Only the methods written in this file. The ones the classes inherit are run from the parents' own files."""
    suite = unittest.TestSuite()
    for cls in list(globals().values()):
        if not (isinstance(cls, type) and issubclass(cls, unittest.TestCase) and cls.__module__ == __name__):
            continue
        own = {name for name in vars(cls) if name.startswith("test_")}
        suite.addTests(cls(name) for name in loader.getTestCaseNames(cls) if name in own)  # -k still chooses among them
    return suite


if __name__ == "__main__":
    unittest.main()
