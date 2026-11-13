### Task 13: The parent's lines to the owner

**Kind:** BUILD. **Spec:** 8 (R1-R7, R5a-R5d, R4, R4b; the cap; the retry), 4.3 (the loop never waits for the network), 6 ("Not verified": `urllib` through the proxy), 3 row 15, 11.1 (`http_stub.py`).

**Files:** Create `aitrader/deadman.py`, `tests/helpers/http_stub.py`. Modify `aitrader/supervise.py`. Test: `tests/test_supervise.py` (class `ParentLines`; the import test of `Foundations` also imports `aitrader.deadman`).

**Interfaces:** Consumes `ownerlines`, Tasks 11-12. Produces:

```python
# tests/helpers/http_stub.py - plays ntfy on 127.0.0.1
class NtfyStub:
    def __init__(self, answers: list[dict] | None = None, cancel_answers: list[dict] | None = None)   # then {"status": 200, "left": 249}
    url: str
    requests: list[dict]                       # {"method", "path", "json"}
    pending: dict[str, dict]                   # by sequence_id: a publish with a delay waits here
    delivered: list[dict]                      # a publish with no delay is delivered at once; entries: message, priority, sequence_id, at (the stub's clock)
    def advance(self, seconds: float) -> None  # the stub's own clock: what is past its delay moves to delivered
    def stop(self) -> None

# aitrader/deadman.py (standard library only; Task 21 adds the dead-man to it)
class Sender:                                  # one worker thread and a queue
    def __init__(self, base_url: str, topic: str | None, timeout: float, env: Mapping | None = None, sync: bool = False)
    def publish(self, payload: dict, tag: str) -> None    # the worker adds "topic"; one JSON POST to base_url
    def request(self, method: str, suffix: str, tag: str) -> None   # <base>/<topic><suffix>: Task 21's DELETE and GETs
    def results(self) -> list[dict]                       # drained by the loop: {"tag", "ok", "status" | "error" (a class name), "left", "retry_after", "lines" (a GET's JSON lines, in memory only)}
    def health(self) -> int | str                         # GET <base>/v1/health, no topic, nothing published: the status, or an exception's class name

# aitrader/supervise.py
def may_send(st: dict, line_id: str, now: datetime, cap: int) -> bool
def gap_line(prev: dict | None, up_at: datetime, cold: bool, cal: dict, sup: dict) -> tuple[str, dict] | None
```

- `Sender` builds its opener from `env` (default `os.environ`): `ssl.create_default_context(cafile=env.get("SSL_CERT_FILE") or env.get("REQUESTS_CA_BUNDLE"))` and a `ProxyHandler` from the proxy variables of `env`, honouring `NO_PROXY`. The parent's lines go out through it from Task 20 on, so it is specified here and not with the dead-man. That `urllib` reaches ntfy from the cloud session is not verified (spec 6): `python3 -m aitrader.supervise --net-check` prints what `Sender.health()` returns and exits 0 only on 200. Task 20 runs it before any prompt changes.
- Stub answers: `{"status": 200, "left": 181}` (header `RateLimit: "messages";r=181;t=3600`), `{"status": 429, "retry_after": 5}`, `{"status": 429, "retry_after": 7200}`, `{"status": 429}` (no ntfy header), `{"status": 500}`, `{"hang": true}`. It also answers `GET /v1/health` (200), `DELETE /<topic>/<seq>`, `GET /<topic>/<seq>/delete` and `GET /<topic>/json?poll=1&sched=1&since=...` (one JSON line per delivered and per pending message, each with `sequence_id`, `priority`, `time`; a pending one has `time` in the future: working rule H1).
- Every parent line has the title "AI Trader - מפקח" (the spec fixes only the dead-man's title) and the priority of `ownerlines`; `held` is `held_text(..., held_names_in_line)`; times are in `owner_tz`; every `render` call passes `max_line_bytes` and `free_text_max_chars`.
- The loop writes an `alert` row when an outcome arrives: `sent` true; `sent` false at a first failure, after which the line is tried again every `alert_retry_seconds` for `alert_retry_minutes` and a late success adds a row with the same `id` and `sent` true; `sent` "capped". `id` is `<kind>-<n>`, n counting the day's alerts. With no topic in `env` nothing is requested and the row says false.
- When a line goes out: R1 when a restart episode ends (the child has been healthy for `healthy_seconds`), once however many falls: `time` and `cause` from the first fall (a code: "crash"; a signal: "killed"; 0 or 143: "stopped"), `down_s` from the first fall to the last `up`, `blind_s` summed, `falls` from the second fall on, `sold` from the `up` rows and `code` from the episode's `code` rows (when one has `code_changed`), `n` = `restarts_today`. R2 at a `hang` row (`render("R2", off=True)` when nothing was killed). R3, then R3b, then nothing, at the first, second and later trips of a day; R3c in place of R3 when every exit since the last healthy run was 7. R5a, R5b, R5d at a child's 4, 5, 6; R5c at `lock_held`. R6 at `stale_stops` start unless every stale name is in the beat's `blind` (then only the row); R6b at its end when R6 went out. R7 once per clock hour that had capped lines. R4 or R4b at the first `up` after `sup_start`, by `gap_line`.
- `gap_line`: `prev` is the last readable row before this `sup_start`. When [`prev.t`, `up_at`] has `outage_report_seconds` or more inside sessions (today's or earlier ones): R4 if `prev.ev` is not `sup_stop` (with `cold_time` = `prev.t` on the owner's clock when `cold`: the parent never runs git, and the last row it can read is what git restored), R4b if it is a `sup_stop` whose `why` is a key of `WORDS["R4b.why"]`. After `why` "halt", "lock_held", "end_of_day" or "closed_today" it is None: R5a-R5e said that the stops are not checked, and the minutes reach R11. The spec gives R4b three words for eight values of `why`; this is the mapping.
- `may_send`: R1, R2 and R6 are counted against `max_alerts_per_hour` (the count is in the state file). R1 and R2 over the count are held back ("capped"). R6 is counted and never held back, and no other line is: the spec lists R6 under the cap and also says that urgent lines are never capped; "stops not checked" must not wait for an hour to turn.
- On its way out the parent gives the worker `send_timeout_seconds` + 1 s. `left` from an answer goes into the next `mark`. The log gets a status code or an exception's class name, never a URL or a message.

- [ ] Write class `ParentLines(Parents)`; its config points `alerts.ntfy_base_url` at a `NtfyStub`, and `env` carries the topic "t0p1c-under-test". `ids()` lists the line ids of the `alert` rows with `sent` true, in order:

```python
    def test_one_r1_for_an_episode_of_three_falls(self):         # runs: crash, crash, crash, then beats for good
        r1 = [q["json"] for q in self.stub.requests if q["json"]["message"].startswith("מנוע החדשות נפל")]
        self.assertEqual((len(r1), "(3 נפילות ברצף)" in r1[0]["message"], r1[0]["title"], r1[0]["priority"]), (1, True, "AI Trader - מפקח", 4))

    def test_a_stub_that_never_answers_does_not_delay_a_restart(self):    # answers [{"hang": True}] * 9. The child is killed twice: the
        self.assertLess(max(first, second), 1.0)                          # second time healthy_seconds + 0.5 s after the first restart,
                                                                          # while R1 of the first still hangs in the worker
    def test_the_lines_of_a_halt_a_trip_and_a_held_lock(self):
        for script, state, want in (                                      # the dummy's script, the state file before -> ids(), halt code
                ([{"beats": 0, "then": "exit", "code": 4}], {}, (["R5a"], 4)), ([{"beats": 0, "then": "exit", "code": 5}], {}, (["R5b"], 5)),
                ([{"beats": 0, "then": "exit", "code": 6}], {}, (["R5d"], 6)), ([{"beats": 0, "then": "exit", "code": 7}], {}, (["R3c"], None)),
                ([{"beats": 0, "then": "exit", "code": 1}], {}, (["R3"], None)),
                ([{"beats": 0, "then": "exit", "code": 1}], {"trips_today": 1}, (["R3b"], None)),
                ([{"beats": 0, "then": "exit", "code": 1}], {"trips_today": 2}, ([], None))):
            self.fresh(state); self.run_parent(script)
            self.assertEqual((self.ids(), (self.state_file()["halt"] or {}).get("code")), want, script)
        self.fresh({})                                                    # a child that is refused the book for lock_wait_seconds
        self.assertEqual((self.run_parent([{"beats": 0, "then": "exit", "code": 3}], lock_wait_seconds=0.5), self.ids()), (3, ["R5c"]))

    def test_the_lines_of_a_hang_and_of_stale_stops(self):
        self.fresh({}); self.run_parent([{"beats": 5, "then": "hang"}], hang_seconds=2, hang_kill_enabled=False, stop_after=4)
        self.assertEqual((self.ids(), "לא נהרג, המתג כבוי" in self.urows("alert")[0]["text"]), (["R2"], True))
        stale = {"held": {"BBB": 48.5}, "beats": -1, "stop_age_s": [[300, 20], [0, 1]]}     # 20 beats with an old stamp, then fresh
        self.fresh({}); self.run_parent([stale], stops_stale_seconds=1, stop_after=5)
        self.assertEqual(self.ids(), ["R6", "R6b"])
        self.fresh({}); self.run_parent([{**stale, "blind": ["BBB"]}], stops_stale_seconds=1, stop_after=5)   # the engine's own alert owns it
        self.assertEqual((self.ids(), [r["what"] for r in self.urows("stale_stops")]), ([], ["start", "end"]))

    def test_the_cap_holds_back_r1_and_r2_never_r6_and_r7_counts_them(self):
        st, now = supervise.load_state(self.paths.state, "2026-11-12"), datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
        self.assertEqual([supervise.may_send(st, i, now, 6) for i in ("R1", "R2", "R6", "R1", "R1", "R1", "R1", "R6", "R3")], [True] * 6 + [False, True, True])
        # a parent whose clock starts at 10:59:57 New York with alerts {"hour": <that hour>, "sent": 6, "capped": 2} in its state file:
        self.assertEqual((self.ids(), "2 שורות נוספות" in self.urows("alert")[0]["text"]), (["R7"], True))

    def test_a_line_that_failed_is_tried_again_and_a_late_success_adds_a_sent_row(self):   # answers 500, then 200; alert_retry_seconds 0.2
        rows = self.urows("alert")
        self.assertEqual(([r["sent"] for r in rows], len({r["id"] for r in rows})), ([False, True], 1))

    def test_gap_line(self):
        cal, sup, at = supervise.load_cfg()["calendar"], supervise.load_cfg()["supervisor"], lambda s: datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc) + timedelta(seconds=s)
        row = lambda ev, **f: {"t": at(0).isoformat(), "ev": ev, **f}
        self.assertEqual(supervise.gap_line(row("mark"), at(200), False, cal, sup)[0], "R4")
        self.assertEqual(supervise.gap_line(row("mark"), at(200), True, cal, sup)[1]["cold_time"], "17:00")      # prev.t in Israel time
        self.assertIsNone(supervise.gap_line(row("mark"), at(179), False, cal, sup))
        self.assertEqual(supervise.gap_line(row("sup_stop", why="handover"), at(200), False, cal, sup)[0], "R4b")
        self.assertIsNone(supervise.gap_line(row("sup_stop", why="halt"), at(200), False, cal, sup))

    def test_the_topic_reaches_no_file_and_no_output_and_net_check_says_the_status(self):   # Review Focus 5: answers 500, a hang, then the
        self.assertEqual([p for p in self.tmp.rglob("*") if p.is_file() and b"t0p1c-under-test" in p.read_bytes()], [])   # stub stopped (refused)
        self.assertNotIn("t0p1c-under-test", out + err)
        self.assertEqual((net_check_rc_with_the_stub_up, net_check_rc_with_the_stub_stopped), (0, 1))
```

- [ ] Run `-k ParentLines`. Expected: `ModuleNotFoundError: No module named 'helpers.http_stub'`.
- [ ] Write `http_stub.py` and `aitrader/deadman.py` (`Sender`); implement `may_send`, `gap_line`, `--net-check` and the sending points in the loop. `Parents` gains `fresh(state)` (a new state directory whose state file holds these keys for the test clock's day), `ids()`, and the `run_parent` keywords used above (config overrides; `stop_after` = seconds until the test sends the parent SIGTERM).
- [ ] Run `-k ParentLines`: 8 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/aitrader/deadman.py ai-trader/tests/helpers/http_stub.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): the parent tells the owner about every restart, hang, trip, halt and gap, one line per event`.

