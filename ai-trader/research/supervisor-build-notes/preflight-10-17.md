# Pre-flight scan - Tasks 10-17 (plan lines 613-1197)

Scanned 2026-11-11. Read-only: no tracked file changed, no git command that writes, no test run.
Read: the plan (whole file; line numbers below are of `ai-trader/research/plans/2026-11-10-supervisor.md` as it stands),
the spec rev 2 (sections 3, 4.1-4.6, 5.3-5.6, 6, 8, 10, 11.1, 11.2 in full), `progress.md`, `controller-notes.md`,
`baseline.md`, `task-2-report.md` (interface only), and in the tree at the live tip: `aitrader/news_live.py`
(`run`/`_run` 1393-1456, `check_stops` 833-912, `_look_at_stops` 1039-1066, `_step` 1341-1390, `_sell`/`_log_trade`
818-828 and 1095-1105, `_step_measured` 636-662), `aitrader/notify.py`, `aitrader/journal.py` 1-110,
`aitrader/__main__.py` 1-160 and 297-300, `aitrader/data.py` `load_config`, `config.json` (`calendar`, `alerts`, `news`,
`market`), `.gitignore`, `tests/test_quiet_hours.py`, `tests/test_config_constants.py`, `BUILD_CLAIMS.md`.
Tasks 2-8 are judged by their plan text (not in this tree). "nl" = `aitrader/news_live.py`. "F n" = finding n below.

## Pairs that share a file or an interface (at least one task in 10-17)

Who writes a file first: `tests/test_supervise.py` Task 3 (`Procs`); `config.json` `supervisor` Task 3 (three keys), the
rest Task 10; `aitrader/supervise.py`, `tests/helpers/dummy_child.py` Task 10; `aitrader/deadman.py`,
`tests/helpers/http_stub.py` Task 13; `aitrader/uptime.py`, `tests/test_uptime.py` Task 16; `scripts/drill_supervisor.py`
Task 17.

| Tasks | Produces -> consumes | Found |
|-------|----------------------|-------|
| 2 -> 10-17 | `no_phone.clean_env(**extra)` -> every child and parent a test starts | agree. `extra` comes last (Task 2 report), so `ParentLines` can pass the made-up topic; a child then inherits it, and `engine_child.py` stubs `notify.send` |
| 2 -> 13, 14, 16 | `ownerlines.render / priority / held_text / sold_text / hhmm`, `WORDS["cause"]`, `["R4b.why"]` (4 keys), `["R5e.why"]` (4, 5, 6), `PARTS` -> the parent's lines, R5e in `--status`, R4c/R9/R11 in `close_lines` | agree on names and fields (`time`, `time2`, `date`, `cold_time`, `off`). `gap_line`'s dict carries `cold_time`, which `render("R4", cold_time=...)` takes. Where `{held}` comes from when there is no beat: F 11 |
| 3 -> 10 | `supervisor` block begun with `max_line_bytes` 1200, `held_names_in_line` 6, `free_text_max_chars` 200 -> Task 10 completes it; `SPEC` in the test holds the same three values | agree |
| 3 -> 10, 11 | `tests/test_supervise.py`, `Procs` (`beat`, `wait_beat`, `wait_for(fn, timeout)`, `dead`, `state`, `sent_file`) -> `Foundations`, `Parents(Procs)` | agree. Task 13 and 21 use `self.tmp` and `self.paths`; neither name is fixed by Task 3 or 11: the briefs name them |
| 3 -> 10, 14 | engine lock text `{"pid", "started_at"}` -> `take_lock` "as the engine's"; `--status` reads both lock files | agree. The same few lines are then written twice (F 18d) |
| 3 -> 12, 17 | `engine_child.py ... [news-live options]` -> `child_cmd` of a parent (the parent appends `--until`, `--supervised`) | options pass through. The engine's own end test reads the real New York clock: F 1 |
| 4 -> 12 | heartbeat `pid`, `phase`, `market_open`, `held {sym: {stop, checked_at}}`, `blind`, `at`, `code` -> `beat_view`, `first_look_done`, `mark`, `up`, `code` | agree on every key. The "stops" beat inside `check_stops` is written before `_covered` moves (nl:841 against nl:903), so only the beat after the look can give `up`: as Task 12 wants. `checked_at` is the look's START (nl:834, 869, 903): F 2 |
| 5 -> 11, 13, 14 | exit 4, 5, 6, 7; `news-live --check`; a supervised engine leaves R5d to the parent | agree: core table 723-725, R5a/R5b/R5d at 929, `--clear-halt` runs `--check` (1014) |
| 5 -> 17 | E1 once per New York day and symbol; a mismatch blocks buys for the process -> drill e "the next start sent E1" | disagree: F 4 |
| 6 -> 12 | SELL rows of `news_trades.jsonl` with `symbol`, `stop`, `price`, `logged_at` (nl:826, 1096) -> `up.sold`, R1's `{sold}` | fields exist. `logged_at` is whole seconds, compared with a float: F 14 |
| 7 -> 12 | `code_stamp()` after the first look -> `up.commit` null, a `code` row at the first beat that carries `code.commit` | agree |
| 8 -> 10, 11 | `--supervised PID`, 143 on a planned stop, `PR_SET_PDEATHSIG`, sleep slices -> the dummy "as the engine does"; the core's `stop(child, "planned")` | agree. The dummy repeats the `prctl` lines (F 18d) |
| 9 -> 10-17 | lands Tasks 2-8 only | agree: `--supervised` is live and unused until Task 20 |
| 10 -> 11 | `Paths`, `append_row`, `read_rows`, `prune_rows`, `load_state`/`save_state`, `take_lock`, `dummy_child.py` (`--until`, `--supervised`), the config keys -> `main`, `restart_core`, `Parents` | agree. What the dummy does with `--until` is not said; Task 11 test 9 needs "nothing" (F 1) |
| 10 -> 12 | `session_hours(day, cal)` -> `open_seconds`; state `last_commit`; dummy run keys `held`, `blind`, `stop_age_s`, `commit`, `open` | agree; early close 2026-11-27 is in `config.json` `calendar.early_close` |
| 10 -> 13 | `alerts.ntfy_base_url`, state `alerts {hour, sent, capped}`, the import test | agree. No day counter for alert ids in the state file: F 13 |
| 10 -> 14 | `Paths.relayed`, `.lock`, `.engine_lock`, `.state`; `until_ny`, `launch_*`, `parent_stale_seconds`, `long_timeout_*` | agree |
| 10 -> 15 | state `handover {at, last_look}`, cleared on another day; `handover_times_ny`, `min/max_leg_minutes` | agree |
| 10 -> 16 | `supervise.read_rows`, `supervise.session_hours`; `report_days`, `uptime_target`, `mark_gap_max_seconds`, `up_hb_max_seconds` | agree |
| 10 -> 17 | `load_cfg`, `--config FILE`, the dummy | agree. The `--fast` list (1154) must also scale `backoff_first_seconds`: back-offs of 1..16 s (31 s) never put 5 restarts inside a 10 s window, drill c would not trip. The task's own test shows it; no ruling needed |
| 10 -> 20, 22, 26, 27 | `SWITCHES`, `SWITCHES_ON` -> one commit per switch | agree |
| 10 -> 21 | `Paths.deadman`, the `deadman` keys, `session_hours` -> `Deadman`, `window_open` | agree |
| 10 -> 23 | `read_rows` (bad line skipped), `prune_rows` -> `slots.read_receipts` (the same contract), "once a day drops lines older than" | the same reader twice: F 18d |
| 10 -> 25 | `session_hours`, the `watcher` keys, `alerts.ntfy_base_url` | agree; `drill_from` and `slots` are outside the compared keys of Task 10's test |
| 11 -> 12 | `watch(child, ran_s)`, `stop(child, "hang")`, `emit`; "ages never use the injected clock" -> `beat_view(hb, mtime, child_pid, now)` | agree. Whether `stop_age_s` grows between beats: F 16 |
| 11, 12 -> 13 | per-test config overrides are needed from Task 11 test 6 (`planned_stop_grace_seconds` 1) and Task 12 (`hang_seconds` 2, the switch); Task 13 says `Parents` "gains" them | the same edit named twice (as Ruling 5): the first user adds it, Task 13 leaves it |
| 11 -> 13 | the ways out (halt, trip, lock_held) and the child's `env` -> R5a-R5d, R3/R3b/R3c, R5c | agree; state `halt` is written by Task 11 and first asserted in Task 13 |
| 11 -> 14 | `sup_stop.why`, the two lock files, `sup_start.timeout_ms`, the launch pair | agree; `/proc/<pid>/cmdline` of the live launch command does name `aitrader.supervise` |
| 11 -> 15 | `watch` answers "handover" -> `(76, "handover")`, `sup_stop` "handover" | agree |
| 11 -> 16 | rows `sup_start`, `start`, `exit`, `tripped`, `sup_stop` | agree |
| 11 -> 17 | `supervise.main(argv, child_cmd=, env=, clock=)`, `--state-dir`, `--config` | agree but for the engine child's `--until` (F 1) |
| 11 -> 19 | the last stdout line, `launch.command` | agree with spec 4.4's table (75 prints "tripped", `sup_stop.why` is "crash_loop") |
| 11, 15 -> 21 | "signal", "orphaned", "handover" exits -> `leave(now, why, held, ...)` | `leave` has no window: F 8 |
| 12 -> 13 | rows `hang`, `stale_stops`, `up`, `code` -> R2, R6/R6b, R1, R4/R4b | R6, R1, R4 agree. R2's kill form: F 5 |
| 12 -> 14 | the last `mark` (`dm`, `left`, its `t`) -> `mark_age_s`, `deadman_ok`, `ntfy_left` | agree |
| 12 -> 15 | `up.handover_s` null -> filled | agree |
| 12 -> 16 | `mark` (`hb`, `stop`, `n`, `left`), `up` (`down_s`, `blind_s`, `handover_s`, `held`), `code` | agree. Names with stops are only in `up` rows: F 11 |
| 13 -> 14 | `alert` rows `{id, kind, sent, text}`, `id` = `<kind>-<n>` -> `unsent`, `--relayed`; R10 listed at once | agree (the test's "R4-2", "R10-4" fit). F 13 |
| 13 -> 16 | `alert` rows -> `ntfy_failed`, R11 "more unprotected minutes than the R4, R4b and R4c rows reported" | the rows carry no minutes: F 6 |
| 13 -> 17 | `NtfyStub`, the cap of 6 -> drills count R1, R2, R3, R6 | drill a asks for 7 R1 in one hour: F 3 |
| 13 -> 20 | `--net-check` | agree |
| 13 -> 21 | `Sender.publish/request/results`, `sync=True`, `NtfyStub.pending/delivered/advance/cancel_answers` | names agree. A third trip has no line: F 9. The stub's poll lines: F 10 |
| 13 -> 22 | `NtfyStub` corrected from the real replies | agree |
| 13 -> 25 | `NtfyStub` poll -> `watch-check`'s one read | F 10 |
| 14 -> 15 | after `sup_stop` "handover" the action is `launch`, also on a day with two trips | agree |
| 14 -> 17 | "alive = cmdline names `aitrader.supervise`" against the `cloud` parent (`drill_supervisor.py cloud DIR`) | no conflict as long as `cloud-check --alive` reads the lock's pid itself (as 1166 says), not `status()` |
| 14 -> 19, 23 | `--status --watchdog`, `--relayed`; `status()` -> the `engine` block of a receipt | agree: all eight receipt fields are in the status keys |
| 15 -> 16, 28 | `handover_s`, `sup_stop` "handover" rc 76 | agree |
| 16 -> 19 | `uptime-report --day --notify` | agree |
| 16 -> 21 | R9 from a `cancel_failed` row with `dm3` false; `alarms` = the day's `new_seq` rows | R9 agrees. `new_seq` is also written on a normal morning: F 7 |
| 16 -> 22, 28 | the day's block -> "`dm` true through the window, `left` falling by about one per 3 minutes" | the block has neither: F 12 |
| 16 -> 23, 25 | `uptime.py` gets the slot and watcher columns | agree |
| 17 -> 20 | `all` at the real numbers, `cloud`, `cloud-check` | F 1, F 2, F 3 decide whether `all` can print seven PASS at the real numbers |
| 17 -> 21, 22 | `guard` already knows `phone --with-owner`; the mode is added in Task 21 | agree |

## Each task against itself

| Task | Tests against code, files created against files touched, commands | Found |
|------|--------------------------------------------------------------------|-------|
| 10 | 8 tests named, "8 tests OK". `SPEC` + `DEADMAN` + `WATCHER` + 5 switches = every key of spec 10 but `slots`, plus `until_ny`, `free_text_max_chars`. 730 days from 2026-01-01 end on 2027-12-31. `notify.send` already has `a = cfg.get("alerts", {})` (notify.py:36); no existing test pins the address (`tests/test_quiet_hours.py:38` takes any url). `aitrader/__init__.py` is empty, so the import test can pass. `.gitignore` exists with the three engine entries | agree. `take_lock`, `Paths`, `save_state` and the dummy get their first test in Task 11. `load_state` "never raises": F 18c. State key `reported_through` is read by no task |
| 11 | 6 + 10 tests, "16 tests OK". Back-offs 1+2+4+8+16 = 31 s inside 600 s: the sixth crash trips. Exit 3: nine children reach 183 s, past 150. `near_until`: 16:04 is the first true. A 143 nobody asked for counts one restart | agree. Test 4 (second parent "writes nothing") is safe only because the clock starts on a whole minute (no mark falls between the two reads) |
| 12 | 11 tests, "11 tests OK". `open_seconds`: 17:50-18:30 UTC on 2026-11-27 = 600, 14:00-14:40 = 600. `mark_due` three cases | agree with notes. Test 9 (the real engine under a parent): F 1. Test 2 expects exactly 2 starts and 1 `hang` row while "the last run repeats": the script needs a second run that beats. Test 7 wants `down_s` > 0 while a row's `t` is whole seconds: `down_s` must come from the real clock. `sold`: F 14 |
| 13 | 8 tests, "8 tests OK". `may_send`: six pass, the seventh R1 is refused, R6 and R3 pass. `gap_line`: 15:00 UTC is 10:00 New York and 17:00 Israel; 200 s gives R4, 179 s nothing | agree on the tests. R2 with the switch on: F 5. Third trip: F 9. `+ 1 s`: F 18b |
| 14 | 5 tests, "5 tests OK". Action order equals spec 4.4. Launch pair three cases. `unsent` four ids | agree. `child_cmd + ["--check"]`: the dummy of Task 10 has no `--check`, so the test passes another command (any list works). R5e's `{held}`: F 11 |
| 15 | 3 tests, "3 tests OK". Six `handover_due` cases recomputed: F, T, F, T, F, T | agree. `last_look[:4] == "2026"`: F 17 |
| 16 | 5 tests, "5 tests OK". 234 s of 23,400 = 0.99; the marks with `hb` 120 and 180 lie inside the exit-to-up stretch; a 15:00-15:05 gap = 300 s, 4 missing marks; 12,600 s on 2026-11-27. `news_health.jsonl` rows have `at` and `stop_gap_max_s` (nl:650-656) | agree. `out_of(...)` must point the command at a temporary state directory (the command has no `--state-dir`; `journal.STATE` does it). F 6, F 7, F 11, F 12 |
| 17 | 3 tests, "3 tests OK"; "return code 2" for a missing script is right. `guard` three cases | F 1, F 2, F 3, F 4, F 15. "Before it imports `helpers`" against "the `ntfy_base_url` of the drill's config copy": the stub's port exists only after `helpers.http_stub` started; `guard` can be given the 127.0.0.1 address first. No ruling needed |

## Against Global Constraints, the cited spec sections and the controller

- Standard library only for `supervise.py` and `deadman.py` (line 39): every import Tasks 10-15 name is standard library
  or `ownerlines`. `uptime.py` is not under that rule and is reached through `aitrader/__main__.py`, which imports
  `journal` (pandas) at line 45: fine.
- Owner's ruling of 2026-11-11 (no sweep): Tasks 10-17 touch `notify.py`, `config.json` (`supervisor`, `alerts`),
  `__main__.py`, `.gitignore` and new files. None is a file the time machine loads.
- Every number in `config.json` (line 21): one literal is mandated, `send_timeout_seconds + 1 s` (932): F 18b. Drill pass
  marks (1 s, 3 s, 5 s, 30 s, 90 s, `hang_seconds` + 10) are the spec's targets, not thresholds of the logic.
- Tests never reach the network or the live state (line 22): `test_notify_posts_to_the_configured_address` replaces
  `requests.post`; `Sender` talks to 127.0.0.1 only; `supervise.load_cfg()` reads the real `config.json`, read-only.
- Spec 4.3, 4.4, 4.5, 4.6, 8, 10, 11.1 against Tasks 10-17: the departures are the ones the plan lists under "Where the
  plan decides" (items 3, 4, 6, 7, 13, 16). Not listed there and found here: F 5, F 11.
- The controller: Tasks 10-17 are BUILD. The only step a subagent may refuse under `controller-notes.md` is the by-hand
  drill run of Task 17 (F 15). Ruling 1 (no push of the work branch) and Ruling 7 apply unchanged.
- Claims that something already exists, checked in the code: `journal.session_hours` (journal.py:76), `a` in
  `notify.send` (notify.py:36), `alerts` block (three names, no `ntfy_base_url`), `.gitignore`, `scripts/`,
  `news_trades.jsonl` rows with `stop` and `logged_at`, `news_health.jsonl` with `stop_gap_max_s`,
  `journal.verify_chain`, `.cache/` ignored, the `news-live` parser. All there. None missing.

## Findings

1. **Tasks 11, 12, 17 (and 20) - task-vs-code. An engine child under a parent ends at once when the real New York clock
   is past the `--until` the parent hands it.** The parent's clock is injected (734, 742: "10:00 New York on 2026-11-12";
   1154: "moved onto a session morning"), but the child gets `--until <until>` (733) and the engine's loop tests
   `datetime.now(NY)` itself (nl:1427-1428). With `--until 16:05` every test and drill that runs `engine_child.py` under
   a parent (Task 12 `test_the_real_engine_gets_a_code_row_after_its_up_row`, 877; drills a, d, f, 1158-1163; so
   `test_the_fast_drills_pass`) passes in the morning and fails from 16:05 New York on: the child returns 0, the parent
   (its clock at 10:00) counts a crash, and the loop trips. The gate's suite and Task 20's drills run after 16:05 New
   York by rule (line 32, 1270-1271). Only `cloud` names `--until 23:59` (1165). Ruling: every parent a test or a drill
   starts with `engine_child.py` gets `--until 23:59` (as `start()` of Tasks 5 and 7 does), the minute 23:59 New York
   is the known ceiling, and the dummy child takes `--until` and ignores it.
2. **Task 17 (and 20) - task-vs-code. Drill f at the real numbers sits on the threshold.** One held name and quote
   stubs of 60 s (1163) against `stops_stale_seconds` 120: a name's stamp is the START of the look
   (nl:834, 869, 903), looks follow back to back, so the stamp the parent can see is 60 s old when it appears and 120 s
   (121 s across the 1 s sleep, nl:1451) when the next one replaces it. "One `stale_stops` start row, one R6" then
   happens zero times or many times by the half-second tick. `--fast` hides it: 4 s quotes against 3 s (1154) is the
   opposite order. Spec 11.1 (f) says only "quote stubs that take 60 s each". Ruling: drill f holds three names (as
   drill a's engine part does): a look costs 180 s (12 s fast), the stamp stays over the threshold, and a beat after
   every quote keeps the hang rule quiet.
3. **Tasks 13 and 17 - task-vs-task. Drill a asks for seven R1 lines in one clock hour; the cap gives six.** Drill a
   = 6 kills of the dummy, "then once with the engine child", pass mark "one R1 per kill" (1158). R1 is counted
   against `max_alerts_per_hour` 6 and held back above it (931; test 965-967), the count lives in the state file and
   survives a new parent, and without `--fast` the numbers are those of `config.json` (1154). Ruling: the engine-child
   part of drill a is its own parent on its own state directory (its own count); the first part stays at six.
4. **Tasks 5 and 17 - task-vs-task. Drill e's pass mark cannot hold after the first mismatch.** "Wherever the book
   disagrees with the journal's last row the next start sent E1" (1162), but E1 goes out once per New York day and
   symbol (316), and a mismatch blocks every new buy for the process (315). After a BUY the book does not know, the
   last row stays that BUY: every later round starts on the same mismatch, with no E1 and no more buys for the rest of
   the 200 rounds. Spec 11.2 step 2 asks for "no mismatch that check 4 missed". Ruling: a mismatch counts as said when the next start left a `news_errors.jsonl` row with
   `where` "book_mismatch" (or `buys_blocked` "book_mismatch" in the heartbeat); E1 is asked for only the first time a
   symbol mismatches; after a round that found one, the next round starts from a fresh state directory.
5. **Tasks 12, 13 (and drill b of 17) - task-vs-spec. R2's kill form cannot be filled "at a `hang` row", and nothing
   stops R1 from following it.** The R2 text (spec 8) carries the restart time and `{blind_s}`, both known only at the
   next `up`; 929 says "R2 at a `hang` row". A hang kill is also "the core's crash path (counted)" (839), and R1 is
   sent "when a restart episode ends" (929) with no exception, so one hang gives R2 and, 60 s later, R1 (two counts
   against the cap). Spec 3 row 2 names R2 alone; spec 11.2 step 2: "one R2". Ruling: switch on: R2 is sent at the
   first `up` after the hang kill, with that `up`'s time and `blind_s`, and that episode sends no R1; switch off: the
   "not killed" form at the `hang` row, as written.
6. **Tasks 13 and 16 - task-vs-task. R11's rule needs minutes the `alert` rows do not carry.** `close_lines` sends R11
   on "more unprotected minutes than the day's R4, R4b and R4c `alert` rows reported" (1114). An `alert` row is `id`,
   `kind`, `sent`, `text` (spec 4.6; 928): the minutes exist only inside the Hebrew text. And an R4c row never exists:
   the parent is the log's only writer (spec 4.1) and `uptime-report` is read-only (1111). Task 16 may not edit
   `supervise.py`. Ruling: Task 13 writes the numbers of a line into its `alert` row (`m` for R4 and R4b at least);
   Task 16 sums `m` over the day's R4/R4b rows and counts the R4c of the same call as reported.
7. **Tasks 16 and 21 - task-vs-task. `deadman.alarms` would count one "alarm" on every normal morning.** Task 16:
   `alarms` = "the day's `new_seq` rows: each is an alarm that went out" (1112). Task 21 takes a new `seq` (row
   `new_seq`) whenever the stored one is within `seq_margin_seconds` of `due_at` or past it (1304), and the file is
   removed only in the undo case (1310): after a normal close (DM3, then the cancel, 1303) yesterday's `seq` is past
   due, so the first ping of the next day writes `new_seq`. The two-week page, on which question 3 is decided, would
   show an alarm a day. Ruling: after a confirmed cancel (the close, a trip or halt whose line was said) the parent
   removes `state/news_deadman.json`; the next arming writes `armed`; `new_seq` keeps the meaning Task 16 reads.
8. **Tasks 11, 15 and 21 - task-vs-task. `leave()` has no window, so a stop after the window closed arms DM2.**
   `leave(now, why, held, said, text)` (1299) leaves "one last ping with DM2" for "handover", "signal", "orphaned"
   (1305), and `main` calls it "on every way out" (1311). The window closes at 16:01 (13:01 on 2026-11-27) and the
   engine runs to 16:05 with a handover listed at 14:17 (649). So the 14:17 handover of 2026-11-27, and any stop signal
   or 110-minute handover between 16:01 and 16:05 (after which `--status` answers `after_hours`, 1021, and nobody
   relaunches), leaves "המפקח נעצר ... סטופים לא נבדקים" to arrive 10 minutes later with the market closed. Spec 6
   ties every ping to the open window. Ruling: `main` calls `leave` for "handover", "signal" and "orphaned" only while
   `window_open`; after the window nothing is published.
9. **Tasks 13 and 21 - task-vs-task. A third trip of a day has no line, and `leave` needs one.** Task 13: "R3, then
   R3b, then nothing" (929). Task 21: at a trip `said` = whether its line was delivered and `text` = that line (1311);
   not said means "replaced by `נשלח באיחור: ` + text" (1305). With no line, `said` and `text` are undefined
   (`text` None in a message, or a crash on the way out). Ruling: at a third or later trip `main` calls
   `leave("crash_loop", held, said=True)`: the waiting message is cancelled (R3b already told him no more lines today).
10. **Tasks 13, 21 and 25 - task-vs-task. The stub's poll lines are too thin for the leak tests that read them.**
    `NtfyStub` answers the poll with lines that have `sequence_id`, `priority`, `time` (926). Task 21 says every line
    ntfy returns carries the topic (1321) and tests that the topic reaches no file on the poll path (1390); Task 25
    tests that `watch-check` never prints a body, against "a NtfyStub that holds BODY-123" (1601-1605). With the stub
    as specified both assertions pass on any code. `tests/helpers/http_stub.py` is in neither task's file list (1286,
    1521). Ruling: Task 13's stub returns ntfy's full line: `id`, `time`, `event`, `topic`, `message`, `title`,
    `priority`, `sequence_id`.
11. **Tasks 13, 14 and 16 - task-vs-spec. `{held}` has no source when the child never wrote a beat.** R3, R3b, R3c,
    R5a, R5b, R5e and R4c all say "פתוח: {held}" (spec 8). The parent's only source of names and stops is the
    heartbeat (`Paths` has no book file, 624; 927), `uptime.jsonl` carries them only in `up` rows, and the heartbeat is
    git-ignored. A child that leaves with 5, 6 or 7 leaves before the trader is built and writes no beat (312); on a
    rebuilt VM (spec 3 row 9) there is no old beat either. `held_text({})` is "אין פוזיציות" (126): the owner would be
    told that nothing is open, in a line that says the stops are not checked. Ruling: when there is no beat of the
    current child, the parent (and `status()` for R5e) reads the positions and stops from `state/news_book.json` as
    plain JSON, the way it already reads `news_trades.jsonl` (843): `Paths` gets `.book`. `open_at_close` and R4c's
    `{held}` in Task 16 are the `held` of the day's last `up` row.
12. **Tasks 16, 22 and 28 - task-vs-task. The day's block has no `dm` and no way to see how fast `left` falls.** Task 22
    reads "`uptime-report --day` shows `dm` true through the window ... `left` falling by about one per 3 minutes and no
    faster ... no `ping_failed` from a 429" (1424; list A, 1664). `day_report`'s keys (1112) are `deadman {alarms,
    ping_failed, cancel_failed}` and `left_min`; no later task adds to them. Ruling: the report stays as Task 16 has it
    (spec 11.2's page lists the alarms, the failed calls and the lowest `left`); Tasks 22 and 28 read `dm` and `left`
    from the `mark` rows of `git show origin/<branch>:ai-trader/state/uptime.jsonl`.
13. **Tasks 10, 13 and 14 - task-vs-task. Alert ids must stay unique across the five parents of a day.** `id` =
    `<kind>-<n>`, "n counting the day's alerts" (928); `unsent` and `--relayed` match by id within a day (1012-1013).
    The state file has `alerts {hour, sent, capped}` only (634). A counter kept in the process starts at 1 after every
    handover: a second "R1-1" would read as already relayed, or as sent. Ruling: at `sup_start`, `n` continues from the
    `alert` rows of that New York day already in `uptime.jsonl`.
14. **Task 12 - task-vs-code. `sold` compares a whole-second stamp with a float.** `sold` = the SELL rows "whose
    `logged_at` is at or after the real time (`time.time()`) at which the previous child ended" (843). `logged_at` is
    `journal.now_utc()`, cut to whole seconds (journal.py:54-55; nl:1096). A sale the new child makes in the same clock
    second in which the old one ended is left out of `up.sold` and of R1's "נמכר בהפעלה". No test in Tasks 12-17 has a
    non-empty `sold`. Ruling: the reference time is cut to its whole second before the comparison.
15. **Task 17 (and 21) - task-vs-controller. The by-hand drill run against "run only unit tests".** 1195 and 1411 ask
    for `python3 scripts/drill_supervisor.py all --fast --rounds 20` (seven PASS); `controller-notes.md` line 37 says
    "Run only unit tests", and that file wins over the brief. Drills b, d, e and g are in no unit test, so a subagent
    that obeys the notes hands them untested to Task 20's landing. Ruling: the Task 17 and Task 21 briefs say that this
    one command is required and allowed (temporary directories, stub children, the `env -u ...` prefix), and its
    seven lines go into the report.
16. **Tasks 11 and 12 - task-vs-itself. Whether a stop stamp ages between beats.** "A stamp inside a beat is aged
    against that beat's own `at`" (734) read alone gives a `stop_age_s` that stands still until the next beat: an
    engine 100 s into one call, with a stamp that was 100 s old at its last beat, would show 100, not 200, in `mark`,
    in the stale-stops rule and in the uptime number. Spec 4.3 and 4.6 mean the stamp's real age. Ruling:
    `stop_age_s` = (the beat's `at` - the oldest `checked_at`) + the beat's own age (`age_s`, by mtime).
17. **Task 15 - rubric (fragile test, plan-mandated). `last_look[:4] == "2026"` (1083).** `last_look` is taken from
    the beat (1068), and the dummy stamps real time (734): the assertion fails from 2027-01-01. Ruling: assert that
    `last_look` parses as an aware time (`datetime.fromisoformat(...).tzinfo`), not its year.
18. **Tasks 10, 13 (and 23) - rubric. What the plan mandates and a reviewer may call a defect; one ruling each, before
    the wave:** (a) timing asserts "within 1 s" (780-782, 941-942, 807-808) are the spec's own named tests (4.3,
    target 2): kept. (b) `send_timeout_seconds + 1 s` (932) is a literal second in the logic against line 21: either
    accepted as a margin, or the wait is `send_timeout_seconds` alone. (c) `load_state` "never raises" and garbage
    becomes a new day's state (634, 687-688): a halt is forgotten in silence; the engine's own start checks find it
    again, so it is safe, but the parent should write the exception's class to `.cache/supervise.log`. (d) repeated
    logic: `supervise.session_hours` beside `journal.session_hours` (mandated by spec 4.5, with the equality test);
    the lock-file write in `news_live.run` and in `take_lock`; the `prctl` lines in `news_live` and in
    `dummy_child.py` (the dummy must not import pandas); `supervise.read_rows` and Task 23's `slots.read_receipts`
    (one contract: Task 23 should call `read_rows`). Per Ruling 3 these come back to the controller, not to a fix loop.
