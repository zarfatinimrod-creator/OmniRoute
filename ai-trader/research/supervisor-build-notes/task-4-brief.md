### Task 4: A heartbeat after every network call

**Kind:** BUILD. **Spec:** 5.5, 12 (the catch-up is unchanged).

**Files:** Modify `aitrader/news_live.py` (module: `read_heartbeat`; `NewsTrader`: new `_beat` and `adopt_previous`, and the call sites in `check_stops`, `catch_up_stops`, `run_queue_at_open`, `_step`, `handle_scored`; `_run`). Test: `tests/test_news_supervised.py` (class `Heartbeat`).

**Interfaces:** Consumes Task 3's `locked`. Produces:

```python
def read_heartbeat() -> dict | None                         # state/news_heartbeat.json; None when absent or unreadable
NewsTrader._beat(self, phase: str) -> None                  # the only writer of the file; never raises (_note_error(e, "heartbeat"))
NewsTrader.adopt_previous(self, prev: dict | None) -> None  # the last stop look and the blind clocks here; Task 5 adds mismatch_told, Task 6 told_through
```

The file (the parent reads it in Tasks 11-14). Kept: `at`, `headlines_seen`, `positions`, `queue`, `stops_checked_at` (meaning unchanged), `buys_blocked`, `code`. New: `pid` (int), `step` (steps begun by this process), `phase`, `market_open` (bool), `held` (`{sym: {"stop": float, "checked_at": ISO or null}}`, `checked_at` from `self._covered`), `blind` (the keys of `self._blind`), `blind_since` (`{sym: ISO}`), `blind_told` (the names whose blind alert a channel took), `told_through` (null until Task 6), `mismatch_told` (null until Task 5), `lock`, `supervised` (false until Task 8).

Phases and where each is written: "boot" (`_run`, right after `adopt_previous`), "stops" (after each held name's quote in `check_stops` and after each `bars_since` call in `catch_up_stops`: three held names can cost 3 x 66 s of bar reads, more than `hang_seconds`), "queue" (after each queued name in `run_queue_at_open`), "poll" (after `poll_headlines`), "quotes" (after each new headline's quote), "score" (after each `score_batch` and after a second check the loop waited for), "idle" (the end of the step, where the file is written today), "stopping" (Task 8). Only the "idle" beat works out `headlines_seen`, `stops_checked_at` and `buys_blocked`, as today; every other beat repeats the last values.

`adopt_previous` runs before this process writes its first beat, and does two things:
- The last stop look. `self._prev_look` = `prev["stops_checked_at"]` as an aware UTC time when `prev` carries one, else `self._last_stop_check()` (the equity curve's last point, as today). Until this process has made its own first look, every beat writes that stamp as `stops_checked_at`. Without this the boot beat would write null over the stamp that `_look_at_stops` reads lazily today, and after every restart the catch-up would start from 09:30 with "no record of the last look".
- The blind clocks. When `prev["at"]` is of today's New York date, each `blind_since` entry of a name still held becomes `self._blind[sym] = [that time, sym in prev["blind_told"]]`: the alert is not sent again after a restart, and "the price is back" still follows a delivered one.

- [ ] Write class `Heartbeat(_Engine)`. Each test runs `self.nt.step()` with `poll_headlines` replaced, unless it says otherwise; `items(n)` gives n fresh AAA headlines:

```python
    def test_the_fields(self):                                              # BBB held at 50.0, no headline
        b = news_live.read_heartbeat()
        self.assertEqual((b["pid"], b["phase"], b["step"], b["market_open"], b["lock"], b["supervised"]), (os.getpid(), "idle", 1, True, True, False))
        self.assertEqual(b["held"]["BBB"]["stop"], 48.5)
        self.assertLessEqual({"at", "headlines_seen", "positions", "queue", "stops_checked_at", "buys_blocked", "code", "blind", "blind_since",
                              "blind_told", "told_through", "mismatch_told"}, set(b))

    def test_a_three_batch_step_beats_between_batches(self):                # batch_max 1, items(3); the score_batch stand-in
        self.assertEqual(seen, ["quotes", "score", "score"])               # appends read_heartbeat()["phase"] to `seen`

    def test_every_headline_quote_leaves_a_beat(self):                      # items(30); journal.save_json wrapped to list phases
        self.assertGreaterEqual(beats.count("quotes"), 30)

    def test_every_bar_read_of_the_catch_up_leaves_a_beat(self):            # AAA, BBB and SPY held; no step: the bars_since stand-in
        now = datetime(2026, 11, 10, 9, 45, tzinfo=NY)                      # appends the count of heartbeat writes so far to `seen`
        self.nt.catch_up_stops([], now, last=now - timedelta(minutes=10))
        self.assertEqual((len(seen), seen == sorted(set(seen))), (3, True))

    def test_blind_lists_a_held_name_with_no_live_quote(self):              # BBB held, nt._quote_is_live -> False
        b = news_live.read_heartbeat()
        self.assertEqual((b["blind"], list(b["blind_since"]), b["blind_told"]), (["BBB"], ["BBB"], []))

    def test_the_boot_beat_keeps_the_last_stop_look_of_the_run_before(self):   # Review Focus 1; no step; BBB held and saved
        T = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=400)
        journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "stops_checked_at": T.isoformat()})
        nt = news_live.NewsTrader(self.cfg)
        nt.adopt_previous(news_live.read_heartbeat()); nt._beat("boot")
        self.assertEqual((nt._prev_look, datetime.fromisoformat(news_live.read_heartbeat()["stops_checked_at"])), (T, T))

    def test_a_restart_keeps_todays_blind_clock_with_its_told_flag_and_drops_yesterdays(self):  # Review Focus 1; no step; BBB held and saved
        since = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat(timespec="seconds")
        for at, kept in ((journal.now_utc(), {"BBB": True}), ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), {})):
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous({"at": at, "blind_since": {"BBB": since, "GONE": since}, "blind_told": ["BBB"]})
            self.assertEqual({s: v[1] for s, v in getattr(nt, "_blind", {}).items()}, kept)
```

- [ ] Run `-p 'test_news_supervised.py' -k Heartbeat`. Expected: `AttributeError: module 'aitrader.news_live' has no attribute 'read_heartbeat'`.
- [ ] Implement `read_heartbeat`, `_beat` and `adopt_previous`; replace the heartbeat write at the end of `_step` with `self._beat("idle")`; add the other call sites; in `_run`, right after the trader is built: `prev = read_heartbeat()`, `nt.adopt_previous(prev)`, `nt._beat("boot")`.
- [ ] Run `-k Heartbeat`: 7 tests, `OK`. Whole suite: `OK` (the heartbeat and catch-up tests of `test_news_guards.py` still pass).
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/tests/test_news_supervised.py`; message `feat(ai-trader): the engine heartbeat is written after every network call and carries pid, phase and per-name stamps`.

