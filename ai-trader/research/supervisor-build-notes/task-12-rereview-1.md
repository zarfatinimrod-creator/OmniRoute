# Task 12 re-review, fix round 1

Fix base c82097e1, head 5ab41f32 (one commit, `ai-trader/aitrader/supervise.py` +8/-4, `ai-trader/tests/test_supervise.py` +22).
Package: `review-task-12-fix1.diff`. Read-only on the clone. No test was re-run: the code answered every doubt.

### Finding Verdicts

- **F1: ADDRESSED.**
  - `ai-trader/aitrader/supervise.py:500-501` (`spawn`): `kid` now keeps `held_before=set(_held(before))`. `before` is the
    same heartbeat `last_look` is taken from, so the two describe the same earlier engine.
  - `ai-trader/aitrader/supervise.py:573-577` (`up`): `after` is built per name of the `up` beat as before. If any name of
    `held_before` is missing from that beat (`kid["held_before"].difference(looks)`), the beat's `at` is appended.
  - The reported case is gone. The previous beat holds BBB, the up beat holds nothing. `after` is now `[at]`, not `[]`, and
    `last` is BBB's old stamp, so `blind_s = open_seconds(last, at)`, no longer 0. This is the upper bound a blind name
    already gets.
  - The guard is unchanged. Nothing held before or now still gives 0 (spec 4.6). An unreadable `at` still puts None in
    `after` and gives 0.
  - `kid` is only filled in `spawn` (line 500), and `up` is only called for a spawned child (line 529-531). So
    `held_before` always exists when `up` reads it.
  - Test `Watching.test_blind_s_counts_a_name_held_before_the_start_that_the_first_look_sold`
    (`ai-trader/tests/test_supervise.py:1124`). The previous beat holds BBB, 40 s old. The dummy run holds nothing: its
    defaults are `held {}`, `open True`, phase "idle" (`tests/helpers/dummy_child.py:39-63`). `open_seconds` is patched.
  - The test wraps `first_look_done` and records the beat it first says yes to. Line 529 reaches that wrapper only with
    the market open and before `up`, so it is exactly the beat passed to `up`.
  - It asserts `up.held == {}`, `blind_s == 42.0`, `a == last` and `b == that beat's at`. This is the test the finding
    asked for.
  - Against the old code `after` is `[]`, `open_seconds` is never asked, and the unpack fails. That matches the RED output
    in the report.

### New Breakage in the Fix Diff

None.

- The fix changes one more case: AAA and BBB were held, the first look sold AAA, and BBB is still held with a fresh stamp.
  Now `b` is the beat's `at`, not BBB's stamp. The two are less than one beat apart, and `at` is the bound that cannot
  understate, so this is not a defect.

### Out-of-Scope Observations

These block nothing.

- The fix's comment says "sold by the first look", but a name can leave the held set another way. The old engine can sell
  it after its last beat and then die before the next one: a hang kill while the sale's notification send is in flight.
  - Then `blind_s` counts from the heartbeat's stale stamp to the new up beat, and `sold` misses the sale, because its
    `logged_at` is before `ref`.
  - The error is on the safe side (it overstates), and it is the same heartbeat-lag error `last_look` already has for a
    name that is still held.
- When a name was sold by the first look and the up beat's `at` cannot be read, `blind_s` now falls to 0. Before, it was
  computed from the remaining names' own stamps.
  - The engine always writes `at`. This matches the guard's existing handling of a blind name with an unreadable `at`.
- The Minor items of the first review were left alone, as the report says: the group SIGKILL within the grace, the `hang`
  row's `t`, the cold-start `blind_s`, the duplicated kill block, the closure size, marks during `stop()`, and the author
  identity.

### Verdict

F1 is ADDRESSED. The fix diff introduces no breakage.

- The fix report has test evidence: the new test's RED and GREEN runs with commands and output, the `Watching` class and
  `test_supervise.py` each run 3 times (21 and 73 tests OK), and the whole suite once (759 OK).
- Task 12 fix round 1 passes.
