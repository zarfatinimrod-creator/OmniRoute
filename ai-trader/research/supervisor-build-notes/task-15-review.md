# Task 15 review - Handover by the clock (+ Ruling 37)

Base e1ea314e, head 0952ee9b, one commit. Review package: `review-task-15.diff` (exit 0, 30,598 bytes). Read-only on the
gate clone. No test re-run: nothing in the code raised a doubt that the reported runs leave open.

### Spec Compliance

Compliant with the brief, ruling P17, ruling P8 (nothing built) and ruling 37 as far as this diff shows. One reading of
ruling 37 is listed under cannot-verify for the controller.

- `handover_due` has the brief's exact signature (supervise.py:322-331). Checked by hand against all six cases of
  `test_handover_due`: F, T, F, T, F, T.
- Only with `--handover`: `watch` answers "handover" after the signal and orphan checks (supervise.py:961-964).
  `restart_core` already maps it to a planned stop and 76 (`PLANNED = {"handover": 76, ...}`, supervise.py:214, checked).
- `main` writes `handover = {"at", "last_look"}` after the core returns (supervise.py:1167-1170). The existing tail then
  writes `sup_stop` "handover", saves and returns 76.
- The next parent's first `up` carries `handover_s` and clears `handover` with a save (supervise.py:1067-1075, 1087).
- Tests: `test_handover_due` is verbatim. `test_a_handover_ends_with_76_and_the_next_parent_measures_it` keeps every
  assertion of the brief. The year check is replaced exactly as ruling P17 says, and `rc2 == 0` is added.
  `test_without_the_flag_no_handover_happens` keeps the brief's assertion and adds a contrast run that proves the setup
  would hand over (test_supervise.py:1756-1785).
- Commit message as the brief gives it. Body clean, no trailer. Only the two listed paths changed. `git status --short`
  is empty.

Checks run on named risks:
- `started_ny` is the parent's start. Main's `now` is set once at supervise.py:817 and never reassigned at main level
  (grep). Every other `now =` is inside a nested function.
- A pending `handover` does not survive into the next day: `load_state` clears it for a file of another day
  (supervise.py:160-176, Task 10).
- The thresholds live in config: `handover_times_ny`, `min_leg_minutes` and `max_leg_minutes` are at config.json:335-337.
  The logic has no literal.
- Ruling 37's scope: `PLANNED` is exactly handover, signal and orphaned, so an end of day never sends R1 through this path.
- Test timing: `Parents.QUICK` sets back-off and loop to 0.05 s (test_supervise.py:780). The 2 s and 3 s windows of the
  ruling-37 runs have a wide margin.
- When the engine stamps a per-name `checked_at`: only on a live quote (news_live.py:1013-1017). `stops_checked_at` is
  adopted from the previous heartbeat whatever its day (news_live.py:1648-1652). Both were checked for the Important
  finding below.

Cannot verify from this diff:
- Spec 4.5 "one last dead-man ping with the longer delay" at a handover: ruling P8 gives it to Task 21. This diff calls
  nothing of the dead-man.
- Spec 4.5 "180 s or more inside the session is reported as R4b": this comes from Task 13's `gap_line` on the next
  parent's first `up`, not from `handover_s`. Check that the gap line counts from the `sup_stop` "handover" row in
  market-open seconds.
- Ruling 37, departure 4: the code requires an `up` AFTER the episode's last fall (supervise.py:1162-1164). Under the
  literal text ("when the episode's up exists") the case fall, up, fall, planned end would send R1. As built it sends
  nothing, and that first crash reaches the owner only through the next parent's gap line, if at all. The reading
  avoids an R1 that says "came back" of an engine that is down again. The controller should confirm it.
- Task 16 reads `handovers` (the `handover_s` values) and attributes "handover" seconds. Those values carry the
  Important finding below.

### Strengths
- `handover_due` is small and readable. The `min_leg_minutes` boundary ("only a closer one is skipped") is pinned by its
  own test, which a mutation pass showed was missing. The implementer reports 14 mutants and 14 killed.
- `test_last_look_is_the_oldest_stop_look_of_the_last_beat` pins two things: `min`, not `max`, and the per-name stamp
  over a newer `stops_checked_at`. It does this with a beat written by hand.
- The no-flag test was made meaningful with `max_leg_minutes=0` plus a contrast run. The brief's single assertion alone
  would pass with or without the feature.
- The start check refuses a `handover_times_ny` that `handover_due` could not parse. Without it a config typo would raise
  inside the loop and kill the parent and its engine mid-session with no `sup_stop`. It follows the existing
  `NUMBERS`/exit 2 pattern and has a test with six bad values and no rows.
- The R1 of an episode that a planned end cuts short goes through `say`, so `finish()` orders its alert row before
  `sup_stop`, and a test checks this. The two "nothing" cases are pinned too.
- `up()` clears a `handover` it cannot read (not a dict) as well, so damaged input cannot stick.
- The concern on the 09:18 handover was found and raised rather than papered over.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. **ai-trader/aitrader/supervise.py:1167-1170 (with `_looks`, supervise.py:356-360, and `up()`, supervise.py:1067-1072):
   at the 09:18 handover, with a name held overnight, `handover_s` reads about 62,000 s. Plan-mandated.**
   - What happens: before the open the engine stamps no per-name `checked_at`, because no quote is live
     (news_live.py:1013-1017). `_looks` therefore falls back to the beat's `stops_checked_at`. Before the first live
     look of the day, that value is the one adopted from yesterday's heartbeat (news_live.py:1648-1652).
   - So `last_look` is about 16:00 of the day before. On the new side, `up()` treats an unlooked name as the beat's `at`,
     about 09:19. The result is neither "look to look" nor "beat to beat".
   - Why it matters:
     - Target 11 is "planned handover -> the next parent is up: 60 s, logged for every handover".
     - Plan line 1665's OPS pass mark is "an `up` whose `handover_s` is under 60" for EVERY handover. It would fail every
       morning the news book holds a name overnight. With the 5-day exit, that is a normal state.
     - Task 16's `handovers` list would report the 17-hour figure.
     - The plan itself guards against exactly this number across days (plan line 634, "must not give the next morning's
       `up` an 18-hour `handover_s`"). The same number comes back through the adopted stamp.
     - It is plan-mandated: spec 4.5 and the brief define `handover_s` as "from the old engine's last stop look". They
       also list a before-open handover time ("the first is before the open, where no stop is checked"). Their test holds
       nothing, so it never meets this case. The implementer raised it as concern 1 and built none of the options.
   - Fix, for the controller's ruling:
     - Recommended: when the last beat says `market_open` false, take `last_look` = that beat's `at` (beat to beat, as
       when nothing is held). That is symmetric with how `up()` already treats an unlooked name on the new side, and
       measures what target 11 is about. Keep per-name stamps in session.
     - Add one test: a held name, `market_open: false`, a `stops_checked_at` hours old, and a handover. Assert
       `0 <= handover_s < 60`.
     - Report option (a), `open_seconds`, gives 0 before the open and loses target 11's relaunch time for the 09:18 leg.

#### Minor (Nice to Have)
1. supervise.py:719-722 (main docstring) says "Ages never read it" of the injected clock. The `max_leg_minutes` backstop
   is an age, and it is read on that clock (`handover_due(started_ny, clock()...)`). A wall-clock jump would move the
   backstop, which exists for the real 2-hour cap. The signature is the brief's. Say so in the docstring.
2. supervise.py:84-93: `min_leg_minutes` and `max_leg_minutes` must be numbers, but zero or a negative value passes. With
   `max_leg_minutes <= 0` and `--handover`, every parent hands over at its first tick. That is an endless chain of 76s,
   one model turn each, the loop Review Focus 2 warns about. The `POSITIVE` pattern covers this class for the loop and
   graces. Adding `max_leg_minutes` to it would need the no-flag test's stand-in changed (`min_leg_minutes=0` and a
   listed time instead).
3. test_supervise.py:1556-1564 (ruling-37 run 3) and the brief's tests depend on process timing, with 2-3 s windows. The
   margin is wide with `QUICK` (0.05 s back-off), but this adds three more timing-bound process runs to a file that
   already takes about 165 s.
4. Report concern 2, accepted as is: a parent that hands over again before any child came up overwrites `last_look`.
   With nothing held the measure restarts from the later beat.
5. Process: one `python3 -` heredoc ran outside the mandatory `safe` wrapper. It only rewrapped lines, with no import,
   so no risk was realised, but it breaches the 15:35 UTC ruling ("EVERY python command").
6. The reported whole-suite output carries noise lines from other modules (`[news] engine started ...`,
   `[journal] skipped unreadable line ...`). They were there before this change and do not come from it. The file runs
   of test_supervise.py are clean.

### Assessment
Task quality: Needs fixes. The build matches the brief and its rulings, and the tests are faithful and strong.
`handover_s` is wrong as a measure for the 09:18 before-open handover whenever a name is held overnight. That is a
plan-mandated defect that breaks target 11's OPS pass mark, and the controller must rule on it before this measure can
be trusted.
