### Task 10: The parent's foundations: config, calendar, log, state file, lock, the dummy child

**Kind:** BUILD. **Spec:** 4.1, 4.3 (state file), 4.5 (calendar), 4.6 (log format), 10, 11.1 (`dummy_child.py`).

**Files:** Create `aitrader/supervise.py`, `tests/helpers/dummy_child.py`. Modify `config.json` (new block `supervisor`; `alerts.ntfy_base_url`), `aitrader/notify.py` (`send`: the address comes from the config), `.gitignore` (`state/news_supervisor.lock`, `state/news_supervisor.json`, `state/news_deadman.json`, `state/news_relayed.json`). Test: `tests/test_supervise.py` (class `Foundations`).

**Interfaces:** Consumes nothing from the engine but its file formats. Produces:

```python
def load_cfg(path: Path | None = None) -> dict                      # the whole config.json (default: beside the package)
def session_hours(day: date, cal: dict) -> tuple[tuple[int, int], tuple[int, int]] | None   # the contract of journal.session_hours
class Paths:   # Paths(state_dir, cache_dir): .lock .state .deadman .relayed .uptime .heartbeat .engine_lock .trades .sup_log .engine_log
def append_row(path: Path, pid: int, ev: str, now: datetime, **fields) -> dict   # adds t (UTC, whole seconds), ev, sup
def read_rows(path: Path) -> list[dict]                             # a line that does not parse is skipped
def prune_rows(path: Path, keep_days: int, now: datetime) -> None   # at sup_start; tmp file + replace
def load_state(path: Path, ny_day: str) -> dict                     # never raises
def save_state(path: Path, st: dict) -> None                        # tmp file + replace
def take_lock(path: Path, now: datetime) -> IO | None               # None: held. The holder's JSON is {pid, started_at}, as the engine's
```

- `append_row` starts with a newline when the file does not end with one. The rows and their fields are the table of spec 4.6, with two changes that Task 12 explains: `up` also has `blind` (a list) and its `commit`, `dirty` and `code_changed` are null; a row the spec does not have, `code` = {`child`, `commit`, `dirty`, `code_changed`}, carries them.
- State file: `{"day", "restarts_today", "trips_today", "halt": null | {"code", "why", "at"}, "alerts": {"hour", "sent", "capped"}, "reported_through", "last_commit", "handover": null | {"at", "last_look"}}`. A file of another New York day: the counts and `alerts` start again and `handover` is cleared (a handover nobody answered must not give the next morning's `up` an 18-hour `handover_s`); `halt`, `reported_through` and `last_commit` stay. A file that does not parse: a new day's state.
- `--state-dir DIR` (Task 11) puts the state files in DIR and the logs in `DIR/.cache/`; the default is `ai-trader/state` and `ai-trader/.cache`.
- `config.json`: the `supervisor` block, begun in Task 3, now with every key of spec 10 at its default, plus `until_ny` ("16:05": the `--until` of the launch command, Task 14) and `free_text_max_chars` (200, Tasks 2-3) (the test below; `slots` comes in Task 23, `watcher.drill_from` in Task 25) and a `_note` that names the spec and says that `planned_stop_grace_seconds` must be raised together with `news.guards` = "enforce" (spec 5.3); `alerts.ntfy_base_url` = "https://ntfy.sh". `notify.send` posts to `a.get("ntfy_base_url", "https://ntfy.sh") + "/"`.
- `tests/helpers/dummy_child.py --heartbeat FILE --script FILE --until HH:MM --supervised PID`. The script is a JSON list of runs; start n plays run n (the last repeats; the count of starts is in `<script>.n`). A run: `{"beats": N or -1, "every_s": 0.1, "first_after_s": 0, "then": "exit" | "hang" | "crash", "code": 0, "ignore_term": false, "held": {}, "stop_age_s": 0, "open": true, "blind": [], "commit": "abc1234"}`. `stop_age_s` is a number, or a list of `[age, beats]` pairs played in order, the last age repeating. It writes a heartbeat with Task 4's fields (phase "idle", `checked_at` = now - `stop_age_s`), honours `--supervised` as the engine does (Task 8), and ends with 143 on SIGTERM. "hang": no more beats, sleep; "crash": `os._exit(code or 1)`.

- [ ] Write class `Foundations(unittest.TestCase)`:

```python
SPEC = {"loop_seconds": 0.5, "healthy_seconds": 60, "backoff_first_seconds": 1, "backoff_max_seconds": 60, "max_restarts": 5,
        "restart_window_seconds": 600, "max_restarts_day": 20, "hang_seconds": 180, "start_grace_seconds": 60,
        "hang_term_grace_seconds": 5, "planned_stop_grace_seconds": 120, "lock_wait_seconds": 150,
        "stops_stale_seconds": 120, "up_hb_max_seconds": 60, "mark_gap_max_seconds": 150, "parent_stale_seconds": 180,
        "outage_report_seconds": 180, "end_of_day_slack_seconds": 60, "max_alerts_per_hour": 6, "alert_retry_seconds": 60,
        "alert_retry_minutes": 15, "send_timeout_seconds": 5, "held_names_in_line": 6, "max_line_bytes": 1200,
        "owner_tz": "Asia/Jerusalem", "launch_from_ny": "08:00", "launch_until_ny": "16:00",
        "handover_times_ny": ["09:18", "10:48", "12:28", "14:17"], "min_leg_minutes": 20, "max_leg_minutes": 110,
        "handover_target_seconds": 60, "long_timeout_ms": 32400000, "uptime_keep_days": 30,
        "receipts_keep_days": 30, "uptime_target": 0.99, "report_days": 14, "until_ny": "16:05", "free_text_max_chars": 200}
DEADMAN = {"ping_seconds": 180, "delay_seconds": 360, "handover_delay_seconds": 600, "fresh_seconds": 90,
           "retry_seconds": 30, "daily_limit_retry_after_seconds": 600, "reserve_messages": 15, "disarm_after_close_seconds": 60,
           "cancel_tries": 3, "cancel_retry_seconds": 20, "seq_margin_seconds": 20}
WATCHER = {"lookback_hours": 24, "ntfy_since": "35m", "stale_minutes": 90,
           "engine_window_ny": ["08:07", "16:01"], "quiet_hours": {"tz": "Asia/Jerusalem", "from": "23:00", "to": "08:00"},
           "max_cost_share": 0.2}
SWITCHES = [("hang_kill_enabled",), ("long_timeout_proven",), ("deadman", "enabled"), ("watcher", "fire_enabled"), ("watcher", "notify_enabled")]
SWITCHES_ON: list = []      # a rollout step that turns a switch on adds its path here, in the same commit as config.json

    def test_the_supervisor_block_carries_the_defaults_of_spec_section_10(self):       # every key but the five switches
        cfg = supervise.load_cfg(); sup = cfg["supervisor"]
        self.assertEqual(({k: sup[k] for k in SPEC}, {k: sup["deadman"][k] for k in DEADMAN}, {k: sup["watcher"][k] for k in WATCHER}),
                         (SPEC, DEADMAN, WATCHER))
        self.assertEqual(cfg["alerts"]["ntfy_base_url"], "https://ntfy.sh")

    def test_a_switch_is_on_only_when_its_rollout_step_said_so(self):
        sup = supervise.load_cfg()["supervisor"]
        for path in SWITCHES:
            self.assertIs(functools.reduce(lambda d, k: d[k], path, sup), path in SWITCHES_ON, path)

    def test_the_parents_calendar_equals_journal_session_hours_for_every_day_of_2026_and_2027(self):
        cal = supervise.load_cfg()["calendar"]
        for i in range(730):
            d = date(2026, 1, 1) + timedelta(days=i)
            self.assertEqual(supervise.session_hours(d, cal), journal.session_hours(d), d)

    def test_an_append_after_a_torn_line_starts_a_new_line_and_the_reader_skips_the_torn_one(self):   # the file ends with '{"t": "x'
        self.assertEqual([r["ev"] for r in supervise.read_rows(path)], ["mark"])

    def test_rows_older_than_the_keep_days_are_dropped(self):                     # rows 31 and 29 days old, keep 30
        self.assertEqual(len(supervise.read_rows(path)), 1)

    def test_a_state_file_of_another_day_keeps_the_halt_only_and_garbage_is_a_new_day(self):   # Review Focus 1 and 4
        st = supervise.load_state(path, "2026-11-12")            # the file: day 2026-11-11, restarts_today 7, trips_today 2, a halt with code 4, a handover
        self.assertEqual((st["day"], st["restarts_today"], st["trips_today"], st["halt"]["code"], st["handover"]), ("2026-11-12", 0, 0, 4, None))
        path.write_text("{not json")
        self.assertEqual((supervise.load_state(path, "2026-11-12")["restarts_today"], supervise.load_state(path, "2026-11-12")["halt"]), (0, None))

    def test_supervise_imports_no_pandas_no_requests_and_no_engine_module(self):
        code = ("import sys, aitrader.supervise; sys.exit(1 if [m for m in ('pandas', 'requests', 'aitrader.journal',"
                " 'aitrader.notify', 'aitrader.news_live') if m in sys.modules] else 0)")
        self.assertEqual(subprocess.run([sys.executable, "-c", code], env=no_phone.clean_env()).returncode, 0)

    def test_notify_posts_to_the_configured_address(self):                        # requests.post replaced; the topic set for this call only
        self.assertEqual(posted_urls, ["http://127.0.0.1:9/"])
```

- [ ] Run `-p 'test_supervise.py' -k Foundations`. Expected: `ModuleNotFoundError: No module named 'aitrader.supervise'`.
- [ ] Add the config block and the `.gitignore` lines; write `supervise.py` (the functions above) and `dummy_child.py`; change `notify.send`.
- [ ] Run `-k Foundations`: 8 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/aitrader/notify.py ai-trader/config.json ai-trader/.gitignore ai-trader/tests/helpers/dummy_child.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): supervisor config block, its own calendar, the uptime log and the state file`.

