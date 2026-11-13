# Task 14c report: BLOCKED on one contradiction in item 2 (R11's threshold)

Nothing is committed. The gate clone is clean at `81bd1283556b37cc8055e2dfff766278c919415b` on `supervisor-build`.
All four items are built and tested in a parked patch, waiting for one ruling:

- Parked patch: `<SCRATCH>/t14c/task-14c-parked.patch`
  (547 lines, sha256 `ca48a2c7c03859f1fc860c6dfdee0eb15427baa4cc6b4d0b5baf420c4ef17d79`). `git apply --check` passes on
  81bd128. Apply it from the clone root with `git apply <patch>`.
- Evidence in the same folder: `red-uptime.txt`, `red-supervise.txt` (RED), `literal-60-uptime.txt` (the brief's rule
  as written), `green-supervise-{1,2,3}.txt`, `suite.txt`, `drills.txt`.

## The contradiction (the question for the controller)

Item 2 of the brief gives a rule and a test, and they do not agree:

- Rule: "sends R11 when the day had a trip or when `unprotected_s` minus the reported seconds is 60 or more."
- Test: "the 40 s + 210 s case gives R11."

In the 40 s + 210 s case, 250 - 210 = 40, and 40 is less than 60. Under the rule as written that day gets no R11, which
is the same result the old code gave ("4 against 4 and disappears"). So the rule as written does not fix the case the
brief gives as the reason for the change. Ruling 50 also says the change is made "so a short unreported stretch next to
a reported one is not lost to rounding". The dispatch says "R11 no longer loses a short unreported stretch to rounding".

The rule as written also breaks an existing test the brief does not mention. In `tests/test_uptime.py`,
`test_the_days_counts_and_r9` expects R11 for a day whose only outage is a 40 s restart that no line told (its comment
says "40 s: one minute untold"). Under the rule as written it gets no R11.

I measured this. With the patch's code and the threshold written as `unprotected_s - reported >= 60`
(`literal-60-uptime.txt`), `test_uptime.py` gives `FAILED (failures=2)`:
- `test_r11_counts_seconds_so_40_untold_seconds_beside_210_told_ones_are_not_lost`: `[] != ['R11']`
- `test_the_days_counts_and_r9`: `['R9'] != ['R9', 'R11']`

The controller notes say to stop with BLOCKED when a test cannot pass as written because the plan contradicts itself.

### The readings, and what each one does
- A. The rule as written: R11 when `unprotected_s - reported >= 60`. R11's {m} is always at least 1, and up to 59 s of
  difference between how R4 measures an outage and how the uptime log measures it is absorbed. But the brief's own
  40 + 210 test fails (it would need other numbers, for example 70 + 210), and `test_the_days_counts_and_r9` must change
  to `["R9"]` and then `[]`. A lone 40 s restart then gets no R11 (today it does, saying 1 minute).
- B. What the parked patch builds: R11 when `round((unprotected_s - reported) / 60) >= 1`. That is the untold remainder
  rounded once, so it fires above 30 s. Every test in the brief passes and every existing test passes unchanged. R11's
  {m} = round(unprotected_s / 60) is at least 1 whenever it fires, because unprotected_s is at least the remainder. This
  reading matches Ruling 50's "not lost to rounding": the rounding now happens once, on the remainder, not once per
  line. The only number in it is the minute, R11's unit. Up to 30 s of measurement difference is absorbed, against A's
  59 s.
- C. R11 whenever anything at all is untold (`> 0`). The tests pass, but a 20 s restart would send R11 saying "0 דקות",
  and a few seconds of difference between R4's `s` (from the row before the outage to the `up`) and the uptime log's
  stretches (mark to mark) could trigger R11 on a day that was fully told.

I recommend B. To build A instead, change the one condition in `uptime.close_lines` and the two test expectations named
above. A also needs new numbers for the brief's 40 + 210 test, or an explicit ruling that that test is dropped.

Everything else in the brief is clear and is built as written. The rest of this report describes the parked patch.

## What the parked patch implements

1. `aitrader/uptime.py`, `close_lines`. One outage gives one line. R4c is not sent, and adds nothing to `reported`,
   when a day's alert row of kind R4 or R4b with `sent` true has a `t` at or after the start of the trailing outage
   (`began`, the time R4c would print).
2. Item 2:
   - `aitrader/supervise.py`: `gap_line` puts `"s": s` (the exact `open_seconds` value, a float) into its fields beside
     `m`. Both `say` call sites (the first `up`'s R4/R4b, and the pause R4 of Ruling 49) pass
     `extra={"m": ..., "s": ...}`. `s` reaches `ownerlines.render` the way `m` does, but no template names `{s}`, so the
     owner's text does not change. Both docstrings are updated.
   - `close_lines` sums the told rows' `s` per id, counted once. A row without a numeric `s` counts `m * 60`, and a row
     with neither counts nothing, as before. R4c adds its own `run` seconds when it is sent. R11's {m} stays
     round(unprotected_s / 60). The threshold is reading B (see above). The docstring is rewritten.
3. `aitrader/__main__.py`: `uptime-report --days N` with N < 1 prints one line,
   `uptime-report: --days takes 1 or more, not N`, to stderr and returns 2.
4. `scripts/drill_supervisor.py`:
   - SIGTERM and SIGHUP are handled. `STOPS = {SIGTERM, SIGHUP}`. In drill mode, `main` installs `interrupted`, which
     sets both signals to SIG_IGN (so a second signal cannot cut the cleanup short) and raises
     `Interrupted(BaseException)`, which the drills' `except Exception` lets through. `run` prints
     `FAIL <drill> stopped by SIGTERM|SIGHUP[ seed=N] (files kept in DIR)` and re-raises. `main` catches it and returns
     1, and no later drill starts.
   - In `run`, the `finally` blocks STOPS (`pthread_sigmask`) while it runs `d.end()` (SIGKILL and wait for every Popen
     the drill started: parents, whose stub children die with them by PR_SET_PDEATHSIG, and the bare engines of e and
     g), then `d.stub.stop()` and the removal of a passed drill's directory. It unblocks afterwards, so a signal that
     arrives during a normal cleanup is handled only once the cleanup is done. Nothing is killed by name. Only the
     script's own Popen objects are killed.
   - `run` makes the temporary directory itself and builds `Drill(name, tmp, fast, rounds, seed)` inside the `try`. A
     failure while building it (for example the NtfyStub) prints a FAIL line, keeps and names the directory (the
     existing rule for a failed drill), and returns False, so the next drill runs.
   - FAIL lines show a `Failed` pass mark (the drill's own words) or `type(e).__name__` for any other exception, never
     the exception's text. Drill g's `git()` no longer captures or prints git's output: its FAIL says
     `git <args> in <dir>: exit N`. Its thread records `round N: <Failed text or class>`.
   - Drill e's seed comes from `--seed N`, or is chosen at the start (`random.randrange(2**32)`). Drill e uses
     `random.Random(d.seed)`, and every FAIL line of drill e carries ` seed=N`.
   - The look mark: if any stamp of the replacement's first look is older than t0 (the kill), drill a fails
     (`a stamp of the replacement's first look is X s older than the kill`). It no longer passes with a negative time.
   - The docstring and usage line are updated.

## TDD evidence

### RED (before any production change; files saved as `red-uptime.txt` and `red-supervise.txt`)
`safe python3 -m unittest discover -s tests -p test_uptime.py -k test_one_outage_gives_one_line -k test_r11_counts_seconds -k test_days_below_one -v`
gave `Ran 3 tests ... FAILED (failures=3)`:
- `test_one_outage_gives_one_line_no_r4c_after_the_r4_that_told_it`: `['R4c'] != ['R11']`. This was expected: R4c went
  out beside the R4 that told the outage, and the double count (20 + 20 against 25) hid R11.
- `test_r11_counts_seconds_so_40_untold_seconds_beside_210_told_ones_are_not_lost`: `[] != ['R11']`. Expected: 4
  against 4 minutes.
- `test_days_below_one_are_refused`: `(0, '2026-10-30  uptime 0.00% ...', 0) != (2, '', 1)`. Expected: `--days 0`
  became report_days (14 days of pages) with exit 0.

`safe python3 -m unittest discover -s tests -p test_supervise.py -k test_the_row_of_r4_carries_its_seconds -k test_a_drill_stopped_by_a_signal -k test_a_fail_line_names -k test_drill_e_takes_a_seed -v`
gave `Ran 4 tests in 5.096s FAILED (failures=4, errors=1)`:
- `test_the_row_of_r4_carries_its_seconds`: `KeyError: 's'` (the row had no `s`).
- `test_a_drill_stopped_by_a_signal_kills_every_child_it_started`, SIGTERM: `(-15, [5569], [5569]) != (1, [], [])`.
  SIGHUP: `(-1, [5597], [5597]) != (1, [], [])`. The script died of the signal and its bare engine child lived on: the
  defect named in Ruling 50.
- `test_a_fail_line_names_the_exceptions_class_and_never_its_text`: the line was
  `FAIL c OSError: https://ntfy.example/t0p1c-under-test (files kept in /tmp/drill-c-...)`, which carries the text.
- `test_drill_e_takes_a_seed_and_says_it_when_it_fails`: `(2, False) != (1, True)`, from
  `error: unrecognized arguments: --seed 12345`.

### GREEN (with the patch applied)
- The four supervise/drill tests: `Ran 4 tests in 6.711s OK`.
- `safe python3 -m unittest discover -s tests -p test_uptime.py`, run 3 times in a row:
  `Ran 14 tests in 0.347s OK`, `0.409s OK`, `0.335s OK`.
- `safe python3 -m unittest discover -s tests -p test_supervise.py` (this file also holds the drill tests), run 3
  times: `Ran 137 tests in 239.740s OK`, `234.502s OK`, `237.259s OK`. The output is only dots. The third run was
  first stopped by my own background-command time limit (600 s, set too short for two runs in one command) and then
  run again whole. A check found no process or `drill-*` directory left by the stopped run.

## Whole suite (with the patch applied)
`safe python3 -m unittest discover -s tests`, wall 319 s:
```
Ran 838 tests in 318.905s

OK
```

## By-hand drill run (with the patch applied)
`safe python3 scripts/drill_supervisor.py all --fast --rounds 20`: rc 0, wall 180 s.
```
PASS a kills=6+1 next_beat_max_s=0.42 engine_beat_s=0.42 engine_look_s=0.42 r1=6+1 tripped=0
PASS b replaced_s=9.1 limit_s=14 hang=1 killed_with=KILL r2=1 r1=0
PASS c restarts=5 tripped=1 r3=1 rc=75
PASS d engine_beat_s=0.56 old_tree_left=0 refused=0 r5c=0
PASS e rounds=20 trades=118 mismatches=0 e1=0 chains=ok
PASS f stale_start=1 stop_s=3.0 r6=1 hang=0 starts=1 watched_s=10
PASS g starts=50 rounds=20 rc0=50 rc7=0
```
Afterwards no `engine_child`, `dummy_child` or `drill_supervisor` process was running and no `/tmp/drill-*` directory
was left.

## Files in the parked patch (all from the brief's list)
- `ai-trader/aitrader/uptime.py` (items 1, 2)
- `ai-trader/aitrader/supervise.py` (item 2 only: `s` in gap_line's fields and in the two alert rows' `extra`)
- `ai-trader/aitrader/__main__.py` (item 3 only)
- `ai-trader/scripts/drill_supervisor.py` (item 4)
- `ai-trader/tests/test_uptime.py`: 3 new tests (items 1, 2, 3)
- `ai-trader/tests/test_supervise.py`: 1 new ParentLines test (item 2), and 3 new Drills tests plus 4 small helpers
  (item 4). The drill tests are in this file, class `Drills`.

When ruled, the commit is `git add` of those six paths, with the brief's message.

## The new tests
- `test_uptime.py`:
  - `test_one_outage_gives_one_line_no_r4c_after_the_r4_that_told_it`. The trailing outage runs from 15:40 New York.
    The R4 row (sent true, `m` 20, no `s`) is at 16:10. There are also 5 untold minutes at 10:00. Result: `["R11"]`
    saying 25 minutes. With no R4 row, or with the R4 row `sent` false, the result is `["R4c", "R11"]` and R4c says
    "מ-22:40 ... 20 דקות". The 5 untold minutes make "once" visible: a double count (40 against 25) would hide R11.
  - `test_r11_counts_seconds_so_40_untold_seconds_beside_210_told_ones_are_not_lost`. The 40 + 210 case gives R11
    with {m} 4. A fully reported day (the 210 s gap told with `s` 210) gives `[]`. A row with only `m` 4 still counts
    (`[]`), and without it the result is `["R11"]`.
  - `test_days_below_one_are_refused`, for 0 and -1: return 2, empty stdout, one stderr line naming the value.
- `test_supervise.py`:
  - `ParentLines.test_the_row_of_r4_carries_its_seconds`. The parent runs on a whole-second clock, so the `up` row's
    `t` is exactly the moment gap_line measured to. The test checks the R4 row's `s == open_seconds(prev.t, up.t)`,
    `m == round(s / 60)`, that `s` is numeric, and that `s` does not appear in the text.
  - `Drills.test_a_drill_stopped_by_a_signal_kills_every_child_it_started`, as subtests for SIGTERM and SIGHUP. The
    test runs drill e (`--fast --rounds 500`) with TMPDIR set to the test's own directory. It reads the bare engine's
    pid from its heartbeat in the drill's directory and requires it to be a live child of the drill script. It
    records every descendant of the drill script (found by parent pid in /proc, together with each start time, so a
    reused pid is not taken for the same process). Then it signals only the drill script. It asserts rc 1, that no
    recorded process is alive, that no process names the test's directory, and that a `FAIL e stopped by SIG...` line
    was printed. Its cleanup kills only a recorded pid that is still the same process (same start time) and whose
    command line names the test's directory.
  - `Drills.test_a_fail_line_names_the_exceptions_class_and_never_its_text`. Two cases: a drill that raises
    `OSError(<URL with a made-up topic>)`, and a NtfyStub that raises `ConnectionError` while Drill is built. Each
    gives one line `FAIL c <Class> (files kept in DIR)`, without the text, with the directory present, and `run`
    returns False.
  - `Drills.test_drill_e_takes_a_seed_and_says_it_when_it_fails`. `e --fast --rounds 0` fails at once (no trade). With
    `--seed 12345` its FAIL line carries `seed=12345`. Without it, the line carries a chosen seed.

## Self-review findings and what I did
- I found a closure bug in my own signal test during RED. The cleanup function closed over the loop variables, so both
  subtests' cleanups acted on the SIGHUP run, and the SIGTERM run's leaked engine (pid 5569) stayed alive after the RED
  run. I killed that one pid by hand, after checking that its command line named my test's own temporary directory
  (`/tmp/tmpwlpowztf/drill-e-...`). Nothing was killed by name pattern. I removed that directory and fixed the test (it
  now binds `p`, `started` and `tmp` as default arguments). No leak was seen in any later run.
- I replaced a tuple-assignment trick in the `descendants` helper with plain statements.
- I put `Drill.__init__`'s attribute order back as it was, to keep the diff small.
- One line in `supervise.py` went over the width after the edit and was wrapped.
- Checked: a passing drill still removes its directory, a failed one keeps and names it, the existing drill tests
  still pass, the seven PASS lines have the same shape, and `cloud` and `cloud-check` are not affected (the handlers
  are installed in drill mode only).

## Departures from the brief, and readings that should be confirmed
1. R11's threshold: reading B instead of the brief's literal "60 or more". This is the reason for BLOCKED (see above).
2. "FAIL lines print the exception's class name ..., never the exception's text": I read this as covering every
   exception that is not `Failed`. A `Failed` keeps its message, because that message is the pass mark stated from the
   drill's own values (which round, which name, which limit). That is what the brief's next sentence asks for, and
   `test_the_fast_drills_pass` relies on it to be readable. The places where outside text got into a `Failed` (git's
   stderr in drill g, the thread's `type: text`) are removed. If the controller wants `Failed` lines reduced to the
   class too, `run` changes in one line.
3. Additions the brief does not name: a FAIL line for the drill that a signal stopped (`stopped by SIGTERM`), which
   carries the kept directory and drill e's seed; and `run(..., seed=None)` defaults the seed so a direct call (the
   test) can omit it. `main` always passes one.
4. Not built: drill g's background thread does not track its in-flight `git` call. If the drill is stopped, that call
   (on local repositories) ends by itself within moments. A `ponytail:` comment names this ceiling and the upgrade
   (a Popen in `Drill.procs`). The brief's list (parents, bare engines, stubs) is fully covered.
5. The look-mark check has no unit test of its own (the brief's test list does not ask for one). Drill a still passes
   in `test_the_fast_drills_pass` and in the by-hand run.

## Concerns
1. Process breach: one `python3 -` with an empty heredoc ran outside the safe wrapper while I was editing the test
   file. It executed nothing (empty input, no import, no network). Every other python command, including the RED,
   GREEN, suite and drill runs, went through `safe`.
2. The leaked RED engine described above lived about a minute, polling stubs on `/tmp` behind its tripwire with no
   network. I killed it by its recorded pid.
3. Whichever R11 reading is ruled, Task 20's hand-off should know that R11 now counts each R4 or R4b row's exact
   seconds. Rows written before this patch count `m * 60`.
