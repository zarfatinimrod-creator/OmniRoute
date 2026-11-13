# Task 14c review: base bf37c23d, head 5640a80b (one commit)

The review package ran with exit 0 (1 commit, 53131 bytes) and is my view of the change. Brief, constraints.md,
controller-notes.md and progress.md Rulings 50 and 54 read. I did not re-run the suite. I ran one stdlib experiment
in the scratchpad (below). I made no change to the clone.

### Spec Compliance

Compliant on everything I could check from the diff. Every item in the brief has its hunk, and every named test exists
with the assertion the brief gives:
- Item 1, `aitrader/uptime.py:231-236`: no R4c, and nothing added to `reported`, when a day's R4/R4b row with `sent` true
  has `t >= began`. `test_one_outage_gives_one_line_no_r4c_after_the_r4_that_told_it` covers three cases:
  - R4 sent true: R11 only, at 25 minutes. A double count would give a negative remainder and no R11, so this
    assertion also proves the R4 is counted once.
  - No R4 row: R4c + R11.
  - An R4 row with sent false: R4c + R11.
- Item 2:
  - `supervise.py:448` puts `s` into gap_line's fields. Both say call sites carry it in `extra`: the pause R4 and the
    first-`up` R4/R4b. A grep finds only these two callers of `gap_line`.
  - `uptime.py:224`: `s`, or else `m * 60`, keyed by id. R4c adds `run` seconds.
  - `uptime.py:238` uses Ruling 54's `round((unprotected_s - reported_s) / 60) >= 1`. `{m}` stays
    `round(unprotected_s / 60)`.
  - Tests: 40 s + 210 s gives R11 with " 4 דקות ". A fully reported day gives none. A row with only `m` counts.
    `test_the_row_of_r4_carries_its_seconds` checks that `s` is numeric and equals `open_seconds` up to the up row's `t`.
- Item 3, `__main__.py:31-33` in the diff: exit 2 and one stderr line. Tested for 0 and -1.
- Item 4, `scripts/drill_supervisor.py`:
  - Handlers for SIGTERM and SIGHUP, exit 1 on an interrupted run.
  - `Drill()` and its directory are built inside the `try`.
  - FAIL lines carry a class name or a `Failed` text built from the drill's own values (Ruling 54). git's output goes
    to DEVNULL.
  - `--seed` option, chosen at the start when not given, printed in every FAIL of drill e.
  - The lower bound on the look mark (`:359`).
  - The three named tests are present.

Cannot verify from this diff:
- R4c is suppressed only when the close slot computes `close_lines` after the come-back R4's alert row is written.
  When the slot runs relative to 16:00-16:22 belongs to Task 20 and the slot files.
- The GREEN runs (3x per file, 840-test suite, seven PASS lines in the drill run) are reported, not re-run here.
- Task 20's hand-off note (R11 counts `s`; rows from before 14c count `m * 60`) belongs to a later task.

### Strengths

- `close_lines` stays small and readable. `told` feeds both the R4c suppression and `reported`, so the two cannot drift
  apart. The `m * 60` fallback keeps older rows readable.
- `s` reaches the alert row through the same `extra` path as `m`. No template names `{s}`, so the owner's text cannot
  change.
- The signal test is robust:
  - It reads the engine's pid from the drill's own heartbeat file and the other pids by parent pid, never by name.
  - It checks the start time to guard against pid reuse.
  - A read-only `/proc` cmdline scan for the test's own mkdtemp catches an engine started after the snapshot.
  - Its cleanup kills only pids it recorded.
  - The implementer showed RED for the changed test by removing the handler lines.
- Drill g's git timeout and the thread's failure text now carry the drill's own values (round, call, limit) and nothing
  from git or an exception.
- `run` restores the caller's mask (`SIG_SETMASK`) instead of unblocking STOPS unconditionally.
- No trading rule, config.json, state file or time-machine file is touched. No new literal threshold: `/ 60` is a unit
  conversion and `>= 1` is Ruling 54's minute.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

1. `scripts/drill_supervisor.py:669-677` (and the claim at `:646`): the `pthread_sigmask(SIG_BLOCK, STOPS)` in `run`'s
   `finally` does not hold back a SIGTERM or SIGHUP while another thread lives. During `d.end()` the NtfyStub's
   `serve_forever` thread is always alive: `d.stub.stop()` comes after `d.end()`, and the thread was created with
   STOPS unblocked.
   - **Why it fails.** The kernel delivers a process-directed signal to a thread that does not block it. CPython then
     runs the Python handler in the main thread at its next bytecode, whatever the main thread's mask.
   - **Check I ran.** `scratchpad/r14c/mask.py`, stdlib only, outside the wrapper's scope and touching nothing:
     - Main thread blocks SIGTERM, no other thread: "cleanup finished with SIGTERM held back".
     - Same with one daemon thread started before the block: "cleanup cut short by SIGTERM at step 0".
   - **Failure scenario.** A drill raises `Failed` or another exception before the `d.end()` inside the `try`. Its
     `finally` blocks STOPS and starts killing `d.procs`. A first SIGTERM from the session's background-command
     teardown arrives during that loop. The handler raises `Interrupted` inside `d.end()`. The procs after that point
     are never killed: a bare engine with `--until 24:00`, or a parent. The run then exits 1 with those processes
     still alive.
   - **Why it matters.** The window is milliseconds. But it is the exact failure Ruling 50 (4) exists to remove, and
     the docstring ("with STOPS held back meanwhile, so that a signal cannot cut that short") and the report both state
     a guarantee the code does not give. A later step added to this cleanup would be trusted to be protected and would
     not be.
   - **Fix.** Make the cleanup safe against `Interrupted` instead of relying on the mask. For example,
     `try: cleanup() except Interrupted: cleanup(); raise`. The handler has already set SIG_IGN for both signals, so
     the second pass cannot be cut short. Or have the handler read a module flag that `run`'s cleanup (and `popen`, see
     Minor 1) raises: while the flag is up, it records the signal and returns, and the code raises `Interrupted` once
     the flag drops. Then remove the mask, or keep it only with a correct comment.

#### Minor (Nice to Have)

1. `scripts/drill_supervisor.py:273`: the `ponytail:` window inside `Popen` (a child forked but not yet in `d.procs`)
   is disclosed with its upgrade path and is milliseconds per start. The controller has not ruled on it yet; Ruling 54
   accepted only drill g's in-flight git call. The flag form of the fix for Important 1 closes this window too, at no
   extra cost.
2. `aitrader/uptime.py:232`: the brief's rule compares only an R4 row's `t` with `began`.
   - **Failure scenario.** An R4 for an earlier outage whose `sent` true row is written late (ntfy retries, or a fall
     seconds after its `up`) at or after a new trailing outage began. That R4 suppresses the trailing outage's R4c.
   - **Impact.** R11 still fires, because the trailing seconds stay unreported, but the R4c line ("from X to the close,
     open: ...") is lost.
   - Plan-mandated. A tighter rule would also require the R4's own span to reach `began`.
3. `aitrader/uptime.py:224`, pre-existing and not new here: an R4 sent the next morning carries yesterday's open seconds
   in `s`. Counted against today's `unprotected_s`, it can hide other untold seconds of today. The old `m` sum did the
   same.
4. `tests/test_supervise.py:1519`: `assertNotIn(f"{s:g}", row["text"])` is a weak guard (it only checks that one digit
   string is absent). The real guard is that no R4 template names `{s}`. Acceptable.
5. `tests/test_supervise.py:2149`: the `/proc` cmdline scan for the test's directory is a read-only name match. The
   brief asked for pids to be identified "not by a name pattern". Here it is an extra assertion, not how pids are
   chosen or killed. Disclosed, and fine.
6. Reported suite output carries `[news] ...` lines from older engine tests. They are pre-existing, and the new tests
   print nothing.
7. Build-wide, not this task: every build commit, this one included, has the author `Claude <<email>>`,
   the clone's configured identity. The message itself carries no attribution line.

### Assessment

Task quality: **Needs fixes.**

Items 1-3 are correct and well tested, and item 4 meets its brief on the main paths. But the cleanup's signal "hold"
does not work in the drill script's real threading configuration (verified). A first SIGTERM or SIGHUP during a failed
drill's cleanup can still leave started children alive, while the code claims it cannot. The fix is a few lines.
