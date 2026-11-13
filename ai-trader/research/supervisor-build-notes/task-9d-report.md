# Task 9d report: test robustness and one guard after Task 9c

Base b9bdd278 (branch supervisor-build, tree clean at start). One commit:
`55756d5b test(ai-trader): sturdier follow-up tests and a guarded failed-step row` (no attribution lines).
Every python command ran through the `safe` wrapper. No `git stash` in any form. `_tasks` was not touched.

## What was implemented

1. **Item 1, the two `+ 1` counts** (tests/test_news_supervised.py, class FollowUps):
   - `test_a_start_beats_after_every_send_git_call_and_priming_feed`: `3 + 1 + 30 + 1` became
     `3 + 1 + 30 + min(1, news_live.read_heartbeat()["step"])`. The comment adds "none if the loop made no step".
   - `test_rows_of_the_run_before_are_left_to_the_late_line`: `1 + 1` became `1 + min(1, news_live.read_heartbeat()["step"])`.
     It had the same assumption (a hard-coded step). Its own `b["step"] > 0` check is unchanged. A 0-step run still
     fails this test, but at the line that names the reason, not at the count.
2. **Item 2** (`test_the_steps_say_the_late_line_again_at_most_once_every_unsent_resend_seconds`, GateFollowUps):
   - The assertion `nt.n["unsent_resend_seconds"] == 120` on the shared config is gone.
   - Instead, `self.cfg["news"]["unsent_resend_seconds"] = 120` is set before the trader is built. `self.cfg` is the
     test's own `copy.deepcopy(CFG)`.
3. **Item 3** (config.json, `news._note`, text only): the `unsent_resend_seconds:` clause now reads "... is sent again by
   a step's closing message at most once in this many seconds, and the late line (the run before's trades nobody was
   told of) is tried again by the steps at most once in this many seconds too (in an outage ...); ...".
   - Checked with a JSON load: with `news._note` removed from both, base and new config are equal. No value changed.
   - The DEFAULTS twin pin test (`test_loss_protocol_pins`) and the lever-note test (`test_news_inputs`) pass in the
     suite.
4. **Item 4** (aitrader/news_live.py, `_run`, the `except Exception` branch of the loop, now lines 1996-1999):
   - The loop's own `journal.append("news_errors.jsonl", ...)` for a failed step sits in a `try`.
   - A failure prints one line with both classes, in error_once's format:
     `[news] error not journaled (cycle: <step error class>): <write error class>`. Then the loop goes on.
   - `fails += 1` and the `alert_after_errors` alert stay after the guard, unchanged. The row itself is unchanged: same
     keys, still one row per failed step, no dedupe.
   - New test: `GateFollowUps.test_a_failed_steps_row_that_cannot_be_written_costs_no_traceback_and_the_loop_takes_its_next_step`.
     Every step fails, and the second sets STOP. The loop's own row (the one with no "where") of the first failed step
     raises `OSError(28)` once. The test asserts:
     - `_run` returns 143;
     - two steps were taken, and exactly one row was refused (class RuntimeError);
     - the second failed step's row is on disk;
     - exactly one "not journaled" line was printed, with the classes only.
5. **Item 5**: the six-scenario test is now six tests, named
   `test_a_guard_whose_line_cannot_go_out_puts_the_class_of_the_error_on_record_and_never_its_text_` plus a suffix:
   - `calendar_line`: start, then 5;
   - `book_line`: GONE, a garbage book, then 6;
   - `chain_line`: GONE, a saved book, a chain broken at the start, then 4;
   - `late_line_and_loop_chain_line`: GONE, a book, an owed heartbeat, the chain whole at the start and broken in the
     step, then 4;
   - `lock_file_and_loop_fails_line`: `run()`, the lock write raises, `alert_after_errors` 1, then 143;
   - `in_a_file_git_ignores`: the `.gitignore` line.

   Two helpers on the class carry the shared parts:
   - `raising()`: the send raises an error whose text holds the secret;
   - `assert_guard_rows(wrote)`: the original final assertions, run after each start.
   `SECRET` and `GUARDS` (a frozenset) are class attributes beside them. The class docstring got one clause for 9d.

## TDD evidence

RED (item 4; the test was written before the guard):
`safe python3 -m unittest discover -s tests -p test_news_supervised.py -k test_a_failed_steps_row_that_cannot_be_written -v`
```
ERROR: test_a_failed_steps_row_that_cannot_be_written_costs_no_traceback_and_the_loop_takes_its_next_step
  File ".../tests/test_news_supervised.py", line 1768, in failing
    raise RuntimeError("a step that fails")
RuntimeError: a step that fails
During handling of the above exception, another exception occurred:
  File ".../aitrader/news_live.py", line 1996, in _run
    journal.append("news_errors.jsonl", {"at": journal.now_utc(), "error": type(e).__name__, "detail": str(e)[:300]})
  File ".../tests/test_news_supervised.py", line 1773, in full_disk
    raise OSError(28, "No space left on device")
OSError: [Errno 28] No space left on device
Ran 1 test in 0.007s
FAILED (errors=1)
```
This failure was expected. It is exactly item 4's reason: the unguarded append turns a failed step into a traceback
out of `_run`, so the loop never takes its next step.

GREEN, the same command after the guard: `Ran 1 test in 0.005s` / `OK`.

Items 1, 2, 3 and 5 are refactors, and their tests stayed green. Mutation runs in throwaway copies, never the clone,
show that each item does what it claims:
- **Item 1.** The FollowUps loop was forced to make no step (`until` "00:00"):
  - the beats test passes with `min(1, step)`;
  - 9c's hard-coded `+ 1` fails it: `AssertionError: 34 != 35`;
  - the late-line test fails at its own `b["step"] > 0` line: `(False, None) != (True, None)`.
- **Item 2.** `unsent_resend_seconds` was tuned to 60 in config.json and DEFAULTS:
  - the 9c item 1 test passes;
  - 9b's sibling test (line 1507) fails, `60 != 120` (see Concerns).
- **Item 5.** Each of the seven `detail=False` guards was reverted in turn, with a fresh bytecode cache per run. Each
  mutation fails exactly the split test that owns that guard, and the other five pass:

  | Guard reverted | Split test that failed |
  | --- | --- |
  | late_line | late_line_and_loop_chain_line |
  | lock_file | lock_file_and_loop_fails_line |
  | calendar_line | calendar_line |
  | book_line | book_line |
  | chain_line | chain_line |
  | loop_chain_line | late_line_and_loop_chain_line |
  | loop_fails_line | lock_file_and_loop_fails_line |

  Dropping the `.gitignore` line fails only `in_a_file_git_ignores`.
  - A first loop run of this check gave a muddled mapping: same-size edits within one second reused a stale `.pyc`.
    A direct re-run, then the loop again with `PYTHONPYCACHEPREFIX` per run, gave the table above.

The task's file, 3 times in a row at the final tree (`safe python3 -m unittest discover -s tests -p test_news_supervised.py`):
`Ran 117 tests in 2.581s OK`, `Ran 117 tests in 2.527s OK`, `Ran 117 tests in 2.721s OK`.
- The 117 tests are 111 + 1 new (item 4) - 1 + 6 (item 5).
- The file's output is pristine: dots, the rule, `Ran`, `OK`.
- The runs were made at about 18:30 New York, after 16:05. The tests run in process with `until` "23:59".

## Whole suite

`safe python3 -m unittest discover -s tests`, final run before the commit, at the committed tree:
```
Ran 716 tests in 102.683s

OK
```
Wall time 103 s. Two earlier full runs during the task were also OK: 716 tests in 99.9 s and in 99.0 s.
- 716 = 710 + 6.
- The suite prints engine log lines (`[news] engine started ...`, `cycle error`, `scorer failed ...`). They come from
  other test files and are older than this task. The task's own file prints none.

## Files changed

- `ai-trader/aitrader/news_live.py`: +4 / -1, item 4 only.
- `ai-trader/config.json`: one `_note` text, item 3.
- `ai-trader/tests/test_news_supervised.py`: items 1, 2, 4 (test) and 5.

## Self-review findings

- ruff (isolated, line length 200), the test file against the base:
  - my first `GUARDS = {...}` brought in a new RUF012 (mutable class default);
  - it became a `frozenset`, and the file went from 8 findings to 7 (the old lambda's unused `noqa: E731` is gone).
- ruff, news_live.py: 25 findings before and after.
- No assertion was weakened. Every assertion of the six-scenario test is still there:
  - the five exit codes, one in each split test;
  - the guard-set check, now per start, with exact equality. The union over the five tests is all seven guards, and
    each test also proves that no other guard wrote a row;
  - the per-row keys and class check, and the secret check, now after every start;
  - the `.gitignore` check.
- Items 1 and 2 keep their assertions. They only stop depending on a timing or a tuned value.
- Stop path, trading rules, buys, sales and holds are untouched. The one code change sits in the failed-step branch,
  after the step has run. The next step still begins with its look at the stops. `fails` and the alert are unchanged.
- The time machine loads no changed file except config.json, and in config.json only the `_note` text changed.

## Departures from the brief, and readings

- **Item 1, the second `+ 1`.** The brief says "if it has the same assumption". It does: a fixed step count. So it got
  `min(1, step)` too. Its separate `b["step"] > 0` check means a run with no step still fails there.
- **Item 5, "six scenarios".** The test drives five starts plus the `.gitignore` check. The sixth test is the
  `.gitignore` check on its own, suffix `in_a_file_git_ignores`, so that no start can hide it.
- **Item 5, the state each split test starts from.** Each split test sets up the state its own start needs, from the
  original lines: GONE and a saved book for the chain test; GONE, a book and an owed heartbeat for the late-line test.
  - The lock-file test starts from an empty state. In the original sequence, that start ran on the leftovers of the
    run before: an owed GONE line, whose `late_line` row was then deduped by `ERRORS_SAID`.
  - On a fresh state the lock-file test owes no line, so its exact guard set is `{lock_file, loop_fails_line}`.
- **Item 4, the printed line.** It names both classes, the failed step's and the write error's, in the format of
  `error_once`'s own fallback line. The brief asks for "one line with the exception class".
- **Class docstring.** One clause for 9d was added, as 9c did for its own items. Comment only.

## Concerns

1. **9b's sibling test also asserts the shared value.**
   `GateFollowUps.test_a_line_no_channel_took_is_sent_again_at_most_once_every_unsent_resend_seconds` (line ~1507)
   asserts `self.nt.n["unsent_resend_seconds"] == 120` against config.json. The mutation run shows that a tuned value
   fails it (`60 != 120`). The brief names only the 9c item 1 test, so it is left as is. It is the same one-line fix.
2. **Throwaway copies left in the scratchpad.** The mutation copies were not deleted, because the harness refused an
   `rm -rf` built on a variable. They are `<SCRATCH>/mut9d-m1` to
   `.../mut9d-m4` and `.../pyc9d`. They are outside the clone; the clone's tree is clean.
