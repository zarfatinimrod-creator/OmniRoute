### Task 5: Start checks and the halt codes

**Kind:** BUILD. **Spec:** 5.4, 5.3 (codes 4, 5, 6, 7), 4.4 (`--check`).

**Files:** Modify `aitrader/news_live.py` (module: `tree_busy`, `start_checks`; `run`, `_run`; `NewsTrader._buys_blocked`, `adopt_previous`, `_beat`), `aitrader/__main__.py` (`news-live`: `--check`; `run` is called with keywords), `skills/trader/SKILL.md` (section 3ב: the code list), `tests/test_news_guards.py` (`OneEngine`: the stand-in for `run` takes `**k`). Test: `tests/test_news_supervised.py` (class `StartChecks`), `tests/test_supervise.py` (class `PullBesideRestarts`).

**Interfaces:** Consumes `ownerlines` (E1, R5d), `_beat`, `adopt_previous`. Produces:

```python
def tree_busy(start: Path | None = None) -> bool   # walks up from start (default: the state directory) to the first .git (a directory, or a "gitdir:" file);
                                                   # true when it holds rebase-merge, rebase-apply or MERGE_HEAD. No git command.
def start_checks(cfg: dict) -> tuple[int, str, dict | None]
    # (0, "", None) | (5, "calendar", None) | (7, "tree_busy", None) | (6, "book", None) | (0, "", {"side": "BUY" | "SELL", "symbol": str})
def run(until_ny="16:05", max_minutes=None, prime=True, check=False) -> int
```

- `start_checks` only reads and decides: it sends nothing and writes nothing. `_run` calls it after the lock and before the trader is built: check 3 is about a book file that `NewsTrader.__init__` cannot load, so it cannot wait for the trader (spec 5.1 names the other order). Its order: calendar (5), pull in progress (7), book (6: the file does not parse, or it is missing while `news_trades.jsonl` has rows), mismatch (the last readable row of `news_trades.jsonl` is a BUY of a name the book does not hold, or a SELL of a name it still holds in the same quantity).
- `_run` acts on the answer. 5: the existing urgent calendar alert, then return 5. 7: it prints `[news] start refused: tree_busy (exit 7)` and returns 7; nothing is sent. 6: it prints `[news] start refused: book (exit 6)`, sends the R5d text itself (`notify.send("AI Trader - תקלה", <R5d>, cfg, "urgent")`) and returns 6: until Task 20 no parent exists to say it, and the live watchdog prompts would start the engine again in silence (from Task 8 on a supervised engine leaves that line to its parent). It returns 4 on `ChainBroken` (after the existing alert), else 0.
- `tree_busy` looks upward from the state directory, never from the package: a test run must not read the working checkout's own `.git`.
- On a mismatch the engine starts: `nt.book_mismatch = {...}`; one `news_errors.jsonl` row with `where` "book_mismatch"; `_buys_blocked` answers first, before the loss review: `("book_mismatch", "התיק לא תואם ליומן העסקאות. עד שסשן הסוחר מיישב את זה אין קניות חדשות. סטופים ומכירות עובדים כרגיל")`. This sentence is not in the spec and reaches the owner on a refused buy: the reviewer reads it.
- E1 goes out once per New York day and symbol, not at each of the day's five launches: `notify.send("AI Trader - תקלה", <E1>, cfg, "urgent")` from `_run`, after `adopt_previous` (Task 7 fixes its place: after the first stop look), unless the previous heartbeat's `mismatch_told` is `{"day": <today, New York>, "symbol": <the same>}`. After a send that a channel took, the heartbeat carries that pair; `adopt_previous` keeps a pair of today.
- `news-live --check` (`run(check=True)`): no lock, no trader, no write, nothing sent. It prints one line per check, runs the four start checks and then `journal.broken_chains(journal.NEWS_CHAINED)`, and returns the first failing code (5, 7, 6, 4) or 0; a mismatch is printed and returns 0. The chain is added to what spec 5.4 lists, so that `--clear-halt` (Task 14) cannot clear a halt 4 over a chain that is still broken.
- `skills/trader/SKILL.md` 3ב gets two lines (the bare engine runs under the old watchdog prompts until Task 20): `- קודי יציאה של המנוע: 0 הגיע לשעת הסיום, 3 מנוע אחר מחזיק את התיק, 4 יומן פגום, 5 לוח החגים לא מכסה את השנה, 6 קובץ התיק חסר או לא קריא, 7 משיכה מ-git באמצע, 143 עצירה מתוכננת.` and `- אחרי 4, 5 או 6 לא מפעילים שוב עד שהסיבה טופלה; אחרי 7 משלימים את המשיכה (או git merge --abort) ומפעילים.`

- [ ] Write class `StartChecks(_Engine)`; `start()` is `news_live._run("23:59", 0.0005, False)` with `poll_headlines`, `time.sleep` and `load_config` replaced:

```python
    def test_a_calendar_that_does_not_cover_today_ends_the_engine_with_5(self):      # journal.calendar_covers -> False
        self.assertEqual(news_live.start_checks(self.cfg)[:2], (5, "calendar"))
        self.assertEqual(self.start(), 5)
        self.assertEqual([p for p, _ in self.sent], ["urgent"])

    def test_a_pull_in_progress_is_7_and_sends_nothing(self):
        for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD"):
            root = Path(tempfile.mkdtemp()); state = root / "ai-trader" / "state"
            state.mkdir(parents=True); (root / ".git").mkdir()
            self.assertFalse(news_live.tree_busy(state))
            (root / ".git" / name).mkdir()
            self.assertTrue(news_live.tree_busy(state), name)
        with mock.patch.object(news_live, "tree_busy", lambda start=None: True), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(news_live.start_checks(self.cfg)[:2], (7, "tree_busy"))
            self.assertEqual(self.start(), 7)
        self.assertEqual((self.sent, "[news] start refused: tree_busy (exit 7)" in out.getvalue()), ([], True))

    def test_trades_with_no_readable_book_is_6_said_once_and_the_file_is_not_written_over(self):   # one BUY row in news_trades.jsonl
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
        self.assertEqual(cli.main(["news-live", "--check"]), 0)
        with mock.patch.object(journal, "broken_chains", lambda names=None: ["news_trades.jsonl"]):
            self.assertEqual(cli.main(["news-live", "--check"]), 4)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), before)
```

- [ ] Write class `PullBesideRestarts(Procs)`. Its `setUp` makes a bare "origin" and a clone in the temporary directory, with `clone/ai-trader/state/` as the engine's state directory, holding a committed book with one position and a `news_trades.jsonl` of two rows written with `journal.append`. Every git call of the class gets `env={**no_phone.clean_env(), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", **{f"GIT_{who}_{what}": "test" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL")}}`: the user's signing, hooks and identity must not be used. Two tests:
  - `test_a_merge_left_open_refuses_the_start_with_7_and_the_book_is_untouched`: a second clone commits and pushes a change to `notes.txt`; the first clone commits a different change to the same file, then `git fetch` and `git merge --no-edit` stop on the conflict. Assert: a start with `--minutes 0.002` returns 7 and the bytes of `news_book.json` are unchanged; after `git merge --abort` a start returns 0.
  - `test_a_restart_loop_beside_a_fetch_and_merge_leaves_book_and_chains_as_they_were`: one thread, 5 times: commit a change to another file in the second clone, push it, then `git fetch` and `git merge --no-edit` in the first. Meanwhile 10 engine starts with `--minutes 0.002`. Assert: every start returned 0 or 7, `news_book.json` holds the same position, and `journal.verify_chain("news_trades.jsonl")` on that directory is `(True, 2)`.
- [ ] Run `-k StartChecks` and `-k PullBesideRestarts`. Expected: `AttributeError: module 'aitrader.news_live' has no attribute 'start_checks'`.
- [ ] Implement as above; the calendar alert leaves its old place in `_run` (it now precedes the return of 5).
- [ ] Run both: 7 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/aitrader/__main__.py ai-trader/skills/trader/SKILL.md ai-trader/tests/test_news_supervised.py ai-trader/tests/test_supervise.py ai-trader/tests/test_news_guards.py`; message `feat(ai-trader): the engine checks calendar, checkout and book before it starts, and leaves with a code that says why`.

