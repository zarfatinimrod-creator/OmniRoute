"""The news engine as a supervised process (supervisor spec, section 5): what the engine itself does about its lock,
its heartbeat and the checks of a start."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import io
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import __main__ as cli
from aitrader import journal, news_live
from test_news_guards import _Engine

NY = ZoneInfo("America/New_York")


def hold(nt, sym="BBB", entry=50.0):
    """A held name on the trader's book: 10 shares, the stop at 97% of the entry."""
    nt.book.state["positions"][sym] = {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": "2026-11-09",
                                       "stop_price": round(entry * 0.97, 4)}


def items(n):
    """n fresh AAA headlines, as a poll hands them to a step."""
    return [{"key": f"k{i}", "symbol": "AAA", "title": f"AAA news {i}", "link": "", "published": journal.now_utc()}
            for i in range(n)]


def step(nt, new=(), scorer=lambda batch, model: {}):
    """One real step with the poll and the scorer replaced: `new` is what the poll finds."""
    with mock.patch.object(nt, "poll_headlines", lambda: list(new)), mock.patch.object(news_live, "score_batch", scorer):
        return nt.step()


@contextlib.contextmanager
def written():
    """journal.save_json wrapped: the phase of every heartbeat written inside the block, in the order of the writes."""
    phases, save = [], journal.save_json

    def listed(name, obj):
        if name == "news_heartbeat.json":
            phases.append(obj["phase"])
        save(name, obj)
    with mock.patch.object(journal, "save_json", listed):
        yield phases


class Lock(_Engine):
    def test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat(self):
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("23:59", max_minutes=0.0005, prime=False), 0)
        self.assertEqual([p for p, b in self.sent if b.startswith("מנוע החדשות רץ בלי נעילה")], ["urgent"])
        self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)
        self.assertEqual(journal._path("news_engine.lock").read_text(), "")   # it holds no lock, so it signs no lock file


class TheLoopsAnswer(_Engine):
    def test_run_hands_back_what_the_loop_returned_and_the_lock_file_names_this_process(self):
        got = []
        with mock.patch.object(news_live, "_run", lambda *a, **k: got.append(k) or 7):
            self.assertEqual(news_live.run(max_minutes=0.001), 7)   # not always 0: the loop gets exit codes of its own
        self.assertEqual(got, [{"locked": True}])
        holder = json.loads(journal._path("news_engine.lock").read_text())
        self.assertEqual((holder["pid"], holder["started_at"][-6:]), (os.getpid(), "+00:00"))


class Unlocked(_Engine):
    def test_a_line_that_cannot_be_built_does_not_cost_the_book_its_only_engine(self):
        news_live.ERRORS_SAID.clear()   # what this process already put in news_errors.jsonl
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live, "owner_line", side_effect=KeyError("supervisor")), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live.run("23:59", max_minutes=0.0005, prime=False), 0)
        self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)   # it ran, and its heartbeat still says how
        self.assertEqual([(e["where"], e["error"]) for e in journal.read("news_errors.jsonl")], [("lock_line", "KeyError")])


class Heartbeat(_Engine):
    def test_the_fields(self):
        hold(self.nt)                                                           # BBB held at 50.0, no headline
        step(self.nt)
        b = news_live.read_heartbeat()
        self.assertEqual((b["pid"], b["phase"], b["step"], b["market_open"], b["lock"], b["supervised"]), (os.getpid(), "idle", 1, True, True, False))
        self.assertEqual(b["held"]["BBB"]["stop"], 48.5)
        self.assertLessEqual({"at", "headlines_seen", "positions", "queue", "stops_checked_at", "buys_blocked", "code", "blind", "blind_since",
                              "blind_told", "told_through", "mismatch_told"}, set(b))

    def test_a_three_batch_step_beats_between_batches(self):
        self.nt.n["batch_max"] = 1
        seen = []
        step(self.nt, items(3), lambda batch, model: seen.append(news_live.read_heartbeat()["phase"]) or {})
        self.assertEqual(seen, ["quotes", "score", "score"])

    def test_every_headline_quote_leaves_a_beat(self):
        with written() as beats:
            step(self.nt, items(30))
        self.assertGreaterEqual(beats.count("quotes"), 30)

    def test_every_bar_read_of_the_catch_up_leaves_a_beat(self):
        for sym, entry in (("AAA", 100.0), ("BBB", 50.0), ("SPY", 500.0)):       # three held names; no step
            hold(self.nt, sym, entry)
        seen = []
        now = datetime(2026, 11, 10, 9, 45, tzinfo=NY)
        with written() as beats, mock.patch.object(news_live, "bars_since", lambda sym, since, now: seen.append(len(beats)) or []):
            self.nt.catch_up_stops([], now, last=now - timedelta(minutes=10))
        self.assertEqual((len(seen), seen == sorted(set(seen))), (3, True))

    def test_blind_lists_a_held_name_with_no_live_quote(self):
        hold(self.nt)
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: False):
            step(self.nt)
        b = news_live.read_heartbeat()
        self.assertEqual((b["blind"], list(b["blind_since"]), b["blind_told"]), (["BBB"], ["BBB"], []))

    def test_the_boot_beat_keeps_the_last_stop_look_of_the_run_before(self):   # Review Focus 1
        hold(self.nt)
        self.nt.save()
        T = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=400)
        journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "stops_checked_at": T.isoformat()})
        nt = news_live.NewsTrader(self.cfg)
        nt.adopt_previous(news_live.read_heartbeat())
        nt._beat("boot")
        self.assertEqual((nt._prev_look, datetime.fromisoformat(news_live.read_heartbeat()["stops_checked_at"])), (T, T))

    def test_a_restart_keeps_todays_blind_clock_with_its_told_flag_and_drops_yesterdays(self):  # Review Focus 1
        hold(self.nt)
        self.nt.save()
        since = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat(timespec="seconds")
        for at, kept in ((journal.now_utc(), {"BBB": True}), ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), {})):
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous({"at": at, "blind_since": {"BBB": since, "GONE": since}, "blind_told": ["BBB"]})
            self.assertEqual({s: v[1] for s, v in getattr(nt, "_blind", {}).items()}, kept)


class EveryCallAndEveryStart(_Engine):
    """What the seven tests above leave open: each place a beat is written, what a beat repeats, a beat that cannot be
    written, and what a new process does with the file it finds."""

    def test_each_look_beats_after_each_quote_and_the_step_after_its_poll_and_at_its_end(self):
        hold(self.nt)
        hold(self.nt, "AAA", 100.0)
        del self.prices["AAA"]              # a quote that brings no price was a call all the same
        self.nt.n["stop_catchup"] = "off"   # whether a bar read is due depends on the hour the test runs at
        with written() as beats:
            step(self.nt)
        self.assertEqual(beats, ["stops", "stops", "poll", "stops", "stops", "idle"])

    def test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once(self):
        t0 = datetime(2026, 11, 10, 9, 45, tzinfo=NY)       # a fixed clock: the test says the same at any hour

        def look(seconds, live):
            """One look `seconds` after 09:45: the beats it wrote, and BBB's stamp in the file when the look is over."""
            with written() as beats, mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: live):
                self.nt._look_at_stops([], now=t0 + timedelta(seconds=seconds))
            return beats, ((news_live.read_heartbeat() or {}).get("held") or {}).get("BBB", {}).get("checked_at")

        def utc(seconds):
            return (t0 + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat()
        self.nt.n["stop_catchup"] = "alert"                       # the bars of an unwatched stretch are read
        self.nt.adopt_previous({"stops_checked_at": utc(-600)})   # the run before looked last at 09:35
        self.assertEqual(look(0, True), ([], None))               # no held name: nothing to stamp, and no beat
        hold(self.nt)
        # no live quote, so the ten minutes since 09:35 are read from the bars (the stand-in has none: the stretch is
        # marked as looked at). The beats of the quote and of the bar read were written before that stamp was set
        self.assertEqual(look(0, False), (["stops", "stops", "stops"], utc(0)))
        self.assertEqual(look(30, False), (["stops"], utc(0)))    # nothing new was stamped: the quote's beat and no more
        self.assertEqual(look(60, True), (["stops", "stops"], utc(60)))   # a live quote stamps the name

    def test_the_beat_of_a_quote_is_written_after_the_sale_that_the_quote_led_to(self):
        hold(self.nt)
        self.prices["BBB"] = 48.0                      # under its stop of 48.50
        self.nt._blind = {"BBB": [datetime.now(NY), True]}   # and it had no live quote until now
        order, save = [], journal.save_json
        with mock.patch.object(journal, "save_json", lambda name, obj: (order.append(name), save(name, obj))[1]):
            self.nt.check_stops([])
        b = news_live.read_heartbeat()
        self.assertEqual(([name for name in order if name != "news_queue.json"], b["phase"], b["positions"]),
                         (["news_book.json", "news_heartbeat.json"], "stops", 0))
        self.assertEqual((b["held"], b["blind"], b["blind_since"], b["blind_told"]), ({}, [], {}, []))   # sold: in no list

    def test_the_opening_queue_beats_after_the_opens_and_after_each_name_bought_or_left_waiting(self):
        self.nt.queue = [{"symbol": sym, "score": 9, "why": "x", "queued_at": journal.now_utc(), "id": sym, "second_check": "passed"}
                         for sym in ("AAA", "BBB")]
        with written() as beats, mock.patch.object(news_live, "official_opens", lambda syms, day: {"AAA": 100.0}):
            self.nt.run_queue_at_open([])   # AAA has its 09:30 bar; BBB has none and no live quote either
        self.assertEqual((beats, list(self.nt.book.positions), [q["symbol"] for q in self.nt.queue]),
                         (["queue", "queue", "queue"], ["AAA"], ["BBB"]))

    def test_a_second_check_the_loop_waited_for_leaves_a_beat_and_one_on_trial_leaves_none(self):
        with written() as beats:
            self._score(self._item())                  # "enforce": the check is asked, and waited for, before the buy
        self.assertEqual((beats, list(self.nt.book.positions)), (["score"], ["AAA"]))
        self.nt.n["guards"] = "log"
        with written() as beats:
            self._score(self._item("k2", "BBB"))       # on trial: asked in the background, the loop does not wait
        self.assertEqual((beats, list(self.nt.book.positions)), ([], ["AAA", "BBB"]))

    def test_between_the_ends_of_two_steps_a_beat_repeats_what_the_last_end_worked_out(self):
        step(self.nt)
        first = news_live.read_heartbeat()
        news_live.set_hold("the owner said so")        # both change while the next step is under way
        self.nt.seen["k0"] = journal.now_utc()
        mid = []
        step(self.nt, items(1), lambda batch, model: mid.append(news_live.read_heartbeat()) or {})
        end = news_live.read_heartbeat()
        self.assertEqual([(b["phase"], b["step"], b["headlines_seen"], b["buys_blocked"]) for b in (first, *mid, end)],
                         [("idle", 1, 0, None), ("quotes", 2, 0, None), ("idle", 2, 1, "hold")])
        looks = [datetime.fromisoformat(b["stops_checked_at"]) for b in (first, *mid, end)]
        self.assertTrue(looks[0] == looks[1] < looks[2], looks)

    def test_a_beat_that_cannot_be_written_costs_a_row_and_never_the_sale(self):
        hold(self.nt)
        self.prices["BBB"] = 48.0                      # under its stop of 48.50
        save = journal.save_json

        def full(name, obj):
            if name == "news_heartbeat.json":
                raise OSError(28, "No space left on device")
            save(name, obj)
        with mock.patch.object(journal, "save_json", full):
            step(self.nt)
        self.assertEqual([(t["side"], t["symbol"]) for t in journal.read("news_trades.jsonl")], [("SELL", "BBB")])
        self.assertEqual({(e["where"], e["error"]) for e in journal.read("news_errors.jsonl")}, {("heartbeat", "OSError")})
        self.assertIsNone(news_live.read_heartbeat())

    def test_a_start_reads_the_file_it_finds_and_beats_before_anything_leaves_the_process(self):
        hold(self.nt)
        self.nt.save()
        T = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=400)
        journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "stops_checked_at": T.isoformat(), "headlines_seen": 7,
                                                  "buys_blocked": "hold"})
        calls, first, save = [], [], journal.save_json
        stamp = {"commit": "abc1234", "dirty": False, "started": "now"}

        def listed(name, obj):
            if name == "news_heartbeat.json" and not first:
                first.append({**obj, "calls": list(calls)})
            save(name, obj)
        with mock.patch.object(journal, "save_json", listed), \
                mock.patch.object(news_live, "live_price", lambda s: calls.append("quote") or (50.0, 0.0)), \
                mock.patch.object(news_live, "code_stamp", lambda: calls.append("git") or stamp), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: calls.append("feeds") or []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(news_live._run("23:59", 0.0005, False, locked=False), 0)
        (b,) = first
        self.assertEqual((b["phase"], b["pid"], b["step"], b["lock"], b["calls"], datetime.fromisoformat(b["stops_checked_at"])),
                         ("boot", os.getpid(), 0, False, [], T))
        self.assertEqual((b["headlines_seen"], b["buys_blocked"]), (7, "hold"))   # not worked out yet: the last values, repeated

    def test_until_its_own_first_look_an_engine_goes_on_saying_the_stamp_it_found(self):
        hold(self.nt)
        self.nt.save()
        T = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=400)
        nt = news_live.NewsTrader(self.cfg)
        nt.adopt_previous({"at": journal.now_utc(), "stops_checked_at": T.isoformat()})
        news_live.market_open_now = lambda: False      # before the bell: its steps run and make no look
        step(nt)
        b = news_live.read_heartbeat()
        self.assertEqual((b["phase"], b["market_open"], datetime.fromisoformat(b["stops_checked_at"])), ("idle", False, T))
        news_live.market_open_now = lambda: True       # the bell: from its own first look on, the stamp is its own
        with mock.patch.object(nt, "_quote_is_live", lambda *a, **k: True):
            step(nt)
        b = news_live.read_heartbeat()
        self.assertGreater(datetime.fromisoformat(b["stops_checked_at"]), T + timedelta(seconds=300))
        self.assertEqual(b["held"]["BBB"]["checked_at"], b["stops_checked_at"])

    def test_after_a_restart_a_blind_alert_is_neither_put_off_nor_said_twice(self):
        hold(self.nt)
        self.nt.save()
        long_ago = (datetime.now(timezone.utc) - timedelta(seconds=self.nt.n["stop_blind_alert_seconds"] + 100)).isoformat()
        for told, said in ((False, ["urgent"]), (True, [])):
            del self.sent[:]
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous({"at": journal.now_utc(), "blind_since": {"BBB": long_ago}, "blind_told": ["BBB"] if told else []})
            with mock.patch.object(nt, "_quote_is_live", lambda *a, **k: False):
                nt.check_stops([])                     # the first look of the new process: still no live quote
            self.assertEqual([p for p, body in self.sent if "אין מחיר עדכני" in body], said)
            nt._beat("stops")
            b = news_live.read_heartbeat()
            self.assertEqual((b["blind"], list(b["blind_since"]), b["blind_told"]), (["BBB"], ["BBB"], ["BBB"]))
            again = news_live.NewsTrader(self.cfg)     # and a third process takes the clock from that file as it is
            again.adopt_previous(b)
            self.assertEqual(again._blind, nt._blind)
            with mock.patch.object(nt, "_quote_is_live", lambda *a, **k: True):
                nt.check_stops([])
            self.assertEqual([p for p, body in self.sent if "חזר" in body], ["high"])   # it follows the alert of either process

    def test_a_file_that_cannot_be_used_costs_what_it_held_and_never_the_start(self):   # Review Focus 4
        hold(self.nt)
        self.nt.save()
        beat = journal._path("news_heartbeat.json")
        self.assertIsNone(news_live.read_heartbeat())                            # no file
        for text in ('{"at": "2026-11-1', "[1, 2]", ""):                        # torn, not a heartbeat, empty
            beat.write_text(text)
            self.assertIsNone(news_live.read_heartbeat())
        journal.write_all("news_equity.jsonl", [{"at": "2026-11-10T14:36:00+00:00", "equity": 1.0, "positions": 1}])
        before_this_task = {"at": journal.now_utc(), "headlines_seen": 3, "positions": 1, "queue": 0, "stops_checked_at": None,
                            "buys_blocked": None, "code": None, "lock": True}
        for prev in (None, before_this_task, {"at": "x", "stops_checked_at": "soon", "blind_since": ["BBB"]},
                     {"at": journal.now_utc(), "stops_checked_at": 5, "blind_since": {"BBB": 5}, "blind_told": None}):
            beat.unlink(missing_ok=True)
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous(prev)
            nt._beat("boot")
            # no stamp that can be read: the last point of the equity curve, as before; and no clock is made up
            self.assertEqual((nt._prev_look, getattr(nt, "_blind", {}), news_live.read_heartbeat()["phase"]),
                             (datetime(2026, 11, 10, 14, 36, tzinfo=timezone.utc), {}, "boot"), prev)
        nt.adopt_previous({"stops_checked_at": "2026-11-10T14:35:00"})          # a stamp written without a zone is UTC
        self.assertEqual(nt._prev_look, datetime(2026, 11, 10, 14, 35, tzinfo=timezone.utc))


BUY_AAA = {"date": "2026-11-10", "symbol": "AAA", "side": "BUY", "qty": 5, "price": 100.0}
E1_AAA = "ביומן העסקאות יש קנייה של AAA"


class _Starts(_Engine):
    """A start of the engine loop on the temporary state, with what it prints kept in self.out."""

    def setUp(self):
        super().setUp()
        quiet = contextlib.redirect_stdout(io.StringIO())   # the engine's own log lines, and journal.read's
        self.out = quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def start(self, until="23:59"):
        with mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg):
            return news_live._run(until, 0.0005, False)

    def files(self):
        return {p.name: p.read_bytes() for p in self.tmp.iterdir()}


class StartChecks(_Starts):
    def test_a_calendar_that_does_not_cover_today_ends_the_engine_with_5(self):
        with mock.patch.object(journal, "calendar_covers", lambda day: False):
            self.assertEqual(news_live.start_checks(self.cfg)[:2], (5, "calendar"))
            self.assertEqual(self.start(), 5)
        self.assertEqual([p for p, _ in self.sent], ["urgent"])

    def test_a_pull_in_progress_is_7_and_sends_nothing(self):
        for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
            root = Path(tempfile.mkdtemp()); state = root / "ai-trader" / "state"
            self.addCleanup(shutil.rmtree, root, True)
            state.mkdir(parents=True); (root / ".git").mkdir()
            self.assertFalse(news_live.tree_busy(state))
            (root / ".git" / name).mkdir()
            self.assertTrue(news_live.tree_busy(state), name)
        with mock.patch.object(news_live, "tree_busy", lambda start=None: True), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(news_live.start_checks(self.cfg)[:2], (7, "tree_busy"))
            self.assertEqual(self.start(), 7)
        self.assertEqual((self.sent, "[news] start refused: tree_busy (exit 7)" in out.getvalue()), ([], True))

    def test_trades_with_no_readable_book_is_6_said_once_and_the_file_is_not_written_over(self):
        journal.append("news_trades.jsonl", BUY_AAA)
        self.assertEqual(news_live.start_checks(self.cfg)[:2], (6, "book"))               # no book file
        journal._path("news_book.json").write_text("{not json")
        self.assertEqual(self.start(), 6)
        self.assertEqual(journal._path("news_book.json").read_text(), "{not json")
        self.assertEqual([(p, b.startswith("קובץ התיק של מנוע החדשות חסר או לא קריא")) for p, b in self.sent], [("urgent", True)])

    def test_a_buy_the_book_does_not_know_blocks_buys_says_e1_once_a_day_and_the_stops_go_on(self):
        hold(self.nt); self.nt.save(); self.prices["BBB"] = 48.0
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "AAA", "side": "BUY", "qty": 5, "price": 100.0})
        with open(journal._path("news_trades.jsonl"), "a") as f:
            f.write('{"torn')                                       # Review Focus 4: the last readable row is the BUY
        self.assertEqual(news_live.start_checks(self.cfg), (0, "", {"side": "BUY", "symbol": "AAA"}))
        self.assertEqual(self.start(), 0)
        self.assertEqual(journal.read("news_trades.jsonl")[-1]["side"], "SELL")          # BBB was under its stop
        self.assertIn("book_mismatch", [e.get("where") for e in journal.read("news_errors.jsonl")])
        self.assertEqual(news_live.read_heartbeat()["buys_blocked"], "book_mismatch")
        # a second start on the same day, again with a BUY of AAA as the last row: E1 is not said twice
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "AAA", "side": "BUY", "qty": 5, "price": 100.0})
        self.assertEqual(self.start(), 0)
        self.assertEqual(len([b for _, b in self.sent if b.startswith("ביומן העסקאות יש קנייה של AAA")]), 1)

    def test_check_takes_no_lock_writes_nothing_and_returns_the_code(self):
        before = sorted(p.name for p in self.tmp.iterdir())
        # a --check that started the engine would run it here on the real config, feeds and scorer: it must fail first
        with mock.patch.object(news_live, "NewsTrader", mock.Mock(side_effect=AssertionError("must not be built"))):
            self.assertEqual(cli.main(["news-live", "--check"]), 0)
            with mock.patch.object(journal, "broken_chains", lambda names=None: ["news_trades.jsonl"]):
                self.assertEqual(cli.main(["news-live", "--check"]), 4)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), before)


class WhatAStartFinds(_Starts):
    """What the five tests above leave open: every row of the start table read from real files (spec 5.4), what a
    refused start leaves alone, when E1 is said again, and what --check prints."""

    def test_the_last_trade_row_is_read_against_the_book(self):
        self.assertEqual(news_live.start_checks(self.cfg), (0, "", None))     # no book and no trade: a first start
        hold(self.nt); self.nt.save()                                         # the book holds 10 BBB
        self.assertEqual(news_live.start_checks(self.cfg), (0, "", None))     # a book and no trade journal
        for row, found in (({"side": "BUY", "symbol": "BBB", "qty": 10}, None),       # bought, and held
                           ({"side": "SELL", "symbol": "AAA", "qty": 5}, None),       # sold, and gone
                           ({"side": "SELL", "symbol": "BBB", "qty": 4}, None),       # a sale is the whole position: not that kill
                           ({"side": "SELL", "symbol": "BBB", "qty": 10}, {"side": "SELL", "symbol": "BBB"}),
                           ({"side": "BUY", "symbol": "AAA", "qty": 5}, {"side": "BUY", "symbol": "AAA"}),
                           ({"side": "BUY", "symbol": ["AAA"]}, None), ({"note": "a row that is no trade"}, None)):
            journal.append("news_trades.jsonl", {"date": "2026-11-10", "price": 1.0, **row})
            self.assertEqual(news_live.start_checks(self.cfg), (0, "", found), row)
        journal.append("news_trades.jsonl", BUY_AAA)
        with open(journal._path("news_trades.jsonl"), "a") as f:
            f.write('7\n[1]\n{"torn')                                         # Review Focus 4: lines that are no rows at all
        self.assertEqual(news_live.start_checks(self.cfg), (0, "", {"side": "BUY", "symbol": "AAA"}))

    def test_a_book_file_that_is_no_book_is_6_and_an_absent_one_only_when_there_are_trades(self):
        book = journal._path("news_book.json")
        for text in ("{not json", "", "[]", "{}", '{"cash": 1, "positions": []}'):
            book.write_text(text)
            self.assertEqual(news_live.start_checks(self.cfg)[:2], (6, "book"), text)
        book.write_text("null")                                               # as good as no file: nothing to write over
        self.assertEqual(news_live.start_checks(self.cfg), (0, "", None))
        journal.append("news_trades.jsonl", BUY_AAA)
        self.assertEqual(news_live.start_checks(self.cfg)[:2], (6, "book"))

    def test_a_refused_start_builds_no_trader_and_changes_no_file_and_the_checks_keep_their_order(self):
        journal.append("news_trades.jsonl", BUY_AAA)                          # trades and no book: 6 when nothing else refuses
        no_cover = mock.patch.object(journal, "calendar_covers", lambda day: False)
        busy = mock.patch.object(news_live, "tree_busy", lambda start=None: True)
        for code, why, refusing in ((5, "calendar", (no_cover, busy)), (7, "tree_busy", (busy,)), (6, "book", ())):
            before = self.files()
            with contextlib.ExitStack() as on:
                for stand_in in refusing:
                    on.enter_context(stand_in)
                on.enter_context(mock.patch.object(news_live, "NewsTrader", mock.Mock(side_effect=AssertionError("must not be built"))))
                self.assertEqual(news_live.start_checks(self.cfg), (code, why, None))
                self.assertEqual(self.start(), code)
            self.assertEqual(self.files(), before, why)                       # no heartbeat, no row, and the book as it was
        self.assertEqual([line for line in self.out.getvalue().splitlines() if "start refused" in line],
                         ["[news] start refused: tree_busy (exit 7)", "[news] start refused: book (exit 6)"])
        self.assertEqual([p for p, _ in self.sent], ["urgent", "urgent"])     # the calendar and the book; a pull says nothing

    def test_the_git_directory_is_the_first_one_above_the_state_directory_also_through_a_gitdir_file(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        real, tree = root / "main" / ".git" / "worktrees" / "wt", root / "wt"
        state = tree / "ai-trader" / "state"
        real.mkdir(parents=True); state.mkdir(parents=True)
        (tree / ".git").write_text(f"gitdir: {real}\n")                      # a linked worktree: the file names its directory
        self.assertFalse(news_live.tree_busy(state))
        (real / "MERGE_HEAD").write_text("0" * 40 + "\n")
        self.assertTrue(news_live.tree_busy(state))
        (tree / ".git").write_text("gitdir: ../main/.git/worktrees/wt\n")    # a path from the folder that holds the file
        self.assertTrue(news_live.tree_busy(state))
        with mock.patch.object(journal, "STATE", state):                      # no start given: the state directory
            self.assertTrue(news_live.tree_busy())
        (state / ".git").write_text("not a git file\n")                       # neither a directory nor a gitdir file: not a .git
        self.assertTrue(news_live.tree_busy(state))
        (tree / "ai-trader" / ".git").mkdir()                                 # a checkout of its own nearer by: that one decides
        self.assertFalse(news_live.tree_busy(state))
        self.assertFalse(news_live.tree_busy())                               # this test's state directory is in no checkout

    def test_a_broken_chain_ends_the_engine_with_4_and_nothing_is_sold(self):
        hold(self.nt); self.nt.save(); self.prices["BBB"] = 48.0              # under its stop of 48.50
        journal._path("news_scores.jsonl").write_text('{"hash": "x", "prev_hash": "genesis", "score": 9}\n')
        self.assertEqual(self.start(), 4)
        self.assertEqual((journal.read("news_trades.jsonl"), ["hash chain broken" in b for _, b in self.sent]), ([], [True]))

    def test_e1_is_said_again_after_a_send_nobody_took_on_another_day_and_for_another_name(self):
        hold(self.nt); self.nt.save()
        journal.append("news_trades.jsonl", BUY_AAA)
        today = datetime.now(NY).date().isoformat()

        def said(prefix=E1_AAA):
            return len([b for _, b in self.sent if b.startswith(prefix)])

        def nobody(title, body, cfg, prio="default", **kw):                   # the phone stand-in when no channel takes a line
            self.sent.append((prio, body))
            return []
        with mock.patch.object(news_live.notify, "send", nobody):
            self.assertEqual(self.start(), 0)
        self.assertEqual((said(), news_live.read_heartbeat()["mismatch_told"]), (1, None))
        self.assertEqual(self.start(), 0)                                     # so the next start says it again
        self.assertEqual((said(), news_live.read_heartbeat()["mismatch_told"]), (2, {"day": today, "symbol": "AAA"}))
        self.assertEqual((self.start(), said()), (0, 2))                      # told today: not again
        self.assertEqual(news_live.read_heartbeat()["mismatch_told"], {"day": today, "symbol": "AAA"})   # it stays in the file
        beat = journal._path("news_heartbeat.json")
        for left in ({"day": (datetime.now(NY).date() - timedelta(days=1)).isoformat(), "symbol": "AAA"}, "AAA", ["AAA"]):
            beat.write_text(json.dumps({**news_live.read_heartbeat(), "mismatch_told": left}))
            before = said()
            self.assertEqual((self.start(), said() - before), (0, 1), left)   # yesterday's, or no pair at all: said
        journal.append("news_trades.jsonl", {**BUY_AAA, "symbol": "CCC"})
        self.assertEqual((self.start(), said("ביומן העסקאות יש קנייה של CCC"), said()), (0, 1, 5))   # another name: its own line
        self.assertEqual(len([e for e in journal.read("news_errors.jsonl") if e.get("where") == "book_mismatch"]), 7)   # a row per start

    def test_only_a_pair_of_today_is_taken_over_from_the_heartbeat_before(self):   # Review Focus 1
        today = datetime.now(NY).date()
        for left, kept in (({"day": today.isoformat(), "symbol": "AAA"}, True),
                           ({"day": (today - timedelta(days=1)).isoformat(), "symbol": "AAA"}, False),
                           ("AAA", False), (["AAA"], False), (None, False)):
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous({"at": journal.now_utc(), "mismatch_told": left})
            nt._beat("boot")                                                  # and what it kept is what its own beats say
            self.assertEqual(news_live.read_heartbeat()["mismatch_told"], left if kept else None, left)

    def test_the_pair_is_in_the_file_as_soon_as_a_channel_took_the_line_also_when_no_step_follows(self):
        hold(self.nt); self.nt.save()
        journal.append("news_trades.jsonl", BUY_AAA)
        self.assertEqual(self.start(until="00:00"), 0)                        # 00:00 has always passed: the loop makes no step
        b = news_live.read_heartbeat()
        self.assertEqual((b["phase"], b["step"], b["mismatch_told"]),
                         ("boot", 0, {"day": datetime.now(NY).date().isoformat(), "symbol": "AAA"}))
        self.assertEqual((self.start(), len([b for _, b in self.sent if b.startswith(E1_AAA)])), (0, 1))

    def test_a_sale_the_book_does_not_show_is_said_with_its_own_word_and_the_name_stays_under_its_stop(self):
        hold(self.nt); self.nt.save()
        journal.append("news_trades.jsonl", {"date": "2026-11-10", "symbol": "BBB", "side": "SELL", "qty": 10, "price": 48.0})
        self.assertEqual(self.start(), 0)
        self.assertEqual([p for p, b in self.sent if b.startswith("ביומן העסקאות יש מכירה של BBB")], ["urgent"])
        b = news_live.read_heartbeat()
        self.assertEqual((list(b["held"]), b["buys_blocked"]), (["BBB"], "book_mismatch"))   # still held, still looked at

    def test_an_e1_that_cannot_be_built_does_not_cost_the_start(self):
        news_live.ERRORS_SAID.clear()   # what this process already put in news_errors.jsonl
        hold(self.nt); self.nt.save(); self.prices["BBB"] = 48.0
        journal.append("news_trades.jsonl", BUY_AAA)
        with mock.patch.object(news_live, "owner_line", side_effect=KeyError("supervisor")):
            self.assertEqual(self.start(), 0)
        self.assertEqual(journal.read("news_trades.jsonl")[-1]["side"], "SELL")   # the stop was looked at all the same
        self.assertEqual([(e["where"], e["error"]) for e in journal.read("news_errors.jsonl")],
                         [("book_mismatch", "BookMismatch"), ("mismatch_line", "KeyError")])

    def test_a_mismatch_answers_before_the_loss_review_and_a_refused_buy_carries_its_sentence(self):
        sentence = "התיק לא תואם ליומן העסקאות. עד שסשן הסוחר מיישב את זה אין קניות חדשות. סטופים ומכירות עובדים כרגיל"
        self.nt.book_mismatch = {"side": "BUY", "symbol": "BBB"}
        with mock.patch.object(news_live.postmortem, "pending", lambda book: ["a loss with no review"]):
            self.assertEqual(self.nt._buys_blocked(), ("book_mismatch", sentence))
        events = self._score(self._item())                                    # a headline that would be bought
        self.assertEqual((dict(self.nt.book.positions), events), ({}, [f"AAA ציון 9: לא קונים. {sentence}"]))
        self.nt.book_mismatch = None
        self.assertIsNone(self.nt._buys_blocked())

    def test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money(self):
        self.nt.book_mismatch = {"side": "BUY", "symbol": "BBB"}
        with mock.patch.object(self.nt, "_quote_is_live", lambda *a, **k: True):   # a real step: one headline, scored 9
            step(self.nt, items(1), lambda batch, model: {x["key"]: {"score": 9, "why": "test"} for x in batch})
        told = [(p, b) for p, b in self.sent if "התיק לא תואם ליומן העסקאות" in b]   # the message as the phone gets it
        self.assertEqual(([p for p, _ in told], dict(self.nt.book.positions)), (["high"], {}))
        last = told[0][1].splitlines()[-1]                                           # the book line, still the last line
        self.assertTrue(last.startswith("תיק חדשות (נייר): $") and last.endswith("%). כסף נייר"), told[0][1])

    def test_check_prints_a_line_per_check_and_returns_the_first_code_that_fails(self):
        def check(*stand_ins):
            """news-live --check: (its code, the lines it printed), with nothing built, written or sent."""
            before, at = self.files(), len(self.out.getvalue())
            with contextlib.ExitStack() as on:
                for stand_in in stand_ins:
                    on.enter_context(stand_in)
                on.enter_context(mock.patch.object(news_live, "NewsTrader", mock.Mock(side_effect=AssertionError("must not be built"))))
                code = cli.main(["news-live", "--check"])
            self.assertEqual((self.files(), self.sent), (before, []))
            return code, [line.removeprefix("[news] check ") for line in self.out.getvalue()[at:].splitlines()]
        ok = ["calendar: ok", "tree_busy: ok", "book: ok", "book_mismatch: ok", "chains: ok"]
        self.assertEqual(check(), (0, ok))
        self.assertEqual(check(mock.patch.object(journal, "calendar_covers", lambda day: False)), (5, ["calendar: failed (exit 5)"]))
        self.assertEqual(check(mock.patch.object(news_live, "tree_busy", lambda start=None: True)),
                         (7, ok[:1] + ["tree_busy: failed (exit 7)"]))
        journal.append("news_trades.jsonl", BUY_AAA)
        self.assertEqual(check(), (6, ok[:2] + ["book: failed (exit 6)"]))
        hold(self.nt); self.nt.save()
        code, lines = check()                                                 # a mismatch is printed, and the engine may start
        self.assertEqual((code, lines[:3], lines[4:], "BUY of AAA" in lines[3]), (0, ok[:3], ok[4:], True))
        journal._path("news_scores.jsonl").write_text('{"hash": "x", "prev_hash": "genesis", "score": 9}\n')
        code, lines = check()
        self.assertEqual((code, lines[4]), (4, "chains: failed (exit 4): news_scores.jsonl"))
        self.assertFalse(journal._path("news_engine.lock").exists())           # and no lock was ever asked for

    def test_the_command_line_hands_check_to_run_by_keyword(self):
        got = []
        with mock.patch.object(news_live, "run", lambda until, minutes, **k: got.append((until, minutes, k)) or 0):
            self.assertEqual((cli.main(["news-live", "--check"]), cli.main(["news-live", "--minutes", "2"])), (0, 0))
        self.assertEqual(got, [("16:05", None, {"check": True}), ("16:05", 2.0, {"check": False})])
