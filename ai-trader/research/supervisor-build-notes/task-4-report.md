# Task 4 report - a heartbeat after every network call

**Status: DONE_WITH_CONCERNS.** One commit on `supervisor-build` in the gate clone, on top of `2c5cf812`:

- `8ed84237` (`8ed842372a9a02f81210ec0fdaade0f158e01c36`)
  `feat(ai-trader): the engine heartbeat is written after every network call and carries pid, phase and per-name stamps`

`git status --short` prints nothing. No attribution line, nothing pushed, no git setting changed.

This is the second dispatch of the task. The first one built it, met two existing tests that the brief contradicts,
and reported BLOCKED with its work parked as a patch. The controller ruled (controller-notes.md, 12:19 UTC). What I
did: checked the clone (HEAD `2c5cf812`, `supervisor-build`, clean), applied the parked patch, read every line of it
against the brief and spec 5.5, applied the three rulings, added the one new beat test first (RED, then the beat),
ran everything again, committed. This report replaces the first one and describes the task as committed.

## What is in the commit

`ai-trader/aitrader/news_live.py` (+102 -13)

- Module: `read_heartbeat() -> dict | None` (`None`: no file, a file that does not parse, or one that is not an
  object). `_utc(stamp)`: ISO text as an aware UTC time; text with no zone is read as UTC.
- `NewsTrader._beat(phase)`: the only writer of `state/news_heartbeat.json` (one `journal.save_json`, atomic as
  before). Kept keys: `at`, `headlines_seen`, `positions`, `queue`, `stops_checked_at`, `buys_blocked`, `code`,
  `lock`. New: `pid`, `step`, `phase`, `market_open`, `held` (`{sym: {stop, checked_at}}`, `checked_at` from
  `self._covered`), `blind`, `blind_since`, `blind_told`, `told_through` (null), `mismatch_told` (null), `supervised`
  (false). Only "idle" works out `headlines_seen`, `stops_checked_at` and `buys_blocked` (the old code for the stamp
  moved here); every other beat repeats the last values. It never raises: `_note_error(e, "heartbeat")`.
- `NewsTrader.adopt_previous(prev)`: `_prev_look` = `prev["stops_checked_at"]` as aware UTC, else
  `_last_stop_check()`; when `prev["at"]` is of today's New York date, each `blind_since` entry of a name still held
  becomes `_blind[sym] = [that time, sym in prev["blind_told"]]`.
- The 13 call sites:

  | Phase | Where | Lines |
  |---|---|---|
  | boot | `_run`, right after `adopt_previous` | 1529 |
  | stops | `check_stops`, once per held name after whatever its quote led to (no price: before the `continue`) | 867, 893 |
  | stops | `catch_up_stops`, after each `bars_since` | 1003 |
  | stops | the end of `_look_at_stops`, when the look stamped a held name (ruling) | 1094 |
  | queue | `run_queue_at_open`: after `official_opens`, and after each queued name (left waiting, bought or turned down) | 1335, 1342, 1356 |
  | poll | `_step`, after `poll_headlines` | 1389 |
  | quotes | `_step`, after each new headline's quote | 1396 |
  | score | `_step`, after each `_scored` batch; `handle_scored`, after a second check that was waited for | 1400, 1190 |
  | idle | `_step`, where the file was written before | 1414 |

- `_step` counts the steps this process has begun (`self._steps`).
- `_run`: `nt.locked = locked`, `nt.adopt_previous(read_heartbeat())`, `nt._beat("boot")`, then `code_stamp()`.

`ai-trader/tests/test_news_supervised.py` (+266 -1): class `Heartbeat` (the brief's seven tests, their assertions as
written) and class `EveryCallAndEveryStart` (eleven more), with the helpers `items(n)`, `step(nt, new, scorer)` and
`written()` (wraps `journal.save_json` and lists the phase of every heartbeat written).

`ai-trader/tests/test_news_inputs.py` (+10 -2): the two edits the controller ruled, nothing else (see "Departures").

## The rulings, as applied

1. `test_the_book_is_on_disk_before_the_request_is_cleared`: the list of saved files leaves out
   `news_heartbeat.json` beside `news_queue.json`. The next assertion (the book first, with no positions; the requests
   file last) is untouched and passes.
2. `test_without_a_live_quote_the_request_waits_and_the_stop_still_fires`: the `journal.save_json` stand-in lets a
   save of `news_heartbeat.json` through and refuses every other save with the same `AssertionError` text as before.
   `assertEqual(journal.read("news_errors.jsonl"), [])` is untouched. I did not take the proposed patch's changed
   error text (`f"{name} rewritten unchanged"`): "refuses every other save as before".
3. The closing beat of a look: `_look_at_stops` ends with one `_beat("stops")` when a held name's stamp in
   `self._covered` differs from the copy taken before the look (`seen`), after the look's save. That covers a stamp
   from a live quote and one from a bar read. A look with no held name, or one that stamped nothing, writes no such
   beat. One test: `test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once`.

## TDD evidence

Every command ran from `<clone>/ai-trader` as
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests ...`.
Outputs are kept in `<SCRATCH>/t4b/out/`.

**RED 1, the brief's tests against the engine of `2c5cf812`** (`-p 'test_news_supervised.py' -k Heartbeat -v`). I did
not take the first report's word for it. The engine file of `2c5cf812` was written into the working tree with
`git show 2c5cf812:ai-trader/aitrader/news_live.py`, the tests were run, and the built file was put back (no stash;
`git diff --stat` was the same before and after). The brief expects
`AttributeError: module 'aitrader.news_live' has no attribute 'read_heartbeat'`: that is what the tests that read the
file say, and the others fail on the next missing piece.

```
ERROR: test_a_restart_keeps_todays_blind_clock_with_its_told_flag_and_drops_yesterdays
AttributeError: 'NewsTrader' object has no attribute 'adopt_previous'
ERROR: test_a_three_batch_step_beats_between_batches
AttributeError: module 'aitrader.news_live' has no attribute 'read_heartbeat'
ERROR: test_blind_lists_a_held_name_with_no_live_quote
AttributeError: module 'aitrader.news_live' has no attribute 'read_heartbeat'
ERROR: test_every_headline_quote_leaves_a_beat
KeyError: 'phase'
ERROR: test_the_boot_beat_keeps_the_last_stop_look_of_the_run_before
AttributeError: 'NewsTrader' object has no attribute 'adopt_previous'
ERROR: test_the_fields
AttributeError: module 'aitrader.news_live' has no attribute 'read_heartbeat'
FAIL: test_every_bar_read_of_the_catch_up_leaves_a_beat
AssertionError: Tuples differ: (3, False) != (3, True)
Ran 7 tests in 0.029s
FAILED (failures=1, errors=6)
```

`-k EveryCallAndEveryStart` at the same moment: `Ran 11 tests ... FAILED (failures=2, errors=9)`.

**RED 2, the new closing-beat test, before that beat existed** (the parked patch applied, the ruling's beat not yet
written; `-k test_a_look_that_stamped -v`). Expected: the look's quote and bar read each leave a beat, both written
before the name was stamped, so the file has no stamp when the look is over.

```
FAIL: test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once
    self.assertEqual(look(0, False), (["stops", "stops", "stops"], utc(0)))
AssertionError: Tuples differ: (['stops', 'stops'], None) != (['stops', 'stops', 'stops'], '2026-11-10T14:45:00+00:00')
Ran 1 test in 0.007s
FAILED (failures=1)
```

**GREEN** (`-k Heartbeat -v`, on the files as committed; the brief's "7 tests, OK"):

```
test_a_restart_keeps_todays_blind_clock_with_its_told_flag_and_drops_yesterdays ... ok
test_a_three_batch_step_beats_between_batches ... ok
test_blind_lists_a_held_name_with_no_live_quote ... ok
test_every_bar_read_of_the_catch_up_leaves_a_beat ... ok
test_every_headline_quote_leaves_a_beat ... ok
test_the_boot_beat_keeps_the_last_stop_look_of_the_run_before ... ok
test_the_fields ... ok
Ran 7 tests in 0.026s
OK
```

`-k EveryCallAndEveryStart -v`: `Ran 11 tests in 0.081s OK` (the new test among them: `... ok`).
`-p 'test_news_inputs.py' -k OperatorExit`: `Ran 28 tests in 0.648s OK`.

**Three times in a row, on the files as committed.**
`tests/test_news_supervised.py`: `Ran 21 tests in 0.238s OK`, `0.212s OK`, `0.216s OK`. Five lines of output each:
the file prints nothing.
`tests/test_supervise.py` (real engine processes, which now write the new file): `Ran 12 tests in 11.085s OK`,
`12.886s OK`, `12.653s OK`. No process was left behind (`pgrep` for the engine child: 0).

**At any hour.** I added and changed no process test, so the 11:10 ruling's evening run does not apply to one. The
in-process file was run with every clock the engine and the tests ask moved by one offset (the first dispatch's
`shifted_inproc.py`, read before use): 11:00, 17:00, 09:31, 23:58 and 03:00 New York today, Saturday 2026-11-14
12:00, and the early close of 2026-11-27 at 12:30 and at 13:30. `Ran 21 tests ... OK` eight times. The real clock
during the other runs was between 08:00 and 08:35 New York, before the bell. The new test runs on a fixed clock of its own
(2026-11-10 09:45 New York, passed as `now`).

**Mutation check of what this dispatch added** (`mutate_end.py`, on a scratch copy, never the clone): six defects
planted one at a time, six caught. No beat at the end of a look; a beat at the end of every look with a held name; a
beat at the end of every look; the closing beat before the catch-up: each fails the new test (and the second and
third also fail older ones). Two for the edited tests, to show they still guard what they guarded: the requests file
rewritten when nothing is done fails `test_without_a_live_quote_the_request_waits_and_the_stop_still_fires`; the
request cleared before the book is saved fails `test_the_book_is_on_disk_before_the_request_is_cleared`. The first
dispatch's 51 mutants of the rest of the patch were not run again.

## Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`,
on the files as committed, wall time 80 s (an earlier run on the same code before a one-line test edit: 70 s, also OK).
Last three lines:

```
Ran 585 tests in 78.606s

OK
```

585 = 567 + 18. What the suite prints above the dashes comes from older tests (`[news] engine started ...`,
`[news] cycle error ...`, `[journal] skipped unreadable line ...`); the new code and the new tests print nothing.
Nothing changed under `state/`, `logs/`, `reports/` or `research/`.

## Files changed

- `ai-trader/aitrader/news_live.py`
- `ai-trader/tests/test_news_supervised.py`
- `ai-trader/tests/test_news_inputs.py` (by the ruling; not in the brief's `git add` line)

## Self-review (`git diff 2c5cf812..HEAD`, read against the brief line by line)

Found and fixed before the commit:

1. My first comment on the closing beat said every beat of the look was written before "the stamp" was set. With two
   names the second name's bar-read beat already carries the first name's stamp. The comment now says what is true: a
   name is stamped only after the beat of its own quote or bar read.
2. The new test depended on `news.stop_catchup` being "alert" in the real `config.json` (the `_Engine` config is a
   copy of it). It now sets "alert" itself, as Task 7's own test does.
3. The proposed edit of the second `OperatorExit` test changed the stand-in's error text. Kept as it was.

Checked and left as built by the first dispatch:

4. Every field of the brief is in the file and every phase is written where the brief says (table above).
5. `stops_checked_at` at "idle": the same rule as the old code when this process has made a look. Before its first
   look the old code wrote null; the new code writes the adopted stamp, which is what the brief asks ("until this
   process has made its own first look, every beat writes that stamp"). `test_loss_protocol_pins.py`'s "no stamp while
   a held name has had no quote" still passes.
6. No trade, stop, buy, sale or hold changes at any call site: a beat is one line that returns nothing and never
   raises, placed after the name's own handling. What does change is what the brief names: the catch-up of a new
   process reads from the stamp the run before left (also when this process ran steps before the bell, where the old
   code wrote null over it), and a blind alert is neither put off nor repeated by a restart.
7. `_run` is the only production path that writes a beat. `__main__.py` builds one more `NewsTrader` (`news-score`),
   which calls none of the methods that beat.
8. No number was added to the code. No test reaches the network, the model, the live state or the phone.
9. One beat costs about 1.0 ms ("stops") to 1.2 ms ("idle") with three held names (measured again on the committed
   code, `beat_cost.py`).

## Departures from the brief

1. **`tests/test_news_inputs.py` is in the commit, with two edits** (the 12:19 ruling; both are quoted under "The
   rulings, as applied"). The first is an expectation, the second is a stand-in.
2. **One beat more than the brief lists, by the ruling:** the closing "stops" beat of `_look_at_stops`.
3. **One beat more than the brief lists, ratified:** "queue" right after `official_opens`.
4. **`check_stops`: the beat follows the name's handling, not the quote's line** (ratified): a sale never waits for its
   own beat, and that beat already shows the book without the sold name.
5. **18 tests, not 7.** `-k Heartbeat` is the brief's seven. `EveryCallAndEveryStart` holds eleven: ten from the first
   dispatch (each call site, what a beat repeats, a beat that cannot be written, a start, a file that cannot be used)
   and the ruling's one.
6. **Readings, ratified:** before a process's first "idle" beat, `headlines_seen` and `buys_blocked` repeat what the
   adopted heartbeat held (null with none); `blind`, `blind_since` and `blind_told` hold held names only (the brief:
   "the keys of `self._blind`"); `nt.locked` is set before the boot beat.
7. **Readings the ruling does not name, kept:** `code` is null in the boot beat (`code_stamp()` runs after it: the
   brief puts the three lines "right after the trader is built"); `adopt_previous(read_heartbeat())` is one line with
   no `prev` variable (Task 7's brief writes it the same way); a blind clock that cannot be read leaves a
   `news_errors.jsonl` row with `where` "adopt_previous" and adopts none; `blind_since` and `checked_at` are UTC
   `isoformat()` text, like `stops_checked_at`.
8. **RED 1 was shown on the first dispatch's tests, not on tests I wrote from nothing:** they were parked with the
   patch. I read each of the seven against the brief (names, stand-ins, assertions) and ran them against the engine of
   `2c5cf812` myself.

## Concerns

1. **Sends are network calls with no beat of their own** (the brief's list and spec 5.5's list do not name them, so
   none was built). `notify.send` waits up to 15 s per channel. The longest stretch I can find with no beat is the
   tail of `check_stops`: after the last name's beat, one blind alert per held name. When Yahoo and ntfy are both
   unreachable (a network outage), N names turn 300 s blind in the same look and each alert times out: N x 15 s with
   one channel, N x 30 s with two. That passes `hang_seconds` (180) at 12 names, or at 6 with both channels, and the
   parent of Tasks 11-14 would kill an engine that is slow, not hung. The other stretches with a call that has no
   beat of its own stay under it: a batch's benchmark quote and the second check after it (66 + 65 = 131 s), the quote
   after a second check and the next headline's check (131 s), a queued name's two quotes (132 s).
2. **A look that stamps nothing writes no closing beat, by the ruling's letter.** A name that goes blind in such a
   look (its `_blind` entry is made after the quote loop) is in the file's `blind` list only with the next beat, in the
   same step ("queue" or "poll"). Spec 4.3 reads `blind` against the stale names; the lag is one beat, far less than
   `stops_stale_seconds`, so I think it is harmless. Widening the condition to "the look changed the blind lists" is
   one more clause if the controller wants it.
3. **Between two "idle" beats, `stops_checked_at` repeats the last worked-out value** (the brief). After a look, the
   fresh stamps are in `held[sym].checked_at` only. Task 12 must read the per-name stamps, not the top-level one,
   to judge a long step.
4. **`_run` until Task 7:** between the boot beat and the first beat of the first step stand git (2 x 15 s), on a
   fresh machine the priming poll, and up to two sends. And `code` is null in the file for that stretch;
   `skills/trader/SKILL.md` reads `code.started` from it. Task 7 owns the order of a start.
5. **A beat that cannot be written leaves one `news_errors.jsonl` row per beat** (the brief names `_note_error`, not
   `error_once`): a full disk is dozens of rows a step. Before this task a heartbeat that could not be written failed
   the step and counted toward the "failed N rounds" alert; now it costs a row and the step goes on, and the parent's
   hang rule is what notices.
6. A caller that never adopts (tests that call `check_stops` or `catch_up_stops` directly) writes
   `stops_checked_at: null` in its first beats, over a stamp a fixture left. `_run` always adopts first (self-review 7).
7. The new test's first held look sends one "bars could not be read" alert to the `_Engine` phone stand-in (the bar
   stand-in has no bars). It is not asserted on.
8. The commit's author name is the clone's configured git identity, as on Tasks 2 and 3.

Scratch files of this dispatch, none in the clone:
`<SCRATCH>/t4b/` (`out/` with every output quoted
above, `mutate_end.py`, `shifted_inproc.py`, `beat_cost.py`, `copy/` the scratch copy the mutants ran on,
`news_live.patched.py`). The first dispatch's files are in
`<SCRATCH>/t4/`.
