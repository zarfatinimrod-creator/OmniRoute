### Task 14c: one outage gives one line, R11 counts seconds, and the drills clean up after themselves

**Kind:** BUILD. **Authority:** the controller's Ruling 50 in the ledger (`progress.md`), from the deferred minors of
Tasks 16 and 17. Not in the plan. It must be committed before Task 20 lands; it changes no trading rule and touches no
file the time machine loads.

**Files:** Modify `aitrader/uptime.py`, `aitrader/supervise.py` (item 2 only: the alert row's extra field),
`aitrader/__main__.py` (item 3 only), `scripts/drill_supervisor.py`, `tests/test_uptime.py`, `tests/test_supervise.py`
(item 2 only), `tests/test_drill_supervisor.py` (or whichever file holds the drill tests; find it). Read the code
first; line numbers below are from eacdefc5 and Task 14b has moved some of them: find each by its function name.

1. **One outage gives one line (spec 8: one outage gives at most DM1, R4, W1).** In `uptime.close_lines`, R4c is sent
   when the day's last outage is still open at the close. Today an outage whose parent comes back between 16:00 and
   16:22 gets R4 (sent by the parent at its come-back) and also R4c, and R11's reported sum counts it twice. From now
   on R4c is not sent, and adds nothing to `reported`, when an alert row of the day of kind R4 or R4b with `sent` true
   has a `t` at or after the start of that trailing outage. Test: a trailing outage from 15:40, an R4 row with sent
   true at 16:10 whose `m` covers it: no R4c, and R11 compares against that R4's minutes once; the same outage with no
   R4 row still gives R4c.
2. **R11 compares seconds.** Today R11 compares `round(unprotected_s / 60)` with the sum of `m` (each rounded on its
   own), so an unreported 40 s beside a reported 210 s gives 4 against 4 and disappears. From now on the R4 and R4b
   alert rows carry `s`, the exact market-open seconds of the outage, beside `m` (supervise.py: where the alert row
   gets `extra={"m": ...}`; `gap_line` already computes `s`, carry it through its fields the same way `m` is carried,
   and keep it out of the owner's text). `close_lines` sums the reported rows' `s` (a row without a numeric `s` counts
   `m * 60`, so older rows still read), adds R4c's own seconds when R4c is sent, and sends R11 when the day had a trip
   or when `round((unprotected_s - reported_s) / 60) >= 1` (Ruling 54: the untold remainder rounded once, so more
   than 30 s untold fires it; the earlier "60 or more" was the controller's slip and contradicted this test and
   `test_the_days_counts_and_r9`). R11's `{m}` stays `round(unprotected_s / 60)`.
   Tests: the 40 s + 210 s case gives R11; a fully reported day gives none; a row with only `m` still counts; in
   `test_supervise.py`, one R4 alert row written by a parent carries a numeric `s` equal to the line's seconds.
3. **`uptime-report --days` below 1 is refused** with exit 2 and one line (today `--days 0` silently becomes
   `report_days` and a negative value prints an empty page with exit 0). Test for 0 and -1.
4. **The drill script cleans up after itself and prints no exception text** (`scripts/drill_supervisor.py`):
   - Every child process a drill starts (parents, bare engine children of drills e and g, stubs) is killed when the
     drill ends by any path: normal end, an exception, and SIGTERM or SIGHUP sent to the drill script (install
     handlers that turn those into the same cleanup, then exit with 1 for the interrupted run). Kill only the pids and
     groups the script itself started; never by a name pattern.
   - `Drill()` is built inside the `try`, so a failure building it (for example the ntfy stub) prints a FAIL line for
     that drill, removes or keeps its temporary directory by the existing rule, and lets the other drills run.
   - FAIL lines print the exception's class name and the kept directory, never the exception's text or git's stderr
     (constraints.md item 11: class, never the text). If a FAIL needs a detail to be readable (which file, which
     round), print that detail from the drill's own values, not from the exception.
   - Drill e's random generator gets a seed: chosen at start when `--seed` is not given, printed in its FAIL line, and
     accepted by a new `--seed N` option so a failed round can be replayed.
   - The look mark refuses a stamp from before the kill: a stamp earlier than t0 is a FAIL, not a negative pass
     (today `max(stamps) - t0` has no lower bound).
   Tests: a drill script run (through the safe wrapper, as the existing drill test runs it) that gets SIGTERM while a
   drill with a bare engine child runs leaves none of its child pids alive afterwards (check each pid it started,
   read from its output or its temporary directory, not by a name pattern); a FAIL line built from an exception
   carries the class and not the text; `--seed` is accepted and printed. Keep the existing drill tests passing.

- [ ] Write the tests of items 1-4; run them: they fail (RED) for the reason each item names.
- [ ] Implement items 1-4.
- [ ] Run `tests/test_uptime.py`, `tests/test_supervise.py` and the drill test file 3 times in a row, then the whole
  suite, then `scripts/drill_supervisor.py all --fast --rounds 20` once (seven PASS lines into the report), every
  python command through the safe wrapper: `OK`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `fix(ai-trader): one outage gives one owner line, R11 counts seconds, the drills kill what they start and print no exception text`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json is not
changed. It touches no file the time machine loads.
