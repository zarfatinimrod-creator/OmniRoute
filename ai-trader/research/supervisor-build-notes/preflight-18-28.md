# Pre-flight scan - Tasks 18-28 (plan lines 1198-1676)

Plan: `ai-trader/research/plans/2026-11-10-supervisor.md`. Spec (the authority): `ai-trader/research/specs/2026-11-10-supervisor-design.md`.
Read-only scan, 2026-11-11. Nothing tracked was changed, no git command that writes was run, no subagent was dispatched.
"F n" = finding n in the list at the end. Line numbers with no file name are plan lines.

## What was read and run

- The plan in full (Tasks 1-17 as producers, 18-28 line by line), the spec in full, `progress.md`, `controller-notes.md`,
  `constraints.md`, `baseline.md`, `research/2026-11-10-supervisor-evidence.json` (the `triggers_T`, `trader_session_G` and
  `environment_E` blocks), `BUILD_CLAIMS.md`, `.gitignore`, `requirements.txt`.
- Code on the live tip: `aitrader/__main__.py` (lines 1-160: `BOOK_CMDS`, the parsers, `main`), `aitrader/journal.py`
  (`use_book`, `_BASE`, `session_hours`, the pandas import), `aitrader/notify.py`, `aitrader/news_live.py:286-312`
  (`context_id`), `skills/trader/SKILL.md` (sections 0, 3א, 3ב), `CLAUDE.md` (hard rules 4 and 8), `tests/test_books.py`
  (`STOCK_ONLY`), `config.json` (calendar, alerts, market, books), `tests/fixtures/`.
- Three things were run, none of them on the live state:
  1. Task 19's four `LEAKS` patterns over the 14 tracked files under `tests/fixtures/`, read exactly as the test reads them
     (`read_text(encoding="utf-8", errors="replace")`): 13 clean, `stock_panel.pkl` hits (F1).
  2. A 10-line `unittest.TestCase` with a helper named `run(self, seconds, **tick)`: the runner raises
     `TypeError: 'TextTestResult' object cannot be interpreted as an integer` and no test body runs (F2).
  3. The dates and zones the plan's tests use (2026-11-11 Wed, 11-21 Sat, 11-23 Mon, 11-26 Thu, 11-27 Fri, 2027-03-12 Fri,
     03-15 Mon; every UTC/New York/Israel pair; 15 `news-watch` due times on 2026-11-11): all as the plan writes them.
- `grep -rn "aitrader-drill-" ai-trader/`: one file, the plan itself, line 1420 (F12).

## Table 1 - pairs that share a file or an interface

| Tasks | Produces -> consumes | Found |
|-------|----------------------|-------|
| 1 -> 18 | the empty rows of "Baseline record" (1732-1734); the claim on `skills/trader/slots/` -> Task 18 fills the rows and creates the files | agree. The claim in `BUILD_CLAIMS.md` names every file Tasks 18-28 create or change |
| 2 -> 19 | `ownerlines.LINES[id] = (priority, template)`, `{file}` kept as a placeholder -> `LINES["S2"][1].split("{file}")[0]`, `LINES["R8"][1]`, `LINES["R12"][1]` | agree. R8 and R12 have no placeholder, so the raw template can be searched in `SKILL.md` |
| 2 -> 21 | DM1-DM4, `priority(id, held)`, `held_text`, `hhmm`, `render` -> the ping texts; "deadman imports ownerlines and nothing else" | agree. DM1/DM2 urgent or high = 5 or 4, DM3 low = 2, DM4 default = 3, as Task 21 and Task 25 use them. The prefix `נשלח באיחור:` is a literal in `deadman.py`, not in the table (plan decision 5) |
| 2 -> 23, 25 | S1; W0-W7 and `WORDS["W0.what"]` ("crash" = "הפקודה קרסה") -> `slots-check`, `watch-check`, `watcher.md` | agree |
| 5 -> 19 | the two exit-code lines in SKILL 3ב -> Task 19 rewrites the launch paragraph of 3ב | agree; the two lines stay, they hold no `pull --rebase` |
| 9 -> 20 | step 1 landed (the engine with codes, the first look, the planned stop) -> step 2 lands on it | agree |
| 10 -> 20, 22, 26, 27 | `SWITCHES`, `SWITCHES_ON`, the five switch keys -> each rollout step flips one in `config.json` and adds its path | names agree. The other tests copy the real config: F11 |
| 10 -> 21 | every `deadman.*` key, `Paths.deadman`, `session_hours(day, cal)`, `load_cfg`, the state file's `trips_today`, `.gitignore` for `news_deadman.json` -> `Deadman`, `window_open` | agree; Task 21 adds no config key, so its commit holds no gated file |
| 10 -> 23, 25 | `receipts_keep_days`, `watcher.lookback_hours`, `ntfy_since`, `stale_minutes`, `engine_window_ny`, `quiet_hours` -> `slots.py`, `watch.py` | agree. Task 10's defaults test compares only the keys it lists, so `slots` and `drill_from` can be added |
| 11 -> 21 | `main`, the `sup_stop` words, return codes 2/75/143, `Parents` (`run_parent`, `spawn_parent`, `urows`) -> `leave(why)`, `DeadmanWiring(Parents)` | agree for `DeadmanWiring`. `DeadmanSwitch` is a plain TestCase and uses `urows`: F2 |
| 12 -> 21 | `mark.dm` and `mark.left` (null until 13 and 21), `beat_view` (`age_s`, `mine`, `held`) -> `Deadman.ok`, `Deadman.left`, `fresh`, `held` | agree; what `dm` is with the switch off is not said: F22 |
| 12, 15 -> 20, 28 | rows `sup_start`, `start`, `up`, `code`, `mark`; `sup_stop` "handover" rc 76; `up.handover_s` -> the morning proof, List A | agree |
| 13 -> 20 | `supervise --net-check` prints `Sender.health()`, exit 0 only on 200 -> Task 20's check before any prompt changes | agree |
| 13 -> 21 | `Sender.publish/request/results`, `Sender(sync=True)`, `NtfyStub` (`answers`, `cancel_answers`, `pending`, `delivered`, `advance`, the poll) -> `Deadman` and its tests | names agree. `results()` has no reset seconds and is one queue: F8 |
| 13 -> 21, 22 | the parent's lines (R1, R2, R4b) go out through the same `Sender` and topic -> the phone drill's parent | differ: F9 |
| 13 -> 25 | `NtfyStub` poll (`sequence_id`, `priority`, `time`); `Sender.request("GET", ...)` with `lines` -> `watch-check` reads the topic "with `urllib`" | stub agrees; a second opener beside `Sender`: F26 (c) |
| 14 -> 19 | `--status --watchdog`, `--relayed ID...`, the action table, `launch.command` -> `news-watch.md`, SKILL 3ב | agree |
| 14 -> 21 | `--status` lists an `alert` row of kind R10 at once -> `Deadman` writes that row at `daily_limit` and `quota` | agree |
| 14 -> 23 | `status()` keys `parent.alive`, `engine.hb_age_s`, `engine.stop_age_s`, `today.restarts/trips/halt`, `deadman_ok`, `ntfy_left` -> the `engine` block of a `news-watch` done line | agree, all eight exist |
| 14 -> 27 | the launch pair by `long_timeout_proven` and `BASH_MAX_TIMEOUT_MS`; `sup_start.timeout_ms` -> Task 27's proof | agree in shape; `test_the_launch_pair` after the flip: F11 |
| 16 -> 19 | `uptime-report --day --notify` prints `{"notify": [{id, priority, text}]}` -> `close.md` pushes each text | agree |
| 16 -> 22, 24, 28 | `day_report` keys -> the evening readings | `missing_marks`, `by_cause.stale_stops`, `left_min`, `commits`, `longest_blind_s` exist; `dm` over the day and the slope of `left` do not: F22 |
| 16 -> 23, 25 | `uptime.py`, "slot and watcher columns are added in Tasks 23 and 25" -> both tasks change `uptime.py` and add it | agree. Neither task names a test for its columns; Task 24's proof ("missed 0, stuck 0") reads them |
| 17 -> 20 | `drill_supervisor.py all` (seven PASS), `cloud DIR`, `cloud-check --alive DIR`, `cloud-check DIR` -> Task 20's commands | agree, spelled the same |
| 17 -> 21 | `guard()` keeps the topic only for `phone --with-owner`; `phone` alone is refused -> mode `phone` with `--phase`, `--dir` | agree with Task 17's test (1184-1187) |
| 18 -> 19 | the slot files "as they stand", pushed to the live branch -> edited in the gate clone on `supervisor-build` | differ: the files are not in the gate clone: F3 |
| 18 -> 20 | the "prompt baseline" commit -> the check before `update_trigger`, and the undo | agree. `news-watch-37.md`, if made, still exists at that commit |
| 18 -> 23 | the saved `list_triggers` reply (scratch folder) -> `tests/fixtures/list_triggers_sample.json`; task names from "Baseline record" | the implementer has no path to it: F17 |
| 18 -> 24 | "trader session" or "another session" per crypto task -> which crypto slots enter `supervisor.slots` | agree. The evidence file binds the crypto go-live task to the crypto session, so most likely no crypto slot file is made |
| 19 -> 20 | the prompt files, SKILL, `CLAUDE.md` -> landed with the gate, then `update_trigger` | agree in content. The first turn under the new prompt may run in a checkout without the code: F5. `CLAUDE.md` is in the scorer's context: F19 |
| 19 -> 24 | the sync block, `tests/test_slot_files.py` -> the receipt lines before it; the test extended | agree |
| 19, 24 -> 25 | two tests over every `slots/*.md` -> Task 25 adds `watcher.md` there | differ: F4 |
| 19 -> 28 | `close.md` -> List A reads uptime, longest `blind_s` and commits from the close log | nothing makes the close slot write them: F21 |
| 20 -> 22 | step 2 landed, the cloud drills' record -> Task 21 lands on it | agree |
| 20 -> 24 | Task 20's landing commit -> the undo of Task 24 | agree. A crypto slot file first made in Task 24 does not exist at that commit (only matters if a crypto task is bound to the trader session) |
| 20 -> 26 | "what each stop left: `sup_stop` signal, or no `sup_stop` at all" -> the stop drill passes on DM2 and `sup_stop` "signal" | conditional: F24 |
| 20 -> 27 | "any time after Task 20" | agree |
| 20, 22, 26 -> 28 | "list A of Task 28" the same evening / the first day | agree |
| 21 -> 22 | phases `pings`, `stop`, `restart`, `handover`, `close`, `peek`; `--with-owner --phase --dir` -> the drill's five steps | spelled the same. "he reports nothing" against R2/R1/R4b: F9. The `close` phase and DM2: F10 |
| 21 -> 25 | seq `aitrader-dm-<stamp>`; priorities 5/4, 2, 3 -> "silent" = a delivered message with that prefix at 4 or 5 | agree |
| 22 -> 25, 26 | rule H1 and the sequence-id field confirmed on a real reply (or `peek`) -> `engine_verdict`; Task 26 repeats the condition (1636) | agree |
| 23 -> 24 | `slot-done` (exit 0/2/10, `--due`, `--fail --note`), `slots-check FILE`, the shape of a slot entry -> the receipt lines, the crypto entries, the Friday check | agree. Task 23's fixture and test against the files Task 24 rewrites: F17 |
| 23 -> 25 | `due_times`, `read_receipts`, `slot_done(..., watcher=)`, `notify: []`, `refire`, `grace_minutes`, `stuck_minutes`, `he`, `task` -> `watch.py`, W6, W7 | agree. Which task is fired for the two-task slot: F23. Who pushes `notify`: F6 |
| 24 -> 26 | the receipt lines live in every prompt -> the watcher's states | agree |
| 25 -> 26 | `watcher.md`, `watch-check`, `would_fire`/`would_notify`, `drill_from`, the name `AI Trader - משגיח W22` in `news-watch.md` -> the session, W22/W52, the dry day | agree, the name is the same in 1544 and 1632 |
| 26, 27 -> 28 | the watcher's two task names and one day's cost; the last landing -> the two-week page, the claim to "Done" | agree. `last_run` in `list_triggers` is one run, not a count: the number of watcher runs comes from the schedule |

## Table 2 - each task against itself

| Task | Tests against code, files created against files touched, commands | Found |
|------|-------------------------------------------------------------------|-------|
| 18 (OPS) | no tests. Creates `slots/*.md`, `git add` names that folder only; steps 2 and 5 also write "Baseline record" (the plan file), which the `git add` does not name | the actor can do every step (`list_triggers` returns the stored prompt). Notes: the plan-file edits need their own add; the copies are typed by the model (F25); the commit is pushed with no gate and at any hour, although Global Constraints line 24 lists "the slot files" as gated: verbatim copies that nothing reads yet, so no gate is the reading |
| 19 (BUILD) | 4 tests named, "4 tests, OK" | count agrees. Test 2 cannot pass on the tree as it stands: F1. Test 1 after Task 25: F4. Tests 3 and 4 agree with the edit list (`--status --watchdog`, `--relayed`, `aitrader postmortem`, no `--minutes 110`; `uptime-report --day --notify`; both `pull --rebase` lines of SKILL, 35 and 160, are in the edit list). The expected RED assumes the slot files are in the gate clone: F3 |
| 20 (OPS) | `drill ... all` at the real numbers runs longer than the 10-minute foreground limit of Bash (drill a alone needs more than `restart_window_seconds`): it is a tracked background command, whose end wakes the controller. Steps 1-5 run in the gate clone (the main checkout has no `scripts/drill_supervisor.py` before the landing) | doable. The 09:00 check: F13. The stale checkout: F5. The backlog step appends the sixth item "only if drill (e) broke a chain", a case in which this task stopped at its second step |
| 21 (BUILD) | 13 + 4 tests named, "`-k Deadman`: 17 tests" | count agrees; `-k Deadman` matches both classes and no other name in the plan. The helper named `run`, the whole-minutes test in the wrong class, `new_deadman()` and its stub: F2. `results()`: F8. `leave` after the window: F10. Not given, the implementer picks: the delay of the `נשלח באיחור:` replacement and of DM3 (the tests need them waiting, so a delay from the config), and what `said` is at a third trip, which has no line. The undelivered-trip test works only when no ping precedes R3 (the stub's answers are a sequence) |
| 22 (OPS) | the publish, the saves and the grep of step 2.5 must be one Bash call: a shell variable does not outlive a call. `--phase stop` has to wait up to `fresh_seconds` (90) to know the last ping, close to Bash's 120 s default | the grep proof: F12. "nothing" in the phone drill: F9, F10. "no gate" for the first landing: F20. The readings of `dm` and `left`: F22. The fixtures under `tests/fixtures/ntfy/` have no `git add` named; they ride with the switch commit |
| 23 (BUILD) | 8 tests named, "8 tests, OK" | count agrees. Every date and due time checks (15 due times; 14:37Z; the holiday; both sides of 2027-03-14; `late_s` 160). `--book crypto` can reach the stock directory through `journal._BASE` (journal.py:23, 46). `BOOK_CMDS` is pinned by no test (`STOCK_ONLY` in `tests/test_books.py:54` is a fixed tuple). The fixture and the `slots_check` test: F17 |
| 24 (OPS + one BUILD edit) | the edit's `git add` holds the slot folder, `test_slot_files.py`, `config.json` | agree. "every file holds ..." against `watcher.md`: F4. Nobody is told to push `notify`: F6. First turn after the landing: F5. The Friday `.cache/triggers.json`: F25 |
| 25 (BUILD) | 12 tests named, no count given | the last assertion of test 2: F7. The other eleven agree with the rules as written (checked: the early-close window 18:00:50Z / 18:22Z, quiet hours 00:30 and 08:22 Israel, W6 on Monday 2026-11-23 only, W7 for "blocked"). Notes: a start that is still inside its grace is "running" only if started due times are listed whatever the grace; `watch.main` has no state-directory argument, so its test must move `journal.STATE`; `news-watch.md` should also answer `unknown,0` while no task is named W22 (Task 26 updates the prompt before it creates the task). `watch-check` does import pandas through `journal` (`__main__.py:45`, `journal.py:18`), as the task says |
| 26 (OPS) | `create_session` and `create_trigger` take everything the step passes; `22 * * * *` is stored as written (only minute-0 hourly crons are re-anchored) | "one full run": F14. `last_served_model`: F15. The stop drill's marks: F24. Stale checkout at the first :37: F5. Notes: the Saturday drill fires into a session that may still run the weekly slot (due 10:17, stuck 480 min), so "within 60 minutes" can be late for that reason alone; the cost step and the dry-day reading page `list_events` 100 raw events at a time, work for a subagent |
| 27 (OPS) | the card, the proof through a one-time task and `list_events`, the flip | the refusal branch: F16. The first leg of the next day: F5. `test_the_launch_pair`: F11 |
| 28 (OPS) | List A and the two-week page | the close log: F21. `dm` and `left`: F22. "`missing_marks` 0" on a day with four handovers is the spec's own line (11.2); a handover that crosses a whole clock minute gives 1 |

## Against the Global Constraints, the cited spec sections, the controller's facts, the "already exists" claims and the rubric

- Push only to the live branch (Ruling 1): every push of Tasks 18-28 is `HEAD:<branch>` or Task 18's own commit. Agree.
- Question 7 = ב: every "land with the gate" of Tasks 20, 22, 24, 26 (twice), 27 is the suite plus the critic. The diffs touch
  `config.json` only in `supervisor` and `alerts`, never `risk`/`signals`/`costs`, and no file of the time-machine list.
  Agree. One landing is "no gate": F20.
- One work branch and `git push origin HEAD:<branch>`: F18.
- "Nothing lands in market hours", "every switch false until its drill": agree in every task of the range.
- No model set (`create_session`, the review agents): agree. The topic never in a file: the drill and the fixtures keep it
  out; the proof of it is F12.
- "Unchanged in trading ... the scorer": F19.
- The controller is not woken by a clock: one step has a deadline (F13); the others ("each evening", "the next morning",
  "after the first :37 slot", "after 14 trading days") are read whenever the owner next writes.
- No shell in the trader's VM: every proof about the trader session in the range names one of the three ways of Global
  Constraints line 35. Agree.
- Spec sections read against their tasks: 4.4 (the seven watchdog steps, both tables), 4.5, 4.7, 6 (every bullet against
  Task 21), 7.1, 7.2, 8 (ids and priorities), 9, 10, 11.1, 11.2, 12, 13. Differences from the spec that the plan lists
  itself (decisions 8, 9, 15, 16) were not counted as findings.
- "Already exists" claims that hold: `__main__` imports `journal` and `journal` imports pandas; `requirements.txt` exists;
  `.cache/` is git-ignored; `skills/trader/SKILL.md` has `pull --rebase` on lines 35 and 160 and nowhere else;
  `CLAUDE.md` hard rule 8 is line 169; `tests/fixtures/` exists with 14 tracked files; `BOOK_CMDS` is `__main__.py:47`.
  One that does not: plan line 11 puts the evidence file under `research/specs/`; it is
  `research/2026-11-10-supervisor-evidence.json` (outside this range, no task of 18-28 reads it).
- Rubric: F26; and F2 (c), a test that would assert nothing.

## Findings

1. **Task 19 - the leak test fails on a fixture that is already in the tree** (task-vs-code).
   `test_no_prompt_and_no_fixture_names_a_session_a_task_a_topic_or_an_address` reads every file under `tests/fixtures/`
   as text. The binary panel `tests/fixtures/stock_panel.pkl` (tracked, 632,110 bytes) matches the address pattern
   (`<email>`). Nothing Task 19 may edit changes that, so "4 tests, OK" (1262) cannot be reached.
   Evidence: 1229-1230, 1244-1247, 1262; the run in "What was read and run", item 1.
   Ruling: the fixture half reads the text fixtures this plan adds (`tests/fixtures/ntfy/**`,
   `tests/fixtures/list_triggers_sample.json`), or skips `*.pkl`. Review Focus 5 is about files that could carry a topic
   or an id.

2. **Task 21 - the test class as written cannot run** (task-vs-itself).
   (a) `DeadmanSwitch(unittest.TestCase)` gets a helper `run(seconds, **tick)`. That name is `TestCase.run`, which the
   runner calls with the result object: the runner raises and no test body runs. (b)
   `test_a_delay_that_is_not_whole_minutes_is_refused_before_any_child_starts` uses the `rc` of a parent run and
   `self.urows`, helpers of `Parents`, inside the plain TestCase. (c) "`answers([...])` and `new_deadman()` start a new
   stub and a new switch": if `new_deadman()` starts a new stub, the handover test's `self.stub.delivered == []` asserts
   nothing, because the DM2 message waits in the old stub.
   Evidence: 1323, every `self.run(` from 1327 to 1383, 1387-1388, 742, 1342-1346.
   Ruling: the helper gets another name (for example `ticks`) in the class and in each fragment line; the whole-minutes
   test moves to `DeadmanWiring(Parents)` (still 17); `new_deadman()` is a new switch on the same state directory and
   the same stub, and only `answers()` starts a new stub.

3. **Tasks 18 -> 19 - the slot files are not in the gate clone** (task-vs-controller).
   Task 18 pushes the files to the live branch. Task 19 edits "every file under `skills/trader/slots/`" on
   `supervisor-build` in the gate clone, whose last merge of the live branch was Task 9's landing; an implementer may
   not fetch or merge. Task 19 finds no folder.
   Evidence: 1208, 1214-1216, 1260; Global Constraints line 34; `controller-notes.md` line 26.
   Ruling: Task 18 stays as written. Before Task 19 is dispatched the controller runs `git fetch origin <branch>` and
   `git merge --no-edit origin/<branch>` in the gate clone and sees the files there.

4. **Tasks 19 and 24 against 25 - `watcher.md` lands in the folder two "every file" tests read** (task-vs-task).
   Task 19's first test asks every `slots/*.md` that holds "git " for `git merge --no-edit origin/`, `git merge --abort`
   and the S2 text. Task 24 adds "every file holds `slot-done <its slot> --start`, `slot-done <its slot>` and
   `re-run: slot-done`". Task 25 creates `skills/trader/slots/watcher.md`, which must hold `git fetch`,
   `merge --ff-only` and the `git stash` ban, and no push, no receipt and no merge of its own. Task 25's list of test
   changes does not take it out of the two older tests.
   Evidence: 1233-1242, 1512, 1521, 1543, 1622; spec 7.2 lines 607-608, 647-650.
   Ruling: both tests run over the slot files that have an entry in `supervisor.slots` (or over `*.md` except
   `watcher.md`); said in the briefs of Tasks 24 and 25.

5. **Task 19 against 20, 22, 24, 26, 27 - the first turn after a landing runs in the old checkout** (task-vs-task).
   The trader's checkout gets a landing only when one of its own turns fetches and merges. The new watchdog prompt runs
   `supervise --status --watchdog` and the launch "before any git work", syncs only at its end, and no longer starts
   the bare engine. A landing is pushed after 16:05; the syncs left that day are the close slot's (16:22) and, from
   Task 24 on, the 16:57 dashboard turn. A push that comes later is first merged at the END of the 08:07 turn of the
   next morning. Then: after Task 20 `python3 -m aitrader.supervise` does not exist at 08:07 (no parent and no engine
   until the 09:07 slot, and the plan's own check says "undo" at 09:00); after Task 24 the first line of the prompt,
   `slot-done ... --start`, is an unknown command; after Tasks 22 and 27 the parent of 08:07 starts on the old config
   and runs on it until the 09:18 handover, so "`dm` true through the window" and "one `sup_start` with `handover`
   false" fail on the first day; after Task 26 `--watcher` is an unknown option at the first :37.
   Evidence: 32, 1219, 1275-1277, 1423-1424, 1512-1514, 1630, 1651; spec 4.4 lines 246-249, 7.1 lines 555-557; evidence
   file, `triggers_T.prompt_facts.dashboard` ("do not pull or commit for this step") and the crypto go-live row (bound
   to the crypto session, so no crypto slot syncs the trader's checkout at night).
   Ruling: each landing gets one proof before its `update_trigger` and before its next-day reading counts: the pushed
   state shows a trader-session commit that descends from the landing commit
   (`git merge-base --is-ancestor <landing> origin/<branch>` after the trader's next state commit). If no trader turn
   will sync before 08:07: a one-time scheduled task bound to the trader session, on the owner's word, whose prompt is
   `git fetch origin <branch> && git merge --no-edit origin/<branch>` (the third way of Global Constraints line 35).
   The spec's order inside the watchdog turn stays.

6. **Tasks 23, 24, 25 - nobody pushes what `slot-done` prints under `notify`** (task-vs-task).
   W6 and W7 exist only as that list. Task 24's receipt lines and Task 25's :37 step run the command and say nothing
   about its output; W6 comes out of `slot-done close`, and `close.md` is not among Task 25's files.
   Evidence: 1447, 1512, 1521, 1542, 1544; spec 7.2 lines 631-632, section 8 rows W6 and W7.
   Ruling: Task 24's edit of every slot file adds "push each text that `slot-done` prints under `notify` through the
   Claude app", with one assertion for it in `tests/test_slot_files.py`.

7. **Task 25 - the last assertion of `test_a_missing_slot_is_fired_once_then_w3_then_nothing`** (task-vs-itself).
   It asks for no W2 and no W3 from any slot at NOW + 60 minutes (19:22:31Z) with the receipts of NOW. By then
   `news-watch` 18:07Z and 18:37Z and `dashboard` 18:57Z are past their 20-minute grace with no line and refire true:
   each gives W2 or W3. `RECEIPTS` cannot hold later `news-watch` lines, because the first test needs its open start to
   read "running" at NOW and "stuck" at NOW + 25 minutes, and "a later receipt closes its older due times". The
   assertion holds only with a fixture that carries receipts dated after NOW and code that ignores a receipt whose `at`
   is later than `now`; the plan says neither.
   Evidence: 1546, 1550-1553, 1555-1562, 1535-1536; spec 7.1 table, lines 583 and 587.
   Ruling: the assertion is about midday, as its `fire` half already is: W2 and W3 lines that name midday (`he`) are
   absent.

8. **Tasks 13 -> 21 - `Sender.results()` does not carry what `Deadman` needs** (task-vs-task).
   (a) DM4 and the pause after it use "the header's `t`"; a result has `left` and `retry_after` only. (b) `results()`
   is one queue "drained by the loop" for the parent's lines, and `Deadman.tick(now, *, fresh, held, window)` takes no
   outcomes: in `main` one of the two readers loses the other's results.
   Evidence: 917, 932, 1298, 1307-1308.
   Ruling, in Task 13's brief (not dispatched yet): each result also has `reset_s` (the `t` of the `RateLimit`
   header), and `results(prefix=None)` returns only the outcomes whose tag starts with the prefix; `Deadman` tags its
   requests `dm-`.

9. **Tasks 13, 21, 22 - the phone drill's parent also sends the parent's lines to the phone** (task-vs-task).
   Same `Sender`, same topic: R2 180 s after the freeze in phase `stop` (the kill switch is off there, so its "not
   killed" form), R1 60 s after the restart in phase `restart`, R4b after the handover when the relaunch takes 180 s
   or more. Task 22 passes each phase on "he reports nothing" or "nothing before".
   Evidence: 1316-1319, 1422; 839; 929-930; spec 11.2 row 3.
   Ruling: spec 11.2 step 3 is about the alarm. "Nothing" in Task 22 means no message titled "AI Trader - דממה", and
   the owner is told before the drill which lines titled "AI Trader - מפקח" belong to it. (With code instead: `phone`
   mode gives the topic to the dead-man only.)

10. **Task 21 - `leave` posts DM2 also when the window is closed** (task-vs-spec).
    "handover", "signal" and "orphaned" post one last DM2 "as they are"; `leave` has no `window`. After `tick` has
    disarmed, a stop by a signal puts a new 10-minute alarm at ntfy. The drill's `close` phase has to end its own
    parent after the `disarmed` row, so "nothing arrives in the 10 minutes after" fails at minute 10;
    `test_the_end_of_the_day_puts_dm3_then_cancels` fails when its parent is ended by SIGTERM; and live, a parent
    stopped between 16:01 and 16:05 leaves a false "stops are not checked" line for the night.
    Evidence: 1305, 1311, 1320, 1404-1406, 1422 step (5); spec 6 lines 474-475 ("while the window is open"), 479-480.
    Ruling: DM2 goes out only while the window is open (the last `tick` had `window` true and no `disarmed` followed);
    otherwise `leave` posts nothing. One test line.

11. **Tasks 11, 13, 14, 17 against 20, 22, 26, 27 - a switch flip in the real config moves every test that copies it**
    (task-vs-task). The suite must print `OK` at each landing. `Parents` copies the real config with three numbers
    changed and the drill script uses "the numbers of `config.json`"; nothing pins the five switches there. After Task
    22's flip every `Parents` test runs a dead-man: `ParentLines` reads `q["json"]["message"]` over all requests (a
    DELETE or a GET has no JSON) and the scripted `answers` are used up by pings. After Task 20's flip a hang is
    killed where a test counts one `hang` row. After Task 27, `test_the_launch_pair` meets `long_timeout_proven` true,
    and the gate clone's VM, in the same environment as the card, holds `BASH_MAX_TIMEOUT_MS`.
    Evidence: 658-659, 742, 1154, 863-864, 938, 941, 1031-1033; the flips at 1273, 1423, 1637, 1651.
    Ruling, in the briefs of Tasks 11, 14 and 17 (not dispatched yet): the config copy of `Parents` and of the drill
    script sets all five switches explicitly (false unless the test or the drill says so), and `status()` in a test
    always gets an explicit `environ`. A flip then moves `SWITCHES_ON` only.

12. **Task 22 - the leak proof of step 2.5 cannot pass** (task-vs-itself).
    "`grep -r "aitrader-drill-" ai-trader/` prints nothing": the plan holds that string and is on the branch.
    Evidence: 1420; `ai-trader/research/plans/2026-11-10-supervisor.md` is tracked.
    Ruling: grep for the value, `grep -rF -- "$T" ai-trader/`, in the same Bash call that holds `$T`.

13. **Task 20 - a deadline for a session that no clock can wake** (task-vs-controller).
    "No such rows by 09:00 New York ... undo", on the next trading morning. The controller runs on the owner's
    messages or when its own background work ends. On that morning there is no dead-man and no watcher yet: if
    `--status` or the launch is broken, nothing else says so.
    Evidence: 1277; the controller's facts; spec 7.2 line 601.
    Ruling: at the landing the controller starts a chain of tracked background waits (each under the 2-hour cap) that
    ends at 08:20 New York of the next session day and then reads the pushed state; the owner is told the evening
    before that the result comes then. (Or he agrees to write at that time.)

14. **Task 26 - "one full run" proves Bash only** (task-vs-itself).
    Line 1631 says the run finds out whether a pre-approval was dropped. It happens with both switches false: `fire`
    and `notify` are empty, so the run never calls `list_triggers` (not in `extra_allowed_tools` at all), the fire
    tool or the push tool. A waiting prompt first appears at the first real fault.
    Evidence: 1631, 1633, 1635, 1543; spec 7.2 lines 668-669, 11.2 row 5.
    Ruling: `list_triggers` joins `extra_allowed_tools`; "no prompt is waiting" is read again on the first run that
    fires (the Saturday drill's transcript) and on the first run that pushes a line, and until that push has been seen
    the session log says the watcher's push is not proven.

15. **Task 26 - `last_served_model` before any turn** (task-vs-controller).
    It is the model of the latest turn. Right after `create_session` with no first prompt there is none, and the step
    reads an empty field as "stop, only he can switch it".
    Evidence: 1631; the `get_session` tool's own text; spec 7.2 lines 596-598.
    Ruling: right after creation read `<session-id>.model` (and `configured_model`); read `last_served_model` in the
    "one full run" step.

16. **Task 27 - the card has no "refused by the tool" branch** (task-vs-controller).
    The environment tools refuse variable names "that steer the session runtime" when an environment is created;
    `BASH_MAX_TIMEOUT_MS` is such a name, and whether `update_environment` takes it is not known. The task knows
    "approved" and "declined".
    Evidence: 1649, 1653; spec 9 lines 735-743, 751; the text of `create_environment` (`set_environment_variables`).
    Ruling: a third branch. On a refusal nothing is retried or worked around; the owner gets one line that only he can
    set it, in the environment's settings, and the task waits with the handovers in place.

17. **Tasks 18 -> 23, and 23 against 24 and 25 - the `list_triggers` fixture** (task-vs-task).
    (a) The sample is made "from the Task 18 reply", which sits in the controller's scratch folder and holds session,
    task and environment ids; the implementer has no path to it. (b) `slots_check(clean_sample, CFG, SLOTS_DIR) == []`:
    if `SLOTS_DIR` is the real slot folder or `CFG` the real config, the test breaks when Task 24 rewrites every slot
    file and adds the crypto slots, and again when Task 25 edits `news-watch.md`; neither `git add` holds the fixture
    or `test_slots.py`.
    Evidence: 1204, 1432, 1495-1499, 1503, 1512, 1521.
    Ruling: the controller hands Task 23 a copy of the reply with the ids already replaced, by path in the brief; the
    `slots_check` test builds its own config and its own slot folder in the temporary directory from the sample.

18. **One work branch, and a landing pushes `HEAD`** (task-vs-constraints).
    Task 22's first landing is "no gate: no gated file changes". That is true while only Task 21 is ahead of the live
    branch. A wave that builds Task 23 (it changes `config.json`) or Task 25 before that landing sends them along,
    ungated and before their own step's drill.
    Evidence: 32, 38, 1418, 1432; ledger, Ruling 3.
    Ruling: from Task 21 on a BUILD task is dispatched only after the landing that stands before it in the plan.

19. **Task 19 - the edit of `CLAUDE.md` is a change to the scorer, by the code's own words** (task-vs-constraints).
    The scorer's `claude -p` runs in the engine's directory, and `context_id` says "an edit to one of them is a change
    to the scorer". Global Constraints keep "the scorer with its model and prompt" unchanged, and the list for the
    critic does not name this edit.
    Evidence: 16, 1214, 1222; `aitrader/news_live.py:292-298` and `:1139`; spec 4.7 line 334, 12 lines 895-897.
    Ruling: the edit stays, the spec asks for it. At Task 20's gate the critic is told that `CLAUDE.md` is in the
    scorer's context and that the `context` stamp in `news_scores.jsonl` changes at the first start after the landing;
    the new stamp goes into the session log.

20. **Task 22 - "no gate" for Task 21's landing against the owner's ruling in `CLAUDE.md`** (task-vs-constraints).
    Spec 12 agrees with the plan (operations code: tests, drills, one adversarial review). The owner's later ruling
    says that for a change "that touches only how the news engine is run, supervised or measured" the sweep is
    skipped and "the quant-critic and the unit suite stay mandatory". The dead-man is such a change.
    Evidence: 1418; Global Constraints lines 24 and 33; `ai-trader/CLAUDE.md:156-160`; spec 12 lines 893-894.
    Ruling: run the critic at this landing too (one agent; its verdict says no time-machine file is touched). That
    meets both texts.

21. **Tasks 19 against 28 - List A reads from the close log what no prompt writes there** (task-vs-task).
    The day's uptime, the longest `blind_s` and the commit of each engine start. Task 19 gives `close.md` only
    `uptime-report --day --notify` and the push of `notify`.
    Evidence: 1220, 1669; spec 11.2 lines 867-868.
    Ruling: Task 19's edit of `close.md` adds: copy the day's block of `uptime-report --day` (uptime,
    `longest_blind_s`, `commits`) into the close log.

22. **Tasks 16 and 21 against 22 and 28 - readings that no producer gives in that shape** (task-vs-task).
    Task 22 reads from `uptime-report --day` that `dm` is true through the window, that `left` falls by about one per
    3 minutes and that no `ping_failed` came from a 429; `day_report` has `left_min` and the counts under `deadman`.
    Its first proof wants marks with `dm` null while the switch is off; Task 21 has `Deadman.ok: bool` and does not say
    what a mark holds then.
    Evidence: 1112, 1296, 1310, 1418, 1424, 1664.
    Ruling: the three readings come from the `mark` and `deadman` rows of `state/uptime.jsonl` (Task 28 already says
    both); Task 21's brief adds "with the switch off or no topic, a mark's `dm` is null".

23. **Tasks 23 -> 25 - which task is fired for the slot with two tasks** (task-vs-task).
    `news-watch` is one slot with two tasks, "a schedule entry carries its own task". `watch-check` fires "the
    `news-watch` task" for a re-run, for `drill-miss` and for `engine-silent`.
    Evidence: 1445, 1536-1537; spec 7.1 line 583 ("yes (the :07 task)").
    Ruling: `news-watch` keeps a slot-level `"task"`, the :07 task, and that is what is fired; only the :37 entry
    carries its own.

24. **Tasks 20 -> 26 - the stop drill's pass marks assume a signal the parent can catch** (task-vs-task).
    "DM2 10 minutes after the stop" and "`up` follows a `sup_stop` signal". Task 20's cloud drill records which it is;
    with a kill there is no DM2 and no `sup_stop`, and the alarm is the last DM1.
    Evidence: 1271, 1639; spec 4.2 lines 173-174.
    Ruling: the marks are read against what Task 20 recorded. Caught signal: as written. Kill: DM1 within 6 minutes
    of the last ping, no `sup_stop`, the rest unchanged.

25. **Tasks 18, 20, 24 - a `list_triggers` reply reaches a file only by being typed again** (task-vs-controller).
    "Each prompt, unchanged, into its file"; "`diff` each prompt against its file"; `.cache/triggers.json` every
    Friday in the trader session, up to ten prompts. The diff compares two texts the same model typed, and one slip
    reads as "someone changed it, stop" or as a false S1 line.
    Evidence: 1206, 1276, 1512-1513; spec 7.1 lines 569-571.
    Ruling: accept the limit and write it in the session log; a difference is read again for that one task before a
    stop or an S1 line.

26. **Rubric - what the plan orders and a reviewer may call a defect** (rubric).
    (a) Errors dropped by design: `watch.load_memory` and `slots.read_receipts` turn an unreadable file or line into
    an empty memory or a skipped line; logs keep an exception's class only. (b) The same sync block word for word in
    every slot file, and the "must never" list word for word in `watcher.md`. (c) `watch-check` reads ntfy "with
    `urllib`" while `Sender.request` (Task 13) already makes a GET with the proxy and CA handling and returns `lines`:
    a second opener would be a duplicated block.
    Evidence: 1439, 1530, 1541, Global Constraints line 23, 1218, 1543, 1534 against 916-917 and 925.
    Ruling: (a) and (b) are the plan's shape (spec 7.1, 7.2); a reviewer's finding on them returns to the controller
    under Ruling 3. (c) Task 25's brief says the read goes through `deadman.Sender(sync=True).request("GET", ...)`.

## Could not be determined here

- Whether the live dashboard prompt holds the string "git " (the evidence file quotes "do not pull or commit for this
  step"). If it does, Task 19's first test asks `dashboard.md` for the sync block one step early.
- Whether the trader session has `get_session`, and whether its reply carries the time of the last turn (Task 25's :37
  step; the plan has a fallback for the first half).
- Which signal `TaskStop` and a timeout send (Task 20 measures it; F24 depends on it).
- Whether `update_environment` takes `BASH_MAX_TIMEOUT_MS` (F16).
- Which session the three crypto tasks are bound to today (the evidence file of 2026-11-10 says the crypto session).
