# Task 15 report - Handover by the clock (+ Ruling 37)

Gate clone `<SCRATCH>/clones/sup`, branch `supervisor-build`.
Checks before anything else: HEAD `e1ea314ebc6f00e3dc72b5fd1b013fe892db7d16`, branch `supervisor-build`, clean tree.

Final HEAD `0952ee9b62a29832c555906d71a35d0515161648`. One commit, no attribution line of any kind, `git status --short`
empty after it:
- `0952ee9b` feat(ai-trader): the parent hands over by the clock before the 2-hour cap and the next one measures the gap

No `git stash` in any form. No push, fetch, pull, merge, rebase, reset or branch command. `_tasks` not touched. Every
test run, file run, suite run, mutation run and diagnostic ran through the `safe` wrapper. One exception, for the
record: a short `python3 -` heredoc that only rewrapped four over-long lines of `supervise.py` (pure text replacement,
no project import, no network) ran without the wrapper. Every later edit script used it.

## What I implemented

### `aitrader/supervise.py`
- `handover_due(started_ny, now_ny, times, min_leg_minutes, max_leg_minutes) -> bool` (module level, beside
  `near_until`). True when `now_ny - started_ny >= max_leg_minutes` (the backstop). Also true when a listed time of
  `now_ny`'s day, `t`, satisfies `started_ny + min_leg_minutes <= t <= now_ny`. So it is true from the first tick at or
  after a listed time that lies `min_leg_minutes` or more after the start; a closer one is skipped. Times are "HH:MM",
  read with `split(":")` as `near_until` reads `--until`.
- `main`, `watch`: after the signal and orphan checks, `if a.handover and handover_due(started_ny,
  clock().astimezone(NY), ...)` answers "handover". `started_ny` is the parent's start on the injected clock (the
  `now` that `sup_start` takes). The core does the rest as built in Task 11: during a child's run it makes the planned
  stop and returns `(76, "handover")`; during a back-off it returns at once with no start. Without `--handover`,
  `watch` never answers "handover".
- `main`, after `restart_core` returns "handover": it reads the last beat, `_read_beat(paths.heartbeat)`, and sets
  `st["handover"] = {"at": _utc(clock()), "last_look": ...}`. `last_look` is the oldest look over the held names,
  `min(_looks(hb).values())`. `_looks` gives each name's `checked_at`, else the beat's `stops_checked_at`, as Task 12
  reads it. With nothing held it is the beat's `at`. With no readable time (no heartbeat file at all) it is `None`.
  The existing tail then writes `sup_stop` "handover", saves the state file, prints `supervise: 76 handover. Run ...`
  and returns 76.
- `up()`: `handover_s` comes from the state file's `handover`, loaded at this parent's start. Its value is
  `round(first - last_look, 1)` seconds. `first` is this child's first look: `max(after)`, the same "first look
  after" that `blind_s` uses. With nothing held, `after` is empty and `first` is the beat's `at`, so the measure runs
  beat to beat. `handover_s` is null when either time cannot be read. The first `up` that sees a `handover` clears it
  (`st["handover"] = None`) and calls `save()` before the row, as the `code` row does with `last_commit`. Every later
  `up` therefore carries null.
- Ruling 37: after `restart_core`, a planned end (`word in PLANNED`) calls `episode_end(clock())` when the episode has
  an `up` that came after its last fall (`ep["ups"][-1]["t"] > ep["falls"][-1]["t"]`). The R1 goes through `say`, so
  `finish()` waits for it and its alert row comes before `sup_stop`. With no `up` after the last fall, nothing more is
  said (see departure 4).
- Config check at start (see departure 3): `min_leg_minutes` and `max_leg_minutes` join `NUMBERS`. Every
  `handover_times_ny` entry must match `HHMM` = `([01]\d|2[0-3]):[0-5]\d`, else exit 2. `UNTIL` is now
  `rf"{HHMM.pattern}|24:00"`, the same regular expression as before.
- Docstrings: module ("Tasks 10-15", the handover), `main` (clock answers the handover times; `--handover`; the state
  file's handover; ruling 37), `up` (`handover_s`).
- Ruling P8: no build here. `leave()` does not exist yet, and the handover path calls nothing of the dead-man.

### `tests/test_supervise.py`
- Class `Handover(Parents)`, at the end of the file, with a helper `clock_from(h, m, s)`: a clock that says h:m:s New
  York on 2026-11-12 and runs on.
  - `test_handover_due`: verbatim from the brief.
  - `test_a_handover_ends_with_76_and_the_next_parent_measures_it`: the clock starts at 09:17:58 New York, so 09:18
    comes 2 s after the start. `min_leg_minutes=0`. The child beats for good. As a safety stand-in, `stop_after=10`
    sends SIGTERM at 10 s, so a parent that never hands over ends with 143 instead of hanging the run. The brief's
    assertions follow. P17's assertion replaces the year check. The second parent runs on the same state directory
    and the same clock, now past 09:18: `--until 09:18`, and its child beats 3 times and exits 0, which is the end of
    the day. Then `0 <= handover_s < 60` and `handover` is None.
  - `test_without_the_flag_no_handover_happens`: `max_leg_minutes=0`, so with the flag a handover is due at every
    tick. The child beats 3 times and exits 0 at `--until 10:00`. The brief's assertion, `["end_of_day"]`, follows.
    Then a contrast run with `--handover` on a fresh state directory gives `[("handover", 76)]`, which proves the setup
    would hand over.
  - Self-review tests: `test_a_listed_time_exactly_min_leg_minutes_after_the_start_is_not_skipped` (the boundary
    survived the mutation pass), `test_last_look_is_the_oldest_stop_look_of_the_last_beat` (a beat written by hand
    with AAA 30 s and BBB 100 s old; the child never beats; `last_look` is BBB's stamp) and
    `test_a_handover_time_that_is_no_clock_time_is_a_bad_config` (six bad values, each exit 2, no row written).
- `ParentLines`, test added by ruling 37: `test_a_planned_end_says_the_r1_of_an_episode_whose_restart_is_up_and_nothing_before_that`.
  It has three runs:
  1. A fall, then a child that beats, with `healthy_seconds=30` and a handover 3 s after the start. Result: rc 76,
     `ids() == ["R1"]` (sent true through the stub), and the last two rows are `alert`, `sup_stop`.
  2. A fall, then a child that never beats, and SIGTERM at 2 s. Result: rc 143, two starts, no alert row.
  3. A fall, then a child that comes up and crashes before it is healthy, then one that never beats, and SIGTERM at
     2 s. Result: rc 143, three starts, one `up`, no alert row.

## TDD evidence

### RED (tests written, no implementation)
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k Handover`
(5 tests at that point; the boundary test came later from the mutation pass):
```
ERROR: test_handover_due
AttributeError: module 'aitrader.supervise' has no attribute 'handover_due'
ERROR: test_last_look_is_the_oldest_stop_look_of_the_last_beat
TypeError: 'NoneType' object is not subscriptable                      (no handover in the state file)
FAIL: test_a_handover_ends_with_76_and_the_next_parent_measures_it
AssertionError: 143 != 76                                              (no handover: the 10 s safety SIGTERM ended it)
FAIL: test_a_handover_time_that_is_no_clock_time_is_a_bad_config
AssertionError: Tuples differ: ([0, 0, 0, 0, 0, 0], 0, [...]) != ([2, 2, 2, 2, 2, 2], 6, [])
FAIL: test_without_the_flag_no_handover_happens
AssertionError: Lists differ: [('end_of_day', 0)] != [('handover', 76)]   (the brief's half passed; the contrast failed)
Ran 5 tests in 20.627s
FAILED (failures=3, errors=2)
```
This failure was expected: the brief's own expectation, `AttributeError ... no attribute 'handover_due'`, is the
failure of `test_handover_due`. The process tests fail one step later because `watch` never answers "handover". The
brief's assertion in the no-flag test passes before and after the change. It is a regression guard, and its contrast
half is what fails RED.

Ruling 37 test, same state of the code (`-k test_a_planned_end_says_the_r1`):
```
AssertionError: Tuples differ: (143, [], ['exit', 'sup_stop']) != (76, ['R1'], ['alert', 'sup_stop'])
Ran 1 test in 10.064s
FAILED (failures=1)
```

### GREEN
`... -k Handover -k test_a_planned_end_says_the_r1 -v`:
```
test_a_handover_ends_with_76_and_the_next_parent_measures_it ... ok
test_a_handover_time_that_is_no_clock_time_is_a_bad_config ... ok
test_a_listed_time_exactly_min_leg_minutes_after_the_start_is_not_skipped ... ok
test_handover_due ... ok
test_last_look_is_the_oldest_stop_look_of_the_last_beat ... ok
test_without_the_flag_no_handover_happens ... ok
test_a_planned_end_says_the_r1_of_an_episode_whose_restart_is_up_and_nothing_before_that ... ok
Ran 7 tests in 11.990s
OK
```

`tests/test_supervise.py` starts processes, so it ran three times in a row each time the file changed:
- Runs 1-3, before the last two test additions (the boundary test, and the third run of the ruling test), at 01:24,
  01:27 and 01:30 New York: `Ran 119 tests in 164.949s / 165.316s / 167.403s`, each `OK`.
- Runs 4-6, on the committed file, at 01:41, 01:44 and 01:47 New York: `Ran 120 tests in 166.525s / 166.213s /
  167.215s`, each `OK`.
- Every output is five lines: dots, the rule, the count, a blank line, `OK`. Pristine. 120 = 113 (Task 14's file) + 7
  new.
- The ruling 37 test alone, three more times after its third run was added: `OK` each.

Any hour (ruling 11:10 UTC): every new process test uses the dummy child, which takes `--until` and never acts on it.
The parent's calendar questions (the day, the handover times, `--until`) read the injected clock only, so the real
New York hour cannot change any result. The 23:59 ceiling of `engine_child.py` starts does not apply: no new test
starts the engine. The runs above were at 01:2x-01:5x New York, outside market hours.

Mutation pass on a scratch copy (`scratchpad/t15/mut`), each mutant against the test that should catch it: 14
mutants, 14 killed. The first pass left M1 alive, and the boundary test was added for it.
- M1 `min_leg` `<=` -> `<`: killed only after the boundary test was added
- M2 "at or after" `<=` -> `<`
- M3 `max_leg` `>=` -> `>`
- M4 the `--handover` check dropped
- M5 `last_look` `min` -> `max`
- M6 `last_look` always the beat's `at`
- M7 `handover` never cleared
- M8 `handover_s` always null
- M9 ruling 37 removed
- M10 ruling 37 on any `up`
- M11 the handover-times check removed
- M12 no `handover` written
- M13 `started_ny` = now
- M14 `min`/`max_leg` dropped from `NUMBERS`

Diagnostic, not a test (scratchpad/t15/peek.py): with BBB held and a 5 s old stamp, the handover wrote `last_look` =
the last beat's `at` - 5 s. The next parent's `up` carried `handover_s` 6.0, which is that stamp plus about 1 s of
relaunch.

## Whole suite
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`,
started 01:50:18 New York on the committed tree, exit 0, wall 229 s. Last three lines:
```
Ran 806 tests in 227.772s

OK
```
806 = 799 (Task 14's independent run at `e1ea314e`) + 7 new. The other output lines (`[news] engine started ...`,
`[journal] skipped unreadable line ...`) come from other modules' engine tests and were there before. An earlier run,
before the last two test additions, gave `Ran 805 tests in 231.046s / OK`.

## Files changed
- `ai-trader/aitrader/supervise.py`
- `ai-trader/tests/test_supervise.py`

## Tests added by ruling
- Ruling 37: `ParentLines.test_a_planned_end_says_the_r1_of_an_episode_whose_restart_is_up_and_nothing_before_that`.
- Ruling P17: the brief's year assertion is replaced in `test_a_handover_ends_with_76_and_the_next_parent_measures_it`
  (no new test).

## Self-review findings and what I did
1. Four new lines of `supervise.py` were over 120 columns; the file keeps to 120. Rewrapped. The one 122-column line
   left in the file was there at `e1ea314e`. In the test file only the brief's verbatim lines and two of mine are over
   120; the file had 234 such lines before.
2. `ho, first = st.get("handover"), None if ... else max(...)` was correct but read badly (a conditional inside a
   tuple assignment). Split into three lines.
3. The `ValueError` text of the config check named only `--until` and the numbers. It now names the handover times
   too. The text is never printed: only the class name is.
4. The mutation pass found the `min_leg_minutes` boundary unpinned. Added
   `test_a_listed_time_exactly_min_leg_minutes_after_the_start_is_not_skipped`. Spec 4.5: "A listed time closer than
   `min_leg_minutes` (20) to the parent's start is skipped", so exactly 20 counts.
5. No test pinned "the oldest `checked_at`" (min, not max; the stamp, not `at`). Added
   `test_last_look_is_the_oldest_stop_look_of_the_last_beat`.
6. A bad `handover_times_ny` would make `handover_due` raise inside the loop. That is a traceback out of `main`, the
   parent dead and its engine with it (PDEATHSIG), and no `sup_stop`. Added the start check and its test (departure
   3).
7. Docstrings updated, so the module and `main` no longer stop at Task 14.

## Departures from the brief, and readings where it is silent
1. **Ruling P17:** the brief's `self.assertEqual(self.state_file()["handover"]["last_look"][:4], "2026")` is replaced by
   `self.assertIsNotNone(datetime.fromisoformat(self.state_file()["handover"]["last_look"]).tzinfo)`, as ruled.
2. **Additions to the brief's given tests.** No given assertion was changed or dropped, except the P17 one.
   - The handover test: `stop_after=10` on the first parent (a safety stand-in, so the RED run and any regression end
     instead of hanging), and `self.assertEqual(rc2, 0)` (the brief computes `rc2` and asserts nothing on it).
   - The no-flag test: the stand-in is `max_leg_minutes=0` (the brief gives no comment for it), plus the contrast run
     with `--handover`.
   - `-k Handover` runs 6 tests, not the brief's 3: three are self-review tests. The ruling 37 test sits in
     `ParentLines`, because it needs the ntfy stub to show the R1 sent.
3. **Config check, not in the brief:** `min_leg_minutes` and `max_leg_minutes` added to `NUMBERS`, and every
   `handover_times_ny` entry must be HH:MM from 00:00 to 23:59, else exit 2. Without it a typo in config.json kills
   the parent mid-session with a traceback (finding 6). The check runs with or without `--handover`, as the `NUMBERS`
   check does for every key main reads.
4. **Ruling 37, "an open restart episode whose `up` row exists":** read as "a child came up after the episode's last
   fall". Take a fall, a child that comes up, a second fall, and a planned end before the next child is up. R1 would
   then say "וחזר אחרי ... שניות" ("came back after ... seconds") of an engine that is down again. So nothing is said,
   and the handover gap measures it, as in the ruling's "no up yet" case. The third run of the ruling test pins this
   reading. Reading it as "any `up` in the episode" is the one-line condition `word in PLANNED and ep["ups"]`
   (mutant M10).
5. **`handover.at`** is `_utc(clock())`, the injected clock, as `halt.at` is. `last_look` comes from the beat, which
   stamps real time. `handover_s` subtracts only beat stamps, so both of its ends are real time.
6. **No readable time in the last beat** (no heartbeat file, as when a parent hands over before its first child ever
   started): `last_look` is null. The next parent's first `up` then carries `handover_s` null and still clears
   `handover`.
7. **`handover_s` is rounded to 0.1 s**, as `blind_s` is. It is plain seconds, as the brief says ("the seconds from
   `last_look`"), not market-open seconds. See concern 1.

## Concerns
1. **The 09:18 handover is before the open, and with a name held overnight its `handover_s` reads about 17 hours.**
   The engine stamps a held name's `checked_at` only on a live look: market open and a live quote
   (`news_live.py:1016`, `_covered`). A process that started before the bell has `checked_at: null` for every held
   name, so `_looks` (Task 12) falls back to the beat's `stops_checked_at`. Before the open, that is the look adopted
   from the previous heartbeat: yesterday's last live look (spec 5.5: "the oldest live look"). So at 09:18
   `last_look` is about 16:00 of the day before. The next parent's first `up` comes at its first beat (market
   closed), so `first` is that beat's `at`, about 09:19, and `handover_s` is about 62,000 s. The brief's own test
   holds nothing, so it does not meet this case.
   - This follows the brief and spec 4.5 to the letter ("the seconds from the old engine's last stop look to the new
     one's first").
   - It contradicts target 11 ("60 s, logged for every handover") and the plan's later OPS pass mark (plan line 1665:
     "Every handover is a `sup_stop` "handover" with `rc` 76 followed by an `up` whose `handover_s` is under 60"). That
     check would fail every morning the news book holds a name overnight.
   - `blind_s` and R4b are not affected: both count market-open seconds (`open_seconds`), which are 0 before the open.
   - Options, one line each in `up()` or at the handover:
     - (a) `handover_s = open_seconds(last_look, first)`: market-open seconds, as `blind_s`. Before the open it is 0;
       in session it equals the plain seconds. A test's value then depends on the hour the suite runs unless
       `open_seconds` is patched, as the `blind_s` tests do.
     - (b) Take `last_look` from per-name `checked_at` only. When no held name has one, use the beat's `at`, i.e. beat
       to beat as with nothing held. Before the open this measures the relaunch itself, which is target 11's subject.
       A blind name in session whose `checked_at` is null would then understate.
     - (c) Keep it as built, and read the OPS mark for in-session handovers only.
   - Not built, because each option changes what the brief defines. It needs the controller's ruling.
2. **A parent that hands over again before any of its children came up** overwrites the pending `handover` with its own
   `last_look`. When names are held this changes nothing: the engine keeps the adopted stamps, so the oldest look is
   the same. When nothing is held, the measure restarts from the later beat. Nothing is at risk then, since there is
   no stop to check. Left as is.
3. **The commit author** is the gate clone's configured identity (`Claude <<email>>`), as on every commit
   of the branch (Ruling 34). The message carries no trailer or footer.

## Fix round 1

Base 0952ee9b (tree clean, branch supervisor-build). One new commit: `2219f55d fix(ai-trader): measure a handover with
the market closed from beat to beat`. Paths: `ai-trader/aitrader/supervise.py`, `ai-trader/tests/test_supervise.py`.
No attribution lines.

### F2 - fixed (the reviewer's recommended form)
- `ai-trader/aitrader/supervise.py:1169-1173` (the handover branch of `main`): when the last beat says
  `market_open` false, `looks` starts empty, so `last_look` = that beat's `at`, as when nothing is held. In session
  (`market_open` true, or a beat without the field) the per-name stamps and `_looks` are used exactly as before. The
  test is `is False`, so only a beat that says the market is closed takes the new path.
- `ai-trader/aitrader/supervise.py:1068-1070` (the comment in `up()`): "beat to beat when nothing is held or the
  market was closed". Comment only.
- Why this is the root: with the market closed no stop is looked at on either side. `up()` (Task 12, as reviewed) already
  takes the new child's first beat for every unlooked name (supervise.py:987 calls `up` at the first beat when
  `view["open"]` is false; supervise.py:1060-1061 maps a stamp older than the child, or a blind name, to the beat's
  `at`). The old side used a look while the new side used a beat. Both sides now use beats when the market is closed.
- Both cases in the review are covered by one condition. The 09:18 case: no per-name stamp, fallback to yesterday's
  adopted `stops_checked_at`. The 14:17 handover of an early-close day: per-name stamps from about 13:00 persist in
  `_covered` and reach the beat (news_live.py:1010, 1711).
- Brief and spec: no contradiction found. The brief defines `last_look` as "the oldest `checked_at` of the last beat, or
  that beat's `at` when nothing was held". Before the open no held name has a `checked_at` at all, so that definition
  says nothing for the 09:18 case. The `stops_checked_at` fallback was a reading of Task 12's `_looks`, not the brief's
  words. Spec 4.5 says "The first is before the open, where no stop is checked". With the market closed the new engine
  has no "first" stop look either, and Task 12 reads its first beat in its place; the fix reads the old side the same
  way. Target 11 (60 s) and the brief's own assertion `0 <= handover_s < 60` now hold for out-of-session handovers.
  - For the controller: in the early-close 14:17 case the fix sets aside per-name stamps that the brief's literal
    "oldest `checked_at`" would use. I found no written ruling on F2 in controller-notes.md, rulings-10-28.md or
    progress.md. I built it because this dispatch lists F2 under "Findings to fix" and names this form.
- Not touched: `_looks`, `up()`'s arithmetic, `blind_s`, R4/R4b (`gap_line` counts market-open seconds), Task 16.

Test added: `Handover.test_with_the_market_closed_a_handover_is_measured_beat_to_beat`
(`ai-trader/tests/test_supervise.py:1811-1831`).
- Setup: a beat written by hand, as the engine writes it with the market closed. `market_open: false`, both names
  blind, `stops_checked_at` 17 h old. AAA has `checked_at: null` (the 09:18 case). BBB has a stamp 80 min old (the
  early-close 14:17 case).
- First parent: its child never beats, then the parent hands over at 09:18, 2 s after its start.
- Second parent: same shifted clock, child closed, both names held with the old stamp.
- Asserts: rc 76 and rc 0; `0 <= handover_s < 60` on the second parent's first `up`; `last_look` equals the beat's `at`.
- The hour is irrelevant: the parents run on the injected clock (2026-11-12 09:17:58 NY), the dummy ignores
  `--until`, and `market_open` comes from the script, never from the real clock.

### TDD evidence
RED, before the fix:
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k test_with_the_market_closed_a_handover_is_measured_beat_to_beat`
```
FAIL: test_with_the_market_closed_a_handover_is_measured_beat_to_beat (test_supervise.Handover.test_with_the_market_closed_a_handover_is_measured_beat_to_beat)
    self.assertTrue(0 <= handover_s < 60, handover_s)
AssertionError: False is not true : 61202.0
Ran 1 test in 2.374s
FAILED (failures=1)
```
(61,202 s is the review's "about 62,000 s".)

Mutant, after the fix: a weaker fix that ignores `market_open` and only replaces the `stops_checked_at` fallback by the
beat's `at` (`looks = [_when(v.get("checked_at")) or _when(hb.get("at")) for v in _held(hb).values()]`) fails the same
test with `AssertionError: False is not true : 4802.0` (the early-close case). The file was restored from a copy and the
Handover tests re-run green.

GREEN, the Handover class 3 times in a row:
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k Handover`
```
== run 1
Ran 7 tests in 7.042s
OK
== run 2
Ran 7 tests in 6.932s
OK
== run 3
Ran 7 tests in 6.983s
OK
```
The whole file 3 times in a row. The handover branch is also reached by the tests at test_supervise.py:930, 1128 and
1549.
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py`
```
== run 1
Ran 121 tests in 169.976s
OK
== run 2
Ran 121 tests in 166.405s
OK
== run 3
Ran 121 tests in 167.504s
OK
```

### Whole suite (before the commit)
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`
exit 0, wall 241 s. Last three lines:
```
Ran 807 tests in 240.560s

OK
```
After the commit, `git status --short` prints nothing. HEAD 2219f55da0545fbe57ab0abf7adde0bcb4d287c7.
