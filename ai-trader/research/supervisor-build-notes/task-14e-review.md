# Task 14e review: a stop that is no finite number reads unknown, two supervisor tests check what they claim, two comments say what is true

Reviewed: 13ec056d..d639d8ec (one commit), from the review package `review-task-14e.diff`. It had no hunks cut off mid-function. Outside the diff I ran one focused check for each named risk, listed below.

### Spec Compliance

Compliant. All five items are built in the places the brief names. Only the five listed files are touched.

- Item 1, `ai-trader/aitrader/ownerlines.py:61`: `stop_text` now also requires `math.isfinite(stop)`. The test in `ai-trader/tests/test_ownerlines.py:150-152` makes the brief's exact call and asserts MU and NVDA as `סטופ לא ידוע` and AMD as `12.00`. The report has RED (`'MU (סטופ nan), NVDA (סטופ inf), ...'`) and GREEN.
- Item 2, `ai-trader/tests/test_supervise.py:238`: `assertEqual(len(self.urows("pause")), 1)` comes after `stop_parent`, where every row has been written. The guard check in the report (SIGSTOP replaced by a sleep) fails with `0 != 1`.
- Item 3, `ai-trader/tests/test_supervise.py:194`: `PAUSED_STAMP_CHILD` writes `stops_checked_at` from the same `stamp` variable as the per-name stamp, so it freezes at the same value. Lines 216-229 keep the lower bound `s >= 4 + 2` and add `abs(s - (seen - frozen.timestamp())) <= 1`. The report has RED against the child-age mutant (`2.877951145172119 not less than or equal to 1`) and GREEN on the real code. The comments say what each assertion checks.
- Item 4, `ai-trader/aitrader/supervise.py:86-91`: comment only. It now names the unbounded `child.wait()` after the SIGKILL.
- Item 5, `ai-trader/scripts/drill_supervisor.py:120-123`: comment only. It says the window is still open, where it is, and what would close it.
- The commit message matches the brief. It has no trailer, no footer and no session link. `git log 13ec056d..d639d8ec` shows one commit, and the branch is `supervisor-build`.

Departures from the brief, judged:
- Departure 1 (the brief's premise for item 3 is false): confirmed. `supervise.py:358-361` (`_looks` / `_stamp_ages`) reads a held name's own `checked_at` first and falls back to `stops_checked_at` only when it is missing. `beat_view` (`supervise.py:381-383`) builds `stop_age_s` from those per-name ages. So R6's `{s}` was already the per-name stamp's age, and adding `stops_checked_at` does not change it. The implementer still built what the brief asked, and the report says so.
- Departure 2 (the `up` row's `blind_s` changes): consistent with the code. `supervise.py:1129` takes `kid["last_look"] or _when(hb.get("stops_checked_at")) or sup_t`. No assertion reads it. The old value depended on the hour, so the new one is saner.
- Departure 3 (a 3 s wait and a two-sided bound): needed. A lower bound alone can never fail against a child-age `{s}`, because the child is always at least as old as its stamp. Without the wait, the two ages differ by only tenths of a second.
- Departure 4 (item 4 also mentions the planned stop): true to the code. In `restart_core` (`supervise.py:261-271`) a planned stop breaks out of the child loop and then returns at `if why == "planned"`, so no tick follows it. A hang stop goes on to the back-off wait, whose `watch(None, 0.0)` calls `look` again.

Cannot verify from this diff:
- That the reported RED and GREEN outputs came from the committed text. The evidence files exist in `scratchpad/t14e/` (red-item1, red-item2-no-pause, red-item3-mutant-final, green-*, suite.txt). Per the dispatch I did not re-run them.
- That the brief's word "no file the time machine loads" holds. I checked one path: `aitrader/__main__.py` imports `news_live` and `supervise` only inside their own subcommands, and no `backtest*.py` names `ownerlines` or `news_live`. A whole-import-graph check belongs to the gate.

### Strengths

- Item 1 is the smallest correct change: one condition and one stdlib import. `isinstance` short-circuits, so a bool or a string is refused before `isfinite` is reached.
- Item 3's mutant check is honest. The report shows the old test passing against the mutant (`base-test-vs-mutant.txt`), which proves the reviewer's point before the fix. It then re-runs RED on the final, tidied text.
- The implementer found that the brief's premise for item 3 was false, checked it two ways (a `beat_view` probe, and the test with the base child), and reported it instead of quietly bending the test.
- Item 5's comment is accurate. I checked it against the code: `hold` is module-level (`drill_supervisor.py:136`), the handler notes a stop only while `hold` is a list (`:145-148`), and only `run`'s `finally` sets it (`:680`, `:688`). `popen` never sets it. The sketched fix mirrors `run`'s `noted, hold = hold, None; if noted: raise Interrupted(...)`.
- Item 4's comment is accurate. I checked it against `stop()` (`supervise.py:1166-1191`): the hang branch is `wait(timeout=hang_term_grace_seconds)`, then SIGKILL, then a bare `child.wait()`. The back-off sleeps in `restart_core` are each at most `loop_seconds`, with a `watch` tick between them.
- The reported test output is clean: only dots, the summary and `OK` for both files.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

1. `ai-trader/tests/test_supervise.py:229`: the lower half of the two-sided bound can fail the real code when the test is descheduled.
   - What I checked: `beat_view` (`supervise.py:370-386`), the R6 path (`:1064-1069`), `say()` (no topic in this class, so the alert row is written at once), `wait_for` (polls every 0.01 s), and `supervise.py` has no fsync.
   - The real code gives `s - (seen - frozen) = rounding error (±0.55) - D`, where D is the time from the parent's tick to the test's `seen`. The assertion fails once D is more than 0.45 s (worst rounding) to 1.45 s (best).
   - D is normally a few tens of milliseconds, so this is rare. But that half of the bound is not needed to catch the mutant. An upper bound alone, `assertLessEqual(s, seen - frozen.timestamp() + 1)`, never fails the real code (a delay only makes `seen` later). It still catches the child-age mutant (about 3 s high) unless D is 2 s or more.
   - Fix: replace the `abs(...)` with that one-sided bound and keep the comment.
2. `ai-trader/tests/test_supervise.py:220`: `frozen` is read from `beat["stops_checked_at"]`, but R6's `{s}` comes from `held.BBB.checked_at` (`_stamp_ages`, `supervise.py:358-361`).
   - The child writes both from one variable, so they are equal today.
   - Reading `beat["held"]["BBB"]["checked_at"]` would tie the assertion to the field R6 really reads, and match the comment "the frozen stamp's age".
3. `ai-trader/tests/test_supervise.py:216`: the comment "the child is 3 s older than its stamp" is really "at least 3 s older": its start-up and the wait for `up` come on top.
4. `ai-trader/aitrader/ownerlines.py:61`: a stop that is an int too large for a float (for example a 400-digit JSON integer) still raises OverflowError, and `say()` (`supervise.py:906`) does not catch it.
   - It is pre-existing and unchanged: I ran `format(10**400, ".2f")` and `math.isfinite(10**400)` through the safe wrapper, and both raise OverflowError. The report discloses it.
   - It is outside this brief, which names floats only. A follow-up could add OverflowError to `say()`'s except list.

### Assessment

Task quality: Approved. All five items match the brief. Each new or strengthened assertion is shown to fail on the defect it guards, and both comments now say what the code does (checked against `stop()`, `restart_core` and the drill's `hold` handling). The one robustness point, the lower half of item 3's two-sided bound, is a rare-flake risk with a one-line fix, not a defect that blocks this task.
