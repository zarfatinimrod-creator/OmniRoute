# Task 16 (uptime-report): re-review of fix round 1

Fix base 391518e3, head 74548ad3 (one commit, `ai-trader/aitrader/uptime.py` and `ai-trader/tests/test_uptime.py`).
Package: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-16-fix1.diff`. Read-only; no suite
re-run.

### Finding Verdicts

- **F1: ADDRESSED.** `uptime.py:61-64`: a mark pair longer than `mark_gap_max_seconds` now books `gap` only, and the
  hang test is an `elif` after it, so a stale `hb` at the end of a pause no longer adds a hang stretch. The
  `_stretches` docstring (`:34-39`) gives spec 4.6's reason. In the test, the 19:00-19:05 case (300 s apart, hb 290)
  now expects `gap 300, hang 380` (`test_uptime.py:135`). The total stays 810. Stale-hb marks a minute apart still
  give hang: 15:00-15:03 from hb 65/125/185, and 16:00-16:03 plus the kill stretch to 16:03:20 (200 s). That makes
  380, as the finding asked. I checked this by hand.
- **F2: ADDRESSED.** `uptime.py:235`: R11's `{r}` is now `report["restarts"] + report["trips"]`. I checked it against
  `supervise.py`:
  - A trip returns before `restarts_today += 1` (`:291-298`), so the fall that trips is never counted.
  - The relaunched parent loads `restarts_today` from state (`:856`). Its first `start` repeats `n`, which is no rise
    in `day_report`'s count.
  - R3's `k` is `trip.restarts + 1` (`:1180`).
  - So falls = restarts + trips, for the window trip, the day-limit trip and a second trip alike (parent 1: 5
    restarts + 1 trip; parent 2: 5 more + 1 = 12 falls).
  The test stand-in now has a real crash loop (n 1..6, `tripped restarts=5`), and `test_uptime.py:100` asserts
  `המנוע נפל 6 פעמים,`. The plan's three assertions are unchanged. R7's `{r}` and the report key `restarts` keep their
  meaning.
- **F3: ADDRESSED (the definition of "false" still needs the controller's confirmation, which the report asks for).**
  - `uptime.py:189-191`: `deadman` is now `{alarms, alarms_true, alarms_false, ping_failed, cancel_failed}`. `alarms`
    is still the day's `new_seq` rows (P7 holds). Because both sides iterate the same day's `new_seq` rows,
    `alarms_true + alarms_false == alarms` always holds.
  - `:264-265`: the page prints `dead-man alarms N (true T, false F)`.
  - The rule (`_true_alarms`, `:82-105`): an alarm is true when an OUTAGE stretch touches the last
    `delay_seconds - seq_margin_seconds` (340 s) before the row. The window is sound. Spec 6 takes a new seq only when
    now >= due_at - 20, and due_at >= the last accepted ping + 360 (600 for DM2). So [t-340, t] always lies in the
    silence. Both numbers come from config.
  - An alarm after a cancel that failed after its day's close reads false. That alarm was DM3, or the DM1 that R9 calls
    "שגויה". Without this check the overnight mark gap would make it read true.
  - The new test (`test_uptime.py:185-211`) has one true alarm (restart 15:00-15:08), one false (fresh marks, eleven
    `ping_failed`), and a next-morning false. It asserts both dicts and the rendered text.
  - The implementer's mutation runs (the close check dropped, all true, all false, a whole-day window) each fail the
    file.
  - The ceiling (a network cut whose last 340 s also hold a restart reads true) is marked `ponytail:`, with the Task 21
    `due_at` note.
  - Open for the controller, not a defect here: DM3 counted as false (spec 6 calls DM3 "a quiet, true line"), and an
    in-session `cancel_failed` (trip, halt) not treated as a close cancel.

### New Breakage in the Fix Diff

1. **Minor**, `uptime.py:103` (`_true_alarms`): `last` changes only on a `cancel_failed` or a `new_seq` row.
   - Failure: a close cancel fails on day D, then the dead-man file disappears before any ping. P7 names the undo as
     the one path that removes the file (plan 1304/1310). The next arming writes `armed`, and the first REAL alarm
     after that (engine down) still sees D's late `cancel_failed` as `last`. It is booked false, so it is missing from
     the true count on the page that decides question 3.
   - Fix: let an `armed` row end the exception (add it to the rows that set `last`). Also have Task 21's brief confirm
     that a kept file's first ping writes `new_seq` with no `armed` before it. Otherwise this one-word change would
     break the morning-after case.
2. **Minor**, `test_uptime.py:135` (the 19:05 case changed): the 19:05 case was the file's only overlap of a hang and a
   gap stretch. Once it was rebooked as a gap, no test pins "hang before gap" in the brief's cause order: a swap of
   those two in `CAUSES` would pass the file. The report's list of pinned orders honestly leaves this pair out.
   - Fix: one overlap case, e.g. a hang kill's exit-to-up inside an exit followed by `sup_stop signal` (a gap), with
     the assertion that hang wins.

### Out-of-Scope Observations

- A VM pause longer than `hang_seconds` also makes the parent's own hang check kill the child at its first tick after
  the pause (`supervise.py:1020-1032`, with an R2 to the owner). The kill's exit-to-up is booked "hang" by the exit-row
  rule (`uptime.py:46-50`, untouched by the fix). It is a few seconds per pause, not the pause itself, but the owner
  still gets an R2 that reads as an engine hang. This belongs to the parent's hang check, not to this report.
- `_stretches` is now computed three times per day report (`_by_second` twice, `_true_alarms` once). That is trivial
  at 30 days of rows.

### Verdict

PASS. All three findings are addressed on the code; the two new items are Minor and block nothing. F3's meaning of
"false" (and DM3 as false) is the implementer's reading of the reviewer's suggestion, and the controller should
confirm it, as the fix report asks. The fix report shows RED, GREEN (3 runs) and the whole suite (818 OK, 246 s),
each with its command and output, plus a six-mutation pass. The commit carries no attribution.
