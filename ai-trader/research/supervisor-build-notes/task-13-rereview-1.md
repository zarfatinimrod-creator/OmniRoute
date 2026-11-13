# Task 13 re-review, fix round 1

Fix range 17e8f705102e04661e9f0ccdab7a448aa6714afc..236430fade78e72aa6a7ad3adbe1a3213bd9f614 (one commit, 236430fa),
package `review-task-13-fix1.diff`. Read-only on the clone; no test re-run (reading the code raised no doubt that the
reported runs do not answer).

### Finding Verdicts

- **F1: ADDRESSED.**
  - `ai-trader/aitrader/deadman.py:124-130` (`_ask`): both `urllib.request.Request(...)` constructions, the publish
    (`base + "/"`) and the `request()` form (`f"{self.base}/{self.topic}{suffix}"`), now sit inside the `try`. A
    schemeless base raises `ValueError('unknown url type: ...')` at construction. The existing
    `except Exception as e: return {"error": _name(e)}` (line 135-136) catches it. `_name` returns only
    `type(e).__name__` for a non-URLError (line 38-42), so the URL and topic go nowhere.
  - `ai-trader/aitrader/deadman.py:116-122` (`_run`): `self._ask(...)` is wrapped in `try/except Exception` and sets
    `r["error"] = _name(e)`. The result is still appended under the lock. `_work` (line 102-104) only loops over
    `_run`, so no `Exception` from a job can end the worker thread. `sync=True` runs the same `_run` through `_put`
    (line 96-100), so it is covered too: a failed job no longer raises into the caller. Any surprise after the `try`
    (header parsing, `_number`, the GET line loop) now gives a class-name result, not a dead worker with pending lines
    stuck in flight.
  - Test `ai-trader/tests/test_supervise.py:1445`
    (`test_a_request_that_cannot_even_be_built_is_named_by_its_class_and_the_worker_lives_on`) is what the finding
    asked for. A threaded `Sender("127.0.0.1", TOPIC, ...)` runs `request("GET", "/json?poll=1", "poll")` and then
    `publish(...)` with stderr redirected. The test asserts both results come back as `(tag, False, None, "ValueError")`
    and stderr is `""`. The default thread excepthook writes to the current `sys.stderr`, so the redirect does capture
    a dead worker's traceback; the reported RED output shows `'Exception in thread ntfy-sender:\nTra...'` captured on
    the old code. The second half runs a `sync=True` sender against the stub with `deadman._number` patched to raise
    `RuntimeError(TOPIC)`. That exercises the `_run` guard directly, and the test asserts `("odd", False, "RuntimeError")`.
  - The implementer disclosed one gap, and I agree it is harmless: with the `_run` guard in place, moving the `Request`
    inside `_ask`'s `try` has no behaviour that can be seen on its own (the guard would name the `ValueError` the same
    way). So no test fails if that move alone is reverted. Both layers the finding asked for are present.

### New Breakage in the Fix Diff

None.

- The guard catches `Exception`, not `BaseException`. That is right for a worker thread (no `KeyboardInterrupt` reaches
  a non-main thread) and matches the existing `except` style of the module.
- `sync=True` callers used to get an exception from a malformed job and now get a not-ok result. That matches the
  `Sender`/`results()` docstrings ("status (HTTP) or error (a class name)"), and the reported full suite (779 OK)
  shows no caller depended on the raise.
- The two re-indented `Request(...)` lines are 122 chars (deadman.py:125, 127). No line-length gate exists for
  `ai-trader/`, and `ownerlines.py` has 46 lines over 120, so this is not a defect.
- The test's threaded sender is closed (`sender.close()`), and the stub is per test (`answers()` -> `addCleanup(stop)`).
  The extra "odd" publish cannot leak into another test.

### Out-of-Scope Observations

- `Sender.health()` (deadman.py:80-90, not touched) already builds its `Request` inside its `try` and returns a class
  name. It has no leak of the F1 kind.

### Verdict

F1 is addressed. The fix diff introduces no breakage. The fix report shows the RED run, a mutation check, the covering
command (`safe python3 -m unittest discover -s tests -p test_supervise.py`: 93 tests OK, three times) and the whole suite
(779 tests OK). Task 13 fix round 1: APPROVED.
