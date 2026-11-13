# Task 16 review: uptime-report

Diff 2219f55d..391518e3 in the gate clone. Read in one pass from `review-task-16.diff` (package exit 0, 2 commits, 3
files, +473). No changed file was read separately; no test was re-run.

Checks outside the diff, one per named risk:
- R11's `{r}` against R3's `{k}`: read `aitrader/supervise.py:1175-1181`. R3 says `k=trip["restarts"] + 1` (falls).
- `stop_gap_max_s` key name: `aitrader/news_live.py:752-757`. The health row's time key is `at` and the field is
  `stop_gap_max_s`. Matches.
- Whether the CLI test could read the clone's real state: `journal.use_book` (journal.py:32-51) does nothing for
  "stocks", so the `journal.STATE` patch holds.
- A missing `uptime.jsonl`: `supervise.read_rows` (supervise.py:109-125) returns `[]`. No crash.
- What a mark's `hb` is after a VM pause: `supervise.py:979-983` with `beat_view` (370-386). `hb` is the heartbeat
  file's age whenever the beat is this child's, so a pause shows as a stale `hb` on the first mark after it.
- R4c's `{held}` when the value is None: `ownerlines.held_text` (ownerlines.py:98-104) prints "אין פוזיציות" today. Task
  14b's brief (item 2) changes None to "לא ידוע".

### Spec Compliance

Not compliant. One finding:
- `ai-trader/aitrader/uptime.py:59-62` and `:98-99`, pinned by `ai-trader/tests/test_uptime.py:111-113,126`. When two
  marks are more than `mark_gap_max_seconds` apart and the later one shows `hb` above `up_hb_max_seconds`, the stretch
  goes under "hang", not "gap". That is what a VM pause looks like: the parent and the engine freeze together, and the
  first mark after the pause shows a heartbeat as old as the pause. Spec 4.6 names that stretch kind as "(a VM pause,
  a dead machine, a stalled parent)". The page exists so that a parent or machine stall can be told from an engine
  failure, and the hosting question (question 3) is decided on it. This build books machine pauses as engine hangs.
  The brief does not map stretch kinds to causes; this mapping is the implementer's (report, concern 3).

Everything else checks out:
- The three interfaces have the brief's signatures.
- `day_report` has every key in the brief's list.
- The union has the four stretch kinds plus the session edges, in the brief's cause order.
- `close_lines` gives R4c, R9 and R11 in that order. R11 follows ruling P6 (sum of `m`, plus this call's R4c), and
  `open_at_close` follows P11 (the `held` of the day's last `up`).
- The CLI forms work, the command is read-only and stock-only, and only `--notify` prints the notify line.
- The docstring has the new entry.
- All five of the brief's tests exist under their names, with the brief's assertions word for word.
- Early close: test 3 runs 2026-11-27 and gets 12,600 s.

Cannot verify from this diff:
- "The controller's addition" to P6: R11 counts only alert rows with `sent` true, once per id. That text is in the
  dispatch, not in controller-notes.md or rulings-10-28.md. Check that the dispatch said this.
- The cause names (`restart`, `hang`, `handover`, `gap`, `stale_stops`) and the row field names the code reads (`id`,
  `kind`, `m`, `sent` on alerts; `n` on starts; `dm3` on `cancel_failed`). They depend on how Tasks 12, 13 and 21
  write the rows. `dm3` belongs to Task 21 and does not exist yet.
- Spec 11.2 wants "dead-man alarms (true and false)". The brief's `deadman` has only `alarms`, `ping_failed` and
  `cancel_failed`. Check whether a later task adds the true/false split.
- Some R4c lines will say "אין פוזיציות" when nothing is known. Fixed once Task 14b lands; until then this module
  inherits the false all-clear (report, concern 1).

### Strengths
- Small and readable. Exactly the three functions of the interface plus private helpers. Standard library only.
  Every threshold comes from `config.json`: `mark_gap_max_seconds`, `up_hb_max_seconds`, `stops_stale_seconds`,
  `outage_report_seconds`, `max_line_bytes`, `free_text_max_chars`, `held_names_in_line`, `owner_tz`,
  `uptime_target`, `report_days`.
- The per-second union is exact and easy to check, and its ceiling is marked with a `ponytail:` comment.
- Every owner line goes through `ownerlines.render` and `ownerlines.priority`, so each ends with "כסף נייר" and stays
  under `max_line_bytes`. No topic, URL or exception text appears anywhere.
- The hang's start comes from the marks, not from the `hang` row's late `t`. This follows Task 12's deferred note.
- The CLI never calls `journal.path` and never creates a file. The test proves it: after both runs the temp directory
  holds only `uptime.jsonl`.
- The tests are built from rows in the parent's real shapes, with no mocks of the module under test. The extra tests
  pin the cause order, the per-id once-only count for P6, and the P11 source. The report's mutation pass shows they
  catch real changes.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. `ai-trader/aitrader/uptime.py:59-62` (fill order at `:98-99`); test `ai-trader/tests/test_uptime.py:111-113,126`.
   - What is wrong: a pair of marks more than `mark_gap_max_seconds` apart whose later mark shows a stale `hb` is
     booked as "hang". A VM pause produces exactly that: `hb` is the heartbeat file's age (supervise.py:981), and the
     parent's first tick after the pause comes before the engine's next beat. The test's 19:00-19:05 case (300 s
     apart, `hb` 290) pins it as hang.
   - Why it matters: spec 4.6 says the mark-gap kind is the VM pause and the dead or stalled machine, and that the
     page must tell parent stalls from engine faults. Question 3 (hosting) is decided on this page against a 99%
     line, which is 234 s a day. Machine time booked as engine hangs points that decision the wrong way.
   - Fix: when a mark pair is longer than `mark_gap_max_seconds`, book it as "gap" only. The stale beat at its end is
     explained by the pause. Do this before adding the hang stretch. Change the 19:05 case's expectation to gap 300,
     and keep one case where marks under 150 s apart show a stale `hb` and still give hang. One condition and one
     assertion.
2. `ai-trader/aitrader/uptime.py:194` (`r=report["restarts"]`).
   - What is wrong: R11 says "המנוע נפל {r} פעמים" ("the engine fell r times"), and `{r}` is the parent's restart
     count. The fall that trips the parent is never restarted. On a crash-loop day the morning R3 reads "נפל 6 פעמים"
     (supervise.py:1180: `k=trip["restarts"] + 1`), and the close's R11 reads "נפל 5 פעמים". R11 is mandatory on
     exactly those days.
   - Why it matters: a wrong number in a line the owner reads, which contradicts the urgent line he got the same
     morning. The implementer flagged it (report, concern 2) and left it. A stated rationale does not lower a finding.
   - Fix: `r=report["restarts"] + report["trips"]`. Each trip follows exactly one fall that was not restarted. Add one
     assertion to `test_close_lines_and_only_the_notify_form_prints_them`: R11's text holds the number of falls.
     Alternatively, get a controller ruling that `{r}` means restarts and say so in the docstring.

#### Minor (Nice to Have)
- `ai-trader/aitrader/uptime.py:61-64`, the time before an exit that a null-`hb` mark makes "gap". When the mark right
  after an exit has a null `hb` (always so for a new parent's first tick before its child beats: supervise.py:981),
  the whole pair interval is unprotected. The seconds from the last mark before the exit up to the exit are booked as
  "gap", not handover or restart. That is up to about 60 s per handover, plus the planned stop, during which no mark
  is written (config `_note`). For slow handovers (marks more than 150 s apart) the spec's own gap rule gives the same
  label. Still, the handover case in the test (`test_uptime.py:120`) puts the exit exactly on a mark minute, so this
  never shows. Consider booking such a time under the cause of the exit stretch it touches, or at least pin the
  current behaviour with an exit between two marks.
- `ai-trader/aitrader/uptime.py:180-181`, the R4c floor. R4c needs `outage_report_seconds` (180 s) of trailing
  outage. The brief says only "still open at the close". This is a defensible reading (it is the size R4 and R4b
  report, and the minutes go to R11 instead), but it is a departure, and the report files it under "readings where
  the brief is silent". List it as a departure so the controller rules on it.
- `ai-trader/aitrader/uptime.py:190-193`, rounding. R11 compares `round(total/60)` with a sum of minutes that were
  each rounded on their own, using banker's rounding. An unreported 40 s can vanish next to an R4 of 210 s (4 against
  round(250/60)=4). A remainder of 30 s rounds to 0. Comparing seconds (`unprotected_s` against 60 * the sum) would
  be exact.
- `ai-trader/aitrader/uptime.py:177-195`. An outage still open at the close whose parent comes back after the close
  but before 16:22 gets an R4 at the `up` and an R4c at the close for the same minutes. Spec 8 says one outage gives
  at most DM1, R4 and W1. The doubled sum also hides other unreported minutes from R11. Same family as the report's
  concern 5 (an R4 for an earlier day's minutes counts toward today).
- `ai-trader/aitrader/uptime.py:177`. `close_lines` builds the 23,400-slot per-second array a second time. `day_report`
  already built it. This is the same work done twice, not wrong.
- `ai-trader/aitrader/uptime.py:13` imports the private `supervise._when`. A small coupling to a private name.
- `ai-trader/aitrader/__main__.py:518`, `n = a.days or ...`. `--days 0` silently means `report_days`, and a negative
  `--days` prints an empty page with exit 0. Refuse `--days < 1` with exit 2, like a bad `--day`.
- `ai-trader/tests/test_uptime.py:95`, the CLI half of test 4 (the brief's assertion). It shows only whether the
  word "notify" appears. It never shows that the command read the temp rows: R4c and R11 in the notify line, or the
  day's percent in the block. Add one assertion on the notify payload's ids.
- `ai-trader/tests/test_uptime.py:54`, `out_of` uses a bare `assert`. `python -O` would skip it. Use a test method's
  `assertEqual` or raise.
- R11 will go out on almost every normal day. Three handovers fall inside the session (10:48, 12:28, 14:17) at about
  60 s each, and R4b reports only 180 s or more. That makes at least one rounded minute that nothing reported. This
  is the plan's letter (spec 8: "outage time not yet reported"), but it may clash with the first-day checklist's
  "a quiet phone". Controller to confirm.
- Process (report, concern 4): one bare `python3` ran outside the mandatory `safe` wrapper (controller ruling of
  15:35 UTC, 2026-11-11). It was a text rewrite with no aitrader import, so nothing reached the network. It is still a
  breach of a rule the controller made absolute.
- The suite output still carries noise from other modules (`[news] engine started ...`, `[journal] skipped unreadable
  line ...`). None of it comes from this change. This task's file is clean.

### Assessment
Task quality: Needs fixes. The module is well built and follows the brief and rulings P6 and P11, but two things
must be fixed before the page can decide anything:
- It books VM pauses as engine hangs, so the cause breakdown that the hosting question rests on is wrong.
- R11 undercounts the engine's falls by the day's trips and contradicts R3 on exactly the days R11 must go out.
