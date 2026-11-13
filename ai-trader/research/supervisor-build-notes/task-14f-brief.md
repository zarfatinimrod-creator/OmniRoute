### Task 14f: no false "Yahoo slow" at the open, a late first start is told, drill a sees a doubled R1, and two 14e minors

**Kind:** BUILD. **Authority:** the controller's Ruling 58 in the ledger (`progress.md`). It covers the three must-fix
items of the pre-landing review (workflow <workflow-run>: ownerlines-1 = time-1, time-2 with time-4, gate-1, all
reproduced by two agents) and two minors of Task 14e. Not in the plan. It must be committed before Task 20 lands. It
changes no trading rule and touches no file the time machine loads.

**Files:** Modify `aitrader/supervise.py`, `aitrader/ownerlines.py` (item 4 only), `scripts/drill_supervisor.py` (item 3
only), `tests/test_supervise.py`, `tests/test_ownerlines.py` (item 4 only), and the drill test file if item 3 needs one.
Read the code first and find each place by its function name. The review's full findings, with reproductions, are in
`<TASKS>/<bg-task>.output` (JSON, `result.merged[].findings[]`
with ids ownerlines-1, time-1, time-2, time-4, gate-1).

1. **A stop stamp's age counts only market-open seconds.** A news position held overnight is normal (max_hold_days 5).
   The day's first child carries the last stop look from before the close. Its first beats with `market_open` true,
   written before its own first look, carry an age of about 63,000 s (236,000 s on a Monday). That beats
   `stops_stale_seconds` (120), so `look` writes a `stale_stops` start row and sends an urgent R6 that blames a slow
   Yahoo, then an R6b. The 09:30 mark also books those seconds. From now on, wherever `look` judges or writes a stop-look
   age, the age counts only market-open seconds: the measure `open_seconds(stamp time, now, cal)` that `gap_line` and
   blind_s already use.
   - It applies to each name's age in the stale check, the unknown-stamp `born` (Ruling 48), R6's `{s}`, the
     `stale_stops` row's stop, and the mark's `stop`.
   - Ruling 53's resume cap stays on top as it is: the smaller of the two counts.
   - A stamp from inside today's session gives the same age as today.
   - A late first start (12:40) with yesterday's stamp still gets its R6 at the boot beat. That is Ruling 35's accepted
     case; R4 (item 2) now goes beside it.
   Tests (unit level, with an injected clock):
   - Yesterday's 16:00 stamp and a beat with `market_open` true at 09:30:05 give no `stale_stops` row and no R6.
   - At 09:32:05, with the stamp unchanged, there is one R6 whose `{s}` is about 125, never tens of thousands.
   - The mark at 09:31 books no stale seconds from the night.
   - A Monday open with Friday's stamp gives the same as the first case.
2. **A late first start of the day is told (R4), and an earlier day's outage is never told twice.** Today `gap_line`
   returns None after any `sup_stop` whose `why` has no R4b word, `end_of_day` and `closed_today` included. When the
   first parent of a day comes up at 09:40 or 12:40, after a normal close (the morning slots can fail, as on 2026-11-11),
   no line goes out. The new watchdog prompt no longer pushes "the engine was down" itself.
   - From now on a previous `sup_stop` with `why` `end_of_day` or `closed_today` is treated like a row that is no
     `sup_stop`, so R4 applies; `open_seconds` gives 0 over a normal night and over closed days.
   - In every case, when the previous row is from an earlier New York day than now, the gap's `s` counts from today's
     session open (`open_seconds(max(prev t, today's open), now, cal)`) and `{time}` shows that same start. The earlier
     day's part was told by that day's R4c, or counted by its R11, and is not told again.
   - Update the docstring.
   Tests:
   - prev = Thursday's 16:05:01 `end_of_day` `sup_stop`; an up on Friday at 12:40 gives R4 with `s` 11400 and `{time}`
     09:30 New York, rendered as `gap_line` renders times today.
   - The same prev and an up on Friday at 08:05 give None.
   - prev = Thursday 15:50, an `exit` with no recovery; an up on Friday at 08:10 gives None; an up on Friday at 09:45
     gives R4 with `s` 900.
   - An up after a `closed_today` `sup_stop` on a closed day gives None, and on the next session at 09:31 gives None
     (60 s is under `outage_report_seconds`).
3. **Drill a sees a doubled R1.** Today `said()` counts only alert ids with `sent` true, and the waits ask only for at
   least k. The hourly cap (`max_alerts_per_hour` 6) equals the six kills. A mutant whose second episode says R1 twice
   still prints PASS. From now on drill a counts R1 alert ids whatever `sent` says.
   - After each kill's wait it fails unless there are exactly that many.
   - After the last wait it lets a few ticks pass and requires exactly KILLS ids in the dummy part, all with `sent` true,
     and exactly 1 in the engine part.
   - The dummy part's parent gets `max_alerts_per_hour` above KILLS (KILLS + 2), so the cap cannot hide a duplicate.
   - Ruling P3 is kept: six kills, and the cap logic itself is unchanged.
   Check it with the review's mutant (a second R1 in one episode, made in a private exported copy, never in the gate
   clone): drill a must print FAIL against it. Say in the report how you made the mutant and quote the FAIL line.
4. **Two of 14e's minors.**
   - (a) `ownerlines.held_text`: an int stop too large for a float (10**400) raises OverflowError in `math.isfinite` or
     the format, which `say()` does not catch. Render it as the unknown word. Test: `held_text({"MU": 10**400}, 3)` gives
     MU's stop unknown.
   - (b) In `tests/test_supervise.py`, the paused-stamp test of 14d/14e keeps only the upper half of its `{s}` bound.
     The lower half fails the real code when the R6 row arrives 0.45-1.45 s late: a flake at the landing suite. The test
     reads the frozen value from the per-name stamp (`held.<name>.checked_at`, the field R6 reads), not from
     `stops_checked_at`. Its comment says "at least 3 s older".

- [ ] Write the tests of items 1-4; run them: they fail (RED) for the reason each item names (4b is a test change: show
  the old lower bound against a delayed row, or say why it cannot be shown).
- [ ] Implement items 1-4.
- [ ] Run `tests/test_supervise.py` and `tests/test_ownerlines.py` 3 times in a row (each run of test_supervise.py takes
  about 275 s: run each as its own Bash command, timeout 600000 ms), then the whole suite once, then
  `scripts/drill_supervisor.py a --fast` once, every python command through the safe wrapper: `OK` and `PASS a`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `fix(ai-trader): stop ages count market-open seconds only, a late first start is told, drill a counts every R1, a huge stop reads unknown`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped (item 1 changes only
how the parent judges and reports an age); config.json is not changed; no file the time machine loads is touched.
