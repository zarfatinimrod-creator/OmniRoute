### Task 7: The first look after any start

**Kind:** BUILD. **Spec:** 5.1, 5.6 ("alerts come after every stop was looked at"), 12 (the catch-up is unchanged).

**Files:** Modify `aitrader/news_live.py` (`_run`, `code_stamp`). Test: `tests/test_news_supervised.py` (class `FirstLook`).

**Interfaces:** Consumes `start_checks`, `adopt_previous`, `say_late`, `_beat`, `_look_at_stops`. Produces the order of `_run`, which Tasks 8 and 11 rely on:

1. load the config; `start_checks` (may return 5, 7, 6); build the trader;
2. `adopt_previous(read_heartbeat())` (the last stop look, the blind clocks, the mismatch flag, what is still unsent: nothing is sent here); `_beat("boot")`;
3. the chain check (`ChainBroken`: the existing alert, return 4);
4. when the market is open, `_look_at_stops(events, guarded=True)`, whose own lines go out as Task 6 says; `_beat("stops")`;
5. the lines that can wait, each a network send of up to 15 s: E2 (no lock), E1 (mismatch), `say_late()`;
6. `code_stamp()`, priming and the loop.

Nothing that reaches the network stands before step 4 except the look's own quotes: a start after a kill is exactly when E1 and a late line are due, and the first look must not wait for them. A first look that returned false, or raised anything but `ChainBroken`, leaves a `news_errors.jsonl` row with `where` "first_look" and the loop starts. `code_stamp` passes `env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}` to both git calls. Nothing inside `_step` changes.

- [ ] Write class `FirstLook(_Engine)`; `start(**kw)` is `news_live._run("23:59", 0.0005, False, **kw)` with `poll_headlines`, `time.sleep` and `load_config` replaced; every test begins with `hold(self.nt); self.nt.save()`. `calls` is filled by stand-ins: `live_price` appends "quote:<sym>", `code_stamp` "git", the poll "feed", `notify.send` "send":

```python
    def test_the_first_outside_call_of_a_start_is_the_held_names_quote(self):
        self.assertEqual(self.start(), 0)
        self.assertEqual(calls[0], "quote:BBB")
        self.assertLess(calls.index("quote:BBB"), min(calls.index("git"), calls.index("feed")))

    def test_the_lines_that_can_wait_go_out_after_the_first_look_and_before_git(self):
        journal.append("news_trades.jsonl", {"date": TODAY, "symbol": "GONE", "side": "SELL", "qty": 1, "price": 9.0, "reason": "x"})
        journal.append("news_trades.jsonl", {"date": TODAY, "symbol": "AAA", "side": "BUY", "qty": 5, "price": 100.0, "reason": "x"})
        journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "told_through": None})    # both rows are unsent; AAA is a mismatch
        self.assertEqual(self.start(locked=False), 0)                                                # and no lock: E2, E1 and one late line
        sends = [i for i, c in enumerate(calls) if c == "send"]
        self.assertEqual((calls[0], len(sends), sends[-1] < calls.index("git")), ("quote:BBB", 3, True))

    def test_after_a_restart_the_catch_up_reads_from_the_last_look_of_the_run_before(self):   # Review Focus 1
        now = datetime(2026, 11, 12, 10, 30, tzinfo=NY); self.cfg["news"]["stop_catchup"] = "alert"
        journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "stops_checked_at": (now - timedelta(minutes=10)).astimezone(timezone.utc).isoformat()})
        # _look_at_stops is wrapped to pass now=now; BBB's quote has no time of its own (not live); the bars_since stand-in
        self.assertEqual(self.start(), 0)                      # appends (since, read_heartbeat()["stops_checked_at"]) to `asked`
        self.assertEqual((asked[0][0].strftime("%H:%M"), asked[0][1] is not None), ("10:20", True))   # not 09:30, and no null stamp

    def test_a_name_under_its_stop_is_sold_saved_and_said_before_git(self):
        self.prices["BBB"] = 48.0     # the code_stamp stand-in notes (the last trade's side, BBB still in the saved book,
                                      # lines sent so far) in `at_git`, then raises
        with self.assertRaises(RuntimeError):
            self.start()
        self.assertEqual(at_git, [("SELL", False, 1)])

    def test_a_broken_chain_at_a_start_sells_nothing_and_returns_4(self):
        self.prices["BBB"] = 48.0
        with mock.patch.object(journal, "broken_chains", lambda names=None: ["news_trades.jsonl"]):
            self.assertEqual(self.start(), 4)
        self.assertEqual(journal.read("news_trades.jsonl"), [])
        self.assertEqual([p for p, _ in self.sent], ["urgent"])

    def test_a_first_look_that_fails_is_on_record_and_the_loop_still_starts(self):   # NewsTrader.check_stops raises; step counted
        self.assertEqual(self.start(), 0)
        self.assertIn("first_look", [e.get("where") for e in journal.read("news_errors.jsonl")])
        self.assertTrue(steps)

    def test_code_stamp_runs_git_with_optional_locks_off(self):                      # subprocess.run replaced; env values listed
        news_live.code_stamp()
        self.assertEqual(set(envs), {"0"})
```

- [ ] Run `-k FirstLook`. Expected: the first test fails with `calls[0] == "git"`.
- [ ] Reorder `_run` as above and add the `env` to `code_stamp`.
- [ ] Run `-k FirstLook`: 7 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/tests/test_news_supervised.py`; message `feat(ai-trader): a new engine process looks at the stops before git, priming and every line that can wait`.

