# Task 14 review - `--status`, `--clear-halt`, `--relayed` (+ Ruling 36 a-j)

Diff 236430fa..9f6190ae (2 commits), read from `review-task-14.diff` (1236 lines, two passes). Checks outside the diff,
one per named risk: the engine lock's text (news_live.py:1841-1858, JSON with `pid`, so `_live(engine_lock, "news-live")`
can see an engine); `take_lock`/`load_state`/`save_state`/`beat_view`/`mark_due` at the head (supervise.py:159-212,
357-375, 390-392: `beat_view(None, ...)` returns an empty view; the first tick writes a mark, so a fresh parent has a
mark within milliseconds); the end of `restart_core`'s crash path (supervise.py:296-301: nothing reads `child` after
a spawn failure); `ownerlines.py:38,90,98-101` (R5e's template and `held_text({})` = "אין פוזיציות"); Ruling 36 is in
progress.md:441 and P11/P13/P29 in rulings-10-28.md:199-224. No test was run: no doubt arose that the reported runs
do not answer.

### Spec Compliance

Compliant with the brief, the controller notes and Ruling 36, among what this diff shows.
- `status()` has the brief's signature and the spec 4.4 keys in order (supervise.py, `status`); `action` follows the
  brief's eight rows top to bottom; `after_hours` is `launch_from_ny <= HH:MM < launch_until_ny` (16:00 is
  after_hours, as the test wants); `wait_for_watchdog` is skipped after a `sup_stop` whose `why` is a `PLANNED` key
  (handover, signal, orphaned).
- Read-only verified by reading: no `open(..., "w")`, no flock, no mkdir in `status`, `_live`, `_argv`, `_ppid`,
  `_relayed`, `_held_now`; main routes `--status` before its first stdout line, the mkdirs and `take_lock`.
- `unsent`: latest row `sent is False`, not relayed today, and (R10, or no live parent, or first row older than
  `alert_retry_minutes`); R5e only with `watchdog` and a halt `at` on an earlier New York day, id `R5e-<today>`,
  `{held}` from the book (P11).
- `launch`: `--handover` + `TWO_HOURS_MS` unless `long_timeout_proven is True` and `BASH_MAX_TIMEOUT_MS >=
  long_timeout_ms`.
- `--relayed` is the only writer of `news_relayed.json`, a new New York day starts an empty list; `--clear-halt` exits 3
  with a live parent, runs `child_cmd or [sys.executable, "-m", "aitrader", "news-live"]` + `--check`, prints its
  output, clears under `take_lock` only on 0, else 1.
- The brief's five tests exist under their names with the brief's assertions unchanged; the stand-ins the comments
  name (lock text = `os.getpid()`; R4-1 relayed; R1-3/R10-4 a minute old) are written in the tests. Additions only.
- Ruling 36 (a)-(j): each item is in the diff with a test labelled "added by ruling". `deadman.py` (docstring only) and
  `config.json` (`_note` text only, no value changed) are in the commit because (j) and (h) name them.
- (f) is read as "SIGKILL to the group once the leader ended or the grace ran out"; this matches the form the Task 12
  review proposed, which (f) folds in, and does not delay a restart. Accepted.

Cannot verify from this diff:
- Controller note (12:19 UTC, 2026-11-11): "Task 14's `--status` tests the lock itself, never the text alone." The
  later brief says "No lock is probed" and defines alive by the lock text + `/proc/<pid>/cmdline`. The build does the
  brief's form ("never the text alone" holds; "the lock itself" does not). The controller should confirm which reading
  binds (report, departure 7).
- `Parents.config` pins all five switches (P29) - unchanged code; the report says so.
- Whether `skills/trader/SKILL.md` and the watchdog prompts (later tasks) call `--status --watchdog`, relay `unsent` and
  then `--relayed` exactly as built.

### Strengths

- `status`, `relay` and `clear_halt` are module-level functions with one job each; main only routes. `closed_day` is
  now one helper for the parent and `--status`, `_held_now` is the parent's closure lifted unchanged, and
  `_signal_group` replaces three copies of the killpg block: reuse, not rebuilding.
- Tests drive real behaviour: stand-in processes whose command line names `aitrader.supervise` / `news-live`, real lock,
  state, log and book files, a deaf grandchild that only a group SIGKILL ends, a spawn of a program that does not exist.
  The `Status.status` helper restores exactly the files a case wrote, so the brief's "status writes nothing" snapshot
  check is a real check, not a tautology.
- Every error path prints an exception class only (`relay`, `clear_halt`, `--status`); the topic is read into one
  local and never logged. No literal threshold: every number is read from the `supervisor` block; the two-hour cap is
  `TWO_HOURS_MS`.
- The race between `--clear-halt`'s `_live` check and `take_lock` is handled (None from `take_lock` = exit 3).
- RED was captured for every new test that can be red, with the reason for the argparse-first failures stated.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `ai-trader/aitrader/supervise.py` (`status`, the R5e block: `held=ownerlines.held_text(_held_now(paths, None), ...)`),
  plan-mandated (ruling P11, "status() uses the same fallback for R5e's {held}").
  - What: on a halt 6 the book is missing or unreadable (that is what halt 6 means, and it stays so until
    `--clear-halt` passes), so `_held_now` returns `{}` and R5e reads "מנוע החדשות עדיין עצור מאז DD.MM (קובץ התיק).
    סטופים לא נבדקים. פתוח: אין פוזיציות. כסף נייר". A book that parses but is no book (ratified at Task 5 as exit 6)
    gives the same text through the caught KeyError/AttributeError.
  - Why: this is the false all-clear inside an urgent "stops are not checked" line that P11 was written to prevent;
    P11 only noted that R5d has no `{held}` and did not look at R5e. The owner gets it every morning the halt lasts.
  - Fix (needs a controller ruling): for code 6 take `{held}` from the last heartbeat (`_read_beat`, the previous
    engine's held names and stops, present on the same VM), or render a "positions unknown" word (an ownerlines
    WORDS/template change). The implementer flagged it (concern 1) rather than guess: correct.

#### Minor (Nice to Have)

- `supervise.py` `status`, kill_stray row: `_ppid(engine) != parent` runs only when `parent` is None (every live-parent
  case was taken by `none`/`replace_parent`), so it means "the engine is still alive". It reads as a comparison with a
  live parent. Checking the engine's parent by command line (`"aitrader.supervise" in _argv(_ppid(engine))`) would be
  the brief's words literally and would spare a supervised engine whose parent's lock text could not be written (full
  disk: `take_lock` keeps the flock but leaves the old text), which today reads `kill_stray` and then `launch`.
- `supervise.py` `status`, none/replace_parent: the log's last mark is read whoever wrote it (report, concern 3). The
  window is a new parent's first tick (milliseconds, `mark_due(None, ...)` is true); acceptable.
- `supervise.py` `status`, unsent: since Ruling 36 (a) a line with no topic is never retried, yet with a live parent it
  waits `alert_retry_minutes` before `--status` lists it.
- `supervise.py` `clear_halt`: `subprocess.run` has no timeout (bounded only by the harness's command timeout), and the
  check runs with `cwd=ROOT` whatever `--state-dir` says, so `--clear-halt --state-dir DIR` from the command line
  (the usage line offers it) checks the live state and clears DIR's halt. Same pattern as the parent's spawn; no
  later brief uses it.
- `supervise.py` main: conflicting forms pass silently (`--status --clear-halt` runs only `--status`; `--watchdog`
  without `--status` asks for `--until`, or with it runs the loop). An argparse mutually exclusive group would refuse
  them with exit 2.
- `supervise.py` `status`, R5e: a book stop that is no number makes R5e vanish from `unsent` (the `except ... pass`);
  this is the class Ruling 38 deferred (the engine always writes a number).
- `tests/test_supervise.py` `Watching.test_on_a_cold_start_with_no_stamp_blind_s_counts_from_sup_start`: the
  `first_look_done` stand-in removes `stops_checked_at` by mutating its argument, so the test relies on `up` reading the
  same dict object; a refactor that copies the beat would make it pass for the wrong reason or fail.
- Reported test output: the whole-suite runs carry pre-existing noise lines ("[news] engine started ...", "[journal]
  skipped unreadable line ...") from other modules; one `test_supervise.py` run failed 7 engine tests at 23:59 New York
  (the accepted ceiling of the 11:10 UTC ruling). Neither comes from this change.

### Assessment

Task quality: Needs fixes. The build matches the brief and Ruling 36 and is well tested; the one Important issue is a
plan-mandated false all-clear in R5e on a halt 6, which needs a controller ruling before it can be fixed.
