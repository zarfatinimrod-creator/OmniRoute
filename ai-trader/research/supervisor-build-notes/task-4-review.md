# Task 4 review - a heartbeat after every network call

Diff 2c5cf812..8ed84237 (one commit), read from `review-task-4.diff`. Reviewed in one pass. Code read outside the diff, one check per named risk, from `git show 8ed84237:ai-trader/aitrader/news_live.py`:
- Risk: `adopt_previous` setting `_prev_look` early clashes with the lazy read in `_look_at_stops`. Checked news_live.py:1072-1075. That read is guarded by `hasattr`, so the adopted value wins and the lazy path only runs when nothing was adopted. No clash.
- Risk: the adopted `_blind` entries have a different shape or time type from what `_stop_sight` uses. Checked news_live.py:1104-1121. It uses `[time, told]`, takes `now - since[0]` across aware datetimes (NY minus UTC is valid), and returns early when `since[1]` is true. Matches.
- Risk: the new closing beat compares against the wrong snapshot. Checked news_live.py:1067. `seen = dict(self._covered)` is taken at the start of the look, before `check_stops`, so the comparison is right.
- Risk: the test that assigns `news_live.market_open_now` directly leaks into other tests. Checked test_news_guards.py:40-57. `_Engine.setUp` saves the original and `tearDown` puts it back, which is the house pattern. No leak.
- Risk: spec 5.5 names sends as calls that need a beat. Checked spec 5.5. It does not: its list is held-name quotes, queued names, the poll, headline quotes, scorer batches, second checks and the end of the step.

No test was re-run.

### Spec Compliance
Compliant.
- `read_heartbeat`, `_beat` and `adopt_previous` match the brief's interfaces (news_live.py diff +34-41, +275-340).
- Every kept field and every new field is written (+325-338). `told_through`, `mismatch_told` = null and `supervised` = false, as the brief says for Tasks 5, 6 and 8.
- Beats sit where the brief puts them:
  - boot: `_run` +365-366.
  - stops: per held name in `check_stops` (+65, +87) and after `bars_since` in `catch_up_stops` (+109).
  - queue: +185, +199.
  - poll: +232.
  - quotes: +239.
  - score: after each batch (+243) and after a second check the loop waited for (+156).
  - idle: +269.
- Only "idle" works out `headlines_seen`, `stops_checked_at` and `buys_blocked`; every other beat repeats `_beat_kept`. Matches the brief.
- `adopt_previous`:
  - Takes the last stop look from `prev["stops_checked_at"]` as aware UTC, else falls back to `_last_stop_check()`.
  - Before this process's first look, every beat writes the adopted stamp (via `_beat_kept`, and `before` at idle).
  - Takes over `blind_since` only when `prev["at"]` is today in New York, only for names still held, and carries the told flag.
- The seven `Heartbeat` tests exist under the brief's names, with the brief's assertions and stand-ins (test_news_supervised.py +515-569).
- Controller rulings of 12:19 UTC:
  - (1) form a, (2) form b: both applied as worded. The error text of the second stand-in is unchanged and the `news_errors.jsonl == []` assertion is untouched (test_news_inputs.py +391-426).
  - The closing "stops" beat of `_look_at_stops` is written only when the look stamped a held name (+131-134), and it has its own test (+585-604).
  - The extra "queue" beat after `official_opens` (+178) was ratified by the controller.
- No unrequested feature. The 11 extra tests in `EveryCallAndEveryStart` are coverage, not features.

Cannot verify from this diff:
- Task 12/14, the parent, reads the per-name `held[sym].checked_at` stamps. The top-level `stops_checked_at` repeats between idle beats by design.
- Task 7 owns start order. Between the boot beat and the first step there are git calls, the priming poll and sends with no beat, and `code` is null in the boot beat.
- Spec 5.5's test "30 slow quote stubs keep the heartbeat younger than `hang_seconds`" is carried by the brief's count assertion (`beats.count("quotes") >= 30`). No timing is tested.

### Strengths
- `_beat` is the single writer. It cannot raise, and a failing write is covered by a test that also shows the sale still happens (+648-661).
- Each per-name beat is written after that name's handling, so a sale never waits for its beat. A test pins the order: book saved, then heartbeat (+606-616).
- `adopt_previous` handles damaged input without failing the start. Covered cases: torn file, non-object, empty file, a non-string stamp, a list `blind_since`, a stamp with no zone (+726-747).
- A three-process restart test shows a blind alert is neither repeated nor put off, and that "the price is back" follows either process's alert (+705-724).
- The closing-beat test runs on a fixed clock and covers four cases: no held name, a bar-read stamp, a look that stamps nothing, and a live-quote stamp.
- No literal threshold was added. No test reaches the network or the phone. No trading rule changed beyond what the brief names (where the catch-up starts after a restart; when the blind alert fires after a restart).

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)
- news_live.py:887 / 918-931 (the alert tail of `check_stops`), and `step()`'s `notify.send`: sends have no beat of their own.
  - In an outage where both quotes and ntfy fail, N blind alerts at 15 s per channel come after the last per-name beat. That passes `hang_seconds` (180) at about 12 names with one channel, or 6 with two.
  - Neither the brief nor spec 5.5 names sends, so this is out of scope for Task 4. It should go to the controller for Task 12, which judges hangs.
  - Fix: a "stops" beat after each `_stop_sight` that sent, or a hang rule that allows for it.
- news_live.py diff +296: `sym in told` uses `told = prev.get("blind_told") or ()`. A damaged string value such as "BBB" would do a substring match ("BB" in "BBB").
  - Fix: `set(told) if isinstance(told, list) else set()`.
- news_live.py diff +332: the stop default `pos.get("stop_price", pos["avg_cost"] * (1 - self.n["stop_loss_pct"]))` now appears a third time (it is also at +73 and +107). Small duplication; a `_stop_of(pos)` helper would remove it.
- news_live.py diff +339-340: a heartbeat that cannot be written leaves one `news_errors.jsonl` row per beat, so a full disk means dozens of rows a step. `_note_error` also stores `str(e)[:300]`, i.e. exception text.
  - Both follow the brief's `_note_error(e, "heartbeat")`. The text is a local OSError, not a topic or URL, so it does not breach the topic rule.
  - `error_once` would rate-limit the rows.
- news_live.py diff +365-367: `code` is null in the boot beat because `code_stamp()` now runs after it. This follows the brief's literal order. `skills/trader/SKILL.md` reads `code.started`, which is null during the start window. Task 7 owns start order.

### Assessment
Task quality: Approved. Every requirement of the brief and every ruling is in the diff, with tests that check real behaviour (save order, alert counts, file contents). What remains is outside this task's scope (sends with no beat) or small hardening.
