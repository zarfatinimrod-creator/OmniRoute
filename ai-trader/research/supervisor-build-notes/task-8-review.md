# Task 8 review - a planned stop, and an engine that dies with its parent

Diff: cbfc4686..3366396f (2 commits), gate clone `sup`. I read the review package once (`review-task-8.diff`); I did not
re-run the suite. Focused checks outside the diff are listed under each verdict.

### Spec Compliance

Not compliant. Two departures need the controller's ruling. Everything else the brief lists is built.

- Every file the brief lists has its hunk: `aitrader/news_live.py`, `aitrader/__main__.py` (`--supervised PARENT_PID`,
  int, handed to `run` by keyword), `config.json` (`news.sleep_slice_seconds` 0.5, plus one sentence in `news._note`),
  `tests/test_news_supervised.py` (class `PlannedStop`), `tests/test_supervise.py` (class `EngineStop`).
- The interfaces match the brief: `STOP` is a `threading.Event`; `request_stop(signum=None, frame=None)` only sets it;
  `_set_pdeathsig()` calls prctl(1, SIGKILL) through ctypes on Linux and does nothing elsewhere;
  `run(..., supervised=None)`; `_run(..., *, locked=True, supervised=None)`.
- `run` clears `STOP` first (news_live.py:1723). It installs `request_stop` for SIGTERM and SIGINT on the main thread
  only (1726), and the `finally` puts the earlier handlers back, with `SIG_DFL` in place of `None`. Verified.
- Order under `supervised=PID`: `_set_pdeathsig()`, then the `getppid` check (one printed line, 143), then the lock.
  This is the race-free order. Verified, and `test_a_wrong_parent_pid_leaves_with_143_before_the_lock` asserts that no
  lock file exists.
- The loop top: a changed parent pid sets `STOP`, and a set `STOP` breaks with code 143 (1841). The wait is slept in
  slices of `news.sleep_slice_seconds` and stops slicing once `STOP` is set (1870). After the loop: `save`, then
  `drain_trial`, then `_beat("stopping")` (1878), then return 143. Heartbeat `supervised` = `nt.supervised`. Verified.
- `_step` once `STOP` is set: no further headline quote and no further batch. The headlines left in `_pending` come
  out of `self.seen`, and `_pending` is emptied, so they get no `step_failed` row (baseline fact (b)). The end-of-step
  look, `drain_trial`, `save` and the "idle" beat are unchanged. Verified (1509-1516).
- Exit 6 sends R5d only when `supervised is None` (the bare engine). Verified.
- All seven named tests exist under their names with the brief's assertions. One of them has a changed final
  assertion (Issue I2). Six more tests cover behaviour the brief requires: extra coverage, not extra features.
- **Extra (Issue I1):** news_live.py:1505 skips the between-batch stop look once `STOP` is set. The brief does not say
  this, and the constraints keep "the three stop looks of a step" unchanged.
- **Changed test (Issue I2):** test_supervise.py:341 asks for the lock again and again until the second ends. The brief
  asks once, right after the child is dead. The controller notes say to stop with BLOCKED in that case; the
  implementer departed and flagged it instead.

Focused checks I ran:
- Risk: an in-process test sets PR_SET_PDEATHSIG on the test runner itself. Checked: every `run(..., supervised=...)`
  call in the diff replaces `_set_pdeathsig`, and `_WatchedStarts.start(**kw)` (test_news_supervised.py:857-862)
  calls `_run` directly, which never calls it. Safe.
- Risk: the first-look test's `quote_delay_s` is silently ignored, so the signal never lands inside the look.
  Checked: `tests/helpers/engine_child.py:15,79` sleeps `quote_delay_s` inside every `live_price`. The key works.
- Risk: the tripwire file of the PARENT's engine is not the one `tearDown` checks. Checked: `Procs.state` is
  `tmp/state` and `sent_file` is `tmp/sent.jsonl`; PARENT passes `dirname(state)/sent.jsonl`. They match.
- Risk: a 143 is overwritten in the loop. Checked: only the `ChainBroken` branch sets `code` (4, then break), and it
  cannot run after the 143 break. Safe.

Cannot verify from this diff:
- R5d for a supervised engine that leaves with 6 is sent by its parent (Task 13). Until then no parent exists, so
  nothing is lost.
- Report concern 3: `PR_SET_PDEATHSIG` fires when the parent's THREAD that forked the engine ends. Task 10/11 must
  start the engine from the parent's main thread (or one that lives as long as the parent). Check this in Task 11's
  review.
- Hour independence (ruling 11:10 UTC): no run with a faked evening clock was made. The report's argument holds on
  reading: `start_engine` adds `--until 23:59`, PARENT passes `24:00`, the session comes from the scenario, and the
  in-process tests use "23:59" or return before the loop. The known ceiling is 23:59-00:00 for the three
  `start_engine` tests.
- The whole suite was run before commit 1 (650 OK, 98 s). After commit 2 (one test only) only its file was re-run
  (79 OK). The landing gate re-runs the suite.

### Strengths

- `run`/`_run` follow the brief's interface exactly. The pdeathsig, getppid, lock order is right. The handlers are
  scoped to the call, set on the main thread only, and restored, with the `None`-handler trap handled
  (news_live.py:1723-1752).
- Every new condition in `_step` and the loop is a no-op while `STOP` is clear. Read line by line, the trading and
  stop paths are unchanged with no stop asked. No literal threshold was added; `sleep_slice_seconds` is in
  `config.json` and `DEFAULTS`.
- The take-back clears both `self.seen` and `_pending`. `test_a_headline_taken_back_is_in_no_file_so_the_next_engine_logs_it_once`
  proves it on disk: there is no `news_seen.json` entry and no `news_seen_log.jsonl` row, not even `step_failed`.
- The process tests are real. The reported mutation (`_set_pdeathsig` made a no-op, so the kill-9 test fails) shows
  the test depends on the kernel call, not only on the loop-top check.
- `end_engine_child` checks `/proc/<pid>/cmdline` before SIGKILL, so it never signals a reused pid. The PARENT gets
  `clean_env()`, and its child gives its stdout and stderr to DEVNULL and runs behind the tripwire.
- No new owner line, no URL or exception text in the new print, and no test reaches the phone, the network, the model
  or the live state.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

**I1. news_live.py:1505 - the between-batch stop look is skipped once STOP is set (beyond the brief).**
- What: `and not STOP.is_set()` was added to the between-batch look's condition (report, departure 6). The brief names
  three changes once `STOP` is set: no further quote, no further batch, and the take-back. It also says the end-of-step
  look runs "as always". The constraints list "the three stop looks of a step" as unchanged, and this review's rubric
  names "anything that ... skips ... a stop look beyond what the brief says".
- Why: what I checked shows no harm. After the batch whose scorer call saw the signal, the next statements are the
  loop's `break` and the in-memory take-back (1509-1516). The unguarded end-of-step look then runs at the moment the
  skipped look would have run. So no look is delayed and no sale changes. But it is an unrequested change to a stop
  look, and only the controller can accept one.
- Fix: either remove `and not STOP.is_set()` from 1505, which restores the brief exactly (cost: one redundant look on
  a planned stop that lands mid-step), or the controller ratifies it as built (spec 5.3: "one call plus one look").

**I2. test_supervise.py:327-341 - the brief's kill-9 test was changed instead of reported BLOCKED.**
- What: in the brief, after `wait_for(dead(child), timeout=1)` there is one non-blocking `flock` that must succeed. The
  test now sets one 1 s deadline from the kill. `dead(child)` must happen inside it, and then
  `wait_for(self.lock_is_free, ...)` keeps asking for the lock until that second is over. The report says the literal
  form failed 3 times out of 3: the engine's main thread shows as a zombie (which `Procs.dead` counts as dead) before
  the other threads have released the lock.
- Why: the change keeps spec 5.3's requirement ("gone within 1 s and the lock is free") under the same 1 s bound,
  measured from the kill. The explanation is plausible: the group leader shows state Z while sibling threads are
  still in `do_exit` and hold the shared files table. But it is a changed assertion of a named test. The controller
  notes say: "Never weaken ... an assertion ... stop and report BLOCKED with the exact contradiction".
- Fix: a controller ruling. I recommend ratifying the polled form as built, since the brief's form tests the kernel's
  teardown order and not the engine.

#### Minor (Nice to Have)

- news_live.py:1870-1872: the wait counts down by the nominal slice, not by the clock, so any oversleep in each of up to 40 slices
  adds up. A `sleep_slice_seconds` of 0 would loop forever on `time.sleep(0)`: no step and no stop look again. A
  negative value raises `ValueError` outside the loop's `try`. A loop on a monotonic deadline fixes the drift and the
  zero case without a literal: `end = time.monotonic() + left`, then sleep `min(end - now, slice)` until `STOP` is set
  or `end` passes.
- news_live.py:1482: when `STOP` is set before the poll (a signal during the top look or the queue), the poll still
  runs, and everything it returns is then taken back. That is wasted time inside the parent's grace. The brief does not
  ask for a skip, so this is noted, not required.
- news_live.py:1876 / report concern 5: after the close, the worst case is a scorer call in flight (90 s) plus
  `drain_trial`'s `verify_timeout_seconds` (60 s) = 150 s. That is more than the 120 s grace, not "inside" it as the
  report says. The book is saved before `drain_trial`, so a SIGKILL there loses only the "stopping" beat. Carry this
  to Task 11.
- news_live.py:101: prctl's return value is not read, so a failed request is silent. A one-line log of a nonzero
  return (no exception text) would show it.
- test_news_supervised.py:1030 (plan-mandated `supervised=1`): if the test runner's parent is pid 1 (a container
  init), the start goes past the check, and the test errors on the `NewsTrader` stand-in. It cannot run an engine.
  `os.getppid() + 1`, as `PlannedStopOfTheLoop` uses, is robust.
- test_supervise.py:332: the comment says "the parent first, then its engine", but `addCleanup` runs last-in first-out,
  so `end_engine_child` runs before `parent.kill`. The behaviour is harmless; the comment is inverted.
- test_supervise.py:327: `tearDown` runs before the cleanups. If the kill-9 test fails, `tearDown` reads the tripwire
  file and deletes the temporary directory while the engine may still be alive. This only matters on the failure path.
- Report: the suite's printed lines (`[news] engine started ...`, `[journal] skipped unreadable line ...`) come from
  older test files. This task's two files print nothing, so this task added no noise.

### Assessment

Task quality: **Needs fixes.** The engine change is correct and careful, the stop path is unchanged while no stop is
asked, and the tests prove real behaviour. Two departures need a ruling: an unrequested skip of the between-batch stop
look (I1, a one-line revert or a ratification) and the kill-9 test's changed lock assertion (I2, ratification
recommended). No other code change is required.
