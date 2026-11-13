# Task 14c, fix round 1: re-review

Fix diff: 5640a80b..d8955a29 (one commit, `ai-trader/scripts/drill_supervisor.py` and `ai-trader/tests/test_supervise.py`),
package `review-task-14c-fix1.diff`. I read the code at d8955a29 with `git show`. The review was read-only and I re-ran no tests.
I disassembled `run` once on the clone's Python 3.13.18 to check the implementer's claim about bytecode.

### Finding Verdicts

**F1: ADDRESSED.**
- **Mask gone.** The `pthread_sigmask(SIG_BLOCK, STOPS)` / `SIG_SETMASK` pair is removed from `run`'s finally
  (`drill_supervisor.py:679-689` at d8955a29). No `sigmask` remains anywhere under `ai-trader` (`git grep`).
- **New flag.** `hold: list[str] | None = None` (`:136`). The handler `interrupted` (`:139-148`) still sets SIG_IGN on both
  STOPS first. While `hold` is a list it appends the signal name and returns; otherwise it raises Interrupted as before. CPython
  always runs Python handlers in the main thread, so it no longer matters which thread the kernel delivers `kill PID` to.
  That thread question was the root of F1, and the flag removes it.
- **Nothing in the cleanup can raise Interrupted now.**
  - `hold = []` is the finally's first statement (`:679`). The inner `finally` resets `hold` with `noted, hold = hold, None`
    (`:687`). `raise Interrupted(noted[0])` (`:689`) only runs after `d.end()`, `d.stub.stop()` and the rmtree have finished.
  - Blocking calls in the cleanup get EINTR when the handler runs. Under PEP 475 they are retried after it returns: `p.wait()`
    (waitpid), the stub's `shutdown()` (lock acquire) and `time.sleep`.
- **Disassembly (Python 3.13.18) confirms the entry claim.**
  - Normal entry: `STORE_FAST passed`, `BUILD_LIST`, `STORE_GLOBAL hold` (offsets 384-388).
  - Exception entry: `PUSH_EXC_INFO`, `BUILD_LIST`, `STORE_GLOBAL hold` (918-922).
  - Both except clauses jump to offset 386 with `JUMP_BACKWARD_NO_INTERRUPT` (678, 798).
  - None of these checks the eval breaker. Even where one does, a handler that runs before `hold = []` raises Interrupted in
    the try or except part. The finally then cleans up in hold mode with SIG_IGN already set. So the guarantee does not depend
    on that bytecode detail.
- **Order and exit code.** A stop noted during the cleanup is raised after it, goes to `main`'s `except Interrupted` (`:804`),
  rc 1, and no further drill starts (the brief's "exit with 1 for the interrupted run").
- **Docstrings.** `run`'s docstring (`:651-655`) and `interrupted`'s docstring (`:140-142`) now describe the flag, not the mask.
- **New test.** `test_a_stop_while_a_failed_drill_cleans_up_cuts_nothing_short` (`test_supervise.py:2159-2177`, script
  `STOP_IN_CLEANUP` at `:2129`) targets F1's exact scenario.
  - A drill raises Failed with two real children. A stand-in first in `d.procs` sends a process-directed SIGTERM from inside
    `Drill.end` in the cleanup.
  - The asserts: both children dead, rc 1, the next drill never started, exactly one FAIL line.
  - The "second drill started" assert also catches a stop that is noted but never raised.
  - Each child counts only while one of its argv elements exactly equals the test's mkdtemp path, which guards against pid reuse.
  - The evidence file `r14c-fix1/red.txt` shows it failing on 5640a80b's script with both children alive (`[2566, 2567]`).
    `r14c-fix1/drill_fixed.py` is byte-identical to d8955a29's script (`cmp`).

### New Breakage in the Fix Diff

None.

I checked these paths:
- A stop that is already on its way as Interrupted from the drill body: SIG_IGN is set, nothing is noted, and the original
  propagates.
- An exception raised by the cleanup itself: the inner finally still resets `hold`, so the flag never leaks past `run`.
- A stop after `hold` goes back to None: the handler raises from the finally, after the cleanup.
- `cloud` mode: it does not use this handler path.
- Tests that call `run` directly without handlers: the flag has no effect there.

The new test launches the script like the existing `Drills.drill` helper: `no_phone.clean_env`, cwd `ai-trader`, and the
script's own `guard()` first.

### Out-of-Scope Observations

- **One-instruction window in the drill body can hang the cleanup** (Minor, pre-existing, the implementer's declared
  remaining limit, not in the fix diff). An Interrupted raised in the drill body can land in `Popen._internal_poll` right after
  `_waitpid_lock.acquire(False)` returns and before its `try`, which leaves the lock held.
  - In 3.13 a CALL ends with a periodic check, so the window is real.
  - The cleanup's `p.wait()` on that process then blocks forever. SIG_IGN is already set, so only SIGKILL ends the script, and
    the processes after that one in `d.procs` are not killed.
  - Unlike the `Drill.popen` window, the code has no `ponytail:` comment for it.
  - The new `run` docstring ("every process ... is killed ... by whatever path") is true of the cleanup but does not mention
    this limit.
- **No line says the run was stopped.** A stop noted during the cleanup of a drill that already printed PASS (or a FAIL for its
  own reason) ends the run with rc 1. The mask design behaved the same way, so the fix did not introduce it.
- **The `Drill.popen` comment is stale** (`:281-283`, review Minor 1, not on the fix list). It still names "a flag the handler
  reads" as the future way to close its window. That flag now exists, so the window can be closed with it later.

### Verdict

F1 is ADDRESSED. The fix introduced no new breakage. The fix report carries test evidence: the covering test's name, the RED
and GREEN command and output, `test_supervise.py` run 3 times (138 tests, OK each time), the whole suite (841 tests, OK) and a
drill run (7 PASS lines). The evidence files are in `scratchpad/r14c-fix1/`.
