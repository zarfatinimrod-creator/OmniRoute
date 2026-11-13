# Task 19 report - the new prompt texts, the git rule, the SKILL table

Gate clone `.../scratchpad/clones/sup`, branch `supervisor-build`. Found HEAD `d639d8ecc6cd4e484e195d4aaace1236efe44ba0`, clean tree.
Commits: `43ac2a13` (the task, the brief's message) and `578cc775` (two self-review fixes). HEAD after: `578cc77545c8bece13764e8350165925ab490e51`. `git status --short` prints nothing.

## What was implemented

- `tests/test_slot_files.py` (new): the brief's four tests, verbatim, with ruling P19's line in the leak test (fixtures with suffix `.pkl` skipped), plus one test added by ruling P37 (`test_the_close_slot_copies_the_days_uptime_block_into_its_log`). Imports `helpers.no_phone` first.
- Every slot file that syncs (close, midday, open, weekly, news-watch, crypto-decide, crypto-fill, crypto-summary):
  - the start-of-turn `git pull --rebase origin <branch>` became `git fetch origin <branch> && git merge --no-edit origin/<branch>`; "if the pull is refused ... pull again" became "... merge again"; a conflict there points to the closing step's rule;
  - the closing commit/push step became one block: commit own state; `git fetch` and `git merge --no-edit origin/<branch>`; push; on a rejected push fetch and merge again, up to 5 tries; never rebase; never end the turn with a merge in progress (complete it, or `git merge --abort`); on a conflict `git merge --abort`, the S2 line with the conflicted file's name in place of `{file}`, and stop; discard nothing. The S2 text is `ownerlines.LINES["S2"][1]` verbatim (aitrader/ownerlines.py:74), with `{file}` kept as the placeholder.
  - crypto: the retry loop keeps its one-line form with fetch and merge before each push: `for i in 1 2 3 4 5; do git fetch origin X; git merge --no-edit origin/X || break; git push -u origin X && break; sleep $((2**i)); done`. In the two night slots (decide 00:12 UTC, fill 01:07 UTC) S2 is written into the night log, not pushed (their own step "No PushNotification at night"); the morning summary's merge meets the same conflict and pushes S2. crypto-summary pushes it.
- `news-watch.md`, one text for both watchdog tasks: (1) cd, install skills, no git first; (2) `python3 -m aitrader.supervise --status --watchdog` and the action table in English (all eight actions, see below), launch as a tracked background command with `launch.timeout_ms`, never nohup/setsid/&; the wake rule (read the last line, run `--status`, do what `action` says); (3) push each `unsent` text with PushNotification, then `--relayed ID...`; (4) `news-status` as Task 18 had it; (5) `postmortem` as Task 18 had it; (6) the sync block; (7) stay silent. Removed: the bare engine launch (`news-live ... --minutes 110`), the pgrep/3-minute heartbeat rule, the "engine was down" push. `news-watch-37.md` deleted.
- `close.md`: new step 6 after its own duty: `python3 -m aitrader uptime-report --day --notify`, copy the day's block (`uptime`, `longest_blind_s`, `commits`) into `logs/YYYY-MM-DD-close.md` (P37), push each `text` under `notify` with PushNotification. Old steps 6 and 7 renumbered 7 and 8.
- `SKILL.md`: section 0 and 3א: `git pull --rebase` became fetch and merge. 3ב: the launch paragraph, its code block and its first bullet (the old relaunch rule) gave way to the parent paragraph, the action table (Hebrew), the `unsent` paragraph, the wake rule and the last-line table (Hebrew) with R8 and R12 verbatim. Section 4א's push loop changed as in the crypto slots.
- `CLAUDE.md` hard rule 8 gained the brief's three sentences verbatim.

### Where each name was read (controller's instruction)
- Actions `--status` can return, from `aitrader/supervise.py` `status()`: `closed_today` (line 616), `after_hours` (618), `none` (620), `replace_parent` (622), `halted` (624), `kill_stray` (626), `wait_for_watchdog` (628), `launch` (630). `wait_for_watchdog` needs `not watchdog` (line 627), so `--status --watchdog` returns exactly the other seven. The woken turn runs plain `--status` (the brief's wake rule) and can get `wait_for_watchdog`; the SKILL table therefore lists all eight and says that `--status --watchdog` never returns `wait_for_watchdog`; news-watch.md names it the same way.
- The parent's last line, `main()` line 1257: `supervise: {rc} {SAID.get(word, word)}{holder}. Run python3 -m aitrader.supervise --status and do what action says.` (AFTER, line 511). Words: `end_of_day` (restart_core line 277), `closed_today` (main line 962), `handover`/`signal`/`orphaned` (PLANNED line 215, codes 76/143/143), `halt` (line 279, codes 4/5/6), `lock_held` with ` pid N` (line 284 at the end; line 816 when another parent holds the parent's own lock at start), `crash_loop` printed as `tripped` (SAID line 510; lines 294, 297). The `3 lock_held` row of the table names both causes.
- S2, R8, R12: `aitrader/ownerlines.py` lines 74, 45, 50, copied character for character (the tests compare against `ownerlines.LINES`).

## TDD evidence

RED - `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_slot_files.py' -v` (from ai-trader/), before any prompt edit:
```
FAIL: test_no_prompt_rebases_and_every_prompt_fetches_merges_and_knows_s2
AssertionError: 'pull --rebase' unexpectedly found in 'Scheduled slot: CLOSE, DECIDE AND LEARN ... : close.md
FAIL: test_the_close_slot_copies_the_days_uptime_block_into_its_log
AssertionError: 0 != 1 : one step names the day's numbers
FAIL: test_the_close_slot_reports_and_the_skill_carries_r8_and_r12
AssertionError: 'uptime-report --day --notify' not found in 'Scheduled slot: CLOSE, ...
FAIL: test_the_watchdog_asks_status_and_no_longer_starts_the_bare_engine
AssertionError: Lists differ: [False, False, True, True] != [True, True, True, False]
Ran 5 tests in 0.022s
FAILED (failures=4)
```
Expected: the first test fails on `close.md` (it sorts first), as the brief says; the close, watchdog and SKILL tests fail because nothing was written yet. The leak test passed at RED: no slot file or text fixture held a leak (it is a guard). A check of its patterns on made-up strings (in a heredoc, never in a file) showed each pattern catches its kind (an id with a digit, an ntfy URL, an address, a `"topic"` value) and passes `<session-id>`, `trig_x`, `ntfy.sh/TOPIC`, `"topic": "TOPIC"`.

GREEN - the same command, three runs in a row (the file starts no process), each:
```
Ran 5 tests in 0.016s
OK
```
Also run: `test_news_supervised.py -k test_the_skill_says_how_to_stop_an_engine_and_what_to_do_on_e1` (it pins SKILL 3ב): OK.

## Whole suite

`safe python3 -m unittest discover -s tests` before commit 1: wall 366 s
```
Ran 855 tests in 365.595s

OK
```
Before commit 2: wall 352 s
```
Ran 855 tests in 350.645s

OK
```
The suite's printed noise (`[news] engine started on commit ...`, `[journal] skipped unreadable line ...`) comes from existing tests; the new file prints nothing.

## Files changed
- `ai-trader/tests/test_slot_files.py` (new)
- `ai-trader/skills/trader/slots/`: `close.md`, `midday.md`, `open.md`, `weekly.md`, `news-watch.md`, `dashboard.md`, `crypto-decide.md`, `crypto-fill.md`, `crypto-summary.md`; `news-watch-37.md` deleted
- `ai-trader/skills/trader/SKILL.md` (sections 0, 3א, 3ב, 4א)
- `ai-trader/CLAUDE.md` (hard rule 8)

## Tests added by ruling
- P37: `test_the_close_slot_copies_the_days_uptime_block_into_its_log` - exactly one line of `close.md` names `longest_blind_s`, and that line also holds `uptime-report --day`, `` `uptime` ``, `` `commits` `` and `logs/YYYY-MM-DD-close.md`.

## Self-review findings and what I did
1. The crypto loop as first written, `git fetch ... && git merge ... || break`, ended the loop on a failed fetch (a network blip), with nothing pushed. Changed to `git fetch ...; git merge ... || break`: only a failed merge ends it (commit 2, also in SKILL 4א).
2. SKILL 3ב says "the session does not start the engine itself", while the bullets kept below (restart before long work; after a fix, stop the task and start again) say "מפעילים". Added one sentence: "מפעילים" below means the parent, by `--status` (commit 2).
3. Checked that `news-watch.md` never tells a turn to run `--status` again right after a launch: a new parent that has not written its first mark, behind an old mark over 180 s, reads as `replace_parent` (status docstring, "unless it has not ticked yet"). The prompt has no such re-check.
4. `--relayed` needs at least one id (argparse `nargs="+"`): the prompt says nothing runs when `unsent` is empty.
5. No session, task or environment id, topic or address in the diff or the commit messages (grep of the diff with the leak patterns: no hit). No attribution lines.

## Departures from the brief, and why
1. **dashboard.md got one sentence (the git rule, no git step).** The brief's first test skips a file only when `"git " not in t`, and its comment says the dashboard prompt runs no git until Task 24. But every slot file Task 18 wrote, dashboard.md included, says "Never git stash.", so the skip never applies and the test as written demands the merge text in dashboard.md. Spec 4.7 puts the rule "in every scheduled prompt", and the brief's file list is "every file under skills/trader/slots/". So dashboard.md step 1 now ends: "This slot runs no git. The checkout's git rule, for the turns that do: `git fetch ...` and `git merge --no-edit origin/...`, never a rebase; a turn never ends with a merge in progress (complete it, or run `git merge --abort`); a conflict is reported with the S2 line ... never resolved by discarding." The dashboard still runs no git, and the test is unchanged. If the controller prefers otherwise, the alternatives are: the test's skip ignores the stash ban (`"git " not in t.replace("git stash", "")`), or it skips dashboard.md by name, as P22 does for watcher.md; then the sentence comes out.
2. **SKILL.md section 4א also changed** (the brief names 0, 3א, 3ב). Its crypto push loop held `git pull --rebase`, and the brief's fourth test asserts `"pull --rebase" not in skill`; Global Constraints ban any rebase in this checkout. It now matches the crypto slot files.
3. **kill_stray uses the two-minute wait, not "after 10 s kill -9".** Spec 4.4's row says "kill <pid> (after 10 s kill -9)" and calls it "today's rule [C skills/trader/SKILL.md:191-193]". Today's rule in SKILL 3ב (from the gate's follow-ups, pinned by `tests/test_news_supervised.py::test_the_skill_says_how_to_stop_an_engine_and_what_to_do_on_e1`) is that `kill <pid>` is a planned stop of up to two minutes and `kill -9` comes only after two minutes. The kill_stray row (SKILL and news-watch.md) follows that rule, so the section does not give two different waits for the same kill. replace_parent keeps the spec's "after 10 s kill -9": it kills a parent that is stalled, and the bullet is about the engine.
4. **news-watch.md step "postmortem"**: "Last step, never before the engine check" became "Never before the engine check", because the sync block (spec 4.4 step 7) now comes after it.
5. **Old SKILL 3ב bullet 1** (relaunch the bare engine on wake) was replaced by the new wake rule. It belongs to the launch procedure the brief replaces. The other bullets of 3ב are unchanged.
6. **Start-of-turn conflicts**: the brief describes the conflict rule only for the closing block. A conflict at the start sync now points to it ("On a conflict: step N's rule"), so no turn goes on with a merge in progress (Global Constraints: a turn never ends with one).

## Concerns
1. "Stop" on a conflict at the start sync means the slot does none of its duty: the close slot stores no decision for tomorrow, and the crypto morning summary is not delivered (S2 goes out instead). That is the literal "send S2 and stop". If the controller means "stop the git work, still do the duty on the local state", the start steps need one more sentence each.
2. dashboard.md's rule sentence (departure 1) is the controller's call. It is honest text the spec asks for, but it exists because the test reads "git stash" as git work.
3. The SKILL 3ב bullets kept as they were (restart before long work, the lock bullet, "after a fix, stop the task and start again") still describe the bare engine's own lock and exit code 3. With the added sentence they read as "through the parent", but they were written for the old flow. Task 24 or a later edit may want to restate them for the parent.
4. The cap row says to go back to `--handover` and set `supervisor.long_timeout_proven` back to false through the gate (spec 9). Until that flag is true nothing reaches this row. The session cannot change `config.json` outside the gate, so for that one launch it adds `--handover` and timeout 7200000 to the command itself.

## Fix round 1

Found HEAD `578cc77545c8bece13764e8350165925ab490e51` on `supervisor-build`, clean tree. One commit this round:
`9663262e` "Slot prompts: a conflict at the start sync no longer skips the slot's work". HEAD after:
`9663262e4a057eead9684b95dd66c6fbdbcd9758`. `git status --short` prints nothing. No attribution line in the message.

### F1 - fixed
The start-of-turn clause "On a conflict: step N's rule" (which led to "abort, send S2, and stop" before the duty) is
replaced in all seven slots that sync at the start. Each now reads: "On a conflict: `git merge --abort`, which discards
nothing, then go on with this slot's work on the local state; step N's merge meets the conflict again and reports it."
The closing blocks are unchanged: there the merge meets the conflict again, aborts, sends S2 (night slots: into the
night log) and stops without pushing. Step numbers checked against each file's closing step.
- `ai-trader/skills/trader/slots/close.md:2` (step 7)
- `ai-trader/skills/trader/slots/midday.md:2` (step 4)
- `ai-trader/skills/trader/slots/open.md:2` (step 4)
- `ai-trader/skills/trader/slots/weekly.md:2` (step 6; inside its parentheses)
- `ai-trader/skills/trader/slots/crypto-decide.md:2` (step 4)
- `ai-trader/skills/trader/slots/crypto-fill.md:2` (step 3)
- `ai-trader/skills/trader/slots/crypto-summary.md:2` (step 5)
So the close slot again runs verify, cycle (close-time stock stop check, tomorrow's decision) and postmortem during a
conflict; open fills; crypto decides and fills; the morning summary is delivered. `news-watch.md` has no start sync
(its sync is step 6) and `dashboard.md` runs no git: neither changed. SKILL.md sections 0 and 3א hold no start-conflict
"stop" (checked): unchanged.

Regression guard added: `ai-trader/tests/test_slot_files.py:54-65`,
`test_a_conflict_at_the_start_sync_is_aborted_and_the_slot_still_does_its_work`. For every slot whose step 1 holds the
start-sync form `&& git merge --no-edit origin/`, step 1 must hold `git merge --abort` and "then go on with this slot's
work on the local state", and must not hold "'s rule" (the pointer to the closing stop); the checked files must be
exactly the seven above. (First draft of the filter matched dashboard.md's rule sentence; narrowed to the `&&` form.)

### Tests run
RED - the final test file against HEAD 578cc775's slot texts (`git archive HEAD` of aitrader/tests/skills into a
scratch dir, new test file copied in, dir removed after), from that copy's ai-trader/:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_slot_files.py'`
```
FAIL: test_a_conflict_at_the_start_sync_is_aborted_and_the_slot_still_does_its_work (test_slot_files.SlotFiles...)
AssertionError: Lists differ: [False, False, True] != [True, True, False]
+ [True, True, False] : close.md
Ran 6 tests in 0.013s
FAILED (failures=1)
```
GREEN - in the gate clone, from ai-trader/, three runs in a row (the file starts no process):
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_slot_files.py' -v`
```
Ran 6 tests in 0.013s
OK
```
(each of the three runs: the same two lines).

Whole suite before the commit, from ai-trader/:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` - rc 0, wall 333 s
```
Ran 856 tests in 332.745s

OK
```
