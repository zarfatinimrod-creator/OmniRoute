# Task 3 report - the engine child for tests, and a lock that names its holder

**Status: DONE_WITH_CONCERNS.** One commit on `supervisor-build` in the gate clone:

- `25d18a4b5672c6170cb7b729f3ab5d1317dd8d97` - `feat(ai-trader): the engine lock names its holder and says when it cannot be taken`
- base `c6bec0f7`; 6 files, +572 -11; `git status --short` prints nothing. No trailer, no body, no attribution line.

Everything the brief asks for is built and its five tests pass as written. The concern is two plan defects I had to
close inside the harness for those tests to pass at all (see "Departures" 1 and 2): the controller should confirm where
those two defaults live, because Tasks 5, 8, 12, 14 and 17 lean on them.

## What is in the commit

**`aitrader/news_live.py`** (+53 -11)
- `owner_line(cfg, line_id, **fields) -> str`: `ownerlines.render` with `max_bytes` = `supervisor.max_line_bytes` and
  `free_chars` = `supervisor.free_text_max_chars`. No number in the code.
- `run()`: the lock file is opened with `"a+"`. `BlockingIOError` (a held lock, controller ruling): prints
  `[news] another news engine holds the book (pid <pid>, started <started_at>): this one does not start (exit 3)`,
  returns 3, writes nothing, sends nothing. Any other `OSError`: the old print, then the engine runs with
  `locked=False`. Once `flock` succeeded the file is rewritten with one line `{"pid": <int>, "started_at": "<UTC>"}`
  (`journal.now_utc()`, whole seconds). `run()` returns what `_run` returns.
- `_lock_holder(lock)`: `(pid, started_at)` from the file, `"unknown"` twice when it does not parse (a holder that has
  not written yet, or an engine from before this commit). The refusal never depends on the file's text.
- `_run(until_ny, max_minutes, prime, *, locked=True) -> int`: `nt.locked = locked`; when not locked one
  `notify.send("AI Trader - תקלה", owner_line(cfg, "E2"), cfg, "urgent")` (priority positional), next to the calendar
  alert, before the loop; returns 0.
- The heartbeat write carries `"lock": getattr(self, "locked", True)`.

**`config.json`**: a `supervisor` block before `books`: `max_line_bytes` 1200, `held_names_in_line` 6,
`free_text_max_chars` 200, and a `_note`.

**`tests/helpers/engine_child.py`** (186 lines): `install(sc, sent)` replaces the nine calls of baseline 4.1 (`_feed`
and `fetch_headlines`, `live_price`, `bars_since`, `official_opens`, `score_batch`, `verify_headline`,
`rescore_headline`, `notify.send`, `code_stamp`) plus `market_open_now`, `NewsTrader._quote_is_live`,
`journal.calendar_covers` and `news_live.load_config`; `install_tripwire(path)`; `engine_options(options)`; `main`.
Every scenario key of the brief's table with its default (`SCENARIO`). Stand-ins are set on `news_live` (baseline
surprise 2). The scorer stand-in returns a `news_live.Scores` with facts, so the engine writes its
`news_scorer_calls.jsonl` row as it does live.

**`tests/test_news_supervised.py`** (53 lines): `hold(nt, sym="BBB", entry=50.0)`; class `Lock` (the brief's test);
two more one-test classes (see "Departures" 4).

**`tests/test_supervise.py`** (281 lines): `Procs` with every member the brief names (`scenario`, `start_engine`,
`write_book`, `beat`, `wait_beat`, `rows`, `sent_rows`, `wait_for`, `step_done`, `dead`, `tearDown`); `EngineLock`
(the brief's four tests); `Harness` (seven tests of the harness itself).

**`tests/test_news_guards.py`**: the two `OneEngine` stand-ins, as the brief says:
`lambda until, minutes, **k: 3` and `lambda *a, **k: ran.append(a) or 0`. Nothing else.

## TDD evidence

Every command ran from `<clone>/ai-trader` as
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests -p '<file>' [-k Lock] -v`.
Saved outputs: `<SCRATCH>/t3/out/`.

**RED, `test_news_supervised.py -k Lock`** (the brief's expected failure: nothing says E2 yet):
```
FAIL: test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat
    self.assertEqual([p for p, b in self.sent if b.startswith("מנוע החדשות רץ בלי נעילה")], ["urgent"])
AssertionError: Lists differ: [] != ['urgent']
Ran 1 test in 0.045s
FAILED (failures=1)
```

**RED, `test_supervise.py -k Lock`** (expected: there is no `engine_child.py`). The brief predicts a
`FileNotFoundError`; the child is started through the interpreter, so the same fact arrives as the interpreter's
exit 2 and its message:
```
FAIL: test_a_second_engine_exits_3_within_2_s_names_the_holder_and_touches_no_state
AssertionError: not within 5 s: step_done; engines that ended: ["exit 2: /usr/local/bin/python3: can't open file
'.../ai-trader/tests/helpers/engine_child.py': [Errno 2] No such file or directory\n"]
FAIL: test_an_open_session_with_a_queued_name_and_a_headline_reaches_nothing_outside
AssertionError: 2 != 0
(the other two: the same "can't open file")
Ran 4 tests in 15.074s
FAILED (failures=4)
```

**GREEN, `-k Lock`, both files (the brief's "5 tests, OK"):**
```
Ran 1 test in 0.049s
OK
Ran 4 tests in 6.396s
OK
```

**GREEN, both files whole, three times in a row** (the process file is the one that must not flake):
```
run 1 test_news_supervised.py | Ran 3 tests in 0.093s  OK      run 1 test_supervise.py | Ran 11 tests in 10.976s  OK
run 2 test_news_supervised.py | Ran 3 tests in 0.092s  OK      run 2 test_supervise.py | Ran 11 tests in 11.409s  OK
run 3 test_news_supervised.py | Ran 3 tests in 0.117s  OK      run 3 test_supervise.py | Ran 11 tests in 12.134s  OK
```
Also six copies of `test_supervise.py` at the same time on this 4-core VM: six times `Ran 11 tests ... OK` (18-20 s
each), so the "exits 3 within 2 s" bound has room (a refused start takes about 0.5 s). The new tests print nothing.

**Mutation check** (`.../scratchpad/t3/mutate.py`, on scratch copies, never in the clone): 39 defects planted one at
a time, 18 in `news_live.py` and 21 in `engine_child.py`; each run is the two new files plus `OneEngine`. At the
commit: `mutants 39 survived 0 not applied 0`. Examples: the lock opened with `"w"` again; the holder appended and not
rewritten; a refused start returns 0; a held lock runs without it; E2 high, twice, or never; the heartbeat's `lock`
stuck either way; `run` answers 0 whatever the loop said; the tripwire writes and goes on; every host local; `claude`
given by its path let through; the tripwire not installed by `main`; every poll the first list; every price the
first value; the scenario's `universe`, `news`, `opens` or `scores` ignored; the orphan given the engine's lock
(then `test_the_lock_is_free_while_an_orphan...` fails: that test is not empty).
The tests I added after the code have their RED here: the run before their assertions existed left survivors
(`opens` ignored; the phone stand-in returning nothing), each killed in the final run.

## Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, on the files as committed. Wall time 70 s. Last three lines:
```
Ran 566 tests in 69.648s

OK
```
566 = 552 + 14. After the run `git status --short` showed only the six paths: nothing under `state/`, `logs/`,
`reports/` or `research/`. No process and no `sleep 60` was left. The `[news] ...` lines in the output are those of
earlier tests; one of them changed its wording (`OneEngine`'s refused start now prints
`(pid unknown, started unknown)`: that test holds the lock on an empty file).

## Files changed

`ai-trader/aitrader/news_live.py`, `ai-trader/config.json`, `ai-trader/tests/test_news_guards.py` (modified);
`ai-trader/tests/helpers/engine_child.py`, `ai-trader/tests/test_news_supervised.py`,
`ai-trader/tests/test_supervise.py` (new). Exactly the brief's six paths. No test outside the list broke.

## Self-review (the diff `c6bec0f7..HEAD`, read again after the commit)

Found and fixed before the commit:
1. **The tripwire had never been seen to fire.** The brief's tests only assert that its file is absent, so a
   tripwire that does nothing passed all of them. Three tests now: each of the five forbidden calls ends its process
   with 97 and leaves the call's name; what stays on 127.0.0.1 (a socket, `urlopen`, `requests`) and a `sleep`
   go through; and `engine_child.main` itself puts the engine behind the wire. The targets (`outside.invalid`,
   `192.0.2.1`, `/nonexistent/claude`) cannot answer, so a broken tripwire would still reach nobody.
2. **An engine with no lock would have signed the lock file.** Not in the brief's test; one assertion added to it
   (`read_text() == ""`), and the mutant is killed.
3. **`run()` returning `_run`'s value was pinned by nothing** (`_run` returns 0 in this task, so `return 0` passed).
   `TheLoopsAnswer` pins it with a stand-in that returns 7, and that the lock file names this process.
4. **I had a `try/except OSError` around the write of the holder's line; I removed it.** It was untested, and an
   engine that cannot write 60 bytes into its own lock file is better dead and loud (under the parent: a crash loop
   the owner is told about) than limping. A lock file that cannot be opened already ended the start before this commit.
5. **A book entered on an earlier day does not play the same on every day.** With the clock moved (scratch
   `shifted_child.py`): a position dated 2026-11-09 gets an urgent "stop not checked 09:30-11:00" line in session
   hours and a "time exit after 9 trading days" sale on 2026-11-20. `write_book` therefore writes "bought today, at
   no recorded time", which both the 5-day exit and the look back at minute bars leave alone. The brief's open-session
   scenario and a held name under its stop were replayed at 11:00 and 16:30 of a session day and on a Saturday (the
   first also on the early close of 2026-11-27): the same rows every time.
6. `wait_for` names the engines that already ended, with their exit code and the end of their stderr: without it a
   child that dies at start is a silent 5 s timeout.

Checked and left as it is:
- The refused start: every state file is byte-identical before and after (the brief's assertion), the lock file
  included; nothing is read but the lock file.
- The orphan: `sleep 60` is started with the default `close_fds`, as `subprocess.run` starts `claude`, and with its
  three streams on `/dev/null` so that it does not hold the test's pipes. `tearDown` kills it only when
  `/proc/<pid>/cmdline` is `sleep 60`: never a pid that was reused.
- No topic, key, address or id in any file. No trading rule is touched: the diff of `news_live.py` is the lock, the
  one line E2, `owner_line` and one heartbeat key.
- Lines over 135 characters in the new files: two, both the brief's own, verbatim.

## Departures from the brief

1. **The harness makes the loop wait 1 s, not `config.json`'s 20 s (`QUICK` in `engine_child.py`).** Plan defect:
   the table gives `news` the default `{}`, and the loop sleeps `news.poll_seconds` after every step. Measured with
   the config's own value: `--minutes 0.001` ends after **20.58 s**; the brief waits 10 s (two tests) and 20 s (one).
   The scenario's own `news.poll_seconds` still wins (the brief's tests set 30 where they need a long sleep). With it
   a start takes about 1.5 s.
2. **The engine child adds `--until 24:00` when the options name no end (`engine_options`).** Plan defect: the
   engine's default is 16:05 New York, so an engine child started after the close ends before its first step
   (measured with a passed `--until`: exit 0 after 0.56 s, no heartbeat). The gate runs after the close: the brief's
   tests 1 and 3 would fail there. An explicit `--until` is passed through unchanged.
3. **A scenario key the harness does not know is refused (exit 2) before the engine starts.** A misspelt key would
   leave its default in place and the test would pass for the wrong reason.
4. **14 tests, not 5.** `-k Lock` still gives the brief's five. Added: `TheLoopsAnswer` and `Unlocked` (one each) and
   `Harness` (seven), for the reasons of self-review 1-3 and departures 1-3, and one scenario replayed end to end
   (`write_book`, a price per call, a list per poll, `universe`, `news`, `opens`, `scores`, `commit`, the phone
   stand-in). Assertions added to the brief's own tests, none removed: no lock file signed without a lock; the refused
   start sent nothing; after kill -9 the file names the new holder; the open-session test also checks that the queue
   was bought, the headline scored and the line sent (else "reaches nothing outside" could pass with an engine that
   did nothing). `a.wait()` follows each `a.kill()`. The `Lock` test runs under `redirect_stdout`.
5. **E2 is guarded**: a line that cannot be built or sent goes to `news_errors.jsonl` (`where` "lock_line") and the
   engine starts. An engine with no lock is the only one the book has. Tested (`Unlocked`).
6. **`config.json`'s block has a `_note`**, as every block of that file has. Task 10's test reads named keys only.
7. Readings of the table where it could be read two ways: `opens`: a name not in it is left out of the answer, as
   the real call does, so the engine's own fallback takes the stand-in's live quote. `prices`: every call stamps
   `QUOTE_TIME`, a null one too. `bars`: rows of `[start (UTC ISO), low, close]`, handed back unfiltered.
   `score_orphan`: one `sleep 60` per engine process, at the first scorer call.
8. `engine_child.py` puts the `ai-trader` folder on `sys.path` itself, so the brief's command line also works by hand.

## Concerns

1. **Departures 1 and 2 are mine to flag, the controller's to settle.** Both live in the engine child, so Task 8's
   `PARENT` script and the drills get them too. What they do not cover: a parent that passes `--until 16:05`
   itself (`supervisor.until_ny`, Tasks 10 and 14) to an engine child after the close. That child stops at once.
   Tasks 12 and 17 need "24:00" in their config copy, or a ruling that the child always overrides `--until`.
2. **Only the session is moved, not the calendar.** `catch_up_stops` still returns at once on a real closed day and
   the 5-day exit counts real sessions (self-review 5). A later test that writes a book by hand with an old entry
   date, or that needs the catch-up to run in a process, will depend on the day it runs.
3. **E2 goes out before the loop**: after priming and before the first stop look. Task 7 moves it.
4. **The lock file keeps its last line after the engine ends**, and a start refused in the instant before the
   holder writes reads the previous holder's pid. The text is only ever a hint; Task 14's `--status` must test the
   lock itself, as Review Focus 1 says.
5. **The tripwire lets only the literal host `127.0.0.1` through**, not `localhost` and not `::1`. The stubs of
   Tasks 13 and 21 must be addressed by that literal.
6. Not pinned by any test: `calendar_covers`, `quote_delay_s`, `score_delay_s`, non-empty `bars`, a null price, and
   that the scenario's `poll_seconds` beats the harness's 1 s (that would cost a 1.5 s sleep in the suite).
7. The suite is 10 to 15 s longer (70 to 76 s in three runs); `test_supervise.py` alone is 11-12 s. Each engine
   start costs 1.5 s.
8. The commit's author name is the clone's configured git identity, as on Task 2's commit. I changed no git setting.

Scratch files, not in the commit: `<SCRATCH>/t3/`
(`look.py`, `look2.py`, `shifted_child.py`, `mutate.py`, `out/`).

## Fix round 1

**Status: DONE.** Two new commits on `supervisor-build`, on top of `25d18a4b` (nothing amended):

- `f78a2624` - `test(ai-trader): the in-process lock tests name their own end, 23:59` (F1)
- `2c5cf812` - `test(ai-trader): a test's default end is set by Procs.start_engine, not by the engine child` (F2)

HEAD `2c5cf812b93007472150d16d6a8103d508516616`. Three files, all test-side and all in the brief's list:
`tests/test_news_supervised.py`, `tests/test_supervise.py`, `tests/helpers/engine_child.py`. No production file
changed. `git status --short` prints nothing. No trailer and no attribution line in either message.

Every command ran from `<clone>/ai-trader` with
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 ...`.
Scratch scripts and saved outputs (not in the commit):
`<SCRATCH>/t3fix1/` (`evening_inproc.py`,
`evening_procs.py`, `evening_child.py`, `out/`).

### F1 - fixed

`tests/test_news_supervised.py:27` (`Lock`) and `:51` (`Unlocked`): `news_live.run(max_minutes=0.0005, prime=False)`
is now `news_live.run("23:59", max_minutes=0.0005, prime=False)`. Nothing else in the file changed.

RED, before the fix, the file with `news_live.datetime.now` answering 17:00 New York
(`python3 .../t3fix1/evening_inproc.py`, the reviewer's check with all three tests of the file):
```
test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat ... ERROR
test_run_hands_back_what_the_loop_returned_and_the_lock_file_names_this_process ... ok
test_a_line_that_cannot_be_built_does_not_cost_the_book_its_only_engine ... ERROR
    self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)
TypeError: 'NoneType' object is not subscriptable
Ran 3 tests in 0.043s
FAILED (errors=2)
```
GREEN, after the fix, the same command (17:00 New York), and again on the committed tree:
```
Ran 3 tests in 0.105s
OK
```
GREEN at the real hour (06:45 New York), `python3 -m unittest discover -s tests -p 'test_news_supervised.py' -v`:
```
Ran 3 tests in 0.103s
OK
```

Left as it is, and not on the list: `TheLoopsAnswer` (`tests/test_news_supervised.py:37`) calls
`news_live.run(max_minutes=0.001)` with `_run` replaced by a stand-in (`:36`). No loop runs and no clock is asked,
so the hour cannot reach it: it is the `ok` line of the RED run above, at 17:00 New York. If the re-reviewer reads the
ruling's "every in-process start" as covering this call too, it is a one-word change.

### F2 - fixed

- `tests/helpers/engine_child.py`: `engine_options` is gone and `main` ends with
  `return cli.main(["news-live", *options])` (`:178`). The child adds no end of its own: with no `--until` the engine
  ends at its real default, 16:05 New York. The module's text says so and points at `Procs.start_engine` (`:25-30`).
- `tests/test_supervise.py:81-85`, `Procs.start_engine`: when the test's options carry no `--until` (either spelling,
  `--until X` or `--until=X`) it puts `--until 23:59` in front of them. The comment at that one place (`:82-84`) names
  the reason (the gate runs after 16:05) and the known ceiling (a start made between 23:59 and 00:00 New York). An
  own `--until` goes through unchanged. The docstring (`:75-77`) says the same.
- `tests/test_supervise.py:283-301`, class `Harness`: the old pin `test_a_start_has_no_end_by_the_clock_unless_its_options_name_one`
  tested `engine_child.engine_options`, which no longer exists. Two pins take its place, both the same at any hour:
  - `test_a_start_made_here_ends_at_23_59_new_york_unless_its_options_name_an_end` (`:283`): the command line
    `start_engine` hands to `subprocess.Popen` (a `mock`, no process) for three option sets:
    `--minutes 5` gets `--until 23:59` in front; `--minutes 5 --until 16:05` and `--until=16:05` are untouched.
  - `test_the_engine_child_hands_the_engine_its_options_as_they_came` (`:293`): the child in a process of its own
    with `cli.main` replaced by a print: given `--minutes 5` it hands the engine exactly `["news-live", "--minutes", "5"]`.
- `:19` `from unittest import mock` is new; `from helpers import engine_child` is gone (its only user was the old pin).

RED, the two new pins against the old code (`-p 'test_supervise.py' -k Harness -v`):
```
FAIL: test_a_start_made_here_ends_at_23_59_new_york_unless_its_options_name_an_end
- [['--minutes', '5'], ['--minutes', '5', '--until', '16:05'], ['--until=16:05']]
+ [['--until', '23:59', '--minutes', '5'], ['--minutes', '5', '--until', '16:05'], ['--until=16:05']]
FAIL: test_the_engine_child_hands_the_engine_its_options_as_they_came
- (0, '["news-live", "--until", "24:00", "--minutes", "5"]\n')
+ (0, '["news-live", "--minutes", "5"]\n')
Ran 8 tests in 6.732s
FAILED (failures=2)
```
GREEN, the whole process file three times in a row at the real hour
(`python3 -m unittest discover -s tests -p 'test_supervise.py' -v`), and a fourth time on the committed tree:
```
run 1  Ran 12 tests in 13.797s  OK
run 2  Ran 12 tests in 11.070s  OK
run 3  Ran 12 tests in 11.411s  OK
committed tree  Ran 12 tests in 12.421s  OK
```

**The evening (ruling 11:10).** The file was run once with the clock question of every engine process answered as
17:00 New York: `python3 .../t3fix1/evening_procs.py 17:00`. It runs `tests/test_supervise.py` unchanged and only
swaps the program `start_engine` starts for `evening_child.py`, which is `engine_child.py` with `datetime.now` moved
in `news_live`, `journal`, `engine_child` and `postmortem`; the command line `start_engine` built goes through as it is.
```
Ran 12 tests in 12.998s
OK
engine processes started at a pretended 2026-11-11T17:00:00 New York: 9
their --until: ['23:59']
```
That the moved clock really reaches the engine's loop, and that the option is what makes the hour irrelevant:
- at a pretended 23:59 (the known ceiling) the four `EngineLock` tests fail, at 23:57 they pass
  (`evening_procs.py 23:59 EngineLock`: `FAILED (failures=4)`; `evening_procs.py 23:57 EngineLock`: `Ran 4 tests ... OK`);
- on a scratch copy with the line `options = ("--until", "23:59", *options)` taken out, at a pretended 17:00, the four
  `EngineLock` tests fail (`their --until: ['none']`, `FAILED (failures=4)`): the child has no default of its own any
  more, so nothing but `start_engine` keeps a test's engine alive after 16:05.

**Mutation check of the two pins** (a scratch copy, never the clone; `-k 23_59 -k as_they_came`): unmutated
`Ran 2 tests ... OK`; each of four planted defects fails exactly one pin:
`start_engine` adds no end; adds its end over the test's own (`if True:`); adds `24:00`; the child adds
`--until 24:00` again.

### Whole suite, before the commits

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, on the files as committed. Wall time 74 s. Last three lines:
```
Ran 567 tests in 74.044s

OK
```
567 = 566 + 1 (one pin became two). After the run: only the three paths changed, no engine child and no `sleep 60` left.

### What the next tasks should know

1. An engine child started with no `--until` now ends at 16:05 New York by the real clock, as the real engine does.
   Whatever starts the child outside `Procs.start_engine` (Task 8's `PARENT` script, the drills of Task 17, a parent
   that passes `supervisor.until_ny`) names the end it needs itself. This settles concern 1 of the first report the
   way the ruling says.
2. `QUICK = {"poll_seconds": 1}` stays in the child (the review's first Minor, for the controller to ratify). The other
   Minor findings are untouched: they were not on this round's list.
3. The author name on the two commits is the clone's configured git identity, as on the task's first commit. I changed
   no git setting.
