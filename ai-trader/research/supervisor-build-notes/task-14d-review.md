# Task 14d review - one pause gives one line, no R6 from pre-pause stamps, a stop that is not a number never drops a line

Diff d8955a29..13ec056d (1 commit, 5 files, +149/-11), read from `review-task-14d.diff`. Commit message matches the
brief word for word and has no attribution lines (`git log -1 --format=%B 13ec056d`). The commit touches exactly the
five files the brief lists. `git status --short` in the gate clone is empty. Tests were not re-run: no doubt came up that
the reported runs (RED, mutants, GREEN, 3 runs of each file, whole suite 849 OK) do not answer.

### Spec Compliance

Compliant, with two departures from the brief's literal text. Both are needed for the brief's own purpose, and I
checked each one against the code:

- Item 1, `ai-trader/aitrader/supervise.py:1005`. `paused()` writes its `pause` row and sets `seen["resumed"]` as
  before. It skips its R4 only while `seen["gap"]` is set AND `gap_line(prev, now, cold)` is truthy now. Checks I ran:
  - `gap_line` (supervise.py:436-457) has no side effects. Its truthiness depends on `prev` and on
    `open_seconds(prev.t, up_at)`, and that count only grows as `up_at` moves later. So a line that is truthy at the
    pause is still truthy at the first `up` (supervise.py:1159-1163, the first `up`, which this diff leaves alone).
  - When it is falsy because of the threshold, the pause's own interval sits inside `[prev.t, now]`, so the pause's
    own R4 is falsy too.
  - The literal form would leave the most common morning start silent. There the row before the parent is
    yesterday's `sup_stop` for `end_of_day`, `gap_line` gives None, and the pause would get no line at all.
  - Result: one line per outage either way (spec 8).
- Item 2, `ai-trader/aitrader/supervise.py:1060`. The cap is `min(born if a is None else a, wall - seen["resumed"])`.
  It applies only while no stale episode is open (`not seen["stale"]`). Check I ran:
  - With the literal cap over an open episode, the capped names come out empty. That takes the
    `elif not names and seen["stale"]` branch (supervise.py:1071-1076): an `end` row, then R6b telling the owner the
    stops are checked again while the stamps are still old.
  - The new start of an episode, which is the brief's case, is capped exactly as written.
  - `seen["resumed"]` is assigned only in `paused()` (supervise.py:1004; the dict starts with None at :872). So a child
    stopped alone is judged as today.
  - `_stamp_ages`, `up()`'s blind_s, the hang check and R6's `{s}` are not in the diff.
- Item 3, `ai-trader/aitrader/ownerlines.py:110-112`. A stop that is not an int or a float, or is a bool, renders
  `WORDS["held"]["unknown"]`; a numeric stop renders as before.
  - All four callers of `held_text` go through the shared function: `say()` supervise.py:901, R5e supervise.py:648,
    R4c uptime.py:235, and the R2/R4/R6 paths through `say()`.
  - `grep ':\.2f'` over `aitrader/*.py` shows no other formatter of a held map. `sold_text` reads trade rows.
    `news_live.py:1114` is the engine's own catch-up line.
  - The brief's two `test_ownerlines.py` assertions are there (`test_ownerlines.py:181`, `:184-185`). So is the
    `--status` test (`test_supervise.py:1946`, rc 0 and the R5e line with "סטופ לא ידוע").
- Item 4, `ai-trader/tests/test_uptime.py`, `test_r4c_says_unknown_when_the_days_last_up_has_no_held_map`:
  - The last `up` has `held=None`, and an earlier `up` holds MU, so the last `up` must win.
  - An exit at 20:30 is open at the close, and no R4 or R4b row is sent, so R4c is still sent under 14c's rule.
  - It asserts "לא ידוע" and not "אין פוזיציות". It passes at once: a pin, as the brief expected.
- Item 5, supervise.py:1022-1024: the `ponytail:` comment says what the brief asks. Comment only.
- Item 6, `test_supervise.py` `kill_ours`: `STAMPLESS_CHILD` and the new `PAUSED_STAMP_CHILD` are in the set.
- Item 1's test, `test_supervise.py:1395-1421`:
  - Real SIGSTOP/SIGCONT to the test's own parent and its child's group, market open, `outage_report_seconds` 2.
  - Exactly one `pause` row, and exactly one R4/R4b row: the first `up`'s, running from the earlier row to the `up`.
  - How the window is held open: the dummy child's `first_after_s` 3 and `start_grace_seconds` 30.
  - Guarded by the `["pause", "up"]` order assertion.
- Item 2's test, `test_supervise.py:1431-1444`. The child's stamp freezes at SIGCONT. The test asserts:
  - the only `stale_stops` row is the R6's;
  - R6.t minus pause.t is at least 2 s, which is stops_stale_seconds;
  - `{s}` is at least 4 + 2;
  - the alert kinds are exactly R4 and R6.
- Extra: two tests beyond the brief (`test_supervise.py:1423`, `:1446`). Each pins one departure; the report's mutant
  runs show each fails on the literal form. Not over-engineering.

Cannot verify from this diff:
- Whether the controller ratifies departures 1 and 2. Both narrow Ruling 53's literal text; the evidence is above.
- That the parent's clock offset (10:00 New York) makes the four new process tests hour-independent under Ruling 16.
  The report states it; `spawn_parent` is not in the diff.
- The reported durations (about 7-8 s per new process test) and the 3x stability runs. Not re-run.

### Strengths

- Both departures are root-cause readings of the brief: the implementer checked each premise against `gap_line` and
  the stale episode's end branch. Each has a mutant run proving its guard test bites.
- `held_text` fixes the shared function once, so every caller (say, R5e, R4c) is covered. The fix reuses the module's
  own word and has no new literal.
- `paused()`'s docstring and the stale-check comment say why, not just what. The R5e `except` comment was corrected
  where the change made it untrue.
- The process tests signal only pids they started. Before signalling they check `/proc/<pid>/cmdline` and the child's
  group. `PAUSED_STAMP_CHILD` exits when orphaned, and a `kill_ours` cleanup is added for it.
- The RED evidence for item 1 shows the exact double (two R4 rows over the same minutes). For item 2 it shows R6 in the
  pause's own second (`timedelta(0)`).

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- `ai-trader/aitrader/supervise.py:1005`: a pause whose R4 was skipped for a pending first `up` gets no line of its own
  if this parent never reaches an `up`, for example:
  - a crash loop that trips;
  - a halt;
  - a SIGTERM before the first look.

  The next parent's R4b starts at the `sup_stop`, after the pause. Before 14d the pause's R4 went out at once. The
  brief's design has this gap; the report names it. R11 still counts the minutes at the close. Fix if wanted: keep the
  skipped line in `seen`, and send it when the parent ends with `seen["gap"]` still set.
- `ai-trader/tests/test_supervise.py:1446`: `test_a_stale_stops_episode_open_before_a_pause_is_still_open_after_it`
  never asserts that a `pause` row was written. If the pause ever went undetected, the guard would pass with nothing
  tested; it already passes on the base code. Add `self.assertEqual(len(self.urows("pause")), 1)`.
- `ai-trader/tests/test_supervise.py:1442`: `PAUSED_STAMP_CHILD` writes no `stops_checked_at`. So R6's `{s}` falls back
  to the child's age (`time.time() - kid["started"]`, supervise.py:1068), not the stamp's age. The assertion "at least
  4 + 2" holds for both, so the test cannot tell them apart, and its comment "{s}: true" claims more than it checks. The
  brief's wording is met.
- `ai-trader/aitrader/ownerlines.py:111`: NaN or inf passes the number test and prints "nan" or "inf" in an owner
  line. The brief's rule (int or float) is met; this is the same class one step further. Fix:
  `math.isfinite(stop)` in the test.
- `ai-trader/aitrader/supervise.py:1022`: the comment's "at most hang_term_grace_seconds" leaves out the unbounded
  `child.wait()` after SIGKILL in a hang stop (supervise.py:1179). Normally instant. The wording is the brief's.
- Pre-existing, not from 14d: the report notes `[news] ...` lines from other test files' engines in the suite output.
  It also notes an orphaned `GROUP_CHILD` (pid 2841, parent 1, from 01:27 UTC), so some earlier test leaked a process.
  Neither comes from this task's files.

### Assessment

Task quality: Approved. All six items are built, and the brief's tests exist with its assertions. The two departures
fix real defects that the literal text would have caused: an untold pause on the usual morning start, and a false R6b
after a pause. I confirmed both in the code. Nothing touches a stop look, a trading rule, config.json or the phone.
