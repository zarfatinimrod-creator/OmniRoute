# Task 9d review: test robustness and one guard after Task 9c

Reviewer: Opus (task-scoped gate). Diff b9bdd278..55756d5b (one commit), read from `review-task-9d.diff`. Review was read-only on the clone. No `git stash` in any form. `_tasks` was not touched. I ran no tests.

### Spec Compliance

Compliant. Each of the brief's five items has its hunk, and nothing outside them changed.

- Item 1: tests/test_news_supervised.py:1305 is now `3 + 1 + 30 + min(1, news_live.read_heartbeat()["step"])`, the form 9c's review proposed. The second `+ 1` that 9c's report names (line 1346) got the same change.
  - Check: heartbeat `"step"` is `getattr(self, "_steps", 0)` (news_live.py:1708), so it is the loop's step count.
- Item 2: tests/test_news_supervised.py:1711. The assertion on the shared value is gone, and `self.cfg["news"]["unsent_resend_seconds"] = 120` is set before `NewsTrader(self.cfg)` is built.
  - Check: `self.cfg` is `copy.deepcopy(CFG)` (tests/test_news_guards.py:50), so no other test sees the change.
  - Check: the trader reads the key from `self.n` (`ncfg(cfg)`, news_live.py:595; used at 1541 and 1562).
- Item 3: config.json:243. Only the `news._note` line changed: the stat shows 1 insertion and 1 deletion, and the value lines are context only.
  - The new clause is accurate: the late-line retry is gated on `self.n["unsent_resend_seconds"]` at news_live.py:1560-1562.
- Item 4: news_live.py:1996-1999. The loop's own `news_errors.jsonl` append for a failed step is now inside a `try`.
  - On failure it prints `[news] error not journaled (cycle: <class>): <class>`. This is the exact format of `error_once`'s own fallback (news_live.py:123). It carries classes only, never exception text.
  - `fails += 1` and the `alert_after_errors` alert follow it unchanged.
  - Test `test_a_failed_steps_row_that_cannot_be_written_costs_no_traceback_and_the_loop_takes_its_next_step` makes the append raise once. It asserts:
    - `_run` returns 143;
    - two steps ran;
    - exactly one row was refused;
    - the second step's row is on disk;
    - exactly one class-only line was printed.
  - The report's RED shows the `OSError` escaping `_run` at line 1996: the right reason. It also shows GREEN.
  - Check: the stand-in `full_disk(name, row)` matches `journal.append(name, record)` (journal.py:142).
- Item 5: the six-scenario test is now six tests, each named after the original plus a suffix (five starts plus the `.gitignore` check). No assertion was lost:
  - The exit codes 5, 6, 4, 4 and 143 are each still asserted, one per test.
  - The guard-set equality now runs after each start, as exact equality on that start's subset. The union of the subsets is the original seven-guard set, so the check is stronger than before.
  - The per-row keys and class check and the secret check run after every start, in `assert_guard_rows`.
  - The `.gitignore` assertion is its own test.
  - Each test clears `ERRORS_SAID` itself.
- Commit: exactly the three listed files, with the brief's message and no attribution lines (`git log -1 --format=%B`).

Cannot verify from this diff:
- The test file passing 3 times in a row (117 tests) and the whole suite passing (716 tests, `OK`, 103 s) through the safe wrapper are the implementer's claims. The controller's independent run at 55756d5b should confirm them.
- That the `DEFAULTS` twin and the note pin tests stay green rests on the reported suite run. The diff itself cannot break them: no value changed.

### Strengths

- Item 4's guard is minimal and sits in the right place. It is a sibling of the existing guards, writes no second row to a journal that just refused one, and reuses `error_once`'s fallback wording. The stop path and the loop's order are untouched.
- The new item 4 test drives the real `_run` loop to a deterministic planned stop (`max_minutes=None`, STOP on the second step), so it does not depend on timing. It pins the printed line exactly, which also proves the `OSError` text is absent.
- The item 5 split made the assertions stronger: exact per-start guard sets replace one union check.
- The report's mutation table backs the split: each reverted guard fails only the test that owns it.
- The report names honestly where the brief left work undone (9b's sibling test) and why the second `+ 1` change is cosmetic.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- tests/test_news_supervised.py:1346: the `min(1, step)` here is cosmetic.
  - `b["step"] > 0`, two lines below, still fails a run with no step. So this test is exactly as timing-dependent as before; only the failing line moves.
  - The brief allowed the change ("if it has the same assumption"), and it is harmless. If the 0-step case is a real risk at the gate, it needs a deterministic loop (as the item 4 test has), not a count change.
- tests/test_news_supervised.py:~1507: 9b's sibling test `test_a_line_no_channel_took_is_sent_again_at_most_once_every_unsent_resend_seconds` still asserts the shared `unsent_resend_seconds == 120`.
  - A tuned value fails it, which is the same defect item 2 fixed.
  - It is outside the brief, which names one test. It needs the same one-line fix in a later task.
- news_live.py:1998: the new fallback line prints once per failed step for as long as the journal refuses writes. It has no once-per-day dedupe like `error_once`'s `ERRORS_SAID`.
  - Acceptable: the `cycle error` line above it already prints once per failed step, so at worst the log doubles.
- news_live.py:1995, 1997: the `cycle error` print (`str(e)[:200]`) and the row's `"detail": str(e)[:300]` still carry the step's exception text.
  - Both are pre-existing context that 9d did not change. The new line correctly carries classes only.
  - Flagged for the whole-branch review against the "never an exception's text in a log" constraint. The file is git-ignored, as the `in_a_file_git_ignores` test pins.
- Housekeeping: the throwaway mutation copies `.../scratchpad/mut9d-m1` to `mut9d-m4` and `.../scratchpad/pyc9d` are still on disk. They are outside the clone, whose tree is clean.

### Assessment

Task quality: **Approved.** All five items are built as the brief and Ruling 33 describe, with the smallest diff:
- the one code change is a correctly placed guard that leaks no exception text;
- the refactors keep or strengthen every assertion;
- no trading rule, stop look or config value changed.
