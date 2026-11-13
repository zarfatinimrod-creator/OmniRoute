# Pre-flight rulings for Tasks 10-28

Controller rulings made before execution, from the pre-flight scan of 2026-11-11 (40 confirmed findings; P1-P18 are the range 10-17, P19-P40 the range 18-28, in the order of `preflight-10-28-confirmed.json`). The spec is the authority, the plan is its argument, and a ruling here wins over the task brief.

How to use it: read the section of your task. Every ruling that binds a task is quoted in full under that task, with the same id and wording wherever it appears, followed by one line that says what THIS task does about it. Plan line numbers refer to `ai-trader/research/plans/2026-11-10-supervisor.md`. Where a ruling says "the controller", the item is also listed in "For the controller" below. Ruling 12 of the ledger (engine processes in tests get `--until 23:59`) is the same cause as P1; P1 widens it.

## Task 10

### P1 (Tasks 10, 11, 12, 17, 20)

- Finding: The engine ends its loop when the REAL New York clock passes `--until` (news_live.py:1427-1428); only the parent's clock is injected (plan 733-734, 742). With `--until 16:05` every test and drill that starts `engine_child.py` passes in the morning and fails from 16:05 New York on: the child exits 0, the parent at its 10:00 clock counts a crash and trips (Task 12's test at plan 877, drills a, d, f at 1158-1163). The gate's suite and Task 20's drills run after 16:05 by rule (plan 32, 1270-1271).
- Ruling: Every start of `engine_child.py` by a test or a drill gets `--until 23:59` unless the test passes its own `--until`: under a parent (the parent is started with `--until 23:59`, so `main` appends it to the child, plan 733) and without a parent (drills e and g, and `Procs.start_engine` of Ruling 12). `tests/helpers/dummy_child.py` takes `--until` and ignores it. The minute 23:59-00:00 New York is the known ceiling, said in a comment at the one place that adds the option.
- Why: The engine's end test reads the real clock and the default `--until` is 16:05, while the gate runs after 16:05.
- If wrong: Nothing; the minute 23:59-00:00 New York stays a known ceiling.
- This task (Task 10): `dummy_child.py` accepts `--until HH:MM` (plan 637) and never ends on it.

### P13 (Tasks 10, 13, 14)

- Finding: An alert id is `<kind>-<n>`, "n counting the day's alerts" (plan 928), and `unsent` and `--relayed` match by id within a day (plan 1012-1013) across up to five parents a day (spec 4.5). The state file keeps only the hourly counts (plan 634), so a counter kept in the process starts at 1 after every handover: a second "R1-1" hides an unsent line behind a sent or an already relayed one. Every test of Tasks 13-14 runs one parent.
- Ruling: At `sup_start`, n continues from the `alert` rows of that New York day already in `uptime.jsonl`: the next n is one more than the largest n in their ids (a late-success row repeats an id, so the rows are not counted). No new state key.
- Why: The log outlives a parent; the state file's layout stays.
- If wrong: A read of the day's rows at each `sup_start`.
- This task (Task 10): No build: the state file layout of plan 634 stays.

### P18 (Tasks 10, 11, 13, 23)

- Finding: Four things the plan mandates that the reviewer's rubric may call defects: (a) timing asserts "within 1 s" (plan 780-782, 807-808, 941-942); (b) `send_timeout_seconds` + 1 s on the way out (plan 932), a literal second against "no literal threshold" (Global Constraints 21), and a fourth new config key would break "three keys are added"; (c) `load_state` "never raises" (plan 628, 634, 687-688), so a state file that does not parse is forgotten in silence; (d) repeated logic: `supervise.session_hours` beside `journal.session_hours`, the lock-file write in `news_live.run` and `take_lock`, the prctl lines in `news_live` and `dummy_child.py`, `supervise.read_rows` and Task 23's `slots.read_receipts`.
- Ruling: (a) Kept: they are the spec's named tests (spec 4.3, target 2, 5.3); a reviewer's finding on them returns to the controller (Ruling 3). (b) On its way out the parent gives the worker `send_timeout_seconds` alone: no `+ 1 s`, no new config key, no literal. (c) Kept: `load_state` never raises; when the file does not parse, the exception's class name (never its text) is written to the parent's log `.cache/supervise.log`, by `main` (Task 11), because Task 10 has no log to write to. (d) Accepted for `session_hours` (spec 4.5 with its equality test), the lock write and the prctl lines (the dummy must not import pandas; `supervise` must not import the engine). Task 23's `slots.read_receipts(path)` returns `supervise.read_rows(path)`.
- Why: (b) is the only real conflict and a result that misses by a hair counts as not delivered (the safe side); (c) is the plan's own decision (Review Focus 4), safe because the start checks find the cause again.
- If wrong: (b): a trip or halt line that arrives in the last instant is treated as not said, and the alarm becomes the late line.
- This task (Task 10): (c): `load_state(path, ny_day) -> dict` still never raises. (d): `session_hours`, `take_lock`, the dummy's prctl lines stay as the plan has them.

## Task 11

### P1 (Tasks 10, 11, 12, 17, 20)

- Finding: The engine ends its loop when the REAL New York clock passes `--until` (news_live.py:1427-1428); only the parent's clock is injected (plan 733-734, 742). With `--until 16:05` every test and drill that starts `engine_child.py` passes in the morning and fails from 16:05 New York on: the child exits 0, the parent at its 10:00 clock counts a crash and trips (Task 12's test at plan 877, drills a, d, f at 1158-1163). The gate's suite and Task 20's drills run after 16:05 by rule (plan 32, 1270-1271).
- Ruling: Every start of `engine_child.py` by a test or a drill gets `--until 23:59` unless the test passes its own `--until`: under a parent (the parent is started with `--until 23:59`, so `main` appends it to the child, plan 733) and without a parent (drills e and g, and `Procs.start_engine` of Ruling 12). `tests/helpers/dummy_child.py` takes `--until` and ignores it. The minute 23:59-00:00 New York is the known ceiling, said in a comment at the one place that adds the option.
- Why: The engine's end test reads the real clock and the default `--until` is 16:05, while the gate runs after 16:05.
- If wrong: Nothing; the minute 23:59-00:00 New York stays a known ceiling.
- This task (Task 11): `Parents.run_parent` and `spawn_parent` pass `--until 23:59` when the test's own argv has no `--until`. Tests that pass `--until 10:00`, `09:55` or `10:02` (plan 810-815) keep theirs.

### P8 (Tasks 11, 15, 21) — OWNER-FACING

- Finding: `leave()` has no window (plan 1299), and `main` calls it on every way out (plan 1311), so "handover", "signal" and "orphaned" leave one last ping with DM2 for 10 minutes (plan 1305) also after the window closed at the session's close + 60 s (plan 1292). The 14:17 handover of 2026-11-27 (close 13:00), and any stop signal or `max_leg_minutes` handover between 16:01 and 16:05, put "the supervisor stopped, stops are not checked" on the phone with the market closed; `--status` answers `after_hours` from 16:00 (plan 1021), so nobody relaunches.
- Ruling: `main` calls `leave` for "handover", "signal" and "orphaned" only while `window_open(now, cal, sup)` is true. After the window nothing is published.
- Why: Spec 6: pings go out only while the window is open; after the close only DM3 can arrive.
- If wrong: Nothing: `tick` has already disarmed at the window's close, so nothing waits.
- This task (Task 11): No build here: `leave` does not exist until Task 21.

### P16 (Tasks 11, 12) — OWNER-FACING

- Finding: "A stamp inside a beat is aged against that beat's own at" (plan 734) read alone gives a `stop_age_s` that stands still until the next beat. Inside one long call (a scorer call of 90 s, a poll of up to 100 s, no beat inside) the parent would never see the stamp pass 120 s, which is the "long call" case of spec 3 row 3, and `mark.stop` and the stale-stops part of the uptime number come out too low. The plan's stale test (plan 866) passes under both readings.
- Ruling: `stop_age_s` = (the beat's `at` - the oldest `checked_at`) + the beat's own age (`age_s`, by the heartbeat file's mtime).
- Why: Spec 4.3 and 4.6 ask for the stamp's age now, not at the last beat.
- If wrong: None found: both parts are already measured.
- This task (Task 11): Plan line 734 reads with this addition.

### P18 (Tasks 10, 11, 13, 23)

- Finding: Four things the plan mandates that the reviewer's rubric may call defects: (a) timing asserts "within 1 s" (plan 780-782, 807-808, 941-942); (b) `send_timeout_seconds` + 1 s on the way out (plan 932), a literal second against "no literal threshold" (Global Constraints 21), and a fourth new config key would break "three keys are added"; (c) `load_state` "never raises" (plan 628, 634, 687-688), so a state file that does not parse is forgotten in silence; (d) repeated logic: `supervise.session_hours` beside `journal.session_hours`, the lock-file write in `news_live.run` and `take_lock`, the prctl lines in `news_live` and `dummy_child.py`, `supervise.read_rows` and Task 23's `slots.read_receipts`.
- Ruling: (a) Kept: they are the spec's named tests (spec 4.3, target 2, 5.3); a reviewer's finding on them returns to the controller (Ruling 3). (b) On its way out the parent gives the worker `send_timeout_seconds` alone: no `+ 1 s`, no new config key, no literal. (c) Kept: `load_state` never raises; when the file does not parse, the exception's class name (never its text) is written to the parent's log `.cache/supervise.log`, by `main` (Task 11), because Task 10 has no log to write to. (d) Accepted for `session_hours` (spec 4.5 with its equality test), the lock write and the prctl lines (the dummy must not import pandas; `supervise` must not import the engine). Task 23's `slots.read_receipts(path)` returns `supervise.read_rows(path)`.
- Why: (b) is the only real conflict and a result that misses by a hair counts as not delivered (the safe side); (c) is the plan's own decision (Review Focus 4), safe because the start checks find the cause again.
- If wrong: (b): a trip or halt line that arrives in the last instant is treated as not said, and the alarm becomes the late line.
- This task (Task 11): (a): the 1 s asserts of `ParentLoop` stay. (c): `main` writes the class name of the state file's parse error to `.cache/supervise.log`. How `load_state` hands that class name to `main` is not fixed by the texts; see "For the controller".

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 11): `Parents`' config copy sets the five switches explicitly.

## Task 12

### P1 (Tasks 10, 11, 12, 17, 20)

- Finding: The engine ends its loop when the REAL New York clock passes `--until` (news_live.py:1427-1428); only the parent's clock is injected (plan 733-734, 742). With `--until 16:05` every test and drill that starts `engine_child.py` passes in the morning and fails from 16:05 New York on: the child exits 0, the parent at its 10:00 clock counts a crash and trips (Task 12's test at plan 877, drills a, d, f at 1158-1163). The gate's suite and Task 20's drills run after 16:05 by rule (plan 32, 1270-1271).
- Ruling: Every start of `engine_child.py` by a test or a drill gets `--until 23:59` unless the test passes its own `--until`: under a parent (the parent is started with `--until 23:59`, so `main` appends it to the child, plan 733) and without a parent (drills e and g, and `Procs.start_engine` of Ruling 12). `tests/helpers/dummy_child.py` takes `--until` and ignores it. The minute 23:59-00:00 New York is the known ceiling, said in a comment at the one place that adds the option.
- Why: The engine's end test reads the real clock and the default `--until` is 16:05, while the gate runs after 16:05.
- If wrong: Nothing; the minute 23:59-00:00 New York stays a known ceiling.
- This task (Task 12): `test_the_real_engine_gets_a_code_row_after_its_up_row` (plan 877) runs its parent with `--until 23:59` (through the Task 11 helper).

### P5 (Tasks 12, 13, 17) — OWNER-FACING

- Finding: R2's kill form (spec 8: "... נהרג והופעל מחדש ב-{HH:MM:SS}. סטופים לא נבדקו {blind_s} שניות ...") needs the restart time and `{blind_s}`, which exist only at the next `up`, yet plan 929 sends R2 "at a hang row"; `render` raises KeyError on a missing field. A hang kill also takes the core's crash path (plan 839), and R1 is sent at the end of every episode with no exception (plan 929): one hang gives R2 and, 60 s later, R1 (two counts against the cap), where spec 3 row 2 and spec 11.2 step 2 name R2 alone.
- Ruling: Switch on: R2 is sent at the first `up` after the hang kill, with that `up`'s time (on `owner_tz`) as `{HH:MM:SS}`, that `up`'s `blind_s` as `{blind_s}`, and the `hang` row's `hb` as `{s}`. That episode sends no R1 when the hang kill was its only fall. If the replacement falls again before it is healthy, R1 goes out as written, with the hang as the first fall (cause "נהרג"). Switch off: the "לא נהרג, המתג כבוי" form at the `hang` row, as written.
- Why: The kill form's fields exist only at the restart's `up`, and the spec names one R2 for one hang.
- If wrong: One R2 waits for the restart (up to `hang_seconds` + the restart, about 190 s at the defaults) instead of going out at the hang row.
- This task (Task 12): No change: the `hang` row keeps `hb` (spec 4.6), which is R2's `{s}`.

### P14 (Tasks 12) — OWNER-FACING

- Finding: `sold` = the SELL rows whose `logged_at` is at or after the real time `time.time()` at which the previous child ended (plan 843), but `logged_at` is cut to whole seconds (journal.py:54-55, news_live.py:1096). A sale the new child makes in the same clock second in which the old one ended is left out of `up.sold` and of R1's "נמכר בהפעלה". The only assertion is `sold == []` (plan 871).
- Ruling: The reference time is cut to its whole second (`int(t)`, rounded down) before the comparison with `logged_at`.
- Why: It matches spec 4.6 (sales since `down_from`, a whole-second `t`).
- If wrong: A sale the old child logged in its own last second is listed too.
- This task (Task 12): `up.sold` compares `logged_at` with the whole second of the reference time.

### P16 (Tasks 11, 12) — OWNER-FACING

- Finding: "A stamp inside a beat is aged against that beat's own at" (plan 734) read alone gives a `stop_age_s` that stands still until the next beat. Inside one long call (a scorer call of 90 s, a poll of up to 100 s, no beat inside) the parent would never see the stamp pass 120 s, which is the "long call" case of spec 3 row 3, and `mark.stop` and the stale-stops part of the uptime number come out too low. The plan's stale test (plan 866) passes under both readings.
- Ruling: `stop_age_s` = (the beat's `at` - the oldest `checked_at`) + the beat's own age (`age_s`, by the heartbeat file's mtime).
- Why: Spec 4.3 and 4.6 ask for the stamp's age now, not at the last beat.
- If wrong: None found: both parts are already measured.
- This task (Task 12): `beat_view` returns `stop_age_s` by this formula.

## Task 13

### P3 (Tasks 13, 17)

- Finding: Drill a asks for seven R1 lines inside one clock hour: 6 kills of the dummy child, then one with the engine child, pass mark "one R1 per kill" (plan 1158). R1 is counted against `max_alerts_per_hour` (6), held back above it, and the count lives in the state file across parents (plan 931, 965-967, 634). The seventh R1 is "capped" and drill a fails, already under `--fast`.
- Ruling: The engine-child part of drill a is its own parent on its own state directory (its own alert count). The first part stays at the spec's six kills of the dummy child. The cap and `may_send` are not changed.
- Why: The engine part needs another `child_cmd`, so it is a second parent anyway; its own directory keeps the cap and the spec's six kills untouched.
- If wrong: Nothing; drill a no longer proves that a seventh R1 in one hour is capped (Task 13's test proves that).
- This task (Task 13): No build. The cap and its test stay as written.

### P5 (Tasks 12, 13, 17) — OWNER-FACING

- Finding: R2's kill form (spec 8: "... נהרג והופעל מחדש ב-{HH:MM:SS}. סטופים לא נבדקו {blind_s} שניות ...") needs the restart time and `{blind_s}`, which exist only at the next `up`, yet plan 929 sends R2 "at a hang row"; `render` raises KeyError on a missing field. A hang kill also takes the core's crash path (plan 839), and R1 is sent at the end of every episode with no exception (plan 929): one hang gives R2 and, 60 s later, R1 (two counts against the cap), where spec 3 row 2 and spec 11.2 step 2 name R2 alone.
- Ruling: Switch on: R2 is sent at the first `up` after the hang kill, with that `up`'s time (on `owner_tz`) as `{HH:MM:SS}`, that `up`'s `blind_s` as `{blind_s}`, and the `hang` row's `hb` as `{s}`. That episode sends no R1 when the hang kill was its only fall. If the replacement falls again before it is healthy, R1 goes out as written, with the hang as the first fall (cause "נהרג"). Switch off: the "לא נהרג, המתג כבוי" form at the `hang` row, as written.
- Why: The kill form's fields exist only at the restart's `up`, and the spec names one R2 for one hang.
- If wrong: One R2 waits for the restart (up to `hang_seconds` + the restart, about 190 s at the defaults) instead of going out at the hang row.
- This task (Task 13): Builds the timing above in the sending points; R1's episode logic skips an episode whose only fall was a hang kill.

### P6 (Tasks 13, 16) — OWNER-FACING

- Finding: R11's rule "more unprotected minutes than the day's R4, R4b and R4c alert rows reported" (plan 1114) needs minutes that an `alert` row does not carry: a row is `id`, `kind`, `sent`, `text` (plan 928, spec 4.6), so the minutes exist only inside the Hebrew text. An R4c row can never exist: the close slot pushes R4c from a read-only command (plan 1111) and the log has one writer (spec 4.1). Task 16 may not touch `supervise.py` (plan 1101).
- Ruling: Task 13 writes the numbers of a line into its `alert` row: an `m` field (the line's minutes) at least for R4 and R4b. Task 16 sums `m` over the day's R4 and R4b `alert` rows and counts the R4c that the same `close_lines` call returns as reported. R11 goes out when the day had a trip, or when the day's unprotected minutes are more than that sum.
- Why: A number field breaks no reader, and parsing Hebrew text for minutes is fragile.
- If wrong: One extra field in two kinds of row.
- This task (Task 13): Adds `m` to the `alert` rows of R4 and R4b.

### P9 (Tasks 13, 21) — OWNER-FACING

- Finding: A third or later trip of a day has no line (plan 929: R3, then R3b, then nothing; spec 4.3), yet `main` must pass `said` = whether "its line" was delivered and `text` = that line (plan 1311), and `said` false builds the waiting message from `text` (plan 1305). Read to the letter that is a TypeError on the way out, or a line reading "None", on a day R3b promised no more lines.
- Ruling: At a third or later trip of a day `main` calls `leave("crash_loop", held, said=True)`: the waiting message is cancelled.
- Why: R3b has already told the owner that no more lines come today, and these are the signature's own defaults (`said=True`, `text=None`, plan 1299).
- If wrong: Nothing: no alarm and no late line after the third trip, as R3b announced.
- This task (Task 13): No build: R3, R3b, then nothing stays.

### P10 (Tasks 13, 21, 22, 25)

- Finding: `NtfyStub` answers the poll with lines of `sequence_id`, `priority`, `time` only (plan 926). Task 25's test that `watch-check` never prints a body against "a NtfyStub that holds BODY-123" (plan 1601-1605) then cannot fail, and Task 21's poll-path topic test (plan 1390-1391) only catches the topic in an error's URL, although every real line carries the topic (plan 1321). Neither task may edit `tests/helpers/http_stub.py` (plan 1286, 1521).
- Ruling: Task 13's stub returns ntfy's full line for every message on the poll: `id`, `time`, `event`, `topic`, `message`, `title`, `priority`, `sequence_id`. Task 22 confirms the field names on a real reply.
- Why: Without real fields the leak tests of Tasks 21 and 25 assert nothing.
- If wrong: A few more fields in a test stub.
- This task (Task 13): `NtfyStub`'s poll answer carries the eight fields.

### P11 (Tasks 13, 14, 16) — OWNER-FACING

- Finding: R3, R3b, R3c, R5a, R5b, R5e and R4c all say "פתוח: {held}", and the parent's only source of names and stops is the heartbeat (plan 833-834, 927; `Paths` has no book path, 624). A child that leaves with 5, 6 or 7 ends before the trader is built (plan 312) and writes no beat, and on a rebuilt VM there is no old beat (the heartbeat is git-ignored). `held_text({})` is "אין פוזיציות" (plan 126): a false all-clear inside an urgent "stops are not checked" line. `open_at_close` and R4c's `{held}` have no stated source at all (plan 1112).
- Ruling: When there is no beat of the current child, the parent (and `status()` for R5e) reads positions and stops from `state/news_book.json` as plain JSON, the way it already reads `news_trades.jsonl`; every position carries `stop_price` (news_live.py:811). `Paths` gets `.book`. In Task 16, `open_at_close` and R4c's `{held}` are the `held` of the day's last `up` row. On exit 6 the book is unreadable, but R5d has no `{held}`.
- Why: The book is tracked and holds every stop; the heartbeat is neither.
- If wrong: One more file the parent reads; a book written mid-save could be read torn (then the line says what the last readable book said).
- This task (Task 13): Adds `Paths.book` and the book fallback for `{held}` in the parent's lines.

### P13 (Tasks 10, 13, 14)

- Finding: An alert id is `<kind>-<n>`, "n counting the day's alerts" (plan 928), and `unsent` and `--relayed` match by id within a day (plan 1012-1013) across up to five parents a day (spec 4.5). The state file keeps only the hourly counts (plan 634), so a counter kept in the process starts at 1 after every handover: a second "R1-1" hides an unsent line behind a sent or an already relayed one. Every test of Tasks 13-14 runs one parent.
- Ruling: At `sup_start`, n continues from the `alert` rows of that New York day already in `uptime.jsonl`: the next n is one more than the largest n in their ids (a late-success row repeats an id, so the rows are not counted). No new state key.
- Why: The log outlives a parent; the state file's layout stays.
- If wrong: A read of the day's rows at each `sup_start`.
- This task (Task 13): `main` seeds the alert counter at `sup_start` from the day's `alert` rows.

### P18 (Tasks 10, 11, 13, 23)

- Finding: Four things the plan mandates that the reviewer's rubric may call defects: (a) timing asserts "within 1 s" (plan 780-782, 807-808, 941-942); (b) `send_timeout_seconds` + 1 s on the way out (plan 932), a literal second against "no literal threshold" (Global Constraints 21), and a fourth new config key would break "three keys are added"; (c) `load_state` "never raises" (plan 628, 634, 687-688), so a state file that does not parse is forgotten in silence; (d) repeated logic: `supervise.session_hours` beside `journal.session_hours`, the lock-file write in `news_live.run` and `take_lock`, the prctl lines in `news_live` and `dummy_child.py`, `supervise.read_rows` and Task 23's `slots.read_receipts`.
- Ruling: (a) Kept: they are the spec's named tests (spec 4.3, target 2, 5.3); a reviewer's finding on them returns to the controller (Ruling 3). (b) On its way out the parent gives the worker `send_timeout_seconds` alone: no `+ 1 s`, no new config key, no literal. (c) Kept: `load_state` never raises; when the file does not parse, the exception's class name (never its text) is written to the parent's log `.cache/supervise.log`, by `main` (Task 11), because Task 10 has no log to write to. (d) Accepted for `session_hours` (spec 4.5 with its equality test), the lock write and the prctl lines (the dummy must not import pandas; `supervise` must not import the engine). Task 23's `slots.read_receipts(path)` returns `supervise.read_rows(path)`.
- Why: (b) is the only real conflict and a result that misses by a hair counts as not delivered (the safe side); (c) is the plan's own decision (Review Focus 4), safe because the start checks find the cause again.
- If wrong: (b): a trip or halt line that arrives in the last instant is treated as not said, and the alarm becomes the late line.
- This task (Task 13): (a): `test_a_stub_that_never_answers_does_not_delay_a_restart` stays. (b): the wait on the way out is `send_timeout_seconds`.

### P26 (Tasks 13, 21)

- Finding: DM4 and the pause after it use "the header's t" (plan 1307-1308), but a `Sender` result has `left` and `retry_after` only (plan 917); the stub already sends `t=3600` (plan 926). Task 21's file line names `class Deadman`, not a change of `Sender` (plan 1286).
- Ruling: In Task 13's brief each `Sender.results()` entry also has `reset_s` (the `t` of the `RateLimit` header). `results()` keeps its plan signature; Task 21 routes the queue's outcomes between `main` and `Deadman` itself, by tag, in the files it owns.
- Why: One field closes (a); (b) lives in files Task 21 owns, so it needs no ruling.
- If wrong: One field in a result dict.
- This task (Task 13): `Sender` parses `t` from the `RateLimit` header into `reset_s`.

### P27 (Tasks 13, 21, 22) — OWNER-FACING

- Finding: The phone drill's parent sends the parent's own lines to the owner's phone through the same `Sender` and topic: R2 180 s after the freeze in phase `stop` (switch off, so the "לא נהרג, המתג כבוי" form), R1 60 s after the restart in phase `restart`, R4b after the handover when the relaunch takes 180 s or more (plan 1316-1319, 839, 929-930). Task 22 passes each phase on "he reports nothing" or "nothing before" (plan 1422), so by the letter three of five phases fail.
- Ruling: Spec 11.2 step 3 is about the alarm. "Nothing" in Task 22 means no message titled "AI Trader - דממה". Before the drill the owner is told which lines titled "AI Trader - מפקח" belong to it: R2 (the "לא נהרג, המתג כבוי" form) about 180 s after `stop`, R1 about 60 s after `restart`, and R4b after `handover` when the relaunch takes 180 s or more. (The scanner's alternative, `phone` mode giving the topic to the dead-man only, is not taken: the refuter calls the reading free of code and the other one an added path in `main`.)
- Why: The drill tests the dead-man; the parent's own lines are correct behaviour.
- If wrong: The owner may read an expected "מפקח" line as a fault if the message before the drill is not clear.
- This task (Task 13): No build.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 13): No build beyond `Parents`: `ParentLines` inherits the pinned switches.

## Task 14

### P11 (Tasks 13, 14, 16) — OWNER-FACING

- Finding: R3, R3b, R3c, R5a, R5b, R5e and R4c all say "פתוח: {held}", and the parent's only source of names and stops is the heartbeat (plan 833-834, 927; `Paths` has no book path, 624). A child that leaves with 5, 6 or 7 ends before the trader is built (plan 312) and writes no beat, and on a rebuilt VM there is no old beat (the heartbeat is git-ignored). `held_text({})` is "אין פוזיציות" (plan 126): a false all-clear inside an urgent "stops are not checked" line. `open_at_close` and R4c's `{held}` have no stated source at all (plan 1112).
- Ruling: When there is no beat of the current child, the parent (and `status()` for R5e) reads positions and stops from `state/news_book.json` as plain JSON, the way it already reads `news_trades.jsonl`; every position carries `stop_price` (news_live.py:811). `Paths` gets `.book`. In Task 16, `open_at_close` and R4c's `{held}` are the `held` of the day's last `up` row. On exit 6 the book is unreadable, but R5d has no `{held}`.
- Why: The book is tracked and holds every stop; the heartbeat is neither.
- If wrong: One more file the parent reads; a book written mid-save could be read torn (then the line says what the last readable book said).
- This task (Task 14): `status()` uses the same fallback for R5e's `{held}`.

### P13 (Tasks 10, 13, 14)

- Finding: An alert id is `<kind>-<n>`, "n counting the day's alerts" (plan 928), and `unsent` and `--relayed` match by id within a day (plan 1012-1013) across up to five parents a day (spec 4.5). The state file keeps only the hourly counts (plan 634), so a counter kept in the process starts at 1 after every handover: a second "R1-1" hides an unsent line behind a sent or an already relayed one. Every test of Tasks 13-14 runs one parent.
- Ruling: At `sup_start`, n continues from the `alert` rows of that New York day already in `uptime.jsonl`: the next n is one more than the largest n in their ids (a late-success row repeats an id, so the rows are not counted). No new state key.
- Why: The log outlives a parent; the state file's layout stays.
- If wrong: A read of the day's rows at each `sup_start`.
- This task (Task 14): No build: `unsent` and `--relayed` rely on ids that are now unique across the day.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 14): `Status`' helper passes `environ={}` unless the test gives one.

## Task 15

### P8 (Tasks 11, 15, 21) — OWNER-FACING

- Finding: `leave()` has no window (plan 1299), and `main` calls it on every way out (plan 1311), so "handover", "signal" and "orphaned" leave one last ping with DM2 for 10 minutes (plan 1305) also after the window closed at the session's close + 60 s (plan 1292). The 14:17 handover of 2026-11-27 (close 13:00), and any stop signal or `max_leg_minutes` handover between 16:01 and 16:05, put "the supervisor stopped, stops are not checked" on the phone with the market closed; `--status` answers `after_hours` from 16:00 (plan 1021), so nobody relaunches.
- Ruling: `main` calls `leave` for "handover", "signal" and "orphaned" only while `window_open(now, cal, sup)` is true. After the window nothing is published.
- Why: Spec 6: pings go out only while the window is open; after the close only DM3 can arrive.
- If wrong: Nothing: `tick` has already disarmed at the window's close, so nothing waits.
- This task (Task 15): No build here: the handover path calls `leave` only from Task 21 on.

### P17 (Tasks 15)

- Finding: `self.assertEqual(self.state_file()["handover"]["last_look"][:4], "2026")` (plan 1083) holds a year. `last_look` comes from the beat and the dummy stamps real time (plan 1068, 637, 734), so the test fails from 2027-01-01, turns the whole suite red and blocks every later gate; controller-notes lines 49-51 forbid the implementer to change it.
- Ruling: The assertion becomes `self.assertIsNotNone(datetime.fromisoformat(self.state_file()["handover"]["last_look"]).tzinfo)`: `last_look` parses as an aware time.
- Why: It tests what the line means and does not expire.
- If wrong: Nothing.
- This task (Task 15): Plan line 1083 is replaced by the assertion above.

## Task 16

### P6 (Tasks 13, 16) — OWNER-FACING

- Finding: R11's rule "more unprotected minutes than the day's R4, R4b and R4c alert rows reported" (plan 1114) needs minutes that an `alert` row does not carry: a row is `id`, `kind`, `sent`, `text` (plan 928, spec 4.6), so the minutes exist only inside the Hebrew text. An R4c row can never exist: the close slot pushes R4c from a read-only command (plan 1111) and the log has one writer (spec 4.1). Task 16 may not touch `supervise.py` (plan 1101).
- Ruling: Task 13 writes the numbers of a line into its `alert` row: an `m` field (the line's minutes) at least for R4 and R4b. Task 16 sums `m` over the day's R4 and R4b `alert` rows and counts the R4c that the same `close_lines` call returns as reported. R11 goes out when the day had a trip, or when the day's unprotected minutes are more than that sum.
- Why: A number field breaks no reader, and parsing Hebrew text for minutes is fragile.
- If wrong: One extra field in two kinds of row.
- This task (Task 16): `close_lines` compares the day's unprotected minutes with the sum of `m` over R4/R4b rows plus the R4c of the same call.

### P7 (Tasks 16, 21) — OWNER-FACING

- Finding: Task 16 counts each `new_seq` row as "an alarm that went out" (plan 1112). Task 21 rewrites `state/news_deadman.json` after each accepted ping and removes it only in the undo case (plan 1304, 1310), so after a normal close (DM3, then the cancel, plan 1303) yesterday's `due_at` lies hours behind and the next morning's first ping writes `new_seq`. The two-week page that decides question 3 would show one alarm a day.
- Ruling: After a confirmed cancel (the close, or a trip or halt whose line was said) the parent removes `state/news_deadman.json`. The next arming writes `armed`. A cancel that failed (row `cancel_failed`) keeps the file, and the `new_seq` that follows is then a true count. `new_seq` keeps the meaning Task 16 reads. Task 21's test `test_an_alarm_that_already_went_out_gets_a_new_seq_and_the_old_one_is_never_touched` still passes (it writes the old file itself).
- Why: Without it the alarm count on the two-week page is false every day.
- If wrong: A cancel the parent thinks confirmed but ntfy kept leaves no file, so the next morning starts a new seq with no `new_seq` row: one true alarm uncounted.
- This task (Task 16): No build: `alarms` stays the day's `new_seq` rows.

### P11 (Tasks 13, 14, 16) — OWNER-FACING

- Finding: R3, R3b, R3c, R5a, R5b, R5e and R4c all say "פתוח: {held}", and the parent's only source of names and stops is the heartbeat (plan 833-834, 927; `Paths` has no book path, 624). A child that leaves with 5, 6 or 7 ends before the trader is built (plan 312) and writes no beat, and on a rebuilt VM there is no old beat (the heartbeat is git-ignored). `held_text({})` is "אין פוזיציות" (plan 126): a false all-clear inside an urgent "stops are not checked" line. `open_at_close` and R4c's `{held}` have no stated source at all (plan 1112).
- Ruling: When there is no beat of the current child, the parent (and `status()` for R5e) reads positions and stops from `state/news_book.json` as plain JSON, the way it already reads `news_trades.jsonl`; every position carries `stop_price` (news_live.py:811). `Paths` gets `.book`. In Task 16, `open_at_close` and R4c's `{held}` are the `held` of the day's last `up` row. On exit 6 the book is unreadable, but R5d has no `{held}`.
- Why: The book is tracked and holds every stop; the heartbeat is neither.
- If wrong: One more file the parent reads; a book written mid-save could be read torn (then the line says what the last readable book said).
- This task (Task 16): `open_at_close` and R4c's `{held}` = `held` of the day's last `up` row.

### P12 (Tasks 16, 21, 22, 28)

- Finding: Task 22 (plan 1424) and list A of Task 28 (plan 1664) read from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429; `day_report` has `left_min` and counts under `deadman` only (plan 1112), and no later task adds keys. The cause of a failed ping cannot be read from the pushed state at all: `.cache/supervise.log` never reaches git (plan 35) and Task 21 fixes no field of a `deadman` row but `what`.
- Ruling: The report stays as Task 16 has it. Tasks 22 and 28 read `dm` and `left` from the `mark` rows of `git show origin/<branch>:ai-trader/state/uptime.jsonl`. Task 21's `ping_failed` row carries `status` (the HTTP code, or the exception's class name).
- Why: The marks already hold both numbers; only the failed ping's cause was missing from git.
- If wrong: One extra field in one kind of row.
- This task (Task 16): No build.

### P38 (Tasks 16, 21, 22, 28)

- Finding: Task 22 reads from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429 (plan 1424); `day_report` has `left_min` and counts only (plan 1112). Task 22's first proof wants marks with `dm` null while the switch is off (plan 1418), but `Deadman.ok` is a bool and is "the `dm` of a mark" (plan 1296), and plan 841 says null only "until Tasks 13 and 21": a mark with `dm` false fails the proof and shows `deadman_ok` false in `--status`.
- Ruling: The three readings come from the `mark` and `deadman` rows of `state/uptime.jsonl` (Task 28 already names both sources, plan 1659). Task 21's brief adds: "with the switch off or no topic, a mark's `dm` is null". A `ping_failed` row carries `status` (the HTTP code or the exception's class name), as in P12.
- Why: No producer gives those readings in the shape the plan reads them.
- If wrong: One null case and one field.
- This task (Task 16): No build.

## Task 17

### P1 (Tasks 10, 11, 12, 17, 20)

- Finding: The engine ends its loop when the REAL New York clock passes `--until` (news_live.py:1427-1428); only the parent's clock is injected (plan 733-734, 742). With `--until 16:05` every test and drill that starts `engine_child.py` passes in the morning and fails from 16:05 New York on: the child exits 0, the parent at its 10:00 clock counts a crash and trips (Task 12's test at plan 877, drills a, d, f at 1158-1163). The gate's suite and Task 20's drills run after 16:05 by rule (plan 32, 1270-1271).
- Ruling: Every start of `engine_child.py` by a test or a drill gets `--until 23:59` unless the test passes its own `--until`: under a parent (the parent is started with `--until 23:59`, so `main` appends it to the child, plan 733) and without a parent (drills e and g, and `Procs.start_engine` of Ruling 12). `tests/helpers/dummy_child.py` takes `--until` and ignores it. The minute 23:59-00:00 New York is the known ceiling, said in a comment at the one place that adds the option.
- Why: The engine's end test reads the real clock and the default `--until` is 16:05, while the gate runs after 16:05.
- If wrong: Nothing; the minute 23:59-00:00 New York stays a known ceiling.
- This task (Task 17): The drill script starts every parent and every bare `engine_child.py` with `--until 23:59` (the `cloud` row already does, plan 1165).

### P2 (Tasks 17, 20)

- Finding: Drill f at the real numbers sits on its own threshold: with one held name and 60 s quote stubs the name's stamp (the START of the look, news_live.py:834, 869, 903) is 120-121 s old when replaced, against `stops_stale_seconds` 120 (plan 1163, 840). So zero or several `stale_stops` start rows and R6 lines, by sub-second timing. Under `--fast` the 4 s quote stub equals `hang_seconds` 4 (plan 1154), so the hang rule sits on its own threshold too.
- Ruling: Drill f holds three names (as drill a's engine part does): one look costs 180 s at the defaults, 12 s under `--fast`, so the stamp stays over the threshold and turns fresh never. Under `--fast` the hang rule is kept out by drill f's config copy pinning `hang_kill_enabled` to false (record keeper's choice between the refuter's two options, which states no preference: this one needs no new code, because Ruling P29 already makes the drill's copy set every switch to false unless the drill says so). The pass mark stays: one `stale_stops` start row, one R6, no kill.
- Why: Spec 11.1 (f) fixes no count of names; three names keep the stamp clear of the threshold at both scales.
- If wrong: A drill f that passes or fails by chance at Task 20's landing; under `--fast` a `hang` row with `killed_with` "none" may still appear beside the pass.
- This task (Task 17): Drill f's runs hold three names; its config copy keeps `hang_kill_enabled` false.

### P3 (Tasks 13, 17)

- Finding: Drill a asks for seven R1 lines inside one clock hour: 6 kills of the dummy child, then one with the engine child, pass mark "one R1 per kill" (plan 1158). R1 is counted against `max_alerts_per_hour` (6), held back above it, and the count lives in the state file across parents (plan 931, 965-967, 634). The seventh R1 is "capped" and drill a fails, already under `--fast`.
- Ruling: The engine-child part of drill a is its own parent on its own state directory (its own alert count). The first part stays at the spec's six kills of the dummy child. The cap and `may_send` are not changed.
- Why: The engine part needs another `child_cmd`, so it is a second parent anyway; its own directory keeps the cap and the spec's six kills untouched.
- If wrong: Nothing; drill a no longer proves that a seventh R1 in one hour is capped (Task 13's test proves that).
- This task (Task 17): Drill a's engine-child kill runs under a second parent with a temporary state directory of its own.

### P4 (Tasks 17, 20)

- Finding: Drill e's pass mark "wherever the book disagrees with the journal's last row the next start sent E1" (plan 1162) cannot hold after the first mismatch: E1 goes out once per New York day and symbol (plan 316), and a mismatch blocks every new buy (plan 315), so the unknown BUY stays the last row and every later round starts on the same mismatch with no E1. A checker written to the letter prints FAIL e at Task 20's 200 rounds for a false reason.
- Ruling: In drill e a mismatch counts as said when the next start left a `news_errors.jsonl` row with `where` "book_mismatch" (or `buys_blocked` "book_mismatch" in the heartbeat). E1 is asked for only the first time a symbol mismatches. After a round that found a mismatch, the next round starts from a fresh state directory. The start that must say it is left to reach its first idle beat before it is judged or killed, because E1 goes out only after the first look (Task 7, step 5).
- Why: The `news_errors.jsonl` row is written at every mismatched start and is what spec 11.2 asks for ("no mismatch that check 4 missed").
- If wrong: Drill e is a little weaker on E1 itself: only the first mismatch of a symbol is checked for E1.
- This task (Task 17): Drill e's checker applies these four clauses.

### P5 (Tasks 12, 13, 17) — OWNER-FACING

- Finding: R2's kill form (spec 8: "... נהרג והופעל מחדש ב-{HH:MM:SS}. סטופים לא נבדקו {blind_s} שניות ...") needs the restart time and `{blind_s}`, which exist only at the next `up`, yet plan 929 sends R2 "at a hang row"; `render` raises KeyError on a missing field. A hang kill also takes the core's crash path (plan 839), and R1 is sent at the end of every episode with no exception (plan 929): one hang gives R2 and, 60 s later, R1 (two counts against the cap), where spec 3 row 2 and spec 11.2 step 2 name R2 alone.
- Ruling: Switch on: R2 is sent at the first `up` after the hang kill, with that `up`'s time (on `owner_tz`) as `{HH:MM:SS}`, that `up`'s `blind_s` as `{blind_s}`, and the `hang` row's `hb` as `{s}`. That episode sends no R1 when the hang kill was its only fall. If the replacement falls again before it is healthy, R1 goes out as written, with the hang as the first fall (cause "נהרג"). Switch off: the "לא נהרג, המתג כבוי" form at the `hang` row, as written.
- Why: The kill form's fields exist only at the restart's `up`, and the spec names one R2 for one hang.
- If wrong: One R2 waits for the restart (up to `hang_seconds` + the restart, about 190 s at the defaults) instead of going out at the hang row.
- This task (Task 17): Drill b passes with one R2 and no R1 from that episode.

### P15 (Tasks 17, 21)

- Finding: Task 17 (plan 1195) and Task 21 (plan 1411) require the by-hand run `python3 scripts/drill_supervisor.py all --fast --rounds 20` (seven PASS lines), while controller-notes.md says "Run only unit tests" and wins over the brief (lines 3, 37). Drills b, d, e and g are in no unit test (plan 1175 runs a, c, f), so an obedient implementer hands them untested to Task 20's landing.
- Ruling: The briefs of Tasks 17 and 21 name this one command as required and allowed: `env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 scripts/drill_supervisor.py all --fast --rounds 20`, on temporary directories, with stub children, 127.0.0.1 only. Its seven lines go into the report.
- Why: Otherwise four drills run for the first time at the real numbers at the landing.
- If wrong: One allowed exception to "only unit tests", bounded to stubs and 127.0.0.1.
- This task (Task 17): The brief carries the command; the report carries its seven lines.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 17): The drill's config copy sets the five switches; drill b sets `hang_kill_enabled` true.

## Task 18

### P21 (Tasks 18, 19)

- Finding: Task 18 commits the slot files on the live branch and pushes (plan 1208). Task 19 edits every file under `skills/trader/slots/` on `supervisor-build` in the gate clone (plan 1214-1216), whose last merge of the live branch was Task 9's landing, and an implementer may not fetch or merge (controller-notes line 26). Task 19 would find no folder and fail its first step (plan 1235, 1260).
- Ruling: Task 18 stays as written (commit in the controller's checkout on the live branch, push). Before Task 19 is dispatched the controller runs, in the gate clone, `git fetch origin <branch>` and `git merge --no-edit origin/<branch>`, and sees `ai-trader/skills/trader/slots/*.md` there.
- Why: Task 18's commit cannot be made in the gate clone (a push of its HEAD would land Tasks 10-17), and nothing else merges the live branch between Task 9 and Task 19.
- If wrong: One merge in the gate clone.
- This task (Task 18): No change.

### P34 (Tasks 18, 23, 24, 25)

- Finding: (a) Task 23's fixture is made "from the Task 18 reply" (plan 1503), which plan 1204 keeps in the controller's scratch folder with session, task and environment ids; a BUILD implementer has no path to it, and a raw copy puts ids into a public-repo commit. (b) `slots_check(clean_sample, CFG, SLOTS_DIR) == []` (plan 1495-1499) breaks when Task 24 rewrites every slot file and adds the crypto slots, and again when Task 25 edits `news-watch.md`, if CFG or SLOTS_DIR is real; neither task's `git add` holds the fixture or `test_slots.py`.
- Ruling: The controller hands Task 23 a copy of the Task 18 reply with the ids already replaced (task ids by `trig_x`, no session id), by path in the brief. The `slots_check` test builds its own config and its own slot folder in the temporary directory from the sample, and never reads `skills/trader/slots/` or the real `supervisor.slots`.
- Why: The implementer needs the reply without its ids, and the test must not move with later prompt edits.
- If wrong: One sanitised file made by the controller.
- This task (Task 18): The reply stays in scratch; the controller makes the sanitised copy before Task 23.

### P40 (Tasks 18, 20, 24) — OWNER-FACING

- Finding: A `list_triggers` reply reaches a file only by the model typing it again: "each prompt, unchanged, into its file" (plan 1206), "diff each prompt against its file" (plan 1276) and `.cache/triggers.json` every Friday in the trader session (plan 1512; spec 7.1) all rest on that copy. The plan treats a difference as hard evidence: "stop, someone changed it" (plan 1276) and an S1 line pushed to the owner.
- Ruling: The limit is accepted and written in the session log. A difference is read again for that one task (`list_triggers`) before a stop or an S1 line. Because the Friday check runs in the trader session, Task 24's edit of `close.md` adds the sentence: before pushing the S1 line, read the differing task again with `list_triggers` and push S1 only if the difference stands.
- Why: One retyping slip must not read as a changed task.
- If wrong: One more read for a task that differs.
- This task (Task 18): The session log states the limit for the files written from the reply.

## Task 19

### P19 (Tasks 19, 22)

- Finding: The leak test `test_no_prompt_and_no_fixture_names_a_session_a_task_a_topic_or_an_address` reads every file under `tests/fixtures/` as text (plan 1244-1247) and fails on a tracked binary fixture: `tests/fixtures/stock_panel.pkl` matches the third LEAKS pattern with `<email>`. Task 19 cannot change that file (plan 1214), so "4 tests, OK" (plan 1262) is unreachable.
- Ruling: The fixture half of the test skips `*.pkl`: the line becomes `for f in [*SLOTS.glob("*.md"), *(p for p in (ROOT / "tests" / "fixtures").rglob("*") if p.is_file() and p.suffix != ".pkl")]:`. Every other fixture stays under the test, so `tests/fixtures/ntfy/**` and `list_triggers_sample.json` are still read. (The refuter gave "skip `*.pkl`" or "skip any file that is not strict UTF-8" with no preference; the suffix test is the smaller one.)
- Why: A price panel cannot carry a topic or an id; the text fixtures stay under Review Focus 5.
- If wrong: A future binary fixture of another suffix would trip the test again.
- This task (Task 19): Uses the line above.

### P21 (Tasks 18, 19)

- Finding: Task 18 commits the slot files on the live branch and pushes (plan 1208). Task 19 edits every file under `skills/trader/slots/` on `supervisor-build` in the gate clone (plan 1214-1216), whose last merge of the live branch was Task 9's landing, and an implementer may not fetch or merge (controller-notes line 26). Task 19 would find no folder and fail its first step (plan 1235, 1260).
- Ruling: Task 18 stays as written (commit in the controller's checkout on the live branch, push). Before Task 19 is dispatched the controller runs, in the gate clone, `git fetch origin <branch>` and `git merge --no-edit origin/<branch>`, and sees `ai-trader/skills/trader/slots/*.md` there.
- Why: Task 18's commit cannot be made in the gate clone (a push of its HEAD would land Tasks 10-17), and nothing else merges the live branch between Task 9 and Task 19.
- If wrong: One merge in the gate clone.
- This task (Task 19): Dispatched only after the controller's merge; the brief may say the folder is there.

### P22 (Tasks 19, 24, 25)

- Finding: Task 25 creates `skills/trader/slots/watcher.md` (plan 1521) in the folder that two "every file" tests read: Task 19's first test asks every `*.md` that holds "git " for `git merge --no-edit origin/`, `git merge --abort` and the S2 text (plan 1234-1242), and Task 24 adds "every file holds `slot-done <its slot> --start`, `slot-done <its slot>` and `re-run: slot-done`" (plan 1512). `watcher.md` holds `git fetch`, `merge --ff-only` and the stash ban and never commits (plan 1543; spec 7.2), and it is not a slot. Task 25's test changes (plan 1622) exempt nothing.
- Ruling: Both tests skip `watcher.md` by name. Task 24 writes its new assertion with the skip from the start. Task 25 adds the same skip to Task 19's first test: `files = sorted(f for f in SLOTS.glob("*.md") if f.name != "watcher.md")` (the `assertGreaterEqual(len(files), 6)` stays). The leak test still reads `watcher.md`. `watcher.md` keeps only Task 25's own assertions.
- Why: `supervisor.slots` does not exist at Task 19, so a name is the simplest filter.
- If wrong: A slot file ever named `watcher.md` would escape the two tests.
- This task (Task 19): No build: `watcher.md` does not exist yet.

### P23 (Tasks 19, 20, 22, 24, 27) — OWNER-FACING

- Finding: The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs `supervise --status --watchdog` before any git work and syncs last (plan 1219; spec 4.4); a landing is pushed after 16:05, the 16:22 close slot is normally gone and the dashboard does not pull, so a later push is first merged at the end of the 08:07 turn of the next morning. After Task 20, `python3 -m aitrader.supervise` does not exist at 08:07 and plan 1277 orders undo at 09:00; after Task 24 the prompt's first line `slot-done ... --start` is an unknown command; after Tasks 22 and 27 the 08:07 parent runs on the old config, so "dm true through the window" and "one sup_start with handover false" fail on the first day.
- Ruling: Each landing of Tasks 20, 22, 24 and 27 gets one more proof before its `update_trigger` and before its next-day reading counts: after the trader session's next state commit (Global Constraints line 35), that commit has the landing commit as an ancestor (`git merge-base --is-ancestor <landing> <the trader's state commit>` exits 0). If no trader turn will sync before 08:07 New York: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35). The spec's order inside the watchdog turn stays.
- Why: Otherwise the first morning after a landing runs old code or old prompts and fails its own proof.
- If wrong: One more proof per landing, and at times one more question to the owner and one scheduled task.
- This task (Task 19): No build: the order inside `news-watch.md` stays as the spec has it.

### P37 (Tasks 19, 28)

- Finding: List A of Task 28 (plan 1669) and spec 11.2 read the day's uptime, the longest `blind_s` and each start's commit from the trader's close log, but Task 19 gives `close.md` only `uptime-report --day --notify` and the push of `notify` (plan 1220); no prompt tells the trader to write the numbers down.
- Ruling: Task 19's edit of `close.md` adds: copy the day's block of `uptime-report --day` (`uptime`, `longest_blind_s`, `commits`) into the close log.
- Why: Otherwise the last line of list A rests on chance.
- If wrong: One sentence in one prompt.
- This task (Task 19): `close.md` gains the copy step.

## Task 20

### P1 (Tasks 10, 11, 12, 17, 20)

- Finding: The engine ends its loop when the REAL New York clock passes `--until` (news_live.py:1427-1428); only the parent's clock is injected (plan 733-734, 742). With `--until 16:05` every test and drill that starts `engine_child.py` passes in the morning and fails from 16:05 New York on: the child exits 0, the parent at its 10:00 clock counts a crash and trips (Task 12's test at plan 877, drills a, d, f at 1158-1163). The gate's suite and Task 20's drills run after 16:05 by rule (plan 32, 1270-1271).
- Ruling: Every start of `engine_child.py` by a test or a drill gets `--until 23:59` unless the test passes its own `--until`: under a parent (the parent is started with `--until 23:59`, so `main` appends it to the child, plan 733) and without a parent (drills e and g, and `Procs.start_engine` of Ruling 12). `tests/helpers/dummy_child.py` takes `--until` and ignores it. The minute 23:59-00:00 New York is the known ceiling, said in a comment at the one place that adds the option.
- Why: The engine's end test reads the real clock and the default `--until` is 16:05, while the gate runs after 16:05.
- If wrong: Nothing; the minute 23:59-00:00 New York stays a known ceiling.
- This task (Task 20): No build. Drills a, d, e, f, g run after 16:05 New York and must still pass.

### P2 (Tasks 17, 20)

- Finding: Drill f at the real numbers sits on its own threshold: with one held name and 60 s quote stubs the name's stamp (the START of the look, news_live.py:834, 869, 903) is 120-121 s old when replaced, against `stops_stale_seconds` 120 (plan 1163, 840). So zero or several `stale_stops` start rows and R6 lines, by sub-second timing. Under `--fast` the 4 s quote stub equals `hang_seconds` 4 (plan 1154), so the hang rule sits on its own threshold too.
- Ruling: Drill f holds three names (as drill a's engine part does): one look costs 180 s at the defaults, 12 s under `--fast`, so the stamp stays over the threshold and turns fresh never. Under `--fast` the hang rule is kept out by drill f's config copy pinning `hang_kill_enabled` to false (record keeper's choice between the refuter's two options, which states no preference: this one needs no new code, because Ruling P29 already makes the drill's copy set every switch to false unless the drill says so). The pass mark stays: one `stale_stops` start row, one R6, no kill.
- Why: Spec 11.1 (f) fixes no count of names; three names keep the stamp clear of the threshold at both scales.
- If wrong: A drill f that passes or fails by chance at Task 20's landing; under `--fast` a `hang` row with `killed_with` "none" may still appear beside the pass.
- This task (Task 20): Drill f at the real numbers runs with three names; no build.

### P4 (Tasks 17, 20)

- Finding: Drill e's pass mark "wherever the book disagrees with the journal's last row the next start sent E1" (plan 1162) cannot hold after the first mismatch: E1 goes out once per New York day and symbol (plan 316), and a mismatch blocks every new buy (plan 315), so the unknown BUY stays the last row and every later round starts on the same mismatch with no E1. A checker written to the letter prints FAIL e at Task 20's 200 rounds for a false reason.
- Ruling: In drill e a mismatch counts as said when the next start left a `news_errors.jsonl` row with `where` "book_mismatch" (or `buys_blocked` "book_mismatch" in the heartbeat). E1 is asked for only the first time a symbol mismatches. After a round that found a mismatch, the next round starts from a fresh state directory. The start that must say it is left to reach its first idle beat before it is judged or killed, because E1 goes out only after the first look (Task 7, step 5).
- Why: The `news_errors.jsonl` row is written at every mismatched start and is what spec 11.2 asks for ("no mismatch that check 4 missed").
- If wrong: Drill e is a little weaker on E1 itself: only the first mismatch of a symbol is checked for E1.
- This task (Task 20): Drill e with 200 rounds is judged by them; no build.

### P23 (Tasks 19, 20, 22, 24, 27) — OWNER-FACING

- Finding: The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs `supervise --status --watchdog` before any git work and syncs last (plan 1219; spec 4.4); a landing is pushed after 16:05, the 16:22 close slot is normally gone and the dashboard does not pull, so a later push is first merged at the end of the 08:07 turn of the next morning. After Task 20, `python3 -m aitrader.supervise` does not exist at 08:07 and plan 1277 orders undo at 09:00; after Task 24 the prompt's first line `slot-done ... --start` is an unknown command; after Tasks 22 and 27 the 08:07 parent runs on the old config, so "dm true through the window" and "one sup_start with handover false" fail on the first day.
- Ruling: Each landing of Tasks 20, 22, 24 and 27 gets one more proof before its `update_trigger` and before its next-day reading counts: after the trader session's next state commit (Global Constraints line 35), that commit has the landing commit as an ancestor (`git merge-base --is-ancestor <landing> <the trader's state commit>` exits 0). If no trader turn will sync before 08:07 New York: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35). The spec's order inside the watchdog turn stays.
- Why: Otherwise the first morning after a landing runs old code or old prompts and fails its own proof.
- If wrong: One more proof per landing, and at times one more question to the owner and one scheduled task.
- This task (Task 20): Applies before `update_trigger` and before the next-morning reading.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 20): The flip commit changes `config.json` and `SWITCHES_ON` only; the suite stays OK.

### P31 (Tasks 20) — OWNER-FACING

- Finding: Plan 1277 sets a check after the next morning's 08:07 slot with an undo at 09:00 New York, for the controller, which no scheduled task can wake. That morning neither the dead-man (Task 22) nor the watcher (Task 26) exists, so this check is the only net if `--status` or the launch is broken.
- Ruling: At the landing the controller starts a chain of tracked background waits (each under the 2-hour cap) that ends at 08:20 New York of the next session day and then reads the pushed state (`git fetch origin <branch>`, `git show origin/<branch>:ai-trader/state/uptime.jsonl | tail -n 8`). The owner is told the evening before that the result comes then. The same mechanism serves Task 9's "next trading morning" proof.
- Why: It is the one way that needs nobody to be awake.
- If wrong: A broken chain of waits (a VM restart) leaves the morning unchecked until the owner writes.
- This task (Task 20): The controller starts the chain at the landing; the owner gets one line that evening.

### P36 (Tasks 20, 22, 24, 26, 27)

- Finding: Plan 1418 lands Task 21 with "no gate"; spec 12 (lines 893-894) and Global Constraints 33 agree for operations code. The owner's later ruling (ai-trader/CLAUDE.md rule 4, 2026-11-11) covers "a change that touches only how the news engine is run, supervised or measured" and keeps "the quant-critic and the unit suite" mandatory; the dead-man is supervision.
- Ruling: The quant-critic runs at Task 21's landing (Task 22's first landing) too: one agent, on Opus (`claude-opus-5-5`), the `git stash` ban verbatim in its prompt; its verdict says the diff touches no file the time machine loads. The same holds for every landing of operations code in this plan (undo landings and any landing of a BUILD edit included): the critic and the unit suite are mandatory.
- Why: It meets the spec and the owner's ruling for the price of one agent.
- If wrong: One more agent run per landing.
- This task (Task 20): Already gated (`config.json`, slot files); the critic runs on Opus and says no time-machine file is touched.

### P39 (Tasks 20, 26) — OWNER-FACING

- Finding: Task 20's cloud drill records whether a stop leaves `sup_stop` "signal" or no `sup_stop` at all (plan 1271; which signal the platform sends is not documented), but Task 26's stop-drill pass marks (plan 1639) assume a caught signal: "DM2 10 minutes after the stop" and "the next `up` row follows a `sup_stop` signal". If TaskStop kills, no `leave` runs: the alarm is the last DM1 and no `sup_stop` exists, so a working system fails its drill by the letter.
- Ruling: Task 26's stop-drill marks are read against what Task 20 recorded. Caught signal: as written. Kill: DM1 within 6 minutes of the last ping, no `sup_stop`, the rest unchanged.
- Why: The plan itself records both outcomes as possible.
- If wrong: Nothing.
- This task (Task 20): The session log records which outcome each cloud stop gave (as plan 1271 already says); Task 26 reads it.

### P40 (Tasks 18, 20, 24) — OWNER-FACING

- Finding: A `list_triggers` reply reaches a file only by the model typing it again: "each prompt, unchanged, into its file" (plan 1206), "diff each prompt against its file" (plan 1276) and `.cache/triggers.json` every Friday in the trader session (plan 1512; spec 7.1) all rest on that copy. The plan treats a difference as hard evidence: "stop, someone changed it" (plan 1276) and an S1 line pushed to the owner.
- Ruling: The limit is accepted and written in the session log. A difference is read again for that one task (`list_triggers`) before a stop or an S1 line. Because the Friday check runs in the trader session, Task 24's edit of `close.md` adds the sentence: before pushing the S1 line, read the differing task again with `list_triggers` and push S1 only if the difference stands.
- Why: One retyping slip must not read as a changed task.
- If wrong: One more read for a task that differs.
- This task (Task 20): Before "stop, someone changed it", and after `update_trigger` before calling a diff a failure, the one differing task is read again.

## Task 21

### P7 (Tasks 16, 21) — OWNER-FACING

- Finding: Task 16 counts each `new_seq` row as "an alarm that went out" (plan 1112). Task 21 rewrites `state/news_deadman.json` after each accepted ping and removes it only in the undo case (plan 1304, 1310), so after a normal close (DM3, then the cancel, plan 1303) yesterday's `due_at` lies hours behind and the next morning's first ping writes `new_seq`. The two-week page that decides question 3 would show one alarm a day.
- Ruling: After a confirmed cancel (the close, or a trip or halt whose line was said) the parent removes `state/news_deadman.json`. The next arming writes `armed`. A cancel that failed (row `cancel_failed`) keeps the file, and the `new_seq` that follows is then a true count. `new_seq` keeps the meaning Task 16 reads. Task 21's test `test_an_alarm_that_already_went_out_gets_a_new_seq_and_the_old_one_is_never_touched` still passes (it writes the old file itself).
- Why: Without it the alarm count on the two-week page is false every day.
- If wrong: A cancel the parent thinks confirmed but ntfy kept leaves no file, so the next morning starts a new seq with no `new_seq` row: one true alarm uncounted.
- This task (Task 21): `Deadman` removes the file after a confirmed cancel; keeps it after `cancel_failed`.

### P8 (Tasks 11, 15, 21) — OWNER-FACING

- Finding: `leave()` has no window (plan 1299), and `main` calls it on every way out (plan 1311), so "handover", "signal" and "orphaned" leave one last ping with DM2 for 10 minutes (plan 1305) also after the window closed at the session's close + 60 s (plan 1292). The 14:17 handover of 2026-11-27 (close 13:00), and any stop signal or `max_leg_minutes` handover between 16:01 and 16:05, put "the supervisor stopped, stops are not checked" on the phone with the market closed; `--status` answers `after_hours` from 16:00 (plan 1021), so nobody relaunches.
- Ruling: `main` calls `leave` for "handover", "signal" and "orphaned" only while `window_open(now, cal, sup)` is true. After the window nothing is published.
- Why: Spec 6: pings go out only while the window is open; after the close only DM3 can arrive.
- If wrong: Nothing: `tick` has already disarmed at the window's close, so nothing waits.
- This task (Task 21): `main` guards the three calls with `window_open`. Built together with P28 (the guard inside `leave`).

### P9 (Tasks 13, 21) — OWNER-FACING

- Finding: A third or later trip of a day has no line (plan 929: R3, then R3b, then nothing; spec 4.3), yet `main` must pass `said` = whether "its line" was delivered and `text` = that line (plan 1311), and `said` false builds the waiting message from `text` (plan 1305). Read to the letter that is a TypeError on the way out, or a line reading "None", on a day R3b promised no more lines.
- Ruling: At a third or later trip of a day `main` calls `leave("crash_loop", held, said=True)`: the waiting message is cancelled.
- Why: R3b has already told the owner that no more lines come today, and these are the signature's own defaults (`said=True`, `text=None`, plan 1299).
- If wrong: Nothing: no alarm and no late line after the third trip, as R3b announced.
- This task (Task 21): `main` passes `said=True` at a trip that sent no line.

### P10 (Tasks 13, 21, 22, 25)

- Finding: `NtfyStub` answers the poll with lines of `sequence_id`, `priority`, `time` only (plan 926). Task 25's test that `watch-check` never prints a body against "a NtfyStub that holds BODY-123" (plan 1601-1605) then cannot fail, and Task 21's poll-path topic test (plan 1390-1391) only catches the topic in an error's URL, although every real line carries the topic (plan 1321). Neither task may edit `tests/helpers/http_stub.py` (plan 1286, 1521).
- Ruling: Task 13's stub returns ntfy's full line for every message on the poll: `id`, `time`, `event`, `topic`, `message`, `title`, `priority`, `sequence_id`. Task 22 confirms the field names on a real reply.
- Why: Without real fields the leak tests of Tasks 21 and 25 assert nothing.
- If wrong: A few more fields in a test stub.
- This task (Task 21): The poll-path topic test now runs against lines that carry the topic.

### P12 (Tasks 16, 21, 22, 28)

- Finding: Task 22 (plan 1424) and list A of Task 28 (plan 1664) read from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429; `day_report` has `left_min` and counts under `deadman` only (plan 1112), and no later task adds keys. The cause of a failed ping cannot be read from the pushed state at all: `.cache/supervise.log` never reaches git (plan 35) and Task 21 fixes no field of a `deadman` row but `what`.
- Ruling: The report stays as Task 16 has it. Tasks 22 and 28 read `dm` and `left` from the `mark` rows of `git show origin/<branch>:ai-trader/state/uptime.jsonl`. Task 21's `ping_failed` row carries `status` (the HTTP code, or the exception's class name).
- Why: The marks already hold both numbers; only the failed ping's cause was missing from git.
- If wrong: One extra field in one kind of row.
- This task (Task 21): The `deadman` row with `what` "ping_failed" gets `status`.

### P15 (Tasks 17, 21)

- Finding: Task 17 (plan 1195) and Task 21 (plan 1411) require the by-hand run `python3 scripts/drill_supervisor.py all --fast --rounds 20` (seven PASS lines), while controller-notes.md says "Run only unit tests" and wins over the brief (lines 3, 37). Drills b, d, e and g are in no unit test (plan 1175 runs a, c, f), so an obedient implementer hands them untested to Task 20's landing.
- Ruling: The briefs of Tasks 17 and 21 name this one command as required and allowed: `env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 scripts/drill_supervisor.py all --fast --rounds 20`, on temporary directories, with stub children, 127.0.0.1 only. Its seven lines go into the report.
- Why: Otherwise four drills run for the first time at the real numbers at the landing.
- If wrong: One allowed exception to "only unit tests", bounded to stubs and 127.0.0.1.
- This task (Task 21): The same; the seven lines show the dead-man changed no drill.

### P20 (Tasks 21)

- Finding: The test class cannot run as written: (a) `DeadmanSwitch(unittest.TestCase)` gets a helper `run(seconds, **tick)`, which is `TestCase.run`; the runner raises `TypeError: 'TextTestResult' object cannot be interpreted as an integer` and no test body runs (plan 1323, every `self.run(` in 1327-1383). (b) `test_a_delay_that_is_not_whole_minutes_is_refused_before_any_child_starts` (plan 1387-1388) uses a parent's rc and `self.urows`, helpers of `Parents`, inside the plain TestCase. (c) If `new_deadman()` starts a new stub, the handover test's `self.stub.delivered == []` (plan 1345-1346) asserts nothing.
- Ruling: The helper is named `ticks(seconds, **tick)`, in the class and in every fragment line (`self.ticks(1800, fresh=True, held={}, window=True)` and so on). `test_a_delay_that_is_not_whole_minutes_is_refused_before_any_child_starts` moves to `DeadmanWiring(Parents)`; the count stays 17. `new_deadman()` makes a new switch on the same state directory and the same stub; only `answers([...])` starts a new stub.
- Why: (a) is reproduced; (b) and (c) cost nothing to pin.
- If wrong: Nothing.
- This task (Task 21): Builds the class with these three changes.

### P26 (Tasks 13, 21)

- Finding: DM4 and the pause after it use "the header's t" (plan 1307-1308), but a `Sender` result has `left` and `retry_after` only (plan 917); the stub already sends `t=3600` (plan 926). Task 21's file line names `class Deadman`, not a change of `Sender` (plan 1286).
- Ruling: In Task 13's brief each `Sender.results()` entry also has `reset_s` (the `t` of the `RateLimit` header). `results()` keeps its plan signature; Task 21 routes the queue's outcomes between `main` and `Deadman` itself, by tag, in the files it owns.
- Why: One field closes (a); (b) lives in files Task 21 owns, so it needs no ruling.
- If wrong: One field in a result dict.
- This task (Task 21): DM4's time = now + `reset_s`; `Deadman` reads its own outcomes by tag from the one queue.

### P27 (Tasks 13, 21, 22) — OWNER-FACING

- Finding: The phone drill's parent sends the parent's own lines to the owner's phone through the same `Sender` and topic: R2 180 s after the freeze in phase `stop` (switch off, so the "לא נהרג, המתג כבוי" form), R1 60 s after the restart in phase `restart`, R4b after the handover when the relaunch takes 180 s or more (plan 1316-1319, 839, 929-930). Task 22 passes each phase on "he reports nothing" or "nothing before" (plan 1422), so by the letter three of five phases fail.
- Ruling: Spec 11.2 step 3 is about the alarm. "Nothing" in Task 22 means no message titled "AI Trader - דממה". Before the drill the owner is told which lines titled "AI Trader - מפקח" belong to it: R2 (the "לא נהרג, המתג כבוי" form) about 180 s after `stop`, R1 about 60 s after `restart`, and R4b after `handover` when the relaunch takes 180 s or more. (The scanner's alternative, `phone` mode giving the topic to the dead-man only, is not taken: the refuter calls the reading free of code and the other one an added path in `main`.)
- Why: The drill tests the dead-man; the parent's own lines are correct behaviour.
- If wrong: The owner may read an expected "מפקח" line as a fault if the message before the drill is not clear.
- This task (Task 21): No build.

### P28 (Tasks 21, 22) — OWNER-FACING

- Finding: `leave` has no `window` (plan 1299) and posts DM2 for "handover", "signal" and "orphaned" "as they are" (plan 1305, 1311), so after `tick` has disarmed a stop by a signal puts a new 10-minute alarm at ntfy. The drill's `close` phase must end its own parent after the `disarmed` row (plan 1320), so step 5 of plan 1422 ("nothing arrives in the 10 minutes after") fails at minute 10; `test_the_end_of_the_day_puts_dm3_then_cancels` (plan 1404-1406) fails when its parent is ended by SIGTERM; live, a parent stopped between 16:01 and 16:05 leaves a false "stops are not checked" line for the night.
- Ruling: DM2 goes out only while the window is open: the last `tick` had `window` true and no `disarmed` followed. Otherwise `leave` posts nothing. One test line in `DeadmanSwitch`: after a `ticks(...)` with `window=False` that disarmed, `self.dm.leave(self.now, "signal", {})` adds no post (`len(self.posts())` is unchanged).
- Why: Spec 6: pings only while the window is open; after the close only DM3 can arrive.
- If wrong: Nothing found.
- This task (Task 21): `leave` checks its own last window. Built together with P8 (the guard in `main`); both stay.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 21): Dispatched after Task 20's landing.

### P38 (Tasks 16, 21, 22, 28)

- Finding: Task 22 reads from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429 (plan 1424); `day_report` has `left_min` and counts only (plan 1112). Task 22's first proof wants marks with `dm` null while the switch is off (plan 1418), but `Deadman.ok` is a bool and is "the `dm` of a mark" (plan 1296), and plan 841 says null only "until Tasks 13 and 21": a mark with `dm` false fails the proof and shows `deadman_ok` false in `--status`.
- Ruling: The three readings come from the `mark` and `deadman` rows of `state/uptime.jsonl` (Task 28 already names both sources, plan 1659). Task 21's brief adds: "with the switch off or no topic, a mark's `dm` is null". A `ping_failed` row carries `status` (the HTTP code or the exception's class name), as in P12.
- Why: No producer gives those readings in the shape the plan reads them.
- If wrong: One null case and one field.
- This task (Task 21): A mark's `dm` is null with `deadman.enabled` false or no topic; `ping_failed` carries `status`.

## Task 22

### P10 (Tasks 13, 21, 22, 25)

- Finding: `NtfyStub` answers the poll with lines of `sequence_id`, `priority`, `time` only (plan 926). Task 25's test that `watch-check` never prints a body against "a NtfyStub that holds BODY-123" (plan 1601-1605) then cannot fail, and Task 21's poll-path topic test (plan 1390-1391) only catches the topic in an error's URL, although every real line carries the topic (plan 1321). Neither task may edit `tests/helpers/http_stub.py` (plan 1286, 1521).
- Ruling: Task 13's stub returns ntfy's full line for every message on the poll: `id`, `time`, `event`, `topic`, `message`, `title`, `priority`, `sequence_id`. Task 22 confirms the field names on a real reply.
- Why: Without real fields the leak tests of Tasks 21 and 25 assert nothing.
- If wrong: A few more fields in a test stub.
- This task (Task 22): Step 2.5 checks these eight field names against the saved real replies; a difference is a BUILD fix of the stub through Task 21's review (plan 1420).

### P12 (Tasks 16, 21, 22, 28)

- Finding: Task 22 (plan 1424) and list A of Task 28 (plan 1664) read from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429; `day_report` has `left_min` and counts under `deadman` only (plan 1112), and no later task adds keys. The cause of a failed ping cannot be read from the pushed state at all: `.cache/supervise.log` never reaches git (plan 35) and Task 21 fixes no field of a `deadman` row but `what`.
- Ruling: The report stays as Task 16 has it. Tasks 22 and 28 read `dm` and `left` from the `mark` rows of `git show origin/<branch>:ai-trader/state/uptime.jsonl`. Task 21's `ping_failed` row carries `status` (the HTTP code, or the exception's class name).
- Why: The marks already hold both numbers; only the failed ping's cause was missing from git.
- If wrong: One extra field in one kind of row.
- This task (Task 22): The three-day evening reading takes `dm` and `left` from the `mark` rows and "no 429" from the `ping_failed` rows' `status`.

### P19 (Tasks 19, 22)

- Finding: The leak test `test_no_prompt_and_no_fixture_names_a_session_a_task_a_topic_or_an_address` reads every file under `tests/fixtures/` as text (plan 1244-1247) and fails on a tracked binary fixture: `tests/fixtures/stock_panel.pkl` matches the third LEAKS pattern with `<email>`. Task 19 cannot change that file (plan 1214), so "4 tests, OK" (plan 1262) is unreachable.
- Ruling: The fixture half of the test skips `*.pkl`: the line becomes `for f in [*SLOTS.glob("*.md"), *(p for p in (ROOT / "tests" / "fixtures").rglob("*") if p.is_file() and p.suffix != ".pkl")]:`. Every other fixture stays under the test, so `tests/fixtures/ntfy/**` and `list_triggers_sample.json` are still read. (The refuter gave "skip `*.pkl`" or "skip any file that is not strict UTF-8" with no preference; the suffix test is the smaller one.)
- Why: A price panel cannot carry a topic or an id; the text fixtures stay under Review Focus 5.
- If wrong: A future binary fixture of another suffix would trip the test again.
- This task (Task 22): The saved ntfy replies are still read by the leak test (plan 1420's proof).

### P23 (Tasks 19, 20, 22, 24, 27) — OWNER-FACING

- Finding: The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs `supervise --status --watchdog` before any git work and syncs last (plan 1219; spec 4.4); a landing is pushed after 16:05, the 16:22 close slot is normally gone and the dashboard does not pull, so a later push is first merged at the end of the 08:07 turn of the next morning. After Task 20, `python3 -m aitrader.supervise` does not exist at 08:07 and plan 1277 orders undo at 09:00; after Task 24 the prompt's first line `slot-done ... --start` is an unknown command; after Tasks 22 and 27 the 08:07 parent runs on the old config, so "dm true through the window" and "one sup_start with handover false" fail on the first day.
- Ruling: Each landing of Tasks 20, 22, 24 and 27 gets one more proof before its `update_trigger` and before its next-day reading counts: after the trader session's next state commit (Global Constraints line 35), that commit has the landing commit as an ancestor (`git merge-base --is-ancestor <landing> <the trader's state commit>` exits 0). If no trader turn will sync before 08:07 New York: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35). The spec's order inside the watchdog turn stays.
- Why: Otherwise the first morning after a landing runs old code or old prompts and fails its own proof.
- If wrong: One more proof per landing, and at times one more question to the owner and one scheduled task.
- This task (Task 22): Applies to both landings (Task 21's code, then the `deadman.enabled` flip) before the evening readings count.

### P27 (Tasks 13, 21, 22) — OWNER-FACING

- Finding: The phone drill's parent sends the parent's own lines to the owner's phone through the same `Sender` and topic: R2 180 s after the freeze in phase `stop` (switch off, so the "לא נהרג, המתג כבוי" form), R1 60 s after the restart in phase `restart`, R4b after the handover when the relaunch takes 180 s or more (plan 1316-1319, 839, 929-930). Task 22 passes each phase on "he reports nothing" or "nothing before" (plan 1422), so by the letter three of five phases fail.
- Ruling: Spec 11.2 step 3 is about the alarm. "Nothing" in Task 22 means no message titled "AI Trader - דממה". Before the drill the owner is told which lines titled "AI Trader - מפקח" belong to it: R2 (the "לא נהרג, המתג כבוי" form) about 180 s after `stop`, R1 about 60 s after `restart`, and R4b after `handover` when the relaunch takes 180 s or more. (The scanner's alternative, `phone` mode giving the topic to the dead-man only, is not taken: the refuter calls the reading free of code and the other one an added path in `main`.)
- Why: The drill tests the dead-man; the parent's own lines are correct behaviour.
- If wrong: The owner may read an expected "מפקח" line as a fault if the message before the drill is not clear.
- This task (Task 22): The pass marks of steps 1-5 read "nothing" as no "AI Trader - דממה" message; the owner gets the message above before step 1.

### P28 (Tasks 21, 22) — OWNER-FACING

- Finding: `leave` has no `window` (plan 1299) and posts DM2 for "handover", "signal" and "orphaned" "as they are" (plan 1305, 1311), so after `tick` has disarmed a stop by a signal puts a new 10-minute alarm at ntfy. The drill's `close` phase must end its own parent after the `disarmed` row (plan 1320), so step 5 of plan 1422 ("nothing arrives in the 10 minutes after") fails at minute 10; `test_the_end_of_the_day_puts_dm3_then_cancels` (plan 1404-1406) fails when its parent is ended by SIGTERM; live, a parent stopped between 16:01 and 16:05 leaves a false "stops are not checked" line for the night.
- Ruling: DM2 goes out only while the window is open: the last `tick` had `window` true and no `disarmed` followed. Otherwise `leave` posts nothing. One test line in `DeadmanSwitch`: after a `ticks(...)` with `window=False` that disarmed, `self.dm.leave(self.now, "signal", {})` adds no post (`len(self.posts())` is unchanged).
- Why: Spec 6: pings only while the window is open; after the close only DM3 can arrive.
- If wrong: Nothing found.
- This task (Task 22): Step 5 of the phone drill ("nothing arrives in the 10 minutes after") can now pass.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 22): The same for the `deadman.enabled` flip.

### P30 (Tasks 22)

- Finding: The leak proof of step 2.5, "`grep -r "aitrader-drill-" ai-trader/` prints nothing" (plan 1420), can never pass: the plan itself holds that string and is tracked (`ai-trader/research/plans/2026-11-10-supervisor.md:1420`).
- Ruling: The proof becomes `grep -rF -- "$T" ai-trader/` prints nothing, run in the same Bash call that holds `$T`: the publish, the saves and this grep are one Bash call (a shell variable does not outlive a call).
- Why: It tests the value itself, not a prefix the plan contains.
- If wrong: Nothing.
- This task (Task 22): Step 2.5 runs as one Bash call ending with the grep above.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 22): Its first landing carries Task 21 only.

### P36 (Tasks 20, 22, 24, 26, 27)

- Finding: Plan 1418 lands Task 21 with "no gate"; spec 12 (lines 893-894) and Global Constraints 33 agree for operations code. The owner's later ruling (ai-trader/CLAUDE.md rule 4, 2026-11-11) covers "a change that touches only how the news engine is run, supervised or measured" and keeps "the quant-critic and the unit suite" mandatory; the dead-man is supervision.
- Ruling: The quant-critic runs at Task 21's landing (Task 22's first landing) too: one agent, on Opus (`claude-opus-5-5`), the `git stash` ban verbatim in its prompt; its verdict says the diff touches no file the time machine loads. The same holds for every landing of operations code in this plan (undo landings and any landing of a BUILD edit included): the critic and the unit suite are mandatory.
- Why: It meets the spec and the owner's ruling for the price of one agent.
- If wrong: One more agent run per landing.
- This task (Task 22): Its first landing runs the suite, the adversarial review and the critic; its second (the flip) is gated anyway.

### P38 (Tasks 16, 21, 22, 28)

- Finding: Task 22 reads from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429 (plan 1424); `day_report` has `left_min` and counts only (plan 1112). Task 22's first proof wants marks with `dm` null while the switch is off (plan 1418), but `Deadman.ok` is a bool and is "the `dm` of a mark" (plan 1296), and plan 841 says null only "until Tasks 13 and 21": a mark with `dm` false fails the proof and shows `deadman_ok` false in `--status`.
- Ruling: The three readings come from the `mark` and `deadman` rows of `state/uptime.jsonl` (Task 28 already names both sources, plan 1659). Task 21's brief adds: "with the switch off or no topic, a mark's `dm` is null". A `ping_failed` row carries `status` (the HTTP code or the exception's class name), as in P12.
- Why: No producer gives those readings in the shape the plan reads them.
- If wrong: One null case and one field.
- This task (Task 22): Its first proof (`dm` null, no `deadman` row) and the three evening readings use the rows above.

## Task 23

### P18 (Tasks 10, 11, 13, 23)

- Finding: Four things the plan mandates that the reviewer's rubric may call defects: (a) timing asserts "within 1 s" (plan 780-782, 807-808, 941-942); (b) `send_timeout_seconds` + 1 s on the way out (plan 932), a literal second against "no literal threshold" (Global Constraints 21), and a fourth new config key would break "three keys are added"; (c) `load_state` "never raises" (plan 628, 634, 687-688), so a state file that does not parse is forgotten in silence; (d) repeated logic: `supervise.session_hours` beside `journal.session_hours`, the lock-file write in `news_live.run` and `take_lock`, the prctl lines in `news_live` and `dummy_child.py`, `supervise.read_rows` and Task 23's `slots.read_receipts`.
- Ruling: (a) Kept: they are the spec's named tests (spec 4.3, target 2, 5.3); a reviewer's finding on them returns to the controller (Ruling 3). (b) On its way out the parent gives the worker `send_timeout_seconds` alone: no `+ 1 s`, no new config key, no literal. (c) Kept: `load_state` never raises; when the file does not parse, the exception's class name (never its text) is written to the parent's log `.cache/supervise.log`, by `main` (Task 11), because Task 10 has no log to write to. (d) Accepted for `session_hours` (spec 4.5 with its equality test), the lock write and the prctl lines (the dummy must not import pandas; `supervise` must not import the engine). Task 23's `slots.read_receipts(path)` returns `supervise.read_rows(path)`.
- Why: (b) is the only real conflict and a result that misses by a hair counts as not delivered (the safe side); (c) is the plan's own decision (Review Focus 4), safe because the start checks find the cause again.
- If wrong: (b): a trip or halt line that arrives in the last instant is treated as not said, and the alarm becomes the late line.
- This task (Task 23): (d): `read_receipts` is one line, `return supervise.read_rows(path)`.

### P24 (Tasks 23, 24, 25) — OWNER-FACING

- Finding: `slot-done` prints `notify` (plan 1447), and Task 25 puts W6 and W7 there (plan 1542), but no prompt tells the trader to push it: Task 24's receipt lines (plan 1512) and Task 25's :37 step (plan 1544) only run the command, close.md pushes only the `notify` of `uptime-report` and the S1 line, and close.md is not in Task 25's file list (plan 1521). Spec 7.2 and rows W6 and W7 of section 8 need both lines to reach the owner.
- Ruling: Task 24's edit of every slot file adds the sentence "push each text that slot-done prints under notify through the Claude app", and `tests/test_slot_files.py` gains one assertion that every slot file (except `watcher.md`, P22) holds that sentence.
- Why: Task 24 edits every file anyway; the model only carries out what it is told (plan 1536).
- If wrong: One sentence per slot file and one assertion.
- This task (Task 23): No build: `notify` stays as specified.

### P34 (Tasks 18, 23, 24, 25)

- Finding: (a) Task 23's fixture is made "from the Task 18 reply" (plan 1503), which plan 1204 keeps in the controller's scratch folder with session, task and environment ids; a BUILD implementer has no path to it, and a raw copy puts ids into a public-repo commit. (b) `slots_check(clean_sample, CFG, SLOTS_DIR) == []` (plan 1495-1499) breaks when Task 24 rewrites every slot file and adds the crypto slots, and again when Task 25 edits `news-watch.md`, if CFG or SLOTS_DIR is real; neither task's `git add` holds the fixture or `test_slots.py`.
- Ruling: The controller hands Task 23 a copy of the Task 18 reply with the ids already replaced (task ids by `trig_x`, no session id), by path in the brief. The `slots_check` test builds its own config and its own slot folder in the temporary directory from the sample, and never reads `skills/trader/slots/` or the real `supervisor.slots`.
- Why: The implementer needs the reply without its ids, and the test must not move with later prompt edits.
- If wrong: One sanitised file made by the controller.
- This task (Task 23): The brief names the sanitised copy's path; `test_slots.py` uses temporary config and slot files.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 23): Dispatched after both landings of Task 22.

## Task 24

### P22 (Tasks 19, 24, 25)

- Finding: Task 25 creates `skills/trader/slots/watcher.md` (plan 1521) in the folder that two "every file" tests read: Task 19's first test asks every `*.md` that holds "git " for `git merge --no-edit origin/`, `git merge --abort` and the S2 text (plan 1234-1242), and Task 24 adds "every file holds `slot-done <its slot> --start`, `slot-done <its slot>` and `re-run: slot-done`" (plan 1512). `watcher.md` holds `git fetch`, `merge --ff-only` and the stash ban and never commits (plan 1543; spec 7.2), and it is not a slot. Task 25's test changes (plan 1622) exempt nothing.
- Ruling: Both tests skip `watcher.md` by name. Task 24 writes its new assertion with the skip from the start. Task 25 adds the same skip to Task 19's first test: `files = sorted(f for f in SLOTS.glob("*.md") if f.name != "watcher.md")` (the `assertGreaterEqual(len(files), 6)` stays). The leak test still reads `watcher.md`. `watcher.md` keeps only Task 25's own assertions.
- Why: `supervisor.slots` does not exist at Task 19, so a name is the simplest filter.
- If wrong: A slot file ever named `watcher.md` would escape the two tests.
- This task (Task 24): The new assertion skips `watcher.md` by name.

### P23 (Tasks 19, 20, 22, 24, 27) — OWNER-FACING

- Finding: The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs `supervise --status --watchdog` before any git work and syncs last (plan 1219; spec 4.4); a landing is pushed after 16:05, the 16:22 close slot is normally gone and the dashboard does not pull, so a later push is first merged at the end of the 08:07 turn of the next morning. After Task 20, `python3 -m aitrader.supervise` does not exist at 08:07 and plan 1277 orders undo at 09:00; after Task 24 the prompt's first line `slot-done ... --start` is an unknown command; after Tasks 22 and 27 the 08:07 parent runs on the old config, so "dm true through the window" and "one sup_start with handover false" fail on the first day.
- Ruling: Each landing of Tasks 20, 22, 24 and 27 gets one more proof before its `update_trigger` and before its next-day reading counts: after the trader session's next state commit (Global Constraints line 35), that commit has the landing commit as an ancestor (`git merge-base --is-ancestor <landing> <the trader's state commit>` exits 0). If no trader turn will sync before 08:07 New York: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35). The spec's order inside the watchdog turn stays.
- Why: Otherwise the first morning after a landing runs old code or old prompts and fails its own proof.
- If wrong: One more proof per landing, and at times one more question to the owner and one scheduled task.
- This task (Task 24): Applies before `update_trigger` and before the next-morning reading.

### P24 (Tasks 23, 24, 25) — OWNER-FACING

- Finding: `slot-done` prints `notify` (plan 1447), and Task 25 puts W6 and W7 there (plan 1542), but no prompt tells the trader to push it: Task 24's receipt lines (plan 1512) and Task 25's :37 step (plan 1544) only run the command, close.md pushes only the `notify` of `uptime-report` and the S1 line, and close.md is not in Task 25's file list (plan 1521). Spec 7.2 and rows W6 and W7 of section 8 need both lines to reach the owner.
- Ruling: Task 24's edit of every slot file adds the sentence "push each text that slot-done prints under notify through the Claude app", and `tests/test_slot_files.py` gains one assertion that every slot file (except `watcher.md`, P22) holds that sentence.
- Why: Task 24 edits every file anyway; the model only carries out what it is told (plan 1536).
- If wrong: One sentence per slot file and one assertion.
- This task (Task 24): Adds the sentence and its assertion.

### P34 (Tasks 18, 23, 24, 25)

- Finding: (a) Task 23's fixture is made "from the Task 18 reply" (plan 1503), which plan 1204 keeps in the controller's scratch folder with session, task and environment ids; a BUILD implementer has no path to it, and a raw copy puts ids into a public-repo commit. (b) `slots_check(clean_sample, CFG, SLOTS_DIR) == []` (plan 1495-1499) breaks when Task 24 rewrites every slot file and adds the crypto slots, and again when Task 25 edits `news-watch.md`, if CFG or SLOTS_DIR is real; neither task's `git add` holds the fixture or `test_slots.py`.
- Ruling: The controller hands Task 23 a copy of the Task 18 reply with the ids already replaced (task ids by `trig_x`, no session id), by path in the brief. The `slots_check` test builds its own config and its own slot folder in the temporary directory from the sample, and never reads `skills/trader/slots/` or the real `supervisor.slots`.
- Why: The implementer needs the reply without its ids, and the test must not move with later prompt edits.
- If wrong: One sanitised file made by the controller.
- This task (Task 24): No build: rewriting the slot files cannot break `test_slots.py`.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 24): Its BUILD edit runs inside the step; the landing carries Tasks 23-24 only.

### P36 (Tasks 20, 22, 24, 26, 27)

- Finding: Plan 1418 lands Task 21 with "no gate"; spec 12 (lines 893-894) and Global Constraints 33 agree for operations code. The owner's later ruling (ai-trader/CLAUDE.md rule 4, 2026-11-11) covers "a change that touches only how the news engine is run, supervised or measured" and keeps "the quant-critic and the unit suite" mandatory; the dead-man is supervision.
- Ruling: The quant-critic runs at Task 21's landing (Task 22's first landing) too: one agent, on Opus (`claude-opus-5-5`), the `git stash` ban verbatim in its prompt; its verdict says the diff touches no file the time machine loads. The same holds for every landing of operations code in this plan (undo landings and any landing of a BUILD edit included): the critic and the unit suite are mandatory.
- Why: It meets the spec and the owner's ruling for the price of one agent.
- If wrong: One more agent run per landing.
- This task (Task 24): Already gated; the critic on Opus.

### P40 (Tasks 18, 20, 24) — OWNER-FACING

- Finding: A `list_triggers` reply reaches a file only by the model typing it again: "each prompt, unchanged, into its file" (plan 1206), "diff each prompt against its file" (plan 1276) and `.cache/triggers.json` every Friday in the trader session (plan 1512; spec 7.1) all rest on that copy. The plan treats a difference as hard evidence: "stop, someone changed it" (plan 1276) and an S1 line pushed to the owner.
- Ruling: The limit is accepted and written in the session log. A difference is read again for that one task (`list_triggers`) before a stop or an S1 line. Because the Friday check runs in the trader session, Task 24's edit of `close.md` adds the sentence: before pushing the S1 line, read the differing task again with `list_triggers` and push S1 only if the difference stands.
- Why: One retyping slip must not read as a changed task.
- If wrong: One more read for a task that differs.
- This task (Task 24): `close.md` gains the re-read sentence before S1; the session log states the limit.

## Task 25

### P10 (Tasks 13, 21, 22, 25)

- Finding: `NtfyStub` answers the poll with lines of `sequence_id`, `priority`, `time` only (plan 926). Task 25's test that `watch-check` never prints a body against "a NtfyStub that holds BODY-123" (plan 1601-1605) then cannot fail, and Task 21's poll-path topic test (plan 1390-1391) only catches the topic in an error's URL, although every real line carries the topic (plan 1321). Neither task may edit `tests/helpers/http_stub.py` (plan 1286, 1521).
- Ruling: Task 13's stub returns ntfy's full line for every message on the poll: `id`, `time`, `event`, `topic`, `message`, `title`, `priority`, `sequence_id`. Task 22 confirms the field names on a real reply.
- Why: Without real fields the leak tests of Tasks 21 and 25 assert nothing.
- If wrong: A few more fields in a test stub.
- This task (Task 25): The `BODY-123` test now has a body in the reply.

### P22 (Tasks 19, 24, 25)

- Finding: Task 25 creates `skills/trader/slots/watcher.md` (plan 1521) in the folder that two "every file" tests read: Task 19's first test asks every `*.md` that holds "git " for `git merge --no-edit origin/`, `git merge --abort` and the S2 text (plan 1234-1242), and Task 24 adds "every file holds `slot-done <its slot> --start`, `slot-done <its slot>` and `re-run: slot-done`" (plan 1512). `watcher.md` holds `git fetch`, `merge --ff-only` and the stash ban and never commits (plan 1543; spec 7.2), and it is not a slot. Task 25's test changes (plan 1622) exempt nothing.
- Ruling: Both tests skip `watcher.md` by name. Task 24 writes its new assertion with the skip from the start. Task 25 adds the same skip to Task 19's first test: `files = sorted(f for f in SLOTS.glob("*.md") if f.name != "watcher.md")` (the `assertGreaterEqual(len(files), 6)` stays). The leak test still reads `watcher.md`. `watcher.md` keeps only Task 25's own assertions.
- Why: `supervisor.slots` does not exist at Task 19, so a name is the simplest filter.
- If wrong: A slot file ever named `watcher.md` would escape the two tests.
- This task (Task 25): Adds the skip to `test_no_prompt_rebases_and_every_prompt_fetches_merges_and_knows_s2`.

### P24 (Tasks 23, 24, 25) — OWNER-FACING

- Finding: `slot-done` prints `notify` (plan 1447), and Task 25 puts W6 and W7 there (plan 1542), but no prompt tells the trader to push it: Task 24's receipt lines (plan 1512) and Task 25's :37 step (plan 1544) only run the command, close.md pushes only the `notify` of `uptime-report` and the S1 line, and close.md is not in Task 25's file list (plan 1521). Spec 7.2 and rows W6 and W7 of section 8 need both lines to reach the owner.
- Ruling: Task 24's edit of every slot file adds the sentence "push each text that slot-done prints under notify through the Claude app", and `tests/test_slot_files.py` gains one assertion that every slot file (except `watcher.md`, P22) holds that sentence.
- Why: Task 24 edits every file anyway; the model only carries out what it is told (plan 1536).
- If wrong: One sentence per slot file and one assertion.
- This task (Task 25): No build: W6 and W7 land in `notify` and are pushed by Task 24's sentence.

### P25 (Tasks 25)

- Finding: The last assertion of `test_a_missing_slot_is_fired_once_then_w3_then_nothing` (plan 1562) asks for no W2 and no W3 from any slot at NOW + 60 minutes (19:22:31Z) with the receipts of NOW. By then dashboard 18:57Z and news-watch 18:37Z are past their 20-minute grace with no line and refire true, and each gives W2 by the rules of plan 1535-1536. RECEIPTS cannot hold later lines for them without breaking the first test (plan 1550-1553).
- Ruling: The assertion is about midday, as its `fire` half already is: `self.assertEqual([n for n in v3["notify"] if n["id"] in ("W2", "W3") and SLOTS["midday"]["he"] in n["text"]], [])` (W2 and W3 lines that name midday by its `he` are absent).
- Why: The assertion as written fails for any code that follows the rules.
- If wrong: Nothing.
- This task (Task 25): Plan line 1562 is replaced by the assertion above.

### P34 (Tasks 18, 23, 24, 25)

- Finding: (a) Task 23's fixture is made "from the Task 18 reply" (plan 1503), which plan 1204 keeps in the controller's scratch folder with session, task and environment ids; a BUILD implementer has no path to it, and a raw copy puts ids into a public-repo commit. (b) `slots_check(clean_sample, CFG, SLOTS_DIR) == []` (plan 1495-1499) breaks when Task 24 rewrites every slot file and adds the crypto slots, and again when Task 25 edits `news-watch.md`, if CFG or SLOTS_DIR is real; neither task's `git add` holds the fixture or `test_slots.py`.
- Ruling: The controller hands Task 23 a copy of the Task 18 reply with the ids already replaced (task ids by `trig_x`, no session id), by path in the brief. The `slots_check` test builds its own config and its own slot folder in the temporary directory from the sample, and never reads `skills/trader/slots/` or the real `supervisor.slots`.
- Why: The implementer needs the reply without its ids, and the test must not move with later prompt edits.
- If wrong: One sanitised file made by the controller.
- This task (Task 25): No build: editing `news-watch.md` cannot break `test_slots.py`.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 25): Dispatched after Task 24's landing.

## Task 26

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 26): The same for the two watcher switches.

### P32 (Tasks 26)

- Finding: Plan 1631 says the "one full run" finds out whether a pre-approval was dropped, but that run (plan 1633) comes before the dry day with both switches false: `fire` and `notify` are empty (plan 1540), so it calls neither the fire tool nor the push tool, nor `list_triggers`, which it uses only per `fire` entry (plan 1543) and which is not in `extra_allowed_tools`. A waiting permission prompt first shows at a real fault. The fire is later proven by the Saturday drill (plan 1638); the push by nothing.
- Ruling: `list_triggers` joins `extra_allowed_tools`. "No prompt is waiting" is read again on the first run that fires (the Saturday drill's transcript) and on the first run that pushes a line. Until that push has been seen, the session log says the watcher's push is not proven.
- Why: Spec 7.2 and row 5 of 11.2 want the run to prove the fire and the push.
- If wrong: One more tool pre-approved and two more transcript reads.
- This task (Task 26): `create_session`'s `extra_allowed_tools` = Bash, `list_triggers`, the fire tool and the Claude app push tool; two later prompt checks.

### P33 (Tasks 26) — OWNER-FACING

- Finding: Plan 1631 reads `external_metadata.last_served_model` right after `create_session`, which carries no first prompt, and stops if it is not `claude-fable-5-2`. The `get_session` tool defines that field as the model "the CLI ran the latest turn on"; with no turn there is none, so the step would read an empty field as "only the owner can switch it". The owner's model order of 2026-11-11 (ai-trader/CLAUDE.md, "Agents and models") also replaces the plan's "no model" and `claude-fable-5-2` here: the watcher only monitors.
- Ruling: `create_session` sets the model `claude-opus-5-5` (the plan's "no model" is replaced). Right after creation, `get_session`: `<session-id>.model` and `configured_model` are `claude-opus-5-5`. In the "one full run" step, after the first turn, `external_metadata.last_served_model` is `claude-opus-5-5`. If any is not: stop, and tell the owner that only he can switch it (`/model` in that session). The owner's yes to creating the session (Task 26) is still asked first, and the question names the model `claude-opus-5-5`.
- Why: The owner's order: Opus for everything that is not building or creating; and `last_served_model` exists only after a turn.
- If wrong: A watcher on the wrong model is caught one step later (at the first full run) instead of at creation.
- This task (Task 26): Creation sets `claude-opus-5-5`; the three reads use that id at the times above; the owner's question names the model.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 26): Its landings carry Task 25 (and any BUILD edit of `news-watch.md`) only.

### P36 (Tasks 20, 22, 24, 26, 27)

- Finding: Plan 1418 lands Task 21 with "no gate"; spec 12 (lines 893-894) and Global Constraints 33 agree for operations code. The owner's later ruling (ai-trader/CLAUDE.md rule 4, 2026-11-11) covers "a change that touches only how the news engine is run, supervised or measured" and keeps "the quant-critic and the unit suite" mandatory; the dead-man is supervision.
- Ruling: The quant-critic runs at Task 21's landing (Task 22's first landing) too: one agent, on Opus (`claude-opus-5-5`), the `git stash` ban verbatim in its prompt; its verdict says the diff touches no file the time machine loads. The same holds for every landing of operations code in this plan (undo landings and any landing of a BUILD edit included): the critic and the unit suite are mandatory.
- Why: It meets the spec and the owner's ruling for the price of one agent.
- If wrong: One more agent run per landing.
- This task (Task 26): Both landings gated; the critic on Opus. A landing of a BUILD edit of `news-watch.md` also gets the critic.

### P39 (Tasks 20, 26) — OWNER-FACING

- Finding: Task 20's cloud drill records whether a stop leaves `sup_stop` "signal" or no `sup_stop` at all (plan 1271; which signal the platform sends is not documented), but Task 26's stop-drill pass marks (plan 1639) assume a caught signal: "DM2 10 minutes after the stop" and "the next `up` row follows a `sup_stop` signal". If TaskStop kills, no `leave` runs: the alarm is the last DM1 and no `sup_stop` exists, so a working system fails its drill by the letter.
- Ruling: Task 26's stop-drill marks are read against what Task 20 recorded. Caught signal: as written. Kill: DM1 within 6 minutes of the last ping, no `sup_stop`, the rest unchanged.
- Why: The plan itself records both outcomes as possible.
- If wrong: Nothing.
- This task (Task 26): The stop drill picks its marks by that record; the owner is told before the drill which alarm to expect (DM2, or DM1 on a kill).

## Task 27

### P23 (Tasks 19, 20, 22, 24, 27) — OWNER-FACING

- Finding: The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs `supervise --status --watchdog` before any git work and syncs last (plan 1219; spec 4.4); a landing is pushed after 16:05, the 16:22 close slot is normally gone and the dashboard does not pull, so a later push is first merged at the end of the 08:07 turn of the next morning. After Task 20, `python3 -m aitrader.supervise` does not exist at 08:07 and plan 1277 orders undo at 09:00; after Task 24 the prompt's first line `slot-done ... --start` is an unknown command; after Tasks 22 and 27 the 08:07 parent runs on the old config, so "dm true through the window" and "one sup_start with handover false" fail on the first day.
- Ruling: Each landing of Tasks 20, 22, 24 and 27 gets one more proof before its `update_trigger` and before its next-day reading counts: after the trader session's next state commit (Global Constraints line 35), that commit has the landing commit as an ancestor (`git merge-base --is-ancestor <landing> <the trader's state commit>` exits 0). If no trader turn will sync before 08:07 New York: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35). The spec's order inside the watchdog turn stays.
- Why: Otherwise the first morning after a landing runs old code or old prompts and fails its own proof.
- If wrong: One more proof per landing, and at times one more question to the owner and one scheduled task.
- This task (Task 27): Applies before the next-day reading of the `long_timeout_proven` flip.

### P29 (Tasks 11, 13, 14, 17, 20, 22, 26, 27)

- Finding: `Parents` copies the real config with three numbers changed (plan 742) and the drill script uses "the numbers of config.json" (plan 1154); nothing pins the five switches there. After Task 22's flip every `Parents` test runs a dead-man (`ParentLines` reads `q["json"]["message"]` over all requests, and a DELETE or GET has no JSON; scripted answers are eaten by pings); after Task 20's flip a hang is killed where a test counts one `hang` row; after Task 27, `test_the_launch_pair` meets `long_timeout_proven` true, and `self.status()` with no `environ` reads the gate VM's own `BASH_MAX_TIMEOUT_MS`.
- Ruling: In the briefs of Tasks 11, 14 and 17: the config copy of `Parents` and of the drill script sets all five switches (`hang_kill_enabled`, `long_timeout_proven`, `deadman.enabled`, `watcher.fire_enabled`, `watcher.notify_enabled`) explicitly, false unless the test or the drill says so, and `status()` in a test always gets an explicit `environ` (the `Status` helper passes `environ={}` when the test gives none). A flip then moves `SWITCHES_ON` only.
- Why: The flips are OPS commits that need the suite OK; the tests must not depend on them.
- If wrong: Nothing.
- This task (Task 27): The same for `long_timeout_proven`.

### P35 (Tasks 21, 22, 23, 24, 25, 26, 27)

- Finding: There is one work branch and a landing pushes HEAD (plan 32). Task 22's first landing is "no gate: no gated file changes" (plan 1418), true only while Task 21 alone is ahead of the live branch; Task 23 changes `config.json` (plan 1432). A wave that builds Task 23 or Task 25 before that landing sends them along ungated and before their own step's drill. The plan also lets Task 27 land "any time after Task 20" (plan 1646) and has undo landings (plan 1426, 1642).
- Ruling: From Task 21 on, a BUILD task is dispatched only after the landing that stands before it in the plan: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; Task 26's BUILD edit (if any) after Task 26's first landing. Task 27's landing and any undo landing happen only when the work branch holds nothing unlanded from another step. In addition (controller's decision): a landing never pushes the work branch's HEAD blindly. The controller cuts a landing branch in the gate clone at the last commit that belongs to that rollout step, merges the live branch into it, gates that commit and pushes it; the work branch then merges the live branch back. So Tasks 10-17 may be built on the work branch before Task 9 lands (Task 9 lands the commit of the last engine task only), and Tasks 18-19 follow the plan's own order.
- Why: Each step must pass its own review and drill before the next step's code rides along.
- If wrong: Slower waves: Tasks 21-26 run one at a time, behind each landing.
- This task (Task 27): Lands only when the work branch holds nothing unlanded from another step.

### P36 (Tasks 20, 22, 24, 26, 27)

- Finding: Plan 1418 lands Task 21 with "no gate"; spec 12 (lines 893-894) and Global Constraints 33 agree for operations code. The owner's later ruling (ai-trader/CLAUDE.md rule 4, 2026-11-11) covers "a change that touches only how the news engine is run, supervised or measured" and keeps "the quant-critic and the unit suite" mandatory; the dead-man is supervision.
- Ruling: The quant-critic runs at Task 21's landing (Task 22's first landing) too: one agent, on Opus (`claude-opus-5-5`), the `git stash` ban verbatim in its prompt; its verdict says the diff touches no file the time machine loads. The same holds for every landing of operations code in this plan (undo landings and any landing of a BUILD edit included): the critic and the unit suite are mandatory.
- Why: It meets the spec and the owner's ruling for the price of one agent.
- If wrong: One more agent run per landing.
- This task (Task 27): Gated; the critic on Opus. Its undo landing gets the critic too.

## Task 28

### P12 (Tasks 16, 21, 22, 28)

- Finding: Task 22 (plan 1424) and list A of Task 28 (plan 1664) read from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429; `day_report` has `left_min` and counts under `deadman` only (plan 1112), and no later task adds keys. The cause of a failed ping cannot be read from the pushed state at all: `.cache/supervise.log` never reaches git (plan 35) and Task 21 fixes no field of a `deadman` row but `what`.
- Ruling: The report stays as Task 16 has it. Tasks 22 and 28 read `dm` and `left` from the `mark` rows of `git show origin/<branch>:ai-trader/state/uptime.jsonl`. Task 21's `ping_failed` row carries `status` (the HTTP code, or the exception's class name).
- Why: The marks already hold both numbers; only the failed ping's cause was missing from git.
- If wrong: One extra field in one kind of row.
- This task (Task 28): List A's `dm`/`left` line reads the `mark` rows.

### P37 (Tasks 19, 28)

- Finding: List A of Task 28 (plan 1669) and spec 11.2 read the day's uptime, the longest `blind_s` and each start's commit from the trader's close log, but Task 19 gives `close.md` only `uptime-report --day --notify` and the push of `notify` (plan 1220); no prompt tells the trader to write the numbers down.
- Ruling: Task 19's edit of `close.md` adds: copy the day's block of `uptime-report --day` (`uptime`, `longest_blind_s`, `commits`) into the close log.
- Why: Otherwise the last line of list A rests on chance.
- If wrong: One sentence in one prompt.
- This task (Task 28): List A's close-log line reads what that step wrote.

### P38 (Tasks 16, 21, 22, 28)

- Finding: Task 22 reads from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per 3 minutes, and that no `ping_failed` came from a 429 (plan 1424); `day_report` has `left_min` and counts only (plan 1112). Task 22's first proof wants marks with `dm` null while the switch is off (plan 1418), but `Deadman.ok` is a bool and is "the `dm` of a mark" (plan 1296), and plan 841 says null only "until Tasks 13 and 21": a mark with `dm` false fails the proof and shows `deadman_ok` false in `--status`.
- Ruling: The three readings come from the `mark` and `deadman` rows of `state/uptime.jsonl` (Task 28 already names both sources, plan 1659). Task 21's brief adds: "with the switch off or no topic, a mark's `dm` is null". A `ping_failed` row carries `status` (the HTTP code or the exception's class name), as in P12.
- Why: No producer gives those readings in the shape the plan reads them.
- If wrong: One null case and one field.
- This task (Task 28): List A reads the same rows.

## For the controller

Checklist in the order the items come up.

1. [P35] Landings (decision c): a landing never pushes the work branch's HEAD. Cut a landing branch in the gate clone at the last commit of that rollout step, merge the live branch into it, gate it, push it; then merge the live branch back into `supervisor-build`. Task 9 lands the commit of the last engine task only; Tasks 10-17 may be built before Task 9 lands.
2. [P31] Task 9's "next trading morning" proof: at the landing start a chain of tracked background waits (each under the 2-hour cap) ending 08:20 New York of the next session day, then read the pushed state; tell the owner the evening before when the result comes.
3. [P1] Briefs of Tasks 10, 11, 12, 17: every engine_child start by a test or drill gets `--until 23:59` unless the test passes its own; the dummy ignores `--until`.
4. [P29] Briefs of Tasks 11, 14, 17: the five switches pinned explicitly in `Parents`' and the drill's config copies; `status()` in a test always gets an explicit `environ`.
5. [P18] Brief of Task 11: decide how `load_state`'s parse-error class name reaches `main` for `.cache/supervise.log` (the texts do not say; `load_state(path, ny_day) -> dict` and "never raises" must stay).
6. [P26] Brief of Task 13 (not yet dispatched): `Sender.results()` entries carry `reset_s`.
7. [P10] Brief of Task 13: `NtfyStub` poll lines carry the eight ntfy fields.
8. [P15] Briefs of Tasks 17 and 21: the by-hand `drill_supervisor.py all --fast --rounds 20` run is required and allowed (env -u prefix, stubs, 127.0.0.1 only); its seven lines go into the report.
9. [P40] Task 18: write the retyping limit of `list_triggers` replies into the session log.
10. [P34] Task 18 -> 23: keep the reply in scratch; before Task 23 make a copy with task ids replaced by `trig_x` and no session id, and give its path in Task 23's brief.
11. [P21] After Task 18's push and before Task 19's dispatch: in the gate clone `git fetch origin <branch>`, `git merge --no-edit origin/<branch>`; see `ai-trader/skills/trader/slots/*.md`.
12. [P36] Every landing of operations code (Task 22's first landing included, and every undo landing): the unit suite and the quant-critic on Opus, verdict naming no time-machine file.
13. [P23] Landings of Tasks 20, 22, 24, 27: before `update_trigger` and before the next-day reading counts, prove a trader-session state commit descends from the landing commit; if no trader turn syncs before 08:07 New York, ask the owner for a one-time sync task bound to the trader session.
14. [P40] Task 20: re-read a differing task with `list_triggers` before "stop, someone changed it" or before calling a post-update diff a failure.
15. [P31] Task 20: at the landing start the chain of waits to 08:20 New York next session day; tell the owner that evening.
16. [P39] Task 20: record in the session log what each cloud stop left (`sup_stop` "signal" or none); Task 26 reads it.
17. [P35] Dispatch order from Task 21: Task 21 after Task 20's landing; Task 23 after Task 22's two landings; Task 25 after Task 24's landing; a Task 26 BUILD edit after Task 26's first landing; Task 27's landing and undo landings only with nothing unlanded from another step on the work branch.
18. [P27] Task 22: before the phone drill tell the owner which "AI Trader - מפקח" lines belong to the drill; read "nothing" as no "AI Trader - דממה" message.
19. [P30] Task 22, step 2.5: one Bash call for the publish, the saves and `grep -rF -- "$T" ai-trader/`.
20. [P12] Tasks 22, 28: read `dm` and `left` from the `mark` rows, and the 429 check from the `ping_failed` rows' `status`, of the pushed `uptime.jsonl`.
21. [P38] Task 22's first proof: marks with `dm` null and no `deadman` row.
22. [P33] Task 26: ask the owner's yes naming `claude-opus-5-5`; create the watcher session with model `claude-opus-5-5`; read `<session-id>.model` and `configured_model` at creation and `last_served_model` after the first turn.
23. [P32] Task 26: `list_triggers` in `extra_allowed_tools`; re-read "no prompt waiting" on the first firing run and the first pushing run; log the push as not proven until seen.
24. [P39] Task 26's stop drill: marks by Task 20's record (kill: DM1 within 6 minutes of the last ping, no `sup_stop`).

## Where the refuter changed the scanner's ruling

- P1: widened from parents in tests and drills to every engine_child start, also without a parent (drills e, g; `Procs.start_engine`).
- P2: added the `--fast` hang threshold (4 s quote stub = `hang_seconds` 4); of its two remedies the kill-switch-off one was taken (no new code, given P29).
- P4: added the clause that the start being judged first reaches its first idle beat.
- P5: R1 is dropped only when the hang kill was the episode's only fall; a second fall before healthy still gets R1.
- P7: added that a failed cancel keeps the file.
- P10: added that Task 22 confirms the field names on a real reply.
- P12: added `status` on the `ping_failed` row.
- P15: added "127.0.0.1 only" to the allowed run.
- P18: only (b) is a conflict; (c)'s log line is written by `main` (Task 11), not Task 10; (d) `read_receipts` returns `supervise.read_rows(path)`.
- P19: skip `*.pkl` instead of narrowing the test to this plan's own fixtures.
- P22: skip `watcher.md` by name instead of filtering on `supervisor.slots` (which does not exist at Task 19).
- P23: narrowed to Tasks 20, 22, 24, 27: Task 26 is not bound (`--watcher` exists from Task 23 and two turns sync before the first 09:37).
- P26: narrowed to `reset_s`; `results(prefix)` dropped as a non-necessity.
- P35: added that Task 27's landing and any undo landing wait for a work branch with nothing unlanded from another step.
- P38: added `status` on the `ping_failed` row.
- P40: added that the re-read before S1 is a sentence in `close.md` (Task 24), not only a log note.

## Owner-facing

Rulings that change a line the owner reads, or what he is asked or told. Hebrew is quoted from spec 8; where the texts give no Hebrew wording for a new message, its content is given and the wording is still owed.

- P5: R2 kill form, now sent at the first `up` after the kill: `מנוע החדשות נתקע: {s} שניות בלי פעימה. נהרג והופעל מחדש ב-{HH:MM:SS}. סטופים לא נבדקו {blind_s} שניות. פתוח: {held}. שעון ישראל. כסף נייר` ({s} = the hang row's `hb`). No R1 for that episode unless the replacement falls again before healthy.
- P6: When R11 goes out changes: `סיכום יום: המנוע נפל {r} פעמים, המפקח עצר {t} פעמים, {m} דקות בשעות המסחר בלי בדיקת סטופים. כסף נייר` is sent on a trip, or when unprotected minutes exceed the sum of `m` in the day's R4/R4b rows plus the same call's R4c.
- P7: The two-week page's dead-man alarm count (sent with question 3) counts only alarms that went out.
- P8: No DM2 after the window closes: `המפקח נעצר ב-{HH:MM} ולא הופעל מחדש כבר 10 דקות. סטופים לא נבדקים. פתוח: {held}. הבדיקה המתוזמנת הבאה מפעילה מחדש. שעון ישראל. כסף נייר`.
- P9: After a third trip no alarm and no "נשלח באיחור: " line; R3b already said `היום לא אשלח על זה עוד שורות, רק סיכום בסגירה`.
- P11: `פתוח: {held}` in R3, R3b, R3c, R5a, R5b, R5e and R4c now lists the book's names and stops when there is no beat, instead of a false `אין פוזיציות`.
- P14: R1's `{sold}` (` נמכר בהפעלה: {sym} בסטופ {stop}, במחיר {fill}.`) no longer drops a sale made in the old child's last second.
- P16: R6 (`מנוע החדשות חי, אבל הסטופים לא נבדקו כבר {s} שניות ({names}). ...`) fires during a long call, and its `{s}` includes the beat's own age.
- P23: The owner may be asked for a one-time scheduled task bound to the trader session, prompt `git fetch origin <branch> && git merge --no-edit origin/<branch>`, when no trader turn syncs a landing before 08:07 New York. Hebrew wording owed.
- P24: W6 (`התרגיל השבועי נכשל: המשגיח לא תפס משבצת חסרה. עד שזה מתוקן אי אפשר לסמוך עליו. כסף נייר`) and W7 (`המשגיח לא רץ כבר {m} דקות, או שהוא מחכה לאישור. בדיקת המשבצות לא פועלת. כסף נייר`) now reach him.
- P27: Before the phone drill he is told that lines titled "AI Trader - מפקח" may come and belong to the drill: R2 (`... בלי פעימה. לא נהרג, המתג כבוי. פתוח: {held}. כסף נייר`) about 180 s after `stop`, R1 about 60 s after `restart`, R4b after `handover` when the relaunch takes 180 s or more; only "AI Trader - דממה" counts. Hebrew wording owed.
- P28: Same as P8: no DM2 after the window (the `close` phase of the phone drill ends with a quiet phone).
- P31: The evening of Task 20's landing he is told the morning result comes at 08:20 New York. Hebrew wording owed.
- P33: The question for creating the watcher session names the model `claude-opus-5-5`. Hebrew wording owed.
- P39: In Task 26's stop drill he is told to expect DM2 10 minutes after the stop, or, if Task 20 recorded a kill, DM1 (`לא התקבלה פעימה ממנוע החדשות מאז ...`) within 6 minutes of the last ping.
- P40: S1 (`המשימות המתוזמנות לא תואמות להגדרות: {what}. כסף נייר`) is pushed only after the differing task was read again.

## Controller's additions (11:05 UTC, 2026-11-11) - they win over the text above where they differ

- P18(c), Task 11 (and Task 10, which defines `load_state`): `load_state(path, ny_day) -> dict` keeps its signature
  and never raises. When the file exists and does not parse, the state it returns (a new day's state) carries one extra
  key, `load_error`, whose value is the exception's class name (never its text). `main` writes one line with that
  class name to the parent's log when the key is there and removes the key before the first save. A clean load has no
  such key. One test in Task 10 (the returned state has the key on garbage and has none on a good file) and one
  assertion in Task 11 (the log line, and the key gone from the saved file).
- P2, Task 17: under `--fast` drill f uses THREE held names and a quote stub of 2 s (shorter than the fast
  `hang_seconds` of 4, so no hang row and no R2 can appear in this drill); at the real numbers three names and 60 s.
  The switches are pinned as P29 says. This replaces "pin the kill switch off" as P2's remedy.
- P6, Tasks 13 and 16: a row counts as "reported" only when its line reached a channel: an R4 or R4b row with
  `sent` true, or a later row with the same id and `sent` true (counted once). Rows that never got `sent` true
  report nothing, and their minutes count toward R11.
- P13: "continues" means the largest n among that New York day's alert rows, plus 1.
- P7, P37 and every other ruling that changes behaviour and names no test: the task that owns the code adds one test
  for it, named by the implementer and listed in its report under "tests added by ruling".
- Decision c and Task 9: the last commit of rollout step 1 is the commit of Task 8b (the owner's decision on a
  fractional score, built right after Task 8). Task 9 lands Tasks 2-8 and 8b together; the quant-critic gets 8b listed
  as the one trading-rule change of that landing, with its forward measurement.
- The Hebrew wording still owed (P23, P27, P31, P33) is for messages the controller itself writes to the owner in
  chat at those OPS steps; no code and no template carries it.

## Controller's additions (2026-11-12) - carry into the dispatches named

- Task 19: before dispatch, P21's merge of the live branch into the gate clone (the slot files are at a89e6c83 and 21aba598 on the live branch); only when no implementer works in the gate clone.
- Task 20: Ruling 44 (--net-check = 200 within three tries a minute apart); Ruling 45 (the "every handover under 60 s" mark excludes a handover with an R6 or a blind name open before it); Ruling 47 (`all` at real numbers runs 35-40 min as a tracked background command; a drill a FAIL on timing is a finding, never a pass; no kill by name pattern; the safe wrapper for every python command).
- Task 21: Ruling 46 (the new_seq row holds the old seq's due_at; the brief names the rows written at the close and their order; the implementer re-checks uptime's provisional dead-man true/false rule against them).
