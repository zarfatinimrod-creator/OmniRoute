### Task 14d: one pause gives one line, no R6 from pre-pause stamps, and a stop that is not a number never drops a line

**Kind:** BUILD. **Authority:** the controller's Ruling 53 in the ledger (`progress.md`), from Task 14b's review minors
and its implementer's concern 5. Not in the plan. It must be committed before Task 20 lands; it changes no trading rule
and touches no file the time machine loads.

**Files:** Modify `aitrader/supervise.py`, `aitrader/ownerlines.py`, `tests/test_supervise.py`,
`tests/test_ownerlines.py`, `tests/test_uptime.py` (item 4 only). Read the code first. Find each place by its function
name: Tasks 14b and 14c have moved lines.

1. **A pause before the first `up` gives one line (spec 8: one outage gives one line).** In `main`, `paused()` sends R4
   for a pause through `gap_line`. When the pause falls between this parent's start and its first `up`, `seen["gap"]`
   is still pending, and the first `up` sends a second R4 or R4b through `gap_line` over the same minutes. `reported`
   in `uptime.close_lines` then counts the pause twice. From now on `paused()` writes its `pause` row as today, but
   sends no R4 while `seen["gap"]` is not None: the first `up`'s line covers the pause. Do not change the first `up`'s
   line. Test: a pause, made the way 14b's pause tests make it (SIGSTOP to the parent and to its child's process group,
   then SIGCONT), before the child's first `up`, with the market open and `outage_report_seconds` small. It gives one
   `pause` row and exactly one alert row of kind R4 or R4b for the stretch, not two. If the window before the first `up`
   cannot be made reliably with a real child, use a child that delays its first look (the way the existing tests'
   stand-in children are written) and say in the report how you held the window open.
2. **No R6 from pre-pause stamps.** After a machine pause, the engine's first fresh beat can still carry per-name stamps
   from before the pause. The stale check in `look` then sends an urgent R6 ("Yahoo slow") beside the pause's R4, and an
   R6b seconds later. From now on, when `seen["resumed"]` is set, each name's age in the stale check is capped at
   `wall - seen["resumed"]`: `min(age, wall - seen["resumed"])`. An unknown stamp keeps Ruling 48's `born` under the
   same cap. So no R6 comes until `stops_stale_seconds` after the resume, and it comes then if the stamps are still
   old. R6's `{s}` stays the true age, as today. Change only the stale check; `_stamp_ages`, `up()`'s blind_s and the
   hang check keep their meaning. A child stopped alone while the parent keeps ticking is judged as today, because
   `seen["resumed"]` is set only by `paused()`. Test: a pause longer than `stops_stale_seconds` (small in the test's
   config) over a child whose beat after the resume still carries the pre-pause stamp for one held name. No
   `stale_stops` row and no R6 before `stops_stale_seconds` after the resume. If the stamp is still old after that,
   there is an R6 with `{s}` at least the pause plus `stops_stale_seconds`. Write the child for this test so its stamp
   does not move after the resume. Signal only the pids and groups your own test started.
3. **A stop that is not a number never drops a line (the same class as Ruling 39).** Today
   `ownerlines.held_text({"MU": None}, n)` raises TypeError on `f"{stop:.2f}"`. A book position without `stop_price`,
   or a beat entry that is not a mapping (`beat_view` gives None), both reach it. `say()` then drops the whole owner
   line, and `--status` returns 2. From now on a name whose stop is not an int or a float (None, a string, a bool) is
   rendered `"MU (סטופ לא ידוע)"`. Build it from `WORDS["held"]["unknown"]`, the module's own word, not a new literal
   in the logic. A numeric stop renders as today. Grep every other caller that formats a held stop as a number.
   `sold_text` formats sales the engine wrote, so leave it unless it reads the same held map. Name any caller you fix
   in the report. Tests in `test_ownerlines.py`: `held_text({"MU": None, "NVDA": 120.5}, 3)` gives both names, MU's
   stop unknown and NVDA's as `120.50`; a string stop gives the same unknown word. In `test_supervise.py`: `status()`
   (R5e or whichever --status path reads the book) on a book with one position that has no `stop_price` returns its
   normal code and prints the line with `סטופ לא ידוע`, not 2.
4. **Pin R4c's unknown word (Task 16's settled item).** One test in `tests/test_uptime.py`: a day whose last `up` row
   has no mapping `held` (so `open_at_close` is None) and whose last outage is still open at the close. Its R4c reads
   `"לא ידוע"` and never `"אין פוזיציות"`. Build the day the way the existing R4c tests build theirs. Task 14c changed
   R4c's rules (an R4 or R4b row sent during the trailing outage suppresses it), so build a day where R4c is still sent.
5. **Name the pause check's ceiling.** At the pause check in `look`
   (`if last is not None and wall - last[0] > sup["hang_seconds"]`), add one `ponytail:` comment. It says that any wait
   inside the loop longer than `hang_seconds` reads as a pause, that today only `stop()` waits, at most
   `hang_term_grace_seconds`, and that the upgrade is to measure the pause from the process's own CPU-stopped time.
   Comment only; no code change.
6. **Test hygiene.** `STAMPLESS_CHILD` joins `kill_ours`'s recognised argv set in `tests/test_supervise.py`, beside
   `GROUP_CHILD`. Any child script this task adds for items 1-2 joins that set too.

- [ ] Write the tests of items 1-4; run them: they fail (RED) for the reason each item names (item 4 may pass at once,
  since 14b already gives "לא ידוע": say so in the report; it is a pin).
- [ ] Implement items 1-3, 5 and 6.
- [ ] Run `tests/test_supervise.py`, `tests/test_ownerlines.py` and `tests/test_uptime.py` 3 times in a row, then the
  whole suite. Run every python command, including one-off text edits, through the safe wrapper. Expect `OK`. Say in
  the report how long each new process test takes.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `fix(ai-trader): a pause before the first up and pre-pause stop stamps raise one line, not three, and a stop that is not a number never drops an owner line`.

**For the report and the gate:** no buy, sale or stop rule changes. No stop look delayed or skipped: item 2 delays only
the owner's line after a pause the R4 already reports. config.json is not changed. The task touches no file the time
machine loads.
