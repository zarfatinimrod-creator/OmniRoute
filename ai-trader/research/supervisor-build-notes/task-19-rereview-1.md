# Task 19 re-review, fix round 1

Fix base 578cc77545c8bece13764e8350165925ab490e51, head 9663262e4a057eead9684b95dd66c6fbdbcd9758 (one commit,
"Slot prompts: a conflict at the start sync no longer skips the slot's work"), gate clone `supervisor-build`.
Package: `review-task-19-fix1.diff` (8 files, +20 -7).

### Finding Verdicts

**F1: ADDRESSED.**
The pointer "On a conflict: step N's rule" (which led to "abort, send S2, and stop" before the slot's work) is gone
from step 1 of all seven slots that sync at the start. Each now reads: "On a conflict: `git merge --abort`, which
discards nothing, then go on with this slot's work on the local state; step N's merge meets the conflict again and
reports it."
- `ai-trader/skills/trader/slots/close.md:2` names step 7, the closing block (`close.md:8`, abort, S2, stop).
- `midday.md:2` names step 4 (`midday.md:5`). `open.md:2` names step 4 (`open.md:5`). `weekly.md:2` names step 6 (`weekly.md:7`).
- `crypto-decide.md:2` names step 4 (`crypto-decide.md:5-6`). `crypto-fill.md:2` names step 3 (`crypto-fill.md:4-5`).
  `crypto-summary.md:2` names step 5 (`crypto-summary.md:6-7`).
- `grep "'s rule"` over `skills/trader/slots/*.md` at head finds nothing. The new clause appears exactly once in each
  of the seven files and in neither `news-watch.md` (it syncs at step 6, with no start sync) nor `dashboard.md` (no git).
- The closing blocks did not change. "Send S2 and stop" is now only in the closing block, after the slot's work. That
  matches the brief and spec 4.7, and the S2 text ("the engine goes on running on what there is"). During a start
  conflict the close slot again runs verify, `cycle` (the close-time stock stop check and tomorrow's decision) and
  postmortem. Open fills. The crypto slots decide and fill. The morning summary is delivered. The night slots' note,
  "the morning summary's merge meets the same conflict and sends it", still holds: the closing merge at
  `crypto-summary.md` step 5 meets the conflict and sends S2.
- SKILL.md section 0 (`SKILL.md:35`) and section 3א (`SKILL.md:160`) contain no stop-on-conflict at the start, so they
  do not contradict the slots that point to them.
- Regression guard `tests/test_slot_files.py:54-65`
  (`test_a_conflict_at_the_start_sync_is_aborted_and_the_slot_still_does_its_work`). For every slot whose step 1 has the
  `&& git merge --no-edit origin/` form, step 1 must contain `git merge --abort` and "then go on with this slot's work
  on the local state", and must not contain "'s rule". The test also pins the set of checked files to the seven. Every
  slot file has a line that starts with "1." (checked), so the `next(...)` call cannot raise StopIteration. The filter
  skips `dashboard.md` (its rule sentence has no `&&`) and `news-watch.md`.

### New Breakage in the Fix Diff

None.

### Out-of-Scope Observations

- `close.md:2`: in the step 1 text, `python3 -m aitrader verify` comes before the conflict clause. An agent that runs
  `git fetch ... && git merge ...; cd ai-trader; python3 -m aitrader verify` as one command line would run verify on
  a tree that is still mid-merge. "Go on with this slot's work on the local state" implies verify runs again after the
  abort, but the text does not say so explicitly. In the other six slots the clause comes before verify or the cycle.
  This ordering was there before the fix. It is a wording nit and blocks nothing.
- `weekly.md:2`: during a lasting conflict, the weekly turn now does its improvement and its before/after sweeps on
  the local state. The finding asked for this behaviour. The sweeps add rows to `state/trials.jsonl`, the file the
  plan expects to conflict. Those rows stay local until the conflict is cleared. Nothing is discarded, and step 6
  reports the conflict.

### Verdict

F1 is addressed. The fix diff breaks nothing. The fix report gives the covering test, the commands, the RED output
(against the 578cc775 texts), three GREEN runs (6 tests OK) and a whole-suite run (856 tests, OK, rc 0, 333 s). The
claims match the diff. I did not re-run the tests.
