# Task 3 review - the engine child for tests, and a lock that names its holder

Diff c6bec0f7..25d18a4b (one commit, 6 files, +572 -11), read from review-task-3.diff.

### Spec Compliance

Not compliant. Two issues:

1. ai-trader/tests/test_news_supervised.py:467 and :491 - the in-process starts `news_live.run(max_minutes=0.0005, prime=False)` pass no `until_ny`, so they run with the engine default "16:05". Controller ruling 2026-11-11 11:10 (binds Task 3): "every in-process start of a test passes "23:59"". Check run: with `news_live.datetime.now` patched to 17:00 New York (scratch script `<SCRATCH>/rev3/evening.py`, run on the clone, no file changed), `Lock.test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat` and `Unlocked.test_a_line_that_cannot_be_built_does_not_cost_the_book_its_only_engine` both ERROR: `TypeError: 'NoneType' object is not subscriptable` at `journal.load_json("news_heartbeat.json")["lock"]`. The loop breaks before its first step, so no heartbeat is written. The gate suite runs after 16:05 New York by rule, so the gate fails every evening. The brief's own fragment omits the argument; the ruling overrides it.
2. ai-trader/tests/helpers/engine_child.py:377-379 (`engine_options`) and ai-trader/tests/test_supervise.py:573-583 (`start_engine`) - the ruling puts the `--until 23:59` default in `Procs.start_engine`, with a comment naming the 23:59-00:00 ceiling. The implementation puts `--until 24:00` inside the engine child instead. Every caller of the child now gets a default the real engine does not have, including Task 8's PARENT script and the Task 17 drills. A supervisor parent that passes no `--until` would therefore be tested against an engine that never ends by the clock, which hides the real 16:05 behaviour. The implementer's report (concern 1) flags this itself.

Verified as built:
- `owner_line` reads `max_line_bytes` and `free_text_max_chars` from `cfg["supervisor"]` (news_live.py:54-58).
- The lock file opens with "a+" (news_live.py:111). After a successful `flock` it is truncated and rewritten as one JSON line with `pid` and `started_at` from `journal.now_utc()` (news_live.py:126-129).
- `BlockingIOError` gives the refusal message, `return 3`, and nothing is written (news_live.py:115-120). The process test asserts every state file is byte-identical and that nothing was sent (test_supervise.py:645-648).
- Any other `OSError` sets `locked=False`, sends one E2 from `_run` with the priority passed positionally (news_live.py:149-153), and puts `"lock"` in the heartbeat (news_live.py:84).
- `_run(..., *, locked=True) -> int`; `run()` returns what `_run` returns. Pinned by `TheLoopsAnswer`, where `_run` returns 7.
- config.json has a `supervisor` block with 1200, 6 and 200.
- The `OneEngine` stand-ins take `**k`, and the `_run` stand-in returns 0 (test_news_guards.py:415, :424).
- engine_child gives every scenario key in the table its default (engine_child.py:266-268). The tripwire covers the four calls, writes the name and ends with `os._exit(97)` without raising (engine_child.py:343-374).
- `hold()` and every `Procs` member are present, and the five named tests exist under their names with the brief's assertions.

Cannot verify from this diff:
- E2's final place after the first stop look. Task 7 owns that.
- The suite total (566, OK). I did not re-run it, per the dispatch.
- That the checker seams match tests/test_core.py exactly. engine_child.py:339-340 copies them; I did not open test_core.py.

### Strengths
- The lock change is small and correct. The refusal never depends on the file's text, because `_lock_holder` falls back to "unknown". An engine with no lock leaves the holder's file alone, and the test pins that (`read_text() == ""`).
- The tripwire is tested both ways: `Harness`, three tests. Five forbidden calls end with 97. Local socket, urlopen, requests and `sleep` go through. `engine_child.main` installs the wire before the engine runs. The forbidden targets cannot answer, so a broken wire still reaches nobody.
- A misspelt scenario key is refused before the engine starts (engine_child.py:388-390). This closes a real false-pass path.
- tearDown kills the orphan only when its cmdline is exactly `sleep 60`, so it never kills a reused pid. `wait_for` reports the engines that already died, with stderr.
- No threshold literal in `news_live.py`. No trading rule touched: the `news_live.py` hunks are the lock, E2, `owner_line` and one heartbeat key.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. ai-trader/tests/test_news_supervised.py:467, :491 - in-process `run()` starts use the default "16:05". The tests fail after 16:05 New York, which is when the gate runs (verified, see Spec 1). Fix: pass `"23:59"` as the first argument in both calls, as ruling 11:10 requires.
2. ai-trader/tests/helpers/engine_child.py:377-379 - the `--until` default lives in the child as "24:00", not in `Procs.start_engine` as "23:59" with a ceiling comment, as ruling 11:10 requires. It changes the engine's default for every caller of the child, including future parent and drill tests. Fix: remove `engine_options` from the child, or rule it explicitly. Add `--until 23:59` in `start_engine` when the options carry none, with the ceiling comment, and pass the child's options through unchanged.

#### Minor (Nice to Have)
- ai-trader/tests/helpers/engine_child.py:269, :287 - `QUICK = {"poll_seconds": 1}` overrides config.json's wait under every scenario. The brief's table does not have this. It is justified, because a 20.58 s wait was measured, but the controller should ratify it: later tasks inherit a 1 s loop.
- ai-trader/aitrader/news_live.py:149-153 - the E2 guard sends failures to `error_once`, which journals `str(e)[:300]`: exception text in a log. The risk is low because `notify.send` already swallows `RequestException`, but this is the pattern the constraints forbid. Prefer a type-only record.
- ai-trader/tests/test_supervise.py:585-593 - `write_book` dates entries today, while `hold()` uses 2026-11-09. The reason is documented. A later test needing an old entry will depend on the real calendar (report concern 2).
- ai-trader/tests/helpers/engine_child.py:365-373 - only the literal host `127.0.0.1` passes, not `localhost` or `::1`. This matches the brief. Later stubs must use that literal.
- Extras beyond the brief: `Harness` (7 tests), `TheLoopsAnswer`, `Unlocked`, and the unknown-key refusal. All are test-side and add confidence. None is production over-engineering.

### Assessment
Task quality: Needs fixes. The lock and engine-child work is sound and well tested. The two in-process lock tests fail at any time after 16:05 New York, when the gate runs, and the `--until` default sits in the child rather than the test harness, against the controller's ruling.
