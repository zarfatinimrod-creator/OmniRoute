# Task 14d report - one pause gives one line, no R6 from pre-pause stamps, a stop that is not a number never drops a line

Start: `d8955a29dcd509c8a717be7d33a35cb86b2df0be`, branch `supervisor-build`, tree clean. One commit:

- `13ec056d` fix(ai-trader): a pause before the first up and pre-pause stop stamps raise one line, not three, and a stop
  that is not a number never drops an owner line

The commit has no attribution lines. `git status --short` is empty after it. Five files, +149/-11.

## What was implemented

1. **A pause before the first `up` (Ruling 53 (1)). Built with one narrowing, departure 1.** `paused()` still writes
   its `pause` row and sets `seen["resumed"]` exactly as before. It then returns without an R4 when
   `seen["gap"] is not None and gap_line(seen["gap"][0], now, seen["gap"][1], cal, sup)`. In words: this parent's first
   `up` is still to come, and that `up` will send a line of its own. That line runs from the row before this parent's
   start, so it spans the pause. The first `up`'s line is not changed.
2. **No R6 from pre-pause stamps (Ruling 53 (2)). Built with one guard, departure 2.** In `look`'s stale check:
   `cap = wall - seen["resumed"]` when `seen["resumed"]` is set and no stale episode is open, else `float("inf")`. The
   test is `min(born if a is None else a, cap) > stops_stale_seconds`. An unknown stamp keeps Ruling 48's `born`, under
   the same cap. R6's `{s}` line is untouched, so it is still the true age. `_stamp_ages`, `up()`'s `blind_s` and the
   hang check are untouched. A child stopped alone is judged as today, because only `paused()` sets `seen["resumed"]`.
3. **A stop that is not a number (Ruling 53 (3)).** `ownerlines.held_text` renders a stop that is not an int or a float
   (None, a string, a bool) as `"MU (סטופ לא ידוע)"`. The word comes from `WORDS["held"]["unknown"]` through a small inner
   `stop_text`. A numeric stop prints as before (`120.50`). The annotation is now `dict | None`, and the docstring says
   what happens. Callers I checked, by grepping every place a held stop is formatted:
   - `supervise.say()`: R1, R2, R2.off, R3*, R4/R4b (also the pause R4), R5a/b/d, R6. All of these pass `{held}`
     through `held_text`, so all of them are fixed by the shared function.
   - `supervise.status()` R5e: also through `held_text`. Its `except (KeyError, ValueError, TypeError)` comment said "or
     a book stop that is no number". That case can no longer happen, so the comment now reads "a halt code no engine
     gives (or no key at all), a line too long". No code change there.
   - `uptime.close_lines` R4c: through `held_text`.
   - Left alone: `sold_text`, which formats the engine's own trade rows, not the held map. Also left alone:
     `news_live.py:1114`, the engine's catch-up alert, which formats the engine's own `stop_price` or its fallback. No
     other caller formats a held stop.
4. **R4c's unknown word is pinned (Ruling 53 (4)).** One test in `test_uptime.py`. It passes at once, as the brief
   expected: 14b already gives "לא ידוע".
5. **The ceiling is named (Ruling 53 (5)).** A `ponytail:` comment sits right above
   `if last is not None and wall - last[0] > sup["hang_seconds"]:`. It says any wait inside the loop longer than
   `hang_seconds` reads as a pause, that today only `stop()` waits (at most `hang_term_grace_seconds`), and that the
   upgrade is to measure the pause from the process's own CPU-stopped time. It is a comment only.
6. **Test hygiene (Ruling 53 (6)).** `STAMPLESS_CHILD` and the new `PAUSED_STAMP_CHILD` are now in `kill_ours`'s set,
   beside `GROUP_CHILD`.

### The tests (8 new)

- `test_ownerlines.py`:
  - `test_a_stop_of_none_is_unknown_and_a_numeric_stop_beside_it_prints_as_before` checks
    `held_text({"MU": None, "NVDA": 120.5}, 3) == "MU (סטופ לא ידוע), NVDA (סטופ 120.50)"`.
  - `test_a_string_or_a_bool_stop_is_unknown_too` covers `"708.97"` and `True`.
- `test_uptime.py`, `test_r4c_says_unknown_when_the_days_last_up_has_no_held_map`: an earlier `up` holds MU, and the
  day's last `up` has `held=None`. The engine is out from 20:30 UTC to the close, and no R4 or R4b told it, so R4c is
  still sent under 14c's rule. The test checks that `open_at_close` is None, that the line is R4c, that it contains
  "פתוח: לא ידוע. שעון ישראל.", and that "אין פוזיציות" is absent.
- `test_supervise.py`, Status class, `test_status_on_a_book_position_with_no_stop_price_returns_0_and_says_its_stop_is_unknown`:
  the state holds a halt 6 from an earlier day, and the book has MU with no `stop_price`. The test calls
  `main(["--status", "--watchdog", ...])` and expects rc 0 plus the R5e text "... פתוח: MU (סטופ לא ידוע). כסף נייר".
- `test_supervise.py`, Watching class:
  - Helper `pause_before_the_first_up(ev, **fields)`:
    - It writes a row `ev` of an earlier parent 1 s before this parent starts.
    - It starts the parent with the dummy child at `first_after_s` 3, `hang_seconds` 2, `start_grace_seconds` 30 and
      `outage_report_seconds` 2.
    - As soon as the `start` row names the child, it pauses for 4 s: SIGSTOP to the parent and to the child's group,
      then SIGCONT, the same as 14b's pause tests.
    - It waits for the `up` and stops the parent (143).
    - It asserts that the log order is `pause` and then `up`, which proves the window held.
  - `test_a_pause_before_the_first_up_gives_one_line_the_first_ups_which_spans_it` (item 1; the earlier row is a
    `mark`):
    - exactly one `pause` row;
    - exactly one R4/R4b row: `[("R4", up.t)]`, the first `up`'s;
    - its text runs from the earlier row's time to the `up`'s;
    - its `s` is greater than the pause's `s`.
  - `test_a_pause_before_a_first_up_that_tells_no_outage_has_its_own_r4` (departure 1): the earlier row is
    `sup_stop` why `end_of_day`. Exactly one R4 row, `[("R4", pause.t)]`, and its text runs from the pause's start to
    its end.
  - `test_stop_stamps_from_before_a_pause_raise_no_r6_until_stops_stale_seconds_after_it` (item 2):
    - The child is `PAUSED_STAMP_CHILD`. Its held name's stamp is fresh at every beat until the child gets a SIGCONT,
      and after that the stamp never moves.
    - Config: `hang_seconds` 2, `stops_stale_seconds` 2, a 4 s pause.
    - Exactly one `stale_stops` row, a `start`, at the R6 row's `t`. R6.t minus pause.t is at least 2 s. R6's `{s}` is
      at least 4 + 2.
    - The alert kinds are exactly `["R4", "R6"]`: no R6b.
  - `test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it` (departure 2):
    - The dummy child has BBB held, with `stop_age_s` 300 from the start, so R6 comes before the pause.
    - Then a 4 s pause and 3 s more.
    - `stale_stops` is `["start"]` only and R6/R6b is `["R6"]` only.

How the window before the first `up` was held open (the brief asked): the window is not made with a real engine. The
dummy child waits `first_after_s` 3 s before its first beat, which is also its first look. `start_grace_seconds` 30
keeps that wait from being a hang. The pause starts the moment the `start` row names the child. That is usually before
the child's interpreter reaches its sleep, so the first beat comes about 3 s after the resume. The helper's assertion on
the `pause` and `up` order would fail loudly if the window ever closed first.

Signals: the tests send SIGSTOP/SIGCONT only to the parent the test spawned (`p.send_signal`) and to its child's
group. The child's pid comes from the beat or the `start` row. Before signalling, the `pause` helper checks the child's
`/proc/<pid>/cmdline` for the expected argv (the dummy's path, or `PAUSED_STAMP_CHILD`) and checks that the child leads
its own group. Nothing is killed by name. The item-2 test adds `kill_ours` of its child as a cleanup.

Ruling 16 (the evening): the new process tests start no engine. Their children, the dummy and `PAUSED_STAMP_CHILD`,
take `--until` and ignore it. The parent gets `--until 24:00` from `parent_argv`, and its clock is moved to 10:00 New
York on 2026-11-12, so the real hour does not enter any of them.

## TDD evidence

Every command ran from `ai-trader/` through `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`.

### RED (tests written; production code at d8955a29)

- `safe python3 -m unittest discover -s tests -p test_ownerlines.py -k test_a_stop_of_none -k test_a_string_or_a_bool -v`
  gives `FAILED (errors=2)`:
  - `TypeError: unsupported format string passed to NoneType.__format__`, at `held_text`'s `f"{stop:.2f}"`;
  - `ValueError: Unknown format code 'f' for object of type 'str'`.

  This is exactly the item-3 crash.
- `safe python3 -m unittest discover -s tests -p test_uptime.py -k test_r4c_says_unknown -v` gives `OK`. It passes at
  once, as the brief expected for item 4: 14b already gives "לא ידוע" through the shared `held_text`. It is a pin.
- The final test forms replayed against d8955a29's `supervise.py` and `ownerlines.py`, in a throwaway copy holding the
  new tests: `safe python3 -m unittest discover -s tests -p test_supervise.py -k test_a_pause_before -k
  test_stop_stamps_from_before -k test_a_stale_stops_episode -k test_status_on_a_book_position` gives
  `Ran 5 tests in 28.037s FAILED (failures=3)`:
  - Item 1:
    `Lists differ: [('R4', '2026-11-12T15:00:04+00:00'), ('R4', '2026-11-12T15:00:07+00:00')] != [('R4', '2026-11-12T15:00:07+00:00')]`.
    The pause's R4 and the first `up`'s R4 cover the same minutes, which is the double the brief names.
  - Item 2: `datetime.timedelta(0) not greater than or equal to datetime.timedelta(seconds=2)`. The R6 came on the
    first fresh beat after the resume, which is the false "Yahoo slow".
  - Item 3 (--status): `Tuples differ: (0, []) != (0, ['... פתוח: MU (סטופ לא ידוע). כסף נייר'])`. --status returned 0
    and the R5e line was gone (see "departed" 3).
  - Passed, as expected (guards):
    - `test_a_pause_before_a_first_up_that_tells_no_outage_has_its_own_r4`: today's code also gives the pause its R4.
    - `test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it`: today's code has no cap.

  Both guards fail on the mutants below.
- (The first RED run of item 1, with `first_after_s` 5, failed the same way, with
  `ValueError: too many values to unpack (expected 1)`. I then reworded the assertions to show the rows, and shortened
  the window to 3 s. Saved outputs: scratchpad `t14d/red-*.txt`.)

### Mutation checks for the two departures (throwaway copies, deleted afterwards)

- Item 1 taken literally ("no R4 while `seen["gap"]` is not None"): `test_a_pause_before_a_first_up_that_tells_no_outage_has_its_own_r4`
  fails with `Lists differ: [] != [('R4', '2026-11-12T15:00:04+00:00')]`. The pause went untold.
- The cap taken literally (also over an open episode): `test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it`
  fails with `(['start', 'end', 'start'], ['R6', 'R6b', 'R6']) != (['start'], ['R6'])`. That is a false R6b ("the
  stops are checked again") and a second R6.

### GREEN

- The new tests plus their neighbours:
  - `safe python3 -m unittest discover -s tests -p test_supervise.py -k test_a_pause_before -k test_stop_stamps_from_before
    -k test_a_stale_stops_episode -k test_status_on_a_book_position -k test_a_pause_of_the_whole -k test_a_pause_shorter -k
    test_a_child_stopped_alone -k test_an_unknown_stop_stamp -k test_r5e_says -v --durations 0` gives
    `Ran 10 tests in 46.503s OK`.
  - `test_ownerlines.py`: `Ran 9 tests OK`. The R4c test: OK.
- New process test durations (`--durations 0`):

  | Test | Duration |
  |---|---|
  | pause before the first `up` (item 1) | 7.80 s |
  | pause before a first `up` that tells no outage | 7.79 s |
  | episode open across a pause | 7.76 s |
  | pre-pause stamps (item 2) | 6.70 s |
  | `--status` with no `stop_price` | 0.003 s |

  The unit tests in `test_ownerlines` and `test_uptime` take milliseconds.
- The three files, three times in a row on the final code (scratchpad `t14d/round{1,2,3}-*.txt`). Each output holds
  only dots and the summary, with no stray line:

  | Round | test_supervise.py | test_ownerlines.py | test_uptime.py |
  |---|---|---|---|
  | 1 | `Ran 143 tests in 270.082s OK` (271 s wall) | `Ran 9 tests OK` | `Ran 15 tests OK` |
  | 2 | `Ran 143 ... OK` (271 s) | OK | OK |
  | 3 | `Ran 143 ... OK` (271 s) | OK | OK |

## Whole suite

`safe python3 -m unittest discover -s tests`, before the commit, on the final code. Wall time 327 s. Last three lines:

```
Ran 849 tests in 326.054s

OK
```

That is 841 plus the 8 new tests. The suite output still carries the pre-existing `[news] ...` lines that other test
files' engines print. The three files of this task print nothing. After the runs no dummy, `PAUSED_STAMP_CHILD`,
`STAMPLESS_CHILD`, parent or engine_child process of mine was left. I checked with a read-only `ps`.

## Files changed

- `ai-trader/aitrader/supervise.py` (+16/-4: `paused()`'s skip and docstring, the `ponytail:` comment, the stale
  check's cap, and the R5e except comment)
- `ai-trader/aitrader/ownerlines.py` (+9/-3: `held_text`)
- `ai-trader/tests/test_supervise.py` (+99/-5: `PAUSED_STAMP_CHILD`, `kill_ours`'s set, the `pause` helper's `child`
  and `argv`, 5 tests and 2 helpers)
- `ai-trader/tests/test_ownerlines.py` (+8: 2 tests)
- `ai-trader/tests/test_uptime.py` (+16: 1 test)

`config.json` is unchanged.

## Self-review findings and what I did

- Several new lines went past the files' 120-column width, measured in characters: reflowed. No new line is over 120.
- Item 1's RED output first showed only "too many values to unpack". I reworded the assertions to compare
  `[(kind, t)]` lists, so a failure shows which lines came.
- The window held open by `first_after_s` 5 cost about 5 s more than needed, because the pause usually lands during
  the child's interpreter start. I cut it to 3 s and checked the window with the `pause`/`up` order assertion.
- The `status()` except comment named a case my change removes: updated.
- `paused()`'s docstring now names the cases where the first `up` tells no outage.
- I did not edit any code file while the 3x runs and the suite were running, so they all ran one version.

## Where I departed from the brief

1. **Item 1 is narrowed: no pause R4 only while the first `up`'s line will actually come.** The brief says "sends no
   R4 while `seen["gap"]` is not None: the first `up`'s line covers the pause". The code shows the premise does not
   always hold. `gap_line` gives the first `up` no line when the row before this parent is a `sup_stop` for a halt, a
   held lock, the end of a day or a closed day, or when there is no row with a time (a fresh or unreadable log).
   - Taken literally, a pause in that window would go untold: no R4 from the pause and none from the `up`. The mutant
     check above shows it.
   - So the skip applies only when `gap_line(prev, now, cold, ...)` gives a line now. That proves the first `up`'s line
     will come and will span the pause. The interval `[prev.t, up]` contains `[pause start, now]`, and `open_seconds`
     only grows.
   - Otherwise the pause keeps its own R4, as before 14d. Either way it is one line for one outage (spec 8, line 723),
     and R11 counts it once.
   - The brief's test, a `mark` before the parent, is unaffected. One more test pins the other branch.
2. **Item 2's cap does not apply to an episode already open.** The brief's formula, applied literally, would also cap
   the ages while an R6 episode that began before the pause is still open. The capped ages fall under
   `stops_stale_seconds` at once, so the episode would "end": an `end` row and an R6b telling the owner that the stops
   are checked again, while the stamps are still old. A second R6 would follow `stops_stale_seconds` later. The mutant
   check above shows it.
   - So the cap applies only when no episode is open (`not seen["stale"]`). An open episode is judged on the true
     ages, as before, and ends with its R6b when the stamps really refresh.
   - The start of a new episode, which is the brief's case, is capped exactly as the brief writes it. One more test
     pins this.
3. **Item 3's starting point.** The brief and the 14b review say `--status` returned 2 on such a book. At d8955a29 it
   returned 0: `status()` caught the TypeError around R5e, and the R5e line was silently missing from `unsent`. Owner
   line lost either way. The new test checks both points the brief names: rc 0, and the line with "סטופ לא ידוע".
4. Two tests more than the brief lists, one for each departure above. They add about 15.5 s to the suite.
5. The 14b `pause` helper takes two optional arguments, `child` (a pid, for a child that has no beat yet) and `argv`
   (the command-line word it checks). Its default behaviour is unchanged.

## Concerns

- Departures 1 and 2 are my reading of Ruling 53's purpose where its literal text and the code disagree. Each is one
  condition and has its own test. If the controller wants the literal forms, each is a one-line revert plus dropping
  its test. The literal forms give an untold pause and a false R6b/R6 pair, respectively.
- Both item 1 and its literal form still share one gap, not built here. If this parent never reaches a first `up`, for
  example a crash loop that trips, a halt, or a planned stop before it, then a pause that skipped its R4 because the
  `up`'s line was pending gets no line. R11 counts those minutes at the close. Rare: it needs a pause inside the
  child's first look and then no `up` at all.
- Observed, not touched: an orphaned `GROUP_CHILD` process (pid 2841, parent 1, started 01:27 UTC, its argv names
  `/tmp/tmp1przykbx/grandchild.pid`) has been alive since long before this task. It is not mine, so I left it alone.
