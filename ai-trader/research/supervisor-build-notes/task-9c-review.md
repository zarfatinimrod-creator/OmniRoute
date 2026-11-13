# Task 9c review: the last follow-ups of step 1 (52ea9265..b9bdd278)

Read: task-9c-brief.md, constraints.md, controller-notes.md, progress.md Rulings 28/29 (lines 345-346), task-9c-report.md,
and the review package review-task-9c.diff (1 commit, 4 files, +237/-37). The suite was not re-run, as instructed.
Focused checks outside the diff are listed where they were made.

### Spec Compliance

Compliant. Each of the brief's 7 items has its code, and its test or the "no new test" the brief allows.
- Item 1, back-off: news_live.py:1561-1565. It sits inside step()'s `finally`, after the closing message (checked at
  1532-1566). Gate: `_late_tried_at is None or monotonic - stamp >= n["unsent_resend_seconds"]`. The stamp starts as
  `None` (615). The start's `say_late()` (`_run`) is unchanged. Test: test_news_supervised.py:1706. Steps at
  0/30/120/150/240/400 s try at `[0.0, 120.0, 240.0]`, then the line is told. That covers "two failed retries 30 s apart
  make one send; after 120 s it is sent again".
- Item 2, the loop's alerts:
  - ChainBroken alert guarded at 1985-1989 (`loop_chain_line`). The code stays 4 and the loop breaks.
  - `alert_after_errors` alert guarded at 2000-2005 (`loop_fails_line`). The loop goes on.
  - Tests at 1727 (returns 4, exactly one `loop_chain_line` row) and 1741 (three steps, 143, the guard row between the
    failure rows).
- Item 3:
  - `asked = [ex.submit(...)]` is inside the `try` whose `finally` shuts the executor down (poll_headlines, 767-768).
  - `carried` and `_carried_at.update(...)` are inside the `try` that guards `_say`/`_mark_told` (1549-1551).
  - No new test, as the brief allows; the report says so.
- Item 4, cut priming: 1960-1965. On `STOP.is_set()` after the priming poll, `nt.seen = {}`. The loop then ends with 143
  at once, and its exit `nt.save()` writes `{}`. Test at 1760: it uses the real priming poll with one feed answering
  and one blocked. The first start leaves `{}`, the second start primes (`len(primed) == 2`) and keeps both keys.
  Checked: priming only runs under `prime and not nt.seen`, so this only acts when `seen` was empty, as the brief scopes it.
- Item 5, no exception text:
  - `error_once` and `_note_error` take `detail: bool = True`. With `False` the row is `{at, error, where}`.
  - `grep -n "detail=False"` gives exactly the seven sites the brief names: 1517 `late_line`, 1859 `lock_file`,
    1891 `calendar_line`, 1899 `book_line`, 1921 `chain_line`, 1989 `loop_chain_line`, 2005 `loop_fails_line`.
    Older sites keep the default.
  - `.gitignore:7` adds `state/news_errors.jsonl`.
  - Test at 1790: every guard is raised with `RuntimeError("https://ntfy.example/secret-topic")`, or `OSError(28, secret)`
    for the lock write. It asserts that each of the seven rows has keys `["at","error","where"]` and the right class,
    and that "secret-topic" is nowhere in the file.
- Item 6, blind alert: news_live.py:1234-1237, `bool(send(...)) or not notify.channels(self.cfg)`.
  - Checked notify.py:28-37: `channels` reads only the environment and `cfg.get("alerts", {})`. With no channel
    configured, `send` only prints, so "said to the log" is literally true.
  - Test at 1838 covers both cases. No channel: 1 alert, told, one "price is back" line. A configured channel that
    failed: 3 alerts, not told, no "back" line.
- Item 7a: `WhoWasTold.test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start` (845) now asserts the
  exact list `[("late_line","OSError")] * 2` over three real steps, with the back-off in force, plus 3 steps and
  `told_through` None.
- Item 7b: the SKILL test (1673) checks:
  - the two-minute bound ("עד כשתי דקות", "`kill -9` רק אם התהליך עדיין שם אחרי שתי דקות"), inside the kill procedure;
  - options א/ב/ג and "ההמלצה: ג.", inside the E1 paragraph.
  - The report's mutation run (6 mutations, all caught) shows the test now tells a broken text from a good one.
- Commit: message as the brief gives it, no attribution lines (the report says so; the package's commit line matches).
- Files beyond the brief's list, under the controller's ruling of 10:35 (existing tests broken by the brief's change):
  - two FollowUps expectations in test_news_supervised.py (1305, 1346);
  - two BlindStop tests in test_news_inputs.py (338, 352).
  - All four are listed in the report under departures. None is about a trade, a stop rule, a buy, a sale or a hold.
    The BlindStop sale test is untouched. See Minor 2 on the form of the BlindStop edit.

Cannot verify from this diff:
- Ruling 28's "a monotonic stamp of the last attempt" can be read two ways: does the start's `say_late` start the
  120 s? The ruling does not settle it; the controller decides (Minor 1).
- The report's GREEN, 3x and whole-suite results (710 OK, 99 s) were not re-run, as instructed. The RED output it quotes
  is consistent with the code: 4 vs 2 late rows, a traceback from the unguarded alerts, `1 != 2` primings, 3 vs 1
  blind alerts, a `detail` key holding the URL.
- That no later task (11, 12, 20) relies on the start's late-line try setting the step's back-off stamp.

### Strengths

- Smallest workable diff. One keyword on the two existing error writers, no new helper, no new config key. The back-off
  reuses `unsent_resend_seconds` (DEFAULTS:63, config.json:246), so no literal threshold.
- The stop path is untouched:
  - `_look_at_stops`, `check_stops`, `catch_up_stops`, `_buy`, `_sell`, the queue and the holds do not appear in the diff.
  - Item 1 only removes sends between a step's end look and the next first look.
  - Item 4 acts only on a planned stop, which already ends the loop before any step.
- The new loop tests are deterministic. Each ends with a planned stop that its own stand-in sets on a fixed step, before
  it does anything else. A defect gives a failure, not a running loop. `STOP` is cleared in cleanup.
- The item 4 test uses the real `poll_headlines` with a feed that is truly still out (`threading.Event`, released in
  cleanup). It is robust to thread order: if the blocked feed answers first, the cut still empties `seen`.
- The item 5 test drives all seven guards through the real `_run`/`run`, and checks the absence of the secret over the
  whole errors file, not only over the guard rows.
- Checked: in-process `run()` (item 5, scenario 5) calls `_set_pdeathsig` only under `supervised` (news_live.py:1832-1834).
  The test passes none, so the test runner is never armed with PDEATHSIG.
- The reworked 7a uses the same stand-ins as `_Starts.start` (test_news_supervised.py:359-363), plus a step wrapper. Its
  reach is no wider than the test it replaces.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

1. news_live.py:1561-1565: the back-off stamp is set only by step()'s retry, never by the start's `say_late`.
   - Effect: in an outage that spans a restart, the first step after a start tries the late line once more, about
     `poll_seconds` after the start's try. That costs up to 15 s per channel between step 1's end look and step 2's
     first look, once per start. 9b did this on every step, so 9c only reduces it.
   - The 9b test pins this reading (test_news_supervised.py:1446-1452: `say_late()` then `step(nt)` retries).
   - The other reading (Ruling 28's "last attempt" includes the start's) is one line in `say_late` plus that test.
     The controller chooses. The implementer raised it as concern 1.
2. test_news_inputs.py:338, 352: the 10:35 ruling says "make the smallest edit of that test's EXPECTATION". These two
   edits change the arrangement instead: `notify.channels` answers `["ntfy"]`.
   - This keeps every assertion, and keeps the tests true to their names. With no channel configured, the alert now
     "goes out" to the log, so "did not go out / never went out" would no longer describe the test. The original
     comment's premise, "(ntfy down, nothing configured)", contradicted itself.
   - It departs from the ruling's letter; the controller should ratify it.
3. test_news_supervised.py:1305: `3 + 1 + 30 + read_heartbeat()["step"]` became a hard-coded `3 + 1 + 30 + 1`.
   - The old form held for any step count. The new one assumes the 30 ms loop made at least one step. A stall of more
     than 30 ms between `t0` and the first clock check would make a 0-step run fail.
   - `+ min(1, read_heartbeat()["step"])` keeps the intent with no such assumption. Line 1346 is covered by its own
     `b["step"] > 0` check.
4. test_news_supervised.py:1711: the item 1 test asserts `nt.n["unsent_resend_seconds"] == 120`, a value read from the
   shared config.json (`copy.deepcopy(CFG)`).
   - Tuning the value in config.json would fail this test, not change it.
   - Setting `self.cfg["news"]["unsent_resend_seconds"] = 120` before building the trader would make the test
     independent of the tuned value.
5. config.json:243: the `_note` still says `unsent_resend_seconds` governs "a step's closing message" only. It now also
   spaces the late line's retries. config.json is outside this brief's files, so the next task that edits config.json
   should add the clause.
6. news_live.py:1996: the loop's own `journal.append("news_errors.jsonl", ...)` for a failed step has no `try`. A
   journal that cannot be written there (a full disk) still ends `_run` with a traceback. This is out of 9c's scope (the
   brief names the two alerts only). The implementer raised it as concern 3; worth a line in a later task.
7. test_news_supervised.py:1790-1836: one 45-line test drives six start scenarios in sequence. A failure in an early
   scenario hides whether the later guards hold. Splitting it per guard would localise failures. Polish only.
8. Process, disclosed in the report, no effect on the diff:
   - One read-only `git stash list` ran. The constraint bans `git stash` anywhere, and this is a `git stash` subcommand.
   - One `python3 -` text substitution ran outside the mandatory `safe` wrapper. It imported nothing of the project.

### Assessment

Task quality: Approved. All seven items are built where and as the brief and Rulings 28-29 say, with tests that fail for
the named reasons and pass deterministically. No trading rule, stop look or config value changed. The remaining points
are a reading the controller should confirm (Minor 1), a ruling-form ratification (Minor 2), and small test-robustness
polish.
