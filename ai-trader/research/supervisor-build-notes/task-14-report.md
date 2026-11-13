# Task 14 report - `--status`, `--clear-halt`, `--relayed` (+ Ruling 36 items a-j)

Gate clone `<SCRATCH>/clones/sup`, branch `supervisor-build`.
Checks before anything else: HEAD `236430fade78e72aa6a7ad3adbe1a3213bd9f614`, branch `supervisor-build`, clean tree.

Final HEAD `9f6190ae41cad87fcccecb586740603194509291`. Two commits, no attribution line of any kind, `git status --short`
empty after each:
- `db887734` feat(ai-trader): supervise --status decides what a woken session does; --clear-halt and --relayed
- `9f6190ae` docs(ai-trader): supervise says which mark --status reads and that --clear-halt takes the parent's lock
  (self-review fixes, docstrings and one comment only)

No `git stash` in any form; no push, fetch, pull, merge, rebase, reset or branch command; `_tasks` untouched. Every python
command ran through the `safe` wrapper (the task's tests, three file runs, the whole suite twice, the mutation pass,
the config diff check).

## What I implemented

### `aitrader/supervise.py`
- `status(paths, cfg, now, *, watchdog=False, environ=None) -> dict`, the JSON of spec 4.4 with the brief's keys in
  order: `action`, `why`, `ny_time`, `session_day`, `parent {alive, pid, mark_age_s}`, `engine {hb_age_s, stop_age_s,
  held, commit, dirty}`, `today {restarts, trips, halt}`, `deadman_ok`, `ntfy_left` (both from the log's last `mark`:
  its `dm` and `left`), `unsent`, `launch {command, timeout_ms}`.
  - Reads only: the state file (`load_state` for today's New York day), `uptime.jsonl` (`read_rows`; an unreadable log
    is no rows), the heartbeat (`_read_beat`, `beat_view` on the beat's own pid; ages from `time.time()` as the parent
    measures them), `news_relayed.json`, the book (for R5e's `{held}`), and `/proc`. No lock is probed, no directory is
    made. The brief's last test pins it (state directory bytes equal before and after).
  - Alive: `_live(lock, name)` = the pid in the lock file's text (`_holder`) when `/proc/<pid>/cmdline` has `name` as
    one of its words: `aitrader.supervise` for the parent lock, `news-live` for the engine lock. A dead pid, a zombie
    (empty cmdline) or a pid that is now another program is not alive (Review Focus 1).
  - `action`, the first row that applies: `closed_today` (`closed_day`, the parent's own rule, now one helper used by
    both: a weekend or a holiday; an uncovered-year weekday is not closed, so the engine's start check halts it with
    5), `after_hours` (`not launch_from_ny <= HH:MM < launch_until_ny`, New York), `none` (a live parent and the log's
    last mark at most `parent_stale_seconds` old), `replace_parent` (a live parent, no such mark), `halted` (a halt in
    the state file), `kill_stray` (a live engine whose `/proc/<pid>/stat` parent pid is not the live parent; `why`
    carries the pid), `wait_for_watchdog` (`trips_today >= 2`, not `watchdog`, and the log's last row is not a
    `sup_stop` whose `why` is a key of `PLANNED`: handover, signal, orphaned), `launch`.
  - `unsent`: today's (New York) `alert` rows grouped by id in file order; listed when the id's latest row has `sent`
    exactly `false` ("capped" is not unsent), the id is not in today's `news_relayed.json`, and either the kind is
    R10, or no parent is alive, or the id's first row is older than `alert_retry_minutes`. With `watchdog` and a halt
    whose `at` falls on an earlier New York day: `{"id": "R5e-<today>", "kind": "R5e", "text": ...}` until that id is
    relayed; `{date}` = the halt's `at` on `owner_tz` as DD.MM, `{why}` = `ownerlines.WORDS["R5e.why"][code]`,
    `{held}` = `held_text(_held_now(paths, None))`, i.e. the book (ruling P11). A line that cannot be built (a halt
    code no engine gives) is left out rather than crash `--status`.
  - `launch`: `cd ai-trader && exec python3 -u -m aitrader.supervise --until <supervisor.until_ny>` plus ` --handover`
    and `TWO_HOURS_MS`, unless `long_timeout_proven is True` and `int(environ["BASH_MAX_TIMEOUT_MS"]) >=
    long_timeout_ms` (missing or not a number = 0): then no `--handover` and `long_timeout_ms`.
- `relay(paths, ids, now)` = `--relayed ID...`: the only writer of `state/news_relayed.json` `{"day", "ids"}`, today's
  ids kept, the new ones added once each in order, another day's file starts an empty list; written whole through
  `save_state` (tmp + rename). Prints `supervise: relayed ...`, exit 0 (1 when the file cannot be written).
- `clear_halt(paths, now, check, env)` = `--clear-halt`: a live parent prints `a live parent, pid N: the halt stays` and
  returns 3. Else runs `[*check, "--check"]` (`check` = `child_cmd` or `[sys.executable, "-m", "aitrader",
  "news-live"]`) with cwd `ai-trader/`, stdout and stderr captured and printed; a non-zero answer: `the check answered
  N: the halt stays`, 1. On 0: `take_lock` on the parent lock (None: 3), `load_state` for today, `load_error` dropped,
  `halt` null, `save_state`, the lock closed, exit 0. A check that cannot start, or a lock or state write that fails,
  is 1 with the class name only.
- `main`: `--status`, `--watchdog`, `--clear-halt`, `--relayed ID...`; these forms need no `--until` and skip the
  loop's number checks; they are routed right after `Paths` is built, before the first stdout line, the mkdirs and
  the lock. `--status` prints `json.dumps(status(...), ensure_ascii=False)` and returns 0 (2 on a config without the
  keys it reads).
- `_held_now(paths, child_pid)`: main's `held_now` closure lifted to module level unchanged, so `status()` reuses it
  (the prompt: "status() reuses them, it does not rebuild them"). Main's three call sites now pass `paths`.

### Ruling 36, items (a)-(j)
- (a) `say`: with no topic, after the cap check, one `alert` row `sent` false and one log line `line <id>: no topic`;
  nothing is published, so there is no retry loop.
- (b) `watch` (asked at once after the core counts a restart, in the wait before the next start): when
  `counts["restarts_today"]` differs from `st["restarts_today"]`, `st` takes it and `save()` (guarded) runs.
- (c) `restart_core`: `spawn()` raising `OSError`, `ValueError` or `subprocess.SubprocessError` is a crash: no `start`
  row, an `exit` row `{child: null, rc: null, signal: null, ran_s: 0.0, why: "spawn <class>"}`, then the crash path
  (counted, back-off, trip). `fall` now says "killed" on `signal is not None` (equal to the old `rc is None` for every
  real exit), so a spawn failure is "crash". Main never raises out of it.
- (d) `restart_core`: in the crash path, when lock refusals came before (`refused_at` set), `delay` goes back to
  `backoff_first_seconds`.
- (e) `main`: every `NUMBERS` value must be an int or float and not a bool; `POSITIVE` (`loop_seconds`,
  `start_grace_seconds`, `hang_term_grace_seconds`, `planned_stop_grace_seconds`) must be above 0. Else exit 2.
- (f) `stop(child, "hang")`: SIGTERM to the group, up to `hang_term_grace_seconds` for the child, then SIGKILL to the
  group whether or not the child ended, `ProcessLookupError` ignored, then `child.wait()`; `killed_with` "TERM" when the
  child ended within the grace, else "KILL". One helper, `_signal_group(pgid, sig)`, for all three killpg calls.
- (g) `up`: `last = kid["last_look"] or _when(hb.get("stops_checked_at")) or sup_t`, `sup_t` = the `sup_start` row's
  `t` (that row now takes the `now` already read for it, so the two are equal to the second).
- (h) `config.json` `supervisor._note`: one sentence added, "planned_stop_grace_seconds must stay at or under
  mark_gap_max_seconds (raise both together): the parent writes no mark while it waits for a planned stop to end." A
  key-by-key diff against `236430fa` shows `/supervisor/_note` as the only difference: no value changed.
- (i) the launch pair's two-hour timeout is `TWO_HOURS_MS`.
- (j) `deadman._opener`'s docstring: urllib's ProxyHandler also reads the process's own `no_proxy`, so "env decides"
  holds whole only when env is `os.environ`.

### `tests/test_supervise.py`
- Class `Status(Parents)`: helpers `live(word)` (a stand-in process `python -c "sleep 60" <word>`, started by the test,
  in `_started` so tearDown kills it), `holds(lock, pid)` (the lock file's text only; nothing takes the lock),
  `status(**case)` (writes the case's files into `self.state`, calls `supervise.status`, then puts back exactly the
  files the case wrote and kills the case's stand-ins; a call with no case writes and restores nothing, so the brief's
  "status writes nothing" check is real), `action(**case)`, `clear_halt(check_rc)` (a halt 4, then `main
  --clear-halt` with a stand-in check that prints a line and exits `check_rc`), `relayed(*ids, now=)`. The config is
  `Parents.config(long_timeout_proven=proven)`, so all five switches are pinned (P29), and `environ={}` unless the test
  gives one. `NOW` = 10:07 New York on 2026-11-12.
- The brief's five tests, each under its name with the plan's assertions verbatim, and the stand-ins its comments name
  written in the test.
- Tests added by ruling 36 (listed below), and three in self-review.

## TDD evidence

### RED
`cd ai-trader && .../safe python3 -m unittest discover -s tests -p test_supervise.py -k Status`, tests written, no
implementation (the brief's five plus the ruling (i) test and two self-review tests at that time):
```
ERROR: test_a_lock_file_that_names_a_live_pid_that_is_no_parent_is_no_parent
AttributeError: module 'aitrader.supervise' has no attribute 'status'
ERROR: test_the_first_row_that_applies_wins
AttributeError: module 'aitrader.supervise' has no attribute 'status'
ERROR: test_the_launch_pair
AttributeError: module 'aitrader.supervise' has no attribute 'status'
ERROR: test_the_two_hour_timeout_is_two_hours_ms
AttributeError: module 'aitrader.supervise' has no attribute 'status'
FAIL: test_clear_halt_clears_only_when_the_check_passes_and_status_writes_nothing
AssertionError: Tuples differ: (2, 4) != (1, 4)
python3 -m aitrader.supervise: error: unrecognized arguments: --clear-halt
FAIL: test_clear_halt_with_a_live_parent_exits_3_and_runs_no_check
AssertionError: Tuples differ: (2, 4, False) != (3, 4, False)
FAIL: test_relayed_keeps_the_days_ids_and_a_new_day_starts_an_empty_list
AssertionError: Tuples differ: (2, 2, 2) != (0, 0, 0)
python3 -m aitrader.supervise: error: unrecognized arguments: --relayed R4-1
FAIL: test_unsent_leaves_out_what_was_relayed_what_is_still_retried_and_adds_r5e_from_the_second_day
AssertionError: 2 != 0
Ran 8 tests in 0.030s
FAILED (failures=4, errors=4)
```
Expected: the brief's own expectation, `AttributeError ... no attribute 'status'`, for every test that calls
`status()`; the tests that drive the command forms fail one step earlier, on argparse's refusal (exit 2) of
`--clear-halt` / `--relayed`, which did not exist yet.

The ruling tests, same state of the code (`-k` on the nine names):
```
ERROR: test_a_spawn_that_raises_is_a_counted_crash_and_main_returns
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/tmpoi519frj/no-such-engine'      (c: the traceback out of main)
ERROR: test_on_a_cold_start_with_no_stamp_blind_s_counts_from_sup_start
ValueError: not enough values to unpack (expected 1, got 0)                                      (g: blind_s 0, open_seconds never asked)
FAIL: test_the_planned_stop_grace_stays_within_the_mark_gap_and_the_note_says_so
AssertionError: 'planned_stop_grace_seconds must stay at or under mark_gap_max_seconds' not found in ...   (h)
FAIL: test_a_bool_or_a_grace_that_is_not_positive_is_a_bad_config
AssertionError: Tuples differ: ([0, 0, 0, 0, 0], 0, [...]) != ([2, 2, 2, 2, 2], 5, [])           (e: all five accepted)
FAIL: test_a_counted_restart_is_on_disk_while_its_back_off_runs
AssertionError: not within 5 s: <lambda>; engines that ended: []                                 (b: no state file in the back-off)
FAIL: test_with_no_topic_a_line_is_one_row_sent_false_and_one_log_line
AssertionError: Tuples differ: ([('R2', False)], 11) != ([('R2', False)], 1)                     (a: 11 "no topic" retries)
FAIL: test_after_lock_refusals_a_crash_backs_off_from_the_first_value
AssertionError: Lists differ: [1, 2, 4, 8, 16, 32] != [1, 2, 4, 8, 16, 1]                        (d)
FAIL: test_a_hang_kill_ends_a_grandchild_that_ignores_sigterm_after_its_leader_ended
AssertionError: not within 2 s: <lambda>; engines that ended: ['exit 75: ']                      (f: the deaf grandchild lived on)
Ran 9 tests in 12.350s
FAILED (failures=6, errors=2)
```
(j) `test_urllib_also_reads_the_process_no_proxy` passed in that run: it pins the existing stdlib behaviour that the
new docstring states; a docstring has no RED. (i) was RED with the Status class above.

### GREEN
- `-k Status`: `Ran 9 tests in 0.087s` / `OK` (the brief's 5, ruling (i), 3 self-review).
- The nine ruling tests: `Ran 9 tests in 6.892s` / `OK`.
- `tests/test_supervise.py` whole, three times in a row, process tests included:
  - run 1: `Ran 110 tests in 151.924s OK`; run 2: `Ran 110 tests in 153.445s OK`.
  - run 3 started at 04:59:17 UTC = 23:59:17 New York: `FAILED (failures=7)`, all seven in EngineLock (4), EngineStop
    (2) and Harness (1), classes this task does not touch, each with `engines that ended: ['exit 0: ']`: their engine
    starts carry `--until 23:59` and the real New York clock had reached 23:59. This is the known ceiling of the
    controller's ruling (11:10 UTC, 2026-11-11: "a test must pass at any hour of the New York day except the one minute
    23:59-00:00"). Not a defect of this change and not retried as one: three fresh runs in a row followed.
  - run 4 (00:02:46 New York): `Ran 110 tests in 152.600s OK`; run 5 (00:05:19): `Ran 110 tests in 151.616s OK`;
    run 6 (00:07:51): `Ran 110 tests in 150.252s OK`. Each output is five lines: dots, the rule, the count, a blank,
    `OK`. Pristine.
- Mutation pass on a scratch copy (13 mutants on the new `status` / `relay` / `clear_halt` logic, each run against its
  test): 13 killed, 0 survived (none `<=` -> `<`; planned stop ignored; `launch_until_ny` inclusive; stray `==`; pid
  alone counts as alive; R10 not at once; no-parent not at once; R5e on the halt day; R5e after relayed; launch `>`;
  clear on any rc; clear with a live parent; relayed forgets the day).

## Whole suite
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`
- before commit `db887734` (started 00:13:08 New York), wall 225 s:
```
Ran 797 tests in 224.055s

OK
```
- before commit `9f6190ae` (started 00:18:23 New York), wall 222 s:
```
Ran 797 tests in 221.747s

OK
```
797 = 779 (the last independent run at `236430fa`) + 18 new. The suite's other output lines (`[news] engine started
...`, `[journal] skipped unreadable line ...`) come from other modules' engine tests and were there before.

## Files changed
- `ai-trader/aitrader/supervise.py` (status, relay, clear_halt, the command forms, closed_day, _held_now lifted,
  _signal_group, POSITIVE, ruling 36 a-g and i)
- `ai-trader/tests/test_supervise.py` (class Status; ruling tests in RestartCore, ParentLoop, Watching, Foundations,
  ParentLines; DEAF_GROUP_CHILD)
- `ai-trader/config.json` (`supervisor._note` text only, item h)
- `ai-trader/aitrader/deadman.py` (`_opener` docstring only, item j) - see "Departures"

## Tests added by ruling (Ruling 36)
- (a) `ParentLoop.test_with_no_topic_a_line_is_one_row_sent_false_and_one_log_line`
- (b) `ParentLoop.test_a_counted_restart_is_on_disk_while_its_back_off_runs`
- (c) `ParentLoop.test_a_spawn_that_raises_is_a_counted_crash_and_main_returns`
- (d) `RestartCore.test_after_lock_refusals_a_crash_backs_off_from_the_first_value`
- (e) `ParentLoop.test_a_bool_or_a_grace_that_is_not_positive_is_a_bad_config`
- (f) `Watching.test_a_hang_kill_ends_a_grandchild_that_ignores_sigterm_after_its_leader_ended`
- (g) `Watching.test_on_a_cold_start_with_no_stamp_blind_s_counts_from_sup_start`
- (h) `Foundations.test_the_planned_stop_grace_stays_within_the_mark_gap_and_the_note_says_so`
- (i) `Status.test_the_two_hour_timeout_is_two_hours_ms` (patches `TWO_HOURS_MS`; the launch pair follows it)
- (j) `ParentLines.test_urllib_also_reads_the_process_no_proxy`

Tests added in self-review: `Status.test_the_status_form_prints_the_json_of_spec_4_4` (the command form itself: exit
0, the brief's keys, `--watchdog` reaches `status()`), `Status.test_clear_halt_with_a_live_parent_exits_3_and_runs_no_check`,
`Status.test_relayed_keeps_the_days_ids_and_a_new_day_starts_an_empty_list` (also: a relayed R5e is listed no more).

## Self-review findings and what I did
1. `main`'s docstring said the woken-session forms "take no lock of a parent's and start no child": false for
   `--clear-halt`. Fixed in `9f6190ae`.
2. `status`'s docstring said "a live parent whose last mark"; the code reads the log's last mark, whoever wrote it.
   The docstring now says so and why it is the same thing (one parent at a time). Fixed in `9f6190ae`.
3. The `POSITIVE` comment ("0 spins") was cryptic; now a full comment line. Fixed in `9f6190ae`.
4. Two new lines were over 120 columns (the usage line and the `sup_t` line); shortened before the first commit. The
   one remaining 122-column line (`save()  # the commit outlives ...`) was there at `236430fa`.
5. No test drove `--status` as a command and none covered "no live parent: listed at once" in `unsent`: added the
   command-form test and one assertion at the end of the unsent test (the parent stand-in killed, then R1-3 listed).
6. Checked: `status` makes no directory and opens nothing for writing; the command forms are routed before main's
   mkdirs; `clear_halt` makes no `.cache` (the brief's `iterdir` snapshot reads every entry as a file).

## Departures from the brief, and readings where it is silent
1. **`aitrader/deadman.py` is in the commit** (four paths, not three). Ruling 36 (j) names `_opener`'s docstring, and
   `_opener` lives in `deadman.py:26`; `supervise.py` has none. The change is the docstring alone.
2. **Additions to the brief's given tests** (no given assertion changed or dropped): the unsent test writes "R4-1
   relayed" through `--relayed` itself, writes a book, and gains two assertions (R5e's exact text: date, why and the
   book's `{held}`; and, once its parent stand-in is killed, R1-3 listed at once). The clear-halt test gains one
   assertion that the check's own output is printed. `-k Status` runs 9 tests, not the brief's 5: one is ruling 36
   (i), three are self-review.
3. **Ruling 36 (c), "a code row (code null, ...)":** read as the `exit` row, whose `rc` is the code: `{child: null,
   rc: null, signal: null, ran_s: 0.0, why: "spawn <ClassName>"}` (a space between "spawn" and the class), and no
   `start` row for a start that never happened.
4. **Ruling 36 (f), "SIGKILL to the group after the grace whether or not the leader ended":** read as "after the wait
   for the child, which ends when the child ends or when the grace runs out". Waiting out the whole grace after a child
   that ended at once would delay every hang restart by up to `hang_term_grace_seconds` and break the timing of three
   existing tests (`test_a_hang_kill_says_r2_at_the_restart_...` with `stop_after=5`, among them). This is also the form
   the Task 12 review proposed.
5. **`session_day`** is `not closed_day(...)`: true on an uncovered-year weekday, where `action` is `launch` (or
   `halted`), consistent with the parent's own rule.
6. **R5e's `{DD.MM}`** is the halt's `at` on `owner_tz` (spec 8: the owner's times are Israel time). For any halt during
   New York market hours it is the same date as New York's.
7. **Controller note (12:19 UTC, 2026-11-11): "Task 14's `--status` tests the lock itself, never the text alone."**
   The brief says "No lock is probed" and gives the `/proc/<pid>/cmdline` test. I built the brief's test: the text
   gives a pid, and the pid must be a live process whose command line names the parent or the engine; the text alone
   never decides. Taking the lock, even for a moment, could refuse a parent that starts in that moment. A read-only
   way to test the lock itself exists (`/proc/locks` lists each flock's pid and file), and I did not add it: it would
   depend on device numbers that overlay filesystems report differently, and an engine running unlocked after an E2
   holds no flock yet is still a stray. If the controller meant `/proc/locks` as well, it is a few lines in `_live`.

## Concerns
1. **R5e for a halt 6 says "פתוח: אין פוזיציות".** Halt 6 means the book is missing or unreadable, and R5e's `{held}`
   comes from the book (ruling P11), so the line carries the false all-clear that P11 itself names. P11 only noted
   that R5d has no `{held}`. Options: a halt-6 R5e takes `{held}` from the last heartbeat, or says that the positions
   are unknown. Needs a ruling and a template change: not built.
2. **The 23:59 New York minute** failed seven engine tests in one of my file runs (run 3, above). This is the accepted
   ceiling. Whoever runs a gate near midnight New York will meet it again.
3. **`mark_age_s` reads the log's last mark, not one written by the live parent's pid.** In the moment between a new
   parent taking its lock and its first loop tick (milliseconds), a stale mark from the parent before it would read as
   `replace_parent`. Filtering by `sup` has the same window the other way round (no mark of its own yet), so I kept
   the simpler read.
4. **The commit author** is the gate clone's configured identity (`Claude <<email>>`), as on every commit
   of the branch (Ruling 34). The messages carry no trailer or footer.

## Fix round 1

Gate clone checks before anything else: HEAD `9f6190ae41cad87fcccecb586740603194509291`, branch `supervisor-build`,
clean tree. One new commit, `e1ea314e` fix(ai-trader): supervise --status reads the lock itself, not the pid in its
text. HEAD after it: `e1ea314ebc6f00e3dc72b5fd1b013fe892db7d16`. No attribution line; `git status --short` empty
afterwards. No `git stash` in any form; no push, fetch, pull, merge, rebase, reset or branch command; `_tasks` not
touched. Every python command went through the `safe` wrapper.

### F2 (Important, spec): `--status` tests the lock itself, never the text alone. Fixed.
Which rule binds: the controller note (12:19 UTC, 2026-11-11), as the finding rules. It agrees with spec 4.4 (rows
none / replace_parent / kill_stray: "its lock is held by a live pid"). It also fits the brief's "No lock is probed":
reading /proc/locks makes no flock call. This replaces my report's departure 7.
- `ai-trader/aitrader/supervise.py:528-547`: `_live(lock, name)` now finds the flock holder in `/proc/locks`.
  `FLOCK_ROW` (:532) matches a holding FLOCK row (`N: FLOCK ADVISORY READ|WRITE <pid> <maj>:<min>:<inode>`). Waiting
  rows begin with "->" and never match. The row is matched on the lock file's `st_ino` alone, with no device compare:
  an overlay filesystem reports another device there than stat does. The `ponytail:` comment at :529-531 names the
  limit: a same-inode flock on another filesystem, held by a process with the same word, would pass too. From the
  matching holders, `_live` returns the first pid whose `/proc/<pid>/cmdline` names `name` (the cmdline check is
  kept). It makes no flock call. A lock file or `/proc/locks` that cannot be read gives None, the same as an
  unreadable cmdline. The lock text is no longer read by `_live`.
  - Case (a): a live parent's lock whose text names an older, dead pid now reads as alive, with the holder's pid.
  - Case (b): a recycled pid that is another `aitrader.supervise` run but holds no lock no longer counts as alive.
- `supervise.py:671-674`: `clear_halt` names the pid that `_live` returned (the holder) and no longer the text's pid.
  It relies on `_live` (finding: ":658").
- Docstrings: `take_lock` (:190-196) no longer says its text is for --status. `status` (:561-563) says how a parent
  is judged alive now.
- `ai-trader/tests/test_supervise.py`:
  - `STAND_IN` (:1545-1554) and `Status.live(word, lock=None)` (:1564): given a lock file, the stand-in holds an flock
    on it. `live` returns only after the stand-in says "held". `holds` (:1573) still writes the holder's text, and
    only that.
  - Every Status case whose stand-in plays a parent or an engine now holds the real lock: `status(parent="alive")`,
    `status(engine=...)`, the unsent test's parent, and the clear-halt live-parent test. In `status()` the file is
    recorded by `touch` before the stand-in creates it.
  - `test_clear_halt_with_a_live_parent_exits_3_and_runs_no_check` (:1706): the text now names pid 99999999, which no
    process has. One assertion added: the printed pid is the holder's.
  - New `test_a_lock_file_whose_text_names_a_live_parent_that_holds_no_lock_is_no_parent` (:1714): the finding's
    test. The text names a live `aitrader.supervise` stand-in that holds no lock, so `parent.alive` is False and
    `action` is "launch". The test then checks two more cases, both still no parent: that stand-in holding another
    file's lock (a parent of another clone), and this lock held by a `news-live` process.
  - New `test_a_held_lock_whose_text_names_an_older_pid_is_a_live_parent_with_the_holders_pid` (:1722): case (a).
    `(alive, pid, action) == (True, <holder pid>, "replace_parent")`. Then, with the parent gone and the engine lock
    held, `kill_stray`'s `why` carries the engine pid from its lock (its text names 99999999).
  - Not changed: every given assertion of the brief, and the brief's
    `test_a_lock_file_that_names_a_live_pid_that_is_no_parent_is_no_parent`, which still passes: the test process
    holds no lock.

### TDD evidence
RED, with the tests changed and `_live` as at 9f6190ae:
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k Status`
```
FAIL: test_a_held_lock_whose_text_names_an_older_pid_is_a_live_parent_with_the_holders_pid
AssertionError: Tuples differ: (False, None, 'launch') != (True, 4159, 'replace_parent')
FAIL: test_a_lock_file_whose_text_names_a_live_parent_that_holds_no_lock_is_no_parent
AssertionError: Tuples differ: (True, 'replace_parent') != (False, 'launch')
FAIL: test_clear_halt_with_a_live_parent_exits_3_and_runs_no_check
AssertionError: Tuples differ: (3, 4, True) != (3, 4, False)
Ran 11 tests in 0.265s
FAILED (failures=3)
```
The third failure: with the text-only reading, `--clear-halt` ran the check while a parent held the lock, and only
`take_lock` stopped it.

GREEN, same command: `Ran 11 tests in 0.288s` / `OK`.

Mutation pass, on a scratch copy against `-k Status`: 6 mutants, 6 killed.
- the cmdline check dropped
- any inode accepted
- the text's pid put first
- the old text reading restored
- `--clear-halt` printing the text's pid
- the hex device not parsed

Real-lock experiment in a temporary directory: a process with `aitrader.supervise` in its argv took the lock through
the real `supervise.take_lock`. `_live` returned its pid. It returned the same pid after the text was overwritten
with 99999999, and None once the process was killed. On this VM (ext4 root) the `/proc/locks` row looked like
`2: FLOCK  ADVISORY  WRITE 3796 fe:00:2031670 0 EOF`.

### Covering tests: `tests/test_supervise.py`, three times in a row (the file starts processes)
Command: `cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py`
- run 1 (00:43:34 New York): `Ran 113 tests in 151.662s` / `OK`
- run 2 (00:46:07 New York): `Ran 113 tests in 154.451s` / `OK`
- run 3 (00:48:42 New York): `Ran 113 tests in 157.482s` / `OK`

Each output is five lines: dots only, the rule, the count, a blank line, `OK`. 113 = 111 test methods in the file at
9f6190ae (`git show 9f6190ae:ai-trader/tests/test_supervise.py | grep -c '    def test_'`) + the 2 new tests. The
"110" in the first report's file runs was one fewer than that file holds at 9f6190ae. The whole-suite count below
(+2) agrees.

### Whole suite, once, before the commit
`cd ai-trader && /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`
(started 00:51:42 New York, wall 220 s, exit 0). Last three lines:
```
Ran 799 tests in 219.751s

OK
```
799 = 797 at 9f6190ae + 2 new tests.

### Files in the commit
`ai-trader/aitrader/supervise.py`, `ai-trader/tests/test_supervise.py`.
