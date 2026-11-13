# Task 19b report: the prompts act on the parent's last line, relaunch after a cleared halt, check a merge before making it, and never skip a slot's work on a conflict

Gate clone `.../scratchpad/clones/sup`, branch `supervisor-build`. Found HEAD `9663262e4a057eead9684b95dd66c6fbdbcd9758`
with a clean tree. Commits:
- `bed70cbb` docs(ai-trader): prompts act on the parent's last line, relaunch after a cleared halt, test a merge before
  making it, and never skip a slot's work on a conflict (the task, with the brief's message)
- `a6250f7c` test(ai-trader): the crypto loop test reads the throwaway remote from the temporary directory too (a
  self-review fix)

HEAD after: `a6250f7c0ec2820eebd938489577300c204f9918`. `git status --short` prints nothing. No attribution lines.

## What was implemented

Item by item, as the brief numbers them:

1. **The woken turn acts on the parent's last line.**
   - `news-watch.md`: the wake sentence is now three ordered steps:
     - (a) Read the parent's last line and exit code, and act by "the last-line table of SKILL.md section 3ב (it is the rule)". The cells are summarised in the prompt:
       - `75 tripped`: tail `.cache/news_live.log`; `git merge --abort` if `MERGE_HEAD` exists; the abort-fails rule.
       - Exit 1, exit 2 or any code not in the table: tail `.cache/supervise.log`. At most one launch per New York day, by `.cache/parent_relaunched`. If the file already holds today's NY date: no launch in this turn, and R12. Else write the date, and the launch comes in (b).
       - The cap with the long timeout: R8, by the table.
     - (b) `cd /home/user/OmniRoute/ai-trader && python3 -m aitrader.supervise --status`, and do what `action` says.
     - (c) Relay `unsent` exactly as step 3 does.
   - SKILL 3ב:
     - The wake bullet says the same in Hebrew. "הטבלה היא לקורא היומן" became "הטבלה היא הכלל".
     - The third column is now "מה עושים (ואז `--status`)". Each existing cell keeps its expected action, written as "כלום; `--status` אומר ...".
     - The `75 tripped` cell and the last row got the new rules. The last row now reads `1`, `2` (`a bad argument or config`, or an argparse error), or any code or line not in the table.
     - The R8 (cap) row is unchanged.
2. **A cleared halt launches.** The `halted` bullet of `news-watch.md` and the halted row of SKILL 3ב now add: when `--clear-halt` exits 0, run `--status --watchdog` again and do what `action` says (normally `launch`). "no launch" became "no launch while the halt stands" in both, so a literal reading is not contradicted by the new sentence.
3. **Named directories in `news-watch.md`.**
   - The launch is "`cd /home/user/OmniRoute && ` followed by `launch.command`", and "(from the repo root)" is gone.
   - Every supervise command starts `cd /home/user/OmniRoute/ai-trader && python3 -m aitrader.supervise`: `--status --watchdog` (twice), the wake's `--status`, `--clear-halt` and `--relayed`.
4. **Check before merge, everywhere.**
   - Every closing block (open 4, midday 4, close 7, weekly 6, news-watch 6): `git fetch`, then the check `git merge-tree --write-tree --name-only HEAD origin/ccr-120121ba-vsvwlj`. Only on exit 0 comes `git merge --no-edit`, then the push.
   - Tries: on a rejected push, fetch, check and merge again, up to 5 tries. A merge refused because of uncommitted files: commit the state and try again, within the same tries.
   - Conflict rule: the check exits 1 and prints the conflicted files after the tree id. Then: do not merge, push nothing, S2 with the first conflicted file's name, and go on with the steps after this one.
   - Backstop: never end with a merge in progress, `git merge --abort` if one is. If the abort fails: push nothing, S2 with the file the abort named, touch nothing else, go on.
   - Every start sync (close, open, midday, weekly, the 3 crypto files) is one chain: `git fetch ... && git merge-tree ... && git merge --no-edit ...`. On a conflict the merge never runs.
   - Start-sync rules: refused merge, then commit the state and "run that line again". Conflict, then "do not merge, then go on with this slot's work on the local state; step N's check meets the conflict again and reports it". Plus the backstop; the night slots write S2 into the night log.
   - `dashboard.md`'s git-rule sentence (Ruling 56(1)) now states the same rule.
5. **No "and stop".**
   - Every closing block goes on after a conflict:
     - open and midday: "the steps after this one";
     - close: "the steps after this one (the daily digest)";
     - weekly: "the weekly summary below", which is in the same step;
     - crypto-summary: the steps after it.
   - In open.md and midday.md, step 1 now says "commit the state (only step 4's commit, not its sync)".
6. **The crypto push loop** in crypto-decide, crypto-fill, crypto-summary and SKILL 4א:
   ```
   ok=; for i in 1 2 3 4 5; do git fetch origin B; git merge-tree --write-tree --name-only HEAD origin/B || break; git merge --no-edit origin/B || break; git push -u origin B && { ok=1; break; }; sleep $((2**i)); done; test -n "$ok"
   ```
   - A failed fetch still runs on and waits.
   - A conflict breaks before any merge, so nothing is aborted.
   - Exit 0 means pushed.
   - The sentence after it in each slot (and in Hebrew in 4א):
     - A nonzero end with conflicted files printed is a conflict: push nothing; S2 goes into the night log at night, and the summary slot sends it with PushNotification; then go on.
     - A refused merge (`would be overwritten by merge`): commit the state and run the loop once more.
     - Any other nonzero end with no conflicted file: the push failed, and the commit waits for the next slot.
     - The backstop.
7. **CLAUDE.md "One builder at a time"**: `git pull` became "sync as hard rule 8 says". That is `git fetch origin <branch>`, then the check (exit 1 = conflict: do not merge, report it), then on exit 0 `git merge --no-edit origin/<branch>`, where `<branch>` is the branch this checkout tracks.
8. **Tests** in `tests/test_slot_files.py`:
   - (a) `test_every_slot_that_runs_git_checks_for_a_conflict_before_it_merges`
   - (b) `test_no_slot_file_stops_on_a_conflict`
   - (c) `test_the_woken_turn_acts_on_the_parents_last_line_and_a_cleared_halt_launches`
   - (d) `test_every_supervise_and_launch_command_of_the_watchdog_starts_from_a_named_directory`
   - (e) `test_claude_md_syncs_without_git_pull`
   - (f) class `CryptoPushLoop`, three real-git tests:
     - conflict: nonzero, no MERGE_HEAD, tree/HEAD/file unchanged, the file name printed, nothing on the remote;
     - clean: 0, both commits on the remote;
     - always-rejecting pre-receive hook: nonzero, the hook ran exactly 5 times, the commit local only.
   - The start-sync test (Task 19 F1) now filters on `&& git merge-tree ...` and checks the same seven files as before.

S2 and R12 were inserted from `ownerlines.LINES` by a scratch script, never retyped. R8 was left untouched in SKILL 3ב.

### Where each last line of the parent was read (aitrader/supervise.py at 9663262e)
- `supervise: {rc} {word}{holder}. Run ... --status and do what action says.`, `main` line 1257, with `SAID` (line 510) and `AFTER` (511). Words:
  - `end_of_day` (0): `restart_core` line 277.
  - `closed_today` (0): `main` line 962.
  - `halt` (4/5/6): line 279.
  - `lock_held pid <engine pid>` (3): line 284.
  - `tripped`, the word `crash_loop` turned into `tripped` by `SAID` (75): lines 294 and 297.
  - `handover` (76), `signal` (143), `orphaned` (143): `PLANNED` line 215, returned at 248/275.
- `supervise: 3 lock_held pid <parent pid>. Run ...`, `main` line 816: another parent holds the parent's own lock at start.
- Exit 2, on stderr:
  - `supervise: a bad argument or config (<class>)`, `main` line 789 (line 799 is `--status` only);
  - an argparse error (`ap.error`, lines 767/770, returned as `e.code` at 772).
- Exit 1: an uncaught exception, a Python traceback (no line of supervise's own).
- The harness's own cap message ("was stopped after reaching its background time limit") has no code.
- The table covers all of these: exit 2 and exit 1 fall in the new last row.

## TDD evidence

RED. From ai-trader/, before any text edit:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_slot_files.py' -v`
```
FAIL: test_a_conflict_ends_nonzero_names_the_file_and_leaves_no_merge_and_the_tree_as_it_was
AssertionError: 0 == 0 : Auto-merging ai-trader/state/backlog.md ... CONFLICT (content): Merge conflict in ai-trader/state/backlog.md
FAIL: test_a_remote_that_rejects_every_push_ends_nonzero_after_five_tries_with_the_commit_still_local
AssertionError: 0 == 0 : Already up to date. (x5)
FAIL: test_a_conflict_at_the_start_sync_is_aborted_and_the_slot_still_does_its_work
AssertionError: Lists differ: [] != ['close.md', 'crypto-decide.md', 'crypto-f[61 chars].md']
FAIL: test_claude_md_syncs_without_git_pull
AssertionError: '`git pull`' unexpectedly found in '# AI Trader - rules ...
FAIL: test_every_slot_that_runs_git_checks_for_a_conflict_before_it_merges
AssertionError: 'git merge-tree --write-tree --name-only HEAD origin/' not found in 'Scheduled slot: CLOSE, ...
FAIL: test_every_supervise_and_launch_command_of_the_watchdog_starts_from_a_named_directory
AssertionError: 0 != 4
FAIL: test_no_slot_file_stops_on_a_conflict
AssertionError: Lists differ: ['close.md', 'crypto-decide.md', 'crypto-f[78 chars].md'] != []
FAIL: test_the_woken_turn_acts_on_the_parents_last_line_and_a_cleared_halt_launches
AssertionError: Lists differ: [False, False, False] != [True, True, True]
Ran 15 tests in 0.662s
FAILED (failures=8)
```
Each failure is the one its item names:
- (f) The loop's regex also matches the old loop, so the old loop itself was run.
  - With a conflict it exits 0 and leaves the merge in progress (gitflow-1).
  - Against an always-rejecting remote it exits 0 after five pushes.
  - The clean case passed with the old loop as well.
- The start-sync test finds no file in the new form.
- (e) `git pull` is still in CLAUDE.md.
- (a) No file has the check.
- (d) 0 of the 4 supervise commands start with the cd.
- (b) Seven files say "and stop".
- (c) None of the three names is there.

The leak test and the new copies-are-one-loop test passed at RED. They are guards: the old loop is the same text in all four places.

GREEN. The same command, three runs in a row (the file starts git and bash processes), each run:
```
Ran 15 tests in 0.690s
OK
```
(0.69 s, 0.76 s and 0.69 s after the fix commit; 0.81 s, 0.97 s and 1.02 s before it.) No `crypto-loop-*` directory is left in /tmp after the runs. Also run: `test_news_supervised.py -k test_the_skill_says_how_to_stop_an_engine_and_what_to_do_on_e1` (it pins SKILL 3ב): OK.

A manual check, not committed, with the loop read from crypto-fill.md and origin set to a path that does not exist: 5 tries, each with the back-off, then rc 1 and no MERGE_HEAD. So a failed fetch waits and tries again.

## Whole suite

From ai-trader/: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`
- Before commit 1, rc 0, wall 328 s:
  ```
  Ran 865 tests in 327.717s

  OK
  ```
- Before commit 2, rc 0, wall 339 s:
  ```
  Ran 865 tests in 337.907s

  OK
  ```

865 = 856 + 9 new tests. The suite's printed noise comes from existing tests; the new tests print nothing.

## Files changed
- `ai-trader/skills/trader/slots/`: `close.md`, `crypto-decide.md`, `crypto-fill.md`, `crypto-summary.md`, `dashboard.md`, `midday.md`, `news-watch.md`, `open.md`, `weekly.md`
- `ai-trader/skills/trader/SKILL.md` (3ב: the halted row, the wake bullet, the last-line table; 4א: the loop and the sentence after it)
- `ai-trader/CLAUDE.md` (the "One builder at a time" line only)
- `ai-trader/tests/test_slot_files.py`

No other test needed a change.

## Self-review findings and what I did
1. **A double launch.** As first read, the brief's exit-1/2 cell says "write the date into it and launch", and then "run --status and do what action says". Read literally, that is a launch and then `--status` right after it. A new parent that has not marked yet, behind a mark older than 180 s, reads as `replace_parent`, and the turn would kill the parent it just started (Task 19's self-review item 3). The R12 branch says "do not launch", and then `--status` says `launch`. Fixed in the text: the cell writes the marker, and the launch comes from (b); in the R12 branch "(in (b) a `launch` is not run)". The same holds in SKILL: "חוץ מ-`launch` כשהטבלה אמרה לא להפעיל בתור הזה". See departure 1.
2. **"merge again" at the start syncs.** After a refused merge, "merge again" would run only the merge. It became "run that line again", so the check runs too.
3. **The test reached the gate clone's directory.** `CryptoPushLoop.on_remote` ran `git --git-dir <tmp remote> merge-base` with no cwd, so from the gate clone's ai-trader/. It is harmless with `--git-dir`, but against the brief's "never touch the gate clone's .git" and the class docstring. Fixed (`cwd=self.tmp`, commit 2).
4. **Leak scan.** The added lines hold no id, address or topic pattern. The test identity uses `nobody`, not an address.
5. **The weekly block.** Its summary push is in the same step as the git block, so "the steps after this one" would skip it. The rule there says "go on with the weekly summary below".

## Departures from the brief, and why
1. **The exit-1/2 cell's launch goes through `--status`** (self-review 1). The brief's "else write the date into it and launch; then run --status and do what action says" became "write the date, and launch in (b)". "Do not launch" also holds against a `launch` from `--status`. Exactly one launch, or none, happens per woken turn, which is the brief's effect. A literal reading of the brief's order would launch twice, or override its own "do not launch".
2. **R12 is sent only on the no-launch branch,** as the brief and Ruling 57 ("then R12") say. The first crash of the day relaunches silently. The old cell said "launch once; R12" every time. Spec 8 says R12 is sent when "the parent ended with a code that is not in the table". See concern 1.
3. **A merge refused inside the crypto loop: "commit the state and run the loop once more".** The loop cannot commit by itself, so "within the same tries" cannot hold literally there. The loop breaks on a refused merge, so no back-off is wasted, and the prose bounds the retry to one more run.
4. **dashboard.md's git-rule sentence was updated.** It runs no git, but under Ruling 56(1) it carries the rule. Test (a) uses the existing test's own filter (`"git " in t`), so it includes the dashboard.
5. **One test beyond item 8:** `test_the_crypto_slots_and_the_skill_carry_the_same_loop`. The loop is run from crypto-fill.md only, and this test proves the other three copies are the same line, so none of them is untested.
6. **SKILL 3ב's wake bullet uses the absolute cd** for its `--status`, as news-watch.md does. The brief names the cd for news-watch.md only.
7. **Small wording changes in the lines being changed:** "no launch" became "no launch while the halt stands" (item 2); "(from the repo root)" was removed from the launch (replaced by the cd); "complete it, or run `git merge --abort`" became "if one is, `git merge --abort`" (the brief's backstop wording).

## Concerns
1. **R12 is sent only on the no-launch branch** (departure 2). On the first crash of a day the owner hears nothing: a parent that dies by an exception sends no line of its own. If the controller wants R12 on the first relaunch too, the cell needs one more clause. The R12 text "הפעלתי אותו מחדש פעם אחת" reads true in both places.
2. **SKILL sections 0 and 3א still sync with a bare `git fetch ... && git merge --no-edit`, without the check.** The brief limits SKILL edits to 3ב and 4א. Section 0 runs at the start of every session; 3א step 5 runs in the trader's live checkout during a loss review. SKILL 3ב's engine-exit bullet ("after 7, complete the pull or git merge --abort") was also left as Task 19 had it.
3. **The parent is relaunched every 30 minutes, with R12 every 30 minutes.** The once-a-day marker gates only the woken turn. The :07/:37 watchdog still launches on `--status --watchdog` = `launch`, as the brief intends. A parent that dies at start is therefore relaunched every 30 minutes, and each death after the first sends R12 again.
4. **The marker can be used up by the session itself.** If the harness wakes the session for a parent it killed with `kill -9` (replace_parent's fallback, exit 137), the turn falls into "any code not in the table" and writes the day's marker. The watchdog still relaunches later. Pre-existing and not introduced here: a woken turn's `--status` right after a fresh launch can read `replace_parent`, before the new parent's first mark.
5. **`git add ai-trader/state/` in news-watch step 6 needs the repo root as cwd,** while steps 2-5 now leave the shell in ai-trader/. The brief names only the supervise and launch commands for the cd. A model sees git's pathspec error at once, but the step could start with `cd /home/user/OmniRoute`.
6. **`git merge-tree` exits 1 also for a ref that does not exist** ("not something we can merge", checked on git 2.43), with no file printed. The texts call a nonzero end "a conflict" only when conflicted files are printed. In the prose blocks a literal reader could take such a 1 for a conflict and send S2 without a file. It cannot happen while `origin/<branch>` exists, which it does in every checkout that has fetched once.
7. **Git version.** `git merge-tree --write-tree` needs git 2.38+. The container has 2.43, and the real-git test fails loudly on an older git, as the prompts would.

## Fix round 1

Start state checked: HEAD a6250f7c0ec2820eebd938489577300c204f9918, branch supervisor-build, tree clean.
Commit of this round: `fde6bdbf test(ai-trader): run the crypto push loop test's git and bash with clean_env`
(HEAD fde6bdbf8b32d5bd5dc800a52f1ad428197425a6). `git status --short` after it prints nothing.

### [F1] fixed
- `ai-trader/tests/test_slot_files.py:122-124` (class `CryptoPushLoop.setUp`): the environment copy of `os.environ`
  minus `GIT_*` is gone. It is now `self.env = no_phone.clean_env(HOME=str(self.tmp), GIT_CONFIG_NOSYSTEM="1",
  GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="nobody",
  GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="nobody", LC_ALL="C")` - the reviewer's suggestion verbatim. Every
  git call (`git()`, `on_remote()`) and the bash run of the loop (`run_loop()`) use `self.env`, so all of them now get
  only PATH, HOME (the temp dir), PYTHONPATH, NO_PROXY=127.0.0.1 and the git overrides.
- `ai-trader/tests/test_slot_files.py:112-113` (the class docstring): says the environment is `no_phone.clean_env()`
  (no GIT_*, AITRADER_*, proxy or BASH_ENV variable of this process) in place of "no GIT_* variable of this process".
- Nothing else changed; no assertion touched.

Proof that the defect is gone (a probe, not committed): a `BASH_ENV` script that appends to a marker file and runs
`exit 7`, handed to python only (inside the safe wrapper, because the wrapper is itself a bash script and would source
it first):
```
/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe env BASH_ENV=<scratch>/bashenv.sh python3 -m unittest discover -s tests -p '<file>' -k CryptoPushLoop
```
- the file as of a6250f7c (copied out with `git show` into a temporary probe file, deleted right after):
  `Ran 4 tests ... FAILED (failures=2, errors=1)`, marker lines: 3 (the loop's bash sourced the inherited BASH_ENV);
- the file after the fix: `Ran 4 tests in 0.698s` / `OK`, marker lines: 0.

### Covering tests, 3 times in a row
Command (from `<clone>/ai-trader`):
```
for n in 1 2 3; do /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_slot_files.py' -v; done
```
Output, each of the three runs: all 15 tests `... ok` (4 CryptoPushLoop, 11 SlotFiles), ending
```
Ran 15 tests in 0.814s   (run 2: 0.791s, run 3: 0.631s)

OK
```

### Whole suite, once, before the commit
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` - exit 0,
wall 343 s. Last three lines:
```
Ran 865 tests in 342.091s

OK
```
No trading rule, config.json or file the time machine loads is touched; the change is in one test file only.
