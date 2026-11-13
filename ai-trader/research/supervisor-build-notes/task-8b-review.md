# Task 8b review: a fraction at the low end sells (backlog 62)

Reviewed: f81e1544..8a9d86d0 (one commit) in the gate clone, from the review package
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-8b.diff`. All three hunks were complete in the
package. The only code outside the diff I read was for the five risks listed below. Nothing in the clone was changed,
and no test was run: reading the code answered every doubt.

### Spec Compliance

Not compliant on one point.

- `ai-trader/aitrader/news_live.py:683` (and `:269`): the brief says the call's `fractions` count is "written into the
  `state/news_scorer_calls.jsonl` row of that call; 0 is written too". The implementation writes 0 only in `_scored`'s
  success path. Two kinds of row get no `fractions` key when the count is 0:
  - a manual `news-score` row (`aitrader/__main__.py:330` calls `nt.scorer_called({**sc.facts, "source": "news-score"})`);
  - the row of a call that raised (`news_live.py:679`).

  Not writing it inside `score_batch` was forced: `tests/test_news_measure.py:104` pins
  `sorted(facts) == ["answered", "model", "prompt", "sent", "wall_s"]`, and the brief requires that file to stay
  unchanged. The gap in those two rows was not forced. All three paths write through `NewsTrader.scorer_called`
  (`news_live.py:656-666`), and no test pins that row's keys. I checked `test_news_measure.py:217-253` and `:311-314`,
  and `test_news_inputs.py:944-958`: they use only `assertNotIn("source")` and `assertNotIn("answered")`. A default of
  0 in `scorer_called` would put the count in every row, inside the brief's files.

Checked and compliant:
- `Scores.fractions` exists and is shaped as the brief says (`:259`).
- `score_batch` keeps its signature and its dict. Text, null, bool, lists, objects, nan and ±inf skip as before
  (`:258` `math.isfinite`).
- In the engine, the held check reads `self.book.positions`. The comparison is `f["raw"] <= self.n["sell_on_score_at_most"]`:
  on the raw value, with the line read from config. The stored entry is `max(1, math.floor(raw))` with `raw_score` (`:686-690`).
- `news_scores.jsonl` carries `raw_score` only for such an entry (`:1272`).
- The sale branch is unchanged (`elif s["score"] <= sell_on_score_at_most and held and px and live`). The second check's
  re-score reads `score_batch`'s dict directly (`:328`), so it never sees a fraction.
- The `config.json` sentence is word for word and in the brief's place. No key or number changed.
- All 8 named tests exist under their names with the brief's assertions. The two additions (`hold(self.nt)` in test 1,
  `float("-inf")` in test 7) weaken nothing.
- The commit message is the brief's, with no trailer.

Cannot verify from this diff:
- That the owner line of a fraction-driven sale ends with "כסף נייר". The sale reuses unchanged `_sell`/`_log_trade`
  code; check it in the whole-branch review.
- The commit author is `Claude <<email>>`. That is the clone's configured identity and is on every commit
  of `supervisor-build`, not something this task chose. Whether the "no AI attribution" constraint covers the author
  field is a question for the whole-branch review.
- The "before" figure (1,190 rows, 0 fractions). It comes from the live state, which was not re-read.

### Strengths
- The tests drive the real `score_batch`. Only `news_live.subprocess.run` is replaced, and the stand-in refuses anything
  that is not a scorer call. The rest of the step is the real `step()` behind `_Engine`'s stubs, so the tests check the
  real parse-to-sale path and not a mock.
- The edges are pinned: 2.0001 against 1.9999, 0.4 stored as 1, nan, inf and -inf. The -inf case is a real crash path
  (`math.floor(-inf)` raises `OverflowError`). The implementer found it and pinned it.
- A mutation table backs the claims. Rounded or floored comparison, no held check, no `max(1, …)`, no `raw_score`, no
  count, and no `isfinite` are all killed.
- The change is small and in the right place. No new config key, no literal threshold, no change to the buy, queue or
  second-check code.
- The trace of every score reader in the report is accurate where I checked it: `:328`, the buy and queue branches
  (need `score > buy_min_score` and a name not held), and the sale branch.
- Named risk checked: the `market_open_now` override in `fresh_engine` (`tests/test_news_low_fraction.py:301`) is a bare
  module assignment. It does not leak, because `_Engine.setUp` saves the original in `_saved` and `_Engine.tearDown`
  restores it (`tests/test_news_guards.py:40-58`).
- Named risk checked: the held check is made on the main thread, right before `handle_scored` for the same chunk
  (`news_live.py:1557-1559`), not in a worker thread.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
1. **The forward measurement counts rows that are not sales.** Where: the brief (task-8b-brief.md:138-141), copied into
   task-8b-report.md:206-208; the behaviour is at news_live.py:686-690 and :1271-1276. This defect is mandated by the
   brief.
   - **What is wrong.** The rule-4 "after" figure is "the rows of `state/news_scores.jsonl` that carry `raw_score`
     (each is a sale this change made…)". But `_scored` creates the entry for every held name at or under the line,
     before the sale's own conditions are checked. `handle_scored` writes the score row (with `raw_score`) for every
     entry. The sale also needs a price, a live quote, and the name still held when the item's turn comes.
   - **Where a `raw_score` row has no sale:**
     - when the quote is not live. `test_the_sale_still_needs_a_live_quote` is exactly this case.
     - when the name was sold earlier in the same chunk, by a second low headline or by the stop look inside a buy's
       second check;
     - when `sell_on_score_at_most` is 0 and the fraction is 0 or less.
   - **Why it matters.** The Saturday review would count non-sales as sales. Rule 4's written measurement of this
     trading-rule change would be wrong from the first such row.
   - **Fix.** No code change. Define the "after" count as the SELL rows of `news_trades.jsonl` that match a `raw_score`
     row (same symbol, same step). Report the `raw_score` rows with no matching sale as their own figure ("the exit was
     due but the sale was blocked by the live-quote rule or the name was already gone").

#### Minor (Nice to Have)
1. `ai-trader/aitrader/news_live.py:688`: no test pins the guard `x["key"] not in scores` (a whole answer beats a
   fraction for the same id). The report says the mutant survives. One subTest would pin it: a duplicate id, answered
   once whole and once as a fraction.
2. `ai-trader/aitrader/news_live.py:686-689`: "held" is read once per chunk, before the chunk is handled; a whole low
   score is judged at its own turn. Two results follow. A name bought earlier in the same chunk is not sold by a later
   low fraction in that chunk. A name sold earlier in the chunk still gets a `raw_score` row. The brief mandates this
   ("before the scores are handled"), and it is rare.
3. `ai-trader/aitrader/news_live.py:1277-1283` and the sale branch: three places carry the floored score, and only
   `news_scores.jsonl` keeps what the scorer said:
   - the sale reason ("bad news score 1");
   - the owner line;
   - the two `news_predictions.jsonl` rows. They get prob 0.32 for an answer of 1.6, which should give 0.336.

   The brief mandates this ("exactly as a whole low score"). The forward grading of the scorer will see 1.
4. `ai-trader/aitrader/news_live.py:686-690`: with `sell_on_score_at_most = 0` (the documented off switch), a fraction
   of 0 or less on a held name now writes a score row and two prediction rows (no sale). Before, it left none. This
   matches what a whole negative answer already does, and it follows the brief's literal comparison. The implementer
   raised it as concern 1.
5. `ai-trader/aitrader/news_live.py:259` and `:263`: `_clean(str(row.get("why", "")), 120)` is now written twice in the
   same loop. Compute `why` once before the two branches.
6. `ai-trader/tests/test_news_low_fraction.py:301`: `fresh_engine` sets `news_live.market_open_now` by assignment. It is
   safe only because `_Engine` happens to save and restore that attribute. A `mock.patch` started with `addCleanup`
   would not depend on that.

### Assessment
Task quality: **Needs fixes.** The code is correct, small and well tested:
- a fraction can only create a whole entry at or under the configured line, for a held name;
- that entry then goes through the unchanged sale path;
- buys, queues and the second check cannot see a fraction.

Two things remain. First, the rule-4 forward measurement (mandated by the brief) counts every `raw_score` row as a sale,
which the brief's own test 6 shows is false. Second, the "0 is written too" count is missing from `news-score` rows and
from the row of a call that raised, though `scorer_called` could carry it for all three paths.
