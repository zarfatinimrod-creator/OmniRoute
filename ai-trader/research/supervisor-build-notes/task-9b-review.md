# Task 9b review: the gate's follow-ups before rollout step 2

Diff: ab7b27f9..5e9cca69 (1 commit, 5 files), read once from `review-task-9b.diff`. Nothing re-run; no file changed.
Line numbers are news_live.py at 5e9cca69 unless the diff line ("d.NNN") is given.

### Spec Compliance

Compliant. Each of items 1-8 has its hunk and at least one test in `GateFollowUps`, under the behaviour the brief gives:
- 1 late line retried: step() finally, d.247-249; test `..._said_again_by_the_next_step_and_told_once` (first send
  fails, second delivered, `told_through` and the heartbeat move, two bodies only).
- 2 `notify.channels` (notify.py:28-37) and "none configured = taken" in `_say` (covers the look's message, line 1194,
  and the closing message), `say_late` and E1; three tests, both cases (no channel / configured channel that failed).
- 3 `news.unsent_resend_seconds` = 120 in config.json and DEFAULTS; `_carried_at` back-off, d.225-236; test pins 0 s,
  30 s (left out), 60 s (new SPY line sent at once, BBB still out), 120 s (BBB again, SPY not).
- 4 five guards: calendar_line, book_line, chain_line, lock_file (OSError only), `_set_pdeathsig` (one printed line);
  two tests return 5, 6, 4, 0, 0, with the lock still held and the loop run supervised.
- 5 clamp in `NewsTrader.__init__` (bool, non-number, <= 0, NaN); test with 0, -1, "0.5": one "config" row each, the
  clock ends the loop.
- 6 drain wait 0 on STOP (d.457), priming stops on STOP and does not wait (d.91-105), a failed batch under STOP goes
  back with the never-started keys (d.271-274); three tests.
- 7 beats after the benchmark quote (d.127), after the closing send (d.245-246; a taken send beats in `_mark_told`),
  and in run_queue_at_open (d.149); three tests.
- 8 SKILL.md 3ב: the kill line replaced with the SIGTERM / 143 / two minutes / "stopping" / exit 3 / `kill -9`
  procedure, and the E1 paragraph (no hand edit, `verify` — it exists, __main__.py:90 — one message ending
  "כסף נייר", one question א/ב/ג recommending ג, buys stay blocked). Checked for bidi marks in added lines: none.
- Commit: exactly the five listed paths, `__main__.py` untouched, no attribution lines (checked `git log -1`).

Cannot verify from this diff:
- Item 7's third call. `run_queue_at_open` makes no second-check call (checked news_live.py 1448-1466 and `_buy`
  856-925: no outside call in `_buy` or `_log_trade`). The beat went after the live quote that stands in for a missing
  09:30 bar, the only call there followed by another call with no beat between. The ledger (progress.md:306) also says
  "the queue's second check". The controller should confirm this reading.
- The ledger's 9b list includes `state/*.tmp` in `.gitignore` (review m9); the brief does not. Not done here.
- Whether step 2's parent relays the engine's printed lines, which is what makes "no channel = said to the log" true
  for the owner.
- The suite (692 OK) and the 3x runs of both files: taken from the report, not re-run.

### Strengths

- Every item is a few lines, in the place the brief names, reusing `error_once`, `_note_error`, `_mark_told`, `_beat`.
- `notify.channels` mirrors `send` exactly: same env names and defaults, Telegram needs both values (checked against
  notify.py:46-70). It reads only whether a variable is set and never returns a value.
- RED evidence is real and item-specific (e.g. the slice test fails 143 != 0, the closing beat 4 not > 4, the drain
  (60, 60)). The tests check real behaviour: the lock is probed with a second `flock`, the slice spin is detected by
  counting sleeps, and the priming test times the poll.
- No test can reach the network, the model or the live state: poll, `_feed`, `score_batch`, `code_stamp` and
  `load_config` are stand-ins, the state is a temp dir, and the channels test uses invented variable names.
  `market_open_now`/`live_price` assignments are restored by `_Engine.tearDown` (checked test_news_guards.py).
- A local `_Engine` keeps "[] = a configured channel failed" for the file's older tests, instead of letting item 2 make
  them vacuous. Checked: no other test module reads `told_through`, `_unsent`, `_mismatch_told` or `say_late`.
- The time machine does not read `news` (checked backtest/strategy/signals/learn/data/metrics).
- `_lock_holder` already tolerates the empty lock file the new guard can leave (checked).
- The report is candid: departures, readings and five concerns listed.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

1. news_live.py:1552 (d.247-249), plan-mandated by brief item 1 ("once per step"). The late-line retry has no
   back-off. Late rows exist when an outage spanned a restart, so they turn up during outages. Then every step makes
   one more send, up to 15 s per configured channel, between the end-of-step look and the next step's first look.
   That is exactly the N5 cost item 3 removes from the closing message. In that case 9b's net effect on the gap
   between stop looks is about zero (critic N5: the gap grows from about 20 s to 35-50 s). Why it matters: the stop
   looks are the project's first safety property. Fix: gate step()'s `say_late()` by `news.unsent_resend_seconds`
   with a monotonic stamp of the last attempt, keep the start's call unthrottled, and add one GateFollowUps test (two
   failed attempts 30 s apart make one send).

#### Minor (Nice to Have)

1. tests/test_news_supervised.py, `WhoWasTold.test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start`
   (d.697-698). The exact list became a set, which drops the count. Each step's retry now writes a `late_line` row via
   `_note_error` whenever the send raises, a row every ~20 s all session. `error_once`'s docstring exists to stop
   exactly that. The closing message's `step_alert` row behaves the same way, so this is not a new kind of row. Use
   `error_once("late_line", e)` in `say_late`, or assert `[...] * (1 + steps)`.
2. news_live.py:766-767 (d.93-95). `asked = [ex.submit(...)]` sits outside the `try`. An exception in `submit` leaves
   the executor never shut down, a guarantee the old `with` block gave. Move the submit list inside the `try`.
3. news_live.py:1542-1543 (d.235-236). `carried = earlier + self._unsent[mine:]` and `_carried_at.update(...)` now sit
   outside the `try` that used to hold `self._unsent[mine:]`. A raise there would replace the step's own exception and
   skip `_step_measured`. It cannot raise on a trader built by `__init__`, but step() otherwise guards half-built
   traders with `getattr`. Move both lines inside the `try`.
4. news_live.py:619-627 (d.63-69). `news-score` (__main__.py:318) also builds `NewsTrader`, so a bad slice writes a
   "config" row there too, not only "at the start". It is harmless, but the clamp is not start-only.
5. news_live.py:d.99-105 with `_run` 1946-1948. A planned stop during a first start's priming saves the partial
   `seen`. The next start then skips priming (`not nt.seen` is false), so headlines from unprimed feeds inside
   `fresh_minutes` are scored and can be bought. The brief accepts "simply not primed", but this consequence is not
   said anywhere. Consider not saving `seen` after a cut priming, so the next start primes again, or note the edge in
   the docstring.
6. news_live.py:1871, 1881, 1903, 1841 (d.371, 380, 403, 341). The new guards record `str(e)[:300]` in
   news_errors.jsonl. The constraints say an error path carries an exception class, never its text. This is the same
   helper and the same form as the E1/E2 guards. `notify.send` catches `requests` errors itself, so the realistic
   texts here (a queue write, a template key, ENOSPC) carry no topic or token. A class-only detail would close it.
7. news_live.py:1970 and 1982. The loop's ChainBroken alert and the alert_after_errors alert stay unguarded. A raise
   there still turns exit 4 into a traceback. This is outside item 4's scope ("the start's"); it is the implementer's
   concern 2, worth a follow-up.
8. tests/test_news_supervised.py:1067-1069. The SKILL test's "כסף נייר" check passes on text already in 3ב. It does
   not check the three options, the ג recommendation or the two-minute bound.

### Assessment

Task quality: Needs fixes. Every item is built as the brief asks and well tested, and nothing changes a buy, sale or
stop rule. One plan-mandated Important remains: the per-step late-line retry has no back-off, which keeps the outage
cost item 3 removes and lengthens the gap between stop looks. The Minors are small and local.
