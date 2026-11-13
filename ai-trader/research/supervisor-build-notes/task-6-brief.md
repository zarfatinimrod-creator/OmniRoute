### Task 6: A sale is said at once

**Kind:** BUILD. **Spec:** 5.6.

**Files:** Modify `aitrader/news_live.py` (`NewsTrader._log_trade`, `_look_at_stops`, `step`, `adopt_previous`, `_beat`; new `_mark_told`, `say_late`; `_run`). Test: `tests/test_news_supervised.py` (class `SaidAtOnce`), `tests/test_supervise.py` (class `SaidBeforeTheKill`).

**Interfaces:** Consumes `_beat`, `adopt_previous`, `read_heartbeat`. Produces:

```python
NewsTrader.told_through: str | None                       # every news_trades.jsonl row up to this hash had its line taken by a channel; in the heartbeat
NewsTrader._unsent: list[str]                             # hashes of the rows whose line no channel has taken yet, oldest first
NewsTrader._mark_told(self, hashes: list[str]) -> None    # after a delivered send that covered these rows: drop them from _unsent; only when
                                                          # _unsent is then empty, told_through = the last row's hash; a beat with the current phase
NewsTrader.say_late(self) -> None
```

- `_log_trade` notes the hash of each row it appends (the last row of the file, read back), so a look and a step know which rows are theirs.
- `_look_at_stops` sends the lines its own look added, right after the look and its save, the way the closing message is sent today (`notify.send("AI Trader - חדשות", <lines + the book line>, cfg, "high")`). A channel took it: `_mark_told(<the rows of this look>)`, and `step()`'s closing message leaves those lines out. No channel took it: the rows join `_unsent` and the lines stay for the step's closing message.
- `step()`'s closing message carries every line of the step that no channel has taken yet. A channel took it: `_mark_told(<the rows of this step>)`.
- `adopt_previous`: `told_through` = `prev["told_through"]` when `prev` has the key, else the hash of the last row on disk (no heartbeat, or one written before this task: nothing is re-sent). With a `prev`, today's rows (their `date` is today's New York date) after the row whose hash is `told_through` (all of today's rows when it is null; none when the hash is not in the file) are kept as `self._late`, and their hashes are the first entries of `_unsent`. A trader on which `adopt_previous` was never called has `told_through` None and nothing unsent or late.
- `say_late()`, called in `_run` after `adopt_previous` (Task 7 fixes its place: after the first stop look): when `self._late` is not empty, one message with the body `"דווח באיחור: " + " | ".join(<side qty symbol @ price - reason>) + ". כסף נייר"`, title and priority as above. A channel took it: `_mark_told(<their hashes>)`. It says only rows that were on disk when the process started, so a sale of the first look is not said twice.
- `told_through` therefore never passes a row whose line nobody got. The spec's wording ("after a delivered send the heartbeat holds the hash of the last row") would pass it as soon as any later message went out, and the sale would never be said. A line that neither the look's send nor the closing send delivered is said at the next start of that day.

- [ ] Write the tests:

```python
class SaidAtOnce(_Engine):
    def test_a_sale_at_the_top_of_a_step_is_sent_before_the_scorer_and_only_once(self):
        hold(self.nt); self.prices["BBB"] = 48.0     # one AAA headline in the poll; the score_batch stand-in copies
        self.nt.step()                               # the bodies sent so far into `at_scorer`
        self.assertTrue(any("SELL 10 BBB" in b for b in at_scorer[0]))
        self.assertEqual(sum("SELL 10 BBB" in b for _, b in self.sent), 1)
        self.assertEqual(news_live.read_heartbeat()["told_through"], journal.read("news_trades.jsonl")[-1]["hash"])

    def test_a_look_whose_send_failed_is_in_the_closing_message_and_told_only_then(self):
        hold(self.nt); self.prices["BBB"] = 48.0     # no headline. The notify.send stand-in: the first call returns [], later
        self.nt.step()                               # calls ["ntfy"]; each call appends (body, self.nt.told_through) to `calls`
        self.assertEqual([("SELL 10 BBB" in b, t) for b, t in calls], [(True, None), (True, None)])
        self.assertEqual(self.nt.told_through, journal.read("news_trades.jsonl")[-1]["hash"])

    def test_a_sale_nobody_got_is_not_passed_by_a_later_message_and_is_said_once_at_the_next_start(self):
        hold(self.nt); self.prices["BBB"] = 48.0
        ok, news_live.notify.send = news_live.notify.send, lambda *a, **k: []
        self.nt.step()                               # the look's send and the closing send both fail
        news_live.notify.send = ok
        self.nt._mark_told([]); self.nt._beat("idle")          # as after some later message that a channel took
        self.assertIsNone(news_live.read_heartbeat()["told_through"])
        for _ in range(2):
            nt = news_live.NewsTrader(self.cfg)
            nt.adopt_previous(news_live.read_heartbeat()); nt.say_late(); nt._beat("boot")
        late = [b for _, b in self.sent if b.startswith("דווח באיחור:")]
        self.assertEqual((len(late), "SELL 10 BBB" in late[0]), (1, True))

    def test_with_no_heartbeat_nothing_is_said_late(self):          # one SELL row of today on disk, no heartbeat file
        nt = news_live.NewsTrader(self.cfg)
        nt.adopt_previous(None); nt.say_late()
        self.assertEqual(self.sent, [])

class SaidBeforeTheKill(Procs):
    def test_the_line_of_a_sale_is_out_before_a_scorer_that_never_returns_and_a_kill_9(self):
        self.write_book({"BBB": 50.0})
        p = self.start_engine({"session": "open", "prices": {"BBB": [48.0]}, "score_delay_s": "never",
                               "polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]]}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "quotes")
        p.kill()
        self.assertEqual(sum("SELL 10 BBB" in r["body"] for r in self.sent_rows()), 1)
```

- [ ] Run `-k SaidAtOnce` and `-k SaidBeforeTheKill`. Expected: the first test fails on `at_scorer[0]` (nothing was sent before the scorer).
- [ ] Implement as above.
- [ ] Run both: 5 tests, `OK`. Whole suite: `OK` (`SaidWhateverHappens` in `test_news_guards.py` still passes: a sale at the top of a failing step is still said).
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/tests/test_news_supervised.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): a stop look's lines go out right after the look, and an unsent trade is reported at the next start`.

