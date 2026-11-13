### Task 8a: Four follow-ups from the reviews of Tasks 4-7

**Kind:** BUILD. **Authority:** the supervisor spec, sections 5.5 (a beat after every network call; the parent kills an
engine whose beat is older than `hang_seconds`) and 5.6 (a sale is said; nothing stops silently), and three concerns
that the implementers of Tasks 4 and 6 reported and the controller ruled on (ledger, 2026-11-11). This task is not in
the plan. It runs after Task 8 and lands with rollout step 1.

**Files:** Modify `aitrader/news_live.py` (`NewsTrader.check_stops` and what it calls to send an alert,
`_look_at_stops`, `step`). Test: `tests/test_news_supervised.py` (class `FollowUps`).

**Interfaces:** Consumes `_beat`, `read_heartbeat` (Task 4), `_unsent`, `_mark_told`, `told_through` (Task 6), the
order of `_run` (Task 7), `hold()` and `_Engine`. Produces no new name: four behaviours.

1. **A beat after every send of a stop look.** Today the tail of `check_stops` can send one "stop not checked" alert
   per held name, each a network call of up to 15 s per channel, with no beat between them: 12 blind names (6 with
   two channels) pass `supervisor.hang_seconds` (180) and the parent of Tasks 11-14 would kill an engine that is slow,
   not hung. From now on a `_beat("stops")` follows each owner alert that a stop look sends (the blind alerts, the
   catch-up alert, and the look's own message of Task 6). A sale never waits for a beat: the beat comes after the
   send, and no beat is added before any sale or save.
2. **The closing beat also when the blind list changed.** `_look_at_stops` ends with one `_beat("stops")` when the
   look stamped a held name (Task 4). It now does so as well when the look changed which held names are blind (a name
   became blind, or stopped being blind), so the file's `blind` and `blind_since` are right as soon as the look ends.
   A look that changed neither still writes no closing beat.
3. **An unsent line of an earlier look is carried by the next step's closing message.** After Task 7 the first look
   of a start runs outside any step. When that look sells and no channel takes its line, the line must not wait for
   the next start of the day: the closing message of a step carries every trade line of this process that no channel
   has taken yet (the rows in `_unsent` that this process logged), oldest first, and a delivered closing message marks
   them told as Task 6 does. Rows adopted from a previous process stay with `say_late()` and are not repeated by the
   closing message. A line is still never dropped and `told_through` still never passes a row whose line nobody got.

4. **No long stretch without a beat at a start.** After Task 7 a start writes its "stops" beat after the first
   look and then, before the first step, sends the lines that can wait (E2, E1, the late line: each up to 15 s a
   channel), runs `code_stamp` (two git calls, up to 15 s each) and the priming poll (one feed call per symbol of
   the universe). From now on a `_beat` with the current phase follows each of those sends, follows `code_stamp`,
   and follows every feed call of the priming poll, so no stretch of a start goes beyond one network call without a
   beat. The order of Task 7 does not change and nothing new stands before the first look.

- [ ] Write class `FollowUps(_Engine)` in `tests/test_news_supervised.py`:

```python
    def test_every_alert_of_a_stop_look_is_followed_by_a_beat(self):
        # 12 names held, none with a live quote, each blind for longer than news.stop_blind_alert_seconds.
        # The notify.send stand-in appends the number of heartbeat writes so far to `seen` and returns ["ntfy"].
        self.nt.check_stops(...)                        # as the other tests of this file call a look
        self.assertEqual(len(seen), 12)
        self.assertEqual(seen, sorted(set(seen)))       # strictly rising: a beat stands between any two sends
        self.assertGreater(writes_after_the_look, seen[-1])   # and one follows the last send

    def test_a_look_that_only_changes_who_is_blind_leaves_a_closing_beat(self):
        hold(self.nt)                                   # first look: BBB has a live quote and is stamped
        self.nt._look_at_stops([], guarded=True)
        # second look: no live quote for BBB, so no stamp changes and BBB turns blind
        self.nt._look_at_stops([], guarded=True)
        b = news_live.read_heartbeat()
        self.assertEqual((b["phase"], b["blind"], list(b["blind_since"])), ("stops", ["BBB"], ["BBB"]))
        # third look: the quote is back; the list empties and the file says so at once
        self.nt._look_at_stops([], guarded=True)
        self.assertEqual(news_live.read_heartbeat()["blind"], [])

    def test_a_look_that_changes_nothing_writes_no_closing_beat(self):       # nothing held
        before = writes()
        self.nt._look_at_stops([], guarded=True)
        self.assertEqual(writes(), before)

    def test_a_first_look_line_nobody_took_is_in_the_first_steps_closing_message(self):
        hold(self.nt); self.nt.save(); self.prices["BBB"] = 48.0
        # notify.send stand-in: the first call returns [] (the look's own send fails), every later call ["ntfy"]
        self.assertEqual(self.start(), 0)               # start() as in class FirstLook: _run with one short step
        told = [b for ok, b in calls if ok and "SELL 10 BBB" in b]
        self.assertEqual(len(told), 1)                  # said once, by the step's closing message, in this same run
        self.assertEqual(news_live.read_heartbeat()["told_through"], journal.read("news_trades.jsonl")[-1]["hash"])

    def test_a_start_beats_after_every_send_git_call_and_priming_feed(self):
        # no lock (E2), a mismatch (E1) and one unsent row (the late line); priming on, 30 symbols in the universe;
        # every outside call's stand-in appends the number of heartbeat writes so far to `seen`
        self.assertEqual(self.start(locked=False, prime=True), 0)
        self.assertEqual(len(seen), 3 + 1 + 30)            # three sends, code_stamp, thirty feed calls
        self.assertEqual(seen, sorted(set(seen)))           # a beat between any two of them

    def test_rows_of_the_run_before_are_left_to_the_late_line(self):
        # one SELL row of today on disk, heartbeat with told_through None; this run trades nothing
        self.assertEqual(self.start(), 0)
        self.assertEqual(sum("SELL" in b for _, b in calls), 1)              # the late line only, not the closing message too
```

  The fragments name what each test must show; complete the stand-ins the comments describe. Where a call's exact
  arguments differ on the tip (`check_stops`, `_look_at_stops`), the code and the earlier tests of this file are
  right; the assertions stay.

- [ ] Run `-p 'test_news_supervised.py' -k FollowUps`. Expected: the first test fails (`seen` holds one number twelve
  times, or `sorted(set(seen))` is shorter than `seen`).
- [ ] Implement the three behaviours.
- [ ] Run `-k FollowUps`: 6 tests, `OK`. Then the whole file and `tests/test_supervise.py` 3 times in a row, then the
  whole suite: `OK` (the brief tests of Tasks 4, 6 and 7 still pass unchanged: in particular the three-batch test
  still reads "quotes", "score", "score").
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/tests/test_news_supervised.py`; message
  `fix(ai-trader): a beat after every send of a look and of a start, the blind list at once, and no unsent line left for the next start`.

**For the report and the gate:** no buy, sale or stop rule changes; no sale is delayed (show where each new beat
stands relative to the sale and the save). It touches no file the time machine loads.
