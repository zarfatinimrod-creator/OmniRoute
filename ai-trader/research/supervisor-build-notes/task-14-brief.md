### Task 14: `--status`, `--clear-halt`, `--relayed`

**Kind:** BUILD. **Spec:** 4.4, 8 (R5e).

**Files:** Modify `aitrader/supervise.py`. Test: `tests/test_supervise.py` (class `Status`).

**Interfaces:** Consumes Tasks 10-13. Produces:

```python
def status(paths: Paths, cfg: dict, now: datetime, *, watchdog: bool = False, environ: Mapping | None = None) -> dict
```

and the forms `--status [--watchdog]` (prints it as JSON, exit 0), `--clear-halt`, `--relayed ID...`.
- Keys, as the JSON of spec 4.4: `action`, `why`, `ny_time`, `session_day`, `parent` {`alive`, `pid`, `mark_age_s`}, `engine` {`hb_age_s`, `stop_age_s`, `held`, `commit`, `dirty`}, `today` {`restarts`, `trips`, `halt`}, `deadman_ok`, `ntfy_left` (both from the last `mark`), `unsent`, `launch` {`command`, `timeout_ms`}.
- `action` is the first row of the spec's table that applies, top to bottom: `closed_today`, `after_hours` (outside `launch_from_ny` to `launch_until_ny`), `none`, `replace_parent`, `halted`, `kill_stray`, `wait_for_watchdog`, `launch`. `wait_for_watchdog` applies only when the last row of the log is not a `sup_stop` whose `why` is "handover", "signal" or "orphaned": after a planned stop the spec's second table says "launch, at once", and on a day with two trips a handover must not leave the stops unchecked until the next watchdog slot.
- `status` reads only. A parent is alive when the pid in its lock file exists and `/proc/<pid>/cmdline` names `aitrader.supervise`; an engine when it names `news-live`. No lock is probed. `kill_stray`: a live engine whose parent pid (`/proc/<pid>/stat`) is not a live parent; `why` carries the pid.
- `launch`: `{"command": "cd ai-trader && exec python3 -u -m aitrader.supervise --until <supervisor.until_ny> --handover", "timeout_ms": 7200000}` while `long_timeout_proven` is false or `environ["BASH_MAX_TIMEOUT_MS"]` is missing or under `long_timeout_ms`; else the command without `--handover` and `timeout_ms` = `long_timeout_ms`.
- `unsent`: today's `alert` ids whose latest row says `sent` false, that are past their retry time (the first row is older than `alert_retry_minutes`, or no parent is alive) and are not in `state/news_relayed.json`; each as `{"id", "kind", "text"}`. A row of kind R10 is listed at once: it is the watchdog turn's line, the parent never retries it (the quota it reports is the channel it would use). With `watchdog` and a halt from an earlier New York day it also holds `{"id": "R5e-<today>", "kind": "R5e", "text": <R5e>}` until that id is relayed. On the day of the halt itself nothing is added: the parent's R5a-R5d spoke that day.
- `--relayed ID...` is the only writer of `state/news_relayed.json` (`{"day", "ids"}`; a new day starts an empty list).
- `--clear-halt`: with a live parent it prints so and exits 3. Otherwise it runs `[sys.executable, "-m", "aitrader", "news-live", "--check"]` (`child_cmd + ["--check"]` in tests) and prints its output; on exit 0 it takes the parent lock, sets `halt` to null and exits 0; else the halt stays and it exits 1.

- [ ] Write class `Status(Parents)`; `self.action(**case)` writes the files a case needs and returns `supervise.status(...)["action"]`; the default `now` is 10:07 New York on 2026-11-12:

```python
    def test_the_first_row_that_applies_wins(self):
        self.assertEqual(self.action(now=datetime(2026, 11, 14, 15, 7, tzinfo=timezone.utc)), "closed_today")
        self.assertEqual((self.action(ny="07:59"), self.action(ny="16:00")), ("after_hours", "after_hours"))
        self.assertEqual((self.action(parent="alive", mark_age_s=180), self.action(parent="alive", mark_age_s=181)), ("none", "replace_parent"))
        self.assertEqual(self.action(halt={"code": 4, "why": "chain", "at": "2026-11-12T14:00:00+00:00"}), "halted")
        self.assertEqual(self.action(engine="alive_without_a_parent"), "kill_stray")
        self.assertEqual((self.action(trips=2), self.action(trips=2, watchdog=True), self.action()), ("wait_for_watchdog", "launch", "launch"))
        self.assertEqual([self.action(trips=2, last_stop=w) for w in ("handover", "signal", "orphaned", "crash_loop")], ["launch"] * 3 + ["wait_for_watchdog"])

    def test_a_lock_file_that_names_a_live_pid_that_is_no_parent_is_no_parent(self):   # Review Focus 1: the lock text holds os.getpid()
        self.assertEqual((self.status()["parent"]["alive"], self.status()["action"]), (False, "launch"))

    def test_the_launch_pair(self):
        two_hours = {"command": "cd ai-trader && exec python3 -u -m aitrader.supervise --until 16:05 --handover", "timeout_ms": 7200000}
        self.assertEqual(self.status()["launch"], two_hours)
        self.assertEqual(self.status(proven=True, environ={})["launch"], two_hours)
        self.assertEqual(self.status(proven=True, environ={"BASH_MAX_TIMEOUT_MS": "32400000"})["launch"],
                         {"command": "cd ai-trader && exec python3 -u -m aitrader.supervise --until 16:05", "timeout_ms": 32400000})

    def test_unsent_leaves_out_what_was_relayed_what_is_still_retried_and_adds_r5e_from_the_second_day(self):
        self.assertEqual([u["id"] for u in self.status()["unsent"]], ["R4-2", "R10-4"])    # a live parent; R4-1 relayed; R1-3 and R10-4 failed a minute ago
        self.assertEqual([u["kind"] for u in self.status(halt_day="2026-11-11", watchdog=True)["unsent"]][-1], "R5e")
        self.assertNotIn("R5e", [u["kind"] for u in self.status(halt_day="2026-11-12", watchdog=True)["unsent"]])

    def test_clear_halt_clears_only_when_the_check_passes_and_status_writes_nothing(self):
        self.assertEqual((self.clear_halt(check_rc=4), self.state_file()["halt"]["code"]), (1, 4))
        self.assertEqual((self.clear_halt(check_rc=0), self.state_file()["halt"]), (0, None))
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}; self.status()
        self.assertEqual({p.name: p.read_bytes() for p in self.state.iterdir()}, before)
```

- [ ] Run `-k Status`. Expected: `AttributeError: module 'aitrader.supervise' has no attribute 'status'`.
- [ ] Implement `status` and the three command forms.
- [ ] Run `-k Status`: 5 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): supervise --status decides what a woken session does; --clear-halt and --relayed`.

