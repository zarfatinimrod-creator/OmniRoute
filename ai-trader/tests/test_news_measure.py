"""The news engine measures itself (basic law 2: accuracy and speed are numbers, not feelings).

1. Every scorer call is on record (state/news_scorer_calls.jsonl): model, prompt stamp, items sent and answered, wall
   time, and the CLI's own time, cost and token counts. Until 2026-11-10 score_batch threw the CLI's envelope away.
2. Every new headline has an outcome (state/news_seen_log.jsonl): scored, or the reason it was not. On 2026-11-09,
   142 of the 666 headlines first seen after priming were never scored and no file said why.
3. A health row every five minutes (state/news_health.jsonl): step and poll times, feeds that answered, scorer calls
   and failures, the headlines sent to the scorer and those it answered, stop checks, the longest gap between two of
   them, the age of the oldest quote one used, the names they looked at and the prices they did not get.

The three journals are measurement. They are not hash-chained (a damaged one must never stop the engine and with it
the stop checks), and a row that cannot be written never costs a step, a score or a sale.
"""

import contextlib
import hashlib
import io
import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest import mock

from aitrader import journal, news_live
from test_core import CFG
from test_news_inputs import HeldOnAClock, TempState

PROMPT_ID = news_live.PROMPT_ID  # the stamp score rows carry under "prompt"; the scorer-call rows carry the same one
MEASURED = ("news_scorer_calls.jsonl", "news_seen_log.jsonl", "news_health.jsonl")
ITEMS = [{"key": "k1", "symbol": "MU", "title": "Micron buyback", "published": "2026-11-09T15:26:32+00:00", "day_move_pct": 5.82},
         {"key": "k2", "symbol": "KO", "title": "Coca-Cola raises guidance", "published": "2026-11-09T15:27:00+00:00"}]
# what `claude -p --output-format json` reported for one scorer call on 2026-11-10 (the figures the engine used to drop)
FIGURES = {"duration_ms": 7089, "duration_api_ms": 4497, "total_cost_usd": 0.00695201,
           "usage": {"input_tokens": 2, "cache_creation_input_tokens": 31533, "cache_read_input_tokens": 28121,
                     "output_tokens": 728, "output_tokens_details": {"thinking_tokens": 552}, "service_tier": "standard"}}


def key_of(sym, title):
    return hashlib.sha1(f"{sym}|{title}".encode()).hexdigest()[:16]  # as fetch_headlines makes it


def cli_reply(rows, **envelope):
    """What subprocess.run gives back for one `claude -p` call that answered `rows` (a str: the answer text as it is)."""
    return SimpleNamespace(stdout=json.dumps({"result": rows if isinstance(rows, str) else json.dumps(rows), **envelope}))


def payload_of(cmd):
    prompt = cmd[-1]
    return json.loads(prompt[prompt.index("ITEMS:") + len("ITEMS:"):])


class Feeds:
    """Stands in for the engine's requests.Session: one Yahoo RSS reply per ticker, built from (title, published)
    pairs. A ticker in `down` answers 503; one in `broken` does not answer at all."""

    def __init__(self, items):
        self.headers, self.items, self.down, self.broken = {}, items, set(), set()

    def get(self, url, params=None, timeout=None):
        sym = params["s"]
        if sym in self.broken:
            raise news_live.requests.ConnectionError("no route")
        rss = "".join(f"<item><title>{t}</title><link>https://example.test/{sym}</link><pubDate>{format_datetime(at)}</pubDate>"
                      "</item>" for t, at in self.items.get(sym, []))
        return SimpleNamespace(status_code=503 if sym in self.down else 200, text=f"<rss><channel>{rss}</channel></rss>")


class ScorerFacts(unittest.TestCase):
    """score_batch itself: the facts of the call ride on its answer (`.facts`) and it writes nothing (the caller
    journals the row). The engine calls it with (items, model) alone, as before."""

    def _score(self, run, items=ITEMS):
        with mock.patch.object(news_live.subprocess, "run", run), contextlib.redirect_stdout(io.StringIO()):
            out = news_live.score_batch(items, "any-model")
        return out, out.facts

    def test_a_call_reports_what_was_sent_and_answered_and_returns_what_it_always_did(self):
        out, facts = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": 7, "why": "buyback"},
                                                              {"id": 1, "symbol": "KO", "score": 6, "why": "guidance"}]))
        self.assertEqual(out, {"k1": {"score": 7, "why": "buyback"}, "k2": {"score": 6, "why": "guidance"}})
        self.assertEqual((facts["model"], facts["prompt"], facts["sent"], facts["answered"]),
                         ("any-model", PROMPT_ID, 2, 2))
        self.assertIsInstance(facts["wall_s"], float)
        self.assertGreaterEqual(facts["wall_s"], 0)
        self.assertNotIn("error", facts)
        self.assertEqual(len(PROMPT_ID), 12)

    def test_the_clis_own_time_cost_and_tokens_are_kept(self):
        _, facts = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": 7, "why": "x"}], **FIGURES))
        self.assertEqual({k: v for k, v in facts.items() if k not in ("model", "prompt", "sent", "answered", "wall_s")},
                         {"duration_ms": 7089, "duration_api_ms": 4497, "total_cost_usd": 0.00695201, "input_tokens": 2,
                          "cache_creation_input_tokens": 31533, "cache_read_input_tokens": 28121, "output_tokens": 728,
                          "thinking_tokens": 552})
        self.assertEqual(facts["answered"], 1)  # KO got no row from the scorer

    def test_an_envelope_without_figures_gives_no_made_up_numbers(self):
        for envelope in ({}, {"duration_ms": "fast", "total_cost_usd": None, "usage": "n/a"}, {"usage": ["tokens"]},
                         {"usage": {"input_tokens": "2", "output_tokens_details": 552}}):
            with self.subTest(envelope=envelope):
                out, facts = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": 7, "why": "x"}],
                                                                     **envelope))
                self.assertEqual(sorted(facts), ["answered", "model", "prompt", "sent", "wall_s"])
                self.assertEqual(out, {"k1": {"score": 7, "why": "x"}})  # odd figures never cost the scores

    def test_a_failed_call_reports_the_error_type_instead_of_the_answer_count(self):
        def timed_out(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 90)
        not_json = lambda cmd, **kw: SimpleNamespace(stdout="usage limit")  # noqa: E731
        for run, error in ((timed_out, "TimeoutExpired"), (not_json, "JSONDecodeError")):
            out, facts = self._score(run)
            self.assertEqual((out, facts["error"], facts["sent"]), ({}, error, 2))
            self.assertNotIn("answered", facts)
            self.assertIn("wall_s", facts)  # a call that timed out took its 90 seconds: the time is the point

    def test_a_failure_the_cli_reports_itself_is_a_failure_not_an_empty_answer(self):
        out, facts = self._score(lambda cmd, **kw: SimpleNamespace(stdout=json.dumps(
            {"is_error": True, "result": "Claude AI usage limit reached", "duration_ms": 412})))
        self.assertEqual((out, facts["error"], facts["duration_ms"]), ({}, "is_error", 412))
        self.assertNotIn("answered", facts)

    def test_an_answer_under_another_ticker_is_named(self):
        out, facts = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": 7, "why": "x"},
                                                              {"id": 1, "symbol": "PEP", "score": 9, "why": "wrong name"}]))
        self.assertEqual((list(out), facts["answered"], facts["symbol_mismatch"]), (["k1"], 1, ["k2"]))

    def test_a_row_whose_score_is_not_a_whole_number_is_skipped_never_raised(self):
        # the scorer is asked for an integer 1-10. null, text (also "9"), a list and a fraction are not one: the row is
        # skipped and the headline has no score. 8.6 is rejected, not rounded: 9 would be a buy the scorer did not call.
        # Until 2026-11-10 null and text raised out of score_batch, and the step that failed skipped its stop check
        for bad in (None, "high", "9", 8.6, 9.5, True, [9], {"v": 9}, float("nan"), float("inf")):
            with self.subTest(score=bad):
                out, facts = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": bad, "why": "x"},
                                                                      {"id": 1, "symbol": "KO", "score": 6, "why": "y"}]))
                self.assertEqual(out, {"k2": {"score": 6, "why": "y"}})  # the row beside it is kept
                self.assertEqual(facts["answered"], 1)
                self.assertNotIn("error", facts)

    def test_a_whole_number_is_a_score_clamped_to_the_scale(self):
        for given, taken in ((9, 9), (9.0, 9), (1, 1), (0, 1), (-3, 1), (15, 10), (10 ** 400, 10)):
            with self.subTest(score=given):
                out, _ = self._score(lambda cmd, **kw: cli_reply([{"id": 0, "symbol": "MU", "score": given, "why": "x"}]))
                self.assertEqual(out, {"k1": {"score": taken, "why": "x"}})
                self.assertIs(type(out["k1"]["score"]), int)

    def test_a_row_id_that_is_no_index_is_skipped_never_raised(self):
        for bad in (float("inf"), float("nan"), None, "first", 7, [0]):  # inf (1e999 in the reply) raised OverflowError
            with self.subTest(id=bad):
                out, facts = self._score(lambda cmd, **kw: cli_reply([{"id": bad, "symbol": "MU", "score": 7, "why": "x"},
                                                                      {"id": 1, "symbol": "KO", "score": 6, "why": "y"}]))
                self.assertEqual((out, facts["answered"]), ({"k2": {"score": 6, "why": "y"}}, 1))

    def test_a_reply_of_any_shape_is_a_failed_call_never_an_error_out_of_the_scorer(self):
        # an error out of score_batch fails the step, and a failed step skips its stop check
        deep = json.dumps({"result": "[" * 100000 + "]" * 100000})  # too deep to parse: RecursionError, not ValueError
        for stdout in ("[]", "null", '"usage limit"', '{"result": null}', '{"result": 7}', deep):
            with self.subTest(stdout=stdout[:40]):
                out, facts = self._score(lambda cmd, **kw: SimpleNamespace(stdout=stdout))
                self.assertEqual(out, {})
                self.assertIn("error", facts)
                self.assertNotIn("answered", facts)
                self.assertIn("wall_s", facts)

    def test_no_items_is_no_call(self):
        with mock.patch.object(news_live.subprocess, "run", side_effect=AssertionError("claude was called")):
            out = news_live.score_batch([], "any-model")
        self.assertEqual((out, out.facts), ({}, {}))


class Engine(TempState):
    """One engine on three names (AAA, BBB, CCC), market closed, no network: the feeds, the scorer CLI, the prices and
    the alerts are stand-ins. Each name has one fresh headline; AAA also has one from two hours ago."""

    def setUp(self):
        super().setUp()
        self.cfg = {**CFG, "universe": {"AAA": "Tech", "BBB": "Tech", "CCC": "Tech", "SPY": "Index"}}
        self.now = datetime.now(timezone.utc)
        self.feeds = Feeds({"AAA": [("AAA wins a contract", self.now - timedelta(minutes=1)),
                                    ("AAA opens an office", self.now - timedelta(hours=2))],
                            "BBB": [("BBB names a new chief", self.now - timedelta(minutes=2))],
                            "CCC": [("CCC recalls a product", self.now - timedelta(minutes=3))]})
        self.calls = []  # the payload of every scorer call
        self.figures = {}
        self.answer = lambda payload: [{"id": p["id"], "symbol": p["symbol"], "score": 6, "why": "x"} for p in payload]
        for target, name, stub in ((news_live.notify, "send", lambda *a, **kw: []),
                                   (news_live, "live_price", lambda s: (100.0, None)),
                                   (news_live, "market_open_now", lambda: False),
                                   (news_live.subprocess, "run", self._claude),
                                   (news_live.requests, "Session", lambda: self.feeds)):
            p = mock.patch.object(target, name, stub)
            p.start()
            self.addCleanup(p.stop)
        self.nt = news_live.NewsTrader(self.cfg)
        self.nt.n["health_log_seconds"] = 3600  # no health row unless a test asks for one

    def _claude(self, cmd, **kw):
        self.calls.append(payload_of(cmd))
        rows = self.answer(self.calls[-1])
        if isinstance(rows, Exception):
            raise rows
        return cli_reply(rows, **self.figures)

    def _step(self):
        with contextlib.redirect_stdout(io.StringIO()):  # "[news] scorer failed" and the like
            return self.nt.step()

    def _outcomes(self):
        return {(r["symbol"], r["outcome"]) for r in journal.read("news_seen_log.jsonl")}


class ScorerCallsOnRecord(Engine):
    def test_every_scorer_call_is_one_row(self):
        self.nt.n["batch_max"] = 2  # three fresh headlines: two calls
        self.figures = FIGURES
        self._step()
        rows = journal.read("news_scorer_calls.jsonl")
        self.assertEqual([(r["sent"], r["answered"]) for r in rows], [(2, 2), (1, 1)])
        for r in rows:
            self.assertEqual((r["model"], r["prompt"]), (self.nt.n["model"], PROMPT_ID))
            self.assertEqual(datetime.fromisoformat(r["at"]).utcoffset(), timedelta(0))
            self.assertEqual((r["duration_ms"], r["duration_api_ms"], r["total_cost_usd"], r["output_tokens"]),
                             (7089, 4497, 0.00695201, 728))
            self.assertGreaterEqual(r["wall_s"], 0)
            self.assertNotIn("source", r)  # only a call made outside the engine names where it came from
        self._step()  # nothing new: no call, no row
        self.assertEqual(len(journal.read("news_scorer_calls.jsonl")), 2)

    def test_a_failed_call_is_on_record_with_its_error(self):
        self.answer = lambda payload: subprocess.TimeoutExpired("claude", 90)
        self._step()
        (row,) = journal.read("news_scorer_calls.jsonl")
        self.assertEqual((row["sent"], row["error"]), (3, "TimeoutExpired"))
        self.assertNotIn("answered", row)

    def test_a_call_whose_answer_cannot_be_parsed_keeps_its_time_cost_and_tokens(self):
        # the figures are in the envelope, and the envelope was read: the call was paid for whatever its answer is worth
        self.figures = FIGURES
        self.answer = lambda payload: '[{"id": 0, "symbol": "AAA", "score": 7, "why": "x"}] note: see [1]'
        self._step()
        (row,) = journal.read("news_scorer_calls.jsonl")
        self.assertEqual((row["sent"], row["error"]), (3, "JSONDecodeError"))
        self.assertNotIn("answered", row)
        self.assertEqual((row["duration_ms"], row["duration_api_ms"], row["total_cost_usd"], row["output_tokens"],
                          row["thinking_tokens"]), (7089, 4497, 0.00695201, 728, 552))

    def test_a_call_that_raises_out_of_the_scorer_is_still_on_record(self):
        def scorer(items, model):  # score_batch never raises on a reply; this is whatever else could go wrong in it
            raise ValueError("an answer that cannot be used")
        with mock.patch.object(news_live, "score_batch", scorer), self.assertRaises(ValueError):
            self._step()
        (row,) = journal.read("news_scorer_calls.jsonl")  # the call was made and paid for
        self.assertEqual((row["model"], row["prompt"], row["sent"]), (self.nt.n["model"], PROMPT_ID, 3))
        self.assertNotIn("answered", row)  # neither an answer count nor an error type: the step's error is in news_errors.jsonl

    def test_scores_and_predictions_carry_the_model_and_the_prompt_stamp(self):
        self._step()
        scores, preds = journal.read("news_scores.jsonl"), journal.read("news_predictions.jsonl")
        self.assertEqual((len(scores), len(preds)), (3, 6))
        for r in scores + preds:  # the forward record can now be split by scorer version, not only by timestamp
            self.assertEqual((r["model"], r["prompt"]), (self.nt.n["model"], PROMPT_ID))
            self.assertNotIn("prompt_hash", r)  # one name for the stamp: the score row's own "prompt"
        self.assertEqual(journal.broken_chains(journal.NEWS_CHAINED), [])


class HeadlineOutcomes(Engine):
    def test_every_new_headline_leaves_one_row(self):
        self._step()
        rows = journal.read("news_seen_log.jsonl")
        self.assertEqual(self._outcomes(), {("AAA", "scored"), ("AAA", "stale"), ("BBB", "scored"), ("CCC", "scored")})
        self.assertEqual(len(rows), 4)
        by_key = {r["key"]: r for r in rows}
        stale = by_key[key_of("AAA", "AAA opens an office")]  # two hours old at first sight: never sent to the scorer
        self.assertEqual(sorted(stale), ["first_seen", "key", "outcome", "published", "symbol"])
        self.assertEqual(datetime.fromisoformat(stale["published"]), (self.now - timedelta(hours=2)).replace(microsecond=0))
        seen = datetime.fromisoformat(stale["first_seen"])
        self.assertEqual(seen.utcoffset(), timedelta(0))
        self.assertLess(abs((seen - datetime.now(timezone.utc)).total_seconds()), 60)
        bbb = key_of("BBB", "BBB names a new chief")
        self.assertEqual(by_key[bbb]["first_seen"], self.nt.seen[bbb])
        self.assertEqual({r["id"] for r in journal.read("news_scores.jsonl")},
                         {k for k, r in by_key.items() if r["outcome"] == "scored"})
        self._step()
        self._step()
        self.assertEqual(len(journal.read("news_seen_log.jsonl")), 4)  # one row per new headline, not one per poll

    def test_a_headline_older_than_the_engines_memory_leaves_no_row(self):
        # `seen` forgets a headline after seen_keep_days, so an old one still in a quiet feed looks new again every
        # few days: a row for it would not be a first sight
        self.feeds.items["CCC"] += [("CCC was founded", self.now - timedelta(days=self.nt.n["seen_keep_days"], hours=1)),
                                    ("CCC moved its office", self.now - timedelta(days=self.nt.n["seen_keep_days"] - 1))]
        self._step()
        rows = [(r["key"], r["outcome"]) for r in journal.read("news_seen_log.jsonl") if r["symbol"] == "CCC"]
        self.assertEqual(sorted(rows), sorted([(key_of("CCC", "CCC recalls a product"), "scored"),
                                               (key_of("CCC", "CCC moved its office"), "stale")]))
        self.assertIn(key_of("CCC", "CCC was founded"), self.nt.seen)  # marked seen as always

    def test_a_headline_the_scorer_skipped_or_answered_under_another_ticker_says_which(self):
        self.answer = lambda payload: [{"id": 0, "symbol": "AAA", "score": 6, "why": "x"},
                                       {"id": 1, "symbol": "ZZZ", "score": 9, "why": "another name"}]  # nothing for id 2
        self._step()
        self.assertEqual(self._outcomes(), {("AAA", "scored"), ("AAA", "stale"), ("BBB", "symbol_mismatch"),
                                            ("CCC", "scorer_no_answer")})

    def test_a_row_with_no_usable_score_is_no_answer_for_that_headline_and_the_step_goes_on(self):
        score = {"AAA": None, "BBB": "high", "CCC": 8.6}
        self.answer = lambda payload: [{"id": p["id"], "symbol": p["symbol"], "score": score[p["symbol"]], "why": "x"}
                                       for p in payload]
        self._step()  # does not raise
        self.assertEqual(self._outcomes(), {("AAA", "scorer_no_answer"), ("AAA", "stale"), ("BBB", "scorer_no_answer"),
                                            ("CCC", "scorer_no_answer")})
        self.assertEqual(journal.read("news_scores.jsonl"), [])
        (call,) = journal.read("news_scorer_calls.jsonl")
        self.assertEqual((call["sent"], call["answered"]), (3, 0))

    def test_a_failed_scorer_call_is_the_outcome_of_every_headline_in_it(self):
        self.nt.n["batch_max"] = 2
        self.answer = lambda payload: subprocess.TimeoutExpired("claude", 90) if len(payload) == 2 else \
            [{"id": 0, "symbol": payload[0]["symbol"], "score": 6, "why": "x"}]
        self._step()
        self.assertEqual(self._outcomes(), {("AAA", "scorer_failed"), ("AAA", "stale"), ("BBB", "scorer_failed"),
                                            ("CCC", "scored")})

    def test_a_step_that_fails_still_leaves_each_headline_a_row(self):
        # the headlines are already marked seen and will not come back: without a row they would vanish, as on 2026-11-09
        with mock.patch.object(self.nt, "handle_scored", side_effect=RuntimeError("disk")), self.assertRaises(RuntimeError):
            self._step()
        self.assertEqual(self._outcomes(), {("AAA", "step_failed"), ("AAA", "stale"), ("BBB", "step_failed"),
                                            ("CCC", "step_failed")})
        self._step()
        self.assertEqual(len(journal.read("news_seen_log.jsonl")), 4)  # said once

    def test_priming_is_one_summary_row_not_one_per_headline(self):
        with mock.patch.object(news_live, "load_config", lambda: self.cfg), contextlib.redirect_stdout(io.StringIO()):
            news_live.run(until_ny="00:00")  # a first start: primes, then stops at once (00:00 has always passed)
        (row,) = journal.read("news_seen_log.jsonl")
        self.assertEqual((row["outcome"], row["count"]), ("primed", 4))
        self.assertEqual(datetime.fromisoformat(row["at"]).utcoffset(), timedelta(0))
        self.assertEqual(len(journal.load_json("news_seen.json")), 4)
        self.assertEqual(self.calls, [])  # primed headlines are never scored


class HealthRow(Engine):
    def _row(self):
        """The health row of a window that ends with one more (quiet) step."""
        self.nt.n["health_log_seconds"] = 0
        self._step()
        self.nt.n["health_log_seconds"] = 3600
        return journal.read("news_health.jsonl")[-1]

    def test_one_row_per_window_from_the_bookkeeping_in_memory(self):
        self._step()
        self._step()
        self.assertEqual(journal.read("news_health.jsonl"), [])  # the window is not over
        row = self._row()
        self.assertEqual(len(journal.read("news_health.jsonl")), 1)
        self.assertEqual((row["steps"], row["feeds_min"], row["universe"]), (3, 3, 3))
        self.assertEqual((row["scorer_calls"], row["scorer_fails"]), (1, 0))  # the first step scored the three fresh headlines
        for name in ("step_s", "poll_s"):
            self.assertGreaterEqual(row[name + "_median"], 0)
            self.assertGreaterEqual(row[name + "_max"], row[name + "_median"])
        # the market is closed: no stop check was made, so there is no gap and no quote age to give
        self.assertEqual((row["stop_checks"], row["stop_gap_max_s"], row["stop_quote_age_max_s"]), (0, None, None))
        self.assertEqual(datetime.fromisoformat(row["at"]).utcoffset(), timedelta(0))
        self.assertGreaterEqual(row["window_s"], 0)
        self.assertEqual(self._row()["steps"], 1)  # after a row the bookkeeping starts over

    def test_the_smallest_number_of_feeds_that_answered(self):
        self._step()  # 3 of 3
        self.feeds.down, self.feeds.broken = {"BBB"}, {"CCC"}  # one answers 503, one does not answer
        self._step()
        self.feeds.down, self.feeds.broken = set(), set()
        row = self._row()  # 3 of 3 again: the worst pass of the window is the one on record
        self.assertEqual((row["feeds_min"], row["universe"], row["steps"]), (1, 3, 3))

    def test_scorer_calls_and_failures_are_counted(self):
        self._step()
        self.feeds.items["BBB"].append(("BBB wins an appeal", self.now))
        self.answer = lambda payload: subprocess.TimeoutExpired("claude", 90)
        self._step()
        row = self._row()
        self.assertEqual((row["scorer_calls"], row["scorer_fails"]), (2, 1))
        self.assertEqual((row["scorer_sent"], row["scorer_answered"]), (4, 3))  # the failed call sent one and answered none

    def test_a_scorer_that_answers_nothing_usable_shows_in_the_row(self):
        # no call failed, so scorer_fails is 0: only what was sent against what was answered shows that nothing came back
        self.answer = lambda payload: "I cannot score these headlines."
        self._step()
        row = self._row()
        self.assertEqual((row["scorer_calls"], row["scorer_fails"], row["scorer_sent"], row["scorer_answered"]), (1, 0, 3, 0))
        self.assertEqual(journal.read("news_scores.jsonl"), [])

    def test_a_window_is_as_long_as_the_time_its_counts_cover(self):
        # the next window opens when a row is cut. Opened at the next step's poll, as it was, it left out the wait
        # between the two steps: about 20 of every 320 seconds at the production cadence
        clock = [news_live.time.time()]
        self.nt.n["health_log_seconds"] = 60
        with mock.patch.object(news_live.time, "time", lambda: clock[0]):
            for _ in range(7):  # a step every 20 seconds; the first row is cut at the fourth
                clock[0] += 20
                self._step()
        self.assertEqual([(r["steps"], r["window_s"]) for r in journal.read("news_health.jsonl")[1:]], [(3, 60)])

    def test_a_first_window_covers_its_first_poll(self):
        clock, feed = [news_live.time.time()], news_live._feed

        def slow(sym, session):  # the feeds take 30 seconds to answer
            if sym == "AAA":
                clock[0] += 30
            return feed(sym, session)
        self.nt.n["health_log_seconds"] = 30
        with mock.patch.object(news_live.time, "time", lambda: clock[0]), mock.patch.object(news_live, "_feed", slow):
            self._step()
        self.assertEqual([(r["steps"], r["window_s"]) for r in journal.read("news_health.jsonl")], [(1, 30)])

    def test_a_step_that_fails_is_a_step(self):
        with mock.patch.object(self.nt, "handle_scored", side_effect=RuntimeError("disk")), self.assertRaises(RuntimeError):
            self._step()
        self.assertEqual(self._row()["steps"], 2)

    def test_a_row_that_cannot_be_written_is_journaled_once_and_never_breaks_a_step(self):
        append = journal.append

        def full(name, record):
            if name == "news_health.jsonl":
                raise OSError("disk full")
            return append(name, record)
        self.nt.n["health_log_seconds"] = 0
        with mock.patch.object(journal, "append", full):
            self.assertEqual(self._step(), [])
            self.assertEqual(self._step(), [])
        errs = [(r["where"], r["error"], r["detail"]) for r in journal.read("news_errors.jsonl")]
        self.assertEqual(errs, [("news_health.jsonl", "OSError", "disk full")])  # once, not once per window
        self.assertEqual(journal.read("news_health.jsonl"), [])
        self.assertEqual(len(journal.read("news_scores.jsonl")), 3)  # the step did its work


class StopCheckHealth(HeldOnAClock):
    """What the stop checks looked like, on the fixed clock of HeldOnAClock (5 AAA held, checks from 11:00 New York)."""

    def _row(self):
        self.nt.n["health_log_seconds"] = 0
        with mock.patch.object(news_live, "market_open_now", lambda: False), \
                mock.patch.object(self.nt, "poll_headlines", lambda: []):
            self.nt.step()
        return journal.read("news_health.jsonl")[-1]

    def test_stop_checks_their_longest_gap_and_the_oldest_quote_they_used(self):
        self._check(0, 100.0, quote_age_s=20)
        self._check(1, 100.0, quote_age_s=45)
        self._check(6, 100.0, quote_age_s=10)  # five minutes after the one before: a step that hung
        row = self._row()
        self.assertEqual((row["stop_checks"], row["stop_gap_max_s"], row["stop_quotes_undated"]), (3, 300.0, 0))
        self.assertAlmostEqual(row["stop_quote_age_max_s"], 45.0, delta=1.0)

    def test_a_price_with_no_quote_time_has_no_age_and_is_counted(self):
        self._check(0, 100.0)  # a price, but Yahoo gave no time for it
        self._check(1, None)  # no price at all: the check used nothing
        row = self._row()
        self.assertEqual((row["stop_checks"], row["stop_quote_age_max_s"], row["stop_quotes_undated"]), (2, None, 1))

    def test_a_window_of_checks_that_saw_no_price_does_not_read_like_an_empty_book(self):
        def window(first_minute, px):
            for m in range(first_minute, first_minute + 3):
                self._check(m, px)
            row = self._row()
            return row["stop_checks"], row["stop_names_max"], row["stop_quotes_missing"], row["stop_quote_age_max_s"]
        self.assertEqual(window(0, None), (3, 1, 3, None))  # AAA held and no price in any check: the stop was blind
        self.nt.book.state["positions"]["BBB"] = {"qty": 5, "avg_cost": 50.0, "last_price": 50.0, "stop_price": 48.5,
                                                  "entry_date": "2026-11-10"}
        self.assertEqual(window(3, {"BBB": 50.0})[:3], (3, 2, 3))  # two names held, one of them without a price each time
        self.nt.book.state["positions"] = {}
        self.assertEqual(window(6, None), (3, 0, 0, None))  # nothing held: the same checks, with nothing to be blind to

    def test_the_first_check_of_a_day_has_no_gap(self):
        self._check(0, 100.0, quote_age_s=20)
        self._check(24 * 60, 100.0, quote_age_s=20)  # the next day: the night is not a gap between two stop checks
        self.assertIsNone(self._row()["stop_gap_max_s"])

    def test_a_quote_stamp_that_cannot_be_read_never_costs_a_stop(self):
        news_live.QUOTE_TIME["AAA"] = "some time this morning"
        news_live.live_price = lambda s: (96.5, None)  # through the 97.00 stop
        ev = []
        self.nt.check_stops(ev, self.T0)
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("AAA" in e and "stop" in e for e in ev))
        self.assertEqual(journal.read("news_trades.jsonl")[-1]["symbol"], "AAA")
        self.assertEqual([(r["where"], r["error"]) for r in journal.read("news_errors.jsonl")], [("stop_health", "ValueError")])


class ScorerNeverCostsAStop(HeldOnAClock):
    def test_a_score_that_is_not_a_number_does_not_cost_the_step_its_stop_check(self):
        item = {"key": "k1", "symbol": "AAA", "title": "AAA news", "link": "", "published": journal.now_utc()}
        reply = cli_reply([{"id": 0, "symbol": "AAA", "score": None, "why": "x"}])
        news_live.live_price = lambda s: (96.5, None)  # AAA is through its 97.00 stop
        with mock.patch.object(news_live, "market_open_now", lambda: True), \
                mock.patch.object(self.nt, "poll_headlines", lambda: [item]), \
                mock.patch.object(news_live.subprocess, "run", lambda cmd, **kw: reply):
            ev = self.nt.step()
        self.assertNotIn("AAA", self.nt.book.positions)
        self.assertTrue(any("AAA" in e and "stop" in e for e in ev), ev)
        self.assertTrue(journal.read("news_trades.jsonl")[-1]["reason"].startswith("stop "))
        self.assertEqual([r["outcome"] for r in journal.read("news_seen_log.jsonl")], ["scorer_no_answer"])


class ErrorOnce(TempState):
    def test_a_fault_that_could_not_be_written_is_written_once_the_journal_is_back(self):
        fault = ValueError("no previous close")
        with mock.patch.object(journal, "append", side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(io.StringIO()):
            news_live.error_once("day_move", fault)  # never raises
        self.assertEqual(journal.read("news_errors.jsonl"), [])
        news_live.error_once("day_move", fault)  # marked as said only now that it is written
        news_live.error_once("day_move", fault)
        self.assertEqual([(r["where"], r["error"], r["detail"]) for r in journal.read("news_errors.jsonl")],
                         [("day_move", "ValueError", "no previous close")])


class MeasurementNeverTrades(Engine):
    def test_the_measurement_journals_are_not_hash_chained(self):
        self.nt.n["health_log_seconds"] = 0
        self._step()
        for name in MEASURED:
            with self.subTest(name):
                self.assertNotIn(name, journal.CHAINED)  # a chained journal that breaks stops the engine and its stop checks
                rows = journal.read(name)
                self.assertTrue(rows)
                self.assertFalse(any("hash" in r for r in rows))

    def test_a_damaged_measurement_journal_never_stops_the_engine(self):
        self._step()
        for name in MEASURED:
            (self.tmp / name).write_text('{"at": "edited by hand"}\nnot json at all\n', encoding="utf-8")
        self.nt._chain_checked = 0.0  # the next step checks the chains again
        self.nt.n["health_log_seconds"] = 0
        self.feeds.items["BBB"].append(("BBB wins an appeal", self.now))
        self._step()  # no ChainBroken
        self.assertEqual(len(journal.read("news_scores.jsonl")), 4)

    def test_rows_that_cannot_be_written_never_cost_a_score(self):
        append = journal.append

        def full(name, record):
            if name in MEASURED:
                raise OSError("disk full")
            return append(name, record)
        self.nt.n["health_log_seconds"] = 0
        with mock.patch.object(journal, "append", full):
            self._step()
            self.feeds.items["BBB"].append(("BBB wins an appeal", self.now))
            self._step()
        self.assertEqual(len(journal.read("news_scores.jsonl")), 4)  # every fresh headline was scored and journaled
        errs = journal.read("news_errors.jsonl")
        self.assertEqual(sorted(r["where"] for r in errs), sorted(MEASURED))  # each on record once, not once per row
        self.assertEqual({r["error"] for r in errs}, {"OSError"})


if __name__ == "__main__":
    unittest.main()
