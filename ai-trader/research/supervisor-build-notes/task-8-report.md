# Task 8 report - a planned stop, and an engine that dies with its parent

Status: DONE_WITH_CONCERNS (the work is complete and green; one test of the brief could not pass as written and was
completed differently - see "Departures", item 1).

Start: HEAD `cbfc4686a20297d35c1fb9fc28848eddf6129efc`, branch `supervisor-build`, tree clean.
End: HEAD `3366396fb2cbafaaaf7063682bee2ceac719ab2b`, two commits, tree clean, nothing pushed.

- `186f4d26` feat(ai-trader): SIGTERM is a planned stop that ends with 143, and a supervised engine dies with its parent
- `3366396f` test(ai-trader): the uninterrupted-wait test no longer depends on a second round fitting into 30 ms

## What was built

`aitrader/news_live.py`
- `STOP` (a `threading.Event`), `request_stop(signum=None, frame=None)` (sets it), `_set_pdeathsig()` (Linux:
  `ctypes.CDLL(None).prctl(1, SIGKILL)`; elsewhere nothing).
- `DEFAULTS["sleep_slice_seconds"] = 0.5`.
- `run(..., supervised=None)`: after the `check` branch it clears `STOP`; on the main thread only it installs
  `request_stop` for SIGTERM and SIGINT and puts the earlier handlers back in a `finally`. With `supervised=PID`,
  before the lock file is opened: `_set_pdeathsig()`, then a parent pid other than PID prints one line and returns 143.
  It hands `supervised` on to `_run`.
- `_run(..., *, locked=True, supervised=None)`: `nt.supervised` (true in every beat); exit 6 sends R5d only when
  `supervised is None`; at the top of every round a changed parent pid sets `STOP`, and a set `STOP` ends the loop with
  143; the wait between steps is slept in slices of `news.sleep_slice_seconds` and ends when `STOP` is set; after the
  usual `save()` and `drain_trial()`, a planned stop writes `_beat("stopping")`.
- `NewsTrader._step`: no further headline quote and no further scorer batch once `STOP` is set; no between-batch look
  once it is set (the end-of-step look follows at once); the headlines still in `_pending` (polled, not handed to the
  scorer) are taken out of `self.seen` and `_pending` is emptied, so they get no `step_failed` row and the next
  engine polls, scores and logs them once. The end-of-step look, `drain_trial`, `save` and the "idle" beat are
  unchanged.
- `_beat`: `"supervised": getattr(self, "supervised", False)`; the docstring names the phase "stopping".

`aitrader/__main__.py`: `news-live --supervised PARENT_PID` (int, default None), handed to `run` by keyword; two
usage lines.

`config.json`: `news.sleep_slice_seconds: 0.5` and one sentence in `news._note`.

## TDD evidence

RED (before any production change; output kept in the scratchpad, `t8/red1.txt`, `t8/red2.txt`):

`safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k PlannedStop -k hands_check -k hands_back`
-> `Ran 11 tests`, `FAILED (failures=1, errors=10)`:
- 9 x `AttributeError: module 'aitrader.news_live' has no attribute 'STOP'` (the new classes clear `STOP` in a
  cleanup, so the missing name is met before the brief's expected `TypeError: run() got an unexpected keyword
  argument 'supervised'`; the same missing feature);
- the command-line test: argparse refuses `--supervised` (SystemExit 2);
- `AssertionError: Lists differ: [{'locked': True}] != [{'locked': True, 'supervised': None}]`.

`safe python3 -m unittest discover -s tests -p 'test_supervise.py' -k EngineStop` -> `Ran 4 tests`, `FAILED (failures=4)`:
- three times `AssertionError: -15 != 143` (SIGTERM killed the engine: exactly what the brief expects);
- the kill-9 test: `not within 5 s` (the child left with argparse's 2 on the unknown option, so no beat came).

GREEN:
- `test_news_supervised.py`, the whole file three times in a row: `Ran 79 tests`, `OK`, `OK`, `OK` (1.5-1.7 s).
- `test_supervise.py`, the whole file with `-v`, three times in a row: `Ran 19 tests in 31.7 s / 32.4 s / 34.6 s`,
  `OK` each time; the four `EngineStop` tests `ok` in each run.
- After the second commit: `-k PlannedStop` three times `Ran 9 tests OK`, the whole file `Ran 79 tests OK`.

Measured besides the tests:
- SIGTERM in the sleep to process exit, five engines: 0.265-0.316 s (limit 1 s; worst case is one 0.5 s slice plus
  the save).
- Mutation: `_set_pdeathsig` made a no-op -> the kill-9 test fails (`not within 1 s`); put back -> passes. The test
  proves the kernel call, not the loop-top check.

The hour of the day (ruling of 11:10 UTC): the runs above were made at 11:30 New York. The four process tests are
indifferent to the hour: `Procs.start_engine` adds `--until 23:59`, the PARENT script passes `--until 24:00`, the
session comes from the scenario (`market_open_now` and `_quote_is_live` are stand-ins), and the one name held
(`write_book`) is bought today with no recorded time, which the minute-bar catch-up and the 5-day exit leave alone.
The known ceiling stays the minute 23:59-00:00 for the three `start_engine` tests. No run with a faked evening
clock was made.

## Whole suite

`safe python3 -m unittest discover -s tests`, before the first commit:

```
Ran 650 tests in 98.426s

OK
```

Wall time 1 min 39 s. 637 before, 13 new. The second commit changed one test only; its file was run again (79 OK),
the whole suite was not. Output of the two files of this task is pristine (dots only); the lines the suite prints
come from older files (`[news] engine started ...`, `[journal] skipped unreadable line ...`), as before.

## Files changed

- `ai-trader/aitrader/news_live.py`
- `ai-trader/aitrader/__main__.py`
- `ai-trader/config.json`
- `ai-trader/tests/test_news_supervised.py` (classes `PlannedStop`, `PlannedStopOfTheLoop`; two expectations edited)
- `ai-trader/tests/test_supervise.py` (`PARENT`, class `EngineStop`)

## Departures from the brief

1. **The kill-9 test, its last two lines.** As written (`wait_for(dead(child), timeout=1)`, then one non-blocking
   `flock`) it failed 3 times out of 3 with `BlockingIOError` although the feature works. Cause, measured:
   `Procs.dead` counts a zombie as dead, and the kernel shows the engine's main thread as a zombie about 0.2 ms
   before the process's other threads (4 threads in all: numpy starts three) have released the open files and with
   them the lock. The test now takes one deadline of 1 s from the kill: `dead(child)` within it, then
   `wait_for(self.lock_is_free, timeout=<what is left of that second>)`. The spec's sentence ("gone within 1 s and
   the lock is free") is asserted whole; what changed is that the lock is asked until the second ends and not once.
   I did not stop with BLOCKED because nothing about what to build was in question; the controller may rule
   otherwise.
2. **The kill-9 test, more.** `PARENT` gives the child `stdout`/`stderr` = DEVNULL (otherwise the engine's own log
   would share the pipe the pid is read from), `--sent <tmp>/sent.jsonl` (so `tearDown` reads this engine's tripwire
   file) and `--until 24:00` (controller ruling). Cleanups end the parent and, by its command line only, the child.
3. **Existing expectations edited** (both in `tests/test_news_supervised.py`, a file of this task):
   `TheLoopsAnswer`: `_run` now gets `{"locked": True, "supervised": None}`;
   `test_the_command_line_hands_check_to_run_by_keyword`: `supervised` is in each call's keywords, and a third call
   (`--supervised 41`) was added.
4. **13 tests, not 7.** The brief's seven are there under their names with their assertions. Six more, for
   behaviour the brief requires and none of its tests reaches: the taken-back headlines leave no `news_seen_log` row
   and are not in the saved seen file (baseline fact (b)); a stop set before the quotes asks no headline quote, starts
   no batch and still makes the end-of-step look; `run` installs the handlers on the main thread only, restores them
   and clears `STOP`; a changed parent pid at the top of a round gives 143 with `phase` "stopping" and
   `supervised` true; the wait is slept in slices and a stop ends it at the next slice; an uninterrupted wait is as
   long as before.
5. **RED text.** `AttributeError ... 'STOP'` where the brief expects the `TypeError` (see RED).
6. **One condition the brief does not name:** the between-batch look is skipped once `STOP` is set. The loop breaks
   right after it and the end-of-step look runs at once, so the look would only be made twice in a row; spec 5.3
   bounds a planned stop at "one call plus one look". No sale, stop check or buy rule changes.
7. Two usage lines for `--supervised` in `__main__`'s docstring (the brief lists the option only).

## Self-review

- Brief line by line: every interface and bullet is implemented (list above). `git status --short` prints nothing.
- Found and fixed: the config note first said a lost parent is seen within one slice (untrue: the parent pid is
  read at the top of a round only, as the brief says) - reworded before the commit. One of my added tests asserted
  the first slice of a second round, which needs the first round to fit into 30 ms of real time - made
  deterministic (commit 2). One of my added tests called `_run` twice and forgot that only `run` clears `STOP`.
- `signal.signal` can hand back `None` for a handler that was not set from Python; putting `None` back raises
  `TypeError` and would turn an exit code into a traceback, so `None` is restored as `SIG_DFL`.
- No trading rule moved: the diff of `_step` adds three `STOP` conditions and the take-back block; with `STOP`
  clear every path is as before (the whole suite, the golden tests included, is green).

## Concerns

1. Departure 1 (the lock asked until the second ends) needs the controller's eye.
2. Outside Linux, and if `prctl` ever fails (its return value is not read), a lost parent is noticed only at the top
   of the next round, up to `poll_seconds` plus a step later - the slices of the wait look at `STOP`, not at the
   parent pid. That is what the brief specifies; on Linux the kernel kills the engine at once.
3. `PR_SET_PDEATHSIG` fires when the THREAD of the parent that started the engine ends, not only when the parent
   process does. The parent of Tasks 10-15 must start the engine from a thread that lives as long as it does (its
   main thread), or the engine is killed while its parent lives.
4. A stop that arrives during a start is honoured at the top of the first round: the lines that can wait, git and
   (on a very first start only) the priming poll still run before it. The brief asks only that the first look be
   finished; not changed.
5. After the close, a planned stop still waits `verify_timeout_seconds` (60) in `drain_trial` when a trial answer is
   out (unchanged code); inside the parent's grace of 120 s.
6. `news.sleep_slice_seconds` of 0 or less would never end the wait. No guard was added (it would be a literal in
   the logic); the value lives in `config.json` and `DEFAULTS`, and the pin test holds the two together.
7. A step that raises while `STOP` is set leaves its unscored headlines seen, with `step_failed` rows, as any
   failing step does today; the take-back runs only in a step that reaches its end.
8. In this VM zombies of killed grandchildren are never reaped (pid 1 does not wait for them); `Procs.dead` already
   treats a zombie as dead.
