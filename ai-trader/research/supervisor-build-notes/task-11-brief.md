### Task 11: The restart core and the parent's loop

**Kind:** BUILD. **Spec:** 4.2, 4.3 (code table, back-off, crash loop), 4.5 (end of day, a day with no session), 3 rows 1, 4, 6, 11.

**Files:** Modify `aitrader/supervise.py`. Test: `tests/test_supervise.py` (classes `RestartCore`, `ParentLoop`, and the base class `Parents`).

**Interfaces:** Consumes Task 10; the engine's exit codes (Tasks 5, 8). Produces:

```python
def restart_core(spawn, watch, stop, near_until, emit, pol, counts, *, mono=time.monotonic, sleep=time.sleep) -> tuple[int, str]
def near_until(now_ny: datetime, until: str, slack_s: float) -> bool   # now_ny >= today's `until` - slack_s. One-sided: any time after it is near
def main(argv=None, *, child_cmd=None, env=None, clock=None, sleep=None) -> int
```

`restart_core` has no network, no file and no wall clock in it. `spawn() -> child` (`.pid`, `.poll()`; a negative code is a signal, as `subprocess.Popen` gives it). `watch(child | None, ran_s) -> None | "hang" | "handover" | "signal" | "orphaned"`, asked every `pol["loop_seconds"]`, also during a back-off. `stop(child, how)` with `how` "planned" or "hang" returns when the child has ended. `near_until() -> bool`: `main` passes `lambda: near_until(<clock, New York>, until, end_of_day_slack_seconds)`. It is one-sided because the engine looks at the clock only at the top of a round: a last step with scorer calls can end minutes after `--until`, and that 0 is still the end of the day, not five instant restarts and a trip after the close. `emit(ev, **fields)` for the rows `start`, `exit`, `tripped`. `counts` = `{"restarts_today": int, "stamps": [...]}`, changed in place. It returns:

| The child, or `watch` | The core |
|-----------------------|----------|
| exit 0 and `near_until()` | `(0, "end_of_day")` |
| exit 4, 5, 6 | `(code, "halt")`, no restart |
| exit 3 | start again with the back-off, not counted, for `lock_wait_seconds` from the first refusal; then `(3, "lock_held")` |
| any other end: a code, a signal, a 0 far from `--until`, a 7 (`exit` row `why` "tree_busy"), a 143 nobody asked for | a crash: start again at once when it ran `healthy_seconds` or more, else after 1, 2, 4, 8, 16 ... s (to `backoff_max_seconds`; the doubling starts again after a healthy run) |
| a crash when one more restart would pass `max_restarts` in `restart_window_seconds`, or `max_restarts_day` | row `tripped`, `(75, "crash_loop")` |
| `watch` says "hang" | `stop(child, "hang")`, then a crash (`why` "hang") |
| `watch` says "handover", "signal", "orphaned" | `stop(child, "planned")` (`why` "planned"); `(76, "handover")` or `(143, <the word>)`; during a back-off: the same answer at once, no start |

A 143 the parent did not ask for is not in the spec's table; it is counted as a crash here, so the trip limit bounds it.

`main`: `python3 -u -m aitrader.supervise --until HH:MM [--handover] [--state-dir DIR] [--config FILE]`.
- The child is `child_cmd + ["--until", until, "--supervised", str(os.getpid())]`; default `child_cmd` = `[sys.executable, "-u", "-m", "aitrader", "news-live"]`. It is started from the main thread (the kernel ties `PR_SET_PDEATHSIG` to the thread that started the child), with `start_new_session=True`, `cwd` = the ai-trader directory, `env`, output appended to `.cache/news_live.log`.
- `clock() -> datetime` (aware, UTC; default now) answers the calendar questions only: the day, the session, `--until`, handover times, the minute of a mark, the `t` of a row. Ages never use it: a beat's age is `time.time()` minus the heartbeat file's mtime, and a stamp inside a beat is aged against that beat's own `at`. So a test or a drill can run the parent on a session morning on any day of the week, next to a child that stamps real time.
- A planned stop is SIGTERM to the child's pid alone, `planned_stop_grace_seconds`, then SIGKILL to its process group (logged). A hang stop is Task 12.
- The parent takes `state/news_supervisor.lock`; a second parent prints the holder's pid, writes nothing and returns 3. SIGTERM, SIGINT and SIGHUP make `watch` answer "signal"; a changed `os.getppid()` makes it answer "orphaned". Handlers are installed on the main thread only and put back on return.
- On a day with no session: `sup_start`, `sup_stop` "closed_today", return 0, no child. `sup_start` carries `until`, `handover`, `timeout_ms` (7,200,000 with `--handover`, else `long_timeout_ms`: the parent is not told the Bash timeout, this is the pair `--status` hands out), `prev_t`, `prev_ev`, `gap_s`, `cold` (no heartbeat file).
- `main` drops log rows older than `uptime_keep_days`, then writes `sup_start`; it writes `sup_stop` and the state file (`restarts_today`, `trips_today`, `halt` on 4, 5, 6).
- Its return codes: 0 (end_of_day, closed_today), 3, 4, 5, 6, 75, 76, 143; 2 for a bad argument or config.
- stdout: first `supervise: pid <pid>, until <HH:MM>, handover <on|off>`; last `supervise: <rc> <word>. Run python3 -m aitrader.supervise --status and do what action says.`, the word being end_of_day, closed_today, handover, tripped, halt, lock_held (followed by `pid <holder>`), signal or orphaned. Everything else goes to `.cache/supervise.log`.

- [ ] Write the tests. `RestartCore.core(children, near_until=False, counts=None, orders=None, **pol)` runs `restart_core` over fake children `[(ran_s, rc), ...]` on a fake clock, from fresh counts unless given; `orders` maps a fake time to what `watch` answers from then on; it keeps `self.backoffs`, `self.counts`, `self.clock`, `self.emitted(ev)`. `Parents(Procs)` adds a config copy (`loop_seconds` 0.05, `backoff_first_seconds` 0.05, `healthy_seconds` 1), `run_parent(script, *argv, clock=None) -> rc` (`supervise.main` in-process, the dummy child as `child_cmd`), `spawn_parent(script, *argv) -> Popen` (the same call inside a `python3 -c` wrapper process), `urows(ev=None)`, `state_file()`. Their default clock is the real one moved so that the test starts at 10:00 New York on Thursday 2026-11-12.

```python
class RestartCore(unittest.TestCase):
    def test_five_quick_crashes_back_off_1_2_4_8_16_and_the_sixth_trips(self):
        self.assertEqual(self.core([(0.1, 1)] * 6), (75, "crash_loop"))
        self.assertEqual((self.backoffs, self.counts["restarts_today"]), ([1, 2, 4, 8, 16], 5))

    def test_a_child_that_ran_60_s_is_restarted_at_once(self):
        self.assertEqual(self.core([(60, 1), (1, 0)], near_until=True), (0, "end_of_day"))
        self.assertEqual(self.backoffs, [0])

    def test_the_day_limit_trips_with_a_clear_window(self):
        self.assertEqual(self.core([(700, 1)], counts={"restarts_today": 20, "stamps": []}), (75, "crash_loop"))

    def test_the_code_table(self):
        for rc in (4, 5, 6):
            self.assertEqual(self.core([(5, rc)]), (rc, "halt"))
        self.assertEqual(self.core([(0.1, 3)] * 99), (3, "lock_held"))
        self.assertEqual((self.clock >= 150, self.counts["restarts_today"]), (True, 0))
        self.assertEqual(self.core([(0.1, 7), (1, 0)], near_until=True), (0, "end_of_day"))
        self.assertEqual(self.emitted("exit")[0]["why"], "tree_busy")
        self.assertEqual(self.core([(30, 143), (1, 0)], near_until=True), (0, "end_of_day"))    # an unasked 143: one restart
        self.assertEqual(self.counts["restarts_today"], 1)
        self.assertEqual(self.core([(0.1, 0)] * 6), (75, "crash_loop"))                         # a 0 far from --until is a crash

    def test_near_until_is_one_sided(self):
        at = lambda hm: datetime(2026, 11, 12, *map(int, hm.split(":")), tzinfo=NY)
        self.assertEqual([supervise.near_until(at(t), "16:05", 60) for t in ("16:02", "16:03", "16:04", "16:05", "16:10", "17:30")],
                         [False, False, True, True, True, True])

    def test_a_stop_order_during_a_back_off_ends_it_without_a_start(self):   # Review Focus 2: watch answers "signal" in the wait
        self.assertEqual(self.core([(0.1, 1)], backoff_first_seconds=30, orders={0.5: "signal"}), (143, "signal"))
        self.assertEqual(len(self.emitted("start")), 1)

class ParentLoop(Parents):
    def test_a_killed_child_beats_again_within_1_s(self):
        p = self.spawn_parent([{"beats": -1}]); first = self.wait_beat()
        t0 = time.time(); os.kill(first["pid"], signal.SIGKILL)
        self.wait_for(lambda: self.beat().get("pid") not in (None, first["pid"]))
        self.assertLess((self.state / "news_heartbeat.json").stat().st_mtime - t0, 1.0)

    def test_a_child_that_always_fails_ends_with_75_after_5_restarts(self):
        self.assertEqual(self.run_parent([{"beats": 0, "then": "exit", "code": 1}]), 75)
        self.assertEqual(len(self.urows("start")), 6)
        self.assertEqual([(r["restarts"], r["trips_today"]) for r in self.urows("tripped")], [(5, 1)])
        self.assertEqual([(r["why"], r["rc"]) for r in self.urows("sup_stop")], [("crash_loop", 75)])

    def test_a_day_with_no_session_starts_no_child(self):                    # 2026-11-14 is a Saturday
        self.assertEqual(self.run_parent([{"beats": -1}], clock=lambda: datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)), 0)
        self.assertEqual([(r["ev"], r.get("why")) for r in self.urows()], [("sup_start", None), ("sup_stop", "closed_today")])

    def test_a_second_parent_returns_3_names_the_holder_and_writes_nothing(self):   # uptime.jsonl bytes unchanged
        self.assertEqual((second.wait(timeout=5), f"pid {first.pid}" in second.stdout.read()), (3, True))

    def test_sigterm_stops_the_child_and_the_parent_ends_with_143(self):
        self.assertEqual(p.wait(timeout=5), 143)
        self.assertEqual(([(r["rc"], r["why"]) for r in self.urows("exit")], self.urows("sup_stop")[0]["why"]), ([(143, "planned")], "signal"))

    def test_a_second_sigterm_while_the_child_is_finishing_changes_nothing(self):   # Review Focus 2: the run has "ignore_term" true,
        self.assertEqual((p.wait(timeout=10), len(self.urows("sup_stop"))), (143, 1))   # planned_stop_grace_seconds 1

    def test_a_parent_that_loses_its_own_parent_stops_with_orphaned(self):   # started by a helper process that exits at once
        self.assertEqual(self.urows("sup_stop")[0]["why"], "orphaned")

    def test_kill_9_of_the_parent_leaves_no_child_and_both_locks_free(self):
        self.wait_for(lambda: self.dead(child_pid), timeout=1)               # then both lock files can be flocked

    def test_a_child_that_ends_with_0_at_until_or_minutes_after_it_is_the_end_of_the_day(self):   # --until 10:00 and --until 09:55,
        self.assertEqual((rc, self.urows("sup_stop")[0]["why"], len(self.urows("start"))), (0, "end_of_day", 1))   # the clock at 10:00

    def test_a_child_that_ends_with_0_two_minutes_before_until_is_restarted(self):   # --until 10:02; runs: exit 0, then beats;
        # spawn_parent, and SIGTERM once the second start is on record
        self.assertEqual(([r["rc"] for r in self.urows("exit")][:1], len(self.urows("start")) >= 2), ([0], True))
```

- [ ] Run `-k RestartCore` and `-k ParentLoop`. Expected: `AttributeError: module 'aitrader.supervise' has no attribute 'restart_core'`.
- [ ] Implement `restart_core` (about 60 lines) and `main` as above.
- [ ] Run both: 16 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): the supervisor parent starts the engine, restarts it by its exit code and gives up after a crash loop`.

