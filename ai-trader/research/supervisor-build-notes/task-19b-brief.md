### Task 19b: the prompts act on the parent's last line, relaunch after a cleared halt, never leave a merge in progress, and never skip the slot's work on a conflict

**Kind:** BUILD (texts and one test file). **Authority:** the controller's Ruling 57 in the ledger (`progress.md`), from
the adversarial check of Task 19's texts (findings consistency-1, -2, -3, -5, -6 and gitflow-1 to -5, all verified real).
Not in the plan. It must be committed before Task 20 replaces the scheduled tasks' texts. It changes no trading rule and
touches no file the time machine loads.

**Files:** Modify `ai-trader/skills/trader/slots/*.md` (the nine files Task 19 left), `ai-trader/skills/trader/SKILL.md`
(sections 3ב and 4א only), `ai-trader/CLAUDE.md` (the "One builder at a time" line only), `ai-trader/tests/test_slot_files.py`.
Read every file first, and the code each sentence talks about (`aitrader/supervise.py`: `status`, `main`'s last lines,
`clear_halt`; `aitrader/ownerlines.py`: R8, R12, S2). Keep every other line as Task 19 left it; change only what is named
here. S2, R8 and R12 texts are copied from `ownerlines.py` as built, never retyped.

1. **The woken turn acts on the parent's last line.** Today `news-watch.md` says, for a background task that ended by
   itself, only "read its last line, run --status, and do what action says", and SKILL 3ב labels the parent's last-line
   table "for the log reader". So no text the session follows sends R12 or R8, nothing limits a relaunch, and the woken
   turn relays nothing. A parent that dies at start (a bad config: exit 2, no row written) is relaunched every time the
   session wakes, without limit, and the owner never hears of it. From now on the wake sentence says: read the parent's
   last line and act by the last-line table of SKILL 3ב. That table stops being "for the log reader" and becomes the
   rule. Its cells say what to do:
   - `75 tripped`: read the last 20 lines of `.cache/news_live.log` first; if a merge is in progress, `git merge --abort`.
   - Exit 1, exit 2, or any code not in the table: read the last 20 lines of `.cache/supervise.log`. Launch again at most
     once per New York day. The marker is the file `.cache/parent_relaunched`, which holds that day's New York date: if
     it already holds today's date, do not launch and send R12; else write the date into it and launch.
   - Stopped at the cap with the long timeout: R8, as the table already says.
   Then run `--status` and do what `action` says. Then relay `unsent` exactly as step 3 does (PushNotification per
   text, then `--relayed` with the ids). Keep the cells that exist and match the code; read `main` for every last line
   the parent can print, and say in the report where you read each one.
2. **A cleared halt relaunches at once.** In the `halted` bullet of `news-watch.md` and the halted row of SKILL 3ב, after
   `--clear-halt` add: when it exits 0, run `--status --watchdog` again and do what `action` says (normally `launch`).
3. **Every command runs from a named directory.** The Bash tool keeps `cd` between calls, so a command that depends on
   the current directory fails after an earlier `cd`. In `news-watch.md`:
   - the launch becomes `cd /home/user/OmniRoute && ` followed by `launch.command`;
   - the wake command becomes `cd /home/user/OmniRoute/ai-trader && python3 -m aitrader.supervise --status`;
   - every other supervise command in that file starts the same way.
   The crypto files already use `cd /home/user/OmniRoute`.
4. **A conflict is found before the tree is touched.** `git merge --abort` fails, and the merge stays in progress, when
   the running engine rewrites a file that the conflicted merge had already written cleanly (reproduced on git 2.43:
   `Entry ... not uptodate`, MERGE_HEAD stays). A merge in progress in the live checkout blocks every later commit and can
   keep the parent from restarting the engine (`tree_busy`). From now on every sync, at the start or at the close, in
   every slot file and in SKILL 4א, goes like this:
   - After `git fetch origin ccr-120121ba-vsvwlj`, first run `git merge-tree --write-tree --name-only HEAD
     origin/ccr-120121ba-vsvwlj`. It touches neither the index nor the tree.
   - Exit 1 is a conflict. Its output names the conflicted files. Do not merge; follow that step's conflict rule (item
     5), with the first conflicted file's name in S2's `{file}`.
   - Exit 0: `git merge --no-edit origin/ccr-120121ba-vsvwlj`.
   - If that merge is refused because of uncommitted files, commit the state and try again, within the same tries.
   - The backstop stays: never end the turn with a merge in progress; `git merge --abort` if one is. If the abort itself
     fails, push nothing, send S2 with the file the abort named, touch nothing else, and go on.
5. **A conflict never skips the slot's work.** In `open.md`, `midday.md`, `close.md`, `weekly.md` and
   `crypto-summary.md`, the closing block ends a conflict with "send S2 ... and stop", but steps still follow it there:
   - open: its postmortem and the fills line;
   - midday: its postmortem and the down-6% line;
   - close: the daily digest;
   - weekly: its summary;
   - crypto-summary: its loss review.
   The old texts ran them whatever the push did. From now on the conflict rule of every closing block, in every slot
   file, is: send S2, push nothing, and go on with the steps after this one; discard nothing. No slot file says "and
   stop". The start sync keeps its rule (go on with the slot's work on the local state). In `open.md` and `midday.md`,
   step 1's "commit the state first (step 4)" becomes "commit the state (only step 4's commit, not its sync)".
6. **The crypto push loop ends with a code that means something.** In `crypto-decide.md`, `crypto-fill.md`,
   `crypto-summary.md` and SKILL 4א, the one-line loop exits 0 even after a conflict, which leaves MERGE_HEAD and a `UU`
   file, and even after five failed pushes. Rewrite it with item 4's check inside. Two things stay:
   - a failed fetch waits and tries again (Task 19's fix round, 578cc775);
   - a conflict aborts nothing it did not start.
   It ends with `test -n "$ok"` (or the same effect), so 0 means pushed. Then one sentence: a nonzero end with conflicted
   files printed is a conflict, handled by that slot's conflict rule. The night slots write S2 into the night log, as
   now; the summary slot pushes it. A nonzero end with none printed means the push failed and the commit waits for the
   next slot.
7. **CLAUDE.md's last `git pull`.** In `ai-trader/CLAUDE.md`, the "One builder at a time" line says "Before changing one of
   these: `git pull`". Make it the same sync as hard rule 8: fetch, item 4's check, then `git merge --no-edit`.
8. **Tests** in `tests/test_slot_files.py`:
   - (a) Every slot file that runs git names `git merge-tree --write-tree --name-only HEAD origin/` and `git merge --abort`.
   - (b) No slot file contains "and stop".
   - (c) `news-watch.md` names the last-line table, `.cache/parent_relaunched`, R12's text from `ownerlines.py`, and
     `--status --watchdog` again after `--clear-halt`.
   - (d) Every wake and launch command in `news-watch.md` starts with `cd /home/user/OmniRoute`.
   - (e) `ai-trader/CLAUDE.md` contains no `` `git pull` ``.
   - (f) A real-git test of the crypto loop as written. Read the loop's line from `crypto-fill.md`, substituting nothing.
     In a temporary directory, build a local bare remote and two clones on branch `ccr-120121ba-vsvwlj`, the remote named
     `origin` in each. Run the line with bash in one clone for each case:
     - the other clone pushed a conflicting change: the line exits nonzero, no `.git/MERGE_HEAD`, the tree is unchanged;
     - the other clone pushed a clean change: the line exits 0, and the remote holds both commits;
     - a remote whose pre-receive hook always rejects: the line exits nonzero after its tries, the commit is still local.
     Make the sleeps short: the test may replace `sleep $((2**i))` with `true` in the copy it runs, and must say so in a
     comment. Never touch origin, the network or the gate clone's own `.git`.
   - Adjust Task 19's start-sync test to the new first-line form; it must still check every file it checked.
   Fix any other test the texts break, and say which in the report.

- [ ] Write the tests of item 8; run them: they fail (RED) for the reason each item names.
- [ ] Edit the texts (items 1-7).
- [ ] Run `tests/test_slot_files.py` 3 times in a row, then the whole suite once, every python command through the safe
  wrapper: `OK`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `docs(ai-trader): prompts act on the parent's last line, relaunch after a cleared halt, test a merge before making it, and never skip a slot's work on a conflict`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json is not
changed; no file the time machine loads is touched.
