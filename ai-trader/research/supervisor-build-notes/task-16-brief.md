### Task 16: `uptime-report`

**Kind:** BUILD. **Spec:** 4.6 (the uptime number), 11.2 (the report), 8 (R4c, R9, R11), 4.5 (the close slot).

**Files:** Create `aitrader/uptime.py`, `tests/test_uptime.py`. Modify `aitrader/__main__.py` (command `uptime-report`, stock-only, and the docstring).

**Interfaces:** Consumes the rows of `state/uptime.jsonl`, `supervise.read_rows`, `supervise.session_hours`, `ownerlines`. Produces:

```python
def day_report(rows: list[dict], day: date, cfg: dict, health: list[dict] | None = None) -> dict
def close_lines(report: dict, rows: list[dict], cfg: dict) -> list[dict]     # [{"id": "R4c" | "R9" | "R11", "priority", "text"}]
def render(reports: list[dict], cfg: dict) -> str
```

- `python3 -m aitrader uptime-report [--day [YYYY-MM-DD] [--notify]] [--days N]`: read-only; default `--days supervisor.report_days`. With `--day` it prints that day's block. Only with `--notify` does it add one JSON line `{"notify": [...]}` from `close_lines`: the close slot is the one caller that pushes those lines, and every later reading of a day (Tasks 22, 28) must not print them for someone to push twice.
- `day_report` keys: `day`, `session_s` (23400; 12600 on an early close; 0 on a day with no session), `unprotected_s`, `uptime` (1 - unprotected / session, rounded to 4 places; null with no session), `missing_marks`, `by_cause` {`restart`, `hang`, `handover`, `gap`, `stale_stops`}, `exposed_s`, `restarts`, `trips`, `handovers` (the `handover_s` values), `longest_blind_s`, `deadman` {`alarms` (the day's `new_seq` rows: each is an alarm that went out), `ping_failed`, `cancel_failed`}, `ntfy_failed`, `left_min`, `commits` (from the `code` rows), `open_at_close`, `stop_gap_max_s` (the day's largest in `news_health.jsonl`; null without the file).
- Unprotected time is the union, cut to the session, of: an `exit` to the next `up`; two marks more than `mark_gap_max_seconds` apart; the stretch between two marks when the later one shows `hb` above `up_hb_max_seconds`; and, while `n` is above 0, stretches with `stop` above `stops_stale_seconds`. The session's time before the day's first row and after its last counts as unprotected. A second that fits two causes is counted once, under the first of: restart, hang, handover, gap, stale stops.
- `close_lines`: R4c when the day's last outage was still open at the close; R9 when a `deadman` row `cancel_failed` carries `dm3` false (Task 21); R11 when the day had a trip, or more unprotected minutes than the day's R4, R4b and R4c `alert` rows reported.
- The slot and watcher columns of the two-week page are added in Tasks 23 and 25.

- [ ] Write `tests/test_uptime.py`; `marks(day, first, last)` gives one `mark` a minute with `hb` 5, and inside an outage `hb` = seconds since the `exit`:

```python
class Report(unittest.TestCase):
    def test_one_known_gap_gives_exactly_99_percent(self):
        rows = marks("2026-11-12", "14:30:00", "21:00:00", outage=("16:00:00", "16:03:54"))
        rows += [row("2026-11-12T16:00:00+00:00", "exit", rc=1, why="exit"), row("2026-11-12T16:03:54+00:00", "up", down_s=234, blind_s=0, handover_s=None)]
        r = uptime.day_report(sorted(rows, key=lambda x: x["t"]), date(2026, 11, 12), CFG)
        self.assertEqual((r["session_s"], r["unprotected_s"], r["uptime"], r["missing_marks"], r["by_cause"]["restart"]), (23400, 234, 0.99, 0, 234))
        self.assertIn("99.00%", uptime.render([r], CFG))

    def test_five_minutes_without_marks_are_a_gap_of_300_s_and_4_missing_marks(self):     # no marks from 15:01 to 15:04
        self.assertEqual((r["unprotected_s"], r["missing_marks"], r["by_cause"]["gap"]), (300, 4, 300))

    def test_an_early_close_day_has_12600_session_seconds(self):                          # Review Focus 3: 2026-11-27, a full day of marks
        self.assertEqual((r["session_s"], r["unprotected_s"], r["uptime"]), (12600, 0, 1.0))

    def test_close_lines_and_only_the_notify_form_prints_them(self):   # an exit at 20:50 UTC with no up; a tripped row; no alert rows
        self.assertEqual([l["id"] for l in uptime.close_lines(r, rows, CFG)], ["R4c", "R11"])
        self.assertTrue(all(l["text"].endswith("כסף נייר") for l in uptime.close_lines(r, rows, CFG)))
        self.assertEqual(("\"notify\"" in out_of("--day", "2026-11-12"), "\"notify\"" in out_of("--day", "2026-11-12", "--notify")), (False, True))

    def test_an_empty_log_is_a_day_with_no_protected_second(self):
        self.assertEqual(uptime.day_report([], date(2026, 11, 12), CFG)["uptime"], 0.0)
```

- [ ] Run `-p 'test_uptime.py'`. Expected: `ModuleNotFoundError: No module named 'aitrader.uptime'`.
- [ ] Write `aitrader/uptime.py` and the command.
- [ ] Run the file: 5 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/uptime.py ai-trader/aitrader/__main__.py ai-trader/tests/test_uptime.py`; message `feat(ai-trader): uptime-report turns the uptime log into the day's percent with its causes`.

