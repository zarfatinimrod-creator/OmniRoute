### Task 14g: a clean day sends no R11, relayed lines say they are late, and four small silent or false lines

**Kind:** BUILD. **Authority:** the controller's Ruling 58 in the ledger (`progress.md`), from the pre-landing review's
should-fix and minor items (workflow <workflow-run>: ownerlines-2 with time-3, ownerlines-3, lifecycle-1, lifecycle-4,
time-6, gate-7). Not in the plan. It must be committed before Task 20 lands. It changes no trading rule and touches no
file the time machine loads.

**Files:** Modify `aitrader/supervise.py`, `aitrader/uptime.py`, `aitrader/ownerlines.py` (item 3 only),
`scripts/drill_supervisor.py` (item 7 only), `tests/test_supervise.py`, `tests/test_uptime.py`, `tests/test_ownerlines.py`
(if item 3 needs it). Read the code first and find each place by its function name (Task 14f, just before you, changed
`look` and `gap_line`). The review's findings, with reproductions, are in
`<TASKS>/<bg-task>.output` (JSON, `result.merged[].findings[]`).

1. **A handover is booked at its true length.** Today `watch` returns `handover` before `look`, so the old parent writes
   no mark in the handover minute. The new parent's first mark has a null `hb`, and `uptime` books a pair whose later mark
   has a null `hb` as a gap for the whole pair: one 46 s handover is booked as about 107 s without stop checks. From now
   on the parent writes its minute's mark before it returns `handover`. If that cannot be done cleanly, `uptime` books a
   null-hb pair as a gap only from the last `exit` or `sup_stop` row inside it, since the exit-to-up stretch already
   covers the outage. Golden test (`tests/test_uptime.py`, built the way its golden days are built): one 46 s handover
   gives `unprotected_s` 46, not 107. Plus a supervise-level test: the old parent's last mark is written in the minute
   it hands over.
2. **A planned short handover is not an untold outage.** R11 (Ruling 54) fires when untold market-open seconds round to a
   minute. Four planned handovers a day (09:18, 10:48, 12:28, 14:17) of about 46 s each make it fire on every clean day.
   The spec's first-day check "a quiet phone" then fails by construction. From now on, in `uptime.close_lines`, the
   exit-to-up stretch of a handover (after a `sup_stop` with why `handover`) that is shorter than
   `outage_report_seconds` counts as reported. A longer one stays untold unless an R4 or R4b row with `sent` true tells
   it. Tests: a day with four sub-60 s handovers and no fall sends no R11; the same day with one handover of 200 s and no
   R4 row sends R11; a trip still sends R11.
3. **A relayed line says it is late.** `--status` hands the watchdog the lines the parent could not send. The watchdog
   relays them up to 30 minutes later, as they are, so a present-tense "the engine is down" can reach the owner after the
   engine is back. From now on:
   - `status()` builds each unsent entry's `text` with a prefix from `ownerlines` (a new WORDS entry, not a literal in
     the logic). The prefix says it was sent late and gives the clock time of the line's first row, in the owner's zone
     (`owner_tz`), as HH:MM. Suggested words: `נשלח באיחור, מ-HH:MM:`.
   - The whole text still fits `max_line_bytes`; cut the free part the way `render` cuts it.
   - An R6 whose R6b already went out with `sent` true is left out of `unsent`, and so is that R6b.
   - The watchdog prompt does not change: it relays `text` as it is.
   Tests: an unsent R3 entry starts with the prefix and its time; an R6 and R6b pair both sent-true-at-R6b gives no R6
   entry; a long line with the prefix stays under `max_line_bytes`.
4. **R2 is not lost at a planned end.** With the hang switch on, R2 is said only at the replacement's first up. A
   planned end (handover, signal, orphaned), a halt, a held lock or a trip between the hang kill and that up drops R2
   with no alert row, so `--status` cannot relay it. From now on, at each of those ends, if an R2 is still pending
   (`ep["r2"]` or whatever holds it now), the parent sends it then. It uses the kill row's time, and a blind time from the
   dead engine's last look to now when that can be built. If the line cannot be built or sent, it writes the alert row
   with `sent` false so the watchdog relays it. Test: a hang kill followed by a planned stop before the next up gives one
   R2 alert row.
5. **A planned stop leaves no grandchild.** A planned stop whose child ends within the grace never signals the child's
   process group, so a `claude -p` scorer call the engine started (`_ask_later`) outlives it. From now on `stop()`, after
   the child's wait returns in the planned branch, signals the child's process group with SIGKILL, as the hang branch
   does. Ruling 36(f) says why this is safe. Test: a stand-in child that leaves a sleeping grandchild in its group; after
   a planned stop, the grandchild's pid is gone. Signal only pids and groups the test started.
6. **No "stops checked again" at the bell.** An R6 episode still open when the market closes is ended by `market_open`
   turning false, and R6b then tells the owner the stops are checked again, which is not what happened. From now on,
   with the market closed, the episode ends with its row only and no R6b. Test.
7. **The cloud drill's alive check reads a live mark.** `cloud-check --alive` passes on any mark after `sup_start`. From
   now on it requires the last mark to be at most `parent_stale_seconds` old and its `hb` not null. In `cloud` mode the
   parent's last line names its drill state directory, so nobody reads it as the live one. Test in the drill test file.

- [ ] Write the tests of items 1-7; run them: they fail (RED) for the reason each item names.
- [ ] Implement items 1-7.
- [ ] Run `tests/test_supervise.py`, `tests/test_uptime.py` and the drill test file 3 times in a row (each run of
  test_supervise.py takes about 275 s: run each as its own Bash command, timeout 600000 ms), then the whole suite once,
  then `scripts/drill_supervisor.py all --fast --rounds 20` once (seven PASS lines into the report), every python
  command through the safe wrapper: `OK`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `fix(ai-trader): planned handovers are booked true and raise no R11, relayed lines say they are late, R2 survives a planned end, no grandchild, no R6b at the bell, a live cloud mark`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json is not
changed; no file the time machine loads is touched.
