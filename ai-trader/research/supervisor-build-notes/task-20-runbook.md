# Task 20 runbook (controller's own, written 15:55 UTC 2026-11-12; moved to Sunday 2026-11-15 by Ruling 60)

The authorities are task-20-brief.md, rulings-10-28.md (## Task 20, P23, P29, P31, P36, P39, P40, and the
"Controller's additions (2026-11-12)" for Rulings 44, 45, 47) and the ledger (Rulings 54, 55). This file only orders them.

Paths: CLONE=<SCRATCH>/clones/sup ;
SAFE=/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe ; live checkout /home/user/OmniRoute (fetch +
merge only, never pull --rebase, never git stash).

## Before 21:05 UTC (allowed: no landing, no drill)
1. Wave 14e+19 done, results ruled, suite OK at the final build head.
2. Adversarial review of supervise.py, deadman.py, uptime.py at the final build head: a workflow with distinct lenses,
   every reviewer reads by `git show <sha>:<path>`, the git stash ban verbatim in each prompt, no model set. Must-fix
   goes back to its owning task before the landing. The drill output part of the review is added after step 4.
3. Landing branch: `git checkout -b landing-step2 supervisor-build` in CLONE, `git fetch origin ccr-120121ba-vsvwlj`,
   `git merge --no-edit origin/ccr-120121ba-vsvwlj` (trader state commits only: state/ files; no overlap expected).

## After 21:05 UTC (16:05 New York)
4. Suite OK on landing-step2. Then `drill_supervisor.py all` at real numbers (e with 200 rounds) as a tracked
   background command, 35-40 min (Ruling 47); seven PASS lines, copied with numbers into the session log. A FAIL e
   with a broken chain stops the landing. A drill a FAIL on timing is a finding, never a pass.
5. Cloud drills, each on its own scratch dir, after step 4 (not concurrent with it):
   (1) `cd ai-trader && exec $SAFE python3 -u scripts/drill_supervisor.py cloud <dir>` in the background; 90 s later
       `cloud-check --alive <dir>` PASS; then TaskStop; then `cloud-check <dir>` PASS. --alive FAIL stops the landing.
   (2) the same with timeout 60000; let it hit; `cloud-check <dir>` PASS.
   Record, for each stop, what uptime.jsonl got (`sup_stop` "signal", or none): P39 / Task 26 read it.
6. `$SAFE python3 -m aitrader.supervise --net-check`: 200, exit 0, within three tries a minute apart (Ruling 44).
   Anything else stops the landing.
7. Flip: config.json supervisor.hang_kill_enabled true + `("hang_kill_enabled",)` in SWITCHES_ON of
   tests/test_supervise.py; suite OK; commit `feat(ai-trader): hang kill on, after drill b` (no attribution lines).
8. Quant-critic, one agent on claude-opus-5-5 (P36), stash ban verbatim: verdict on live..landing-step2, says no
   time-machine file is touched (rule 4: no sweep).
9. Land: push `HEAD:ccr-120121ba-vsvwlj` from CLONE (fetch + merge again first if origin moved), then merge back into
   the live checkout with fetch + merge, then merge landing-step2 back into supervisor-build.
10. Owner question, one Hebrew message (א yes / ב not now, recommended א): replace the scheduled tasks' texts with the
    files at the pushed commit (up to ten tasks; the :07 and :37 watchdogs share news-watch.md once news-watch-37.md is
    deleted by Task 19).
11. P23 proof before any update_trigger: the trader's next state commit has the landing as ancestor. The crypto decide
    task (00:12 UTC, trader session) pulls and commits state, so it is the expected proof; no extra scheduled task is
    needed unless that run fails to sync.
12. On yes, after step 11: pre-check that each task is unchanged since the baseline (its `updated_at` is before the
    baseline list at 06:36 UTC 2026-11-12: exact, no retyping; text compare only as a backup, P40 re-read on a
    difference). Then update_trigger each with its file's text at the pushed commit; then read each back and compare;
    a difference is read again once before it counts (P40).
13. P31: a chain of tracked background waits (each under the 2-hour cap) to 08:20 New York of 2026-11-13, then
    `git fetch origin ccr-120121ba-vsvwlj` and `git show origin/ccr-120121ba-vsvwlj:ai-trader/state/uptime.jsonl | tail
    -n 8`: that day's sup_start, start, up, code and mark rows. None by 09:00 New York: read the trader session's last
    turn (list_events) and, if the parent was not launched, undo (task-20-brief.md, last item). The owner gets one line
    the evening of the landing saying the result comes then.
14. The same evening: Task 28's list A. Append the spec's first five backlog items to state/backlog.md and land them
    with the state. Session log 2026-11-12 (task #9).

## Added 18:20 UTC (Rulings 57, 58)
- Build order before the landing: 19b (prompts), then 14f, then 14g; each through the wave script. The landing
  slips to about 23:00-01:00 UTC. P23's proof comes from whichever crypto sync runs after the push (00:12, 01:07 or
  06:03 UTC).
- At step 6, also check the topic variable: `[ -n "$AITRADER_NTFY_TOPIC" ] && echo set || echo unset`. Print set or
  unset only, never the value (review ownerlines-9: with no channel the engine counts a line as told once it is logged).
- What to watch in the drills (review synthesis):
  - Drill a: exactly 6 R1 ids in the dummy part and 1 in the engine part, none capped.
  - Drill b: one hang row and one R2.
  - Drill e's mismatches=0 and drill g's rc7=0 are expected and are no evidence for check 4 or the git rule.
  - Cloud drills: record the signal TaskStop and the timeout send, and confirm in /proc that no parent or engine
    outlives the stop.
- First live day: no R6 at 09:30 with an overnight name. At each handover, the exit-to-up seconds; a planned stop ends
  inside 120 s with no group SIGKILL; no `claude -p` outlives the old engine. A relayed line carries the late prefix.
