"""Basic law, item 3 (Nimrod, 2026-11-09 and 2026-11-10): every realized loss is studied, none is left unexamined, and
the news engine opens no new position while one of its losses has no review."""

import contextlib
import copy
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aitrader import __main__ as cli
from aitrader import journal, news_live, postmortem
from test_core import CFG

REVIEW = {"inside_rules": True, "data_ok": False, "verdict": "bad_data", "causes": ["bad_input"],
          "what": "the scorer was told the stock was flat while it was up 5.82% on the day",
          "lesson": "a wrong input is worse than none", "fix": "the move is read from the daily bars",
          "fix_ref": "commit 896cc1f"}
WHAT, LESSON, FIX = REVIEW["what"], REVIEW["lesson"], REVIEW["fix"]


class _State(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state = journal.STATE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE = self._state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fill(self, name, symbol, side, pnl, reason="stop"):
        journal.append(name, {"date": "2026-11-10", "symbol": symbol, "side": side, "qty": 1, "price": 10.0,
                              "value": 10.0, "realized_pnl": pnl, "reason": reason, "logged_at": journal.now_utc()})


class Ledger(_State):
    def test_only_losing_sells_are_losses(self):
        self._fill("news_trades.jsonl", "AAA", "BUY", 0.0, "news score 9")
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("trades.jsonl", "BBB", "SELL", 12.5, "exit")       # a winner is not a loss
        self._fill("trades.jsonl", "CCC", "SELL", 0.0, "trim")        # break-even is not a loss
        self._fill("trades.jsonl", "DDD", "BUY", -0.4, "entry")       # a fee on a buy is a cost, not a realized loss
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")
        got = postmortem.losses()
        self.assertEqual([(x["book"], x["symbol"], x["realized_pnl"]) for x in got],
                         [("stocks", "EEE", -7.25), ("news", "AAA", -30.0)])
        self.assertEqual(postmortem.pending(), got)
        self.assertEqual([x["symbol"] for x in postmortem.pending("news")], ["AAA"])

    def test_review_clears_pending_and_one_review_can_cover_several_fills(self):
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")
        self._fill("trades.jsonl", "FFF", "SELL", -2.0, "trim")
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        keys = [x["key"] for x in postmortem.pending("stocks")]
        rec = postmortem.record(keys, **{**REVIEW, "verdict": "planned_loss", "inside_rules": True, "data_ok": True})
        self.assertEqual(rec["loss_usd"], -9.25)
        self.assertEqual([x["symbol"] for x in postmortem.pending()], ["AAA"])
        s = postmortem.summary()
        self.assertEqual((s["losing_fills"], s["reviews"], s["pending_usd"], s["realized_loss_usd"]), (3, 1, -30.0, -39.25))

    def test_key_must_name_exactly_one_losing_fill(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        full = postmortem.pending()[0]["key"]
        with self.assertRaises(ValueError):
            postmortem.record(["news:zzzzzzzz"], **REVIEW)     # matches none
        with self.assertRaises(ValueError):
            postmortem.record([], **REVIEW)
        postmortem.record([full.split(":")[1][:10]], **REVIEW)  # a bare hash prefix is enough
        self.assertEqual(len(postmortem.pending()), 1)

    def test_a_key_too_short_to_be_a_key_clears_nothing_even_when_only_one_loss_waits(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        full = postmortem.pending()[0]["key"]
        h = full.split(":")[1]
        self.assertEqual(postmortem.MIN_KEY, 8)
        for short in ("n", "news", "news:", h[:7], "news:" + h[:7], "stocks:" + h, "nope:" + h, ":" + h[:7]):
            with self.assertRaises(ValueError, msg=short):       # "n" is the book's first letter, not the fill's name
                postmortem.record([short], **REVIEW)
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))
        postmortem.record(["news:" + h[:8]], **REVIEW)          # eight characters of the hash, in its own book
        self.assertEqual(postmortem.pending(), [])

    def test_how_much_of_the_hash_names_a_sale_is_set_in_config(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        h = postmortem.pending()[0]["key"].split(":")[1]
        self.assertEqual(CFG["postmortem"]["min_key_chars"], postmortem.MIN_KEY)
        with mock.patch("aitrader.data.load_config", lambda book="stocks": {"postmortem": {"min_key_chars": 12}}):
            with self.assertRaises(ValueError):
                postmortem.record([h[:11]], **REVIEW)
            postmortem.record([h[:12]], **REVIEW)
        self.assertEqual(postmortem.pending(), [])

    def test_one_review_is_of_one_book(self):
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")
        self._fill("trades.jsonl", "FFF", "SELL", -2.0, "trim")
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        e, f, a = (x["key"] for x in postmortem.pending())
        with self.assertRaises(ValueError) as err:
            postmortem.record([e, a], **REVIEW)                   # an unrelated stock loss cleared with the news text
        self.assertIn("one book", str(err.exception))
        self.assertEqual(len(postmortem.pending()), 3)
        postmortem.record([e, f], **REVIEW)                       # the losing trims of one rebalance: one review
        self.assertEqual([x["key"] for x in postmortem.pending()], [a])

    def test_where_the_fix_lives_is_more_than_a_letter(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = [postmortem.pending()[0]["key"]]
        for ref in ("x", "abc123", "  a  b  "):
            with self.assertRaises(ValueError, msg=ref):
                postmortem.record(key, **{**REVIEW, "fix_ref": ref})
        rec = postmortem.record(key, **{**REVIEW, "fix_ref": "  896cc1f "})   # a short commit hash is enough
        self.assertEqual(rec["fix_ref"], "896cc1f")

    def test_a_review_needs_its_answers(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = [postmortem.pending()[0]["key"]]
        for bad in ({"verdict": "whatever"}, {"what": " "}, {"lesson": ""}, {"fix": ""}, {"causes": [" "]}):
            with self.assertRaises(ValueError, msg=str(bad)):
                postmortem.record(key, **{**REVIEW, **bad})
        self.assertEqual(len(postmortem.pending()), 1)          # a refused review covers nothing

    def test_a_cause_named_twice_is_a_repeated_mistake(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        a, b = (x["key"] for x in postmortem.pending())
        postmortem.record([a], **{**REVIEW, "causes": ["Bad Input", "priced_in"]})
        self.assertEqual(postmortem.repeated(), {})
        postmortem.record([b], **{**REVIEW, "causes": ["bad_input"]})
        self.assertEqual(postmortem.repeated(), {"bad_input": 2})

    def test_looking_never_creates_a_crypto_directory(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        postmortem.summary()
        self.assertFalse((self.tmp / "crypto").exists())

    def test_crypto_fills_are_listed_and_the_ledger_stays_in_the_stock_directory(self):
        with journal.use_book("crypto"):
            self._fill("trades.jsonl", "BTC-USD", "BUY", -0.5, "entry")
            self._fill("trades.jsonl", "BTC-USD", "SELL", -40.0, "exit")
            got = postmortem.pending()
            self.assertEqual([(x["book"], x["symbol"]) for x in got], [("crypto", "BTC-USD")])
            postmortem.record([got[0]["key"]], **REVIEW)
        self.assertTrue((self.tmp / postmortem.LEDGER).exists())
        self.assertEqual(postmortem.pending(), [])

    def test_a_loss_of_one_cent_is_a_loss(self):
        self._fill("trades.jsonl", "EEE", "SELL", -0.01, "trim")
        self._fill("news_trades.jsonl", "AAA", "SELL", -0.01)
        self.assertEqual([(x["book"], x["realized_pnl"]) for x in postmortem.pending()],
                         [("stocks", -0.01), ("news", -0.01)])     # "any size": there is no dust threshold

    def test_every_review_keeps_covering_its_fills(self):
        for sym, pnl in (("AAA", -30.0), ("BBB", -5.0), ("CCC", -1.0)):
            self._fill("news_trades.jsonl", sym, "SELL", pnl)
        a, b, c = (x["key"] for x in postmortem.pending())
        postmortem.record([a], **REVIEW)
        postmortem.record([b], **{**REVIEW, "causes": ["other"]})
        self.assertEqual([x["key"] for x in postmortem.pending()], [c])   # the first review still counts after the second
        postmortem.record([c], **{**REVIEW, "causes": ["third"]})
        self.assertEqual(postmortem.pending(), [])

    def test_a_fill_named_twice_in_one_review_is_covered_once(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = postmortem.pending()[0]["key"]
        rec = postmortem.record([key, key.split(":")[1][:12], key], **REVIEW)
        self.assertEqual((rec["keys"], len(rec["fills"]), rec["loss_usd"]), ([key], 1, -30.0))

    def test_a_key_is_a_prefix_not_a_fragment(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = postmortem.pending()[0]["key"]
        with self.assertRaises(ValueError):
            postmortem.record([key[8:]], **REVIEW)                 # the middle of the hash names nothing
        self.assertEqual(len(postmortem.pending()), 1)

    def test_reviews_are_read_from_the_stock_directory_whatever_book_is_active(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        with journal.use_book("crypto"):
            self._fill("trades.jsonl", "BTC-USD", "SELL", -40.0, "exit")
            for i, x in enumerate(postmortem.pending()):          # one review per book: they are two events
                postmortem.record([x["key"]], **{**REVIEW, "causes": [f"c{i}"]})
            self.assertEqual(postmortem.pending(), [])            # `verify --book crypto` must not list them again
            self.assertEqual(len(postmortem.reviews()), 2)
        self.assertFalse((self.tmp / "crypto" / postmortem.LEDGER).exists())

    def test_a_review_line_that_cannot_be_read_puts_its_fills_back_on_the_list(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        a, b = (x["key"] for x in postmortem.pending())
        postmortem.record([a], **REVIEW)
        postmortem.record([b], **{**REVIEW, "causes": ["other"]})
        ledger = self.tmp / postmortem.LEDGER
        first, second = ledger.read_text(encoding="utf-8").splitlines()
        ledger.write_text(first[: len(first) // 2] + "\n" + second + "\n", encoding="utf-8")   # review 1 is torn
        with contextlib.redirect_stdout(io.StringIO()):            # journal.read reports the line it skipped
            self.assertEqual([x["key"] for x in postmortem.pending()], [a])   # fail closed: unreviewed again

    def test_one_review_naming_a_tag_twice_is_not_a_repeat(self):
        journal.append(postmortem.LEDGER, {"keys": [], "causes": ["bad_input", "bad_input"]})   # a hand-written row
        self.assertEqual(postmortem.repeated(), {})

    def test_a_review_is_more_than_a_word(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = [postmortem.pending()[0]["key"]]
        self.assertEqual(postmortem.MIN_CHARS, CFG["postmortem"]["min_chars"])
        for field, n in postmortem.MIN_CHARS.items():
            for short in ("x" * (n - 1), "x" + " " * n + "y"):      # padding with spaces is not text
                with self.assertRaises(ValueError, msg=(field, short)):
                    postmortem.record(key, **{**REVIEW, field: short})
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))
        postmortem.record(key, **{**REVIEW, **{f: "x" * n for f, n in postmortem.MIN_CHARS.items()}})   # the line itself is enough
        self.assertEqual(postmortem.pending(), [])

    def test_the_shortest_review_is_set_in_config_and_a_config_that_cannot_be_read_keeps_the_default(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        a, b = ([x["key"]] for x in postmortem.pending())
        with mock.patch("aitrader.data.load_config", lambda book="stocks": {"postmortem": {"min_chars": {"what": 3}}}):
            postmortem.record(a, **{**REVIEW, "what": "abc"})
            with self.assertRaises(ValueError):
                postmortem.record(b, **{**REVIEW, "lesson": "abc"})  # the fields config does not name keep their default

        def stocks_unreadable(book="stocks"):
            if book == "stocks":
                raise OSError("no config")
            return {}
        with mock.patch("aitrader.data.load_config", stocks_unreadable):
            with self.assertRaises(ValueError):
                postmortem.record(b, **{**REVIEW, "what": "abc"})
        self.assertEqual(len(postmortem.pending()), 1)

    def test_the_answers_must_agree_with_the_verdict(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = [postmortem.pending()[0]["key"]]
        planned = {"verdict": "planned_loss", "inside_rules": True, "data_ok": True, "fix_ref": ""}
        for bad in ({**planned, "inside_rules": False},              # a planned loss is inside the rules...
                    {**planned, "data_ok": False},                   # ...and on good data
                    {"verdict": "bad_data", "data_ok": True},
                    {"verdict": "rule_broken", "inside_rules": True, "data_ok": True},
                    {"verdict": "bad_data", "fix_ref": ""},          # every verdict but a planned loss says where its fix lives
                    {"verdict": "bad_rule", "data_ok": True, "fix_ref": "  "},
                    {"verdict": "ops_defect", "data_ok": True, "fix_ref": ""},
                    {"verdict": "rule_broken", "inside_rules": False, "fix_ref": ""}):
            with self.assertRaises(ValueError, msg=str(bad)):
                postmortem.record(key, **{**REVIEW, **bad})
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))
        rec = postmortem.record(key, **{**REVIEW, **planned})         # a planned loss needs no fix to point at
        self.assertEqual((rec["verdict"], rec["fix_ref"]), ("planned_loss", ""))

    def test_each_verdict_is_accepted_with_answers_that_fit_it(self):
        fits = {"bad_data": (True, False), "bad_rule": (True, True), "rule_broken": (False, True),
                "ops_defect": (True, True), "planned_loss": (True, True)}
        self.assertEqual(set(fits), set(postmortem.VERDICTS))
        for i, (verdict, (inside, ok)) in enumerate(fits.items()):
            self._fill("news_trades.jsonl", f"S{i}", "SELL", -1.0 - i)
            key = [postmortem.pending()[0]["key"]]
            rec = postmortem.record(key, **{**REVIEW, "verdict": verdict, "inside_rules": inside, "data_ok": ok, "causes": [f"c{i}"]})
            self.assertEqual((rec["verdict"], rec["inside_rules"], rec["data_ok"]), (verdict, inside, ok))
        self.assertEqual(postmortem.pending(), [])
        self.assertEqual(postmortem.summary()["by_verdict"], {v: 1 for v in fits})

    def test_a_loss_is_reviewed_once(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        a, b = (x["key"] for x in postmortem.pending())
        postmortem.record([a], **REVIEW)
        for again in ([a], [b, a]):                                # alone, or slipped in next to a new one
            with self.assertRaises(ValueError) as e:
                postmortem.record(again, **{**REVIEW, "causes": ["other"]})
            self.assertIn("already reviewed", str(e.exception))
            self.assertIn(a, str(e.exception))
        self.assertEqual((len(postmortem.reviews()), [x["key"] for x in postmortem.pending()]), (1, [b]))
        self.assertEqual(postmortem.repeated(), {})                # one loss, one review: its cause is named once

    def test_a_repeat_counts_losses_not_reviews_and_a_planned_loss_is_never_one(self):
        for sym, pnl in (("AAA", -30.0), ("BBB", -5.0), ("CCC", -1.0), ("DDD", -2.0), ("EEE", -3.0)):
            self._fill("news_trades.jsonl", sym, "SELL", pnl)
        a, b, c, d, e = (x["key"] for x in postmortem.pending())
        planned = {**REVIEW, "verdict": "planned_loss", "inside_rules": True, "data_ok": True, "causes": ["stop_did_its_job"]}
        postmortem.record([a], **planned)
        postmortem.record([b], **planned)                           # a stop doing its job twice is not a mistake made twice
        self.assertEqual(postmortem.repeated(), {})
        postmortem.record([c, d], **{**REVIEW, "causes": ["bad_input"]})   # two losses under one review are still two losses
        self.assertEqual(postmortem.repeated(), {"bad_input": 2})
        postmortem.record([e], **{**REVIEW, "causes": ["Bad Input", "late"]})
        s = postmortem.summary()
        self.assertEqual(s["repeated_causes"], {"bad_input": 3})
        self.assertEqual(s["causes_used"], {"bad_input": 2, "late": 1, "stop_did_its_job": 2})   # the tags to choose from

    def test_a_ledger_line_that_is_not_a_review_reviews_nothing(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = postmortem.pending()[0]["key"]
        good = {"keys": [key], "verdict": "bad_data", "causes": ["bad_input"], "what": WHAT, "lesson": LESSON, "fix": FIX}
        for bad in ("just a string", ["a", "list"], {**good, "verdict": "fine"}, {**good, "keys": key},
                    {**good, "what": "  "}, {**good, "lesson": None}, {**good, "fix": 7}, {**good, "causes": []},
                    {**good, "causes": "bad_input"}, {k: v for k, v in good.items() if k != "verdict"}):
            journal.write_all(postmortem.LEDGER, [bad])
            self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1), bad)
            postmortem.summary()                                    # and the tool that lists them keeps working
        journal.write_all(postmortem.LEDGER, [good])
        self.assertEqual(postmortem.pending(), [])

    def test_where_fills_pay_a_fee_a_sale_that_does_not_cover_it_is_a_loss(self):
        def sale(sym, pnl, fee):
            journal.append("trades.jsonl", {"date": "2026-11-10", "symbol": sym, "side": "SELL", "qty": 1, "price": 10.0,
                                            "realized_pnl": pnl, "fee": fee, "reason": "exit"})
        with journal.use_book("crypto"):
            sale("AAA-USD", 0.30, 0.50)       # the gain does not cover a fee of the sale's own size: the round trip lost
            sale("BBB-USD", 0.50, 0.50)       # exactly covered: not a loss
            sale("CCC-USD", 0.80, 0.50)
            sale("DDD-USD", -0.10, "n/a")     # a fee that is not a number: the row is skipped, never guessed
            got = postmortem.losses("crypto")
            self.assertEqual([(x["symbol"], x["realized_pnl"], x["loss"]) for x in got], [("AAA-USD", 0.3, -0.2)])
            s = postmortem.summary()                              # the sums speak of what was lost, with the right sign
            self.assertEqual((s["pending_usd"], s["realized_loss_usd"]), (-0.2, -0.2))
            rec = postmortem.record([got[0]["key"]], **REVIEW)
            self.assertEqual(rec["loss_usd"], -0.2)
        self._fill("news_trades.jsonl", "AAA", "SELL", 0.30)       # no fee in this book: a gain is a gain
        self.assertEqual(postmortem.losses("news"), [])

    def test_a_crypto_config_that_cannot_be_read_is_an_error_not_an_empty_list(self):
        with mock.patch("aitrader.data.load_config", side_effect=ValueError("bad json")):
            with self.assertRaises(ValueError):
                postmortem.losses()

    def test_a_fill_without_a_hash_still_gets_its_own_key(self):
        journal.write_all("news_trades.jsonl", [                    # rows no chain ever hashed (hand-written, legacy)
            {"date": "2026-11-10", "symbol": "AAA", "side": "SELL", "realized_pnl": -30.0},
            {"date": "2026-11-10", "symbol": "BBB", "side": "SELL", "realized_pnl": -5.0}])
        a, b = (x["key"] for x in postmortem.pending())
        self.assertNotEqual(a, b)
        self.assertEqual([x["key"] for x in postmortem.pending()], [a, b])   # the same key on every read
        postmortem.record([a], **REVIEW)
        self.assertEqual([x["symbol"] for x in postmortem.pending()], ["BBB"])


class Cli(_State):
    def _run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_list_record_and_verify_line(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        code, out, _ = self._run("postmortem")
        self.assertEqual(code, 0)
        self.assertIn('"pending_usd": -30.0', out)
        _, out, _ = self._run("verify")
        self.assertIn("LOSSES AWAITING REVIEW: 1", out)
        key = postmortem.pending()[0]["key"]
        code, _, err = self._run("postmortem", "--record", "--keys", key)
        self.assertEqual(code, 2)                               # the three answers are required
        code, out, _ = self._run("postmortem", "--record", "--keys", key, "--inside-rules", "yes", "--data-ok", "no",
                                 "--verdict", "bad_data", "--causes", "bad_input", "--what", WHAT, "--lesson", LESSON, "--fix", FIX, "--fix-ref", "commit 896cc1f")
        self.assertEqual(code, 0)
        self.assertIn('"pending": []', out)
        _, out, _ = self._run("verify")
        self.assertNotIn("LOSSES AWAITING REVIEW", out)

    ANSWERS = ["--inside-rules", "yes", "--data-ok", "no", "--verdict", "bad_data"]
    TEXT = ["--causes", "bad_input", "--what", WHAT, "--lesson", LESSON, "--fix", FIX, "--fix-ref", "commit 896cc1f"]

    def test_verify_counts_every_book_and_a_waiting_review_is_not_a_failure(self):
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")
        with journal.use_book("crypto"):
            self._fill("trades.jsonl", "BTC-USD", "SELL", -40.0, "exit")
        for argv in (("verify",), ("verify", "--book", "crypto")):
            code, out, _ = self._run(*argv)
            self.assertIn("LOSSES AWAITING REVIEW: 2 (-$47.25)", out, argv)
            self.assertIn("ALL CHAINS OK", out, argv)
            self.assertEqual(code, 0, argv)   # sessions stop on a verify that exits 1: a waiting review must not stop a cycle

    def test_verify_survives_a_review_ledger_it_cannot_use(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        with mock.patch.object(postmortem, "pending", side_effect=OSError("disk")):
            code, out, _ = self._run("verify")
        self.assertEqual(code, 0)
        self.assertIn("ALL CHAINS OK", out)
        self.assertIn("postmortem check failed: OSError", out)   # said out loud, never silent, never fatal

    def test_verify_names_a_cause_that_came_back(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        self._fill("news_trades.jsonl", "BBB", "SELL", -5.0)
        a, b = (x["key"] for x in postmortem.pending())
        postmortem.record([a], **REVIEW)
        self.assertNotIn("REPEATED CAUSES", self._run("verify")[1])
        postmortem.record([b], **REVIEW)
        code, out, _ = self._run("verify")
        self.assertEqual(code, 0)
        self.assertIn("REPEATED CAUSES: bad_input (2 losses)", out)

    def test_a_list_that_cannot_be_built_exits_1_and_says_which_file(self):
        with mock.patch.object(postmortem, "summary", side_effect=OSError("disk")):
            code, out, err = self._run("postmortem")
        self.assertEqual((code, out), (1, ""))
        self.assertIn(postmortem.LEDGER, err)

    def test_news_status_shows_a_loss_that_waits(self):
        import json as _json
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        got = _json.loads(self._run("news-status")[1])
        self.assertEqual([x["symbol"] for x in got["losses_awaiting_review"]], ["AAA"])
        with mock.patch.object(postmortem, "pending", side_effect=OSError("disk")):
            got = _json.loads(self._run("news-status")[1])
        self.assertIn("unreadable (OSError)", got["losses_awaiting_review"])

    def test_each_of_the_three_answers_is_required_on_its_own(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        for i in (0, 2, 4):
            answers = self.ANSWERS[:i] + self.ANSWERS[i + 2:]
            code, out, err = self._run("postmortem", "--record", "--keys", "news:", *answers, *self.TEXT)
            self.assertEqual((code, out), (2, ""), self.ANSWERS[i])
            self.assertIn("needs --inside-rules, --data-ok and --verdict", err, self.ANSWERS[i])
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))   # no answer is ever filled in for him

    def test_a_refused_review_exits_2_and_writes_nothing(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        code, out, err = self._run("postmortem", "--record", "--keys", "news:zzzzzzzz", *self.ANSWERS, *self.TEXT)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("names 0 losing fills", err)
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))

    def test_the_review_is_recorded_as_it_was_given(self):
        self._fill("news_trades.jsonl", "BBB", "SELL", -7.25)
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        keys = ",".join(x["key"] for x in postmortem.pending())
        code, _, _ = self._run("postmortem", "--record", "--keys", keys, *self.ANSWERS, "--causes", "Bad Input, priced_in",
                               "--what", WHAT, "--lesson", LESSON, "--fix", FIX, "--fix-ref", "backlog 12")
        self.assertEqual(code, 0)
        (rec,) = postmortem.reviews()
        self.assertEqual((rec["inside_rules"], rec["data_ok"], rec["verdict"], rec["causes"], len(rec["keys"]), rec["loss_usd"],
                          rec["fix_ref"]), (True, False, "bad_data", ["bad_input", "priced_in"], 2, -37.25, "backlog 12"))
        self.assertEqual(postmortem.pending(), [])


    def test_the_answers_of_a_review_without_the_word_record_write_nothing_and_say_so(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = postmortem.pending()[0]["key"]
        code, out, err = self._run("postmortem", "--keys", key, *self.ANSWERS, *self.TEXT)   # --record forgotten
        self.assertEqual((code, out), (2, ""))
        self.assertIn("--record", err)
        self.assertEqual((postmortem.reviews(), len(postmortem.pending())), ([], 1))
        self.assertEqual(self._run("postmortem")[0], 0)           # the plain list is still the plain list

    def test_a_ledger_that_cannot_be_written_is_said_without_a_traceback_and_the_loss_stays(self):
        self._fill("news_trades.jsonl", "AAA", "SELL", -30.0)
        key = postmortem.pending()[0]["key"]
        (self.tmp / postmortem.LEDGER).mkdir()
        code, out, err = self._run("postmortem", "--record", "--keys", key, *self.ANSWERS, *self.TEXT)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("NOT written", err)
        self.assertIn(postmortem.LEDGER, err)


class NewsEngineWaitsForTheReview(_State):
    def setUp(self):
        super().setUp()
        self.prices = {"AAA": 100.0, "BBB": 50.0, "SPY": 500.0}
        self._lp, self._mo = news_live.live_price, news_live.market_open_now
        news_live.live_price = lambda s: (self.prices.get(s), 0.0)
        news_live.market_open_now = lambda: True
        self.cfg = copy.deepcopy(CFG)
        self.cfg["universe"] = {"AAA": "Tech", "BBB": "Tech", "SPY": "Index"}

    def tearDown(self):
        news_live.live_price, news_live.market_open_now = self._lp, self._mo
        super().tearDown()

    def _item(self, key, sym):
        return {"key": key, "symbol": sym, "title": f"{sym} wins huge contract", "published": "2026-11-09T14:00:00+00:00",
                "price": self.prices[sym], "day_move_pct": 0.0}

    def _lose_on_aaa(self, nt):
        nt.handle_scored([self._item("a", "AAA")], {"a": {"score": 10, "why": "x"}}, [])
        self.prices["AAA"] = nt.book.positions["AAA"]["avg_cost"] * 0.96
        nt.check_stops([])
        self.assertNotIn("AAA", nt.book.positions)
        self.assertEqual(len(postmortem.pending("news")), 1)

    def test_no_new_position_until_the_loss_is_reviewed(self):
        nt = news_live.NewsTrader(self.cfg)
        self._lose_on_aaa(nt)
        ev = []
        nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, ev)
        self.assertNotIn("BBB", nt.book.positions)
        self.assertTrue(any("BBB" in e and "תוחקר" in e for e in ev), ev)
        postmortem.record([postmortem.pending("news")[0]["key"]], **REVIEW)
        nt.handle_scored([self._item("c", "BBB")], {"c": {"score": 10, "why": "x"}}, [])
        self.assertIn("BBB", nt.book.positions)

    def test_the_wait_never_blocks_a_sale(self):
        nt = news_live.NewsTrader(self.cfg)
        nt.handle_scored([self._item("a", "AAA"), self._item("b", "BBB")],
                         {"a": {"score": 10, "why": "x"}, "b": {"score": 10, "why": "x"}}, [])
        self.prices["AAA"] = nt.book.positions["AAA"]["avg_cost"] * 0.96
        nt.check_stops([])                                       # AAA stopped: a loss is now waiting
        self.assertEqual(len(postmortem.pending("news")), 1)
        self.prices["BBB"] = nt.book.positions["BBB"]["avg_cost"] * 0.96
        nt.check_stops([])                                       # BBB's stop still sells
        self.assertNotIn("BBB", nt.book.positions)

    def test_switch_off_restores_the_old_behaviour(self):
        self.cfg["news"]["block_buys_until_loss_reviewed"] = False
        nt = news_live.NewsTrader(self.cfg)
        self._lose_on_aaa(nt)
        nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, [])
        self.assertIn("BBB", nt.book.positions)

    def test_an_unreadable_ledger_blocks_buys_rather_than_allowing_them(self):
        nt = news_live.NewsTrader(self.cfg)
        self._lose_on_aaa(nt)
        orig = postmortem.pending
        postmortem.pending = lambda book=None: (_ for _ in ()).throw(OSError("disk"))
        try:
            ev = []
            nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, ev)
        finally:
            postmortem.pending = orig
        self.assertNotIn("BBB", nt.book.positions)               # fail closed: no data, no trade

    def _two_held_one_stopped(self):
        """AAA and BBB bought on the news, then AAA stopped out: BBB is still held and a news loss is waiting."""
        nt = news_live.NewsTrader(self.cfg)
        nt.handle_scored([self._item("a", "AAA"), self._item("b", "BBB")],
                         {"a": {"score": 10, "why": "x"}, "b": {"score": 10, "why": "x"}}, [])
        self.prices["AAA"] = nt.book.positions["AAA"]["avg_cost"] * 0.96
        nt.check_stops([])
        self.assertEqual((list(nt.book.positions), len(postmortem.pending("news"))), (["BBB"], 1))
        return nt

    def test_the_wait_is_on_when_the_config_does_not_say(self):
        self.cfg["news"].pop("block_buys_until_loss_reviewed", None)
        self.assertIs(news_live.DEFAULTS["block_buys_until_loss_reviewed"], True)
        nt = news_live.NewsTrader(self.cfg)
        self._lose_on_aaa(nt)
        nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, [])
        self.assertNotIn("BBB", nt.book.positions)

    def test_a_loss_in_another_book_does_not_stop_the_news_engine(self):
        self._fill("trades.jsonl", "EEE", "SELL", -7.25, "trim")       # the quant book's own loss, not reviewed
        with journal.use_book("crypto"):
            self._fill("trades.jsonl", "BTC-USD", "SELL", -40.0, "exit")
        self.assertEqual([x["book"] for x in postmortem.pending()], ["stocks", "crypto"])
        nt = news_live.NewsTrader(self.cfg)
        nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, [])
        self.assertIn("BBB", nt.book.positions)

    def test_a_queued_buy_is_not_filled_at_the_open_while_a_loss_waits(self):
        nt = news_live.NewsTrader(self.cfg)
        self._lose_on_aaa(nt)
        news_live.market_open_now = lambda: False                       # a headline after the close is queued, not bought
        nt.handle_scored([self._item("b", "BBB")], {"b": {"score": 10, "why": "x"}}, [])
        self.assertEqual([q["symbol"] for q in nt.queue], ["BBB"])
        news_live.market_open_now = lambda: True
        ev = []
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"BBB": 50.0}):
            nt.run_queue_at_open(ev)
        self.assertNotIn("BBB", nt.book.positions)
        self.assertEqual([(t["symbol"], t["side"]) for t in journal.read("news_trades.jsonl")], [("AAA", "BUY"), ("AAA", "SELL")])
        self.assertTrue(any("BBB" in e and "תוחקר" in e for e in ev), ev)   # the refusal and its reason are on record
        self.assertEqual(nt.queue, [])                                  # turned down once, not tried again every step
        postmortem.record([postmortem.pending("news")[0]["key"]], **REVIEW)
        nt.queue = [{"symbol": "BBB", "score": 9, "why": "big contract", "queued_at": journal.now_utc()}]
        with mock.patch.object(news_live, "official_opens", lambda syms, day: {"BBB": 50.0}):
            nt.run_queue_at_open([])
        self.assertIn("BBB", nt.book.positions)                         # reviewed: the open-queue works as before

    def test_a_bad_news_sale_is_not_held_back(self):
        nt = self._two_held_one_stopped()
        nt.handle_scored([self._item("c", "BBB")], {"c": {"score": 1, "why": "fraud"}}, [])
        self.assertNotIn("BBB", nt.book.positions)
        self.assertTrue(journal.read("news_trades.jsonl")[-1]["reason"].startswith("bad news score 1"))

    def test_a_whole_engine_step_still_checks_the_stops_while_a_loss_waits(self):
        nt = self._two_held_one_stopped()
        self.prices["BBB"] = nt.book.positions["BBB"]["avg_cost"] * 0.96
        with mock.patch.object(nt, "poll_headlines", lambda: []), \
                mock.patch.object(news_live.notify, "send", lambda *a, **kw: []):
            ev = nt.step()
        self.assertNotIn("BBB", nt.book.positions)
        self.assertTrue(any(e.startswith("SELL") and "BBB" in e and "stop" in e for e in ev), ev)

    def test_a_ledger_that_cannot_be_used_stops_buys_and_never_a_sale(self):
        nt = self._two_held_one_stopped()
        (self.tmp / postmortem.LEDGER).write_text("null\n", encoding="utf-8")   # valid JSON, but not a review
        ev = []
        nt.handle_scored([self._item("c", "AAA")], {"c": {"score": 10, "why": "x"}}, ev)   # must come back, not raise
        self.assertEqual(list(nt.book.positions), ["BBB"])              # fail closed: nothing bought
        self.assertTrue(any("AAA" in x and "תוחקר" in x for x in ev), ev)
        self.prices["BBB"] = nt.book.positions["BBB"]["avg_cost"] * 0.96
        nt.check_stops([])
        self.assertEqual(list(nt.book.positions), [])                   # the stop never reads the ledger


if __name__ == "__main__":
    unittest.main()
