### Task 14e: the minors of 14c and 14d that cost little: no "nan" in an owner line, two tests that check what they claim, two comments that say what is true

**Kind:** BUILD. **Authority:** the controller's Ruling 55 in the ledger (`progress.md`), from Task 14d's review minors and
one of Task 14c's. Not in the plan. It must be committed before Task 20 lands; it changes no trading rule and touches no
file the time machine loads.

**Files:** Modify `aitrader/ownerlines.py` (item 1), `aitrader/supervise.py` (item 4: comment only),
`scripts/drill_supervisor.py` (item 5: comment only), `tests/test_ownerlines.py` (item 1), `tests/test_supervise.py`
(items 2 and 3). Read the code first; find each place by its function or test name, not by line number.

1. **A stop that is not a finite number is unknown.** `ownerlines.held_text` (Task 14d) renders a stop that is no int or
   float as `WORDS["held"]["unknown"]`. A float NaN or infinity still passes and prints `nan` or `inf` in an owner line.
   From now on a float stop that is not finite (`math.isfinite`) is rendered the same unknown word. Test in
   `tests/test_ownerlines.py`: `held_text({"MU": float("nan"), "NVDA": float("inf"), "AMD": 12.0}, 3)` gives MU's and
   NVDA's stop unknown and AMD's as `12.00`.
2. **The open-episode guard asserts its pause.** In `tests/test_supervise.py`, the test Task 14d added for "an R6
   episode already open before the pause is judged on the true ages" (the open-episode guard) never asserts that a
   `pause` row was written, so it passes even when no pause happened (it already passes on the code before 14d). Add an
   assertion that exactly one `pause` row was written (the file's own helper for reading rows, for example
   `self.urows("pause")`), placed where the pause has surely been seen.
3. **R6's `{s}` is checked against the stamp, not the child's age.** `PAUSED_STAMP_CHILD` (Task 14d) writes per-name
   stamps but no `stops_checked_at`, so R6's `{s}` falls back to the child's age (`time.time() - kid["started"]`), and the
   test's comment ("`{s}`: true") claims more than it checks. Make the child also write `stops_checked_at`, frozen at its
   pre-pause value like the per-name stamp, so `{s}` comes from the stamp's age (`view["stop_age_s"]`). Then assert that
   R6's `{s}` is at least the pause's seconds plus `stops_stale_seconds`, measured from that frozen stamp. Keep the
   comment true to what the test checks. If writing `stops_checked_at` changes what the test observes in another way,
   say so in the report.
4. **The pause check's ponytail comment names every wait.** At the pause check in `supervise.main`'s loop (the
   `ponytail:` comment Task 14d added above `if last is not None and wall - last[0] > sup["hang_seconds"]`), the words "at
   most hang_term_grace_seconds" leave out the `child.wait()` after SIGKILL in `stop()`, which has no bound (normally
   instant). Say so in the comment. Comment only; no code change.
5. **The drill's ponytail comment says what is still open.** In `scripts/drill_supervisor.py`, the `ponytail:` comment in
   `Drill.popen` (Task 14c) still names "a flag the handler reads" as the future way to close the window between the fork
   and the child being added to `d.procs`. That flag now exists (look for it: Task 14c's fix round added a hold flag the
   signal handler reads). Make the comment true: either the window is closed by that flag (then say how, in one line, or
   drop the comment), or it is still open (then say exactly where and what would close it). Read the code to decide;
   comment only, no code change.

- [ ] Write the tests of items 1-3; run them: item 1's test fails (RED) before the change, and item 3's new `{s}`
  assertion fails against a mutant where R6's `{s}` uses the child's age (say in the report how you checked it); item 2
  is a guard: show it fails when the pause is removed from the test (for example by not sending SIGSTOP), then restore.
- [ ] Implement items 1, 4 and 5.
- [ ] Run `tests/test_ownerlines.py` and `tests/test_supervise.py` 3 times in a row (each run of test_supervise.py takes
  about 270 s: run each as its own command, timeout 600000 ms, never two in one command), then the whole suite once,
  every python command through the safe wrapper: `OK`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `fix(ai-trader): a stop that is no finite number reads unknown, two supervisor tests check what they claim, two comments say what is true`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json is not
changed. It touches no file the time machine loads.
