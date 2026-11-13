# Task 13 review: the parent's owner lines (when each is sent, the cap, quiet hours)

Base 5ab41f32, head 17e8f705, gate clone `.../scratchpad/clones/sup`. Review package: `review-task-13.diff` (2 commits,
4 files, +849 -42), read in three passes. No changed file was read outside the package. The checks I ran outside the
diff are listed with the risk each one tested.

### Spec Compliance

Compliant with the brief as the controller's rulings change it (rulings-10-28.md, Task 13 section: P5, P6, P10, P11, P13,
P18(b), P26, P29).
- Files: `aitrader/deadman.py` (new), `tests/helpers/http_stub.py` (new), `aitrader/supervise.py`, `tests/test_supervise.py`
  each have their hunk. The `Foundations` import test also imports `aitrader.deadman` (test_supervise.py:597).
- Interfaces: `NtfyStub(answers, cancel_answers)` with `url`, `requests`, `pending`, `delivered`, `advance`, `stop`. It
  plays all six answer kinds and serves `/v1/health`, both cancel forms and the poll with the eight fields of P10.
  `Sender(base_url, topic, timeout, env, sync)` has `publish`, `request`, `results` (with `reset_s`, P26) and `health`.
  `may_send` and `gap_line` keep the brief's signatures.
- The opener: `ssl.create_default_context(cafile=SSL_CERT_FILE or REQUESTS_CA_BUNDLE)` and a `ProxyHandler` built from
  env, empty when env's NO_PROXY names the base host. `--net-check` prints what `health()` returns, exits 0 only on 200,
  publishes nothing, and touches no state.
- Lines: the title is "AI Trader - מפקח" and the priority is ownerlines' word mapped to ntfy's number. `held_text` takes
  `held_names_in_line`, the times are on `owner_tz`, and the one `render` call passes `max_line_bytes` and
  `free_text_max_chars`.
- Every sending point is in place: R1 per episode, with cause, falls, down_s, blind_s, sold, code and n. R2 has both
  forms with P5's timing, and a lone hang kill sends no R1. Then R3/R3b/nothing, R3c, R5a/b/d, R5c, R6 (unless blind),
  R6b, R7, and R4/R4b by `gap_line` with `m` in the row (P6).
- Rows: `alert` rows are written `sent` true, false or "capped". A failed line is retried every
  `alert_retry_seconds` for `alert_retry_minutes`, and a late success adds a row with the same id. Ids continue from the
  day's rows (P13). On the way out the parent waits `send_timeout_seconds` (P18(b)) and writes the rows before
  `sup_stop`. `left` goes into the marks (spec 6 line 508: "into every mark"). The log holds a status or a class name.
- Tests: the brief's 8 exist under their names with the brief's assertions, and the stand-ins are written in.
  `test_one_r1_for_an_episode_of_three_falls` lets each crash run beat 3 times first. That is still "crash, crash,
  crash, then beats for good" and it is a stronger test (departure 2, accepted). There are 11 more tests: 7 for rulings
  and 4 from the implementer's self-review.
- Commits: no attribution lines. The first message is the brief's own. The tree is clean, and nothing changed under
  state/, logs/, reports/ or research/ (checked with `git log` / `git status` / `git diff --stat`).

Cannot verify from this diff:
- `restart_core` (unchanged) calls `watch`/`look` while no child runs, during a back-off. Retries and R7 are driven only
  from `look`.
- The engine's beat always carries a number as each held name's stop. A null stop makes `held_text` raise, and the line
  is not built (see Minor).
- ntfy's real `RateLimit` header, the JSON publish to `<base>/`, and the poll's field names. Task 22 confirms these on a
  real reply.
- `urllib` reaches ntfy through the session proxy and CA bundle (spec 6, "Not verified"). Task 20's `--net-check` asks.
- `load_state` keeps the `alerts` key for a second parent on the same day (Task 10 code).

### Strengths
- The loop never waits for the network. `publish` only queues, and `drain` reads the results on each tick. The
  implementer killed a `sync=True` mutant with `test_a_stub_that_never_answers_does_not_delay_a_restart`.
- The topic stays out of everything on the parent's path. It goes into the request body (POST to `<base>/`) and
  nowhere else. Errors are named by class, and for a `URLError` by the class it wraps. The leak test checks every file
  under tmp, stdout and stderr, after a 500, a hang and a refused connection.
- `may_send` is small and pure apart from `st`, and it replaces `alerts` whole, as the shallow merge requires.
- `gap_line` reuses `open_seconds`, which spans several days (supervise.py:294-306, checked). R4b reads its words from
  `ownerlines.WORDS["R4b.why"]` (checked: handover, crash_loop, signal and orphaned), so halt, lock_held, end_of_day and
  closed_today give None, as the brief says.
- The cold R4 form is exercised end to end: `test_the_rows_of_r4_and_r4b_carry_their_minutes` runs on a fresh directory
  with no heartbeat and asserts `sent` true.
- `Parents.config` sends every parent test's lines to a dead local port, so no parent test can post to ntfy.sh.
- The ordering fix in commit 17e8f705 (save, then the `code` row) is reasoned out and reproduced, not guessed.
- The implementer ran a mutation pass (18 mutants), and the report is candid about its readings and concerns.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
- `ai-trader/aitrader/deadman.py:126` (and `_work`/`_run`, lines 104-119): the URL is built outside the try, and the
  worker's job loop has no guard.
  - What happens: `urllib.request.Request(f"{self.base}/{self.topic}{suffix}")` runs before the `try` at line 127. A
    base URL with no scheme makes it raise `ValueError("unknown url type: '<base>/<topic>/...'")`. The exception
    escapes `_run`. The single worker thread dies, and `threading.excepthook` prints the exception text to stderr.
  - Check I ran: on a scratch copy of deadman.py, under the `safe` wrapper with no network,
    `Sender('ntfy.example', 'SECRET-TOPIC-X', 1, env={}).request('GET', '/json?poll=1', 'poll')` printed
    `ValueError: unknown url type: 'ntfy.example/SECRET-TOPIC-X/json?poll=1'` to stderr. A `publish` after it got no
    result at all (`results: []`).
  - Why it matters, for the topic: this is Review Focus 5 ("urllib errors print URLs") and the constraint that the topic
    never reaches stdout or an error path. `request()` is specified in this task for Task 21's cancel and poll, which
    put the topic in the URL.
  - Why it matters, for the parent: any unexpected exception in a job ends every later owner line for the parent's life.
    Pending lines stay "in flight" for good, are never retried, and get a `sent` false row only at exit.
  - Fix: build the `Request` inside the `try` in `_ask`. In `_work`/`_run`, catch `Exception` around the job and record
    `{"error": _name(e)}`, so the worker survives and the class name is the only trace. Add one test: a schemeless base
    and a `request()` call give a result with an error class, nothing on stderr, and a later publish still gets a
    result.

#### Minor (Nice to Have)
- `ai-trader/aitrader/supervise.py:615`: a line that cannot be built (KeyError/ValueError/TypeError) is logged by class
  and dropped. It gets no `alert` row, so `--status` cannot relay it. A `None` stop in a beat or a book makes an urgent
  "stops are not checked" line (R3/R5a/R5b) vanish for the owner. Consider writing an `alert` row `sent` false with
  the kind, or rendering `{held}` with a fallback for a name that has no number.
- `ai-trader/aitrader/supervise.py:701`: R7 is checked only in `look`. If the first line of a new hour comes from the R3
  or R5 calls after `restart_core` returns (supervise.py:882 onward), `may_send` resets `alerts` to the new hour and
  the previous hour's capped count never reaches R7. If R7 fails to render, it is tried again on every tick (log noise
  only). Edge cases.
- `ai-trader/aitrader/supervise.py:631-651`: with no topic, every line is still "retried" every `alert_retry_seconds`
  for `alert_retry_minutes`, with a "no topic" log line each time, though nothing can ever be requested. Delete the
  line from `pending` after its first false row when the sender has no topic.
- `ai-trader/tests/test_supervise.py:1441`: the proxy test has to blank `os.environ`'s NO_PROXY because urllib's
  `ProxyHandler.proxy_open` consults the process environment's no_proxy as well as the `env` given to the Sender. So
  "env decides" holds only when env is `os.environ`, which is the production default. Worth one line in the `_opener`
  docstring.
- `ai-trader/aitrader/supervise.py:577-664`: `main` gained six more nested closures and three more shared mutable dicts
  (`seen`, `ep`, `pending`). The style matches the existing closures, but `main` is now hard to follow. The line
  bookkeeping (`say`/`drain`/`finish`/`pending`) could become a small object later.
- `ai-trader/tests/test_supervise.py:1424`: `test_ntfys_remainder_goes_into_the_marks` needs R1 answered within about 3 s
  of start, before the 10:01:00 mark (margin about 1.8 s), so it could flake on a slow machine.
- `ai-trader/tests/helpers/http_stub.py` (poll): `since` is ignored and every message is listed. That is fine for this
  task. Task 21 or 25 tests that depend on `since` filtering would need the stub extended (which those tasks may not
  do, per P10's finding).

### Assessment
Task quality: Needs fixes. The task meets the brief and every ruling that binds it, and the tests are real behaviour
tests on a local stub. One fragile spot in the new `Sender` is enough to block: an exception outside the request's `try`
kills the only worker thread and prints the exception text, which carries the topic for `request()`. That is the
error-path leak Review Focus 5 names. The fix is two small guards and one test.
