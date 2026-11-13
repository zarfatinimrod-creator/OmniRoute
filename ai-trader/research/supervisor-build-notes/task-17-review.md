# Task 17 review: the drill script

Reviewed: 74548ad3..eacdefc5 in the gate clone (3 commits; `ai-trader/scripts/drill_supervisor.py` new, 740 lines;
`ai-trader/tests/test_supervise.py` +74). The review package was read once, in one pass. Line numbers below are the
files at eacdefc5. No test was re-run; the clone was not changed.

### Spec Compliance

Compliant. Checked against the brief, `constraints.md`, `controller-notes.md` and rulings P1, P2 (with the
controller's addition), P3, P4, P5, P15, P29 of `rulings-10-28.md`:

- CLI: `DRILL... [--fast] [--rounds N]` with a b c d e f g all, `cloud DIR`, `cloud-check [--alive] DIR`
  (drill_supervisor.py:711-736). PASS/FAIL lines and exit 0 only when every drill passed (:610-629, :736).
- `guard(argv, environ, base_url)` is main's first statement (:713), before `helpers`/`aitrader` are imported; the
  module top level imports the standard library only, so `load_script` runs nothing. It pops all three phone variables,
  returns the topic for `phone --with-owner`, refuses `phone` without the flag, and exits 2 on a non-127.0.0.1 host
  (:102-118).
- Each drill: its own `mkdtemp`, state directories, config copies (and so locks), NtfyStub (:229-238). Parents' clock
  moved onto MORNING, 10:00 NY Thursday (:68, :271-278). Every parent and bare engine gets `--until 24:00` (P1 with the
  12:19 ruling; :69, :275, :282).
- Config copy pins all five switches false; drill b sets `hang_kill_enabled` true (P29; :198-208, :356).
- a: six dummy kills spaced `max(healthy, window/5) + 1` and only after the previous R1; then the engine kill under a
  second parent on its own state directory (P3); 1 s beat mark on all seven kills, 3 s look mark on the engine's
  `held[*].checked_at`; no trip; one R1 per kill (:305-350).
- b: one hang row, one R2, no R1 after `healthy + 2 ticks + 1` (P5; :353-373). c: max_restarts, one tripped row, one
  R3, rc 75 (:376-390). d: parent SIGKILL in the 30 s scorer stub, new parent at once, old engine dead, beat within
  5 s, no rc-3 exit and no R5c (:393-419). e: the four P4 clauses, verify_chain on all NEWS_CHAINED after every kill,
  the brief's FAIL text for a broken chain (:446-506). f: three names, 60 s / 2 s quote stubs (controller's P2
  addition), one stale_stops start row, one R6, no hang, one start (:579-604). g: Task 5's loop ported 1:1 at 50/20
  (compared with tests/test_supervise.py:257-286) on a temporary repo, `GIT_CONFIG_GLOBAL=/dev/null`, no stash
  (:509-576). cloud / cloud-check as the brief's rows (:632-708).
- The three plan tests exist under their names with the plan's assertions (test_supervise.py:1861, :1866, :1876);
  the added fourth (:1890) pins each `--alive` condition alone. P15: the report carries the seven PASS lines.
- Commits: plan message on the first; no trailer or attribution line (author per Ruling 34); `git status --short`
  empty; branch `supervisor-build`.

Departures I judged inside the brief: `--fast` also scales `backoff_first_seconds` 0.1, `backoff_max_seconds` 2 and
`loop_seconds` 0.05 (:74-75). The brief asks for "a scaled config that keeps their order"; with the real 1-2-4-8 s
back-off drill c's five crashes cannot fall inside a 10 s window (arithmetic checked: restarts at 1, 3, 7, 15, 31 s), so
the plan's own test could not pass without it, and backoff_max 60 against healthy 2 would break the order. See Minor 1.

Cannot verify from this diff:
- That drill e's judging path (mismatch row, E1 body) works: no 20-round run met a mismatch; only the implementer's
  planted experiment exercised it. Check at Task 20's 200-round run, or ask for a unit test that plants the row.
- Drills b, d, e, g and both cloud checks at the real numbers, and the cloud flow on a real session (Task 20).
- Drill a at the real `loop_seconds` 0.5 against the 1 s mark (report concern 1: 0.57-0.91 s measured).
- The by-hand `all --fast --rounds 20` run and the 3x GREEN runs (not re-run, per the dispatch).
- Task 12's R6 on an unknown stamp saying "0 שניות" (report concern 5): owner-facing, outside this diff; the
  controller should rule on it. Drill f no longer reaches that path (Minor 4).

### Strengths

- The phone guard is first and complete; the module imports nothing of the project at import time, so the plan's
  `load_script` test is honest.
- Every signal to a heartbeat pid goes through `signal_child` (:181-185), which refuses a pid whose command line is no
  stub child: a reused pid cannot be hit.
- `cloud-check --alive` reads the flock holder from /proc/locks with the reviewed `supervise.FLOCK_ROW` (:647-654),
  following the controller's note that the lock, never its text, decides; the test fixture plants a lock file whose
  text names a live pid to prove it.
- Drills fail loudly on a vacuous pass: e with no trade, f with an unmeasured stale age, any drill whose engine child
  tripped its tripwire.
- Drill e's mismatch predicate is written independently of the engine's `start_checks` (:434-443), so the drill
  checks the engine rather than restating it.
- The self-review found and fixed two real defects before review (cloud-check reading an earlier parent's sup_stop;
  drill f passing on the unknown-stamp path rather than on aging).

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

1. drill_supervisor.py:74-75 - `--fast` scales three numbers the brief does not list. The back-off is required (above)
   but the controller notes say a plan test that cannot pass as written is reported BLOCKED, not resolved in place;
   it needs the controller's ratification. `loop_seconds` 0.05 also means the unit test no longer measures the real
   tick against the absolute 1 s mark: `test_the_fast_drills_pass` passes with 0.32 s margin while the real tick
   measures up to 0.91 s. Task 20's real-number run is the only check of the spec 11.2 mark. The fast config still
   breaks the real order for `hang_term_grace_seconds` (5 > hang 4), `start_grace_seconds` (60 > 4) and
   `planned_stop_grace_seconds` (120 > window 10), as the plan's own list does. Fix: controller ruling; name the
   ratified list in the FAST comment.
2. drill_supervisor.py:280-282, :610-629 - a bare engine child of drills e and g outlives the drill when the drill
   process is stopped from outside. Python's default SIGTERM runs no `finally`, so `d.end()` does not run. The bare
   child has no PDEATHSIG and `--until 24:00` never comes, so it polls stubs on its /tmp directory forever. Parents
   are safe: they stop with "orphaned". This is plausible at Task 20, which must run `all` as a tracked background
   command. Fix: in `main`, a SIGTERM/SIGHUP handler that raises SystemExit, so `run`'s `finally` kills what the
   drill started.
3. drill_supervisor.py:622-623, :517, :555 - the FAIL line prints an exception's text (`{type(e).__name__}: {e}`), and
   so do git's stderr and the merge thread's errors. Constraint 11 says error paths carry the class, never the text.
   Real exposure today is nil: `guard` has removed the owner's topic before anything runs, and every URL is
   127.0.0.1 with a made-up topic. But Task 21 adds the `phone --with-owner` mode, which holds the real topic, to this
   file. Fix: print the class only (keep the drill's own `Failed` text, which it composes itself), or have Task 21
   route its mode around `run`.
4. drill_supervisor.py:583-587 - drill f now seeds a heartbeat stamped "now". The start row therefore comes from that
   adopted stamp aging past the threshold, and the drill tests a restart with slow quotes, not a cold start. That is a
   defensible reading of P2. But the cold-start path, where Task 12's R6 reads "0 שניות", is now drilled nowhere. Say
   so in the drill's comment or in the hand-off to Task 20.
5. drill_supervisor.py:337 - the look mark is `max(stamps) - t0`, with no lower bound. A stamp from before the kill
   would pass as a negative look. It cannot happen in this scenario: `_covered` starts empty in a new process, and
   the catch-up skips a name entered today with no `news_entry.at`, checked at news_live.py:1080-1084 and :606. Still,
   `min(stamps) >= t0` costs nothing. The measure reads the look's start, not the mtime the stamps reached the file,
   which is the brief's literal reading.
6. drill_supervisor.py:612 - `Drill(...)` is built outside the `try`. If `NtfyStub()` fails, the exception ends `main`,
   the later drills never run, and the mkdtemp directory leaks.
7. drill_supervisor.py:469 - drill e's `random.Random()` is unseeded, and a FAIL line does not print the seed. A failed
   round cannot be replayed.
8. drill_supervisor.py:94-99 duplicates `PARENT_WRAPPER` (test_supervise.py:726-731) verbatim.
   drill_supervisor.py:692-695 nearly duplicates `replaced` (:157-162). Both are small. A shared helper under
   tests/helpers would keep the wrapper in one place.
9. drill_supervisor.py:713 - `guard` gets the constant `LOCAL`, not a config copy's address. It is equivalent by
   construction, because `config_copy` writes `f"{LOCAL}:{port}"` (:206). But a later edit of `config_copy` would not
   be caught by the guard. An assert on the host in `config_copy` would close it.
10. drill_supervisor.py:657-665 - `cloud-check DIR` fails on any process, its own ancestors included, whose argv names
    DIR, for example a `timeout 60 python3 ... cloud-check DIR` wrapper. It is fine under the Bash tool's `bash -c`
    (one argv string) and under the `safe` wrapper. On a missing DIR, `flockable` (:683) raises FileNotFoundError and
    prints a traceback. The non-`--alive` mode has no automated test.
11. drill_supervisor.py:218 - the -3% stop is the literal 0.97 rather than `news.stop_loss_pct`. It is fixture data
    and mirrors the reviewed `Procs.write_book` (test_supervise.py:112).
12. Report accuracy: "3.5 s fast" for the kill gap is wrong. The code gives `max(2, 10/5) + 1` = 3 s. The RED output
    covers the plan's three tests only, and the fourth test's failing run is shown through mutations instead.
13. Process, not code (report concern 6): a `pkill -9 -f "engine_child.py --state-dir /tmp/tmp"` could have hit
    another session's test engines (Hard Rule 22 spirit), and three plain `python3` calls ran outside the mandatory
    `safe` wrapper. Both were disclosed. The controller may want to restate the rule for Task 20/21 implementers.

Checks run (one per named risk):
- Adopted per-name stamps faking drill a's look: news_live.py:606 (`_covered = {}`), :1677-1711 (`held[*].checked_at`
  comes only from `_covered`), :1080-1084 (catch-up skipped for today's entry with unknown time). No risk here.
- Torn heartbeat reads giving a spurious KeyError on `["pid"]`: dummy_child.py:66-67 and journal.save_json both write
  tmp + rename. No risk.
- Tripwire check looking in the wrong place: engine_child.py:177 writes `<sent>.tripwire` into the drill's tmp, which
  `Drill.tripped` globs (:300-302). It matches.
- Untested `cloud-check DIR` attributes: supervise.py:75-81 has `lock`, `uptime`, `engine_lock`; `FLOCK_ROW` at :547.
- Drill d waiting for phase "quotes": the reviewed SaidBeforeTheKill test (test_supervise.py:285) uses the same
  phase as "inside the scorer".
- Child environment under the drill's PARENT: same as the tests' PARENT_WRAPPER (no `env=`; the parent's own
  environment is `clean_env` plus a made-up topic; the engine child is behind its tripwire).
- Back-off arithmetic for the drill c departure: verified against config.json's supervisor block.
- Commit hygiene: `git log` 74548ad3..eacdefc5 has no trailer; `git status --short` is empty.

### Assessment

Task quality: Approved.

Every requirement of the brief and its rulings is built and pinned by the plan's tests. The findings are robustness,
coverage and hand-off points, none of which makes a drill's verdict wrong. The one item the controller must act on is
ratifying the three extra `--fast` numbers (Minor 1). Minor 2 should be fixed before Task 20 runs `all` as a background
command.
