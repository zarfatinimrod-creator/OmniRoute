# Task 8d report - the priming poll keeps its eight threads, with a beat after each feed call

**Status: DONE.** One commit on `supervisor-build` in the gate clone, on top of `82b2036e`:

- `15c8c4e4` (`15c8c4e4327b3f8a7b38200d4de75b28a2b97b1a`)
  `fix(ai-trader): the priming poll asks its feeds in parallel again, with a beat after each one`

Start state checked first: HEAD `82b2036ed4dd49d77f6e3a542584355533d86b1b`, branch `supervisor-build`, tree clean.
After the commit `git status --short` prints nothing. The commit has the brief's message and no trailer or attribution
line. Nothing was pushed, no git setting was changed, `git stash` was not used, and no subagent was dispatched. Every
python command ran through the `safe` wrapper.

## What is built (`aitrader/news_live.py`, `poll_headlines`, +6 -7, and the import)

```python
with ThreadPoolExecutor(max_workers=8) as ex:
    asked = [ex.submit(_feed, s, self.session) for s in self.universe]
    if prime:  # this thread, never a worker, beats after each feed call it gets back: ...
        for _ in as_completed(asked):  # ... (a step's poll has its one beat after the poll)
            self._beat(self._phase)
    batches = [f.result() for f in asked]
```

- The priming poll uses the same pool as a normal poll: 8 workers, as before Task 8a. `max_workers=1 if prime else 8` is gone.
- Task 8a's worker wrapper `fed` is gone. The workers only call `_feed`. The calling thread takes the results as they
  complete (`concurrent.futures.as_completed`, now imported next to `ThreadPoolExecutor`). It writes
  `self._beat(self._phase)` after each result it receives. No beat is written from a worker thread.
- A step's poll (`prime=False`) is unchanged: eight threads, no beat per feed, and its one "poll" beat after the poll.
- `batches` keeps the universe's order (the futures are read in the order they were submitted), as `ex.map` did. The
  headlines are therefore handled in the same order as before.
- The stray blank line that Task 8a left before `def fed` is gone.
- `_run`'s docstring ("A beat follows ... each feed call of the priming poll") is still true and is unchanged.

No buy, sale or stop rule changed. Priming runs at a start, after git and before the loop, and sells nothing. `news_live.py`
is not loaded by the time machine (`backtest.py` does not import it).

## Tests (`tests/test_news_supervised.py`, class `FollowUps`)

1. **`test_a_start_beats_after_every_send_git_call_and_priming_feed`** (Task 8a's priming test). The name stays.
   - Unchanged: the scenario (no lock, a mismatch, one unsent row, 30 names, priming on, the 5 ms feed stand-in) and
     the assertion `len(seen) == 3 + 1 + 30`.
   - The old assertion `seen == sorted(set(seen))` covered every call. Its part over the feed calls is replaced, as
     the brief says:
     - `after - before >= 30`: the beats written while the priming poll ran, counted on each side of the call, are at
       least the number of feed calls.
     - `max(returned) < after`: each feed stand-in reads the beat count as it returns; every such count is lower than
       the count once `poll_headlines` returned. So a beat follows the last feed call.
   - Its part that is not about the feed calls stays:
     - `seen[:4]` is strictly rising: a beat between any two of the three sends and git.
     - `min(seen[4:]) > seen[3]`: a beat between git and the first feed call.
   - To read the count when the priming poll returns, the test wraps `NewsTrader.poll_headlines` in `primed`. `start()`
     captures it as `poll` and calls it for the priming poll. The step polls never reach it. `start()` itself is not
     changed.
2. **New: `test_priming_asks_its_feeds_in_parallel`**. It sets 16 names (`self.nt.universe`), and each feed stand-in
   waits 0.2 s (`threading.Event().wait`, as the file's other feed stand-in does). It calls
   `self.nt.poll_headlines(prime=True)` and asserts:
   - the poll took less than 1.6 s (eight at a time is about 0.4 s; one at a time is 3.2 s);
   - at least 16 heartbeat writes;
   - every beat was written by the calling thread (one assertion more than the brief lists; see "Departures").
   - `import time` was added to the file for `time.monotonic()`.

## TDD evidence

All commands were run from `<clone>/ai-trader` through `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`.
Output is in `<SCRATCH>/t8d/`.

**RED** (`red.txt`): `safe python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k FollowUps -v`, with the
engine of `82b2036e` and the new tests:

```
test_priming_asks_its_feeds_in_parallel (...) ... FAIL
FAIL: test_priming_asks_its_feeds_in_parallel (test_news_supervised.FollowUps.test_priming_asks_its_feeds_in_parallel)
    self.assertLess(time.monotonic() - t0, 1.6)   # eight at a time: about 0.4 s
AssertionError: 3.2309671049988538 not less than 1.6
Ran 10 tests in 3.586s
FAILED (failures=1)
```

This is the failure the brief expected: about 3.2 s, because the old engine asks the feeds one at a time. The restated
start test passed on the old engine, as it should. A serial poll with a beat from its one worker after each feed
also meets "beats >= feed calls and a beat after the last one".

**GREEN** (`green-final.txt`, final files): the same command gives all 10 tests `... ok`, `Ran 10 tests in 0.605s`, `OK`.

**Three times in a row, final files:**
- `tests/test_news_supervised.py`: `Ran 89 tests in 2.303s OK`, `2.241s OK`, `2.144s OK`.
- `tests/test_supervise.py` (the file that starts processes): `Ran 19 tests in 34.608s OK`, `35.042s OK`, `35.479s OK`.

Each run printed 5 lines, so the output is pristine. No engine child was left behind (`pgrep -af engine_child` found
nothing).

**Planted defects** (`mutate.py`, on a scratch copy `t8d/copy`, never the clone; `mutants2.txt` has the final tests).
Each defect was planted alone and the whole `FollowUps` class was run against it. All 7 were caught:

| Defect | Caught by |
|---|---|
| M1 no beat during priming | both tests |
| M2 one beat after all the feeds | both tests |
| M3 30 beats written without waiting for the feeds | the start test (`max(returned) < after`) |
| M4 serial priming (`max_workers=1 if prime else 8`) | the new test (time) |
| M5 beats from the workers after each feed (8 threads) | the new test (thread) |
| M6 beats from the workers before each feed | both tests |
| M7 one beat fewer (the last result gets none) | both tests |

**At any hour** (the 11:10 ruling): I added and changed no process test. The new test calls `poll_headlines` directly
and reads no clock. The changed test starts through `_run("23:59", ...)` as before. The whole file was also run on the
scratch copy, which is byte-identical to the clone's two files, with every clock the engine and the tests read moved
(Task 8a's `t8a/shifted_inproc.py`, read before use). It printed `Ran 89 tests ... OK` at each of these New York times:
- Wednesday 2026-11-11 at 17:00, 03:00, 09:31 and 23:58;
- Saturday 2026-11-14 at 12:00 (no session);
- Friday 2026-11-27, the 13:00 early close, at 12:30 and 13:30.

## Whole suite

`safe python3 -m unittest discover -s tests` in the gate clone, on the final files just before the commit. Wall time
93 s:

```
Ran 674 tests in 92.450s

OK
```

That is the base's 673 plus 1. An earlier run with the first version of the tests also gave 674 OK (98 s). The commit
holds exactly the tree these runs used. `ruff check --select F,E9,B` on the two files reports only the 3 old B905
findings (`zip()` without `strict=`), none of them in lines this task touched.

## Files changed

- `ai-trader/aitrader/news_live.py`
- `ai-trader/tests/test_news_supervised.py`

These are the brief's two paths and nothing else. Nothing changed under `state/`, `logs/`, `reports/` or `research/`.

## Self-review (`git diff 82b2036e..HEAD`)

Fixed before the commit:
1. Three new test lines were 121-127 characters wide. They were reworded, and the thread recorder became a small named
   function. The file has older long lines, but this task's lines stay within 120.
2. A first comment said "after each feed that answers". A feed that returns `None` (no answer) also gets a beat, so it
   now says "each feed call it gets back".
3. The old test's comment ("two feeds asked side by side would both see the same count") explained the strictly rising
   check over the feeds. That check is gone, so the comment was removed.

Checked and left as built:
4. **Brief, line by line.** Pool size 8 for priming: done. `as_completed` and a beat with the current phase after each
   result, from the calling thread: done, and pinned by a test. Restated assertion, name kept, other assertions kept:
   done. New test with 16 feeds, 0.2 s, under 1.6 s and at least 16 beats: done.
5. **One writer of `news_heartbeat.tmp`.** Only the calling thread beats during priming. Task 8a's reason for the
   single worker (two beats racing on the temporary file) does not come back.
6. **An exception inside a feed call** (`_feed` catches `requests.RequestException`, so only a programming error
   reaches this):
   - During priming, every result is still awaited and beaten, and `f.result()` then raises as `ex.map` did.
   - In a step's poll there is one small difference. `ex.map` cancelled the feeds not yet started when it met the
     exception. Now the `with` block waits for them, at most 10 s each across 8 workers, before the step's exception
     goes up. The step fails either way. I left it, because the extra code to cancel would guard against a defect that
     does not exist.
7. `self.session` is shared by 8 threads during priming again. That is how every step's poll uses it, and how priming
   used it before Task 8a.

## Departures from the brief

1. **The start test's strictly rising check over the non-feed calls.** The brief says the test's "other assertions
   stay". The old single assertion `seen == sorted(set(seen))` covered both the feed calls and the sends and git. Only
   its feed part is restated. Its non-feed part is kept as two assertions:
   - `seen[:4]` strictly rising;
   - the smallest feed count greater than git's count.
2. **The test reads the count at the priming poll's return through a `primed` wrapper** (`mock.patch.object` on
   `NewsTrader.poll_headlines`, inside the test). The brief's measure, "the count after `poll_headlines` returns",
   cannot be read after `start()`. `_run` writes more beats after priming (the loop's steps), and those would hide a
   missing beat after the last feed (M3 and M7 are caught only because of this).
3. **One assertion more in the new test:** every beat of the priming poll is written by the calling thread. It pins the
   brief's "No beat is written from a worker thread". Without it, M5 (beats from 8 workers, which can race on the
   temporary file) passes every test.
4. **The new test calls `self.nt.poll_headlines(prime=True)` directly**, the priming poll itself, and not a whole
   `_run`. The brief's measure is the priming, and a direct call keeps the stopwatch free of git, sends and the loop.

## Concerns

None that block. One note: the new test's limit (1.6 s) is four times the expected 0.4 s, so a loaded machine has a
wide margin. Over 7 runs of the file it took 2.1-2.6 s in total for 89 tests.

Scratch files, none in the clone: `<SCRATCH>/t8d/`
(`red.txt`, `green.txt`, `green-final.txt`, `file-*.txt`, `file-final-*.txt`, `sup-*.txt`, `sup-final-*.txt`,
`suite.txt`, `suite-final.txt`, `mutate.py`, `mutants.txt`, `mutants2.txt`, `shift.txt`, `copy/`).
