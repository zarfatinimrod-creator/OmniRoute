# The loss-protocol pins: what was integrated, and how every disagreement was decided

Written on the evening of 2026-11-10 (New York) in a scratch directory, by the session that integrated three reviews of
the first 44 test methods. Each claim names the command or the file it rests on. Checked again on 2026-11-11 at 03:35
New York on the branch tip: the pins file alone (51 tests OK), the whole suite (442 OK) and all 420 mutants
(412 killed, 8 left: K14, K22, K27, PM64, PM75, X02, X03, BY1).

What is kept in this folder:
- `../../tests/test_loss_protocol_pins.py` is the file the notes call "the pins file".
- `waiting.diff`: what has to change in `tests/test_news_guards.py` and `tests/test_postmortem.py` when they are free
  (`patch -p1` from `ai-trader/`, against those files as they stood at commit e6a82895).
- `fold.py`: builds the same merged form from the pins file by class name (use it when `waiting.diff` no longer applies).
- `methods.json`: one row per method: class, name, the mutants it is there to kill, whose version it is.
- `mutation/harness.py` and `mutation/mutants.py`: the mutation harness and its 420 mutants. Every mutant is anchored
  on a line number of the code at e6a82895, so they need new anchors after any change to `news_live.py`,
  `postmortem.py` or `__main__.py`. The harness expects a copy of the project next to it (`PRISTINE`) and writes
  only beside itself; it never touches the checkout.
- `tools/`: the clock tools (`at_clock.py` runs tests at a moved clock; `boundary_enum.py` puts a day boundary between
  every two clock reads of a test) and `boundary_enum_merged_two_files.txt`, the list of the fourteen older methods
  that fail when a day turns inside them.

Paths below that start with `pins/` are the scratch paths of that evening. `pins/real_pins` and `pins/merged` were
not kept: the first is this checkout, the second is what `fold.py` builds.

## In short

- The three reviews are integrated into one file of 51 test methods that touches no claimed file. It passes alone and
  with the whole suite (442 tests), in the evening after 16:05 New York, ten times in a row, at 25 moved clock
  instants, in 17 shuffled or reversed orders, and at about 175 times slower on a starved machine.
- Every method fails on the mutants it is there to kill. With the file added, 412 of the 420 mutants are killed and
  the 8 left are the ones the second opinion judged equivalent or harmless.
- Where the flakiness review (A) and the honesty review (B) both rewrote a method, one version was written: eight
  methods, section 3.
- No test pins a BUY on a day-move the engine cannot read any more. The code still makes that buy; that question is
  open and belongs to the session that holds `news_live.py` (section 4 and section 8, item 1).
- Found on the way, by none of the three reviews: six of the methods failed when a day turned inside them. Fixed here.
  Fourteen older methods in the landed files have the same fault; listed, not changed (section 8, item 6).
- What had to change in the two claimed test files is in `waiting.diff` and waits for the claim.

## 1. What is delivered

| File | What it is |
|---|---|
| `pins/real_pins/ai-trader` | A copy of the landed project plus ONE new file, `tests/test_loss_protocol_pins.py` (51 methods in 14 classes). Nothing else differs. |
| `pins/merged/ai-trader` | The same 51 methods folded into their classes in `tests/test_news_guards.py` (+46) and `tests/test_postmortem.py` (+5), with the reviewers' changes to what those two files already had. |
| `pins/waiting.diff` | The unified diff from the landed two files to the merged two files. It is what has to wait for the other session's claim. `patch -p1` from `ai-trader/`. |
| `pins/methods.json` | One row per method: class, name, the mutants it is there to kill (`kills`), whose version it is, a note, and the other mutants it fails on in the full run. |
| `pins/INTEGRATION.md` | This file. |
| `pins/work/` | The tools and outputs behind the numbers below (`fold.py` builds the merged form from the pins file). |

The merged form is not written by hand: `pins/work/fold.py` takes each class body of the pins file, appends it to the
class it extends, and then makes the edits of section 6. So the two forms hold the same 51 method bodies, text for text.

In the pins file a class statement reads `class Hold_(_ChecksOver, g.Hold)`: the class it extends is the last base, and
`_ChecksOver` is the file's own wait for background threads (section 4). `fold.py` reads it that way; the older
`scratchpad/merge_tests.py` reads the first base and will not work on this file.

## 2. From 44 methods to 51

- The mutation run wrote 44 methods (39 + 5). Read from `scratchpad/adopt2/ai-trader/tests/test_loss_protocol_pins.py`.
- One is dropped (B's S4, section 4).
- Eight are added (C's, section 5).
- Three have a new name, because B's replacement asserts something else than the old name said:
  - `test_a_step_keeps_whether_its_first_look_at_the_stops_ran` is now
    `test_what_a_failing_engine_says_of_the_stops_is_what_its_own_steps_saw`;
  - `test_a_move_that_cannot_be_compared_changes_nothing_on_trial_and_refuses_when_enforced` is now
    `test_a_move_that_cannot_be_compared_never_fails_the_batch_and_is_no_buy_when_enforced`;
  - `test_the_heartbeat_has_no_stamp_while_a_held_name_was_never_looked_at` is now
    `test_the_heartbeat_has_no_stamp_while_a_held_name_has_had_no_quote_and_no_bars_read`.

| Class | Methods | Of which new (C) |
|---|---|---|
| `Hold_` | 10 | 1 (M24) |
| `OnTrial_` | 4 | - |
| `SecondCheck_` | 6 | 1 (DT5) |
| `StopCooldown_` | 1 | - |
| `CatchUpStop_` | 9 | 5 (LS3 x2, U27, A02, U03) |
| `StopsFirst_` | 1 | - |
| `Bars_` | 2 | 1 (A02) |
| `OneEngine_` | 1 | - |
| `PauseSaidAtOnce_` | 1 | - |
| `NothingSlowBeforeASale_` | 3 | - |
| `SaidWhateverHappens_` | 7 | - |
| `QueueAndRecord_` | 1 | - |
| `Ledger_` | 4 | - |
| `Cli_` | 1 | - |

Whose version each method is (`methods.json`, field `version`): 15 as first written, 17 B's, 1 A's chosen over B's,
1 B's chosen over A's, 1 where A and B made the same change, 5 where A's and B's were merged, 2 B's with one thing
changed by the integrator, 8 C's (6 with at most a small change, 2 reworked), 1 first-written method changed by the
integrator alone.

## 3. Where A and B both rewrote a method

Applying A's diff and then B's leaves 7 of B's 18 hunks rejected (`scratchpad/adopt3/ai-trader/tests/test_news_guards.py.rej`).
Those 7 hunks hold 12 methods. Seven of the 12 were rewritten by both reviewers; five were changed by B alone and were
rejected only because they sit next to a method A changed (they are in the next list). One more method was changed by
both without a rejected hunk. That makes eight.

The order of importance used: (1) it can only fail on a real regression; (2) it still fails on its own mutants;
(3) it reads what the owner or a later session can see; (4) its name says what it asserts.

| Method | A's version | B's version | What is in the file, and why |
|---|---|---|---|
| `OneEngine_.test_while_an_engine_runs_nobody_else_can_take_the_book_not_even_to_share_it` | The stubbed step raises `ChainBroken` after it tried the lock; end time `"24:00"`; `code_stamp` and `load_config` stubbed. | One line: `run("24:00", 0.001, prime=False)`. The loop still ends on a 60 ms budget and git is still started. | **A's.** The rule for a loop's end is a step that raises `ChainBroken` or `"24:00"`, never a small budget, and no real process. |
| `NothingSlowBeforeASale_.test_the_engine_says_which_code_it_started_on` | The real step, then `ChainBroken`; `_run("24:00", 1, False)`. | `run("24:00", 0.0005, prime=False)`: through the public door, but ended by a 30 ms budget. | **Both:** A's end of the loop, B's public door (`run`, not `_run`). |
| `SaidWhateverHappens_.test_the_loop_prints_what_a_failed_step_had_already_done` | A stubbed step that sets `last_events` by hand, `ChainBroken` at the second round; asserts the sentence `cycle error: RuntimeError`. | The real step (a held name under its stop, the feeds fail); asserts one word and the SELL row; ended by a 30 ms budget. | **Both:** B's real step and B's assertions, A's end of the loop (`ChainBroken` at the second round), through `run`. A stubbed step shows only that the loop prints a list; the real one shows that a failed step leaves it. |
| `NothingSlowBeforeASale_.test_a_step_does_not_wait_for_a_trial_check_that_has_not_answered` | No clock: it records the wait the step gives `drain_trial` (`[0.0]`). Keeps one line on the private `_trial`. | Keeps the 0.8 s wall-clock bound; drops the `_trial` line. | **Both:** A's method without the `_trial` line. "Still out" is read from the record: no `second_check` row yet. |
| `SaidWhateverHappens_.test_the_wait_for_answers_still_out_is_one_wait_in_all_not_one_for_each` | No real wait: stand-ins for the three answers use up the time they are given on a clock the test owns; asserts the sum is 0.4. Ends on `_trial == []`. | Keeps the 1.0 s wall-clock bound; reads the record (`news_checks.jsonl`) instead of `_trial`. | **Both:** A's clock, B's record at both ends. The private boxes of `_trial` are still swapped: only they carry the wait, and property 1 and 2 come before property 3. |
| `SaidWhateverHappens_.test_trial_checks_wait_their_turn_when_config_says_one_at_a_time` | An event instead of a 5 s poll; asks the pool itself (`_trial_gate.acquire(blocking=False)` is refused); keeps `asked == {"AAA"}` and the assertion on the shipped `verify_parallel`. | Sets `verify_parallel` itself; `len(set(asked)) == 1` (either headline may go first); ends on the record; keeps the poll. | **Both:** A's event and A's question to the pool (the only sign of VP1 that does not rest on a sleep; it is a private attribute, kept for property 2), B's three points. `verify_calls` is set in the test as well. |
| `CatchUpStop_.test_in_the_selling_mode_a_breach_found_by_a_look_is_sold_by_that_same_look` | The fixture's own time passed to the look; asserts the look returns True. | The same change, without the return value. | **B's shorter form.** The return value is not needed for the kills (LS6, LS9, LS10 all fail without it). |
| `StopsFirst_.test_after_a_stalled_step_the_gap_of_a_name_with_a_live_quote_is_still_read` | A fixed time; `_stops_checked_at` and `_covered` set by hand; bars come back empty. | Three looks of the engine at fixed times; the engine sets its own stamps; every minute bar is there; asserts no urgent alert. | **B's.** Both are free of the wall clock. A's fixture makes the engine send the urgent "cannot read the prices" alert and never looks at it (run in a copy, `pins/work/a_fixed`: it passes with one urgent alert sent; B's sends none); B's reads nothing private. |

Checked for each of the eight, by hand (`pins/work/byhand.py`: the mutant goes into a throwaway copy, the one method
is run, the mutant is taken out, the method is run again). From `pins/work/byhand_pins_v4.txt`
(72 pairs of mutant and method over the 51 methods: `pairs 72 | not as expected: 0`):

- RL2: `Lists differ: ['taken', 'refused'] != ['refused', 'refused']`; without it OK.
- RN1: `TypeError: 'NoneType' object is not subscriptable`; without it OK.
- ST4: `'SELL 10 BBB' not found in '[news] engine started on commit x, guards enforce\n[news] cycle error: RuntimeError: feeds down\n...'`; without it OK.
- K29: `Lists differ: [60] != [0.0]`. K30: `[1.0] != [0.0]`; without them OK.
- DT2: `1.2000000000000002 != 0.4 within 7 places`; without it OK.
- VP1: `True is not false`; without it OK.
- LS6, LS9, LS10: the position is still held (`{'AAA': {...}} != {}`); without them OK.
- LS9 (stalled step): `Lists differ: [] != ['10:00']`; without it OK.

`test_trial_checks_wait_their_turn...` was listed for CJ20, DT2 and VP1. It now kills VP1 only, on purpose: CJ20
(config 1 to 4) is killed by the fallbacks test, and its "kill" of DT2 was a thread of the neighbouring test
answering into it (A's B6 and B's S7 both say so; DT2 is killed by the one-wait method above).

## 4. The other decisions

**B's blocking B2 is kept as binding.** No method pins that the engine BUYS on a day-move it cannot read. The method
is B's replacement: on trial the batch must come back (nothing is asserted about a buy); enforced, it is no buy.
It fails on Y42 (`{'AAA': {'qty': 47, ...}} != {}`) and passes without it.
**Open, and not for this file:** the code question. `_buy` reads only `None` as "not known". B's probe, run again
here on the landed code (`pins/work/probe_move.txt`): on trial the moves `'5.8'`, `'n/a'`, NaN, `[5.8]` and `True` are
all bought (`bought=True rows=[('', 'bought')]`); enforced, NaN and `True` are still bought and the others are refused
as `no_chase`; only `None` gives `('unknown_move', 'refused')`. The law says no buy when today's move is not known
(`config.json`, `news._note_guards`: `require_known_move` "is always enforced"). A move that is not a finite number
should be read as not known. That change belongs in `aitrader/news_live.py`, which the other session holds; it goes
through rule 4, and into `state/backlog.md` by a session that may write there. The live loop cannot produce such a
move today (`live_price` returns a rounded number or `None`; read, not run).

**B's S4 is dropped**, as B proposed: `test_on_trial_a_quote_that_stopped_being_live_after_the_score_does_not_cancel_the_buy`.
Its one mutant, H04, is still killed by two methods of the pins file, checked by hand:
`OnTrial_.test_on_trial_the_buy_is_made_at_the_quote_the_scorer_saw_and_no_newer_quote_is_asked_for`
(`'AAA' unexpectedly found in ['SPY', 'AAA']`) and
`SecondCheck_.test_with_the_check_switched_off_an_enforced_buy_is_made_at_the_scored_quote`
(`104.10399999999998 != 100.1 within 6 places`).

**B's other replacements are taken as B wrote them**, with these exceptions:

- *The last two of B's S12* (`verify` survives a hold it cannot judge; a key that fits two fills) were not applied or
  run by B. They are applied here and checked: M08 gives `RuntimeError: boom`, PM14 gives `ValueError not raised`.
- *S2, what a failing engine says of the stops.* B ended each run by a two-minute budget on a clock that mixes the real
  time with a skew. Here each run is three rounds of the real step and then `ChainBroken`, through `run`. T13 and X21
  still fail on it (the alert says the wrong thing about the stops in each case).
- *S3, the heartbeat with no stamp.* B read the wall clock and patched the calendar so that the session "opened this
  minute". Here every look of the step is given a fixed 09:31 on 2026-11-10 (the real calendar, one minute after the
  bell), by wrapping `_look_at_stops`, which already takes `now=`. HB3 still fails on it
  (`'2026-11-10T14:31:00+00:00' is not None`). B's version, run in a copy (`pins/work/b_fixed`) with a boundary at
  every position between its clock reads, fails when the spring clock change falls inside it: `clocks forward
  (2027-03-14 02:00): fails at 6 of 14 positions ... '2027-03-14T07:00:00.500000+00:00' is not None`. It passed at the
  other ten boundaries. The cause (read): it needs the step to run within a few minutes of the test's own clock read.
- *S13, a hold holds back no kind of sale.* B's added line is in. The fixture's entry date is a fixed date instead of
  today's (see also section 5 on day boundaries).

**A's findings on threads (B5, B6)** are not answered inside the methods. A's fix is a wait in `_Engine.setUp` and
`tearDown`, which this file may not touch. So the pins file carries its own wait: `_ChecksOver`, first in the bases
of every class, joins every live thread named `trial-check` before a test starts and before it ends. When the methods
are folded in, the wait is A's, in the parents (section 6).

## 5. C's eight methods, and what the integrator found on the way

All eight are in, each fails on its own mutant and passes without it (`pins/work/byhand_pins_v4.txt`): M24
`SystemExit: 1`; LS3 `{'AAA': ...} != {}` and `2 != 1`; A02 `KeyError: 'stop_breach'` and an extra `'09:37:25'` row;
U27 `'AAA' not found in {}`; U03 the bars were read at 140 seconds; DT5 below.

Changes to C's text:

- **DT5 no longer waits.** C's method waited 5 seconds of real time behind a 9-second bound. The new one starts calls
  that never answer and gives the engine a clock the test owns; it asserts that every wait for a call has an end and
  that the three together get less than two timeouts. With DT5: `False is not true : [None, None, None]`; without: OK.
  It runs in milliseconds. The kill is kept; what is no longer shown is a real thread being abandoned after 5 real
  seconds. The numbers it rests on (two looks, the rescore, 60 seconds) are set in the test.
- **U03** does not set the private `_stops_checked_at` (it passes `last=` to `catch_up_stops`) and does not assert the
  shipped 90 and 120: it sets the gap and the minimum itself.
- **U27** lost its line on the private `_unseen_lows`. The position still held and no breach mark say the same.
- **The two LS3 methods** got one day for both engines (next point).

**Six methods failed when a day turned inside them.** Not found by A, B or C; found by putting a clock boundary at
every point between two clock reads of every test (`pins/work/boundary_enum.py`). Before the fix
(`pins/work/boundary_enum_pins_v1.txt`: 6,452 runs, 11 boundaries):

- `StopCooldown_.test_the_cooldown_is_one_session...` at New York midnight: 17 of 21 positions. It read today's date
  itself and the engine read it again. Shown also on a ticking clock: of 8 single runs started in the last 30 ms
  before midnight, 4 failed.
- Five methods at UTC midnight (19:00 or 20:00 in New York): the two LS3 methods, `test_a_price_exactly_at_the_stop...`,
  `test_in_the_selling_mode...` and `Hold_.test_a_hold_holds_back_no_kind_of_sale`. A breach mark is sold on only while
  it is "found today", by the UTC date, and the mark and the look that reads it could see two days.

Fixed in the methods: the cooldown method gives the engine a clock that stands at a fixed Tuesday (and sets the
cooldown of one session itself); the five give `journal.now_utc` one fixed day. After the fix, on the delivered file
(`pins/work/boundary_enum_pins_v4.txt`): `runs 6057 | (test, boundary) pairs that fail somewhere: 0`, over New York
midnight, UTC midnight, a minute, both bells, 16:05, both weekend edges, the New Year and both clock changes.
This is a test matter only: a session (09:30 to 16:00 New York) never crosses UTC midnight (read, not run).
All six still fail on their own mutants (S06, S08, S09, S10; Y02, Y05; U07, U08; LS6, LS9, LS10; LS3 twice).

**Numbers a test rests on are set in the test**, where the law does not state them (B's S7, applied to three more
places): `verify_calls` in the turn method, the three numbers of the DT5 method, and `rebuy_cooldown_sessions` in
the cooldown method. A legitimate change of `config.json` then does not fail a test about behaviour.

## 6. What waits for the claim (`waiting.diff`)

The diff has, besides the 51 folded methods:

1. **A's wait for background checks** (A's B5 and B6), as A wrote it: `_background_checks_over()` in
   `tests/test_news_guards.py`, called first in `_Engine.setUp` and `_Engine.tearDown`; and in
   `tests/test_postmortem.py`, `import threading` and the same join at the top of `NewsEngineWaitsForTheReview.tearDown`.
2. **Three old methods with clock defects** (A's S3; A named them and did not write them). Written here:
   - `test_the_alert_for_a_failing_engine_says_the_truth_about_the_stops`: `"23:59"` becomes `"24:00"`.
   - `test_a_gap_is_measured_from_the_look_before_this_step_not_from_its_own_first_look`: a fixed 11:00:30 on
     2026-11-10 given to every look of the step; asserts the bars are asked for once, from 10:50.
   - `test_the_lock_is_free_again_when_the_engine_ends`: `code_stamp` stubbed, so git is not started.

Evidence for the three, on the landed files and on the merged ones, with the clock moved (`pins/work/at_clock.py`):

- Landed, 23:59:10: `FAIL ... test_the_alert_for_a_failing_engine... 0 != 1 : []`. Landed, 00:00:20, 00:05, 03:05 on
  2027-03-14 and the second 01:05 on 2027-11-07: `FAIL ... test_a_gap_is_measured...`. Merged, the same instants:
  `ran 159 failures 0 errors 0` each time.
- The three still fail on exactly the mutants they failed on before: T15; L01, U01, U02, U17, U18, U23, U24, LS1, LS2,
  A06, A08, CJ09, CJ17, CJ19; none (compared between `scratchpad/adopt/results_merged_all.json` and
  `pins/harness_run/results_merged_420_v4.json`).
- Git: with a fake `git` first on PATH, the landed suite started it 3 times; the merged two files start it 0 times.

`waiting.diff` (921 lines, 19 hunks) applied with `patch -p1` to a fresh copy of the two landed files gives the two
merged files byte for byte (`cmp`). It adds 51 `def test_` lines and removes none; 8 lines of the landed files are
replaced, all in the three old methods. It will stop applying when the other session's work changes these two files;
`pins/work/fold.py` rebuilds the merged form from the pins file by class name, and its edits to the old text stop
with an error instead of guessing when the text has moved.

No change that B or C asked for touches a method that already existed; all of theirs are in the 51.

## 7. Runs

All on the delivered files (sha256 in `pins/work/delivered.sha`), after 16:05 New York. The transcript of the first
block is `pins/work/final_transcript.txt` (`pins/work/final_check.sh`). `PYTHONDONTWRITEBYTECODE=1` was set so that no
`__pycache__` is written into the delivered trees.

**The runs asked for** (clock at the start: `Tue Nov 10 17:53:49 EST 2026`; at the end: `17:55:34 EST`)

| Run | Decisive output |
|---|---|
| from `pins/real_pins/ai-trader`: `python3 -m unittest discover -s tests -p "test_loss_protocol_pins.py"` | `Ran 51 tests in 0.460s` `OK` |
| from `pins/real_pins/ai-trader`: `python3 -m unittest discover -s tests` | `Ran 442 tests in 45.968s` `OK` (the landed suite alone, in the same copy before the file was added: `Ran 391 tests in 46.205s` `OK`) |
| from `pins/merged/ai-trader`: `python3 -m unittest discover -s tests` | `Ran 442 tests in 45.267s` `OK` |
| the pins file alone, 10 times in a row | `OK 10 of 10` (0.444 s to 0.480 s each) |
| once with `PATH` led by `scratchpad/mutlens2/shim` | `claude on PATH: .../mutlens2/shim/claude`, `Ran 51 tests in 0.448s` `OK`, `shim directory after: claude`, `no CALLED marker` |
| once with a fake `claude` and a fake `git` first on `PATH` (`pins/shim`) | `OK`; neither left its mark: the pins file starts no process |
| `diff -r /home/user/OmniRoute/ai-trader pins/real_pins/ai-trader -x .cache -x __pycache__` | one line: `Only in .../pins/real_pins/ai-trader/tests: test_loss_protocol_pins.py` |
| `diff -rq /home/user/OmniRoute/ai-trader pins/merged/ai-trader -x .cache -x __pycache__` | two lines: `tests/test_news_guards.py` and `tests/test_postmortem.py` differ |

**After 16:05 New York: evidence for A's B1.** Every run of this work was made between 16:23 and 18:00 New York.
The control, at `17:20:18 EST` on the real clock: the 44 methods as first written, in a copy
(`pins/work/control`), gave `FAIL: test_while_an_engine_runs_nobody_else_can_take_the_book_not_even_to_share_it` ...
`Lists differ: [] != ['refused', 'refused']`, `Ran 44 tests` `FAILED (failures=1)`. The delivered file is green at
the same hour.

**The landed tree moved while this ran.** `pins/work/resync.py`: since the first copy (21:22 UTC) 17 files changed or
appeared, all under `state/`, `logs/`, `reports/` and `research/` (other sessions' operations); `code, tests, config,
rules: none`. Both copies were brought up to date with those 17 files before the runs above. The two diffs were run
once more at `22:59:28 UTC` with the same output; a later write to `state/` by another session will show as one more
line.

**Mutants** (the mutation run's own harness and its 420 mutants, pointed at the delivered trees by
`pins/harness_run/run_harness.py`; nothing is written outside `pins/`)

| Tree and tests | Result |
|---|---|
| `real_pins`, the four landed news and postmortem test files plus the pins file, all 420 | `KILLED 412` / `SURVIVED 8 K14 K22 K27 PM64 X02 X03 PM75 BY1`, no timeout (`run_real_pins_420_v4.log`, 13m56s) |
| of those 412, killed by the pins file and by no landed test file | 68: the 62 of the mutation run and M24, LS3, A02, DT5, U27, U03 |
| `merged`, the four test files, all 420 | `KILLED 412` / `SURVIVED 8`, the same 8, no timeout (`run_merged_420_v4.log`, 12m30s) |
| every one of the 51 methods fails on every mutant it is there to kill | true in both runs (`methods.json` is built from the first; the check on the second printed an empty list) |
| by hand, one mutant and one method at a time | `pairs 72 | not as expected: 0` (`pins/work/byhand_pins_v4.txt`) |

The 8 that survive are the 8 that C judged equivalent or harmless.

**The clock** (`pins/work/at_clock.py` moves the name `datetime` inside the project and test modules; the moved clock
ticks at the real speed)

- The delivered pins file at 25 instants: `ran 51 failures 0 errors 0` at each (`pins/work/at_clock_pins_v4.txt`):
  16:10, 21:30, 23:30 on New Year's Eve, 23:59:10, 00:00:20, 00:05, 00:09, 09:30:10, 15:59:50; runs that cross 16:05, UTC midnight, New York
  midnight and the spring clock change; a Saturday, a Sunday evening, a Monday before the open, Thanksgiving, the
  early-close Friday, three other days, 2028-01-04 (outside the calendar), 03:05 after the spring change, and both
  01:05 of the autumn change.
- The tool sees what A saw. The 44 as first written, same tool: 16:10, 1 failure (A's B1); 23:59:10, 2 failures
  and 1 error (B1 and both of A's B2); 00:00:20, 2 failures (both of A's B3).
- Every position of a boundary between two clock reads: section 5 (`runs 6057`, 0 failing).

**Order and leftovers** (`pins/work/iso.py` shuffles, tags every thread with the test that started it, and compares
21 seams after every test)

- The pins file alone, 13 orders and 4 reversed ones: `'failed': 0, 'left_by_pins': 0, 'seams_left': 0,
  'started_among_strays': 0`.
- The pins file with the two landed parent files, 26 orders (5,538 test runs), twice. First time: 1 failure, an old
  method (`test_news_guards.OnTrial.test_a_low_rescore_is_written_down_and_does_not_stop_the_buy`), started while a
  `trial-check` thread left by another old method
  (`test_postmortem.NewsEngineWaitsForTheReview.test_switch_off_restores_the_old_behaviour`) was alive. Second time:
  0 failures. Both times `'pins_failed': 0, 'left_by_pins': 0`. This is A's B6, still open in the landed files.
- The merged two files, 26 orders and 4 reversed ones: `'failed': 0, 'started_among_strays': 0`.
- A run of the pins file leaves nothing behind: the number of entries in the temp directory was 187,239 before and
  after, and no file in the tree was newer than the pins file after it.

**A starved machine.** 12 busy loops at normal priority, the pins file at `nice 19` in the same shell, several passes
in one process (`pins/work/repeat.py`). An idle pass takes 0.46 s. An earlier version: 6 passes of 83 to 88 s each,
`passes 6 | not green 0`. The delivered file: 3 passes of 80 to 82 s each (about 175 times slower),
`passes 3 | not green 0` (`pins/work/starved_repeat_v4.txt`). The two full mutant runs were also made while other
jobs ran on the machine (load average 6 to 7), with no timeout.

## 8. Left open

Nothing below blocks adding the one new file. Each item names who can close it.

**For the session that holds the claim (code and config)**

1. *An unreadable move is bought.* Section 4. `aitrader/news_live.py`, `_buy`: read a move that is not a finite
   number as not known. No test pins the present behaviour any more.
2. *Two observations of B's on the code*, not re-run here: in the default catch-up mode a held name with no live
   quote and unreadable bars gets a "looked at" stamp in the heartbeat (the owner is told once); and a hold release
   takes effect even when its record cannot be written.
3. *C's sentence for `config.json`, `news._note_guards`:* with 90 and 120 the minimum decides, and the gap is also
   how close to the closing bell the last look of an earlier day must be. And a word in the comment at
   `news_live.py` line 824 that the breach mark is saved there too.
4. *`test_the_fallbacks_in_the_code_say_what_config_says` now reads every key of `DEFAULTS`.* A new key in
   `DEFAULTS` that is not in `config.json` fails it. That is Hard rule 5, but the work being brought in should
   expect it.

**For the session that folds the methods in (the two test files)**

5. *Apply `waiting.diff`, or run `fold.py`*, then delete `tests/test_loss_protocol_pins.py`. Until then the parents'
   own tests can still fail in a shuffled order through threads they leave (seen once in 52 orders, above).
6. *Fourteen old methods fail when a day turns inside them* (`pins/work/boundary_enum_merged_two_files.txt`: New
   York midnight, UTC midnight and 16:05 tried; none of the 51 is among them; thirteen have the two causes of
   section 5). Eleven in `CatchUpStop` at UTC midnight (a breach mark "found today").
   Three at New York midnight: `StopCooldown.test_a_name_stopped_out_today_is_not_bought_back_today` and
   `OnTrial.test_a_name_stopped_out_today_is_bought_back_and_it_is_on_record` (the `_stop_row` helper reads today's
   date, and so does the engine), and `SaidWhateverHappens.test_the_heartbeat_stamp_is_the_oldest_look_among_the_names_still_held`.
   Each window is short: the time between two clock reads inside one test, once a day. No reviewer asked for a
   change here, so none is in `waiting.diff`.
   One day for the whole `CatchUpStop` fixture, in its `setUp`, would close eleven of them.
7. *One test outside the two files still starts git:* `tests/test_audit_fixes.py`, once per run (found with the fake
   `git`). And the `Checker` tests leave an empty `aitrader-scorer` directory in the temp directory (A's S3; no fix
   was written by anyone).
8. *The file is new under `tests/`.* By "One builder at a time" it needs its own line in `BUILD_CLAIMS.md` before it
   is committed; the open claim names `tests/test_news_*.py`, not this file. Not done here: this work was read-only
   on the project.

**Known limits of the pins themselves**

9. *Verified against the landed code only*, as it stood in `/home/user/OmniRoute/ai-trader` on 2026-11-10 (the task
   names it commit e6a82895; no git command was run to check). Its code, test, config and rule files did not change
   during this work. The work being brought in changes `news_live.py` and `__main__.py`: run the file
   on it. The 420 mutants are anchored on the line numbers of the landed code and need new anchors after that.
   B's review lists which backlog items (33 to 44) will touch which methods.
10. *Private names still used*, each because nothing public carries the thing: the boxes of `_trial` (the one-wait
    method), `_trial_gate` (the turn method), `_look_at_stops` and its `now=` (six methods), `_ask_second` (a check
    that raises), `_chart` (a reply in Yahoo's shape), `journal._path` (the lock), and `_quote_is_live` patched to
    True in six methods, as the parents' tests do. Backlog item 44(6), one worker with a queue, will break the
    first two. Gone from the 44: `_early_look`, `_buys_blocked`, `_log_trade`, `_covered`, `_unseen_lows`,
    `_stops_checked_at`, and `_trial` in four of the five methods that read it.
11. *Time that is still there, and why it cannot fail good code.* `time.sleep(0.2)` in the turn method: a second,
    softer sign next to the deterministic one. The 30-second waits on events are deadlines for a test that is
    stuck. The `1` in `run("24:00", 1, ...)` is a backstop against a loop that would never end: the loop is ended by
    `ChainBroken`; under the starvation above a whole pass of 51 methods took 82 s. The parents' helper `_score`
    gives a background check 5 seconds to answer; the 8 landed `OnTrial` methods that call it rest on that too.
12. *What the new DT5 method no longer shows:* a real thread being left behind after five real seconds. It shows
    that every wait is given an end and how long the waits are together.
13. *`"operator exit:"`* is still read by the hold method; backlog item 43 plans to reword it (B's S13).
