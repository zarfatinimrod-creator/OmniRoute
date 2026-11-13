# Task 8b report - a fraction at the low end sells (backlog 62, owner's decision of 2026-11-11)

Status: DONE_WITH_CONCERNS. The concerns are small and listed at the end.
Gate clone: start `f81e15446593db92d6caf870ab1d17f66e339095` on `supervisor-build`, clean tree (checked first).
Commit: `8a9d86d0b156b580ea61fdd38f49e6728e6322b8` feat(ai-trader): a fractional news score at or under the sell line sells a held name (owner's decision, backlog 62)
(one commit; the self-review fixes were folded into it with `--amend`. It was made in this dispatch, so no earlier commit was rewritten.)

## What I built

`aitrader/news_live.py`
- `import math`.
- `Scores.fractions` (a new dict on every `Scores`): `{key: {"raw": float, "why": str}}` for every row whose score is a
  finite float that is not whole. The `why` is cleaned the same way as a score's `why` (`_clean(..., 120)`). `Scores`
  docstring updated.
- `score_batch`: before the existing whole-number test, `isinstance(sc, float) and math.isfinite(sc) and not
  sc.is_integer()` notes the row in `out.fractions` and `continue`s, so a fraction is still no score in the dict.
  Text, null, bool, lists, objects, nan, inf and -inf go on to the old test and are skipped as before. After the loop,
  `facts["fractions"] = len(out.fractions)` when there is at least one. Signature, dict contents, `answered` and
  `symbol_mismatch` are unchanged. Docstring updated.
- `NewsTrader._scored` (the place that takes the batch's answer before `handle_scored` uses it): when the call has
  facts, `facts.setdefault("fractions", 0)` before `scorer_called`, so every engine row in `news_scorer_calls.jsonl`
  carries the count, 0 too. A plain-dict stand-in has no facts and no `fractions` (`getattr`), so it still leaves no
  row. Then, for each headline of the chunk with a fraction `f` where the key has no whole score, the symbol is in
  `self.book.positions`, and `f["raw"] <= self.n["sell_on_score_at_most"]`, it adds
  `scores[key] = {"score": max(1, math.floor(raw)), "why": f["why"], "raw_score": raw}`. From there the existing code
  handles it as it handles a whole low score: the same `elif` in `handle_scored` (held, `px`, `live`), `_sell`,
  `_log_trade`, the same journal rows and the same owner line. The seen log says `scored` for that headline. Every
  other fraction stays out of `scores`, so its seen-log row is still `scorer_no_answer`.
- `handle_scored`: the `news_scores.jsonl` row gets `raw_score` right after `score`, only when the entry has one
  (`**({"raw_score": ...} if "raw_score" in s else {})`). A whole score's row is the same as before.
- Docstrings: the module docstring's owner's-rules line, `score_batch`, `Scores`, `_scored`, and one clause in
  `_seen_row` (see "Departures", 4).

`config.json`: in `news._note`, the brief's sentence, word for word, right after "sell_on_score_at_most and
max_hold_days are Claude's additions (set to 0 to disable).". No key added, no number changed. The file parses.

`tests/test_news_low_fraction.py` (new, 8 tests): class `LowFraction(_Engine)`. The scorer's reply goes through the
REAL `score_batch`. Only `news_live.subprocess.run` is replaced, by `_claude`. It refuses any command that is not
`claude -p ... ITEMS:`, reads the payload with `payload_of`, and returns `cli_reply` rows: the CLI envelope, with the
answer array as text. `payload_of` and `cli_reply` are reused from `tests/test_news_measure.py`. `json.dumps` writes
nan, inf and -inf as `NaN`, `Infinity` and `-Infinity`, and `json.loads` reads them back. `_quote_is_live` is replaced
with "live" for the whole class. BBB's live price is 49.5 (`LIVE_BBB`), above the 48.5 stop of `hold()`, so only a
score can sell it.
- `step_with(rows)`: the poll returns one fresh headline per row, then the real `self.nt.step()`, with stdout captured.
- `fresh_engine(session_open=True)`: calls `_Engine.tearDown` and `_Engine.setUp` (`super()`), reusing them rather
  than copying their body. The class's patches started with `addCleanup` stay in place. It then sets the live price
  and the session clock.
- `fresh_engine_holding_bbb()` is `fresh_engine()` followed by `hold(self.nt)`.
- The eight tests are the brief's, under its names, with its assertions (see "Departures", 2 and 3).

## Every reader of a score entry (`grep -n '\["score"\]\|\.get("score"' aitrader/`)

The only new entries are made in `_scored`. They are whole ints, `max(1, floor(raw))` with `raw <= sell_on_score_at_most`
(2 today, so the entry is 1 or 2), and only for symbols in `self.book.positions`.
- `news_live.py:257`: the parser itself (`row.get("score", 5)`).
- `news_live.py:328`, `_rescore` (the second check's re-score) reads `score_batch(...)`'s dict directly, not through
  `_scored`. That dict never holds a fraction, so the second check never sees one. `_judge_second`'s
  `isinstance(again, int)` is untouched.
- `news_live.py:1266` ("quote not live - no buy"): needs `score > buy_min_score` (8). Not reached by 1 or 2.
- `:1271` / `:1277-1283`: the score row and the two prediction rows. These are written as for any whole low score;
  the score row also carries `raw_score`.
- `:1285` (the buy branch), `:1310` (`_buy`), `:1314` (the queue): need `score > 8`. They also need
  `sym not in self.book.positions`, and every new entry is for a held name. Not reachable.
- `:1321`: the bad-news sale, the intended path. It still needs the name held, `px` (a price) and `live` (a live quote).
- `:1382-1383` (`_judge_second`): reached only from the buy branch, through `_second_check`. Not reachable.
- `:1451-1454`: queue items. These are only appended in the buy branch. Not reachable.
- `dashboard.py:86` reads `news_entry.score` of a position. That is written at a buy, and a fraction never buys.
- `dashboard.py:191-193` reads `news_scores.jsonl` rows. It sees a whole 1 or 2; `raw_score` is ignored, and
  `s["score"] > 8` is false.
- No other module reads `news_scores.jsonl` (`grep -rln news_scores --include=*.py`: `news_live.py`, `dashboard.py`,
  and `journal.py`, which only names it as a chained file).

## TDD evidence

RED (before any production change; `hold(self.nt)` already in test 1):
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_news_low_fraction.py' -v`
```
test_the_line_is_compared_on_the_fraction_itself ... (raw=1.9999) ... FAIL
test_the_line_is_compared_on_the_fraction_itself ... (raw=0.4) ... FAIL
ERROR: test_a_fraction_at_or_under_the_line_on_a_held_name_sells_and_the_record_keeps_what_was_said
    t = journal.read("news_trades.jsonl")[-1]
IndexError: list index out of range
ERROR: test_the_line_is_compared_on_the_fraction_itself
    self.assertEqual(journal.read("news_scores.jsonl")[-1]["score"], 1)  # 0.4 is stored as 1, never 0
IndexError: list index out of range
ERROR: test_the_scorer_call_row_counts_the_fractions
    self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 1)
KeyError: 'fractions'
FAIL: ... (raw=1.9999)  AssertionError: False != True
FAIL: ... (raw=0.4)     AssertionError: False != True
Ran 8 tests in 0.105s
FAILED (failures=2, errors=3)
```
Why this was the expected failure:
- Before the change, a fraction is dropped. BBB stays in the book, there is no trade row and no score row, and the
  call row has no `fractions`.
- The other five tests pass already, as they should. They pin behaviour that must not change: no buy, no queue, a
  high fraction, a name that is not held, the live-quote rule, and the whole/no-number values.
- Test 7's whole score 2 sells through the real parser and the stand-ins, which shows the harness can sell at all.
- The brief expected an `AssertionError` on the trade row. Taking `[-1]` of an empty journal raises `IndexError`, so
  the trade-row failure shows as an ERROR. It is still "no trade row; BBB still in the book".

GREEN, the same command, run 3 times in a row (each one `Ran 8 tests ... OK`):
```
test_a_fraction_at_or_under_the_line_on_a_held_name_sells_and_the_record_keeps_what_was_said ... ok
test_a_fraction_never_buys_never_queues_and_leaves_no_score ... ok
test_a_high_fraction_on_a_held_name_changes_nothing ... ok
test_a_low_fraction_on_a_name_that_is_not_held_is_dropped_as_today ... ok
test_a_whole_low_score_and_everything_that_is_no_number_are_as_before ... ok
test_the_line_is_compared_on_the_fraction_itself ... ok
test_the_sale_still_needs_a_live_quote ... ok
test_the_scorer_call_row_counts_the_fractions ... ok
Ran 8 tests in 0.200s
OK
```
The file starts no process and the output is pristine. I ran it 3 times anyway.

Unchanged files, each run alone through `safe`:
- `tests/test_news_measure.py`: `Ran 41 tests ... OK`. The loop over `None, "high", "9", 8.6, 9.5, True, ...` is green
  and unchanged.
- `tests/test_news_inputs.py`: `Ran 71 tests ... OK`.

Mutation check: each mutant was applied to a scratch copy, run through `safe`, and the copy was then deleted.

| Mutant | Result |
|---|---|
| compare `round(raw)` | killed (2 failures) |
| compare `floor(raw)` | killed (2 failures) |
| no held check | killed |
| no `max(1, ...)` | killed |
| no `raw_score` in the row | killed |
| no 0 count | killed |
| no count | killed |
| no `isfinite` | killed only after I added `-inf` (see "Departures", 3) |
| no `key not in scores` guard | survives (see "Concerns") |

## Whole suite

`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`, from
`ai-trader/`, on the final tree, exit 0, wall time 90 s:
```
Ran 667 tests in 89.603s

OK
```
The first run, before the self-review fixes, was also OK: 667 tests in 103.4 s, wall time 104 s.

## Files changed

- `ai-trader/aitrader/news_live.py` (+44 / -9)
- `ai-trader/config.json` (one sentence in `news._note`)
- `ai-trader/tests/test_news_low_fraction.py` (new, 125 lines)

After the commit, `git status --short` prints nothing. Nothing changed under `state/`, `logs/`, `reports/` or
`research/`.

## Self-review findings and what I did

1. My first edit of the `_seen_row` docstring left a broken line wrap. I reflowed it.
2. Without the `isfinite` guard, `-Infinity` (valid input to Python's `json.loads`) would be a "fraction" under the
   line. `math.floor(-inf)` raises `OverflowError`, and that would fail the step. The guard is in the code, but the
   brief's tests did not pin it (the mutant survived). I added `float("-inf")` to test 7's list, and the mutant is now
   killed.
3. If the scorer answers the same id twice, once with a whole number and once with a fraction, the fraction must not
   override the whole answer. That would change the trading of a headline that had a whole score, which the brief
   does not allow ("everything else stays as it is"). The `x["key"] not in scores` guard keeps the whole answer. It
   is one condition and no test pins it (see "Concerns").
4. Checked:
   - `sell_on_score_at_most` is read from the config, never written as a number in the logic.
   - The comparison is on `raw` itself; `math.floor` is used only for the stored number.
   - `answered` still counts only whole scores. The second check's own test is untouched.
   - `facts` is a fresh object per call, so the `setdefault` cannot leak between calls.

## Departures from the brief, and why

1. Where the count lives. The brief says `score_batch` counts the fractions in the call's facts, 0 too. Two existing
   tests in `tests/test_news_measure.py` pin the exact keys of `score_batch`'s facts:
   `ScorerFacts.test_an_envelope_without_figures_gives_no_made_up_numbers` (`sorted(facts) == ["answered", "model",
   "prompt", "sent", "wall_s"]`) and `test_the_clis_own_time_cost_and_tokens_are_kept`. The brief requires that file to
   stay unchanged and green. So `score_batch` writes `fractions` into its facts only when there is at least one, and
   the engine (`_scored`) writes 0 when there is none. Every engine row in `news_scorer_calls.jsonl` therefore carries
   the count, 0 included, which is what the forward measurement reads and what the new test asserts.
   Side effect: a manual `news-score` check row (`__main__.py`, not in the brief's files) carries `fractions` only when
   there was one. Readers should sum `row.get("fractions", 0)`.
2. Test 1 (`test_a_fraction_at_or_under_the_line_on_a_held_name_sells...`) has `hold(self.nt)` as its first line. The
   brief's body leaves it out. But the brief says BBB is held through `hold(self.nt)` "where a test says held", the
   test's name says "held name", and its expected RED says "BBB still in the book". Without the line the test could
   not pass under the brief's own rule, because a fraction on a name that is not held is dropped. The assertions are
   unchanged.
3. Test 7's list of values that are no number has one more, `float("-inf")`. This strengthens the test (finding 2) and
   weakens no assertion. It is still 8 tests.
4. Lines changed beyond the brief's list:
   - The `news_scores.jsonl` row in `handle_scored`: the brief requires `raw_score` in that row, and the row is
     written there.
   - One clause of the `_seen_row` docstring. Without it the docstring would say every non-whole score is
     `scorer_no_answer`, which is no longer true.
5. The test module starts with its docstring, and `from helpers import no_phone  # noqa: F401` is its first statement.
   This matches `tests/test_ownerlines.py` and `tests/test_news_supervised.py`. The brief says the file "begins with"
   the import.
6. The whole-answer-wins guard (finding 3) is not in the brief.

## For the gate (rule 4) and the forward measurement

- Before: `state/news_scores.jsonl` on 2026-11-11 had 1,190 rows and 0 fractions. This is the brief's figure; I did not
  re-read the live state.
- After, read at every Saturday review:
  - the rows of `state/news_scores.jsonl` that carry `raw_score`. Each one is a sale this change made, and a losing one
    goes through the loss protocol like any other sale;
  - the sum of `fractions` in `state/news_scorer_calls.jsonl` (engine rows always carry it; use `get(..., 0)` for
    `news-score` rows). This is how often the scorer answers with a fraction at all.
- Time machine: no backtest module imports `news_live` or reads the `news` block (grep of `backtest.py`,
  `strategy.py`, `signals.py`, `data.py`, `learn.py`). `config.json` is loaded whole by the time machine, so its
  `config_sha256` changes, but the only change is the `news._note` text. No number the replay reads changed.

## Concerns

1. `sell_on_score_at_most = 0` is the documented way to switch the bad-news exit off. With that setting, a negative
   fractional answer (for example -0.5) on a held name is still at or under the line. It gets a score entry of 1, so
   one score row and two prediction rows are written, and there is no sale (1 is not <= 0). Before this change it left
   no row. Trading is unchanged, and this is exactly what a whole negative answer (-3, clamped to 1) already does.
   I kept the brief's literal comparison (`raw <= line`). If the owner wants a switched-off exit to ignore fractions
   completely, the fix is one extra condition (`line >= 1`).
2. No test pins the whole-answer-wins guard (`x["key"] not in scores`); a duplicate-id answer is the only case it
   covers. A 9th test would go beyond the brief's 8. One subTest would pin it if the reviewer wants it.
3. As in departure 1: `news-score` rows carry `fractions` only when it is above 0.

## Fix round 1

Start: `8a9d86d0b156b580ea61fdd38f49e6728e6322b8` on `supervisor-build`, clean tree (checked first).
Commit: `7c37bd53` fix(ai-trader): every scorer-call row carries the fractions count, 0 too
(a new commit; nothing amended. The message has no trailer.)

### F1 - fixed
- `ai-trader/aitrader/news_live.py:668` (`NewsTrader.scorer_called`): the row is now
  `{"at": journal.now_utc(), "fractions": 0, **facts}`. All three writers go through this function: the engine's call
  (`_scored`), the row of a call that raised (`_scored`'s `except`, `:679`), and the manual check
  (`aitrader/__main__.py:330`). So every row carries the count, and 0 is written too. When `facts` has a count
  (`score_batch` writes one when it is at least 1), that count overrides the 0. Empty `facts` still leaves no row,
  because the `if facts:` guard is unchanged.
- `ai-trader/aitrader/news_live.py:683-684` (old lines): the `facts.setdefault("fractions", 0)` in `_scored` is removed.
  The facts that `_scored` returns are read by `step` only for `"error"` and `"symbol_mismatch"` (`:1560-1561`), so
  removing it changes nothing else.
- `scorer_called`'s docstring now says every row carries the count, 0 too. `score_batch` and its facts are unchanged:
  `tests/test_news_measure.py:104` still pins their keys, and that file is unchanged.
- Report departure 1's side effect and concern 3 (news-score rows carry `fractions` only when it is above 0) no
  longer apply. Every row in `news_scorer_calls.jsonl` now carries `fractions`. The forward sum is now a plain sum
  of `row["fractions"]`. Old rows written before this change still need `row.get("fractions", 0)`.

Test: `tests/test_news_low_fraction.py`, `test_the_scorer_call_row_counts_the_fractions` (still 8 tests). I added
assertions and changed none of the brief's.
- The row of a call that raised out of the scorer (`score_batch` replaced by one that raises `ValueError`) has
  `fractions` 0.
- The row of a news-score check has `source` "news-score" and `fractions` 0. The row is written the way `__main__.py:330`
  writes it: the real `score_batch` through the class's `subprocess.run` stand-in, then
  `nt.scorer_called(sc.facts and {**sc.facts, "source": "news-score"})`.

RED, before the code change:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_news_low_fraction.py' -k test_the_scorer_call_row_counts_the_fractions -v`
```
ERROR: test_the_scorer_call_row_counts_the_fractions
  File ".../tests/test_news_low_fraction.py", line 125, in test_the_scorer_call_row_counts_the_fractions
    self.assertEqual(journal.read("news_scorer_calls.jsonl")[-1]["fractions"], 0)
KeyError: 'fractions'
Ran 1 test in 0.012s
FAILED (errors=1)
```
(line 125 is the row of the call that raised)

GREEN. Covering tests, each through the safe wrapper, from `ai-trader/`:
- `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p 'test_news_low_fraction.py' -v`,
  3 times in a row. The file starts no process, so the 3 runs were not required. Each run printed:
  ```
  test_a_fraction_at_or_under_the_line_on_a_held_name_sells_and_the_record_keeps_what_was_said ... ok
  test_a_fraction_never_buys_never_queues_and_leaves_no_score ... ok
  test_a_high_fraction_on_a_held_name_changes_nothing ... ok
  test_a_low_fraction_on_a_name_that_is_not_held_is_dropped_as_today ... ok
  test_a_whole_low_score_and_everything_that_is_no_number_are_as_before ... ok
  test_the_line_is_compared_on_the_fraction_itself ... ok
  test_the_sale_still_needs_a_live_quote ... ok
  test_the_scorer_call_row_counts_the_fractions ... ok
  Ran 8 tests in 0.086s / 0.114s / 0.080s
  OK
  ```
- `tests/test_news_measure.py` (unchanged; it covers the `scorer_called` rows, including the call that raised):
  `Ran 41 tests in 0.167s`, `OK`.
- `tests/test_news_inputs.py` (unchanged; it covers the news-score row): `Ran 71 tests in 0.993s`, `OK`.

Whole suite: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests`,
from `ai-trader/`, before the commit. Exit 0, wall time 95 s. Last three lines:
```
Ran 667 tests in 94.115s

OK
```
After the commit, `git status --short` prints nothing.
