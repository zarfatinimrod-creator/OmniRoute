# Task 11 report - the restart core and the parent's loop

Gate clone `<SCRATCH>/clones/sup`, branch
`supervisor-build`. Found HEAD `55756d5b5d8fcd7184cd7f22438f4884b1374c40`, branch `supervisor-build`, clean tree (all
three checks ran before anything else). Final HEAD `62fc1622fbd22fa4f5e214140f49269df3056991`.

Commit: `62fc1622` feat(ai-trader): the supervisor parent starts the engine, restarts it by its exit code and gives up
after a crash loop. Paths: `ai-trader/aitrader/supervise.py`, `ai-trader/tests/test_supervise.py`, exactly the brief's.
The message has no attribution line of any kind. After the commit `git status --short` printed nothing. No
`git stash` in any form; no push, fetch, merge, rebase, reset or branch command. Every python command ran through the
`safe` wrapper (the mutation runner too). `_tasks` was not touched.

## What I implemented

`aitrader/supervise.py` (standard library only; new imports `argparse`, `re`, `signal`, `subprocess`, `sys`,
`threading`, `time`, `zoneinfo`):

- `restart_core(spawn, watch, stop, near_until, emit, pol, counts, *, mono=time.monotonic, sleep=time.sleep) ->
  tuple[int, str]`. No network, no file, no wall clock. It plays the brief's table:
  - 0 with `near_until()`: `(0, "end_of_day")`. 4, 5, 6: `(code, "halt")`, no restart.
  - 3: started again after the back-off, not counted, for `lock_wait_seconds` from the first refusal; then
    `(3, "lock_held")`.
  - Every other end is a crash: a code, a signal, a 0 far from `--until`, a 7 (the `exit` row says "tree_busy"), and a
    143 nobody asked for. The core starts the child again at once after a run of `healthy_seconds` or more. Otherwise
    it waits `backoff_first_seconds` and doubles the wait each time, up to `backoff_max_seconds`. The doubling starts
    again after a healthy run.
  - When one more restart would pass `max_restarts` in `restart_window_seconds`, or `max_restarts_day`: a `tripped`
    row and `(75, "crash_loop")`.
  - When `watch` says "hang": `stop(child, "hang")`, then a crash (`why` "hang").
  - When `watch` says "handover", "signal" or "orphaned": `stop(child, "planned")` (`why` "planned"), then `(76,
    "handover")` or `(143, word)`. During a wait the core gives the same answer at once and starts nothing.
  - `watch(None, 0.0)` is asked at least once before every start (also when the wait is 0) and every `loop_seconds`
    during a wait. While a child runs it is asked after each `poll()`, every `loop_seconds`.
  - Rows: `start` {`child`, `n`, `backoff_s`}, `exit` {`child`, `rc`, `signal`, `ran_s`, `why`}, `tripped`
    {`restarts`, `window_s`}.
- `near_until(now_ny, until, slack_s) -> bool`: `now_ny >= today's until - slack_s`, one-sided. It compares wall-clock
  times in New York. "24:00" is the midnight that ends the day.
- `main(argv=None, *, child_cmd=None, env=None, clock=None, sleep=None) -> int`, and `if __name__ == "__main__"`.
  - Command line: `--until HH:MM` (required; 00:00-23:59 or 24:00), `--handover`, `--state-dir DIR` (state in DIR,
    logs in DIR/.cache), `--config FILE`. It returns 2 for a bad argument or config: one that cannot be read, has no
    `supervisor`/`calendar` block, or has a non-number among the twelve supervisor keys main and the core read.
  - It reads `os.getppid()` first. It prints the first stdout line, creates the state and cache directories (ruling 30),
    and takes `news_supervisor.lock`. When another parent holds the lock it prints `supervise: 3 lock_held pid <holder>.
    Run ...`, writes nothing and returns 3.
  - It opens `.cache/supervise.log`. On the main thread only, it installs handlers for SIGTERM, SIGINT and SIGHUP; a
    handler only notes the signal. A `finally` puts the handlers back (SIG_DFL for one not set from Python), closes the
    log and frees the lock.
  - `load_state` for the New York day. A `load_error` is written to the log by class name and popped before any save
    (P18(c)).
  - `prune_rows` with `uptime_keep_days`, then `sup_start` {`until`, `handover`, `timeout_ms` (7,200,000 with
    `--handover`, else `long_timeout_ms`), `prev_t`, `prev_ev`, `gap_s`, `cold`}. A failure to read or write the log
    is logged and the parent goes on (ruling 30, spec 4.6). `emit` guards `append_row`.
  - A day with no session: `sup_stop` "closed_today", rc 0, no child.
  - Otherwise it runs the core with:
    - `spawn`: `child_cmd + ["--until", until, "--supervised", pid]` (default `[sys.executable, "-u", "-m", "aitrader",
      "news-live"]`). The child starts from the calling (main) thread with `start_new_session=True`, `cwd` = ai-trader,
      `env`, stdin from /dev/null, and stdout+stderr appended to `.cache/news_live.log`.
    - `watch`: "signal" once a handler has fired, "orphaned" when `os.getppid()` changed.
    - `stop`: SIGTERM to the child's pid alone (`Popen.send_signal`, so nothing is sent to a child already reaped),
      then `planned_stop_grace_seconds`, then SIGKILL to its process group. The SIGKILL is logged.
    - `near_until` on the injected clock in New York.
    - A `tripped` row also carries `trips_today` (the state file's count plus one).
  - Then `sup_stop` {`why`, `rc`} and the state file (`restarts_today`, `trips_today`, and `halt` = {`code`, `why`,
    `at`} on 4, 5, 6).
  - The last stdout line is `supervise: <rc> <word>. Run python3 -m aitrader.supervise --status and do what action
    says.`. The words are end_of_day, closed_today, handover, tripped (for `crash_loop`), halt, `lock_held pid
    <engine-lock holder>`, signal and orphaned. Everything else goes to `.cache/supervise.log`.
- Ruling 30, in this file:
  - `prune_rows` raises `ValueError` on a naive `now`.
  - The module docstring now says "So far (Tasks 10-11)" and gives the command line.

`tests/test_supervise.py`:
- `NY` constant.
- `RestartCore`: `core(children, near_until=False, counts=None, orders=None, **pol)` over fake children on a fake
  clock (`{**SPEC, **pol}`, the spec's defaults, so a tuned config does not move it); `self.backoffs`, `self.counts`,
  `self.clock`, `self.emitted(ev)`.
- `Parents(Procs)`:
  - The config copy: `loop_seconds` 0.05, `backoff_first_seconds` 0.05, `healthy_seconds` 1, and the five switches
    pinned false (P29).
  - `run_parent(script, *argv, clock=None)`: in-process, with stdout captured in `self.out`.
  - `spawn_parent(script, *argv, child_cmd=None, **sup)`: `PARENT_WRAPPER` in a `python3 -c` process.
  - `urows(ev=None)` and `state_file()`.
  - The default clock is the real one moved to 10:00 New York on Thursday 2026-11-12.
  - `--until 24:00` is added when a test names no end (P1 / Ruling 16).
  - Helpers: `dummy_cmd`, `engine_cmd`, `parent_argv`, `parent_cmd`, `sup_log`, `files`, `kill_ours`.
- `ParentLoop`.
- Module-level: `PARENT_WRAPPER`, `HELPER`, `GROUP_CHILD`, `saturday()`, `flockable()`.
- Ruling 30 in `Foundations`: `test_notify_posts_to_the_configured_address` sets `market.quiet_hours` to None in its
  config copy, plus one new test.

## Tests

The brief's 16, each under its name with the brief's assertion, and the stand-ins its comments describe written in:

RestartCore (6): `test_five_quick_crashes_back_off_1_2_4_8_16_and_the_sixth_trips`,
`test_a_child_that_ran_60_s_is_restarted_at_once`, `test_the_day_limit_trips_with_a_clear_window`,
`test_the_code_table`, `test_near_until_is_one_sided`, `test_a_stop_order_during_a_back_off_ends_it_without_a_start`.

ParentLoop (10):
- `test_a_killed_child_beats_again_within_1_s`
- `test_a_child_that_always_fails_ends_with_75_after_5_restarts`
- `test_a_day_with_no_session_starts_no_child`
- `test_a_second_parent_returns_3_names_the_holder_and_writes_nothing`: every file under `state/` stays byte for byte,
  apart from the heartbeat the first parent's child rewrites. This covers `uptime.jsonl`.
- `test_sigterm_stops_the_child_and_the_parent_ends_with_143`: the test signals after the child's first beat (ruling 30).
- `test_a_second_sigterm_while_the_child_is_finishing_changes_nothing`: `ignore_term`, `planned_stop_grace_seconds` 1,
  and the second SIGTERM 0.3 s after the first.
- `test_a_parent_that_loses_its_own_parent_stops_with_orphaned`: through `HELPER`.
- `test_kill_9_of_the_parent_leaves_no_child_and_both_locks_free`: `engine_child.py` as the child, so that
  `news_engine.lock` is really held. The child is gone within 1 s, then both locks can be flocked within the same
  second; the reason for that second is the EngineStop note about numpy threads.
- `test_a_child_that_ends_with_0_at_until_or_minutes_after_it_is_the_end_of_the_day`: `--until 10:00` and `09:55`,
  each on a fresh state directory, in a `subTest`.
- `test_a_child_that_ends_with_0_two_minutes_before_until_is_restarted`: `--until 10:02`. SIGTERM goes once the second
  start is on record and its child beats.

Tests added by ruling:
- `ParentLoop.test_a_state_file_that_does_not_parse_is_named_in_the_log_and_saved_whole` (P18(c)): a torn state file.
  The log names `JSONDecodeError` exactly once, and the saved state file has no `load_error`.
- `Foundations.test_prune_rows_refuses_a_time_without_a_zone` (ruling 30).
- `ParentLoop.test_an_uptime_log_that_cannot_be_written_does_not_stop_the_parent` (ruling 30, spec 4.6): `uptime.jsonl`
  is a directory. The parent still ends `0 end_of_day`, writes its state file, and its log names `IsADirectoryError`.
- `ParentLoop.test_a_state_directory_that_does_not_exist_yet_is_made` (ruling 30).

Test added from my mutation pass (a behaviour the brief specifies that no named test checked):
- `ParentLoop.test_a_planned_stop_signals_the_child_alone_and_not_its_group`. The child (`GROUP_CHILD`) starts `sleep
  60` in its own process group. After the parent's planned stop, the parent returns 143, the `exit` row says
  `(143, "planned")`, and the `sleep` is still alive. With SIGTERM sent to the group instead, the test fails.

### RED

Commands (from `ai-trader/`, through the safe wrapper):
`... safe python3 -m unittest discover -s tests -p test_supervise.py -k RestartCore`

```
AttributeError: module 'aitrader.supervise' has no attribute 'restart_core'
Ran 6 tests in 0.004s
FAILED (errors=6)
```

`... -k ParentLoop` (13 tests at that point; summarised by `sort | uniq -c`):

```
      7 AttributeError: module 'aitrader.supervise' has no attribute 'main'
      4 AssertionError: not within 5 s: beat; engines that ended: ['exit 1: Traceback ... AttributeError: module 'aitrader.supervise' has no attribute 'main'\n']
      1 AssertionError: not within 20 s: <lambda>; engines that ended: [... no attribute 'main' ...]
      1 AssertionError: not within 5 s: beat; engines that ended: []      (the orphan test: its helper was still alive)
      1 FAILED (failures=7, errors=7)
      1 Ran 13 tests in 50.105s
```

`... -k test_prune_rows_refuses`: `AssertionError: ValueError not raised`, `FAILED (failures=1)`.

These failures were expected: the brief names `AttributeError: module 'aitrader.supervise' has no attribute
'restart_core'`, and `main` did not exist either. The spawned parents died on that `AttributeError`, so the tests
waiting for a beat timed out naming it. `prune_rows` did not yet refuse a naive time.

### GREEN

`... -k RestartCore -k ParentLoop -v`: all 20 `ok`, `Ran 20 tests in 4.695s`, `OK`.
Whole file (`-p test_supervise.py`, it starts processes), six runs in a row on the final code: 51 tests OK each time
(42.7 s, 41.3 s, 40.4 s, then three more `OK`). Output pristine: a dot line and the summary only, no warnings.

### Mutation pass (scratch copy outside the clone, removed afterwards; safe wrapper)

Killed, against the tests listed:
- RestartCore:
  - a two-sided `near_until`
  - no doubling
  - a 143 taken as a halt
  - lock refusals counted
  - no `watch` in the wait
  - no day limit
  - `>` for `>=` on `max_restarts`
  - a 0 always taken as the end of the day
- ParentLoop:
  - no orphan check
  - no SIGKILL after the grace
  - no `start_new_session`: `killpg` misses and the stop hangs
  - `load_error` kept
  - `emit` unguarded
  - closed days not detected: the in-process parent never returns, killed by the runner's timeout
  - a wrong `timeout_ms`
  - no holder pid
  - `trips_today` wrong
  - no signal handler
  - `restarts` wrong
Three survived the first pass:
1. No reset of the doubling after a healthy run.
2. The last lock retry not placed at the end of `lock_wait_seconds`.
3. SIGTERM to the group instead of the pid.

I added one assertion each for (1) and (2) and the test above for (3); all three are killed now. One survivor is
equivalent and was left as it is: dropping `state_dir.mkdir` changes nothing under `--state-dir`, because
`cache_dir = state_dir/.cache` is made with `parents=True`. The default layout (`ROOT/state` beside `ROOT/.cache`)
needs both calls.

### The hour (ruling P1 / the 11:10 ruling)

The runs above were made at about 19:12 New York (EST), after 16:05. The hour cannot change these tests:
- The dummy child takes `--until` and never acts on it.
- The one engine child (the kill-9 test) gets `--until 24:00`, and `(now.hour, now.minute) >= (24, 0)` is never true in
  `news_live._run`.
- The parent's calendar questions read the moved clock: 10:00 New York on 2026-11-12, or the fixed Saturday.

## Whole suite

`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` from
`ai-trader/`, on the final code just before the commit (wall 116 s):

```
Ran 737 tests in 115.694s

OK
```

737 = 716 at the found HEAD (Task 9d's independent run) + 21 new. An earlier run, made before the last refactors, also
ended `Ran 737 tests in 106.342s` / `OK`. The `[news] ...` lines in the suite's output come from the engine's test
modules and are not new; none of this task's tests prints anything.

## Files changed

- `ai-trader/aitrader/supervise.py` (+272, -2; 448 lines)
- `ai-trader/tests/test_supervise.py` (+347)

## Self-review (`git diff 55756d5b..HEAD`)

I went through the brief line by line against the diff; every interface, row, field, stdout line and return code is
there. Found and fixed:
- Two lines over 120 characters in `supervise.py` (the file had none). One is reworded; the other became a named inner
  function `at_until()`.
- The log file is opened before the handlers are installed, so a failing `open` cannot leave the test process's
  handlers replaced.
- `run_parent` had `child_cmd` and `**sup` keywords that no test used. I removed them, since Task 13 adds the config
  keywords itself.
- The three mutation survivors above.
- An inline `import os` inside `GROUP_CHILD` was moved up. `GROUP_CHILD` gets its own clean-up, because it does not die
  with its parent.

Checked and left:
- A SIGTERM during the grace wait does not break `Popen.wait` (PEP 475); the second-SIGTERM test covers it.
- `send_signal` sends nothing to a child already reaped. `killpg` runs only while the child is unreaped, so the group
  id is still the child's.
- The second parent creates directories that already exist and writes no file.

## Departures from the brief, and readings where it is silent

1. Tests: 21 new, where the brief has 16: the 4 by ruling and the 1 from the mutation pass, named above.
2. Assertions added to named tests. The brief's own assertion is kept in each.
   - The 75 test also checks the state file (5, 1) and the two stdout lines verbatim.
   - The no-session test checks:
     - no heartbeat file;
     - the `sup_start` fields of a first parent (until "24:00", handover false, `timeout_ms` 32,400,000, prev null,
       gap null, cold true);
     - those of a second parent with `--handover` (7,200,000, `prev_ev` "sup_stop", `gap_s` 0).
   - The second-parent test checks every state file, not only `uptime.jsonl`.
   - The second-SIGTERM test checks that the exit row is `(None, 9, "planned")` and that the log names SIGKILL.
   - The 10:02 test asserts the parent's 143.
   - The 60 s test also checks the doubling reset: `[1, 0, 1]`.
   - The code table asserts `clock < 152`: the last lock try is at the end of the 150 s, not a 60 s back-off later.
3. The orphan stand-in. The brief's comment says "a helper process that exits at once". My helper exits when the test
   closes its stdin, right after the parent's first child beat. If the helper exited before `main` read
   `os.getppid()`, the parent would be born orphaned, see no change and never stop. That is a race, so the test would
   be flaky.
4. Ruling 30, the dummy's early SIGTERM: I took the second option it allows. The tests wait for the child's first
   beat before signalling. `tests/helpers/dummy_child.py` is not in the brief's commit paths and was not touched.
5. Ruling 30, "_older rejects a naive now": the check is in `prune_rows`, the one caller that holds `now`. `_older`
   receives the cutoff, and it catches `ValueError` inside its own `try`, so a raise there would be swallowed.
6. In `test_a_killed_child_beats_again_within_1_s` the unused `p =` of the brief is dropped.
7. `Parents` has helpers beyond the brief's list (named above). `spawn_parent` takes `child_cmd` (the kill-9 test
   needs the real engine for the engine lock) and config overrides (`planned_stop_grace_seconds` 1).
8. Readings:
   - `tripped`: on the window limit, `restarts` = the restarts inside the window and `window_s` =
     `restart_window_seconds`. On the day limit, `restarts` = `restarts_today` and `window_s` = null. Otherwise a day
     trip with a clear window would say "0 restarts in 600 s"; R3 (Task 13) must handle the null.
   - `start.n` = `restarts_today + 1`, so the uncounted lock retries repeat their n.
   - The last lock retry falls at the end of `lock_wait_seconds` (`wait = min(back-off, time left)`), then
     `lock_held`. Retrying a whole back-off past 150 s would leave stops unchecked for up to 60 s longer after the old
     engine let go.
   - `halt.why` is "chain", "calendar" or "book" for 4, 5, 6. Task 14's fixture uses "chain"; R5e has three words.
   - A second parent's last line uses the word `lock_held` with the parent lock holder's pid. That is the brief's
     word list; Task 14's `--status` tells the two cases apart.
   - `stop(child, "hang")` is the planned stop for now. Task 11's `watch` never answers "hang"; Task 12 builds the
     group stop and `hang_term_grace_seconds`.
   - `TWO_HOURS_MS = 7_200_000` is a named constant. It is the harness's cap, a platform fact the brief writes as a
     number, and no config key holds it.

## Concerns

1. The state file is written only when the parent ends, as the brief says. If the parent itself is killed (SIGKILL, out
   of memory), that day's restarts since its start are lost, and the next parent's day limit counts from the last
   saved value. A save at each counted restart would be one guarded line. I left it out because the brief lists the
   end-of-run write only.
2. If `spawn` raises (for example `Popen` failing on a missing executable), the exception leaves `main` after the
   `finally`: the handlers are put back and the lock freed, but there is a traceback, rc 1, and no `sup_stop`. The
   default command is `sys.executable`, so this is unlikely. The spec says nothing about it.
3. `main` does not refuse to start when the state file holds a halt from earlier. The brief does not ask for it, and
   `--status` (Task 14) answers `halted` before any launch.
4. Task 12 note: `test_a_second_parent_returns_3...` compares every file under `state/` while the first parent runs.
   Once Task 12 writes a `mark` every clock minute, that test can see a mark row land during its 1-2 s window when a
   minute turns. The moved clock starts at 10:00:00 at setUp, so a minute boundary is about 60 s away, but Task 12
   should keep that in mind.

## Fix round 1

Start: HEAD 62fc1622fbd22fa4f5e214140f49269df3056991 on `supervisor-build`, clean tree. One new commit:
`9d813d54 fix(ai-trader): the supervisor parent starts the engine on a weekday the calendar does not cover`.

### F1 (Important, spec): an uncovered weekday read as "closed_today" - fixed

- `ai-trader/aitrader/supervise.py:384-387`: the closed path now needs both conditions: `session_hours(day, cal) is None`
  and `(day.weekday() >= 5 or day.year in cal.get("years", []))`. The reviewer's condition is used as written.
  `session_hours` itself is unchanged (supervise.py:38-47), so its equality with `journal.session_hours` still holds
  (spec 4.5; Foundations test). A weekday of an unlisted year now starts the child. The engine's `start_checks`
  (news_live.py:1746, 1757-1758) refuses with 5 after its urgent line (news_live.py:1885-1891), and `main`'s existing
  halt path writes `halt` `{code 5, why "calendar"}` and `sup_stop` "halt". That is spec 4.3's code-5 row. A weekend
  of an unlisted year stays "closed_today": there is no stop to look at, and the next weekday raises the halt.
  I started the child rather than returning `(5, "halt")` directly, so the engine's own check and its urgent line stay
  the single source of the code-5 answer.
- `ai-trader/tests/test_supervise.py:970-985`, a new test:
  `ParentLoop.test_a_weekday_of_a_year_the_calendar_does_not_list_starts_the_engine_and_halts_on_its_5`.
  - The days are 2-8 January of `max(config years) + 1`, at 15:00 UTC (10:00 New York).
  - A dummy child scripted to exit 5 stands in for the engine's start check 1.
  - First run, on the weekend day: rc 0 and no child.
  - Second run, on the first weekday: rc 5.
  - Then: exactly 1 `start` row; `sup_stop` rows `[("closed_today", 0), ("halt", 5)]`; state file `halt.code`
    5 and `halt.why` "calendar".
  - Both runs use a child that ends at once (exit 5), so a mutant that wrongly starts a child on the weekend fails
    with 5 != 0 and does not hang.
- RED, before the fix (first form of the test, weekday only):
  `... safe python3 -m unittest discover -s tests -p test_supervise.py -k test_a_weekday_of_a_year` ->
  `AssertionError: 0 != 5`, `FAILED (failures=1)`.
- Mutants of the fix (each applied by sed, run under `timeout 60`, then the file restored):
  - The old condition (no clause): `AssertionError: 0 != 5`, killed.
  - Without the weekend clause (`day.year in years` only): `AssertionError: 5 != 0`, killed.
  - An earlier draft ran the weekend case with a child that beats for ever (`{"beats": -1}`). Under the second mutant
    that hung, and I stopped the run. No stray process was left (checked with `pgrep`). I restored `supervise.py` from
    the backup before going on, and changed the weekend script to the exit-5 child.

### Covering tests (3 runs in a row; the file starts processes)

Command, from `ai-trader/`:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k ParentLoop -k RestartCore -k Foundations`

```
Ran 33 tests in 5.224s

OK
Ran 33 tests in 5.241s

OK
Ran 33 tests in 5.416s

OK
```

The hour does not matter. The new test's clock is fixed, and the dummy child takes `--until` without acting on it.
The runs were made at about 19:45 New York.

### Whole suite, before the commit

`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` from
`ai-trader/` (wall 104 s), last three lines:

```
Ran 738 tests in 103.675s

OK
```

738 = 737 + the 1 new test. After the commit, `git status --short` prints nothing.
