### Task 8c: A waiting exit is cancelled only with the owner's words (backlog item 63, the owner's decision of 2026-11-11)

**Kind:** BUILD. **Authority:** not the supervisor spec. The owner's decision recorded in `ai-trader/state/backlog.md`,
item 63, and in `ai-trader/CLAUDE.md` (the loss protocol, step 5, and hard rule 3): "a request that is still waiting is
taken back (`news-exit SYMBOL --cancel`) only on Nimrod's word, and the cancel is written down with his words."
Gate: rule 4 as for a news-engine lever (quant-critic, unit suite; no time machine sweep).

**Why:** cancelling an exit keeps a position open, which is more risk, and Claude may only reduce risk. Today
`news-exit SYMBOL --cancel` drops the waiting request and leaves no trace anywhere. The code now keeps what the law
says: no cancel without his words, and every cancel on record.

**Files:** Modify `aitrader/__main__.py` (the `news-exit` parser and branch; the usage line in the module docstring),
`skills/trader/SKILL.md` (section 3ב, the `news-exit` block), `config.json` (the words about `--cancel` in
`news._note`; no new key, no number). Test: create `tests/test_news_exit_cancel.py`.

**Interfaces:** Consumes `news_live.update_exits`, `news_live._clean`, `journal.append`, `helpers.no_phone` (Task 2).
Produces:

- `news-exit SYMBOL --cancel --said TEXT`. `--said` is the owner's own words (cleaned with `_clean(text, 120)`, the
  way `--reason` is).
  - `--cancel` with no `--said`, or with a `--said` that is empty after cleaning: prints to stderr
    `news-exit --cancel needs --said with the owner's words: a waiting exit is taken back only on his word`,
    returns 2, and changes nothing (the requests file is not opened for writing).
  - `--said` without `--cancel`: prints to stderr `--said belongs to --cancel`, returns 2, changes nothing.
  - `--cancel --said TEXT` when no request for SYMBOL is waiting: as today (the existing message, exit 1), and no row.
  - `--cancel --said TEXT` when a request was waiting: the request is dropped as today, and then one row is appended
    with `journal.append("news_exit_cancels.jsonl", {"symbol": SYMBOL, "said": TEXT, "request": <the entry that was
    waiting, as it stood in the file: its reason and requested_at>})`. `journal.append` adds the time and the hash.
    If that append raises, the command prints to stderr
    `the request for SYMBOL was cancelled but the cancel could not be written down: tell the owner` and returns 1.
- `state/news_exit_cancels.jsonl` is a new journal file. It is not added to `journal.NEWS_CHAINED` (the engine does
  not read it and a problem with it must never stop the engine).
- Nothing in `aitrader/news_live.py` changes. A request without `--cancel` behaves exactly as today.
- `skills/trader/SKILL.md` 3ב: the command line `python3 -m aitrader news-exit SYMBOL --cancel         # לבטל בקשה שעוד מחכה`
  becomes `python3 -m aitrader news-exit SYMBOL --cancel --said "..."   # לבטל בקשה שעוד מחכה - רק במילה של נמרוד`,
  and one bullet is added under the block:
  `- ביטול (`--cancel`) רק אחרי שנמרוד אמר. המילים שלו נכנסות ל-`--said` ונרשמות ב-`state/news_exit_cancels.jsonl`. בלי `--said` הפקודה מסרבת, ולא משנה דבר.`
- `config.json` `news._note`: the words "(state/news_exits.json; `--cancel` takes a waiting request back)" become
  "(state/news_exits.json; `--cancel --said TEXT` takes a waiting request back, only on the owner's word, and writes
  it to state/news_exit_cancels.jsonl)".

- [ ] Write `tests/test_news_exit_cancel.py`. It begins with `from helpers import no_phone  # noqa: F401`. The tests
  run `cli.main([...])` on a temporary state directory, the way the existing `news-exit` tests do (find them with
  `grep -n "news-exit" tests/*.py` and reuse their base class or set-up; do not copy it). `ask()` is
  `cli.main(["news-exit", "BBB", "--reason", "wrong data"])`.

```python
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
        self.assertNotIn("BBB", news_live.exit_requests())
        row = journal.read("news_exit_cancels.jsonl")[-1]
        self.assertEqual((row["symbol"], row["said"], row["request"]["reason"]), ("BBB", "תבטל, טעות בשם המניה", "wrong data"))
        self.assertTrue(journal.verify_chain("news_exit_cancels.jsonl")[0])

    def test_nothing_waiting_is_exit_1_and_leaves_no_row(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", "--said", "תבטל"]), 1)
        self.assertFalse(journal._path("news_exit_cancels.jsonl").exists())

    def test_said_without_cancel_is_refused_and_no_request_is_made(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["news-exit", "BBB", "--reason", "x", "--said", "y"]), 2)
        self.assertIn("--said belongs to --cancel", err.getvalue())
        self.assertNotIn("BBB", news_live.exit_requests() or {})

    def test_a_cancel_that_cannot_be_written_down_says_so_and_is_exit_1(self):
        self.assertEqual(self.ask(), 0)
        with mock.patch.object(journal, "append", side_effect=OSError("disk")), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(["news-exit", "BBB", "--cancel", "--said", "תבטל"]), 1)
        self.assertIn("could not be written down", err.getvalue())

    def test_the_new_file_is_not_one_the_engine_checks(self):
        self.assertNotIn("news_exit_cancels.jsonl", journal.NEWS_CHAINED)
```

  Where a helper name differs on the tip (`exit_requests`, `verify_chain`, `_path`), baseline.md and the code are
  right; the assertions stay. Existing tests that call `news-exit ... --cancel` without `--said` now get exit 2: give
  each of them `--said` with a short text (list every such edit in the report); do not change what they assert about
  the request itself.

- [ ] Run `python3 -m unittest discover -s tests -p 'test_news_exit_cancel.py' -v`. Expected: the first test fails
  (`0 != 2`: today a cancel needs no words).
- [ ] Implement as above.
- [ ] Run the file again: 6 tests, `OK`. Then the whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/__main__.py ai-trader/skills/trader/SKILL.md ai-trader/config.json ai-trader/tests/test_news_exit_cancel.py`
  plus any existing test file whose `--cancel` call got `--said`; message
  `feat(ai-trader): a waiting news-exit is cancelled only with the owner's words, and the cancel is on record (backlog 63)`.

**For the report and the gate:** this narrows a lever (a cancel can only keep risk, so it now needs the owner's
words). It changes no buy, no sale and no stop. It touches no file the time machine loads. Forward record: every
cancel is a row in `state/news_exit_cancels.jsonl`, read at the Saturday review.
