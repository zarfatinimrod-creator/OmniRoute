# Task 10 report - the parent's foundations

Gate clone `<SCRATCH>/clones/sup`, branch `supervisor-build`.
Found HEAD `634c70eb2676956dc7e6a1e24743065c2e85bf70`, branch `supervisor-build`, clean tree (all three checks ran
before anything else). Final HEAD `52ea9265f8fe2b5399782865231fab7cabf5da26`.

Commits:
- `fc68e63f` feat(ai-trader): supervisor config block, its own calendar, the uptime log and the state file
- `52ea9265` docs(ai-trader): the supervisor note says plainly when the owner-line pin test fails (one word of the
  config `_note`, from the self-review)

No attribution line of any kind in either message. No `git stash`; no push, fetch, merge, rebase, reset or branch
command. Every python command ran through the `safe` wrapper.

## What I implemented

`aitrader/supervise.py` (new, standard library only: `fcntl`, `json`, `os`, `datetime`, `pathlib`, `typing`):
- `load_cfg(path=None)`: the whole `config.json`, default the one beside the package (`ROOT = ai-trader/`).
- `session_hours(day, cal)`: the contract of `journal.session_hours`, from the calendar block. Weekend, holiday or a
  year not listed in `years` -> `None`; else `((9, 30), (16, 0))`, or `(13, 0)` on an early close.
- `Paths(state_dir, cache_dir)`: `.lock .state .deadman .relayed .uptime .heartbeat .engine_lock .trades` under the
  state directory (`news_supervisor.lock`, `news_supervisor.json`, `news_deadman.json`, `news_relayed.json`,
  `uptime.jsonl`, `news_heartbeat.json`, `news_engine.lock`, `news_trades.jsonl`), `.sup_log .engine_log` under the
  cache directory (`supervise.log`, `news_live.log`).
- `append_row(path, pid, ev, now, **fields) -> dict`: `{"t": now in UTC whole seconds, "ev", "sup": pid, **fields}`
  as one JSON line (`ensure_ascii=False`, `default=str`, as `journal.append`); starts with a newline when the file's
  last byte is not one. Returns the row.
- `read_rows(path) -> list[dict]`: rows in order, `[]` with no file; a line that is not a JSON object is skipped
  (bad JSON and bad UTF-8 both). Lines are split as bytes, so a U+2028 inside a Hebrew text field cannot split a row.
- `prune_rows(path, keep_days, now)`: drops rows whose `t` is older than `now - keep_days`; keeps every other line
  byte for byte (the file is git-tracked); rewrites only when something goes, through `<name>.tmp` and `replace`.
- `load_state(path, ny_day) -> dict`, never raises: no file -> a new day's state; same day -> the file over a new
  day's defaults; another day -> a new day's state keeping `halt`, `reported_through`, `last_commit` (counts,
  `alerts` reset, `handover` cleared); a file that cannot be read as a JSON object -> a new day's state plus
  `load_error` = the exception's class name (ruling P18(c), controller's addition). The state layout is the brief's:
  `day, restarts_today, trips_today, halt, alerts {hour, sent, capped}, reported_through, last_commit, handover`.
- `save_state(path, st)`: `<name>.tmp` then `replace`, `indent=2` as `journal.save_json`.
- `take_lock(path, now) -> IO | None`: as `news_live.run` takes the engine lock: `open("a+")`, `flock(LOCK_EX |
  LOCK_NB)`; `BlockingIOError` -> close, `None`; any other `OSError` from the lock call is raised; the holder
  truncates and writes `{"pid", "started_at"}` (UTC, whole seconds) + newline. Checked by hand in a scratch directory
  (two processes): the second gets `None` and still reads the holder's line; after the holder closes, the next holder
  writes its own line.

`tests/helpers/dummy_child.py` (new, standard library only): `--heartbeat FILE --script FILE [--until HH:MM]
[--supervised PID]`. Start n plays run n, the last repeats, the count is in `<script>.n`. Run keys and defaults as
the brief lists them (`beats` -1 by default). It writes the engine's heartbeat with Task 4's field set (phase
"idle", every held name's `checked_at` = now - the stop age; `stop_age_s` a number or `[[age, beats], ...]`), atomically.
`--until` is taken and never acted on (ruling P1). `--supervised PID`: the same prctl lines as `news_live`
(`PR_SET_PDEATHSIG` = SIGKILL, Linux), 143 when the parent is not PID at start, and 143 when it changes before a beat.
SIGTERM ends it with 143 (`ignore_term`: ignored). `then`: "exit" -> `code`; "hang" -> sleeps for ever; "crash" ->
`os._exit(code or 1)`.

`config.json`: the `supervisor` block now holds every key of spec 10 at its default (not `slots`, not
`watcher.drill_from`), plus `until_ny` "16:05" and the existing three; the five switches false; `deadman` written as
spec 10 writes it; a `_note` naming the spec, the switches, and that `planned_stop_grace_seconds` must be raised with
`news.guards` = "enforce" (spec 5.3), and that DM1, DM2 and R8 say four of the values in words. `alerts.ntfy_base_url`
= "https://ntfy.sh".

`aitrader/notify.py`: `send` posts to `a.get("ntfy_base_url", "https://ntfy.sh") + "/"` (one line).

`.gitignore`: `state/news_supervisor.lock`, `state/news_supervisor.json`, `state/news_deadman.json`,
`state/news_relayed.json`, with a comment that `state/uptime.jsonl` is tracked.

`tests/test_supervise.py`: module docstring extended by one clause; imports added (`contextlib`, `functools`, `io`,
`re`, `date`, `timedelta`, `notify`, `ownerlines`, `supervise`); `DUMMY_CHILD`; the plan's `SPEC`, `DEADMAN`,
`WATCHER`, `SWITCHES`, `SWITCHES_ON` verbatim; class `Foundations` with 11 tests.

## Tests

The plan's 8, each under its name with the plan's assertion, the stand-ins its comments describe written in:
1. `test_the_supervisor_block_carries_the_defaults_of_spec_section_10`
2. `test_a_switch_is_on_only_when_its_rollout_step_said_so`
3. `test_the_parents_calendar_equals_journal_session_hours_for_every_day_of_2026_and_2027`
4. `test_an_append_after_a_torn_line_starts_a_new_line_and_the_reader_skips_the_torn_one` (file ends `{"t": "x`)
5. `test_rows_older_than_the_keep_days_are_dropped` (rows 31 and 29 days old, keep 30)
6. `test_a_state_file_of_another_day_keeps_the_halt_only_and_garbage_is_a_new_day` (day 2026-11-11, restarts 7,
   trips 2, halt code 4, a handover)
7. `test_supervise_imports_no_pandas_no_requests_and_no_engine_module`
8. `test_notify_posts_to_the_configured_address` (`requests.post` replaced, the made-up topic "t0p1c-under-test" set
   with `mock.patch.dict` for this call only, the base URL `http://127.0.0.1:9`; stdout of `send`'s `ALERT:` print
   captured so the test output stays clean)

Tests added by ruling:
9. `test_the_owner_lines_say_the_numbers_the_config_holds` (controller ruling 11): reads the numbers out of the
   templates in `ownerlines.LINES` and holds `deadman.delay_seconds` = DM1's "6 דקות" x 60, `deadman.handover_delay_seconds`
   = DM2's "10 דקות" x 60, `long_timeout_ms` = R8's "9 שעות" x 3,600,000, `len(handover_times_ny)` = R8's
   "4 פעמים ביום". Parsing the text (not formatting the config) means a value like 390 cannot pass by rounding.
10. `test_a_state_file_that_does_not_parse_is_named_by_its_error_class_and_a_good_one_is_not` (P18(c), controller's
    addition): a torn state file gives `load_error` == "JSONDecodeError" exactly (the class, no text); a good file
    (saved after the key is removed, as `main` will do) has no key; no file at all has no key either.
11. `test_the_dummy_child_plays_run_n_at_start_n_and_never_ends_on_until` (P1: "the dummy takes --until and ignores
    it", no test of its own): three starts with `--until 00:00` (passed at every hour) give codes `[5, 6, 6]` and
    `<script>.n` = 3; the last heartbeat has phase "idle", step 3, `market_open`, `blind` ["BBB"], `code.commit`,
    `supervised` false, BBB's stop 48.5 and `checked_at` exactly 7 s before `at` (the third age of
    `[[300, 2], [7, 1]]`).

### RED

Command (from `ai-trader/`):
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_supervise.py' -k Foundations -v`

```
ERROR: test_supervise (unittest.loader._FailedTest.test_supervise)
ImportError: Failed to import test module: test_supervise
  File ".../ai-trader/tests/test_supervise.py", line 29, in <module>
    from aitrader import journal, notify, ownerlines, supervise
ImportError: cannot import name 'supervise' from 'aitrader' (.../ai-trader/aitrader/__init__.py)
Ran 1 test in 0.000s
FAILED (errors=1)
```

Expected: the module did not exist. The plan expected `ModuleNotFoundError: No module named 'aitrader.supervise'`;
Python words the same missing submodule this way when it is imported as `from aitrader import supervise`.

The first GREEN attempt had 2 failures, both mistakes in my test code, not in the implementation: a tuple built wrong
in test 4, and test 10 saving a state that still carried `load_error` (fixed by removing the key first, as `main`
will).

### GREEN

Same command:

```
Ran 11 tests in 0.675s
OK
```

Three runs of `-k Foundations`: 11 tests OK each (0.59 s, 0.56 s, 0.67 s). Three runs of the whole file
(`-p 'test_supervise.py'`, it starts processes): `Ran 30 tests in 36.111s OK`, `36.756s OK`, `37.342s OK`. Output
pristine (a dot line and the summary only). The runs were at about 22:22 UTC = 17:22 New York, after 16:05; the dummy
never reads the clock, and test 11 passes `--until 00:00` so that an `--until` the dummy obeyed would fail it at any hour.

### Mutation check (scratch copy, removed afterwards)

Each mutant run against `-k Foundations`; all but one failed the tests:
notify back to the literal URL; handover kept across days; halt dropped across days; no `load_error`; no newline
after a torn line; prune keeps everything; no early close; dummy always plays the last run; dummy writes no stop
age; dummy ends on `--until`; `delay_seconds` 390; `long_timeout_ms` 10 h; `hang_kill_enabled` true; `import pandas`
in supervise. The survivor: `session_hours` ignoring `years` (2026-2027 are both covered). I added one assertion to
the calendar test: a weekday of the first year after the calendar's last is `None` for both functions (the year is
taken from the config, so the test does not break when 2028 is added).

## Whole suite

`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` from `ai-trader/`.

Before commit `fc68e63f` (wall 95 s):
```
Ran 704 tests in 94.683s

OK
```
Before commit `52ea9265` (wall 98 s):
```
Ran 704 tests in 97.425s

OK
```
704 = the 693 before this task (derived, not re-run) + 11 new.

## Files changed

- `ai-trader/aitrader/supervise.py` (new, 180 lines)
- `ai-trader/tests/helpers/dummy_child.py` (new, 112 lines)
- `ai-trader/tests/test_supervise.py` (+153, -8 including the new imports)
- `ai-trader/config.json` (`supervisor` block, `alerts.ntfy_base_url`)
- `ai-trader/aitrader/notify.py` (1 line)
- `ai-trader/.gitignore` (+5)

After each commit `git status --short` printed nothing; nothing under `state/`, `logs/`, `reports/`, `research/`.

## Self-review

Read `git diff 634c70eb..HEAD` against the brief line by line. Every interface name, signature and behaviour of the
brief is there; the state layout and the another-day rule are exact; the config holds every key of the test plus the
switches.
Found and fixed:
- The config `_note` ended "when a value and its text part": now "disagree" (commit `52ea9265`).
- The calendar test let a `session_hours` that ignores the calendar's years pass: one assertion added (above).
- Two of my test fragments were wrong on the first run (above).
Checked and left: `<name>.tmp` names are matched by the existing `state/**/*.tmp` ignore line; `prune_rows` does not
touch the file when nothing is dropped (the file is tracked, so no needless diffs); `read_rows` keeps only dicts, so
`r["ev"]` cannot meet a bare number; the dummy's tmp-and-rename heartbeat cannot be read half-written; SIGTERM during a
heartbeat write leaves the old beat in place.

## Departures from the brief

1. 11 tests, not the brief's 8: the three added by ruling (11, P18(c), P1), named above.
2. Assertions added to plan tests (the plan's own assertion is kept in each): test 4 also checks the row as returned
   and as read (`t` in UTC, whole seconds, from a New York time with microseconds); test 5 also checks the surviving
   row is the 29-day one and no tmp file is left; test 6 also checks `alerts` reset and `reported_through` /
   `last_commit` kept (the brief's state rule); test 3 also checks an unlisted year is closed.
3. The dummy refuses (exit 2, a line on stderr) a run key it does not know or a `then` other than exit/hang/crash, as
   `engine_child.py` refuses an unknown scenario key: a misspelt key would play the default and a test would pass for
   the wrong reason. The brief gives no default for `beats`: -1 (beat for ever). `--until` and `--supervised` are
   optional arguments (`--supervised` absent = an engine with no parent).
4. Tmp files are `<name>.tmp` (e.g. `news_supervisor.json.tmp`), not `with_suffix(".tmp")` as journal does:
   `news_supervisor.json` and `news_supervisor.lock` share a stem (the 9b review's minor about `with_suffix`).
5. Readings where the brief is silent: `prune_rows` keeps a line whose age cannot be read (only lines known to be
   old are dropped, spec 4.6); in `load_state` a JSON object with no `day` counts as another day (the halt is kept,
   the safe side) and a JSON value that is not an object counts as unreadable (`load_error` = its exception class,
   e.g. "AttributeError" for a list); `take_lock` raises an `OSError` from `flock` other than `BlockingIOError`
   (Task 11's `main` decides), and keeps the lock when only the text write fails (as the engine does).
6. A second commit (the `_note` word). The brief names one commit; the dispatch allows a further one.

## Concerns

1. `session_hours` carries 9:30, 16:00 and 13:00 as literals, exactly as `journal.session_hours` does; the calendar
   block has no hours. Rule 5 says no literal threshold in the logic; P18(d) accepted the repeated function. I did not
   add calendar keys (outside the brief, and journal would then disagree with them).
2. `append_row` raises on a failed write (a full disk), as `journal.append` does. Spec 4.6 says a damaged line must
   never stop the parent: Task 11's `emit` should guard its writes so a log failure cannot end the loop.
3. `take_lock` swallows a failed write of the holder's text with no log line (this layer has no log); `--status` then
   sees a stale or empty text, which the controller already rules a hint only.
4. `Paths` creates no directory. Task 11's `main` must create the state and cache directories (a drill's fresh
   `--state-dir`) before `take_lock` and the log.
5. The dummy writes no last "stopping" beat on SIGTERM (the engine does). Not in the brief; if Task 15 needs the
   handover's `last_look` from a stopping beat, the dummy will need it there.
6. The module docstring of `supervise.py` says "So far (Task 10)": accurate at this commit, for Task 11 to update.
