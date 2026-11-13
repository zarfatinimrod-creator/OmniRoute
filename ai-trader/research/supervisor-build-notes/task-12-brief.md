### Task 12: What the parent sees: marks, `up`, a hang, stale stops

**Kind:** BUILD. **Spec:** 4.3 (hang, stale stops), 4.6 (rows `up`, `mark`, `hang`, `stale_stops`; `blind_s`), 3 rows 2, 3, 17.

**Files:** Modify `aitrader/supervise.py` (the `watch` that `main` gives the core). Test: `tests/test_supervise.py` (class `Watching`).

**Interfaces:** Consumes Task 4's heartbeat, Task 11's `watch` and `stop`. Produces:

```python
def open_seconds(a: datetime, b: datetime, cal: dict) -> float           # the part of [a, b] inside regular sessions
def beat_view(hb: dict | None, mtime: float | None, child_pid: int, now: float) -> dict   # now = time.time()
    # {"mine", "age_s", "stop_age_s" | None, "held": {sym: stop}, "open", "blind", "phase"}
def first_look_done(hb: dict | None, child_pid: int, started: float) -> bool               # started = time.time() at the start
def mark_due(last_mark: datetime | None, now: datetime) -> bool          # the first tick inside a new clock minute
```

- Hang: a running child whose beat is not `mine` or is older than `hang_seconds`; a new child has `start_grace_seconds` for its first beat. Switch on: row `hang` (`killed_with` "TERM" or "KILL"), SIGTERM to the child's group, `hang_term_grace_seconds`, SIGKILL to the group, then the core's crash path (counted). Switch off: one row `hang` with `killed_with` "none" per hang, and nothing is signalled.
- Stale stops: the market open, a name held, the beat fresh, `stop_age_s` above `stops_stale_seconds`: row `stale_stops` `what` "start" once per episode and "end" when it is fresh again. Nothing is killed.
- `mark`: fields of spec 4.6; `dm` and `left` are null until Tasks 13 and 21.
- `up`: when the beat says the market is closed, at this child's first beat; when it is open, at its first beat for which `first_look_done`. `first_look_done`: the beat is this child's, its phase is not "boot", and every held name either has a `checked_at` at or after `started` or is in the beat's `blind` list. A held name with no live quote (a halted stock, a stale Yahoo quote) keeps its old `checked_at` for hours; without the second half no `up` would be written, the whole stretch would count as a restart outage and the close slot would send a false R4c. The blind time itself belongs to `stale_stops` and to the engine's own blind-quote alert.
- `up` fields: `child`; `down_from` (the `t` of the last `exit` row, null at a parent's first start), `down_s`, `blind_s` = `open_seconds(the last look before the end, the first look after)` when a name was held, else 0 (for a name in `blind`, "the first look after" is this beat's `at`); `handover_s` (null until Task 15); `held`; `blind` (the beat's list); `commit`, `dirty` and `code_changed`, all three null; `sold` = the SELL rows of `news_trades.jsonl` (read as plain JSON lines) whose `logged_at` is at or after the real time (`time.time()`, kept in memory) at which the previous child ended, or at which this parent started. Row times come from the injected clock and `logged_at` from the real one: they are never compared.
- `code`: the engine stamps its code only after the first look (Task 7), so the first-look beat has none. At the first beat of a child that carries `code.commit`, the parent writes one row `code` = {`child`, `commit`, `dirty`, `code_changed`} (`code_changed` against the state file's `last_commit`, which is updated then; false while there is no `last_commit`). R1 (sent `healthy_seconds` later), `uptime-report` and the first-day check read the commit from this row.

- [ ] Write class `Watching(Parents)`:

```python
    def test_open_seconds_is_cut_to_the_session(self):          # Review Focus 3: 2026-11-27 closes at 13:00 New York, 18:00 UTC
        cal, utc = supervise.load_cfg()["calendar"], lambda h, m: datetime(2026, 11, 27, h, m, tzinfo=timezone.utc)
        self.assertEqual(supervise.open_seconds(utc(17, 50), utc(18, 30), cal), 600)
        self.assertEqual(supervise.open_seconds(utc(14, 0), utc(14, 40), cal), 600)      # the open is 14:30 UTC

    def test_a_frozen_child_is_killed_and_replaced(self):        # hang_seconds 2, the switch on; the run: 5 beats, then "hang"
        self.assertEqual(([r["killed_with"] for r in self.urows("hang")], len(self.urows("start"))), (["TERM"], 2))

    def test_with_the_switch_off_a_hang_is_logged_once_and_nothing_is_signalled(self):
        self.assertEqual(([r["killed_with"] for r in self.urows("hang")], len(self.urows("start"))), (["none"], 1))

    def test_a_new_child_has_the_start_grace_for_its_first_beat(self):    # hang_seconds 1, start_grace_seconds 5, "first_after_s" 3
        self.assertEqual(self.urows("hang"), [])

    def test_a_beat_left_by_another_pid_is_no_beat(self):        # Review Focus 1: a fresh heartbeat file with pid 1, a child that never beats
        self.assertEqual(len(self.urows("hang")), 1)

    def test_stale_stops_start_once_and_end_once(self):          # BBB held; "stop_age_s" [[300, 20], [0, 1]]; stops_stale_seconds 1
        self.assertEqual([r["what"] for r in self.urows("stale_stops")], ["start", "end"])

    def test_up_says_what_the_restart_cost(self):                # BBB held at a stop of 48.5; the child is killed once
        up = self.urows("up")[-1]
        self.assertEqual((up["held"], up["blind"], up["commit"], up["handover_s"], up["sold"]), ({"BBB": 48.5}, [], None, None, []))
        self.assertGreater(up["down_s"], 0)

    def test_up_is_written_while_a_held_name_is_blind(self):     # Review Focus 1: the run has BBB held, "blind": ["BBB"], "stop_age_s" 3000
        self.assertEqual([(r["held"], r["blind"]) for r in self.urows("up")], [({"BBB": 48.5}, ["BBB"])])

    def test_the_real_engine_gets_a_code_row_after_its_up_row(self):   # engine_child.py as child_cmd, session "open", BBB held
        self.assertEqual([(r["ev"], r.get("commit")) for r in self.urows() if r["ev"] in ("up", "code")], [("up", None), ("code", "abc1234")])

    def test_code_changed_compares_with_the_child_before(self):        # dummy runs with "commit" aaa1111, aaa1111, bbb2222; killed twice
        self.assertEqual([r["code_changed"] for r in self.urows("code")], [False, False, True])

    def test_a_mark_is_due_once_per_clock_minute(self):
        t = lambda s: datetime(2026, 11, 12, 15, 0, s, tzinfo=timezone.utc)
        self.assertEqual([supervise.mark_due(None, t(5)), supervise.mark_due(t(5), t(59)), supervise.mark_due(t(5), t(59) + timedelta(seconds=1))], [True, False, True])
```

- [ ] Run `-k Watching`. Expected: `AttributeError: module 'aitrader.supervise' has no attribute 'open_seconds'`.
- [ ] Implement as above.
- [ ] Run `-k Watching`: 11 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): the parent logs a mark a minute, measures every restart, kills a hung engine and notes stale stops`.

