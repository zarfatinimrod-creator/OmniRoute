# Task 7 review - the first look after any start

Diff: ce6abbe3..cbfc4686 (1 commit), from the review package `review-task-7.diff`. Read the brief, constraints.md,
controller-notes.md (every ruling through 16:05 UTC) and spec 5.1, 5.6 and 12. The diff was reviewed in one pass.
Line numbers are for the file at cbfc4686.

### Spec Compliance

Compliant.

- `_run` follows the brief's six steps in order (news_live.py:1703-1777):
  1. config, `start_checks`, the trader;
  2. `adopt_previous`, then `_beat("boot")`;
  3. the chain check, which returns 4 (1732-1742);
  4. `market_open_now()` and then `_look_at_stops(events, guarded=True)`, then `_beat("stops")` (1736, 1748);
  5. E2, E1, `say_late()`;
  6. `code_stamp()`, priming, the loop (1771).
- Nothing before the first look reaches the network except the look's own quotes.
- A look that returns False, or raises anything but `ChainBroken`, leaves a row with `where` "first_look" and the loop
  still starts (1737-1738, 1743-1744).
- `code_stamp` gives `env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}` to both git calls, through the shared lambda
  (news_live.py:331-332).
- `_step` is untouched: the news_live.py hunks are only `code_stamp` and `_run`.
- All 7 tests the brief names exist under their names in `FirstLook` (test_news_supervised.py:860-936), each with the
  brief's assertion unchanged. Three of them add one more assertion.
- The RED the brief expects (`calls[0] == "git"`) is in the report.
- Three edits sit outside the brief's own list, and the controller ruled on each:
  - the test_supervise.py scenario `[51.0, 51.0, 48.0]` (option 1);
  - the Task 5 expectation "boot" -> "stops";
  - `_beat(nt._phase)` after E1, the log print of the first look's lines, and the "stops" beat before the bell.
- The commit message matches the brief and carries no attribution trailer. Nothing under `state/`, `logs/`, `reports/`
  or `research/` changed.
- Spec 5.1 builds the trader before `start_checks`; the brief puts `start_checks` first. The code follows the brief (the
  Task 5 order). The brief wins, so this is not a finding.

Cannot verify from this diff:
- Tasks 8 and 11 rely on this order. Whether it fits them can be judged only in those tasks.
- The process-level harness test (test_supervise.py `test_a_scenario_is_played_as_written`) with the extra scripted
  quote: I did not re-run it. The report has three green runs.
- The report's "any hour" runs (`t7/shifted.py`) and the 637-test suite: I did not re-run them.
- Every commit on the branch has author name "Claude" (the gate clone's git identity), not only this one. Whether that
  counts as AI attribution is a question for the whole-branch review.

### Strengths

- The reorder is a move, not a rewrite. The E2, E1, late-line, stamp and priming blocks are carried over word for word,
  so the diff is easy to audit.
- The chain check sits inside the same `try` as the look, so a broken chain returns 4 before any quote and no stop is
  sold. It also leaves `_chain_checked` unset, so step 1 reads the chains as before.
- Moving `say_late` after the first look is safe. `_mark_told` (news_live.py:1402-1409) moves `told_through` only when
  no row is still owed, so a first-look sale cannot hide an older row that was never sent.
  `test_a_sale_of_the_first_look_and_a_late_line_of_the_same_start_are_each_said_once_the_sale_first` pins this.
- The tests check real behaviour through `_Engine`'s stand-ins, which record the order of calls that leave the process.
  The order is not asserted on the mocks themselves. Examples:
  - `at_git` shows the trade row, the saved book and the sent line on disk at the moment git is asked;
  - the heartbeat test shows the file says "stops", step 0, no code and a stamped BBB when git is asked;
  - the broken-chain test shows only the alert leaves the process.
- `test_the_alert_of_a_broken_chain_at_a_start_is_word_for_word_the_one_of_a_step` ties the repeated alert text in
  `_run` to `_step`'s.
- The report lists 14 planted defects, all caught.

Checks I ran (each for a named risk):
- Risk: a first-look exception carries the topic or a URL into `news_errors.jsonl` through `_note_error`'s
  `str(e)`. Checked `_look_at_stops` (1084-1125): the quotes, the catch-up and `_say` are guarded inside it. Checked
  `notify.send` (notify.py:45-56): it catches `requests.RequestException` and prints only the class name. Nothing
  network-borne reaches the new `except` in `_run`. No finding.
- Risk: `_note_error` or `_beat` raises in the new error path and turns "not a crash" into a crash. Checked
  news_live.py:1127-1132: `_note_error` swallows its own failure. Checked news_live.py:1542-1550: `_beat` is documented
  never to raise. No finding.
- Risk: the stand-ins `_WatchedStarts` installs leak past a test. Checked `_Engine.setUp` and `tearDown`
  (test_news_guards.py:33-59): `live_price`, `market_open_now`, `notify.send` and `bars_since` are saved and restored.
  No finding.
- Risk: the new tests depend on the date they run. `hold()` dates BBB's entry 2026-11-09, and the 5-day exit in
  `check_stops` uses the wall clock (news_live.py:904-906). Checked:
  - `_Engine` sets `max_hold_days` to 0 (test_news_guards.py:52);
  - `adopt_previous` takes `stops_checked_at` with no day check (news_live.py:1512-1515), which test 3 relies on;
  - ran one focused test with only the engine's clock moved 7 days ahead, to 2026-11-18, through the `safe` wrapper
    plus the `env -u` prefix, from a scratch runner outside the clone:
    `TheOrderOfAStart.test_when_git_is_asked_the_file_says_the_first_look_is_over_and_carries_no_code_yet` printed
    `OK`. `git status --short` stayed empty.

  No finding.
- Risk: the catch-up stand-in in test 3 has the wrong signature. Checked `bars_since(sym, since, now)`
  (news_live.py:408) and `_look_at_stops(self, events, guarded=False, now=None)` (1084). Both match the stand-ins.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- news_live.py:1732-1735 and 1739-1742 repeat `_step`'s chain check and its message (1452-1455). They also repeat the
  loop's alert handler (1791-1793).
  - Why it matters: three copies of one fail-closed path.
  - Mitigation: the brief's "nothing inside `_step` changes" forces the copy, the controller ratified it on
    2026-11-11 at 16:05, and a word-for-word test pins the texts together.
  - Fix: a small `_chain_alarm(bad)` helper if `_step` is ever opened again. Not now.
- news_live.py:1732: the start reads every chain, and step 1 reads them again at once because `_chain_checked` is not
  set.
  - Why it matters: one extra full verification of the journals per start, before step 1's look. The first look is not
    delayed.
  - Fix: optional, `nt._chain_checked = time.time()` after a clean check in `_run`. The report says leaving it unset
    was deliberate.
- news_live.py:1739-1742: the start's `ChainBroken` return skips `nt.save()`, the trial drain and `[news] stopped`,
  which the loop's `ChainBroken` path runs.
  - Why it matters: harmless at start (nothing has changed and no trial is out), but the engine's log of a refused
    start ends without its usual last line.
  - Fix: optional, print `[news] stopped` before `return 4`.
- news_live.py:1703-1777: `_run` grows from about 83 to about 110 lines.
  - Fix: the first-look block (1729-1748) could become a `NewsTrader` method. The brief names `_run`, so this is
    acceptable as built.
- test_news_supervised.py:844: `_WatchedStarts` sets `news.stop_catchup` to "off" (production uses "alert").
  - Why it matters: only test 3 covers a start with the catch-up on.
  - Mitigation: the same idiom is used at lines 156 and 646 of the file, and the reason (hour independence) is stated.
- Report, "The whole suite": the suite's output has printed lines between the dots. The report says they come from
  older tests, not from this task's tests, and the new classes capture stdout through `_Starts`. Still noise in the
  gate's output; not this task's to fix.

### Assessment

Task quality: Approved. `_run` now runs the brief's six steps in order. Every named test exists with its assertion. The
three out-of-list edits are all ones the controller ruled on. I found no defect in the stop path, the error path or the
order of sends. The minor items are polish, or were mandated and ratified.
