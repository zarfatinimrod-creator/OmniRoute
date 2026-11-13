### Task 15: Handover by the clock

**Kind:** BUILD. **Spec:** 4.5, 2 (target 11), 3 row 5.

**Files:** Modify `aitrader/supervise.py`. Test: `tests/test_supervise.py` (class `Handover`).

**Interfaces:** Consumes `watch` (Task 11), `up` (Task 12), the state file's `handover`. Produces:

```python
def handover_due(started_ny: datetime, now_ny: datetime, times: list[str], min_leg_minutes: int, max_leg_minutes: int) -> bool
```

- True from the first tick at or after a listed time of the day that lies `min_leg_minutes` or more after the parent's start; true also once the parent has run `max_leg_minutes`.
- Only with `--handover`: `watch` answers "handover"; the core makes the planned stop; `main` writes `handover = {"at", "last_look"}` into the state file (`last_look` = the oldest `checked_at` of the last beat, or that beat's `at` when nothing was held), `sup_stop` "handover", and returns 76.
- The next parent's first `up` carries `handover_s`, the seconds from `last_look` to its own first look (beat to beat when nothing is held), and clears `handover`.

- [ ] Write class `Handover(Parents)`:

```python
    def test_handover_due(self):
        t, T = lambda hm: datetime(2026, 11, 12, *map(int, hm.split(":")), tzinfo=NY), ["09:18", "10:48", "12:28", "14:17"]
        self.assertEqual([supervise.handover_due(t(a), t(b), T, 20, 110) for a, b in
                          (("08:07", "09:17"), ("08:07", "09:18"), ("09:05", "09:18"), ("09:05", "10:48"), ("14:20", "16:09"), ("14:20", "16:10"))],
                         [False, True, False, True, False, True])      # 09:05 is under 20 minutes before 09:18; 14:20 + 110 min = 16:10

    def test_a_handover_ends_with_76_and_the_next_parent_measures_it(self):   # the clock is shifted so that a listed time comes 2 s
        self.assertEqual(rc, 76)                                              # after the start; min_leg_minutes 0
        self.assertEqual(([(r["rc"], r["why"]) for r in self.urows("exit")], self.urows("sup_stop")[-1]["why"]), ([(143, "planned")], "handover"))
        self.assertEqual(self.state_file()["handover"]["last_look"][:4], "2026")
        rc2 = self.run_parent(...)                                            # a second parent on the same state directory
        self.assertTrue(0 <= self.urows("up")[-1]["handover_s"] < 60)
        self.assertIsNone(self.state_file()["handover"])

    def test_without_the_flag_no_handover_happens(self):
        self.assertEqual([r["why"] for r in self.urows("sup_stop")], ["end_of_day"])
```

- [ ] Run `-k Handover`. Expected: `AttributeError: module 'aitrader.supervise' has no attribute 'handover_due'`.
- [ ] Implement as above.
- [ ] Run `-k Handover`: 3 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): the parent hands over by the clock before the 2-hour cap and the next one measures the gap`.

