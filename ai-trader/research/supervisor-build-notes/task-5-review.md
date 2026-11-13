# Task 5 review - start checks and the halt codes

Diff 8ed84237..001493a6 (1 commit, 6 files, +492 -18), read from review-task-5.diff in two passes (the file is 970 lines).

### Spec Compliance

Compliant. Every item checked against the diff:
- `tree_busy(start=None)`: news_live.py:193-210. It walks up from `journal.STATE` (never the package), follows a `gitdir:` file, looks for the three marks, runs no git command.
- `start_checks(cfg)`: news_live.py:213-246. Order is calendar 5, tree_busy 7, book 6, mismatch. It only reads. The last readable row is the last dict row (a torn line is skipped). SELL counts as a mismatch only when the held qty is the same.
- `_run`: news_live.py:313-324. The checks run after the lock and before `NewsTrader(cfg)`. 5 sends the old calendar alert, unchanged, then returns; the old call site is removed (old 337-340). 7 prints the brief's line and sends nothing. 6 prints its line and sends R5d urgent, with the priority positional. `ChainBroken` sets code 4 (news_live.py:378) and `_run` returns `code` (397).
- Mismatch: news_live.py:327 and 346-361. `nt.book_mismatch` is set; there is one `news_errors.jsonl` row with `where` "book_mismatch"; E1 is said once per New York day and symbol, guarded by `_mismatch_told`. The pair is recorded only when a channel took the line.
- `_buys_blocked`: news_live.py:127-129. It answers first, before the loss review, with the brief's sentence verbatim.
- `adopt_previous`: news_live.py:164-165. It keeps only a pair of today. `_beat` writes it at news_live.py:187.
- `run(..., check=False)` goes to `_check` (news_live.py:249-267, 291-292): no lock, no trader, no write, nothing sent; four start checks, then `broken_chains(NEWS_CHAINED)`; codes 5/7/6/4/0; a mismatch is printed and gives 0.
- `__main__.py:54-55,78`: adds `--check` and passes `check` by keyword.
- SKILL.md:414-415: the two lines, matching the brief.
- Tests: `StartChecks` has the brief's five tests under their names with the brief's assertions (test_news_supervised.py:592-642). The `--check` test adds a `NewsTrader` must-not-be-built guard; it removes nothing. `PullBesideRestarts` has both tests (test_supervise.py:874-957), with `GIT_ENV` verbatim from the brief.
- test_loss_protocol_pins.py: four expectations change from 0 to 4 (lines 442, 465, 488, 511 of the package), allowed by the 10:35 ruling. `test_news_guards.py` is left out, as the controller ruled.

Cannot verify from this diff:
- Whether the refused-buy event carrying the `book_mismatch` sentence reaches the owner inside a message that ends with "כסף נייר". The sentence itself does not end with it, like the existing loss_review sentence. Check the path that turns `_buys_blocked` text into an owner message.
- E1's final place after the first stop look belongs to Task 7. For now E1 goes out after priming and before the loop.
- The behaviour of the old watchdog prompts on exit 5/6 (see Minor 4). It lives in scheduled-task prompts outside the repo.

### Strengths

- The checks are separated cleanly: `start_checks` decides, while `_run` and `_check` act. A refused start builds no trader and changes no state file, and a test asserts this for all three codes (test_news_supervised.py:676-691).
- Review Focus 4 is covered well: torn last line, a JSON line that is not an object, a list symbol, a row with no side, and a book that parses but is not a book. None of them can raise in `start_checks`.
- E1 is guarded like E2: if the line cannot be built or sent, an error row is left and the engine still starts and looks at its stops (test at 773-781).
- E1 dedupe is tested properly: no channel took it, another day, a malformed pair, another name, and no step after the send (719-763).
- The `PullBesideRestarts` deviations make the test meaningful. They are an own commit so each merge writes MERGE_HEAD, and a semaphore so the rounds overlap the starts. Added assertions check that the thread finished and that a 0 was seen.
- Checked (risk: git calls in the engine racing the test's merges and taking `index.lock`): `tests/helpers/engine_child.py:126` stubs `code_stamp`, so engine children run no git beside the merges.
- Checked (risk: R5d/E1 owner lines lacking the paper-money suffix): `ownerlines.py:36-37,50-51`. Both end with "כסף נייר"; the calendar alert keeps "(כסף נייר)".
- No new literal threshold, and no trading-rule change beyond a refused start, held buys on a mismatch, and the exit code after `ChainBroken`.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)
1. news_live.py:236-239 and test_news_supervised.py:666-674: check 6 goes beyond spec 5.4 row 3 ("has rows AND missing or does not parse"). An unparseable or non-book file gives 6 even with an empty journal. Then R5d tells the owner "ויש עסקאות ביומן" when there are none. The action is defensible (otherwise `NewsTrader.__init__` would crash), but the owner text is false in that case. Fix by taking a decision from the controller, or by using a line without that clause.
2. news_live.py:322-323: the R5d send is not guarded. If `owner_line` raises (as the E1 test shows it can, `KeyError("supervisor")`), the start ends with a traceback, exit 1 instead of 6, and nothing is said. E1 and E2 are both guarded. Wrap it like E2, with `error_once`, and return 6.
3. news_live.py:352-353: a failed write of the `book_mismatch` row is dropped with `except Exception: pass`. That is acceptable here, since the failing write is the error journal itself, but it leaves no trace at all. `error_once("book_mismatch_row", e)` would at least try.
4. news_live.py:315-324 (brief-mandated): under the old watchdog prompts ("start again at once"), each relaunch after exit 5 or 6 sends another urgent line until the session follows the new SKILL lines. The implementer's report discloses this; Task 20 resolves it.
5. news_live.py:230: `journal.read("news_trades.jsonl")` is not guarded. If the file cannot be read (OSError), the start ends with a traceback and not one of the codes.
6. __main__.py:78: `run(a.until, a.minutes, check=a.check)`. The brief says "`run` is called with keywords", and until/minutes are still positional. Only `check` is a keyword, and the test pins that shape (test_news_supervised.py:819-823).
7. Process, not in the diff: the report says one of the implementer's scratch mutation runs reached real Yahoo feeds and made four real `claude -p` calls. The constraints forbid any experiment touching the network or the model. The committed tests are now guarded, but the controller should know, and a similar guard note is worth adding for Tasks 7, 8 and 14.
8. test_supervise.py:927-957: the loop test has never been seen to produce a 7 (report concern 4). It guards invariants and does not exercise the 7 path, which is pinned by the first test and in-process. The suite also grew by about 16 s.

### Assessment

Task quality: Approved. Everything the brief asks for is built and tested under its names and assertions, the stop path is unchanged apart from refusing a start, and the remaining points are wording, one unguarded owner-line send, and process notes.
