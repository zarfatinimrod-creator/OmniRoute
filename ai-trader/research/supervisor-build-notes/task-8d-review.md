# Task 8d review - the priming poll keeps its eight threads, with a beat after each feed call

Reviewed: 82b2036e..15c8c4e4 (one commit) in the gate clone, from the review package
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-8d.diff` (exit 0, 1 commit, 9266 bytes).
No test was re-run: reading the code raised no doubt that the reported runs do not answer.

### Spec Compliance

Compliant. Each item of the brief, checked against the diff:

- `aitrader/news_live.py:58` (package line): `ThreadPoolExecutor(max_workers=8)` for priming and for a step's poll alike; `max_workers=1 if prime else 8` is gone. Matches "the same pool size for priming as for a normal poll (8, as before Task 8a)".
- `news_live.py:59-63` (package lines): the futures are submitted, and only when `prime` is true the calling thread runs `for _ in as_completed(asked): self._beat(self._phase)`. The workers run `_feed` only (the 8a wrapper `fed`, which beat from the worker, is deleted). Matches "the calling thread takes the feed results as they complete ... writes `self._beat(<current phase>)` after each one ... No beat is written from a worker thread". `as_completed` is imported next to `ThreadPoolExecutor`.
- `news_live.py:63`: `batches = [f.result() for f in asked]` keeps the universe's order, as `ex.map` did, so headline handling order is unchanged.
- `tests/test_news_supervised.py`, `test_a_start_beats_after_every_send_git_call_and_priming_feed`: name kept; `len(seen) == 3 + 1 + 30` kept; the feed part of the old strictly-rising assertion is replaced by `after - before >= 30` (beats during priming >= feed calls) and `max(returned) < after` (the count each feed stand-in reads at its return is lower than the count once `poll_headlines` returned). Both are the brief's wording. The non-feed part of the old assertion is kept as `seen[:4]` strictly rising and `min(seen[4:]) > seen[3]`, which is the honest reading of "its other assertions stay".
- New `test_priming_asks_its_feeds_in_parallel`: 16 names, a 0.2 s feed stand-in, `assertLess(elapsed, 1.6)`, `assertGreaterEqual(writes, 16)`. Present under its exact name with the brief's numbers. One extra assertion (every beat from the calling thread) pins the brief's own "no beat from a worker thread"; it is a test of a stated requirement, not an extra feature.
- Commit message is the brief's, character for character; files are exactly the brief's two paths; nothing under `state/`, `logs/`, `reports/`, `research/` (checked with `git diff --stat 82b2036e 15c8c4e4 -- ai-trader/state ai-trader/logs ai-trader/reports ai-trader/research`: empty). No trailer, no "Generated with", no session link in the message.
- No buy, sale or stop rule is touched: the diff changes only how the feed results are collected.

Cannot verify from this diff alone:
- The commit's author identity is `Claude <<email>>`, as on every earlier commit of `supervisor-build` (checked `git log -6`). It comes from the clone's git config, predates this task, and is not one of the three forms the constraint lists; the whole-branch review should decide whether it meets "No AI attribution in any commit" before anything lands.
- Spec 5.5's purpose ("a write after every network call") is met by the priming poll here; whether every other network call of the start and the loop has its beat spans Tasks 4, 7, 8a and is not judged here.

### Strengths

- Smallest diff that does the job: +6 -7 in `poll_headlines`, the 8a worker wrapper deleted rather than worked around, and a step's poll left byte-for-byte equivalent in its results and its single "poll" beat.
- The single-writer property of `news_heartbeat.tmp` that 8a bought with a single worker is kept by construction: only the calling thread beats.
- Both new assertions in the restated test are deterministic, not timing-based: `as_completed` yields a future only after the stand-in has appended to `returned` and returned, so `max(returned) < after` cannot flake; the beat count during priming is exactly 30.
- The `primed` wrapper measures the count at the priming poll's own return instead of after `start()`, where the loop's later beats would hide a missing last beat. `(before, after), = priming` fails loudly if the priming poll is not called exactly once.
- The new test calls the priming poll directly, so its stopwatch measures only the feed fan-out; the 1.6 s bound is four times the expected 0.4 s and half the serial 3.2 s.
- The report's planted-defect table (7 mutants, including beats from workers and one beat short) shows each test earns its place; M5 is caught only by the extra thread assertion, which justifies it.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- `ai-trader/aitrader/news_live.py:63` (package line; `poll_headlines`): on an exception raised inside a feed call, a step's poll now waits for every queued feed before the exception surfaces (`with` exit = `shutdown(wait=True)` with no cancel), where `ex.map`'s result iterator cancelled the not-yet-started ones. Named risk checked: could this delay a stop look in practice? `_feed` (news_live.py:130-160) catches `requests.RequestException` and date-parse errors and parses with regex, so only a programming error raises; and the SIGTERM/SIGINT handler (news_live.py:94, 1783) only sets STOP and raises nothing, so a signal never takes this path. Worst case on such a defect: universe/8 x 10 s before a step that fails anyway. Fix if wanted: `ex.shutdown(cancel_futures=True)` in an `except` around the result read. Not worth code today.
- `ai-trader/tests/test_news_supervised.py` (restated start test, `seen[:4]` / `seen[4:]`): the split is positional and tied to the order in `_run` (sends at news_live.py:1865-1887, `code_stamp` at 1889, priming at 1894 - checked). A reorder of the start would make it fail loudly, not pass silently, so it is acceptable; a one-line comment naming that order would help the next reader.
- `ai-trader/tests/test_news_supervised.py` (restated start test, `primed`): it works because `start()` captures `NewsTrader.poll_headlines` at call time (test file line 1160-1161, checked) and only routes the priming call to it. That coupling to the helper's internals is implicit; the `(before, after), = priming` unpacking guards it.

### Assessment

Task quality: Approved. The change restores the eight-thread priming poll exactly as the brief rules, keeps every beat on the calling thread, and its tests pin the brief's two restated properties and the new parallelism with deterministic or wide-margin assertions; the one behavioural difference outside priming (no cancel on a feed exception) is reachable only through a programming error and never through a signal.
