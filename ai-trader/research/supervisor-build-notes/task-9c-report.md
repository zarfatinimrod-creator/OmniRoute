# Task 9c report: the last follow-ups of step 1, owed before rollout step 2

Gate clone at start: HEAD 52ea9265f8fe2b5399782865231fab7cabf5da26, branch supervisor-build, tree clean (checked).
One commit: `b9bdd278 fix(ai-trader): the last follow-ups of step 1 - a late-line back-off, the loop's alerts guarded,
a cut priming primes again, no exception text in the new rows` (no attribution lines; the body is empty).
`git status --short` prints nothing after it. Test and suite commands all ran through the controller's `safe` wrapper
(two slips are listed at the end).

## What was implemented (news_live.py line numbers at b9bdd278)

1. **The late-line retry backs off (Ruling 28).** New attribute `self._late_tried_at = None` in `NewsTrader.__init__`
   (615). In `step()`'s `finally`, after the closing message (1559-1565), the retry runs only when `_late` is not empty
   AND (`_late_tried_at is None` OR `time.monotonic() - _late_tried_at >= self.n["unsent_resend_seconds"]`). The stamp is
   set just before the try. The start's `nt.say_late()` in `_run` is unchanged (unthrottled, and it neither reads nor sets
   the stamp; see "Readings"). A delivered late line still goes through `_mark_told` and empties `_late`, as before. The
   `say_late` docstring now says "at most once every news.unsent_resend_seconds".
2. **The loop's two alerts are guarded.** Both sit in `_run`'s loop. The ChainBroken alert: `try` / `except Exception as
   e2` -> `error_once("loop_chain_line", e2, detail=False)` (1985-1989). The code stays 4 and the loop breaks as before.
   The `alert_after_errors` alert: the same guard with `where` "loop_fails_line" (2000-2005). The loop goes on to its wait
   and its next step.
3. **Shutdown and step error handling stay whole.** `poll_headlines`: `asked = [ex.submit(...)]` moved inside the `try`
   whose `finally` shuts the executor down (767-768). `step()`: `carried = earlier + self._unsent[mine:]` and
   `self._carried_at.update(...)` moved inside the `try` that guards `_say` and `_mark_told` (1549-1551). No new test.
   Every existing test still passes: the 3x runs of both files and the whole suite below.
4. **A cut priming primes again.** In `_run` (1958-1965), after `nt.poll_headlines(prime=True)`: when `STOP.is_set()`,
   `nt.seen = {}` and one printed line (`[news] a planned stop cut the priming: nothing is kept, the next start primes
   again`). The loop then ends at once with 143, and its exit `nt.save()` writes `news_seen.json` as `{}`. The next start
   reads `{}`, `not nt.seen` holds, and it primes. When priming was not cut: `nt.save()` and the "primed N" line, as
   before. The `_run` docstring gets one sentence on this.
5. **No exception text in the new guards' rows; the errors file stays out of git.** `error_once` and
   `NewsTrader._note_error` take a new `detail: bool = True`. With `detail=False` the row is `{at, error, where}`: the
   class name and no `detail` key (111-120, 1207-1211). Older callers pass nothing, so they write what they wrote
   before. `detail=False` is passed by exactly the seven sites the brief names: `lock_file` (1859), `calendar_line`
   (1891), `book_line` (1899), the start's `chain_line` (1921), `late_line` (1517), and item 2's `loop_chain_line` (1989)
   and `loop_fails_line` (2005). `ai-trader/.gitignore` gets `state/news_errors.jsonl` (line 7, beside the other
   `state/news_*` lines). `git check-ignore -v state/news_errors.jsonl` -> `ai-trader/.gitignore:7`. The file is not
   tracked (`git ls-files` empty).
6. **The blind-quote alert follows the channel rule.** `_stop_sight` (1234-1237):
   `since[1] = bool(notify.send(...)) or not notify.channels(self.cfg)`. The send is made first, as in `_say`. With no
   channel configured the alert counts as taken (said to the log). It is not repeated every window, and "the price is
   back" follows it. With a channel configured and a failed send nothing changes. The docstring says so.
7. **Two weak tests made strong** (see TDD below): the WhoWasTold late-line row count, and the SKILL test of 3ב.

Where the guards and the back-off stand, for the gate: back-off at 1559-1565 (stamp 615). Loop guards at 1985-1989 and
2000-2005. Start guards at 1885-1891 (calendar), 1893-1899 (R5d), 1916-1921 (chain), 1853-1859 (lock file).
Late-line guard at 1503-1517 (`say_late`).

**No buy, sale, stop or hold rule changed, and no stop look is delayed or skipped.**
- Item 1 removes sends between a step's end look and the next step's first look; it adds none.
- Items 2 and 5 only wrap sends that already existed, or change what an error row holds.
- Item 3 moves lines inside a `try`.
- Item 4 acts after the first look, on a planned stop that is already ending the loop. It skips one save; the loop's exit
  save writes the book and the queue as before.
- Item 6 can only make an alert be sent less often.
- `_look_at_stops`, `check_stops`, `catch_up_stops`, `_buy`, `_sell`, the queue and the holds are untouched.

No file the time machine loads was touched: `backtest`, `strategy`, `signals`, `learn`, `data`, `metrics` and `broker`
neither import `news_live` nor `notify` (grep: no match). `config.json` was not changed.

## TDD evidence

New tests in `tests/test_news_supervised.py`, class `GateFollowUps` (docstring extended for 9c):
- `test_the_steps_say_the_late_line_again_at_most_once_every_unsent_resend_seconds` (item 1, line 1706);
- `test_a_broken_chain_in_the_loop_whose_alert_cannot_be_sent_still_ends_with_4` (item 2, 1727);
- `test_a_loop_whose_alert_after_errors_cannot_be_sent_takes_its_next_step` (item 2, 1741);
- `test_a_planned_stop_that_cuts_the_first_priming_leaves_the_next_start_to_prime_again` (item 4, 1760);
- `test_a_guard_whose_line_cannot_go_out_puts_the_class_of_the_error_on_record_and_never_its_text` (item 5, 1790);
- `test_a_blind_quote_alert_counts_as_said_with_no_channel_configured_and_is_tried_again_when_one_failed` (item 6, 1838).

The item 7 tests that were strengthened are `WhoWasTold.test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start`
(845) and `GateFollowUps.test_the_skill_says_how_to_stop_an_engine_and_what_to_do_on_e1` (1673).

**RED** (tests written, no production change):
`safe python3 -m unittest discover -s tests -p test_news_supervised.py -k GateFollowUps -k test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start -v`
```
ERROR test_a_broken_chain_in_the_loop_whose_alert_cannot_be_sent_still_ends_with_4
    self.assertEqual(self.start(), 4)
RuntimeError: ntfy is down
ERROR test_a_loop_whose_alert_after_errors_cannot_be_sent_takes_its_next_step
    self.assertEqual(news_live._run("23:59", None, False), 143)
RuntimeError: ntfy is down
ERROR test_a_guard_whose_line_cannot_go_out_puts_the_class_of_the_error_on_record_and_never_its_text
    self.assertEqual(self.start(), 4)
RuntimeError: https://ntfy.example/secret-topic
FAIL  test_a_blind_quote_alert_counts_as_said_with_no_channel_configured_...   (then named ..._said_to_the_log_once_...)
AssertionError: Tuples differ: (3, False) != (1, True)
FAIL  test_a_planned_stop_that_cuts_the_first_priming_leaves_the_next_start_to_prime_again
AssertionError: 1 != 2
FAIL  test_the_steps_say_the_late_line_again_at_most_once_every_unsent_resend_seconds
AssertionError: Lists differ: [0.0, 30.0, 120.0, 150.0, 240.0] != [0.0, 120.0, 240.0]
FAIL  test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start
AssertionError: Lists differ: [('late_line','OSError')] * 4 != [('late_line','OSError')] * 2
Ran 23 tests in 0.470s
FAILED (failures=4, errors=3)
```
Each failure has the cause its item names:
- item 2: the unguarded loop alerts turn 4 into a traceback, and stop the loop.
- item 6: with no channel configured, the blind alert was sent 3 times and never counted as said.
- item 4: the next start did not prime again (one priming, not two).
- items 1 and 7a: the steps retried the late line at 30 s and 150 s; with three steps that is 4 rows, not 2.

The item 5 test first fell on the item 2 traceback, so its own RED was taken in a second stage. I added only item 2's
guards (still writing the text), then ran
`safe python3 -m unittest discover -s tests -p test_news_supervised.py -k test_a_guard_whose_line_cannot_go_out -k test_a_broken_chain_in_the_loop -k test_a_loop_whose_alert_after_errors`:
```
FAIL: test_a_guard_whose_line_cannot_go_out_puts_the_class_of_the_error_on_record_and_never_its_text
AssertionError: Tuples differ: (['at', 'detail', 'error', 'where'], 'RuntimeError') != (['at', 'error', 'where'], 'RuntimeError')
 : {'at': '2026-11-11T22:53:46+00:00', 'error': 'RuntimeError', 'detail': 'https://ntfy.example/secret-topic', 'where': 'calendar_line'}
Ran 3 tests in 0.023s
FAILED (failures=1)
```
That is the URL text in the calendar guard's row, which is item 5's reason. The two item 2 tests passed at this stage.

The SKILL test (7b) passed at RED, as expected: 3ב already holds the text, and the item only makes the test check it.
Its strength was shown with a scratch mutation run instead. It ran the test against mutated SKILL text by patching
`Path.read_text` (scratch script outside the clone; the file was not edited):
`advice a: killed`, `option b dropped: killed`, `option c dropped: killed`, `no two-minute bound: killed`,
`kill -9 at once: killed`, `E1 message without paper money: killed`.
The old form survives at least "kill -9 at once" (it only checked the substring `kill -9`) and "E1 message without paper
money" (`כסף נייר` appears elsewhere in 3ב).

**GREEN** (same command, `-v`): `Ran 23 tests in 0.492s` / `OK`.

Both files, 3 times in a row, on the final tree:
```
test_news_supervised.py   Ran 111 tests in 2.562s OK | 2.578s OK | 2.590s OK
test_supervise.py         Ran 30 tests in 35.471s OK | 34.538s OK | 34.773s OK
```
Plus `test_news_inputs.py` (edited, below): `Ran 71 tests in 1.067s OK`.
The runs were made at 17:55-18:05 New York, after the close. No new process test.
- Every in-process start of the new tests passes "23:59" (the known ceiling is the minute 23:59-00:00).
- Three tests run `_run`/`run` with `max_minutes=None` and end only by a planned stop that their own step stand-in sets
  on a fixed step: the item 2 errors test, the item 5 test and the reworked 7a test. Their step count and exit code
  therefore do not depend on timing.
- Each such stand-in sets STOP before it does anything else, so a defect cannot leave a loop running.
- `STOP` is cleared in cleanup (GateFollowUps' `setUp`; 7a adds its own `addCleanup`).

## Whole suite

`safe python3 -m unittest discover -s tests` from `ai-trader/`, on the committed tree, wall 99 s:
```
Ran 710 tests in 97.637s

OK
```
That is 704 before, plus the 6 new tests. A first whole-suite run, before the edit of test_news_inputs.py, gave
`FAILED (failures=2)` (the two BlindStop tests below). The printed lines in the suite output come from other files, as
before this task. `test_news_supervised.py` and `test_news_inputs.py` alone print only the unittest summary. No output
line contains "secret-topic".

## Files changed

- `ai-trader/aitrader/news_live.py`: items 1-6.
- `ai-trader/.gitignore`: `state/news_errors.jsonl`.
- `ai-trader/tests/test_news_supervised.py`: six new GateFollowUps tests, the two item 7 tests, the class docstring, and
  two FollowUps expectations (below).
- `ai-trader/tests/test_news_inputs.py`: two BlindStop tests, one setup line each (below; outside the brief's list).

## Self-review (git diff 52ea9265..HEAD)

I checked the diff line by line against items 1-7 and the brief's Files and commit lines. Each item has its code, and
its test or the stated "no new test".
- Existing patterns are reused: `error_once` and `_note_error` (one keyword added), the `notify.channels` rule of `_say`
  and `say_late`, and the `_carried_at`-style monotonic stamp. There is no new helper, and no config key.
- `ruff check --select F,E9` on the three Python files: clean. A full `ruff check` gives the base's findings plus one
  more `RUF100` on a new `# noqa: E731` lambda. The repo and Task 9b write that `noqa` the same way; the local ruff has
  E731 off.
- Fixed during the review:
  - the `say_late` docstring line I had left over-long (rewrapped);
  - a comment in the item 5 test that was split across code lines;
  - the item 6 test's name, which did not read ("... and one a channel failed again");
  - the item 1 test's config check, which now pins the value on the trader it drives.
- Edge cases looked at:
  - Item 1. A trader built without `__init__` (tests/test_audit_fixes.py) never reaches the stamp: `getattr(self,
    "_late", None)` short-circuits. A clock that starts at 0.0 is handled with `is None`, not truthiness.
  - Item 3. A raise while building `carried` is now caught as `step_alert` and the step's own exception wins.
  - Item 4. A stop set after a complete priming also drops the marks. That is harmless: the next start primes again, and
    priming only marks, never scores.
  - Item 6. A partial cfg (no `alerts` block) still works: `channels` defaults the names.

## Departures from the brief

1. **`tests/test_news_inputs.py`, class `BlindStop`, two tests** (a file the brief does not list; added to the commit
   under the controller's ruling on existing tests broken by the brief's change). Both modelled "a channel that took
   nothing" with a send stand-in answering `[]`, while `notify.channels` was the real one. A test run configures no
   channel, so item 6 made that "said to the log". One test's comment even said "(ntfy down, nothing configured)".
   Each test gets one line,
   `self.enterContext(mock.patch.object(news_live.notify, "channels", lambda cfg: ["ntfy"]))`, plus a comment saying a
   channel is configured and that with none configured the log takes it. Their assertions are unchanged:
   - `test_an_alert_that_did_not_go_out_is_tried_again_after_another_window` (337);
   - `test_no_price_is_back_line_for_an_alert_that_never_went_out` (351).
   These tests are about the owner's alert, not about a stop rule. The sale-under-a-blind-quote test of the same class,
   `test_a_failing_alert_never_stops_a_sale_and_is_journaled`, is untouched and passes. This mirrors 9b's local `_Engine`
   in test_news_supervised.py.
2. **Two FollowUps expectations in tests/test_news_supervised.py** (same file, tests the brief does not name; item 1 makes
   the late line tried after the first step only, while these loops make many steps within milliseconds):
   - `test_a_start_beats_after_every_send_git_call_and_priming_feed` (1271):
     `3 + 1 + 30 + read_heartbeat()["step"]` -> `3 + 1 + 30 + 1`.
   - `test_rows_of_the_run_before_are_left_to_the_late_line` (1332): `1 + read_heartbeat()["step"]` -> `1 + 1`. Its own
     `b["step"] > 0` check still holds.
   Each comment says why (task 9c). Neither test is about a trade, a stop, a buy, a sale or a hold.
3. **7a is reworked, not only re-asserted.** The test ran `self.start()` (a 30 ms loop), whose step count depends on
   timing, so "with the back-off in force" could not be pinned. It now runs `_run("23:59", None, False)` with the same
   stand-ins as `_Starts.start` plus a step wrapper. The wrapper runs three real steps, and the third sets STOP. The test
   asserts:
   - `run == 143` (the start went on to its loop);
   - exactly `[("late_line", "OSError")] * 2` (the start, then the first step; steps 2 and 3 fall within
     `unsent_resend_seconds`);
   - three steps, and `told_through` still None.
4. **The item 5 test also checks the `.gitignore` line**: one `assertIn("state/news_errors.jsonl", ...split())`, in the
   way `test_time_machine_honesty.py` checks `state/trial_runs/`. It ties the two halves of item 5 together.
5. **Readings of the brief:**
   - Item 1. "a monotonic stamp of the last attempt" is read as the last attempt of step()'s retry. The start's
     `say_late` "stays as it is": it is not gated, and it does not set the stamp. So in an outage that spans a restart,
     the start tries once, the first step after it tries again (about `poll_seconds` later), and then at most every
     120 s. This keeps 9b's pinned behaviour ("said again by the next step", GateFollowUps test of 9b, unchanged). The
     other reading, where the start's try also starts the 120 s, is a one-line move: set the stamp in `say_late`. It
     would save that one extra send at a restart and change 9b's test. See concern 1.
   - Item 5. "the exception's class name only" is built as a row with no `detail` key: `{at, error, where}`, where
     `error` is the class.
   - Item 2. The `where` names are "loop_chain_line" and "loop_fails_line".
   - Item 4. The brief suggests "do not save `seen` after a cut first priming". It is built as "keep no marks of it":
     `nt.seen = {}`, because the loop's exit save would otherwise write them. The after-priming save is skipped on a
     cut; the exit save follows at once.

## Concerns

1. **Item 1's reading** (above): the first step after a start tries the late line once more before the back-off holds.
   The cost is one extra send of up to 15 s per channel, once per start, in an outage. The controller can choose the
   other reading; it is a one-line change plus 9b's test.
2. **Older call sites still write an error's text.** As the brief ordered, they are unchanged: `lock_line` (E2),
   `mismatch_line` (E1), `step_alert`, `look_alert`, `stop_sight`, `first_look`, and the loop's own row for a failed
   step. A send error that carried a URL would still land there. Since this task the file is ignored by git, so a broad
   `git add` no longer publishes it; it stays on disk.
3. **The loop's own error row is unguarded.** `_run`'s `except Exception` branch writes
   `journal.append("news_errors.jsonl", ...)` with no `try`. A journal that cannot be written there (for example a full
   disk) would still end `_run` with a traceback. It is not in the brief; the same one-line guard would cover it.
4. **The new ignore line covers the stock book only.** It is `state/news_errors.jsonl`, as the brief gives it. The news
   engine refuses `--book crypto` (`__main__.py`), so no `state/crypto/news_errors.jsonl` is written today.
5. **Two slips of procedure, both without effect:**
   - One plain `python3 -` (not through `safe`) ran a text substitution that edited the seven `detail=False` call sites
     in news_live.py. It imported nothing of the project and touched no network.
   - A read-only `git stash list >/dev/null` slipped into a shell line that ran ruff. No stash was created, popped or
     changed.
