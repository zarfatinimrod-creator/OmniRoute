# Task 14e report: a stop that is no finite number reads unknown, two supervisor tests check what they claim, two comments say what is true

Status: DONE_WITH_CONCERNS. The concerns are small; see the last section.

Base 13ec056d, branch supervisor-build, tree clean at start. One commit:
`d639d8ec fix(ai-trader): a stop that is no finite number reads unknown, two supervisor tests check what they claim, two comments say what is true`
(full: d639d8ecc6cd4e484e195d4aaace1236efe44ba0). It has no attribution lines. `git status --short` printed nothing after the commit.

Evidence files are in `<SCRATCH>/t14e/`.

## What I built

1. **NaN and infinite stops read as unknown** (`aitrader/ownerlines.py`, `held_text.stop_text`).
   - The number test is now `isinstance(stop, (int, float)) and not isinstance(stop, bool) and math.isfinite(stop)`.
   - `import math` is added (standard library). The docstring names Ruling 55.
   - New test in `tests/test_ownerlines.py`:
     `test_a_nan_or_infinite_stop_is_unknown_and_a_finite_one_beside_it_prints_as_before`.
     It checks the brief's call exactly: `held_text({"MU": nan, "NVDA": inf, "AMD": 12.0}, 3)` must equal
     `"MU (סטופ לא ידוע), NVDA (סטופ לא ידוע), AMD (סטופ 12.00)"`.
   - This is a real input: `json.loads("1e400")` gives `inf` and `json.loads("NaN")` gives `nan`.

2. **The open-episode guard asserts its pause** (`tests/test_supervise.py`,
   `test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it`).
   - Added `self.assertEqual(len(self.urows("pause")), 1)` right after `stop_parent`. By then every row has been written.

3. **R6's `{s}` is checked against the frozen stamp** (`tests/test_supervise.py`).
   - `PAUSED_STAMP_CHILD` now also writes `"stops_checked_at": stamp`. This is the same variable as the per-name stamp, so it freezes at the same pre-pause value. The comment above the child says so.
   - `test_stop_stamps_from_before_a_pause_raise_no_r6_until_stops_stale_seconds_after_it` changes in three ways:
     - It sleeps 3 s after the first `up`, before the pause. Without this sleep, the child's age and its stamp's age differ by only a few tenths of a second, and a child-age mutant could not be caught.
     - Once R6 is seen, it reads the time (`seen`) and the frozen `stops_checked_at` from the heartbeat file.
     - It asserts `s >= 4 + 2` (pause plus `stops_stale_seconds`), as before. It also asserts the new `abs(s - (seen - frozen.timestamp())) <= 1`: `{s}` is the frozen stamp's age, never the child's.
   - The old comment "`{s}`: true, pause + 2" is replaced by two comments that say what each assertion checks.

4. **The pause check's `ponytail:` comment** (`aitrader/supervise.py`, in `main`'s `look`, above
   `if last is not None and wall - last[0] > sup["hang_seconds"]`). It is a comment only. It now says:
   - only a hang `stop()` waits and then ticks again (a planned stop ends the loop);
   - that wait is at most `hang_term_grace_seconds` for the SIGTERM;
   - then comes the `child.wait()` after the SIGKILL, which has no bound (normally instant).

5. **The drill's `ponytail:` comment** (`scripts/drill_supervisor.py`, `Drill.popen`). It is a comment only.
   - The `hold` flag exists (module-level, read by `interrupted`), but only `run`'s cleanup raises it. `popen` never does.
   - So the window is still open. The comment now says exactly where it is: between the fork inside `Popen` and the `self.procs.append(p)` below. A stop there raises Interrupted and leaves that one child unkilled.
   - It also says what would close it: `hold = []` before the `Popen`, then after the append, raise any stop noted meanwhile, as `run`'s cleanup does.

## TDD evidence

All commands ran from `ai-trader/` through `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`.

**Before any edit: the base test cannot catch the mutant** (`base-test-vs-mutant.txt`).
- Mutant: in `supervise.py`, R6's `s = round(stop_s if stop_s is not None else time.time() - kid["started"])` became `s = round(time.time() - kid["started"])`, i.e. the child's age always.
- Ran the base test against it:
  `safe python3 -m unittest discover -s tests -p test_supervise.py -k test_stop_stamps_from_before_a_pause_raise_no_r6 -v`
  - Result: `... ok`, `Ran 1 test in 6.821s`, `OK`. This confirms the review's point that the old assertion cannot tell the two ages apart.

**Item 3, RED against the mutant** (`red-item3-mutant.txt`; re-run on the final, tidied test in `red-item3-mutant-final.txt`). Same mutant, same command:
```
    self.assertLessEqual(abs(s - (seen - frozen.timestamp())), 1)   # {s}: the frozen stamp's age, never the child's
AssertionError: 2.877951145172119 not less than or equal to 1
Ran 1 test in 9.791s
FAILED (failures=1)
```
- Expected: the child is 3 s older than its stamp, so a child-age `{s}` is about 3 s off. The old lower bound `s >= 6` still passed on that run; only the new assertion fails.
- The mutant was removed with an exact Edit. `git diff --quiet -- ai-trader/aitrader/supervise.py` then confirmed the file was clean, before the comment of item 4 was written. No `MUTANT` text remains (`grep -c` gives 0).
- On the real code the same test passes (`green-item3-real.txt`: `Ran 1 test in 9.781s`, `OK`).

**Item 2, the guard check** (`red-item2-no-pause.txt`).
- I temporarily replaced `self.pause(p, 4)` in the guard test with `time.sleep(4)`: no SIGSTOP, so no pause. Then:
  `safe python3 -m unittest discover -s tests -p test_supervise.py -k test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it -v`
```
    self.assertEqual(len(self.urows("pause")), 1)              # Ruling 55: the pause was seen, else this guards nothing
AssertionError: 0 != 1
FAILED (failures=1)
```
- I then restored `self.pause(p, 4)`; the final diff shows it unchanged. The only edit afterwards was to that line's comment text.

**Item 1, RED** (`red-item1.txt`):
`safe python3 -m unittest discover -s tests -p test_ownerlines.py -k test_a_nan_or_infinite_stop -v`
```
AssertionError: 'MU (סטופ nan), NVDA (סטופ inf), AMD (סטופ 12.00)' != 'MU (סטופ לא ידוע), NVDA (סטופ לא ידוע), AMD (סטופ 12.00)'
FAILED (failures=1)
```
- This is the defect the brief names. After the change (`green-item1.txt`): `Ran 1 test in 0.000s`, `OK`.

**GREEN, each run its own command:**
- `safe python3 -m unittest discover -s tests -p test_ownerlines.py`, three times: `Ran 10 tests`, `OK` each time.
- `safe python3 -m unittest discover -s tests -p test_supervise.py`, three times, each its own Bash command with a 600000 ms timeout:
  - run 1: `Ran 143 tests in 271.714s`, `OK` (wall 273 s)
  - run 2: `Ran 143 tests in 270.709s`, `OK` (wall 272 s)
  - run 3: `Ran 143 tests in 271.409s`, `OK` (wall 272 s)
- The output of all three is pristine: only dots, the summary and `OK`. After the runs, `ps` showed no PAUSED_STAMP_CHILD, dummy, parent wrapper, `signal.pause` or `sleep 60` process left behind.

## Whole suite (once, before the commit)

`safe python3 -m unittest discover -s tests` (`suite.txt`), wall 342 s. The last three lines:
```
Ran 850 tests in 341.273s

OK
```
- That is 849 at the base plus the one new test from item 1. Items 2 and 3 change existing tests and add none.
- The `[news] ...` lines in the output come from older engine tests in other files. They were already there (both earlier reviews note them). The files of this task print nothing.

## Files changed

- `ai-trader/aitrader/ownerlines.py` (+4/-2): `import math`, the `math.isfinite` test, one docstring sentence.
- `ai-trader/aitrader/supervise.py` (+3/-2): comment only.
- `ai-trader/scripts/drill_supervisor.py` (+4/-3): comment only.
- `ai-trader/tests/test_ownerlines.py` (+5): one test.
- `ai-trader/tests/test_supervise.py` (+11/-5): `PAUSED_STAMP_CHILD` with `stops_checked_at` and its comment; the item 3 test; the item 2 assertion.

Nothing else changed: no buy, sale or stop rule, no stop look delayed or skipped, no change to `config.json`, and no file the time machine loads.

## Self-review

- I checked the diff against the brief, line by line: all five items are built, each in the place the brief names.
- Item 3's new bound is robust, for three reasons:
  - The parent's `{s}` is `round(round(stop_age_s, 1))`, and `stop_age_s` is `(at - frozen) + (wall - mtime)`, which is at most `wall - frozen`. `seen` is taken after the row is read, so `s - (seen - frozen)` can never go above about 0.55.
  - Below, it fails only if the R6 row took more than about 0.45 s to be read. `wait_for` polls every 0.01 s.
  - The mutant is about 3 s off.
  It passed in all three file runs and in the suite.
- Item 1, edge cases:
  - A bool is still refused before `isfinite` is reached, and so is a string, because `isinstance` short-circuits.
  - A normal int still prints as before.
  - An int too large for a float raises OverflowError, both before (in the `:.2f` format) and now (in `math.isfinite`). That behaviour is unchanged; see Concerns.
- Tidying before the commit:
  - I shortened three test lines whose padded comments ran past 120 characters.
  - I split the heartbeat read onto its own line.
  - I re-ran the item-3 mutant check on the final text (`red-item3-mutant-final.txt`) so that the evidence matches the committed test.
- Ruling 16 does not apply here: these tests start no engine. Their children are the dummy and `PAUSED_STAMP_CHILD`, and their parents run on the test's shifted clock.
- SIGSTOP and SIGCONT go only through the existing `pause` helper. It signals only the parent the test started and the child's own process group, after checking that child's `/proc` cmdline and process group.

## Departures from the brief

1. **Item 3's premise is not true of the base code.** The brief says that without `stops_checked_at`, R6's `{s}` "falls back to the child's age". It does not.
   - `_looks` takes each held name's own `checked_at` first, and falls back to `stops_checked_at` only when that is missing. So `view["stop_age_s"]` was already the per-name stamp's age, and `{s}` already came from it.
   - Check 1: I called `supervise.beat_view` on a beat that had a per-name stamp only: `stop_age_s` came back 6.0, not None.
   - Check 2: I ran the new test with the base child (no `stops_checked_at`) and the frozen time read from `held.BBB.checked_at` (`probe-base-child-no-stops-checked-at.txt`): it passes, with `s 6 stamp_age 6.13`.
   - The review's real point is right: the old lower bound could not catch a child-age `{s}`. I added `stops_checked_at` as the brief asks, and it matches the real engine, which writes both. But it changes nothing in what R6 reads.
2. **Writing `stops_checked_at` changes one thing that no assertion reads: the `up` row's `blind_s`.** The brief asked to report this.
   - `up()` takes `kid["last_look"] or _when(hb.get("stops_checked_at")) or sup_t` as the cold stamp.
   - Without `stops_checked_at` it took `sup_t`, which is on the test's shifted clock (10:00 New York). Against the child's real-time stamps that gave `blind_s` 3312.8 in my run; the value depends on the hour.
   - With it, `blind_s` is 0.0 (`probe-with-stops-checked-at.txt`). The test's assertions are unaffected, and the alerts are still `["R4", "R6"]`.
   - The probe line was printed by a temporary edit, removed before the commit (`grep -c PROBE` gives 0).
3. **Item 3 has an upper bound and a 3 s wait that the brief does not spell out.**
   - The brief asks for `{s}` "at least the pause's seconds plus `stops_stale_seconds`" and also for the assertion to fail against the child-age mutant. A lower bound alone can never fail against that mutant, because the child is always at least as old as its stamp.
   - So the test keeps the lower bound and adds `|s - frozen stamp's age| <= 1`.
   - It also lets the child live 3 s before the pause, so that the two ages differ by more than that tolerance. This adds about 3 s to `test_supervise.py`.
4. **Item 4's comment also mentions the planned stop.** The old words, "only stop() waits, at most hang_term_grace_seconds", were also untrue of a planned stop, which waits up to `planned_stop_grace_seconds` with an unbounded wait after its SIGKILL. No tick follows a planned stop, though, because `restart_core` returns right after it. The comment now says "a planned stop ends the loop" to stay true. It is still a comment only.

## Concerns

- **Pre-existing, not changed, not in the brief: a huge integer stop crashes `held_text`.** An int too large for a float, such as a JSON integer of 400 digits, raises OverflowError there. `say()` catches only KeyError, ValueError, TypeError and AttributeError, so it would not catch this. Before this task the format raised it; now `math.isfinite` raises it first. The outcome is the same. Only a corrupt book or beat could hold such a value. A fix would be to add OverflowError to `say()`'s except, or to test `isfinite` only on floats and refuse such ints. It is left as it was.
- **The `Drill.popen` window is still open.** It is now disclosed truthfully, not closed: this task is comment only. Closing it is the few lines the comment names.
- `test_supervise.py` takes about 3 s longer, because of item 3's wait: about 271 s per run.
