# Task 15 re-review, fix round 1 (Handover by the clock)

Fix base 0952ee9b, head 2219f55d (one commit: `fix(ai-trader): measure a handover with the market closed from beat to
beat`). Diff package: `review-task-15-fix1.diff` (supervise.py +7/-3, test_supervise.py +22).

### Finding Verdicts

**F2 - ADDRESSED.**
- Defect at 0952ee9b: the handover branch took `last_look` from `_looks(hb)`. With no per-name stamp before the open,
  `_looks` fell back to the adopted `stops_checked_at` (yesterday's close). On an early-close day the stamps were from
  about 13:00. The next parent's `up()` takes the beat's `at` for every unlooked or blind name, so `handover_s` came out
  at about 62,000 s at 09:18 and about 4,700 s at 14:17.
- At 2219f55d, `ai-trader/aitrader/supervise.py:1172-1173`:
  `looks = [] if hb.get("market_open") is False else list(_looks(hb).values())` then
  `looks = looks or [_when(hb.get("at"))]`. When the last beat says the market is closed, `last_look` is that beat's
  `at`. Neither the 09:18 path (stops_checked_at fallback) nor the early-close path (13:00 per-name stamps) is used
  then. This is the form the finding recommended.
- The new side is unchanged and matches. `up()` runs at the first beat when `view["open"]` is false
  (supervise.py:987). It maps a blind name, a missing stamp, or a stamp older than the child to the beat's `at`
  (supervise.py:1059-1061). So both sides now measure from a beat. `handover_s` (supervise.py:1072-1074) is the gap
  between the two beats.
- The test is real. The engine always writes `"market_open": bool(market_open_now())` (news_live.py:1709), so
  `is False` matches every beat it writes. A beat without the field, or with `true`, keeps the old path unchanged.
- New test `Handover.test_with_the_market_closed_a_handover_is_measured_beat_to_beat`
  (test_supervise.py:1811-1831). It covers both cases in one beat: AAA with `checked_at: null` and a `stops_checked_at`
  17 h old (09:18), and BBB with a stamp 80 min old (early close). It asserts `0 <= handover_s < 60` on the next
  parent's first `up`, and `last_look == at`.
- The test discriminates. The report shows RED at 61,202.0 s without the fix. A weaker mutant that only drops the
  `stops_checked_at` fallback fails it at 4,802.0 s.
- Brief wording. Before the open no held name has a `checked_at`, so the brief's "oldest `checked_at`" does not cover
  the 09:18 case. The early-close case does depart from the brief's literal wording: BBB's 13:00 stamp is set aside.
  That departure is what the finding asked for. The brief's own assertion `0 <= handover_s < 60` and target 11 need
  it. The implementer flags it for the controller (see Out-of-Scope).

### New Breakage in the Fix Diff

None.
- `hb = {}` (no beat file) still gives `last_look` None, as before.
- An in-session beat (`market_open` true or missing) takes the per-name path, byte for byte as before.
- A handover by `max_leg_minutes` after the close (about 16:07) is also measured beat to beat on both sides.
- In the edge case where the last beat is closed but the next `up` is in session (around 09:30), `handover_s` is the
  real gap of a few tens of seconds, not yesterday's stamp.
- The two comment edits (supervise.py:1068-1070, 1169-1170) describe the new behaviour correctly.

### Out-of-Scope Observations

- The finding said F2 needed the controller's ruling before a fix, because spec 4.5 reads "the old engine's last stop
  look". No ruling on F2 is recorded in controller-notes.md or progress.md. The implementer built it because the
  dispatch listed F2 under "Findings to fix". The controller should record the ruling and the plan line 1068 wording,
  since the early-close case now departs from the brief's literal "oldest `checked_at`".
- Unchanged path: the in-session handovers (10:48, 12:28, and 14:17 on a full day) still use per-name stamps. A held
  name that is blind in session keeps an old `checked_at` for hours (first_look_done docstring), while the new side's
  `up()` takes the beat's `at` for it. So the same old-stamp against new-beat mismatch can still give a large
  `handover_s` in session. The finding scoped this out ("In session, keep the per-name stamps").

### Verdict

F2 is addressed. The fix diff introduced no new breakage. The fix report gives the covering test, the commands, the RED
output, and the GREEN runs: the Handover class 3 times (7 OK), test_supervise.py 3 times (121 OK) and the whole suite
(807 OK). The fix round passes. The controller should still record the F2 ruling.
