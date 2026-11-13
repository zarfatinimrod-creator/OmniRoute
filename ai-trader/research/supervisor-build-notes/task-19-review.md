# Task 19 review - the new prompt texts, the git rule, the SKILL table

Base d639d8ec, head 578cc775 (2 commits), gate clone `.../scratchpad/clones/sup`. Review package
`review-task-19.diff` (exit 0, 60,781 bytes) read whole in two passes (lines 1-344, 345-410); no hunk was cut off.
Inputs: brief, constraints.md, controller-notes.md, rulings-10-28.md (P19, P21, P22, P23, P37 for Task 19), spec
4.4, 4.5, 4.7 and the S2/R8/R12/R4c/R9/R11/R5e rows of 8.

### Spec Compliance

Not compliant, one item:

- `ai-trader/skills/trader/slots/close.md:2`, `midday.md:2`, `open.md:2`, `weekly.md:2`, `crypto-decide.md:2`,
  `crypto-fill.md:2`, `crypto-summary.md:2` - Extra, beyond the brief: the start-of-turn merge now says "On a
  conflict: step N's rule", and that rule is "`git merge --abort`, send S2, and stop". The brief and spec 4.7 give
  "send S2 and stop" only for the closing block, which runs after the slot's duty. Applied at the start, it skips the
  slot's whole duty while a conflict lasts. Details are under Important below. The implementer lists this as
  departure 6 and concern 1.

Verified as compliant (each one checked against the diff, and against code at 578cc775 where the prompt names code):
- Every slot file: `pull --rebase` is gone and the start step reads `git fetch origin <branch> && git merge --no-edit
  origin/<branch>`. A grep of every slot file at HEAD counts 0 `pull --rebase`, 1 `git merge --abort` and 1 full S2
  text per file. No other `pull --rebase` is left under `ai-trader/` outside research/logs/state (`git grep`).
- The closing blocks hold, in order: commit own state; fetch and merge; push; on a rejected push, fetch and merge
  again up to 5 tries; never rebase; never end with a merge in progress; on a conflict, abort, S2 with `{file}`, stop,
  discard nothing. The S2 text equals `ownerlines.LINES["S2"][1]` (ownerlines.py:74) character for character. The
  crypto one-liner fetches and merges before each push, and only a failed merge breaks the loop (commit 2).
- `news-watch.md`: (a) `--status --watchdog` comes first and the sync is last (step 6); (b) `unsent` is sent, then
  `--relayed ID...`; (c) `postmortem` stays. The bare `news-live --minutes 110` launch, the pgrep/3-minute rule and
  the "engine was down" push are gone. The wake rule is there. `news-watch-37.md` is deleted.
- `close.md`: step 6, after the duty, runs `uptime-report --day --notify` and pushes each `text` under `notify`. P37's
  copy step is there too. Checked in the code: `__main__.py:528-529` prints the JSON line `{"notify": [...]}` last.
  `uptime._line` gives `{"id","priority","text"}`, and `uptime.render` prints `uptime`, `longest_blind_s` and
  `commits`. The prompt's names are real.
- `SKILL.md` 3ב: the launch paragraph gives way to the parent (launched only on `--status`'s word, as a tracked
  background task, never nohup/setsid/&). Both tables are in Hebrew, and R8 and R12 equal `ownerlines.LINES`
  (ownerlines.py:45, 50). Each row I checked against `supervise.status()` (lines 616-630) and `main()` (816, 1257):
  `wait_for_watchdog` needs `trips_today >= 2`, `not watchdog` and a last row that is no PLANNED `sup_stop` (line
  627). R5e goes into `unsent` only with `--watchdog`, for a halt from an earlier New York day (line 643).
  `3 lock_held pid N` has both causes (816 and 1256). The last-line format matches `AFTER` (line 511).
  `today.trips` is a real key (status return). Sections 0 and 3א now use fetch and merge.
- `CLAUDE.md` hard rule 8 has the brief's three sentences word for word.
- `tests/test_slot_files.py`: the four tests are the brief's own, under their names and with their assertions. The
  leak test's fixture line is P19's line word for word. `from helpers import no_phone` comes first. One more test pins
  P37.
- Commit hygiene: commit 1's message is the brief's. Neither message has an attribution line (`git log` grep). The
  stat touches nothing under state/logs/reports/research. Only the brief's paths are changed.

Cannot verify from this diff:
- Departure 3 (the `kill_stray` row waits up to two minutes before `kill -9`, where spec 4.4 says 10 s) needs the
  controller's ratification. It does follow spec 5.3's planned stop and the SKILL bullet pinned by
  `test_news_supervised.py`.
- Departure 1 (the dashboard gets the git-rule sentence) and the night crypto slots' S2 going into the night log
  instead of a push both need the controller's ratification.
- Whether a trader turn syncs before 08:07 after the Task 20 landing is P23's proof, not this task's.

### Strengths
- Every command, flag and output field the prompts name was read from the code at HEAD, and the report gives the
  line for each (`--relayed`, `--clear-halt`, the eight actions, the last-line words, the `notify` shape). Spot checks
  of five of them matched.
- The self-review caught a real fault in the crypto loop. `git fetch ... && git merge ... || break` would have ended
  the push loop on a network blip; commit 2 fixed it, and it fixed SKILL 4א the same way.
- The prompt never re-runs `--status` right after a launch, so a new parent that has not yet ticked cannot read as
  `replace_parent`. The `--relayed` step is skipped when `unsent` is empty (argparse `nargs="+"`).
- Departures are listed openly, each with the alternative the controller can take.
- The test file is small, starts no process and reads only the repository's own files.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. **A conflict at the start sync skips the slot's whole duty, the stock book's close-time stop check included.**
   Where: `slots/close.md:2` ("On a conflict: step 7's rule"), and the same clause in `midday.md:2`, `open.md:2`,
   `weekly.md:2`, `crypto-decide.md:2`, `crypto-fill.md:2`, `crypto-summary.md:2`.
   - What is wrong: step 7's rule is "`git merge --abort`, send S2, and stop". A conflict at step 1 therefore ends the
     close turn before `verify`, `cycle`, `postmortem` and the log. `cycle` is where the stock book's trailing stop is
     checked at the close (strategy.py:154-159; midday.md's own text says "the stock book's stop is checked at the
     close"). It is also where tomorrow's decision is stored.
   - The conflict also lasts: the plan expects ones like `state/trials.jsonl` after a landing. While it lasts, every
     slot's start merge meets it again. The open slot fills nothing. The close slot checks no stock stop and decides
     nothing. Crypto decides and fills nothing. The crypto morning summary, and the night's urgent queue with it, is
     not delivered.
   - Why it matters: "anything that delays, skips or reorders a stop look beyond what the brief says" is on this
     task's list of what the project cannot afford. The brief puts "send S2 and stop" only in the closing block,
     after the duty. The S2 text itself says "המנוע ממשיך לרוץ על מה שיש" (work goes on, on what is there).
   - Fix: at each start step, on a conflict run `git merge --abort` (nothing is discarded) and go on with the slot's
     duty on the local state. The closing block then meets the conflict again, sends S2 and stops without pushing.
     If the controller does want the duty skipped, it rules so and the prompts say so; the brief does not.

#### Minor (Nice to Have)
1. `tests/test_slot_files.py:28` - the skip `if "git " not in t:` is dead code. Every slot file says "Never git
   stash", so the skip never runs, and its comment ("the dashboard prompt runs no git until Task 24") is false. This
   test is what made the git-rule sentence go into `dashboard.md:2`. The text is plan-mandated. The controller can
   leave it, or take the implementer's `t.replace("git stash", "")` option.
2. `slots/dashboard.md:2` - the added git-rule sentence for a slot that runs no git (departure 1). Spec 4.7 ("every
   scheduled prompt") supports it, and the sentence says plainly that the slot runs no git. Controller's call.
3. `skills/trader/SKILL.md:197` and `slots/news-watch.md:7` - the `kill_stray` row waits up to two minutes before
   `kill -9`, where spec 4.4 says 10 s. This matches the pinned SKILL bullet and spec 5.3, since a `kill -9` at 10 s
   would cut into a planned stop's save. It is a departure from the spec's text and needs ratification.
4. `slots/news-watch.md:11` - step 4 keeps "PushNotification only if the engine could not be started", a leftover of
   the flow in which the session started the engine. The session now starts only the parent, and R4/R5x report
   outages, so this trigger can no longer happen as written or would repeat R4.
5. `skills/trader/SKILL.md:218-227` - the bullets kept from the old 3ב are still written for the bare engine
   (implementer's concern 3). "Restart before long work" now reads as "run `--status`", which answers `none`, and the
   engine's exit codes (3, 7) sit beside the parent's codes. The one added sentence covers this only in part.
6. `slots/crypto-decide.md:4`, `slots/crypto-fill.md:3` - at night, S2 goes into the night log, not a push. This keeps
   the owner's no-push-at-night rule. S2 then reaches the owner only because the morning summary's start merge meets
   the same conflict, and under Important 1 that same rule makes the summary itself not go out.
7. Every closing block - S2 has no once-per-conflict rule. A conflict that lasts sends S2 from every slot, and from
   the watchdog every 30 minutes. The spec has no dedupe either; this is a note for the controller.
8. `skills/trader/SKILL.md:216` - after R8, `--status` keeps answering with the long-timeout command until
   `long_timeout_proven` is changed through the gate. The row says "back to `--handover`" but not that every later
   launch that day must add it by hand (implementer's concern 4). No launch can reach this row until the flag is true.

### Assessment
Task quality: Needs fixes. The texts are accurate against the code: every command, flag, output field and owner line
checks out, and the brief's four tests are word for word. The one thing to fix is the start-of-turn "stop" on a
conflict. It goes beyond the brief and, while a conflict lasts, skips the close-time stock stop check and every
slot's duty.
