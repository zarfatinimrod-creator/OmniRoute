# Task 8a report - four follow-ups from the reviews of Tasks 4-7

**Status: DONE_WITH_CONCERNS.** One commit on `supervisor-build` in the gate clone, on top of `3366396f`:

- `11e7e693` (`11e7e6932b2b81049ebbd1ab73193571f5f9337d`)
  `fix(ai-trader): a beat after every send of a look and of a start, the blind list at once, and no unsent line left for the next start`

Start state checked first: HEAD `3366396fb2cbafaaaf7063682bee2ceac719ab2b`, branch `supervisor-build`, tree clean.
After the commit `git status --short` prints nothing. The commit has no trailer and no attribution line. Nothing was pushed,
no git setting was changed and no subagent was used. Every python command ran through the `safe` wrapper.

The work is complete and green. The concerns are three readings of the brief that the controller should see; they are
at the end, and concern 1 is the main one.

## What is built (`aitrader/news_live.py`, +43 -11)

1. **A beat after every send of a stop look** (`_beat("stops")`):
   - `_stop_sight`: after the urgent "no live quote" alert, and after the high "the price is back" line (the blind
     alerts). The beat after the alert carries the told flag the send just set.
   - `catch_up_stops`: after the "stop traded through while unwatched" alert (the catch-up alert).
   - `_look_at_stops`: after the look's own message (Task 6). If a channel took it, `_mark_told` writes the beat as
     before. If no channel took it, or the send raised, a new `_beat("stops")` follows.
2. **The closing beat also when the blind list changed:** `_look_at_stops` takes `was_blind` (the held names in
   `_blind`, the file's own `blind` set) before the look. Its closing `_beat("stops")` is now written when that set
   changed, or when a held name was stamped (Task 4). A look that changed neither writes no closing beat.
3. **This process's earlier unsent lines go in the next closing message.** `step()` records `earlier` when it begins:
   the hashes in `_unsent` that are not rows of `_late`, which are the rows adopted from the run before. Its closing
   message builds their lines from the journal with `_trade_line` and puts them first, oldest first, before the step's
   own owed lines. The message now also goes out when the step itself has no lines. A message a channel took calls
   `_mark_told(earlier + self._unsent[mine:])`. Adopted rows stay with `say_late()`. A journal that cannot be read
   leaves the earlier rows owed for the next step, writes an error row (`where` "step_alert"), and the step's own lines
   still go out.
4. **No long stretch without a beat at a start** (`_run`, order of Task 7 unchanged, nothing new before the first
   look): `nt._beat(nt._phase)` after the E2 block, after the E1 block (moved out of the "taken" branch, so it follows
   the send whether or not a channel took it), after `say_late()`, and after `code_stamp()`. The beat after
   `code_stamp()` also puts `code` in the file at once. In `poll_headlines(prime=True)`, a beat follows each feed
   call, and the priming poll asks one feed at a time (see concern 3). A step's poll is unchanged: eight threads and
   its one "poll" beat. Two lines in `_run`'s docstring say this.

No new method, attribute or module name: only local names (`fed`, `blind`, `was_blind`, `told`, `unsent`, `late`,
`earlier`).

## Where each new beat stands relative to the sales and saves

One beat costs 0.48 ms with three held names (measured, `t8a/beat_cost.py`). A send costs up to 15 s per channel.

| New beat | Stands right after | Relative to sales and saves |
|---|---|---|
| `_stop_sight`, two places | the blind alert / the "price is back" line | In the tail of `check_stops`, after every sale of that call (each `_log_trade` saves the book) and after the exits save. |
| `catch_up_stops` | the catch-up alert | After the live look's sales. Before an optional "sell"-mode sale and before the look's save, but those already waited behind the alert's send (old order); the beat adds 0.5 ms to a send of up to 15 s. |
| `_look_at_stops`, closing beat (new condition) | the look's save | After every sale and save of the look; same place as Task 4's beat. |
| `_look_at_stops`, after a message no channel took | the look's own message | After the look's save and closing beat, the last thing the look does. |
| `_run`: E2, E1, late line, `code_stamp` | each send / git | After the first look and its "stops" beat; no sale can happen at a start after that point. |
| `poll_headlines(prime=True)` | each feed call | At a start, after git; no sale. |

No beat stands between a quote and the sale it leads to, or between a sale and its save. No buy, sale or stop rule
changed. With the "stopping" beat of Task 8 nothing new runs after it, and every new start beat repeats the current
phase (`nt._phase`). `news_live.py` is imported only by `aitrader/__main__.py`. `backtest.py` does not import it, so
the diff touches no file the time machine loads.

## TDD evidence

All commands from `<clone>/ai-trader` through `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`.
Output is kept in `<SCRATCH>/t8a/`.

**RED, the first run** (`red.txt`): `safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k FollowUps -v`,
with the engine of `3366396f` and the tests just written. `Ran 7 tests`, `FAILED (failures=5)`. The first test fails
the way the brief expects:

```
FAIL: test_every_alert_of_a_stop_look_is_followed_by_a_beat
    self.assertEqual(seen, sorted(set(seen)))     # strictly rising: a beat stands between any two sends
AssertionError: Lists differ: [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12] != [12]
FAIL: test_a_look_that_only_changes_who_is_blind_leaves_a_closing_beat
AssertionError: Tuples differ: ('stops', [], []) != ('stops', ['BBB'], ['BBB'])
FAIL: test_a_first_look_line_nobody_took_is_in_the_first_steps_closing_message
AssertionError: 0 != 1
FAIL: test_a_start_beats_after_every_send_git_call_and_priming_feed
AssertionError: Lists differ: [3, 3, 4, 5, 5, 5, ...] != [3, 4, 5]
FAIL: test_the_catch_up_alert_the_price_back_line_and_the_looks_own_message_are_each_followed_by_a_beat
AssertionError: Lists differ: [0, 1, 2, 2, 3, 3, 5, 5] != [0, 1, 2, 3, 5]
```

`test_a_look_that_changes_nothing_writes_no_closing_beat` and `test_rows_of_the_run_before_are_left_to_the_late_line`
passed on the old engine. That is expected: they pin what must not change, and the planted defects M6 and M7 below
show that they catch a wrong build.

**RED, the final tests on the old engine** (`red-final.txt`). The engine of `3366396f` was put into a scratch copy;
the clone was not touched. `Ran 8 tests`, `FAILED (failures=6)`: the same five, plus the eighth test
(`... [(1, 0), (1, 0), (0, 1), (0, 1)] != [... (1, 1)]`: the old line was not carried). The start test now fails with
`[3, 3, 3, ...]`, because no channel takes a line there (see "Self-review", item 2).

**GREEN** (`green.txt`): `-k FollowUps -v` gives all 8 tests `... ok`, `Ran 8 tests in 0.349s`, `OK`.

**Three times in a row**, on the committed files:
- `tests/test_news_supervised.py` (in-process): `Ran 87 tests in 2.350s OK`, `2.216s OK`, `2.381s OK`.
- `tests/test_supervise.py` (the file that starts processes): `Ran 19 tests in 36.872s OK`, `36.610s OK`,
  `35.311s OK`.

Each run printed 5 lines (pristine). No engine child was left behind (`pgrep`).

**At any hour** (the 11:10 ruling). I added and changed no process test. The whole in-process file was run with
every clock the engine and the tests ask moved (`t8a/shifted_inproc.py`, Task 6's script, read before use, run on a
scratch copy). It printed `Ran 87 tests ... OK` at each of these New York times: Wednesday 17:00, 03:00, 09:31 and
23:58; Saturday 2026-11-14 12:00 (no session); and the early close of 2026-11-27 at 12:30 and 13:30. The starts of
the new tests pass "23:59" (the known ceiling is 23:59-00:00), and the look test uses a fixed clock of its own.

**Planted defects** (`t8a/mutate.py`, on a scratch copy, never the clone; output in `mutants2.txt`). There were 19
defects, planted one at a time, each run against the whole of `test_news_supervised.py`. All 19 were caught, and
the old engine (M0) fails 7 tests. The defects:
- no beat after the blind alert, after the price-back line, after the catch-up alert, or after a look message no
  channel took;
- the blind list left out of the closing condition, or a closing beat after every look;
- the closing message carries the late rows too, carries no earlier row, does not mark the earlier rows, puts them
  after the step's own lines, works them out at the closing message (which repeats a line), or marks every unsent row;
- no beat after E2, E1, the late line, `code_stamp` or a priming feed; the priming poll on eight threads; the E1 beat
  only when the line was taken (as before).

The first run left M18 (priming on eight threads) alive, because the feed stand-ins returned at once. The start test's
feed stand-in now waits 5 ms, as a real feed takes time, and M18 then failed 5 runs out of 5.

## Whole suite

`safe python3 -m unittest discover -s tests` in the gate clone, on the committed files, wall time 104 s:

```
Ran 658 tests in 103.102s

OK
```

That is 650 + 8. An earlier run, with the first 7 tests, gave `Ran 657 tests in 107.800s OK` (108 s). The lines the
suite prints above the dashes come from older tests, as before.

## Files changed

- `ai-trader/aitrader/news_live.py`
- `ai-trader/tests/test_news_supervised.py`: class `FollowUps` (8 tests) and one edited expectation (see
  "Departures").

These are the brief's two paths and nothing else. Nothing changed under `state/`, `logs/`, `reports/` or `research/`.

## Self-review (`git diff 3366396f..HEAD`)

Found and fixed before the commit:
1. Nothing pinned the brief's "oldest first", nor that a closing message never says the same line twice. I added the
   eighth test (two plain steps; the line of the first step's sale goes out ahead of the second's in one message).
   It catches M10 and M11.
2. In the start test, a delivered late line gets the beat that `_mark_told` writes, which hid the new beat after
   `say_late` (M15 survived). The send stand-in now has no channel take any line. The assertions are the brief's.
3. M18, as described above.
4. Two engine comment lines were wider than 120 characters; both were reworded.

Checked and left as built:
5. The brief, line by line, is covered by the list under "What is built". Each new behaviour has a test, or a defect
   that a test catches. The brief tests of Tasks 4, 6 and 7 pass unchanged, and the three-batch test still reads
   "quotes", "score", "score".
6. `step()` reads `_unsent` and `_late` with `getattr`, so `tests/test_audit_fixes.py`'s `__new__` trader still
   reaches its chain check (the whole suite is green).
7. The priming poll's beats are written from the one worker thread while the main thread waits in `ex.map`, so only
   one writer touches `news_heartbeat.tmp`. On eight threads, two beats could race on that file.
8. A few beats are redundant, written where they cost a millisecond and keep the code simple. The E1 block beats even
   when E1 was told earlier today and nothing was sent; the beat after `say_late()` comes even when no line was due,
   and is a second beat after a delivered one. No beat changes a value except `at`.
9. `ruff check --select F,E9,B` reports the same 3 old findings on the base and on the new files.

## Departures from the brief, and readings

1. **One expectation of a Task 4 test edited** (this task's own file, not a brief test): in
   `EveryCallAndEveryStart.test_each_look_beats_after_each_quote_and_the_step_after_its_poll_and_at_its_end`,
   `["stops", "stops", "poll", "stops", "stops", "idle"]` became
   `["stops", "stops", "stops", "poll", "stops", "stops", "idle"]`, with a comment. In that test the first look turns
   both held names blind, and item 2 requires a closing beat for exactly that. It is a heartbeat test, not a trade
   test, and nothing else in it changed.
2. **8 tests, not 6.** The brief's six are there under their names, with their assertions. Three carry one more
   assertion each:
   - the blind-only test: BBB's `checked_at` is unchanged, so the blind list alone made that beat;
   - the first-look test: the first send was the failed look message;
   - the late-line test: the one SELL message is the late line, the loop made steps, and `told_through` stays null.

   Two tests were added: `test_the_catch_up_alert_the_price_back_line_and_the_looks_own_message_are_each_followed_by_a_beat`
   (the three sends of item 1 that the brief's tests do not reach) and
   `test_a_line_no_message_took_is_carried_step_after_step_oldest_first_and_once_in_each_message`.
3. **Fixture details:** `FollowUps.setUp` sets `news.stop_catchup` "off", because whether a bar read is due depends
   on the hour; the one test that needs the catch-up sets "alert" with a fixed clock. `writes()` is a method
   (`self.writes()`). `start(locked=True, prime=False)` stubs the step's poll and lets the priming poll run for real,
   through a `_feed` stand-in, so test 5 sees its 30 feed calls and steps make none.
   - The late-line test's stand-in has no channel take anything. Otherwise the late line is delivered and
     `_mark_told` drops its row, so no build could fail the test.
   - The start test has no channel take anything, for the reason in self-review 2.
   - The start test's feed stand-in waits 5 ms (self-review 3).
4. **The priming poll asks one feed at a time.** That is the only way a beat can stand between any two of its feed
   calls, which the brief's test asserts. Concern 3 gives the cost.
5. **The look's message beat:** when a channel took the message, the beat is the one `_mark_told` already writes.
   The new beat is written only when no channel took it or the send raised, so a delivered message gets one beat, not
   two.

## Concerns

1. **Two once-per-name sends of the catch-up still have no beat of their own:** `_catchup_unread` ("the bars could
   not be read") and `_earlier_days_unread` ("an earlier day was not looked back at"). The brief's rule says "each
   owner alert that a stop look sends", but its list in brackets names the blind alerts, the catch-up alert and the
   look's own message. "The catch-up alert" is the term the plan uses for the breach alert, and I built to that list.
   A beat after `_catchup_unread` would add a fourth beat to `look(0, False)` in Task 4's ruling test
   `test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once`, which I did not want to
   edit without a ruling.
   - The longest stretch this leaves is about 126 s with two channels: an unread alert (30 s), the next name's
     earlier-day alert (30 s) and its bar read (up to 66 s). That is under `hang_seconds` (180), and each send happens
     at most once per name per process.
   - If the controller wants these covered: one `self._beat("stops")` after each of the two sends, plus that test's
     expectation edited from 3 beats to 4.
2. **While a line of this process stays untaken, every step's closing message sends it again.** This is the brief's
   "every trade line of this process that no channel has taken yet". In a network outage that is one more send per
   step, up to 15 s per channel, until a channel takes it. With no channel configured at all, `notify.send` returns
   `[]` after printing `ALERT: ...`, so the engine would print that line every step for the rest of the process. The
   live engine has a topic set. Before this task, a step without lines of its own sent nothing.
3. **A first start is slower when Yahoo is slow:** the priming poll now asks its feeds one at a time (departure 4).
   That is 30 names at a usual 0.2-0.5 s, so 6-15 s instead of about 2 s; at the 10 s timeout it could reach 300 s,
   with a beat after each call, so it is never taken for a hang. Priming runs only when `news_seen.json` is empty
   (a fresh machine).
4. Beats are counted, not timed. The tests show a beat between any two calls that leave the process; they cannot
   show the real seconds, which depend on Yahoo and ntfy.
5. A trade line carried by a closing message is rebuilt from its journal row with `_trade_line`, so it reads exactly
   as the look wrote it. The loss-pause sentence of a losing sale is not a trade line and is not carried; it is in
   the engine's log. The late line has always behaved this way.
6. The commit's author is the clone's configured git identity, as on every earlier commit of this branch.

Scratch files, none in the clone: `<SCRATCH>/t8a/`
(`red.txt`, `red-final.txt`, `green.txt`, `file-*.txt`, `sup-*.txt`, `suite.txt`, `suite-final.txt`, `mutate.py`,
`mutants.txt`, `mutants2.txt`, `shifted_inproc.py`, `beat_cost.py`, `copy/`).

## Fix round 1

**Status: DONE.** One new commit on `supervisor-build` in the gate clone, on top of `11e7e693`. No commit was amended.
- `f81e1544` (`f81e15446593db92d6caf870ab1d17f66e339095`)
  `fix(ai-trader): a beat after the catch-up's "could not be read" and "earlier day" alerts`

Start state checked first: HEAD `11e7e6932b2b81049ebbd1ab73193571f5f9337d`, branch `supervisor-build`, tree clean.
After the commit `git status --short` prints nothing. The commit has no trailer and no attribution line. Every python
command ran through the `safe` wrapper. Nothing was pushed. Scratch output is in
`<SCRATCH>/t8a-fix1/`.

### F1 and F3 (one defect, one fix): fixed
- `ai-trader/aitrader/news_live.py:1092` (`_catchup_unread`): `self._beat("stops")` right after its `notify.send`.
- `ai-trader/aitrader/news_live.py:1112` (`_earlier_days_unread`): `self._beat("stops")` right after its `notify.send`.
- Both beats come after the function's once-per-name early return, so a beat follows only a real send. The beat in
  `_catchup_unread` also covers its call from the `except` branch of `catch_up_stops` (`:1080`).
- Placement relative to sales and saves: these beats stand where the catch-up alert's beat already stood (`:1075`).
  That is in `catch_up_stops`, after the live look's sales and their saves. They stand before the optional
  "sell"-mode re-check and before the look's `save(seen=False)`, but those already waited behind the send itself.
  A beat adds about 0.5 ms to a send of up to 15 s per channel. No beat was added before a sale or a save that its
  send did not already precede. No buy, sale or stop rule changed.
- With these beats the longest stretch of a stop look without a beat is one outside call: one send (up to 15 s per
  channel) or one bar read (up to 66 s).

**One expectation edited (departs from the brief; it needs the controller's ruling).** This is the Task 4 ruling test
`EveryCallAndEveryStart.test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once`
(`tests/test_news_supervised.py:182`).
- The edit: `look(0, False)` now expects `["stops", "stops", "stops", "stops"]` instead of three "stops" beats. The
  comment at `:180-181` says that the "could not be read" alert has its own beat.
- Why: that look's stand-in returns no bars for the ten minutes it reads, so `_catchup_unread` sends, and the fix
  writes a beat after that send.
- What did not change: the stamp check `utc(0)`, and the other three looks of the test.
- It is a heartbeat test, not a test about a trade, a stop rule, a buy, a sale or a hold. It is in this task's own
  file. It is not a brief test of Task 4 (no brief names it). The finding and the dispatch both name this exact edit.
- The brief tests of Tasks 4, 6 and 7 pass unchanged. The three-batch test still reads "quotes", "score", "score".

**New test (FollowUps):**
`test_the_earlier_day_alert_and_the_unread_bars_alert_of_a_look_are_each_followed_by_a_beat`
(`tests/test_news_supervised.py:1305`). The setup:
- A fixed clock on Tuesday 2026-11-10, so the test gives the same result at any hour.
- Six held names. The run before last looked on Monday at 14:00, two hours before that close.
- Live quotes above the stops. Bars that cannot be read (`bars_since` returns `None`).
- One list records every outside call (quote, bars, send) with the number of heartbeat writes so far.

The test makes two looks:
1. At 09:31, 60 s after the open (under `stop_catchup_min_seconds` 120): six earlier-day alerts in a row, with no
   bar read.
2. At 09:40: per name, a bar read and then the "could not be read" alert.

It asserts the call sequence `["quote"]*6 + ["send"]*6 + ["quote"]*6 + ["bars", "send"]*6`, and that the counts,
followed by the final write count, are strictly rising.

### RED (new test, engine of `11e7e693`)
`safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k FollowUps -v` (`t8a-fix1/red.txt`):
```
FAIL: test_the_earlier_day_alert_and_the_unread_bars_alert_of_a_look_are_each_followed_by_a_beat
AssertionError: Lists differ: [0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 7, 8, 9, 10, 11, 12, 13, 1[41 chars], 20] != [0, 1, 2, ..., 20]
Ran 9 tests in 0.337s
FAILED (failures=1)
```
The six earlier-day sends all saw count 6, and each "could not be read" send shared its count with the next name's
bar read (`14, 14, 15, 15, ...`). The call-sequence assertion passed, so the scenario was right.

### GREEN and covering runs (after the fix)
- `safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k FollowUps -v`: 9 tests `ok`,
  `Ran 9 tests in 0.310s` / `OK`.
- `safe python3 -m unittest discover -s tests -p 'test_news_supervised.py'` three times in a row: `Ran 88 tests in
  2.004s OK`, `2.454s OK`, `2.308s OK`. Before the expectation edit, this file failed only in the ruled test, with
  `(['stops', 'stops', 'stops', 'stops'], '2026-11-10T14:45:00+00:00') != (['stops', 'stops', 'stops'], ...)`.
- `safe python3 -m unittest discover -s tests -p 'test_supervise.py'` (the file that starts processes), three times in
  a row: `Ran 19 tests in 37.197s OK`, `36.747s OK`, `34.326s OK`. No engine child was left (`pgrep`).
- The other files that drive the catch-up, once each: `test_news_guards.py` `Ran 113 tests ... OK`,
  `test_loss_protocol_pins.py` `Ran 51 tests ... OK`, `test_news_inputs.py` `Ran 71 tests ... OK`.
- Planted defects, one at a time, on a scratch copy (`t8a-fix1/copy`, never the clone), against the whole file:
  - Without the beat in `_catchup_unread`: 2 failures (the new test and the ruled test).
  - Without the beat in `_earlier_days_unread`: 1 failure (the new test).
- At any hour: the whole file was run on the scratch copy, which is byte-identical to the clone's files, with the
  clocks of the engine and the tests moved (`t8a/shifted_inproc.py`, read before use). It printed `Ran 88 tests ... OK`
  at New York Wednesday 17:00, 03:00, 09:31 and 23:58, on Saturday 2026-11-14 12:00 (no session), and on 2026-11-27
  (early close) at 12:30 and 13:30. I added and changed no process test.

### Whole suite (before the commit, in the gate clone)
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`, wall time 98 s:
```
Ran 659 tests in 97.566s

OK
```
That is 658 + 1. The whole-suite run and the three runs of each file used the working tree just before the commit. The
commit holds exactly that tree: the two files, unchanged after the runs.

### Left unfixed
None. The review's Important 2 (serial priming) and its minor items were not on this round's list, and I did not
touch them.
