### Task 8b: A fraction at the low end sells (backlog item 62, the owner's decision of 2026-11-11)

**Kind:** BUILD. **Authority:** not the supervisor spec. This task has no section there. Its authority is the owner's
decision recorded in `ai-trader/state/backlog.md`, item 62, and the gate is `ai-trader/CLAUDE.md` rule 4 with the
owner's second ruling of 2026-11-11 (a change to the news engine's trading rules: quant-critic, unit suite, and a
forward measurement written down with the change; no time machine sweep).

**The decision, in the owner's terms:** the scorer is asked for a whole number from 1 to 10. When it answers with a
fraction (for example 1.6), the engine drops that answer today. For a buy that is the safe side. For the bad-news exit
it is not: 1.6 on a held name does not sell, and only the -3% stop protects. From now on: for the bad-news exit a
fraction is compared as it is - `news.sell_on_score_at_most` (2) or less sells (1.6 sells, 2.4 does not). Buys do not
change: only a whole number above `news.buy_min_score` (8) buys.

**Evidence before the change:** `state/news_scores.jsonl` on 2026-11-11 held 1,190 rows, every score a whole number,
0 fractions. No sale was missed so far. The change is for a case not yet seen live.

**Files:** Modify `aitrader/news_live.py` (`Scores`, `score_batch`, the place in `NewsTrader` that takes the scorer's
answer for a batch before `handle_scored` uses it; the module docstring line about the owner's rules and
`score_batch`'s docstring), `config.json` (one sentence in `news._note`; no new key, no changed number). Test: create
`tests/test_news_low_fraction.py`.

**Interfaces:** Consumes `helpers.no_phone` (Task 2), `test_news_guards._Engine`, `hold()` of
`tests/test_news_supervised.py` (Task 3). Produces:

```python
Scores.fractions: dict[str, dict]     # key -> {"raw": float, "why": str}: every row whose score was a finite number
                                      # that is not whole. Empty when there was none. A plain dict returned by a
                                      # test stand-in has no such attribute and is read as "none" (getattr).
```

- `score_batch` keeps its signature and what its dict holds: a fraction is still NOT a score there (the existing test
  `tests/test_news_measure.py`, the loop over `None, "high", "9", 8.6, 9.5, True, ...`, stays green unchanged). It now
  also notes each fraction in `Scores.fractions` and counts them in the call's facts as `fractions` (an int, written
  into the `state/news_scorer_calls.jsonl` row of that call; 0 is written too, so the count can be read forward).
  Text, null, bool, lists, objects, nan and inf are no fraction and stay skipped exactly as today.
- The engine, where it has the batch's answer and before the scores are handled: for each fraction whose headline's
  symbol is HELD in the news book and whose `raw` is at or below `self.n["sell_on_score_at_most"]`, the headline gets
  a score entry `{"score": max(1, math.floor(raw)), "why": <the row's why>, "raw_score": raw}` and from there on is
  handled by the existing code exactly as a whole low score is. Nothing else about that path changes: the sale still
  needs what the existing bad-news exit needs (the name held, a price, a live quote), it goes through the same sale
  code, the same journal rows and the same owner line. The `news_scores.jsonl` row of such a headline carries
  `raw_score` next to `score`, so the record shows what the scorer really said.
- Every other fraction is dropped exactly as today (no score for that headline, the seen log's "scorer_no_answer"):
  a fraction above the line; any fraction on a name that is not held; any fraction where a buy, a place in the opening
  queue or a second check would read it. A fraction never buys, never queues and never passes a second check. The
  second check's own test of its answer (`isinstance(again, int)`) is not touched.
- The comparison is on the fraction itself (`raw <= sell_on_score_at_most`), not on a rounded value, and the line is
  read from the config, never written as a number in the logic. `math.floor` is used only for the whole number that
  is stored.
- `config.json` `news._note` gets one sentence after "sell_on_score_at_most and max_hold_days are Claude's additions
  (set to 0 to disable).": `Owner's decision 2026-11-11: a scorer answer that is a fraction counts only for the
  bad-news exit of a held name, compared as it is (1.6 sells, 2.4 does not); it never buys.`

- [ ] Write `tests/test_news_low_fraction.py`. It begins with `from helpers import no_phone  # noqa: F401`. Class
  `LowFraction(_Engine)`. The scorer's reply is given through the REAL parser: `subprocess.run` inside `news_live` is
  replaced by a stand-in that returns the CLI envelope (`{"result": "<json array as text>", ...}`) for the rows the
  test wants, so that `score_batch` itself does the reading. `step_with(rows)` is: the poll returns one fresh headline
  per row, then `self.nt.step()`. BBB is held at 50.0 through `hold(self.nt)` where a test says "held"; its live
  price is 49.5 (above the 48.5 stop), so only the score can sell it.

```python
    def test_a_fraction_at_or_under_the_line_on_a_held_name_sells_and_the_record_keeps_what_was_said(self):
        self.step_with([{"symbol": "BBB", "score": 1.6}])
        t = journal.read("news_trades.jsonl")[-1]
        self.assertEqual((t["side"], t["symbol"], t["qty"]), ("SELL", "BBB", 10))
        row = journal.read("news_scores.jsonl")[-1]
        self.assertEqual((row["symbol"], row["score"], row["raw_score"]), ("BBB", 1, 1.6))
        self.assertNotIn("BBB", self.nt.book.positions)

    def test_the_line_is_compared_on_the_fraction_itself(self):                 # sell_on_score_at_most is 2
        for raw, sells in ((2.4, False), (2.0001, False), (1.9999, True), (0.4, True)):
            with self.subTest(raw=raw):
                self.fresh_engine_holding_bbb()
                self.step_with([{"symbol": "BBB", "score": raw}])
                self.assertEqual("BBB" not in self.nt.book.positions, sells)
        self.assertEqual(journal.read("news_scores.jsonl")[-1]["score"], 1)     # 0.4 is stored as 1, never 0

    def test_a_fraction_never_buys_never_queues_and_leaves_no_score(self):
        for session_open in (True, False):                                      # a buy in session, a queue place outside it
            with self.subTest(session_open=session_open):
                self.fresh_engine(session_open=session_open)
                self.step_with([{"symbol": "AAA", "score": 9.5}, {"symbol": "AAA", "score": 8.6}])
                self.assertEqual(journal.read("news_trades.jsonl"), [])
                self.assertEqual(journal.load_json("news_queue.json") or [], [])
                self.assertEqual(journal.read("news_scores.jsonl"), [])

    def test_a_high_fraction_on_a_held_name_changes_nothing(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 9.5}])
        self.assertEqual((journal.read("news_trades.jsonl"), "BBB" in self.nt.book.positions), ([], True))

    def test_a_low_fraction_on_a_name_that_is_not_held_is_dropped_as_today(self):
        self.step_with([{"symbol": "AAA", "score": 1.6}])
        self.assertEqual((journal.read("news_trades.jsonl"), journal.read("news_scores.jsonl")), ([], []))

    def test_the_sale_still_needs_a_live_quote(self):                           # the rule of the whole low score
        hold(self.nt)
        with mock.patch.object(news_live.NewsTrader, "_quote_is_live", lambda self, *a, **k: False):
            self.step_with([{"symbol": "BBB", "score": 1.6}])
        self.assertIn("BBB", self.nt.book.positions)

    def test_a_whole_low_score_and_everything_that_is_no_number_are_as_before(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 2}])
        row = journal.read("news_scores.jsonl")[-1]
        self.assertEqual((row["score"], "raw_score" in row, "BBB" in self.nt.book.positions), (2, False, False))
        for bad in (None, "1", "1.6", True, [1.6], {"v": 1}, float("nan"), float("inf")):
            with self.subTest(bad=bad):
                self.fresh_engine_holding_bbb()
                self.step_with([{"symbol": "BBB", "score": bad}])
                self.assertIn("BBB", self.nt.book.positions)

    def test_the_scorer_call_row_counts_the_fractions(self):
        hold(self.nt)
        self.step_with([{"symbol": "BBB", "score": 9.5}, {"symbol": "AAA", "score": 7}])
        self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 1)
        self.fresh_engine()
        self.step_with([{"symbol": "AAA", "score": 7}])
        self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 0)
```

  `float("nan")` and `float("inf")` cannot travel in strict JSON: for those two the stand-in writes `NaN` and
  `Infinity` into the array text, which Python's `json.loads` reads. `fresh_engine(...)` and
  `fresh_engine_holding_bbb()` give a new temporary state and a new trader the way `_Engine.setUp` does (reuse it;
  do not copy its body). Where a name of `_Engine` differs from what this brief assumes, baseline.md and the file
  itself are right and the test is written to them; the assertions stay.

- [ ] Run `python3 -m unittest discover -s tests -p 'test_news_low_fraction.py' -v`. Expected: the first test fails
  with BBB still in the book (`AssertionError` on the trade row: there is none).
- [ ] Implement as above. Trace every reader of a score entry (`grep -n '\["score"\]\|\.get("score"' aitrader/`) and
  show in the report that no reader can see a fraction: the only new entries are whole numbers at or below the line,
  for held names.
- [ ] Run the file again: 8 tests, `OK`. Then `tests/test_news_measure.py` and `tests/test_news_inputs.py` alone
  (both `OK`, unchanged), then the whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/config.json ai-trader/tests/test_news_low_fraction.py`;
  message `feat(ai-trader): a fractional news score at or under the sell line sells a held name (owner's decision, backlog 62)`.

**For the report and the gate (rule 4, forward measurement):** before = 1,190 score rows, 0 fractions
(`state/news_scores.jsonl`, 2026-11-11). After = read at every Saturday review: the rows of `state/news_scores.jsonl`
that carry `raw_score` (each is a sale this change made; a losing one goes through the loss protocol like any sale)
and the sum of `fractions` in `state/news_scorer_calls.jsonl` (how often the scorer answers with a fraction at all).
This is a trading-rule change of the news engine. It touches no file the time machine loads.
