# Task 6 report - a sale is said at once

**Status: DONE_WITH_CONCERNS.** Two commits on `supervisor-build` in the gate clone, on top of `67096b47`:

- `fb9881e1` (`fb9881e1eec9f4cd9fd39b05fdaef2e6b32ac8d6`)
  `feat(ai-trader): a stop look's lines go out right after the look, and an unsent trade is reported at the next start`
  (the brief's message; 3 files, +339 -10)
- `ce6abbe3` (`ce6abbe351f198997bcdcf1583686c34500bab61`)
  `fix(ai-trader): the beat after a stop look's own message names the look, not the end of the step before`
  (from my own review of the first commit; 2 files, +16 -3)

Start state checked first: HEAD `67096b47eea6ba5271eedeb96cf55ed0b48dbe4a`, branch `supervisor-build`, tree clean.
After the last commit `git status --short` prints nothing. No trailer, no attribution line, nothing pushed, no git
setting changed, no subagent, no existing test edited.

Everything the brief asks for is built and its five tests pass under their names with the assertions the brief gives.
The concerns are readings where the brief's sentences and its own rule ("`told_through` never passes a row whose line
nobody got") do not say the same thing, and limits of the design itself. They are at the end.

## What is in the commits

**`aitrader/news_live.py`** (+107 -10)

- `NewsTrader.__init__`: `told_through` (None), `_unsent` ([]), `_late` ([]), `_last_row` (the hash of the journal's
  last row as far as this process has read), `_told_lines` (the places in the running step's lines that a look's own
  message delivered), `_phase` (where the loop is).
- `_trade_line(f)` (module level): the one spelling of `side qty symbol @ price - reason`, for `_log_trade` and the
  late line.
- `_log_trade`: after the journal row and the book save, the hash of the file's last row is read back
  (`journal.read("news_trades.jsonl")[-1]["hash"]`), kept as `_last_row` and appended to `_unsent`. A read that fails
  leaves a `news_errors.jsonl` row (`where` "trade_hash") and never costs the sale.
- `_say(lines) -> bool`: the step's message as it was built before (`"AI Trader - חדשות"`, the lines, the book line
  ending `. כסף נייר`, "high"); whether a channel took it. Used by the look and by the closing message, so both end
  with the paper-money words (Task 5's deferred note).
- `_look_at_stops`: when the look added lines, after the look, its save and its beat: `_say(<the look's own lines>)`.
  A channel took it: those places go into `_told_lines` and `_mark_told(<the rows this look appended>)`. A send that
  raises leaves a row (`where` "look_alert"); either way the lines stay for the closing message. The look states its
  phase ("stops") when it starts (second commit).
- `step()`: the closing message carries the lines that are not in `_told_lines`; none left, no message. A channel
  took it: `_mark_told(<this step's rows still unsent>)`.
- `_mark_told(hashes)`: drops them from `_unsent`; only when `_unsent` is then empty `told_through = _last_row`; then
  `_beat(self._phase)`.
- `say_late()`: with `_late` not empty, one message `"דווח באיחור: " + " | ".join(...) + ". כסף נייר"`, same title and
  priority. A channel took it: `_mark_told(<their hashes>)` and `_late` is emptied. It never raises (`where` "late_line").
- `adopt_previous`: a fourth block, guarded like the others. `told_through` from `prev` when it has the key; today's
  rows (New York date) after that row are `_late`, their hashes `_unsent`; all of today's rows when it is null. No
  heartbeat, no key, or a mark that is no row of the journal: the journal's last row, nothing late.
- `_beat`: writes `told_through`, keeps the phase it was called with.
- `_run`: `nt.say_late()` after E2 and E1, right before the loop (Task 7 moves the three together).

**`tests/test_news_supervised.py`** (+245): `trade()` helper, `SaidAtOnce` (the brief's four), `WhoWasTold` (thirteen
more). **`tests/test_supervise.py`** (+10): `SaidBeforeTheKill` (the brief's one).

## TDD evidence

Every command ran from `<clone>/ai-trader` as
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests ...`.
Outputs are kept in `<SCRATCH>/t6/out/`.

**RED, `-p 'test_news_supervised.py' -k SaidAtOnce -v`** (the brief's expected failure: nothing was sent before the scorer):

```
test_a_look_whose_send_failed_is_in_the_closing_message_and_told_only_then ... FAIL
test_a_sale_at_the_top_of_a_step_is_sent_before_the_scorer_and_only_once ... FAIL
test_a_sale_nobody_got_is_not_passed_by_a_later_message_and_is_said_once_at_the_next_start ... ERROR
test_with_no_heartbeat_nothing_is_said_late ... ERROR
    self.assertTrue(any("SELL 10 BBB" in b for b in at_scorer[0]))
AssertionError: False is not true
AssertionError: Lists differ: [] != [(True, None), (True, None)]
AttributeError: 'NewsTrader' object has no attribute '_mark_told'
AttributeError: 'NewsTrader' object has no attribute 'say_late'
Ran 4 tests in 0.030s
FAILED (failures=2, errors=2)
```

**RED, `-p 'test_supervise.py' -k SaidBeforeTheKill -v`** (the sale's line was owed to a closing message that a scorer
which never returns never lets happen):

```
test_the_line_of_a_sale_is_out_before_a_scorer_that_never_returns_and_a_kill_9 ... FAIL
    self.assertEqual(sum("SELL 10 BBB" in r["body"] for r in self.sent_rows()), 1)
AssertionError: 0 != 1
Ran 1 test in 0.504s
FAILED (failures=1)
```

`-k WhoWasTold` before the code (nine of today's thirteen): `Ran 9 tests ... FAILED (failures=4, errors=5)`. The
other four came during the review; each has its RED: three in the planted-defect run below, and
`test_the_beat_after_a_looks_message_says_stops_also_when_the_look_asked_no_quote` failed on the first commit with
`AssertionError: Tuples differ: ([True], 'idle', 1) != ([True], 'stops', 0)`.

**GREEN** (on the files as committed):

```
-p 'test_news_supervised.py' -k SaidAtOnce -v      Ran 4 tests in 0.013s    OK   (all four "... ok")
-p 'test_supervise.py' -k SaidBeforeTheKill -v     Ran 1 test in 0.359s     OK
-p 'test_news_supervised.py' -k SaidAtOnce -k WhoWasTold -v    Ran 17 tests in 0.291s   OK
```

The brief's "5 tests, OK".

**Three times in a row.** `tests/test_supervise.py` (the file that starts processes), whole, on the final engine
code: `Ran 15 tests in 30.046s OK`, `28.665s OK`, `31.617s OK`. `tests/test_news_supervised.py`:
`Ran 57 tests in 1.171s OK`, `1.102s OK`, `1.203s OK`. Five lines of output each: the new tests print nothing.
No engine child and no `sleep 60` was left after any run.

**At any hour** (the 11:10 ruling). The real clock was between 09:44 and 10:26 New York.
- In-process: `shifted_inproc.py` (the earlier dispatches' script, read before use; a copy is in `t6/`), which
  moves every clock the engine and the tests ask. The whole module, `OK` each time: 17:00, 11:00, 09:31, 23:58 and
  03:00 New York today, 00:01 tomorrow, Saturday 2026-11-14 12:00 (no session), and the early close of 2026-11-27 at
  12:30 and 13:30. The new tests take "today" from the same clock the engine reads, and the one test that needs a
  session passes its own fixed time into the look.
- The process test: `evening_procs.py 17:00 SaidBeforeTheKill` and `... 03:00 ...` (Task 3's script): the engine
  process answers the clock as 17:00, then 03:00, New York. `Ran 1 test ... OK` both times,
  `engine processes started at a pretended 2026-11-11T17:00:00 New York: 1`, `their --until: ['23:59']`. The test
  starts its engine through `Procs.start_engine`, which adds `--until 23:59`; the scenario's session is "open"
  whatever the hour, and the sale needs only the price under the stop.

**Planted defects** (`t6/mutate.py`, on a scratch copy of the tracked files, never in the clone; no `claude` on
`PATH`, every proxy a dead local port, 120 s per run). 54 defects, one at a time, in `news_live.py`; each run is
`test_news_supervised.py` and `SaidWhateverHappens`, and for some `SaidBeforeTheKill` or `BrokenChainFailsClosed`.
On the committed code: `mutants 54 survivors: 0`. Examples: the look sends nothing, or every line of the step so
far, or before its save, or before its beat; the closing message repeats what the look delivered, or marks every
unsent row, or marks although nobody took it; the mark moves at any delivered message, or to the last row told and
not the journal's last; no beat after a delivered message; a trade row not counted as owed; the first row read back;
no heartbeat owing all of today's rows; a mark the journal does not hold kept; the marked row itself owed; rows of
another day owed; the late line said twice by one process, marked although nobody took it, urgent, without its
last words; a late line or a look's send that raises costing the start or the step; a start that says nothing late.
The first run left one survivor that was a defect changing nothing (my mistake in the list). After the second
commit one real survivor showed: nothing pinned that `_beat` keeps its phase once the look states its own. One
assertion (the beat after a closing message says "idle") now does.

## Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, before each commit, on the files as committed.

Before `fb9881e1`, wall time 110 s:

```
Ran 623 tests in 109.134s

OK
```

Before `ce6abbe3`, wall time 97 s (the last three lines of the final run):

```
Ran 624 tests in 96.009s

OK
```

624 = 606 + 18. The `[news] ...` lines above the dashes are those of older tests. `SaidWhateverHappens` passes
unchanged. After the runs only the three paths were changed: nothing under `state/`, `logs/`, `reports/` or
`research/`.

The first whole-suite run, before the commit, had one error and it changed the code, not the test:
`test_audit_fixes.BrokenChainFailsClosed.test_news_engine_stops_on_its_own_broken_chain` builds a trader with
`NewsTrader.__new__` (no `__init__`) and expects `step()` to raise `ChainBroken`. `step()` read `self._unsent`
before the chain check. It now reads it with `getattr` (a comment says why). That test is about the engine
stopping; I did not touch it.

## Files changed

`ai-trader/aitrader/news_live.py`, `ai-trader/tests/test_news_supervised.py`, `ai-trader/tests/test_supervise.py`.
The brief's list, nothing else.

## Self-review (`git diff 67096b47..HEAD`, against the brief line by line)

Found and fixed:

1. **The beat after a look's message could say "idle" in the middle of a step** (second commit). `_mark_told` beats
   "with the current phase", which I kept as the phase of the last beat. A look with nothing held asks no quote and
   writes no beat, so after a line such as "exit request for ZZZ dropped: not held" the beat repeated "idle" and
   worked out `headlines_seen`, `stops_checked_at` and `buys_blocked` again, which `_beat` says only the end of a
   step does. A look now sets the phase to "stops" when it starts. One test (RED quoted above).
2. Nothing pinned that the look's message goes out after its save and its beat: one test, on a fixed clock, with a
   stop mark found by the catch-up (a sale saves the book by itself, so only a mark tells the order).
3. Nothing pinned that a step's closing message leaves the rows of the run before alone, nor that the told lines
   are forgotten with their step, nor that a late line which cannot be sent does not cost the start: three tests.
4. A late-line row with no `reason` (a row written by hand; the tests of Task 5 write such rows) would have raised
   and the whole late line would have failed at every start of that day. A missing field is said as "?".
5. `adopt_previous` with no heartbeat on a journal whose last row has no hash would have read "null" and owed all
   of today's rows. The no-key case now owes nothing whatever the last row is.
6. The whole journal is read at each trade for one hash. Measured in a temporary directory: 0.8 ms at 100 rows,
   15 ms at 2,000, 168 ms at 20,000. The live file has two rows after two days. A `ponytail:` comment names the
   ceiling and the way out (read the last line only).
7. An unused name in a test (found by `ruff --select F`), one line over the file's usual width.

Checked and left:

8. Every bullet of the brief has its code and its test (the list above). The late line's body, title and priority
   equal the brief's, character for character (asserted whole, twice).
9. No trade rule changes. A sale is still made, journaled and saved before anything is sent; the look's message
   comes after every stop was looked at, after the catch-up and after the second look of "sell" mode. What does
   change is named by the brief: a message inside the step. It can hold what follows the look (the poll, the next
   batch, a buy after its second check, which is bought at a fresh quote as before) for as long as a send takes,
   15 s a channel at most, and only when that look had something to say.
10. No number was added to the logic. Every new send passes the priority positionally.
11. No test reaches the network, the model, the live state or the phone. Every new step in a test goes through the
    module's `step()` helper or `_Starts.start()`, which replace the poll (see departure 9).
12. Review Focus 1 and 4, for this task: a heartbeat with no mark, with a null mark, with a mark of another day,
    with a mark the journal does not hold, with a mark that is no hash at all; a journal with a torn line and a
    line that is no row; a journal that cannot be read. One table test.
13. Task 7's brief was read against this code: its second test (two unsent rows of today, a heartbeat with a null
    mark: E2, E1 and one late line) and its fourth (a sale of the first look is "said" before git: one line sent)
    get from Task 6 what they expect.

## Departures from the brief, and readings

1. **A row is in `_unsent` from the moment it is appended**, not from a failed send. The brief says "No channel
   took it: the rows join `_unsent`". Read literally, a buy made while scoring is in no list until the closing
   message fails, so a look that sells right after it and is delivered would move the mark past the buy; if the
   closing message then fails, the buy is never said. That breaks the brief's own rule and its definition of
   `_unsent` ("the rows whose line no channel has taken yet"). `_log_trade` therefore adds the hash at once. The
   brief's tests cannot tell the two apart; `test_a_delivered_look_does_not_move_the_mark_past_a_buy_whose_line_is_still_to_come` does.
2. **"the last row's hash" in `_mark_told` is the journal's last row** as this process knows it (`_last_row`), not
   the last of `hashes`. Otherwise a late line said after the first look (Task 7's order) would put the mark on the
   late row, behind the sale the look already told, and the next start would say that sale again.
3. **A mark that is no row of the journal becomes the journal's last row** at `adopt_previous` (the brief: the mark
   is `prev["told_through"]`, and "none [is late] when the hash is not in the file"). Nothing is said late, as the
   brief says. But with the foreign mark kept, a trade of this process whose line nobody took would again find
   "not in the file" at the next start and never be said. The same for a mark that is no hash at all (a number, a list).
4. **The look's message goes out after the look's beat too**, not only "after the look and its save": the beat is a
   file write that carries the look's stamps (ruling of 12:19), the send can take 15 s a channel.
5. **`step()` reads `_unsent` with `getattr`** (the existing test above). No existing test was edited.
6. **Names the brief does not give**: `_say`, `_trade_line`, `_last_row`, `_told_lines`, `_phase`; the `where` of
   three error rows ("look_alert", "trade_hash", "late_line"); "?" for a field a late row lacks.
7. **`say_late` empties `_late` once a channel took the line**, so a second call in the same process says nothing.
   A line nobody took stays, and its rows stay owed.
8. **A look states its phase** (second commit; self-review 1). The brief names `_beat` and `_look_at_stops`, not this.
9. **The tests call the module's `step(nt, ...)` helper where the brief's fragments write `self.nt.step()`.**
   `_Engine` does not replace the feeds: the bare call would poll Yahoo for real. The helper replaces the poll and
   the scorer and then calls `nt.step()`; the stand-ins the comments describe are written in each test. Test 4's
   row is written with the new `trade()` helper.
10. **18 tests, not 5.** `WhoWasTold` holds thirteen: what each of a step's two messages carries and how it ends;
    a delivered look and an earlier buy; a look's send that raises; the order save, beat, message; the mark in the
    file at once; the phase of the beat after a look's message; a hash that cannot be read back; the start table;
    the late line word for word, until taken and never again; a sale of this process not in the late line; a step's
    closing message and the rows of the run before; a late line that cannot be sent; a start through `_run`, twice.
11. **Two commits**: the brief's, and the fix my review found.
12. **Where `say_late()` stands in `_run`**: after E2 and E1, before the loop. The brief says "after `adopt_previous`".

## Concerns

1. **Said at least once, not exactly once.** The mark is one hash. After a line that no channel took, it stays
   where it is for the rest of that process, so the next start of that day says late every trade after it, also
   those whose own lines were delivered. And a kill between a delivered message and the beat that follows it says
   that line once more at the next start. This is the brief's design (a mark, not a list); the other choice loses lines.
2. **For Task 7**: a line of a look made outside a step (the first look of a start) that no channel took is not
   tried again by the first step. Its rows stay owed and are said at the next start of the day.
3. **The late line has no size limit.** ntfy takes 4,096 bytes; a row is about 100 to 350 bytes. A late line of a
   dozen trades could be refused at every start of that day and then dropped with the day. The step's own message
   has had the same exposure all along.
4. **No beat during a send.** The look's message is one more network call of up to 15 s a channel with no beat
   before it returns (Task 4's deferred note on sends). The beat right after a delivered one is new.
5. **A heartbeat written by the code of Tasks 4 and 5 has `"told_through": null`.** By the brief's rule a start
   with this code after such a file says all of today's rows late. The live engine gets Tasks 3 to 8 in one landing
   and its present heartbeat has no such key (nothing is said again), so this is a development-only case.
6. A quiet-hours answer of `notify.send` (`["queued"]`) counts as "a channel took it" (as in Task 5). The stock
   book has no quiet hours.
7. A row whose hash could not be read back is not counted: the mark can pass it. Its line still goes out the usual way.
8. `journal.read` prints `[journal] skipped unreadable line` once more per trade and per start when the journal
   holds an old torn line.
9. The commits' author name is the clone's configured git identity, as on every earlier commit of this branch.
10. The spec's wording of 5.6 ("after a delivered send the heartbeat holds the hash of the last row") is not what
    is built; the brief says why. The spec file was not touched.

Scratch files, none in the clone: `<SCRATCH>/t6/`
(`out/` with every output quoted above, `mutate.py`, `shifted_inproc.py`, `evening_procs.py`, `evening_child.py`,
`copy/` the scratch copy the planted defects ran on).
