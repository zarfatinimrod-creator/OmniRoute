# Task 11 review: the restart core and the parent's loop

Diff 55756d5b..62fc1622 (1 commit), read from `review-task-11.diff`. Every hunk was whole; no changed file was read
separately. Checks outside the diff, each one aimed at a named risk:
- `Paths` fields used by `main` (`engine_lock`, `heartbeat`, `engine_log`, `sup_log`) exist: supervise.py:56-67 at head. The lock_held-from-core path has no process test, so this was the only way to rule out an AttributeError.
- Row fields against spec 4.6: start {child, n, backoff_s}, exit {child, rc, signal, ran_s, why}, tripped {restarts, window_s, trips_today}, sup_start and sup_stop all match.
- `supervise.session_hours` (supervise.py:38-47) against the engine's exit-5 check (news_live.py:1746-1756, 1885-1887; journal.py:71). This was to see what an uncovered year does under the parent.
- One probe of `restart_core` with fakes, through the `safe` wrapper. It ran from the scratchpad, wrote nothing to the clone and was deleted. Five lock refusals, then a quick crash, then a 0: the start rows' `backoff_s` were `[0, 1, 2, 4, 8, 16, 32]`.

### Spec Compliance

Compliant on everything I could check, with one gap: an uncovered year is treated as "closed_today" (Important 1). The rest of the brief is there:
- The three signatures match the brief.
- `restart_core` follows the brief's table, row by row and in the right order: planned stop, end of day, halt, lock wait, crash, trip.
- `watch` is asked before every start (also with a 0 wait) and every `loop_seconds` while a child runs and during a back-off.
- `near_until` is one-sided, and "24:00" works.
- `main`:
  - parses the brief's command line and returns 2 for a bad argument or config;
  - takes the lock, and a second parent prints `lock_held pid <holder>`, writes nothing and returns 3;
  - installs the signal handlers on the main thread only and puts them back;
  - catches orphaning through `os.getppid()`;
  - prunes the uptime log, then writes `sup_start` with the seven fields;
  - on a day with no session, writes `sup_stop` "closed_today" and starts no child;
  - builds the child command as the brief gives it and starts it from the main thread with `start_new_session=True`, `cwd`=ROOT, the given `env` and output to `.cache/news_live.log`;
  - does a planned stop as SIGTERM to the child's pid, the grace, then a logged SIGKILL to its group;
  - writes the state file (restarts_today, trips_today, halt on 4, 5, 6);
  - prints the two stdout lines with the brief's words (`crash_loop` prints as `tripped`).
- All 16 tests the brief names are there under their names, each with the brief's assertion.
- The extras are allowed or are tests of what the brief already asks for:
  - Ruling 30 (progress.md:347): the naive-time refusal in `prune_rows`, the quiet_hours fix in the notify test, the guarded `emit`, the mkdir before the lock, the docstring.
  - Ruling P18(c): the parse-error class name goes to the log.
  - Ruling P29: the five switches are pinned off.
  - The later controller note on `--until`: 24:00, which replaces P1's 23:59.
  - The planned-stop-is-pid-only test checks what the brief already asks.
- The orphan stand-in departs from the brief, and the departure is justified. A helper that exits "at once" would race `main`'s `getppid()` read, and the test would be flaky.

Cannot verify from this diff:
- Handover by the clock (`handover_times_ny`, `max_leg_minutes`): that is Task 15, and `watch` never answers "handover" yet.
- The hang stop to the group with `hang_term_grace_seconds`: Task 12. `stop(child, "hang")` is the planned stop for now.
- The owner lines R3/R3b/R3c/R5a-d, and `leave()` under ruling P8: Tasks 13 and 21.
- Whether `--status` (Task 14) reads the last stdout line, the `tripped` row with `window_s` null, and the state file's `halt.why` words as written here.
- What signal the real harness sends (TaskStop or the 2-hour cap), and PR_SET_PDEATHSIG tied to the main thread on the platform: the drills of Tasks 17 and 20.

### Strengths

- The core holds no I/O and gets its clock injected. The first check of every outer loop asks `watch` before any start, so a stop order during a back-off never costs a start (Review Focus 2). The brief's test proves it.
- The lock wait puts its last try at the end of `lock_wait_seconds` (supervise.py:259) and does not overshoot by a whole back-off. A test assertion pins it (`clock < 152`).
- `stop` uses `Popen.send_signal`, so a child that was already reaped is never signalled. `killpg` runs only while the child is not yet reaped, so the group id is still the child's.
- The tests run real behaviour. RestartCore uses a fake clock that moves only on `sleep`. ParentLoop runs real processes with an explicit clean environment, the engine behind its tripwire, and clean-ups that check `/proc/<pid>/cmdline` before they kill.
- Mutation pass: three of 22 mutants survived the first pass. Each now has its own test or assertion. The one survivor left is shown to be equivalent.
- No log line or error path carries an exception's text, a URL or the topic: only class names.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

1. supervise.py:384: on any weekday of a year the calendar does not list, the parent says "closed_today", starts no engine and tells nobody.
   - What happens: `session_hours` (Task 10, supervise.py:45) returns None for a year not in `cal["years"]`, and `main` treats that as a day with no session. It returns 0 "closed_today" and starts no child.
   - Why it matters:
     - The engine's exit 5 exists for exactly this day. news_live.py:1746 says "config.json's calendar does not cover today: every day would read as closed, and no stop be checked." Its urgent alert at news_live.py:1885-1887 is now unreachable under the parent.
     - Spec 4.3's row for code 5 (halt, R5b, exit 5) never happens.
     - The calendar lists 2026-2027. From the first weekday of 2028, every launch would end at once with code 0. No stop is looked at and no owner line goes out. That is a skipped stop look with no alarm, which the constraints rule out.
     - The root is in two spec rules together: spec 4.5's equality with `journal.session_hours`, and the "closed_today" rule. Neither says outright what to do with an uncovered weekday, so this is not plan-mandated. The controller may still want to rule on it.
   - Fix: treat an uncovered year as closed only on a weekend. For example, take the closed path only when `day.weekday() >= 5 or day.year in cal.get("years", [])`. Otherwise start the child: the engine exits 5, and `main`'s existing halt path writes halt "calendar". Or return `(5, "halt")` directly. Add one ParentLoop test with a clock on a weekday of a year the config copy does not list, expecting rc 5 and `halt.why` "calendar".

#### Minor (Nice to Have)

1. supervise.py:259-260 with 275: the lock retries and the crash back-off share one `delay`.
   - What happens: after N refusals, the first quick crash of the engine that finally got the lock waits 2^N s, up to `backoff_max_seconds`, where the brief's sequence starts at 1 s. The probe showed 32 s after five refusals.
   - Why it is Minor: the brief's "the doubling starts again after a healthy run" can be read as one shared sequence. The case also needs a long lock wait followed by a quick crash.
   - Fix if wanted: reset `delay` to `backoff_first_seconds` when a code other than 3 follows a refusal.
2. supervise.py:269-271: `restarts_today` and the window stamp count a restart when it is decided, before the back-off. A stop order during that back-off (`(143, "signal")`, no start) still saves the restart in the state file, so the day's count runs high by one.
3. supervise.py:233: `start.n` = `restarts_today + 1`.
   - Lock retries repeat their n.
   - Each new parent after a handover starts again at the same n as the last one, because a handover adds no restart. So n is not quite spec 4.6's "start number today".
4. supervise.py:433: the state file is written only when the parent ends. If the parent is SIGKILLed (OOM, or a harness signal no one has checked yet), the restarts since its start are lost, and the next parent's 20-a-day limit counts from the last saved value. A guarded save after each counted restart would close this.
5. supervise.py:390-394: if `spawn` raises (`Popen` failing with ENOMEM or EAGAIN, or the engine log not opening), the exception leaves `main` with rc 1 and a traceback. No `sup_stop` row is written, the state file is not saved and no last line is printed. Treating a failed spawn as a crash would keep the trip bound and the rows.
6. supervise.py:316: a parent whose launcher died before this line runs is "born orphaned" and never stops. The test deliberately avoids this race. The window is tiny with `exec`, but it is the one orphan case no check covers.
7. supervise.py:288: `TWO_HOURS_MS = 7_200_000` is a literal outside config.json. The brief gives the number and it is a fact of the platform, not a threshold the parent acts on. Task 14's `--status` should reuse this constant and not write the number again.
8. supervise.py:329: the NUMBERS check accepts `bool` (`isinstance(True, int)`) and takes zero or negative values for `loop_seconds` and the graces. A config typo would give a busy loop or a stop that does not wait.

### Assessment

Task quality: Needs fixes. The core, the code table, the signal and orphan paths and the tests are sound and match the brief. One defect blocks: on any weekday of a year the calendar does not list, the parent says "closed_today", starts no engine and so skips the engine's own exit-5 alarm. The fix is one condition and one test.
