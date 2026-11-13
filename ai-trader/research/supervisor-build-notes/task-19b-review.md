# Task 19b review (base 9663262e, head a6250f7c)

Review package: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-19b.diff` (2 commits, 12 files, +188/-44). Read in one pass. No test was re-run.

### Spec Compliance

Items 1 to 8 are all implemented. Two issues:

- **Spec issue (Important).** `ai-trader/tests/test_slot_files.py:411-414`: the `CryptoPushLoop` subprocess environment is copied from `os.environ`, minus the `GIT_*` variables. Global Constraint 10 says every process a test starts gets `helpers.no_phone.clean_env()`. Details are under Issues.
- **Plan-mandated gap (Important).** SKILL sections 0 and 3א still sync without the check, because the brief limits SKILL edits to 3ב and 4א. Details are under Issues.

Checked against the diff:
- Item 1. The steps are in order in the text:
  - `news-watch.md` step 2: (a) the last-line table "(it is the rule)", (b) the cd'd `--status`, (c) relay as in step 3.
  - SKILL 3ב: the wake bullet (א/ב/ג), "הטבלה היא הכלל", and the new third column.
  - The `75 tripped` cell: tail `news_live.log`, then `MERGE_HEAD`, then `git merge --abort`.
  - The exit 1/2/other cell: tail `supervise.log`, then the `.cache/parent_relaunched` marker with the NY date, then R12 on the no-launch branch.
  - The R8 row is unchanged.
- Item 1, last lines. I checked the report's sources in `aitrader/supervise.py` at the head:
  - 215 (`PLANNED`), 277 (`end_of_day`), 279 (halt), 284 (`lock_held`), 294 and 297 (`crash_loop`), 510-511 (`SAID`/`AFTER`).
  - 767, 770 and 772 (argparse), 789-790 (exit 2), 816 (parent's own lock), 962 (`closed_today`), 1257 (the printed line).
  - All are present. The table covers every one; exits 1 and 2 fall in the last row.
- Item 2. The `halted` bullet and the halted row: "--clear-halt ... when it exits 0, run `--status --watchdog` again". Present in both.
- Item 3. Every `python3 -m aitrader.supervise` in `news-watch.md` starts `cd /home/user/OmniRoute/ai-trader && ` (5 of 5). The launch is "`cd /home/user/OmniRoute && ` followed by `launch.command`".
- Item 4. The check `git merge-tree --write-tree --name-only HEAD origin/...` comes before every merge:
  - Every start sync is one `&&` chain: close, open, midday, weekly and the 3 crypto files.
  - Every closing block has it: open 4, midday 4, close 7, weekly 6, news-watch 6.
  - dashboard.md's git rule has it.
  - SKILL 4א's loop has it.
  - Each one has the refused-merge rule, the backstop and the abort-fails rule.
- Item 5. "and stop" is gone from every slot file. Each closing block goes on after a conflict, and weekly names "the weekly summary below". open and midday step 1 say "(only step 4's commit, not its sync)".
- Item 6. The loop has `ok=`, the check, `|| break` and `{ ok=1; break; }`, and ends with `test -n "$ok"`. The fetch is not `&&`-chained, so a failed fetch still waits. The sentence after it is present in all three crypto files and in 4א.
- Item 7. CLAUDE.md:236-239: fetch, then the check, then `git merge --no-edit`. There is no `` `git pull` ``.
- Item 8. Every named test exists with the brief's assertion:
  - (a) `test_every_slot_that_runs_git_checks_for_a_conflict_before_it_merges`
  - (b) `test_no_slot_file_stops_on_a_conflict`
  - (c) `test_the_woken_turn_acts_on_the_parents_last_line_and_a_cleared_halt_launches`
  - (d) `test_every_supervise_and_launch_command_of_the_watchdog_starts_from_a_named_directory`
  - (e) `test_claude_md_syncs_without_git_pull`
  - (f) the three `CryptoPushLoop` cases. They read the line from crypto-fill.md, and the only substitution is the sleep, with a comment. The repos are a bare remote plus two clones on `ccr-120121ba-vsvwlj`. The assertions: nonzero, no MERGE_HEAD, HEAD/status/file unchanged; 0 with both commits on the remote; nonzero after 5 tries (the hook counts them), commit local.
  - The start-sync test now filters on `&& git merge-tree ...` and still lists the same 7 files.
- Commits: two, both with plain messages and no attribution lines (`git log 9663262e..a6250f7c`).

Extra, judged acceptable:
- `test_the_crypto_slots_and_the_skill_carry_the_same_loop`, a small guard that proves the untested copies are the same line.
- SKILL 3ב's wake bullet uses the absolute cd too.
- Departure 1 (the launch goes through (b)) avoids the launch-then-`--status`-reads-`replace_parent` kill, and keeps the brief's effect.

Cannot verify from this diff:
- What the harness reports when a background task is ended by TaskStop or by the `kill -9` fallback of `replace_parent`: whether it wakes the session, and with which code. This decides whether the session's own kill can use up the day's relaunch marker (see Minor).
- That `launch.command`, as `--status` prints it, is meant to run from the repo root, so that `cd /home/user/OmniRoute && ` is the right prefix.
- That the trader session's VM has git 2.38 or newer, which `merge-tree --write-tree` needs (the gate container has 2.43).
- That no other test pins the old wording. The report claims the full suite passed (865 OK, twice); not re-run here.

### Strengths
- Every last line of the parent is traced to a `supervise.py` line, and the citations check out (list above).
- The real-git test runs the exact line from the prompt in throwaway repositories, with a guard that the temporary directory is not under the checkout (`assertNotIn(ROOT, self.tmp.parents)`).
  - The rejection case counts the hook's runs (5), not just the exit code.
  - The conflict case checks status, HEAD, the file's content and the remote.
  - The RED run shows the old loop exiting 0 both with a conflict and against a remote that rejects every push, which is the real defect.
- The self-review caught three real problems:
  - the double launch in the literal brief order;
  - "merge again" skipping the check after a refused start merge;
  - the weekly block's summary sitting in the same step.
- S2 and R12 come from `ownerlines.LINES`, and test (c) pins R12 in `news-watch.md`.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. **`ai-trader/tests/test_slot_files.py:411-414`: the test's git and bash processes do not get `clean_env()`.**
   - What is wrong: `self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}` passes on every other variable: the proxy variables, every non-phone `AITRADER_*`, and `BASH_ENV`, which a non-interactive `bash -c` sources.
   - Why it matters:
     - Global Constraint 10 says every process a test starts gets `helpers.no_phone.clean_env()` (no `AITRADER_*`, no proxy, `NO_PROXY=127.0.0.1`).
     - The project already has the pattern for git: `tests/test_supervise.py:200`, `GIT_ENV = {**no_phone.clean_env(), "GIT_CONFIG_GLOBAL": "/dev/null", ...}`.
     - The remote is a local path, so no network is reached today. But an inherited `BASH_ENV` or another stray variable can change what the loop does under test.
   - Fix: `self.env = no_phone.clean_env(HOME=str(self.tmp), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="test", ...)`. Then drop the `os.environ` copy (PATH is kept by `clean_env`).
2. **The same checkout still has two syncs without the check (plan-mandated).**
   - Where: `ai-trader/skills/trader/SKILL.md:35` (section 0, "כל סשן") and `:160` (3א, after a loss review). Both are `git fetch ... && git merge --no-edit origin/ccr-120121ba-vsvwlj` / `git merge --no-edit`, unchanged.
   - Why it matters:
     - The brief limits SKILL edits to 3ב and 4א, so this was left on purpose (report concern 2). But the slots send the trader session to exactly these texts: close.md "Follow ... sections 0-3", and open 5, midday 5, close 4 and news-watch 5 → 3א.
     - A conflict at the 3א sync, during market hours in the live checkout, leaves MERGE_HEAD and a `UU` file. That is the gitflow-1 hazard this task exists to remove.
     - The slot's backstop sits in an earlier step. Where the engine rewrites a cleanly merged file, `git merge --abort` fails, so the merge in progress blocks later commits and can give `tree_busy` on restart.
     - The new rule now contradicts SKILL 0 and 3א.
   - Fix: a follow-up card (before Task 20 replaces the texts, or with it) that puts the same check before both merges in SKILL 0 and 3א.

#### Minor (Nice to Have)
- `news-watch.md` step 2(a), R12 branch: "in (b) a `launch` is not run" does not say whether the "then launch" of `replace_parent` and `kill_stray` is also withheld. One more clause would close it.
- `news-watch.md` step 2(a), `75 tripped`: the abort-fails branch ends at "touch nothing else", with no "and go on". It is unclear whether (b) runs (a launch while MERGE_HEAD stands would end with 7 again).
- `news-watch.md` step 2(a) and the SKILL 3ב last row: a parent ended by the session's own `kill -9`, in the `replace_parent` fallback (137, no line), falls in "any code not in the table" and uses up the day's marker. A later genuine crash that day is then not relaunched on wake, and no stop look runs until the next :07/:37 watchdog (at most 30 minutes). The brief's rule causes this; it is rare.
- The same cell: a parent that dies at start is still relaunched by every :07/:37 watchdog, so R12 reaches the owner about every 30 minutes all day. The brief mandates this; R12 carries no once-a-day limit.
- `ai-trader/CLAUDE.md:236`: "sync as hard rule 8 says" introduces a check that hard rule 8 (lines 188-190: "`git fetch`, then `git merge --no-edit`") does not name. The brief restricts the edit to this line; the wording claims more than rule 8 says.
- `ai-trader/tests/test_slot_files.py:475-478`: `test_the_crypto_slots_and_the_skill_carry_the_same_loop` compares a set, so a file that loses its loop entirely still passes. Assert one match per text.
- `crypto-*.md` and SKILL 4א: after a refused merge, "commit the state and run the loop once more" allows up to 10 tries, not "within the same tries". This is departure 3; the one-line loop cannot commit by itself, so it is acceptable.
- Start sync plus closing block: if the start's `git merge --abort` fails, the closing block's backstop meets the same merge and sends S2 a second time for one stuck merge.
- `news-watch.md` step 2(a), exit 1/2 cell: it reads `.cache/supervise.log` "(in ai-trader/)" with no cd command, while the `75 tripped` cell names one. Item 3's named-directory rule is half applied inside one bullet.
- `news-watch.md` step 6: `git add ai-trader/state/` needs the repo root as the current directory, but steps 2-3 leave the shell in `ai-trader/`. This was already so before the task (the old step 2 also cd'd into ai-trader) and is outside item 3's list (report concern 5).
- The report says the whole suite prints noise from existing tests. None of it comes from the new tests (the file's runs print only `Ran 15 tests ... OK`).

### Assessment
**Task quality: Needs fixes.**

The texts do what items 1-7 ask, the last lines are traced correctly, and the real-git test is a faithful, strong behavioural check. Two things should be fixed:
- The new test class must start its processes with `clean_env()`, as Global Constraint 10 and the existing `GIT_ENV` pattern require.
- The plan's scope leaves SKILL 0 and 3א syncing without the check in the live checkout, which needs a follow-up before the texts are trusted as "no merge is ever left in progress".
