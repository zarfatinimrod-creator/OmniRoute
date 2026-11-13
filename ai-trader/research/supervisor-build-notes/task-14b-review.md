# Task 14b review - base eacdefc5, head 81bd1283

Review package: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-14b.diff` (1 commit, 6 files,
+227/-33), read in one pass. Read-only on the gate clone; HEAD = 81bd1283, `git status --short` empty. No test re-run.

### Spec Compliance

Items 1, 2, 3, 5, 6 and 7 are implemented as the brief asks. One departure needs a controller decision:

- `ai-trader/tests/test_supervise.py:772-790` (item 4): the brief says `main(["--status", "--clear-halt", ...])` and
  `main(["--watchdog", ...])` each **raise `SystemExit` with code 2**. The test asserts `main(...) == 2` plus argparse's
  refusal text instead. The brief's form cannot pass: `main` has caught argparse's `SystemExit` and returned its code
  since before this task (`supervise.py`, unchanged lines `except SystemExit as e: return e.code ...`). The CLI still
  exits 2 through `sys.exit(main())`, and the substitute is stronger: it checks the message and that nothing was written
  to the state dir. But the controller notes say a contradiction between a brief's test and the code means stopping
  with BLOCKED, not swapping in another assertion. The implementer did report it openly ("departed" 1, concern 4). The
  root defect is in the brief. Fix: the controller ratifies the `== 2` + message form. No code change is recommended.

Checked against the brief, item by item:
- Item 1: `supervise.py:131-147` (diff). `_held_now` returns `None` from the same except clause (missing, not JSON, a
  list, no `positions` map, a position that is no mapping), `{}` only for a book that reads, and never falls back to
  another pid's beat.
- Item 2: `ownerlines.py:31-53` (diff). `WORDS["held"] = {"none", "unknown"}` is the module's own pattern. I grepped
  every caller of `held_text` / `_held_now`: supervise.py 647 (R5e), 900 (`say`), 1002 (pause R4), 1079 (R2.off),
  1228/1230 (R3*, R5a/b/d), and uptime.py 226 (R4c). All of them pass the value straight to `held_text`, and none
  calls `len()` on it or iterates it. Tests (a)-(c): `test_r5e_says_the_positions_are_unknown_when_the_book_cannot_be_read`
  checks the full R5e text, so "never אין פוזיציות" holds. Test (d): `test_held_text_says_unknown_for_none_and_no_positions_for_an_empty_book`.
- Item 3: `timeout=` on the check; `TimeoutExpired` prints one line naming the seconds and returns 1. The key is in
  `config.json`, in `NUMBERS` and in the `_note`. On the state dir I checked `aitrader/__main__.py:98-104`: news-live
  takes `--until`, `--minutes`, `--check` and `--supervised` only. `journal.STATE = ROOT / "state"`
  (`journal.py:21`). No env lookup exists in journal.py or news_live.py except `GIT_OPTIONAL_LOCKS`. So the refusal
  is the right build.
- Item 3, lock path: an explicit `--state-dir` equal to the default is allowed. I checked `Paths` (`supervise.py:74-86`):
  the lock and the state file live in `state_dir`, not `cache_dir`. An explicit default `--state-dir` therefore sees
  the live parent's lock. No bypass.
- Item 4: one mutually exclusive group, and `ap.error` for `--watchdog` without `--status`. The run form is unchanged.
- Item 5: `test_news_supervised.py:1522` sets the value on `self.nt.n` with the sibling's comment, and the assertion on
  config.json's value is gone.
- Item 6: `supervise.py` diff 421-426. Only the stale check changed. `_stamp_ages`, `blind_s` and R6's `{s}` line are
  untouched. With any unknown age, `beat_view.stop_age_s` is None (`supervise.py:383`), so `{s}` is the child's age, as
  the brief wants.
- Item 7: `paused()` writes one `pause` row (start = the previous tick's `t`, wall seconds, the child's pid) and
  reuses `gap_line` with `{"t", "ev": "pause"}` (no second R4 builder). Its `say(...)` mirrors `up()`'s R4 call
  (`supervise.py:1146-1148`), with `extra={"m": ...}`. The hang skip covers `mine` only, so a child with no beat keeps
  `start_grace_seconds`. The gap is measured on `time.time()`, the clock `beat_view` reads.
- Item 7, back-off ticks: I checked `restart_core` (`supervise.py:243-266`). `watch(None, 0.0)` → `look` runs on
  back-off ticks too, so a pause with no child is detected.
- Item 7, the three process tests: all present, and they signal only the spawned parent and the dummy child's own
  group, after checking its cmdline and pgid. Durations are reported (6.69 s, 2.19 s, 3.70 s).
- config.json: the diff shows exactly the new key and one `_note` clause. That matches the report's key-by-key diff.
- Commit message and file list are as the brief gives them. No attribution lines.

Cannot verify from this diff:
- That no existing test asserted R6 at the boot beat with no stamp. The report says none did. That rests on the suite
  passing, which I did not re-run.
- Whether the controller wants `uptime.close_lines` R4c to say "לא ידוע" when `open_at_close` is None. It changes
  through the shared `held_text` with no edit to uptime.py, and no test pins it. To check: one test in
  `tests/test_uptime.py`, or a ruling.
- Whether the pause's R4 `m` and uptime's own minute counting from marks (`uptime.py:166`, `:231`) together
  double-count a pause in R11. That spans unchanged uptime.py.
- The reported runs (the three files 3x OK, and the whole suite `Ran 831 tests ... OK` in 297 s). I did not re-run them.

### Strengths

- Each fix sits in the shared function. `held_text` handles `None` once for every caller, and the report names the one
  caller whose text changes without an edit (R4c).
- `--clear-halt`: the timeout is fail-safe (a check that doesn't answer leaves the halt). The state-dir refusal comes
  before the live-parent check and before the check runs. The test of the refusal could not touch the live state even
  if the refusal regressed: the check is a stand-in, and the lock and halt are under the temp dir.
- Item 7 is built on the right clock. `wall` is read once per tick and used for both the beat age and the gap. R4 is
  built by `gap_line` itself, not a copy.
- The tests check behaviour, not mocks. The process tests are real SIGSTOP/SIGCONT pauses, with a guard that a child
  stopped alone is still a hang. The R5e test covers all five unreadable-book cases from Ruling 39. The conflicting-forms
  test checks argparse's own message, so its 2 cannot be a config error's 2.
- Item 5 got a real RED: in a throwaway copy, a tuned config failed the old test and passed the new one.
- The report is candid. It discloses the one python command run without the safe wrapper, the R4c side effect, the
  R6-after-pause gap and the item-4 departure.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `ai-trader/tests/test_supervise.py:772-790`: the item-4 test form departs from the brief (spec; plan_mandated). The
  brief mandates "raise `SystemExit` with code 2" from `main(...)`, which contradicts `main`'s established contract (it
  catches argparse's `SystemExit` and returns the code). The test asserts `== 2` plus the argparse message. This matters
  because a named test's assertion differs from its brief, and the controller notes call for BLOCKED, not a
  substitution. Fix: the controller ratifies the substituted form (recommended; it is stronger). The alternative,
  having `main` re-raise, would change every in-process argparse error and is not recommended.

#### Minor (Nice to Have)

- `ai-trader/aitrader/supervise.py` (diff 375-387, 389-401), pause before the first `up`: if the machine pauses after
  this parent's start and before its first `up`, `paused()` sends R4 for the pause. The first `up` then also measures
  `seen["gap"]` from the previous parent's last row, an interval that contains the same pause. The result is two lines
  for one outage, with R4/R4b `m` counted twice for R11. Rare: the window is the child's first look. Fix: on a pause,
  set `seen["gap"]` to the resume tick, or skip the pause R4 while `seen["gap"]` is pending.
- `ai-trader/aitrader/supervise.py` (diff 432), R6's `{s}`: it still reads `time.time() - kid["started"]` while the
  stale check uses `born` from `wall`. The two agree to microseconds, but `{s}` could reuse `born`. Also, with one name
  stamped from an earlier life and another unknown, `{s}` is the child's age, which is a lower bound (the report names
  this).
- `ai-trader/aitrader/supervise.py` (diff 298), duplicate rule: the `--clear-halt` key check
  `type(x) not in (int, float)` restates the NUMBERS rule (`isinstance(bool) or not isinstance((int, float))`) in a
  second spelling. A non-positive value is accepted, which is fail-safe because the halt stays.
- `ai-trader/aitrader/supervise.py` (diff 399-401), no `ponytail:` comment on the known ceiling: any in-loop wait
  longer than `hang_seconds` reads as a pause. Today the only one is `stop(child, "hang")`, bounded by
  `hang_term_grace_seconds` (5 s against 180 s). The ceiling is named only in the report, not in the code.
- R6 after a long pause (out of the brief; report concern 2): the engine's first fresh beat after resuming can carry
  pre-pause per-name stamps, so an urgent R6 and then an R6b follow the pause's R4. The numbers are true, but it is two
  extra lines for one event. This is a controller question.
- Pre-existing, outside the brief: `ownerlines.held_text` raises `TypeError` on a `None` or non-number stop (a book
  position without `stop_price`, or a beat entry that is no dict, gives `None` in `beat_view`/`_held_now`). `say()` then
  drops the whole owner line, and `--status` returns 2. It is the same "cannot tell" class as Ruling 39, one level
  down. Candidate for a ruling.
- `ai-trader/tests/test_supervise.py` (diff 578-590), cleanup gap: `STAMPLESS_CHILD` is not in `kill_ours`'s
  recognised argv set. It is harmless because the child exits when its parent pid changes.
- Reported test output: the whole-suite output still carries `[news] ...` / `[journal] ...` lines. They are
  pre-existing, from other test files, and the three files of this task print nothing.
- Process: one text-only `python3 -` edit script ran without the mandatory safe wrapper (report concern 1). It had no
  aitrader import and no network, and the edit was re-applied after RED. Self-reported, with no effect on the delivered
  code.

### Assessment

Task quality: Approved. The code does what Rulings 39, 41, 48 and 49 ask, in the shared functions, with the right clock
and real process tests. No stop look is touched, no threshold is a literal, the config change is the one key and its
clause, and no topic or exception text reaches an output. Spec compliance hangs on one item: the controller must ratify
the item-4 test's `main(...) == 2` form in place of the brief's `SystemExit`, which cannot pass against `main`'s
contract.
