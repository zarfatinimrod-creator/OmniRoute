# Task 14c report (second dispatch): DONE

Commit `5640a80b` on `supervisor-build` in the gate clone (parent `bf37c23d`), full sha
`5640a80bf16f757cf9bc7701a002ed2d2be6a594`. Message, with no attribution lines:
`fix(ai-trader): one outage gives one owner line, R11 counts seconds, the drills kill what they start and print no exception text`.
`git status --short` prints nothing after the commit.

## What I did

1. Checked the start state. HEAD was `bf37c23d872dabfda8047c7df25e095ec21c1627`, the branch was `supervisor-build`, and the
   tree was clean.
2. Checked the parked patch's sha256: `ca48a2c7c03859f1fc860c6dfdee0eb15427baa4cc6b4d0b5baf420c4ef17d79`. It matches.
3. Read the patch against the brief (as amended by Ruling 54), the controller notes and constraints.md. `git apply --check`
   passed on bf37c23d, and I applied it there.
4. Made five small changes on top of the patch (see "Changes over the parked patch").
5. Ran the GREEN runs, the whole suite and the drill run, then committed and reviewed the diff.

The first dispatch's RED evidence stands, and I did not redo RED (dispatch instruction). Every python command went through
`safe`, including the one-off checks.

## What is implemented (brief items 1-4)

1. **One outage gives one line** (`aitrader/uptime.py`, `close_lines`). R4c is not sent, and adds nothing to `reported`,
   when one of the day's alert rows has kind R4 or R4b, `sent` true, and a `t` at or after `began` (the start of the
   trailing outage, the time R4c would print).
2. **R11 counts seconds.**
   - `supervise.gap_line` puts `"s": s` (the exact `open_seconds`) into its fields beside `m`. Both `say` call sites that
     write an R4 or R4b row pass `extra={"m": ..., "s": ...}`: the first `up` and the pause R4. No template names `{s}`,
     so the owner's text does not change.
   - `close_lines` sums the told rows' `s`, once per id. A row without a numeric `s` counts `m * 60`. R4c's own `run`
     seconds are added when R4c is sent.
   - R11 is sent when `report["trips"]` or `round((unprotected_s - reported_s) / 60) >= 1` (Ruling 54). R11's {m} stays
     `round(unprotected_s / 60)`.
3. **`uptime-report --days N` with N < 1** prints `uptime-report: --days takes 1 or more, not N` to stderr and returns 2
   (`aitrader/__main__.py`).
4. **The drill script** (`scripts/drill_supervisor.py`):
   - **SIGTERM and SIGHUP are handled.** `main`, in drill mode only, installs `interrupted` for STOPS = {SIGTERM, SIGHUP}.
     The handler sets both signals to SIG_IGN and raises `Interrupted(BaseException)`. `run` prints
     `FAIL <drill> stopped by SIG...[ seed=N] (files kept in DIR)` and re-raises. `main` returns 1, and no other drill
     starts.
   - **The cleanup in `run`'s `finally` runs with STOPS blocked:** `d.end()` (SIGKILL and wait for every Popen of the
     drill), then `d.stub.stop()`, then removal of a passed drill's directory. Afterwards the earlier signal mask is put
     back. Only the script's own Popen objects are killed, never anything found by name.
   - **The temporary directory and `Drill(name, tmp, fast, rounds, seed)` are created inside the `try`.** A failure while
     building them prints a FAIL line, keeps and names the directory, and lets the next drill run.
   - **FAIL lines carry no exception text.** They carry a `Failed` text, which is built from the drill's own values
     (Ruling 54), or `type(e).__name__`, never an exception's text. Drill g's `git()` sends git's output to DEVNULL. Its
     FAIL says `git <args> in <dir>: exit N`, or `not within 30 s` when the call times out. Its thread records
     `round N: <Failed text or class>`.
   - **Drill e's seed.** The seed is `--seed N`, or chosen in `main` with `random.randrange(2**32)`. Drill e uses
     `random.Random(d.seed)`, and every FAIL line of drill e carries ` seed=N`.
   - **The look mark (drill a).** A stamp of the replacement's first look that is older than t0 is a FAIL.

## Changes over the parked patch (my reading of the patch against the brief)

- **`run`'s `finally` puts the earlier signal mask back.** It now calls `pthread_sigmask(SIG_SETMASK, mask)`, using the
  mask returned by the `SIG_BLOCK` call. The patch unblocked STOPS unconditionally. The new form is the same size and does
  not unblock a mask a caller had set, for example a direct `run()` call in a test process.
- **A git timeout in drill g now raises a `Failed` that names the call** (`git <args> in <dir>: not within 30 s`). Before,
  it reached `run` as the bare class `TimeoutExpired`. The brief says: "If a FAIL needs a detail to be readable ..., print
  that detail from the drill's own values". The old line had this detail only through the exception's text.
- **A `ponytail:` comment in `Drill.popen` names a known ceiling.** If the handler runs inside `subprocess.Popen`, after
  the fork and before the child is in `d.procs`, that one child is not killed. Blocking STOPS across the start is no fix:
  a blocked mask is inherited by the child. I checked this: a child started with SIGTERM and SIGHUP blocked shows
  `SigBlk: 0000000000004001`. The parents would then ignore `d.stop`'s SIGTERM. The upgrade is a flag the handler reads.
  This is the same kind of accepted ceiling as drill g's in-flight git call (Ruling 54).
- **The signal test passes `--seed 23`.** With this seed, drill e's first three engines live 3.70, 3.79 and 3.57 s, so
  the signal comes while the engine that beat is still running.
  - It also records that engine's pid and start time directly, instead of `assertIn(pid, descendants)`.
  - With random seeds, drill e's own kill could reap the engine between detection and the `/proc` snapshot. That would
    fail the test about 1% of the time, a flake by the "one in three" rule.
- **The `--seed` help line is wrapped** to keep the script within 120 columns, as it was before.

Everything else in the patch matched the brief and Ruling 54, and I kept it as it was.

## TDD evidence

### RED (first dispatch, stands; files in `<SCRATCH>/t14c/`)
- `red-uptime.txt`: `safe python3 -m unittest discover -s tests -p test_uptime.py -k test_one_outage_gives_one_line -k test_r11_counts_seconds -k test_days_below_one -v`
  gave `FAILED (failures=3)`. Each failure was expected:
  - `['R4c'] != ['R11']`: R4c went out beside the R4 that had told the outage, and the double count hid R11.
  - `[] != ['R11']`: 4 minutes against 4 minutes.
  - `(0, '2026-10-30  uptime 0.00% ...', 0) != (2, '', 1)`: `--days 0` became report_days.
- `red-supervise.txt`: the 4 new supervise and drill tests gave `FAILED (failures=4, errors=1)`. Each failure was
  expected:
  - `KeyError: 's'`.
  - `(-15, [5569], [5569]) != (1, [], [])` and `(-1, ...)`: the script died of the signal and its bare engine lived on.
  - The FAIL line carried the URL text.
  - `unrecognized arguments: --seed`.
- **Extra check, this dispatch, after my test change.** I removed the two lines that install the handlers from the
  applied script and ran the signal test. It failed as it should: `(-15, [21868], [21868]) != (1, [], [])` and
  `(-1, [21895], [21895]) != (1, [], [])`. The test's cleanup killed the leaked engines by their recorded pid. I then put
  the script back byte for byte (same sha256 `2f50353f...`). No engine process was left afterwards.

### GREEN (this dispatch, with the final code)
- `safe python3 -m unittest discover -s tests -p test_uptime.py`, 3 times in a row: `Ran 14 tests in 0.210s OK`,
  `0.242s OK`, `0.195s OK`.
- `safe python3 -m unittest discover -s tests -p test_supervise.py -k test_the_row_of_r4_carries_its_seconds -k test_a_drill_stopped_by_a_signal -k test_a_fail_line_names -k test_drill_e_takes_a_seed -v`:
  `Ran 4 tests in 6.798s OK`.
- `safe python3 -m unittest discover -s tests -p test_supervise.py`, 3 times in a row. This file holds the drill tests
  (class `Drills`) as well as item 2's test.
  - Results: `Ran 137 tests in 237.580s OK`, `236.550s OK`, `237.426s OK`.
  - The output of each run is only dots and the summary (`r2-supervise-{1,2,3}.txt`).

## Whole suite
`safe python3 -m unittest discover -s tests` from `ai-trader/`, wall 299 s (`r2-suite.txt`):
```
Ran 840 tests in 298.202s

OK
```
That is 833 tests at bf37c23d plus the 7 new ones (3 in test_uptime.py, 4 in test_supervise.py). The suite prints the
same `[news] ...` lines from older engine tests as the first dispatch's run did. My three files print nothing.

## Drill run
`safe python3 scripts/drill_supervisor.py all --fast --rounds 20`: rc 0, wall 181 s (`r2-drills.txt`):
```
PASS a kills=6+1 next_beat_max_s=0.46 engine_beat_s=0.46 engine_look_s=0.45 r1=6+1 tripped=0
PASS b replaced_s=9.1 limit_s=14 hang=1 killed_with=KILL r2=1 r1=0
PASS c restarts=5 tripped=1 r3=1 rc=75
PASS d engine_beat_s=0.61 old_tree_left=0 refused=0 r5c=0
PASS e rounds=20 trades=144 mismatches=0 e1=0 chains=ok
PASS f stale_start=1 stop_s=3.0 r6=1 hang=0 starts=1 watched_s=10
PASS g starts=50 rounds=20 rc0=50 rc7=0
```
Afterwards no `/tmp/drill-*` directory was left, and no engine_child, dummy_child or drill_supervisor process was running.
I checked with a read-only `ps` listing; nothing was killed.

## Files changed (all from the brief's list, added by name)
- `ai-trader/aitrader/uptime.py` (items 1, 2)
- `ai-trader/aitrader/supervise.py` (item 2 only: `s` in gap_line's fields and in the two alert rows' `extra`, plus two
  docstrings)
- `ai-trader/aitrader/__main__.py` (item 3 only)
- `ai-trader/scripts/drill_supervisor.py` (item 4)
- `ai-trader/tests/test_uptime.py`: 3 new tests
- `ai-trader/tests/test_supervise.py`:
  - `ParentLines.test_the_row_of_r4_carries_its_seconds`
  - `Drills.test_a_drill_stopped_by_a_signal_kills_every_child_it_started`, with SIGTERM and SIGHUP as subtests
  - `Drills.test_a_fail_line_names_the_exceptions_class_and_never_its_text`
  - `Drills.test_drill_e_takes_a_seed_and_says_it_when_it_fails`
  - 4 small /proc helpers

6 files changed, 312 insertions(+), 52 deletions(-).

## Self-review (`git diff bf37c23d..HEAD`)
- **Brief, line by line:**
  - Item 1: the rule and both test cases, plus a row with `sent` false still gives R4c.
  - Item 2:
    - `s` on both R4 and R4b alert rows.
    - The `m * 60` fallback.
    - R4c's seconds are added only when R4c is sent.
    - Ruling 54's threshold.
    - R11's {m} is unchanged.
    - All four of the brief's tests are present.
  - Item 3: 0 and -1 are tested.
  - Item 4: every bullet is covered, including the three tests, and the existing drill tests pass.
- **Edge cases:**
  - A late-success second alert row with the same id counts once (dict keyed by id).
  - A negative remainder (R4's `s` measured wider than the log) rounds to 0 or below and sends no R11.
  - R11's {m} is at least 1 whenever it fires.
  - `s` stays out of the owner's text: R4 and R4b have no `{s}`; R2's `{s}` is a separate field of another line.
- **Signals:**
  - A signal during a normal cleanup is held until the cleanup is done. It is then raised and ends the run with 1, and
    no further drill starts.
  - `cloud` and `cloud-check` install no handler.
- **Fixed during review:** the 5 changes listed above.
- **Trading rules:** no buy, sale or stop rule changes. No stop look is delayed or skipped. `config.json` is unchanged. No
  file the time machine loads is touched.

## Departures from the brief
- **Ruling 54's accepted departures, kept as built:**
  - A `Failed` keeps its message, which is built from the drill's own values.
  - There is a FAIL line for a drill stopped by a signal, with its kept directory and drill e's seed.
  - `run(..., seed=None)` for direct calls.
  - Drill g's in-flight git call is under a `ponytail:` comment.
  - The look-mark lower bound has no unit test of its own; drill a covers it.
- **Drill g's git timeout** is a `Failed` that names the call instead of the bare class (see above). This reads the
  brief's "detail from the drill's own values" sentence. It is not new scope.
- **The signal-window ceiling in `Drill.popen`** is documented with a `ponytail:` comment, not closed (see above). This is
  a narrow gap in "killed by any path".
- **The signal test reads every `/proc/<pid>/cmdline`** to assert that no process names the test's own `mkdtemp`
  directory. This catches an engine started after the snapshot. It is read-only: the test kills only pids it recorded as
  descendants of the drill script it started, and only when that pid still has the recorded start time and still names
  the directory.

## Concerns
- Task 20's hand-off should say that R11 now counts each R4 or R4b row's exact `s`, and that rows written before 14c count
  `m * 60` (Ruling 54).
- The suite's `[news] ...` output comes from older engine tests. It was there before this task and is unchanged.

## Fix round 1
Base 5640a80b (clean tree, branch supervisor-build). One new commit: `d8955a29 fix(ai-trader): a stop during a drill's
cleanup no longer cuts the cleanup short`. Files: `ai-trader/scripts/drill_supervisor.py`, `ai-trader/tests/test_supervise.py`
(both on the brief's list). Evidence files are in `<SCRATCH>/r14c-fix1/`.

### F1 (Important): fixed
The reviewer is right. The main thread's `pthread_sigmask(SIG_BLOCK, STOPS)` held nothing back while the NtfyStub's
`serve_forever` thread was alive. The new test reproduced it (RED, below): both children of a failed drill were still
running after a SIGTERM arrived during the cleanup.

I used the reviewer's flag form, not the retry form. A retry (`try: cleanup() except Interrupted: cleanup(); raise`)
still lets an Interrupted land at any point in pass 1. That includes the point inside `Popen._internal_poll` right after
`self._waitpid_lock.acquire(False)` returns and before its `try:`, which leaves the lock held. Pass 2's `p.wait()` would
then block forever on that lock. With the flag, nothing is raised inside the cleanup at all.
- `scripts/drill_supervisor.py:136`: a module flag, `hold: list[str] | None = None`.
- `scripts/drill_supervisor.py:139-148`: `interrupted` still sets SIG_IGN for both signals first. When `hold` is a list,
  it appends the signal's name and returns. Otherwise it raises `Interrupted` as before. Its docstring says why a mask
  would not do.
- `scripts/drill_supervisor.py:656`: `global hold` in `run`.
- `scripts/drill_supervisor.py:679`: the first statement of `run`'s `finally` is `hold = []`. I disassembled `run` on
  this Python (3.13). Before that `STORE_GLOBAL` there are only `BUILD_LIST`/`PUSH_EXC_INFO`, and the except clauses
  reach the finally by `JUMP_BACKWARD_NO_INTERRUPT`. None of these checks for signals, so no handler can run between
  entering the finally and the flag going up.
- `scripts/drill_supervisor.py:687`: in the inner `finally`, `noted, hold = hold, None`.
- `scripts/drill_supervisor.py:689`: `raise Interrupted(noted[0])` if a stop was noted. It reaches main, which returns 1,
  and no other drill starts.
- The mask (`SIG_BLOCK`/`SIG_SETMASK`) is removed. `run`'s docstring (:651-655) now says what is true: a stop that comes
  during the cleanup is only noted and is raised as Interrupted once the cleanup is done.
- An Interrupted that is already on its way (stopped in the drill body) runs the same cleanup. SIG_IGN is already set,
  so nothing is noted, and the original Interrupted carries on as before.
- The earlier claim under "Self-review", "Signals" ("a signal during a normal cleanup is held until the cleanup is
  done") now holds through the flag, not the mask.
- Not touched: the `ponytail:` window in `Drill.popen` (review Minor 1, not on the fix list). Its comment still names
  "a flag the handler reads" as the upgrade path, and that flag now exists.

New test: `tests/test_supervise.py:2154-2205`, `Drills.test_a_stop_while_a_failed_drill_cleans_up_cuts_nothing_short`,
with its script `STOP_IN_CLEANUP` at :2157.
- A subprocess loads the drill script by importlib and replaces drill c with a drill that does three things: puts a
  stand-in process first in `d.procs`, starts two real `sleep(120)` children through `d.popen`, and raises `Failed`.
- The stand-in's `poll()` sends `os.kill(os.getpid(), SIGTERM)` (process-directed, as from outside, while the stub's
  thread lives) and sleeps 0.5 s. The handler then runs in the main thread mid-`Drill.end`.
- It runs `main(["c", "d"])`, and drill d prints "second drill started".
- Assert: rc 1, two children printed, neither still running, "second drill started" absent (the noted stop ended the
  run after the cleanup), and exactly one FAIL line, `FAIL c two children started`.
- A pid counts as the child only while its argv still holds this test's own mkdtemp path, as an exact argv element (a
  guard against pid reuse). The test's cleanup SIGKILLs only such pids.

### TDD
RED. The new test against 5640a80b's `drill_supervisor.py` (HEAD's file written in temporarily with `git show`, then my
file put back and checked with `cmp`):
`safe python3 -m unittest discover -s tests -p test_supervise.py -k test_a_stop_while_a_failed_drill_cleans_up_cuts_nothing_short`
```
AssertionError: Tuples differ: (1, 2, [2566, 2567], False, ['FAIL c two children started']) != (1, 2, [], False, ['FAIL c two children started'])
Ran 1 test in 0.636s
FAILED (failures=1)
```
The two children were left alive. The test's cleanup killed them; a `ps -p 2566,2567` afterwards printed nothing.

GREEN (same command, the fix in place):
```
Ran 1 test in 0.651s
OK
```

### Covering tests, 3 times in a row (the file starts processes; it holds every drill test)
`cd ai-trader && safe python3 -m unittest discover -s tests -p 'test_supervise.py'` (`supervise-3x.txt`):
```
Ran 138 tests in 244.301s  OK  run 1: 245 s
Ran 138 tests in 239.521s  OK  run 2: 240 s
Ran 138 tests in 237.564s  OK  run 3: 238 s
```

### Whole suite
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`
(`suite.txt`), wall 304 s. Last three lines:
```
Ran 841 tests in 303.408s

OK
```
That is 840 plus the one new test.

### Drill run (extra, because `run` changed)
`safe python3 scripts/drill_supervisor.py all --fast --rounds 20`: rc 0, wall 173 s (`drills.txt`).
- Output: seven PASS lines (a-g).
- Afterwards there was no `/tmp/drill-*` directory and no engine_child, dummy_child or drill_supervisor process. I checked
  with a read-only `ps`.

### Remaining limit (not part of F1; nothing changed for it)
- An Interrupted raised in a drill's body still lands wherever the body is. That is the design the brief asks for: the
  handler ends the running drill.
- If it lands in the same one-instruction window of `Popen._internal_poll` described above, inside the body's own
  `poll()`, the cleanup's `p.wait()` on that one process could block.
- The flag cannot help with this: it covers the cleanup, not the drill body. Fixing it would mean a handler that never
  raises, which is a redesign of item 4. Nothing was changed for it.
