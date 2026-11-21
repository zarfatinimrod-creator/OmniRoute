"""A waiting news exit is cancelled only with the owner's words (the owner's decision of 2026-11-11, state/backlog.md
item 63).

A cancel keeps a position open, which is more risk, and Claude may only reduce risk. `news-exit SYMBOL --cancel`
therefore needs `--said` with the owner's own words, and every cancel is a row in state/news_exit_cancels.jsonl. That
journal is not hash-chained, like news_holds.jsonl (the other journal of the owner's word): the engine does not read
it, and a problem with it must never stop the engine.
"""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import io
import unittest
from datetime import datetime
from unittest import mock

from aitrader import __main__ as cli
from aitrader import journal, news_live
from test_news_inputs import TempState


class CancelOnTheOwnersWord(TempState):
    def setUp(self):
        super().setUp()
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))  # the command prints the requests file

    def ask(self):
        return cli.main(["news-exit", "BBB", "--reason", "wrong data"])

    def test_a_cancel_without_the_owners_words_is_refused_and_changes_nothing(self):
        self.assertEqual(self.ask(), 0)
        before = journal._path("news_exits.json").read_bytes()
        for extra in ([], ["--said", ""], ["--said", "   "]):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", *extra]), 2)
                self.assertIn("needs --said", err.getvalue())
        self.assertEqual(journal._path("news_exits.json").read_bytes(), before)
        self.assertFalse(journal._path("news_exit_cancels.jsonl").exists())

    def test_a_cancel_with_his_words_drops_the_request_and_is_on_record(self):
        self.assertEqual(self.ask(), 0)
        self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", "--said", "תבטל, טעות בשם המניה"]), 0)
        self.assertNotIn("BBB", news_live.exit_requests()[0])
        row = journal.read("news_exit_cancels.jsonl")[-1]
        self.assertEqual((row["symbol"], row["said"], row["request"]["reason"]), ("BBB", "תבטל, טעות בשם המניה", "wrong data"))
        self.assertIsNotNone(datetime.fromisoformat(row["at"]).tzinfo)  # the command stamps the row: not chained

    def test_nothing_waiting_is_exit_1_and_leaves_no_row(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", "--said", "תבטל"]), 1)
        self.assertFalse(journal._path("news_exit_cancels.jsonl").exists())

    def test_said_without_cancel_is_refused_and_no_request_is_made(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["news-exit", "BBB", "--reason", "x", "--said", "y"]), 2)
        self.assertIn("--said belongs to --cancel", err.getvalue())
        self.assertNotIn("BBB", news_live.exit_requests()[0] or {})

    def test_a_cancel_that_cannot_be_written_down_says_so_and_is_exit_1(self):
        self.assertEqual(self.ask(), 0)
        with mock.patch.object(journal, "append", side_effect=OSError("disk")), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", "--said", "תבטל"]), 1)
        self.assertIn("could not be written down", err.getvalue())

    def test_the_new_file_is_not_one_the_engine_checks(self):
        self.assertNotIn("news_exit_cancels.jsonl", journal.NEWS_CHAINED)


if __name__ == "__main__":
    unittest.main()
