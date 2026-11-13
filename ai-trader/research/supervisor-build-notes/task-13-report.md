# Task 13 report - the parent's lines to the owner

Gate clone `<SCRATCH>/clones/sup`, branch `supervisor-build`.
Checks before anything else: HEAD `5ab41f3253b48d508b8a780a26fa8ae65bf16ca0`, branch `supervisor-build`, clean tree.

Final HEAD `17e8f705102e04661e9f0ccdab7a448aa6714afc`. Two commits, both on the brief's four paths only, no attribution
line of any kind, `git status --short` empty after each:
- `f2037aff` feat(ai-trader): the parent tells the owner about every restart, hang, trip, halt and gap, one line per event
- `17e8f705` fix(ai-trader): the parent saves its state file before it writes the code row, so whoever reads the row
  finds the state saved (self-review fixes, see below)

No `git stash` in any form; no push, fetch, merge, rebase, reset or branch command; `_tasks` untouched. Every python
command ran through the `safe` wrapper (tests, the whole suite, the scratch peek, the mutation runner, the probes).

## What I implemented

### `tests/helpers/http_stub.py` - `NtfyStub` (new, standard library)
- `ThreadingHTTPServer` on the literal `127.0.0.1`, port 0; `url`, `requests` (`{"method", "path", "json"}`), `pending`
  (by sequence_id), `delivered`, `advance(seconds)`, `stop()` (idempotent; releases hung requests, then a request is
  refused). Nothing is written to any file; the handler logs nothing (pristine output).
- Answers, in order, then `{"status": 200, "left": 249}`: `answers` for publishes, `cancel_answers` for the DELETE and
  the GETs on the topic paths (the delete form and the poll). 200 sends `RateLimit: "messages";r=<left>;t=3600`;
  `retry_after` sends `Retry-After`; `{"status": 429}` sends no ntfy header; `{"hang": true}` never answers.
- POST `/`: a `delay` ("6m", "10m", "30s", a number) keeps the message in `pending`; the same sequence_id replaces a
  waiting one; no delay delivers at once. DELETE `/<topic>/<seq>` and GET `/<topic>/<seq>/delete` cancel.
  GET `/<topic>/json?...`: one JSON line per delivered and per waiting message with ntfy's eight fields (ruling P10):
  `id, time, event, topic, message, title, priority, sequence_id`; a waiting one's `time` is in the future (H1).
  GET `/v1/health`: 200.
- Its own clock `clock`, in whole Unix seconds (so `at` differences are exact); `advance` delivers what is due, at its
  due time.

### `aitrader/deadman.py` - `Sender` (new, standard library only, imports nothing of the package)
- `Sender(base_url, topic, timeout, env=None, sync=False)`: one worker thread and a queue (`sync=True`: in the
  caller's thread). `publish(payload, tag)` (the topic goes into the body inside the sender, POST to `<base>/`),
  `request(method, suffix, tag)` (`<base>/<topic><suffix>`), `results()` (drained), `health()` (GET
  `<base>/v1/health`, no topic: the status or a class name).
- Result: `{"tag", "ok", "status", "error", "left", "reset_s", "retry_after", "lines"}`; `status` (HTTP) or `error`
  (an exception's class; for urllib's `URLError` the class it wraps, e.g. `ConnectionRefusedError`), `left`/`reset_s`
  = `r`/`t` of `RateLimit` (ruling P26), `lines` = a GET's JSON lines, in memory only. With no topic nothing is
  requested and the result is not ok (status and error None).
- The opener: `ssl.create_default_context(cafile=env SSL_CERT_FILE or REQUESTS_CA_BUNDLE)` and a `ProxyHandler` from
  env's `http(s)_proxy` / `HTTP(S)_PROXY`, empty when env's `NO_PROXY` names the base host.
- `PRIORITY` maps ownerlines' words to ntfy's numbers (high 4, urgent 5, ...).

### `aitrader/supervise.py`
- `may_send(st, line_id, now, cap)`: R1, R2, R6 counted in the clock hour (`alerts.hour` = UTC "YYYY-MM-DDTHH");
  R1 and R2 over the count held back (capped += 1), R6 counted and never held back, every other line goes and is not
  counted; a new hour restarts the counts; `alerts` is always replaced whole (Ruling 30, shallow same-day merge).
- `gap_line(prev, up_at, cold, cal, sup)`: as the brief; `>= outage_report_seconds` of session time in [prev.t, up_at];
  R4 (with `cold_time` = prev.t on `owner_tz` when cold) unless prev is a `sup_stop`; R4b when its `why` is a key of
  `WORDS["R4b.why"]`; else None. Fields: `time`, `time2`, `m` (round(seconds / 60)), plus `cold_time` or `why`.
- `--net-check`: needs no `--until`; prints `supervise: net-check <what health() returned>`, exit 0 only on 200, nothing
  published, before the lock.
- `Paths.book` (ruling P11). `NUMBERS` also validates the eight keys the lines read.
- In `main`: a `Sender` on `alerts.ntfy_base_url` with the topic of `env` (default `os.environ`), and four helpers:
  - `say(kind, now, extra, **fields)`: renders from `ownerlines` (every call passes `max_line_bytes` and
    `free_text_max_chars`; `{held}` through `held_text(..., held_names_in_line)`, R1's `{sold}` through `sold_text`),
    title "AI Trader - מפקח", ownerlines' priority as ntfy's number; id `<kind>-<n>`, n seeded at `sup_start` from the
    largest n of that New York day's `alert` rows (ruling P13); `may_send` false: an `alert` row `sent` "capped";
    the state file saved (the hour's counts survive the parent).
  - `drain(now)` (every loop tick): an `alert` row `{id, kind, sent, text}` (+ `m` for R4/R4b, ruling P6) `sent` true,
    or `sent` false at a line's first failure; tries again every `alert_retry_seconds` for `alert_retry_minutes`; a
    late success adds a row with the same id. `left` of an answer goes into the marks. The log gets
    `line <id>: <status or class>`, never a URL or a message.
  - `finish()` (every way out): `send_timeout_seconds` for the lines in flight (ruling P18(b), no +1 s), then a row
    `sent` false for each without an outcome; all this before the `sup_stop` row.
  - `held_now(pid)`: the child's own beat, else the book's positions and `stop_price` (ruling P11).
- The sending points:
  - R1 at the end of a restart episode (the current child has its `up` and has run `healthy_seconds`), once: time and
    cause of the first fall (code: "crash", signal or hang kill: "killed", 0/143: "stopped"), `down_s` first fall to
    last `up`, `blind_s` summed, `falls` from the second fall, `sold` of the episode's `up` rows, `code` of its `code`
    rows with `code_changed`, `n` = `restarts_today`. A fall = an exit row that is neither a lock refusal (3) nor
    planned. No R1 when a hang kill was the only fall (P5).
  - R2: switch off, the "לא נהרג, המתג כבוי" form at the `hang` row; switch on, the kill form at the first `up` after
    the kill, with that `up`'s time (HH:MM:SS, owner_tz) and `blind_s` and the hang row's `hb` (P5).
  - R3 / R3b / nothing at the first / second / later trip of the day; R3c in place of R3 when every exit since the last
    healthy run was 7. R5a, R5b, R5d at 4, 5, 6; R5c at `lock_held`.
  - R6 at `stale_stops` start unless every stale name is in the beat's `blind`; R6b at its end when R6 went out.
  - R7 once the clock hour of `alerts.hour` has passed with capped lines.
  - R4 / R4b at the parent's first `up`, by `gap_line`, with `m` in the row.

### `tests/test_supervise.py`
- `Foundations.test_supervise_imports_no_pandas_no_requests_and_no_engine_module` also imports `aitrader.deadman`.
- `Parents`: `ENV` (more variables for the parent's environment), `ntfy_url` (default `http://127.0.0.1:9`, a dead
  local port, written into every config copy), `paths` (property), `fresh(state)`, `ids()`, `run_parent(...,
  stop_after=None, **sup)` (config overrides; SIGTERM from a timer, with a no-op handler around the call so a late
  signal cannot hit the test runner). `spawn_parent` passes `ENV`.
- Class `ParentLines(Parents)`: a `NtfyStub` per test (`answers([...])` starts a new one), topic "t0p1c-under-test"
  in `ENV`. 19 tests (below).

## TDD evidence

### RED (as the brief expects)
`cd ai-trader && .../safe python3 -m unittest discover -s tests -p test_supervise.py -k ParentLines`, with the tests
written and no stub, sender or supervise change:
```
    from helpers.http_stub import NtfyStub
ModuleNotFoundError: No module named 'helpers.http_stub'
Ran 1 test in 0.000s
FAILED (errors=1)
```
Expected: the helper module did not exist yet. (I had written the stub first by mistake; I moved it out of the clone
before this run and back after, so the run above is the real RED.)

Second RED level, with the stub and `deadman.py` in place and `supervise.py` unchanged (15 tests then; summary by
`sort | uniq -c`):
```
      1 AttributeError: module 'aitrader.supervise' has no attribute 'may_send'
      1 AttributeError: module 'aitrader.supervise' has no attribute 'gap_line'
      3 IndexError: list index out of range                       (no alert row)
      1 ValueError: not enough values to unpack (expected 1, got 0)
      1 AssertionError: Tuples differ: ([], 4) != (['R5a'], 4)
      1 AssertionError: Tuples differ: ([], 0) != ([False, True], 1)
      1 AssertionError: Lists differ: [] != [('R5a', False)]
      1 AssertionError: Lists differ: [] != ['R5b-4']
      1 AssertionError: Lists differ: [] != ['R2']
      2 AssertionError: not within 5/10 s: <lambda>             (no request ever reached the stub)
Ran 15 tests in 42.095s
FAILED (failures=7, errors=6)
```
The two that passed were the stub and sender tests (P10, P26), whose code existed by then. Expected.

### GREEN
`... safe python3 -m unittest discover -s tests -p test_supervise.py -k ParentLines -v`, on the final commit:
```
test_a_capped_line_is_on_record_and_never_requested ... ok
test_a_hang_kill_says_r2_at_the_restart_and_r1_only_when_the_new_child_falls_too ... ok
test_a_line_that_failed_is_tried_again_and_a_late_success_adds_a_sent_row ... ok
test_a_stub_that_never_answers_does_not_delay_a_restart ... ok
test_alert_ids_go_on_from_the_days_rows ... ok
test_gap_line ... ok
test_ntfys_remainder_goes_into_the_marks ... ok
test_on_its_way_out_the_parent_waits_send_timeout_seconds_and_records_an_unanswered_line ... ok
test_one_r1_for_an_episode_of_three_falls ... ok
test_r1_says_what_the_restart_sold_and_the_new_code ... ok
test_the_cap_holds_back_r1_and_r2_never_r6_and_r7_counts_them ... ok
test_the_lines_of_a_halt_a_trip_and_a_held_lock ... ok
test_the_lines_of_a_hang_and_of_stale_stops ... ok
test_the_rows_of_r4_and_r4b_carry_their_minutes ... ok
test_the_sender_goes_through_the_proxy_of_its_env_unless_no_proxy_names_the_host ... ok
test_the_sender_reads_status_left_reset_and_retry_after_and_names_an_error_by_its_class ... ok
test_the_stub_keeps_a_delayed_message_until_its_time_and_polls_with_ntfys_fields ... ok
test_the_topic_reaches_no_file_and_no_output_and_net_check_says_the_status ... ok
test_with_no_beat_of_its_child_a_line_lists_the_books_names ... ok
Ran 19 tests in 70.061s
OK
```
- The brief's 8, under its names and assertions, stand-ins written in.
- Tests added by ruling (7): P5 (`test_a_hang_kill_says_r2...`, both halves of the ruling), P6 (`..._r4_and_r4b_carry_
  their_minutes`), P11 (`..._lists_the_books_names`), P13 (`test_alert_ids_go_on_from_the_days_rows`: yesterday's
  R1-9 ignored, today's R1-3 twice -> R5b-4), P26 (`test_the_sender_reads_status_left_reset...`), P10
  (`test_the_stub_keeps_a_delayed_message...`), P18(b) (`test_on_its_way_out...`: a hung publish, send_timeout 1,
  return within 1-2.5 s, one row R5a `sent` false, and the last row is `sup_stop`).
- Tests added in self-review (4): a capped line in the loop (row "capped", no request, state `capped` 1); ntfy's `left`
  in the marks; R1's `{sold}` and `{code}` parts; `NO_PROXY` of the sender's env (with `os.environ`'s cleared).

The whole file starts processes: on the final code it ran three times in a row, `Ran 92 tests` `OK` each (145.3 s,
143.4 s, 142.5 s); before the review fixes also three times (144.5, 143.5, 144.3 s) and three more earlier. Output
pristine: one dot line and the summary.

The hour (the 11:10 ruling): every new process test uses the dummy child, which ignores `--until`, and the parent's
moved clock (10:00 New York on 2026-11-12; 10:59:57 and 10:00:57 in two tests); `gap_line` and P6 read only moved or
fixed times. Every run above was made after 16:05 New York (the last ones between 22:15 and 22:50 EST).

### Mutation pass
Scratch runner `<SCRATCH>/t13/mutate.py` (each mutant on
`supervise.py`, its target tests, restore checked byte for byte). 18 mutants, all killed in the end: R6 held back over
the cap; no R7; R6 despite `blind`; R1 at every fall; R1 after a lone hang kill; no R3c; R3b again at the third trip;
no retry; no wait on the way out; rows after `sup_stop`; ids from 1 in each parent; no book fallback; no `m`; no `left`
in marks; capped lines sent; no R2 off form; no R4b; the loop waiting for the network (`sync=True`).
Two survived the first pass: "rows after sup_stop" was a broken mutant (it wrote `sup_stop` twice; redone, killed);
"R1 at every fall" survived because the brief's crash runs never beat, so every fall came before the first `up` - see
departure 2.

## Whole suite
`.../safe python3 -m unittest discover -s tests` from `ai-trader/`, on the final code, wall 207 s:
```
Ran 778 tests in 206.462s

OK
```
778 = 759 (end of Task 12) + 19. (Before the first commit: `Ran 778 tests in 200.276s` / `OK`, wall 201 s.)

## Files changed
- `ai-trader/aitrader/deadman.py` (new, 145 lines)
- `ai-trader/aitrader/supervise.py` (+313 -42 with the test file; 912 lines)
- `ai-trader/tests/helpers/http_stub.py` (new, 158 lines)
- `ai-trader/tests/test_supervise.py` (1443 lines)

## Self-review (`git diff 5ab41f32..HEAD`) and what I did
- The brief line by line against the code: every line id, when it goes, its fields, the cap, the retry, the rows, the
  log, `--net-check`, the stub's answers and paths, and the five rulings this task builds (P5, P6, P10, P11, P13, P18(b),
  P26). Found and fixed:
  - A flaky existing test, `ParentLoop.test_a_second_parent_returns_3_names_the_holder_and_writes_nothing`: failed
    once in one whole-suite run. It snapshots state/ when the first parent's `code` row appears, and the parent saved
    the state file right after that row (Task 12's order, kept by me). Probed: with the old order the state file is
    absent at the row and appears after it. Reproduced: with 0.05 s between row and save, old order 5/5 FAILED, new
    order (save, then row) 5/5 OK. Fix in `supervise.py`: `save()` before `emit("code")` (commit `17e8f705`). The test
    itself is unchanged.
  - Two leaked worker threads in the proxy test: its senders now run `sync=True`.
  - `seen["gap"]` re-read the last row; it now takes `prev`, which `main` already holds.
  - `serve_forever`'s 0.5 s poll made every `stub.stop()` cost 0.5 s; 0.05 s now (-6 s for the class).
  - The R1 test's crash runs, see departure 2.
  - One line over 120 characters (the `Paths` docstring), reflowed.
- Checked and left: the loop never blocks on the sender (publish only queues; results are drained); the topic is in a
  request body or URL only; the `alert` rows come before `sup_stop`, so the row before the next `sup_start` stays the
  `sup_stop` that `gap_line` and `--status` read.

## Departures from the brief, and readings where it is silent
1. Import order in the test file: `from helpers.http_stub import NtfyStub` comes before `from aitrader import ...`, so
   RED shows the brief's message (with the package import first, RED named `deadman`).
2. `test_one_r1_for_an_episode_of_three_falls`: the crash runs beat 3 times before they crash
   (`[{"beats": 3, "then": "crash"}] * 3 + [{"beats": -1}]`, `stop_after=4`). Still "crash, crash, crash, then beats
   for good", and the assertion is the brief's. With crash runs that never beat, a parent that sent R1 at the first
   `up` instead of after `healthy_seconds` passed the test (mutation survivor).
3. 19 tests in `ParentLines` where the brief has 8: 7 by ruling, 4 from self-review (named above).
4. Two additions to the interfaces: `Sender.close()` (the worker ends after the jobs before it; `main` calls it in its
   `finally`, so an in-process parent leaves no thread), and `NtfyStub.clock` (its clock, exposed so tests can read
   message times against it).
5. The sender builds its opener at its first request, inside that request's try: a CA file that cannot be read fails
   the request with its class name instead of stopping the parent.
6. `--until` is no longer `required=True` in argparse: `main` calls `ap.error` with argparse's own message when it is
   missing, unless `--net-check`.
7. `Parents.config` writes `alerts.ntfy_base_url` = `http://127.0.0.1:9` into every config copy (ParentLines: the
   stub), so no parent test can ever post to ntfy.sh, topic or not.
8. `left` is the last answer's remainder in every mark after it, not only the next one (Task 14 reads the last mark).
9. The state file is saved at every line (the hour's counts) and before the `code` row, not only at the parent's end.
10. P18(b) as ruled: the way out waits `send_timeout_seconds`, not +1 s; a line without an outcome by then gets a row
    `sent` false (else it would have no row and `--status` could not list it for relay).
11. Readings:
    - R3: `{k}` = the tripped row's `restarts` + 1 (the falls); `{m}` = the window in minutes for a window trip
      ("6 falls in 10 minutes"), and for the day's limit the minutes since the day's first uptime row.
    - R5c `{s}`: seconds since the first refusal of this run of refusals.
    - R6 `{s}`: the start row's stop age; when it cannot be read, the seconds since this child started. R6b `{s}`: R6's
      `{s}` plus the time between the two rows.
    - R1 `down_s` and `blind_s` with one decimal; R2's `{s}` is the hang row's `hb` (one decimal).
    - R3c: "since the last healthy run" counts the exits after that run, not the healthy run's own exit.
    - `{held}` of R3, R3b, R3c, R5a, R5b: the beat of the last child when it is that child's, else the book.
    - A line that cannot be built (an unknown field, a stop that is not a number) is logged with the class name and
      not sent.
    - With no topic: no request, the row says `sent` false, the log says "no topic".
    - Stub: `since` is not filtered (every message is listed); health is always 200.

## Concerns
1. R6 after a slow restart (Task 12's concern 4, now with lines): when a restart takes over `stops_stale_seconds` with
   a name held, the new child's first beats carry the old stamp, so R6 and then R6b go out besides R1. That follows spec
   4.3 to the letter; whether R6 should skip the boot of a restarted child is the controller's call.
2. An episode cut by a planned stop or a handover (falls within the last `healthy_seconds` before it) never gets its
   R1; the next parent does not know those falls. The spec is silent.
3. `held_text`/`sold_text` (Task 2) format numbers: a beat or a book with a null stop makes the line fail to build. It
   is logged by class, not sent. The engine always writes a number.
4. The suite grew by about 65 s (ParentLines 70 s); most of it is the `stop_after` values of the brief's tests.
5. Commit metadata (as Task 12 noted): the author is the gate clone's configured identity; the messages carry no
   attribution.

## Fix round 1

Checks before anything else: HEAD `17e8f705102e04661e9f0ccdab7a448aa6714afc`, branch `supervisor-build`, clean tree.
Final HEAD `236430fade78e72aa6a7ad3adbe1a3213bd9f614`. One new commit, nothing amended, `git status --short` empty after it:
- `236430fa` fix(ai-trader): the sender's worker survives any failed job and names it by class only

No `git stash` in any form; no push, fetch, merge, rebase, reset or branch command; `_tasks` untouched. Every python
command ran through the `safe` wrapper. No attribution line in the commit.

### F1 (Important) - fixed
- `ai-trader/aitrader/deadman.py:125-130` (`_ask`): the `Request` (both the publish and the `request()` form) is now
  built inside the `try`, so urllib's refusal of a URL (`ValueError: unknown url type: '<base>/<topic>/...'`) is caught
  by the existing `except Exception` and returns `{"error": "ValueError"}`; the URL text goes nowhere.
- `ai-trader/aitrader/deadman.py:117-120` (`_run`, the one function both the worker and `sync=True` run per job): the
  `_ask` call is guarded; any exception becomes `r["error"] = _name(e)` and the result is still appended, so the worker
  thread never dies and every job gets a result. (The guard is in `_run` rather than `_work` so it covers both modes;
  `_work` only loops over `_run`.)
- Test `ai-trader/tests/test_supervise.py:1445`,
  `ParentLines.test_a_request_that_cannot_even_be_built_is_named_by_its_class_and_the_worker_lives_on`:
  - a threaded `Sender("127.0.0.1", TOPIC, ...)` (no scheme, no port: urllib refuses the URL before any socket, and if
    it ever got further it would be this machine), with stderr redirected: `request("GET", "/json?poll=1", "poll")`,
    then `publish(...)`; asserts both results come back as `(tag, False, None, "ValueError")` and stderr is `""`;
  - then a `sync=True` sender on the stub with `deadman._number` patched to raise `RuntimeError(TOPIC)` (a surprise after
    the request's `try`): the publish comes back as `("odd", False, "RuntimeError")` instead of raising.
- RED (the test on the old `deadman.py`):
  ```
  AssertionError: Tuples differ: ([], 'Exception in thread ntfy-sender:\nTra[1408 chars]'\n') != ([('poll', False, None, 'ValueError'), ('li[32 chars], '')
  Ran 1 test in 5.021s
  FAILED (failures=1)
  ```
  No result at all, and the dead worker's traceback (which quotes the URL with the topic) on stderr: the reviewer's probe.
- Mutation check (scratch copies, restored and compared byte for byte): old file FAILED (above); without the `_run` guard
  FAILED (`RuntimeError: t0p1c-under-test`, the second half); with only the `_run` guard (the request built outside the
  `try` again) OK - the guard gives the same result, so that half of the fix is defence in depth and has no behaviour of
  its own to test.

### Covering tests
`test_supervise.py` starts processes, so the whole file, three times in a row, from `ai-trader/`:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py`
```
Ran 93 tests in 146.820s
OK
Ran 93 tests in 144.272s
OK
Ran 93 tests in 149.560s
OK
```
(walls 148 s, 145 s, 150 s; `ParentLines` alone: `Ran 20 tests in 69.938s` `OK`.)

### Whole suite (before the commit)
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`, wall 220 s:
```
Ran 779 tests in 219.189s

OK
```
779 = 778 + the one new test. The topic does not appear in the suite's output (`grep -c t0p1c` = 0); the other printed
lines are the existing `[news] ...` prints of the engine tests.

### Not changed
The review's Minor items were not on the fix list and were left as they are.
