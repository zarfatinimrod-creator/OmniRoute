# Task 8a - re-review of fix round 1

Fix base `11e7e6932b2b81049ebbd1ab73193571f5f9337d`, head `f81e15446593db92d6caf870ab1d17f66e339095` (one commit,
`f81e1544`), gate clone `<SCRATCH>/clones/sup`.
Diff package: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-8a-fix1.diff` (2 files,
+28 / -2). Read-only review. No test was re-run: no doubt came up that the existing runs do not answer.

### Finding Verdicts

**F1 - ADDRESSED.**
- `ai-trader/aitrader/news_live.py:1092`: `self._beat("stops")` now follows the `notify.send` of `_catchup_unread`
  (`:1089-1091`). It stands after the once-per-name early return (`:1086-1087`), so a beat follows only a real send.
  Both callers are covered by the one line: the bars-unreadable path (`:1056`) and the `except` path (`:1080`).
- `ai-trader/aitrader/news_live.py:1112`: `self._beat("stops")` now follows the `notify.send` of
  `_earlier_days_unread` (`:1109-1111`). It stands after the `unread is None or sym in told` return (`:1106-1107`).
- The only caller of `catch_up_stops` is `_look_at_stops` (`:1139`), so both beats fire only inside a stop look. The
  phase is already "stops" there (`:1126`). `_beat` never raises (`:1645-1646`), so the new lines cannot cost a step.
- The ruled test expectation was edited as the finding asked:
  `tests/test_news_supervised.py:182` now expects four "stops" beats for `look(0, False)`. I checked the count
  against the code: quote beat, bar-read beat (`:1049`), the new beat after the "could not be read" send, then the
  closing beat. The stamp check `utc(0)` and the other three looks are unchanged. The controller ruling is still
  owed (see Out-of-Scope).
- The new test is `FollowUps.test_the_earlier_day_alert_and_the_unread_bars_alert_of_a_look_are_each_followed_by_a_beat`
  (`tests/test_news_supervised.py:1300-1321`). I traced it against `catch_up_stops`:
  - Look 1 at 09:31: six quotes, then for each name `_earlier_days_unread` is called (Monday 14:00 is before the open
    and more than `stop_catchup_gap_seconds` before Monday's close; `entry_date` 2026-11-09 is not the look's day).
    Then `continue` at `:1043-1044` (60 s < `stop_catchup_min_seconds`).
  - Look 2 at 09:40: six quotes, then per name a bar read (`None`), `_covered` is set, and `_catchup_unread` sends.
  - That gives the sequence `["quote"]*6 + ["send"]*6 + ["quote"]*6 + ["bars","send"]*6`, which the test asserts.
  - The strictly-rising assertion fails without either beat: six equal counts in look 1, and each send sharing its
    count with the next bar read in look 2. RED in `t8a-fix1/red.txt`: `[..., 6, 6, 6, 6, 6, 6, ...]`. The report's
    planted-defect runs match: 1 failure without the `:1112` beat, 2 without the `:1092` beat.
  - Clock and `entry_date` are fixed, and `now` is passed in, so the test does not depend on the hour.
  - The module stand-ins are restored by `_Engine.tearDown` (`tests/test_news_guards.py:56-59`).

**F3 - ADDRESSED.** This is the same defect as F1, and the same two lines fix it.
- The scenario F3 named is now covered: N held names whose last look was on an earlier day, in the first
  `stop_catchup_min_seconds` after the open, with no bar read between their sends. Each send in that loop is now
  followed by a beat (`:1112`), so the longest stretch without a beat is one send.
- Every send reachable in a stop look now has a beat after it:
  - the catch-up alert, `:1074/1075`;
  - the unread alert, `:1089/1092`;
  - the earlier-day alert, `:1109/1112`;
  - the price-back line, `:1177/1178`;
  - the blind alert, `:1189/1192`;
  - the look's own message, `:1154`: its beat comes from `_mark_told` when the message is delivered, and from
    `:1162` when it is not.
- The test F3 suggested (several earlier-day names, a look under 120 s after the open, a send stand-in that records
  the heartbeat writes, assert strictly rising) is the first half of the new test. The second half also covers
  `_catchup_unread`.
- The placement is the one F3 asked for: after the early returns, where the catch-up alert's beat at `:1075` already
  sits. That is after the live look's sales and saves (`check_stops` runs first, `:1131`). The beats do come before
  the optional "sell"-mode re-check (`:1141-1142`) and before `save(seen=False)` (`:1146`), but those already waited
  behind the sends themselves. The added cost is one heartbeat write per send, and "sell" is not the configured
  mode. No beat was put before a sale or a save that its send did not already precede.

### New Breakage in the Fix Diff
None.
- The new beat after the unread alert writes `held[sym].checked_at` for a stretch that could not be read. The stamp
  was set at `:1055` before the send, so it now reaches the file a little before the closing beat of the same look.
  The value is the same: the Task 4 test still sees `utc(0)`. It is still written only after that name's bar-read
  beat, as Task 4's ruling requires.
- No buy, sale or stop rule changed. No file the time machine loads was touched.
- The commit message has no Co-Authored-By, no "Generated with" line and no session link.

### Out-of-Scope Observations
- The edit of the Task 4 ruling test's expectation (`tests/test_news_supervised.py:182`, 3 -> 4 "stops" beats) still
  needs the controller's ruling. Both the finding and the implementer's report say so. The edit is the smallest
  one that states the new behaviour, and it is a heartbeat test, not a test about a trade, stop, buy, sale or hold.
- Commit `f81e1544`'s author is `Claude <<email>>`, as on every earlier commit of `supervisor-build`
  (the clone's configured identity, report item 6). Constraint 8 lists trailers, footers and session links, not the
  author field. Still, the controller may want the identity checked before the landing.
- The `_earlier_told` and `_catchup_blind` sets live only in memory, so a process started after a kill sends the
  same earlier-day lines again (F3 notes this). Each of those sends now has its beat. Whether to repeat them across
  processes is not this fix's question.
- The fix report says the review's Important 2 (serial priming) and its minor items were not on this round's list.
  They are untouched and not verdicted here.

### Verdict
APPROVED for this round: F1 and F3 are fixed by two `_beat("stops")` lines, each after its function's once-per-name
return. A new test exercises both sends, and its RED was shown. The fix report gives the covering commands and their
output:
- FollowUps: 9 tests OK.
- `test_news_supervised.py`: 88 tests OK three times.
- `test_supervise.py`: 19 tests OK three times.
- The whole suite: 659 tests OK.

These match the diff (one new test; 658 + 1). One process item stays open: the controller must ratify the edited
expectation in the Task 4 ruling test.
