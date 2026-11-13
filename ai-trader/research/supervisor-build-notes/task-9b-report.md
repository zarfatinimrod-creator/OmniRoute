# Task 9b report: the gate's follow-ups before rollout step 2

Gate clone at start: HEAD ab7b27f973e12289dfa3d5dc1a4fa80c6ac00e6d, branch supervisor-build, tree clean.
One commit: `5e9cca69 fix(ai-trader): the gate's follow-ups before the supervisor's step 2 - retries, guards, a clamp,
a planned stop that waits on nothing, three beats, the SKILL procedures` (no attribution lines). `git status --short`
prints nothing after it. Every python command ran through the controller's `safe` wrapper.

## What was implemented (news_live.py line numbers at 5e9cca69)

1. **The late line is said again (review M3).** `step()`'s `finally`, after the closing message: while `self._late` is
   not empty it calls `say_late()` (line 1552) and then beats (1554). A delivered late line marks its rows told through
   `_mark_told`, as before; `say_late` still never raises.
2. **No channel configured counts as said to the log (review M4).** New `notify.channels(cfg) -> list[str]`
   (notify.py:28): `"ntfy"` when the topic variable named by `alerts.ntfy_topic_env` is set, `"telegram"` when both
   Telegram variables are; standard library and the same env names and defaults as `send`; it returns names only, never
   a value. The engine counts a line as taken when `notify.send(...)` returned something **or** `notify.channels(cfg)`
   is empty: `_say` (1483; it carries the look's message and the closing message), `say_late` (1506) and E1 (1935).
   With a channel configured and a failed send, nothing changes.
3. **A line sent again backs off (critic N5).** New key `news.unsent_resend_seconds` = 120 in `config.json` and in
   `DEFAULTS` (plus one sentence in `news._note`). In `step()`'s closing message, an older owed row (`earlier`) is
   carried only when the last closing message that carried it is at least that many seconds old (1534-1535, monotonic
   clock); otherwise it is left out of the message and stays in `_unsent`. The send time is kept per row in
   `self._carried_at` (set in `__init__`, 611; updated at 1543 for every row a closing message carries). A new line is
   never held back: the look's own message and the closing message of the step that made the row always carry it.
4. **The start's sends and writes are guarded (review m5, m6, m10; critic N8, N9).** Each as E1/E2 are, with
   `error_once(<where>, e)` and the code it would have returned:
   - calendar alert before exit 5: `where` "calendar_line" (1879);
   - R5d before exit 6: "book_line" (1887; the `owner_line` render is inside the guard too);
   - broken-chain alert of the start before exit 4: "chain_line" (1909);
   - holder's name into the lock file: `except OSError` -> "lock_file" (1848); the lock stays held and `_run` runs;
   - `_set_pdeathsig()`: any exception -> one printed line, `[news] the engine could not ask to die with its parent
     (<type>): it looks for its parent at the top of every round` (1825); the supervised start goes on (no row).
5. **The wait's slice is clamped (critic N6, review m2).** `NewsTrader.__init__` (619-627, next to the existing
   unknown-word checks): a `sleep_slice_seconds` that is a bool, not an int/float, or not > 0 (0, negative, NaN, text)
   is replaced by `DEFAULTS["sleep_slice_seconds"]` and one `news_errors.jsonl` row with `where` "config" is written.
   `NewsTrader` is built once per start in `_run`, after the start checks, so a refused start writes no such row.
6. **A planned stop waits on nothing (review m1, m3, m4; critic N4).**
   - The last `drain_trial` waits 0 when `STOP.is_set()` (1992), as it already did while the market is open.
   - The priming poll (764-775): after each feed result it beats and, once STOP is set, keeps only the futures already
     answered and stops; the executor is shut down with `wait=False, cancel_futures=True` after a stop (pending feeds
     are not started, running ones are not waited for), and as the old `with` block did otherwise.
   - A scorer batch whose call failed (`"error" in facts`), that has no scores, while STOP is set (1588): the batch loop
     ends before `handle_scored`, so its keys stay in `_pending` and the existing STOP block takes them out of `seen`
     and the pending record, with no `scorer_failed` row. The call stays in `news_scorer_calls.jsonl`.
7. **Three beats (critic N12).** `handle_scored`: `_beat("score")` right after the benchmark quote (1270). `step()`:
   `_beat(self._phase)` after the closing send when nothing took it (1551; a taken send already beats in `_mark_told`).
   `run_queue_at_open`: `_beat("queue")` right after the live quote that stands in for a missing 09:30 bar (1458); the
   beat that stood before `continue` moved up to it, so a name left waiting still writes one beat.
8. **SKILL.md 3ב.** The line "`kill <pid>`, ואז מפעילים" is replaced: `kill <pid>` sends SIGTERM, a planned stop; the
   engine finishes the call already out and one stop look, saves and exits 143, up to about two minutes; wait until the
   process is gone (or `phase` is `"stopping"` in `state/news_heartbeat.json`, then gone); a start before that exits 3;
   `kill -9` only if it is still there after two minutes. New paragraph **E1 (התיק לא תואם ליומן העסקאות)**: no hand edit
   of `news_book.json`; `python3 -m aitrader verify`; one Hebrew message with the last journal row and the book's
   positions in exact numbers ending "כסף נייר"; one question, א restore from the journal row / ב leave the book and
   mark the row reviewed / ג keep buys blocked and look again tomorrow, recommending ג; buys stay blocked until he
   answers (the engine already blocks them). Hebrew, as the section is.

No buy, sale or stop rule changed. No stop look is delayed or skipped by these changes (the beats are file writes; the
end-of-step look still comes before the closing message; see concern 1 for the time the late-line retry can take
after it). No file the time machine loads was touched except `config.json`, where only `news` changed (one key and its
note); `backtest`, `strategy`, `signals`, `learn`, `metrics`, `broker` and `data` neither import `notify`/`news_live`
nor read `news`. `__main__.py` was not needed.

## TDD evidence

Tests: `tests/test_news_supervised.py`, class `GateFollowUps`, 15 tests (items 1-8; item 2 has three, items 4 and 7
have two and three, item 6 three).

**RED-1** (`safe python3 -m unittest discover -s tests -p test_news_supervised.py -k GateFollowUps`), tests written,
no code yet:
```
AttributeError: module 'aitrader.notify' has no attribute 'channels'    (x15, in setUp)
Ran 15 tests in 0.012s
FAILED (errors=15)
```
Expected: the module's `_Engine` takes the real `notify.channels` in `setUp`, and the function did not exist. I then
added only `notify.channels` (the first half of item 2) and ran it again.

**RED-2** (same command):
```
ERROR test_a_line_no_channel_took_is_sent_again_at_most_once_every_unsent_resend_seconds   KeyError: 'unsent_resend_seconds'
ERROR test_a_lock_file_that_cannot_be_signed_or_a_death_signal_...                         OSError: [Errno 28] No space left on device
ERROR test_a_start_whose_alert_cannot_be_sent_still_ends_with_its_code                     OSError: [Errno 28] No space left on device
FAIL  test_a_batch_that_failed_while_a_planned_stop_was_asked_...     (['k1', 'k2'], ['k1', 'k2']) != (['k1'], ['k1'])
FAIL  test_a_late_line_no_channel_took_at_the_start_...                ['דווח באיחור: ...'] != [... x2]   (said once only)
FAIL  test_a_wait_slice_that_is_not_a_positive_number_...             143 != 0 : 0   (the spin ended only by the test's stop)
FAIL  test_after_a_planned_stop_the_last_drain_...                    (60, 60) != (0, 60)
FAIL  test_after_a_planned_stop_the_priming_poll_...                  ['key-S00', ..., 'key-S15'] != ['key-S00']
FAIL  test_the_benchmark_quote_of_a_scoring_has_a_beat_after_it      ([('SPY', 0)], 0) != ([('SPY', 0)], 1)
FAIL  test_the_closing_send_of_a_step_has_a_beat_after_it_...         4 not greater than 4
FAIL  test_the_live_quote_that_stands_in_for_the_opening_bar_...      1 not greater than 1
FAIL  test_the_skill_says_how_to_stop_an_engine_and_what_to_do_on_e1 '`kill <pid>`, ואז מפעילים' unexpectedly found
FAIL  test_with_no_channel_configured_a_closing_message_...           (None, ['d81d…']) != ('d81d…', [])
FAIL  test_with_no_channel_configured_the_lines_of_a_start_...        (None, None) != ('02da…', {'day': …, 'symbol': 'AAA'})
Ran 15 tests in 4.103s
FAILED (failures=11, errors=3)
```
Each fails for its item's reason: an unguarded send or write raises (item 4), the late line is not said again (1), no
channel still reads as not taken (2), the slice spins (5), the drain waits 60 s, priming reads all 16 feeds and a failed
batch stays seen (6), no beat after the three calls (7), the old SKILL line (8). The one test that passed is the unit
test of `notify.channels`, added just before. Item 3's KeyError is the missing key; with only the key added, the same
test failed for the back-off itself:
```
First differing element 2:  (30.0, True, False)  !=  (30, False, False)
...                          (60.0, True, True)   !=  (60, False, True)
```
(the old BBB line was sent again at 30 s and 60 s).

**GREEN** (same command, `-v`): `Ran 15 tests in 0.263s  OK`.

Both files 3 times in a row, after the edits of the existing tests:
```
test_news_supervised.py   Ran 104 tests in 2.487s OK | 2.504s OK | 2.861s OK
test_supervise.py         Ran 19 tests in 33.940s OK | 33.847s OK | 34.096s OK
```
The runs were made at 16:2x-16:3x New York (after the close). Every in-process start of the new tests passes "23:59"
(one passes "00:00" on purpose: the start's lines and no step); the known ceiling is the minute 23:59-00:00. No new
process test.

## Whole suite

`safe python3 -m unittest discover -s tests` from `ai-trader/`, before the commit, wall 95 s:
```
Ran 692 tests in 94.095s

OK
```
(677 before this task plus the 15 new tests.) The new class prints nothing (its stdout is captured); the whole file's
run prints only the unittest summary.

## Files changed

- `ai-trader/aitrader/news_live.py` (items 1-7)
- `ai-trader/aitrader/notify.py` (`channels`)
- `ai-trader/config.json` (`news.unsent_resend_seconds` 120 and one sentence in `news._note`)
- `ai-trader/skills/trader/SKILL.md` (section 3ב)
- `ai-trader/tests/test_news_supervised.py` (class `GateFollowUps`; a local `_Engine`; six existing expectations, below)

## Self-review (git diff ab7b27f9..HEAD)

- Checked line by line against the brief; every item has its code and at least one test.
- `ruff check` on the three Python files: the same findings as at the base, plus three `RUF100` on `# noqa: E731` of
  the new test lambdas (the repo writes that `noqa` the same way elsewhere; the local ruff has E731 off). `ruff --select
  F,E9`: clean.
- Fixed during the review: an invisible right-to-left mark I had typed into the SKILL line (removed; none elsewhere),
  one awkward Hebrew phrase ("שהוא באמצעה" -> "שכבר יצאה"), and an unused name left by an expectation edit
  (`gone = trade("GONE")` -> `trade("GONE")` in the test whose expectation no longer names the hash).
- Edge cases looked at: a trader built without `__init__` (tests/test_audit_fixes.py) never reaches `_carried_at` or
  the retry (`getattr` on `_late`, and no owed lines); a planned stop during a step's own poll still reads every result
  (only priming stops early); a failed batch that still carried scores is handled as before (the `not scores` guard);
  `notify.channels` reads only whether a variable is set.

## Departures from the brief

1. **A local `_Engine` in tests/test_news_supervised.py.** With item 2, a test run (no phone variables) has no channel
   configured, so every send the stand-in answers with `[]` would now count as taken. The tests of this file that model
   "a channel that took nothing" would then test nothing. The import became `from test_news_guards import _Engine as
   _GuardsEngine`, and a local `_Engine(_GuardsEngine)` sets `notify.channels` to answer `["ntfy"]` (the stand-in phone
   already answers `["ntfy"]`) and keeps the real one as `self.real_channels` for `GateFollowUps`. No other test module
   broke, so `tests/test_news_guards.py` is untouched.
2. **Six existing expectations in tests/test_news_supervised.py**, each stating the new behaviour (no assertion about a
   trade, stop, buy, sale or hold was touched):
   - `EveryCallAndEveryStart.test_a_second_check_the_loop_waited_for_leaves_a_beat_and_one_on_trial_leaves_none`:
     `["score"]` -> `["score", "score"]` and `[]` -> `["score"]` (the benchmark quote's beat, item 7).
   - `FollowUps.test_a_line_no_message_took_is_carried_step_after_step_oldest_first_and_once_in_each_message`: one line
     `self.nt.n["unsent_resend_seconds"] = 0` (its steps are milliseconds apart; the back-off is GateFollowUps'). Its
     assertions are unchanged. This is a setting, not an expectation.
   - `FollowUps.test_a_start_beats_after_every_send_git_call_and_priming_feed`: `len(seen) == 3 + 1 + 30` ->
     `3 + 1 + 30 + <steps>` (the late line nobody takes is a send after each step, item 1).
   - `FollowUps.test_rows_of_the_run_before_are_left_to_the_late_line`: SELL messages `== 1` -> `== 1 + <steps>`
     (the late line at the start and after each step, still never in a closing message).
   - `WhoWasTold.test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start`: the list of rows -> the set
     `{("late_line", "OSError")}` (a row each time the late line is tried).
   - `WhoWasTold.test_a_steps_closing_message_does_not_tell_the_rows_of_the_run_before`: the closing message still
     carries BBB's line and not GONE's; the late line said again after it is the third message, which the stand-in
     takes, so GONE is told then: `([True, True], None, [gone])` -> `([(True, False), (True, False), (False, True)],
     <last row>, [])`; `gone = ` dropped as unused.
3. **A fourth beat**, after the late-line retry in `step()` (1554). The retry is a new send (item 1), and every call
   that leaves the process has a beat after it (spec 5.5; `_beat`'s docstring; the start's `say_late` has one).
4. **Readings of the brief:**
   - Item 3: the back-off counts between closing messages. A line of a start's first look (sent by the look, outside
     any step) is still carried by the first step's closing message at once, as Task 8a built and pinned
     (`FollowUps.test_a_first_look_line_nobody_took_is_in_the_first_steps_closing_message`); from then on it waits
     120 s. Within a step, the closing message of the step that made a row always carries it (its first send there).
   - Item 4, `_set_pdeathsig`: one printed line and no `news_errors.jsonl` row, since it runs before the lock and a
     start refused with 3 writes nothing. The lock-file write catches `OSError` only, as the brief names.
   - Item 6, failed batch: unseen again only when the call failed **and** returned no scores, so a batch that carried
     answers is never thrown away.
   - Item 6, priming: "not yet read" is taken as "not answered by the time the stop is seen"; answered feeds are
     primed whether or not `as_completed` had yielded them yet.
   - Item 7, "the second check inside run_queue_at_open": `run_queue_at_open` makes no second-check call; its calls are
     the 09:30 opens (beat after), the live quote asked when a name has no 09:30 bar, and the quote of the move (the
     name's own beat follows `_buy` in `finally`). The only call followed by another call with no beat between was the
     live quote, when it found a live price; the beat is placed right after it. If the move quote was meant, it already
     has the name's beat after `_buy`, which makes no outside call.

## Concerns

1. **The late-line retry is not under the back-off.** The brief says once per step; in an outage with late rows owed,
   each step pays one more send (up to 15 s per channel), between its end-of-step look and the next step's top look,
   which is the cost N5 is about. The back-off of item 3 covers only the closing message. If wanted, `say_late` in
   `step()` can be gated by the same `unsent_resend_seconds`.
2. **Unguarded sends of the loop.** Item 4 guards the start's sends. The loop's twins are still unguarded: the
   `ChainBroken` alert inside the loop (a raise there ends `_run` with a traceback instead of 4) and the
   `alert_after_errors` alert. Same one-line guard if wanted.
3. **A raising late-line send writes a row every step** (`_note_error`, as the closing message's `step_alert` already
   does). `notify.send` raises only in rare paths (a quiet-hours queue write; the stock book has no quiet hours).
4. **After a planned stop during priming**, up to 8 feed calls may still be running when `poll_headlines` returns; the
   lock is freed when `run()` returns, but the interpreter's exit joins those executor threads (up to 10 s, the feed
   timeout). Still inside the parent's 120 s grace.
5. Not in this task: `state/*.tmp` in `.gitignore` (progress.md lists it with 9b; the brief does not); the blind-quote
   alert still counts only a channel as delivery, so with no channel configured it prints again each window.
6. A slip: I ran a read-only `git stash list` once while checking the tree (piped to nothing). No stash was created,
   popped or changed.

## Fix round 1

Start: HEAD 5e9cca695715d411e2eee79f49fcc9dbac398d64, branch supervisor-build, tree clean (checked). One commit:
`634c70eb fix(ai-trader): keep the atomic saves' .tmp files out of git, in both books` (no attribution lines).

### F2 (state/*.tmp in .gitignore) - fixed

- `ai-trader/.gitignore:7-8`: one comment line and the pattern `state/**/*.tmp`. I took the reviewer's broader
  form: `journal.save_json` / `write_all` (journal.py:224-227, 236-239) write `<name>.tmp` in the ACTIVE state dir,
  and under `journal.use_book("crypto")` that is `state/crypto/` (config.json `market.state_subdir` "crypto"). In
  gitignore `a/**/b` also matches `a/b`, so `state/**/*.tmp` covers everything `state/*.tmp` does plus the crypto
  folder. Checked in a scratch repository that `state/*.tmp` alone leaves `state/crypto/news_heartbeat.tmp` not
  ignored (rc=1), so the narrow form would have left half the hole.
- Check in the clone after the change (`git check-ignore -v`):
  `state/news_heartbeat.tmp` -> `ai-trader/.gitignore:8:state/**/*.tmp` (rc 0); `state/crypto/trials.tmp` -> same
  (rc 0); `state/news_book.json` rc 1; `state/crypto/trials.jsonl` rc 1 (tracked files stay trackable).
  `git ls-files 'state/*.tmp'` was and stays empty.
- Test: `tests/test_news_supervised.py:1663-1677`, `GateFollowUps.test_the_temporary_file_of_an_atomic_save_is_never_a_file_git_takes_in_either_book`.
  It copies `ai-trader/.gitignore` into a fresh temporary git repository (`git init`, env from `no_phone.clean_env`
  with `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`; local only, no network, no real state), and asserts
  `git check-ignore` says ignored for `state/news_heartbeat.tmp` and `state/crypto/news_heartbeat.tmp`, and not
  ignored for `state/news_book.json` and `state/crypto/trials.jsonl`. The `.tmp` name comes from the same
  `with_suffix(".tmp")` the journal uses. The narrow pattern `state/*.tmp` fails it (crypto case).
- Departure from the brief: the commit adds `ai-trader/.gitignore`, which is not in the brief's Files or `git add`
  list; the finding's suggested fix names it ("a small 9b fix commit (add ai-trader/.gitignore to its git add)").
  Task 10 still adds its own four `state/news_*` lines to the same file; no conflict with this line.

Nothing else was changed: the Important and Minor items of the review are not in this round's list.

### Tests

RED (new test before the .gitignore line),
`safe python3 -m unittest discover -s tests -p test_news_supervised.py -k atomic_save`:
```
    self.assertEqual([ignored(p) for p in (f"state/{tmp}", f"state/crypto/{tmp}")], [True, True])
AssertionError: Lists differ: [False, False] != [True, True]
Ran 1 test in 0.016s
FAILED (failures=1)
```
GREEN, same command: `Ran 1 test in 0.017s` / `OK`.

Covering files (from `ai-trader/`, `safe` = `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe`):
- `safe python3 -m unittest discover -s tests -p test_news_supervised.py`, 3 times in a row:
  `Ran 105 tests in 2.274s OK`, `Ran 105 tests in 2.295s OK`, `Ran 105 tests in 2.370s OK`.
- `safe python3 -m unittest discover -s tests -p test_time_machine_honesty.py` (its
  `test_run_records_stay_out_of_git` reads `.gitignore` split on whitespace): `Ran 38 tests in 7.342s OK`.

Whole suite before the commit, `safe python3 -m unittest discover -s tests` from `ai-trader/`, wall 99 s, last three lines:
```
Ran 693 tests in 98.073s

OK
```
(692 + the one new test.) After the commit `git status --short` printed nothing.
