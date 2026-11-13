# Task 7 report - the first look after any start

**Status: DONE.** Second dispatch. Committed in the gate clone on `supervisor-build`:
`cbfc4686a20297d35c1fb9fc28848eddf6129efc` - `feat(ai-trader): a new engine process looks at the stops before git,
priming and every line that can wait` (parent `ce6abbe3`). `git status --short` prints nothing after it.

The first attempt's two parked patches were applied to `ce6abbe3` (both applied cleanly), every line was read
against the brief, spec 5.1 / 5.6 and the controller's ruling of 16:05 UTC, and RED, GREEN, the planted defects, the
shifted clocks and the whole suite were all run again by me in this dispatch. I changed nothing in the patches: I
found nothing in them that the brief, the spec or the rulings contradict.

## What is built

`aitrader/news_live.py` (+42 -11):

- `_run`, in the brief's order:
  1. config, `start_checks` (5, 7, 6 end here), the trader;
  2. `adopt_previous(read_heartbeat())`, `_beat("boot")`;
  3. the chain check: `journal.broken_chains(journal.NEWS_CHAINED)`; broken = the existing alert (print + urgent
     send, the same words as `_step`), return 4, no look, no sale;
  4. when `market_open_now()`: `_look_at_stops(events, guarded=True)` (its own lines go out from the look, Task 6);
     then `_beat("stops")`;
  5. E2 (no lock), E1 (mismatch), `say_late()`;
  6. `code_stamp()`, priming, the loop.
  The E2 / E1 / late-line blocks and the stamp and priming blocks were moved, not rewritten.
- A first look that returned false, or raised anything but `ChainBroken`, leaves a `news_errors.jsonl` row with
  `where` "first_look" and the loop starts (its first step looks again).
- The first look's lines are printed to the engine's log in the loop's own format (ratified).
- The beat after a delivered E1 writes the current phase (`nt._beat(nt._phase)`), no longer "boot" (ratified).
- `code_stamp`: both git calls get `env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}`.
- A docstring on `_run` states the order, since Tasks 8 and 11 rely on it. Nothing inside `_step` is touched.

`tests/test_news_supervised.py` (+161 -2): `_WatchedStarts(_Starts)` (the fixture with `calls`), `FirstLook` (the
brief's 7 tests), `TheOrderOfAStart` (6 more), `import subprocess`, one Task 5 expectation ("boot" becomes "stops").

`tests/test_supervise.py` (+4 -3): the ruled option 1, see departures.

## TDD evidence

All commands from `<clone>/ai-trader` through `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`.

**RED** (this dispatch): the patched tests against the engine file of `ce6abbe3` (written back with
`git show HEAD:ai-trader/aitrader/news_live.py`, then the patched file restored; no stash).
`safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k FirstLook -k TheOrderOfAStart`:
`Ran 13 tests in 0.404s`, `FAILED (failures=12)`.

| Test | Failure | Why expected |
|---|---|---|
| `FirstLook.test_the_first_outside_call_of_a_start_is_the_held_names_quote` | `'git' != 'quote:BBB'` | the brief's expected RED: git stood first |
| `...lines_that_can_wait_go_out_after_the_first_look_and_before_git` | `('git', 3, False) != ('quote:BBB', 3, True)` | the three lines went out after git |
| `...after_a_restart_the_catch_up_reads_from_the_last_look_of_the_run_before` | `2 not less than 0` | the added assertion (bars read before git); the brief's own assertion already held - it pins what the new order must keep |
| `...a_name_under_its_stop_is_sold_saved_and_said_before_git` | `[(None, True, 0)] != [('SELL', False, 1)]` | at git nothing was sold, saved or said |
| `...a_broken_chain_at_a_start_sells_nothing_and_returns_4` | `['git', 'send'] != ['send']` | the added assertion; the brief's three already held (the first step found the chain) |
| `...a_first_look_that_fails_is_on_record_and_the_loop_still_starts` | `'first_look' not found in []` | there was no first look |
| `...code_stamp_runs_git_with_optional_locks_off` | `{None}` against `{'0'}` | no `env` was passed |
| `TheOrderOfAStart`, 5 of 6 | e.g. `('boot', 0, None, False) != ('stops', 0, None, True)` | no first look, no "stops" beat, no log line |

The one that passed on the old engine is the word-for-word test of the broken-chain alert: a pin of "the existing
alert" (planted defects M13 and M8 show it bites on the new code).

**GREEN**: `-k FirstLook -v`: the 7 tests `ok`, `Ran 7 tests in 0.150s`, `OK`.
The whole file three times in a row: `Ran 70 tests`, `OK`, `OK`, `OK` (1.5 s each).
`tests/test_supervise.py` (the process tests) three times in a row: `Ran 15 tests in 30.056s OK`, `30.089s OK`,
`28.786s OK`. Only `test_supervise.py` starts processes in this suite; `test_news_supervised.py` is in-process.

**Planted defects** (this dispatch, in a scratch copy that is deleted again; script
`<SCRATCH>/t7/mutate.py`, output
`<SCRATCH>/t7/mutants2.txt`): 14 planted, 14 caught -
the late line before the first look; the look's lines not printed; git without the env; git with only the one
variable; no row for a look that returned false; a look that raises ends the start; no beat after the look; a
broken chain that says nothing; a look on a broken chain; a look before the bell; git before the lines that can
wait; "boot" after E1; the alert in other words; no chain check at a start.

**Any hour** (the 11:10 UTC ruling): the 13 new tests with the engine's and the test module's clock moved
(`.../t7/shifted.py`): Wednesday 19:08, Saturday 11:08 and Wednesday 05:08 New York, `OK` each time. The starts pass
"23:59" themselves and `market_open_now` is `_Engine`'s stand-in. The edited harness test starts its engine through
`Procs.start_engine`, which adds `--until 23:59`, and its scenario says `"session": "open"`: the hour does not matter.

## The whole suite

`safe python3 -m unittest discover -s tests`, in the gate clone, before the commit; wall time 1 min 33 s:

```
Ran 637 tests in 92.735s

OK
```

637 = 624 + 13. The printed lines between the dots are the same ones the suite printed before this task (old tests
that let the engine print); the new tests capture their output.

## Files changed

- `ai-trader/aitrader/news_live.py`
- `ai-trader/tests/test_news_supervised.py`
- `ai-trader/tests/test_supervise.py` (not in the brief's list; by the controller's ruling)

## Self-review (`git diff ce6abbe3..HEAD`)

Checked line by line against the brief; nothing to fix:

- The order is the brief's six steps. Before the first look the only calls that leave the process are the look's
  own quotes (test 1, and the before-the-bell test reads the chains at `calls == []`).
- A broken chain returns 4 before any quote; it does not save the book and does not set `_chain_checked`, so the
  first step reads the chains again as it always did.
- `guarded=True`: a failed live look is a row "early_stops" plus the row "first_look"; anything raised after it
  (for example the save) is the row "first_look" alone, and the look's lines are still printed.
- The first look's `_told_lines` cannot leak into step 1 (`step()` resets the set); `_unsent` keeps a row whose
  line no channel took.
- `nt._beat(nt._phase)` after E1 is "stops" at that point, so the file never goes back to "boot" after the look.
- Nothing inside `_step` changed; no trading rule changed. What changes is that a start makes one more look, as the
  spec says.
- No number added; no literal threshold.

## Departures from the brief, and readings

1. **`tests/test_supervise.py` is in the commit** (ruling of 16:05 UTC, option 1). In
   `Harness.test_a_scenario_is_played_as_written` the scripted quotes `"BBB": [51.0, 48.0]` became
   `[51.0, 51.0, 48.0]`, and the comment says which look sees which price: a start now looks once before the first
   step. The expected trades `[("BUY", "CCC", 42.0), ("SELL", "BBB", 48.0)]` and the positions are untouched.
2. **The first look's lines are printed to the engine's log** (ratified). Without it
   `test_the_loop_prints_what_a_failed_step_had_already_done` in `tests/test_loss_protocol_pins.py` fails (M2).
3. **`_beat("stops")` at every start, also before the bell** (ratified).
4. **The beat after a delivered E1 keeps the current phase**, and in `WhatAStartFinds`,
   `test_the_pair_is_in_the_file_as_soon_as_a_channel_took_the_line_also_when_no_step_follows`, the expected phase
   "boot" became "stops" (ratified; a heartbeat test, not a trade test).
5. **The chain check is written out in `_run`** with `_step`'s text repeated, so that nothing inside `_step`
   changes; `test_the_alert_of_a_broken_chain_at_a_start_is_word_for_word_the_one_of_a_step` holds the two texts
   together (ratified).
6. **`class FirstLook(_WatchedStarts)`**, where `_WatchedStarts(_Starts)` and `_Starts` is an `_Engine`: the fixture
   holds the stand-ins and `start(**kw)` for both new classes. `hold(self.nt); self.nt.save()` is in its `setUp`.
   `stop_catchup` is "off" there (whether a bar read is due depends on the hour); the brief's third test turns it on.
7. **13 tests, not 7.** `-k FirstLook` runs the brief's 7 under their names with the brief's assertions. Three carry
   one assertion more (the order of the three lines; the bars read before git; nothing but the alert leaves the
   process on a broken chain), and the code-stamp test also checks that the rest of the environment reaches git.
   `TheOrderOfAStart` adds 6: before the bell, the heartbeat at git, the log, a look that raises, a sale plus a late
   line in one start, the alert's words.
8. **A look that returned false** gets its row through `_note_error(RuntimeError(...), "first_look")`: there is no
   exception at hand, and the "early_stops" row before it names the real one.

## Concerns (none blocks; all known to the controller)

1. Between the "stops" beat and the first step a start has no beat: up to three sends, two git calls and the
   priming poll. Ruled: Task 8a, item 4.
2. A line of the first look that no channel took is not carried into the first step's closing message. Ruled:
   Task 8a. It is in the engine's log and is said late at the next start of the day.
3. `NewsTrader.__init__` can send an urgent line before the first look (an unknown word in `news.stop_catchup` or
   `news.guards`). Old code, untouched; the one exception to "nothing reaches the network before step 4".
4. `_run` is now about 110 lines (83 before). Kept inline, as the brief names `_run`.
