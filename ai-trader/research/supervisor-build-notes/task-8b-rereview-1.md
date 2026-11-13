# Task 8b - re-review of fix round 1

Fix base `8a9d86d0`, head `7c37bd53` (one commit: "fix(ai-trader): every scorer-call row carries the fractions count, 0 too").
Diff package: `/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-8b-fix1.diff` (2 files, +12 -3).
Read-only on the gate clone; the suite was not re-run.

### Finding Verdicts

- **F1 - ADDRESSED.**
  - `ai-trader/aitrader/news_live.py:668`: `NewsTrader.scorer_called` now writes
    `{"at": journal.now_utc(), "fractions": 0, **facts}`. The `if facts:` guard is unchanged, so empty facts still
    write no row. A count from `score_batch` (`:268-269`, only when it is 1 or more) comes later in the dict and
    overrides the 0.
  - All three writers go through this one function:
    - the engine's call: `_scored`, `:684`;
    - the row of a call that raised: `_scored`'s `except`, `:681`;
    - the manual check: `aitrader/__main__.py:330`.
    So every row now carries the count, and 0 is written too. That is the defect F1 named.
  - The `facts.setdefault("fractions", 0)` in `_scored` is gone. The facts that `_scored` returns therefore no longer
    carry `fractions` when the count is 0. The report says `step` reads those facts only for `error` and
    `symbol_mismatch`. A grep found no other reader of a `fractions` key in those facts, so removing it loses nothing.
  - `score_batch` and its facts are unchanged. `tests/test_news_measure.py:104`, `sorted(facts)` with no
    `fractions`, still holds, and that file is not touched.
  - I checked every existing test that reads a scorer-call row: `test_news_measure.py:213-253`, `:313-314`, and
    `test_news_inputs.py:944-958`. None of them pins the full set of keys or the whole row, so adding a key breaks
    none of them.
  - Besides the engine (`news_live.py:17`, `:657`, `:668`), the file is named only in prose:
    `skills/trader/SKILL.md:245` and `state/backlog.md`. No other code reads it.
  - The new assertions in `tests/test_news_low_fraction.py:122-130` cover the two paths F1 named:
    - The call that raised (`:123-125`). The `assertRaises(ValueError)` proves the call was made, so `[-1]` is that
      call's row and not a leftover row.
    - The news-score row (`:127-130`).
    The recorded RED is `KeyError: 'fractions'` at line 125, the row of the call that raised. It shows the test failed
    before the fix.

### New Breakage in the Fix Diff

- **Minor - `ai-trader/tests/test_news_low_fraction.py:127`.** The news-score item is
  `{"symbol": "AAA", "title": "AAA news", "published": ...}`, with no `"key"`.
  - What happens: inside the real `score_batch`, the scorer's row for that item reaches
    `out[x["key"]]` (`news_live.py:263`). It raises `KeyError`, which the per-row `except` swallows (`:264`). The
    check's row therefore has `answered: 0`.
  - What it means: the item is not shaped like a fetched headline, so this does not reproduce a real check that
    answered. The assertion still separates fixed from broken code: before the fix this row had no `fractions` at
    all. Correctness is not affected.
  - Fix: add `"key": "k9"` to that item. Or drive the row through `run_cli("news-score")` as
    `tests/test_news_inputs.py:918-935` (`_news_score`) does; its item carries `"key": "k1"`.
- Nothing else. The production change is one dict literal and one deleted `setdefault`.

### Out-of-Scope Observations

- Rows already in `state/news_scorer_calls.jsonl` from before this change have no `fractions` key. The Saturday sum
  still needs `row.get("fractions", 0)` over the old rows. The fix report says so.

### Fix-report test evidence

The fix report gives the evidence for every covering run:
- RED: the command (the safe wrapper, `-k test_the_scorer_call_row_counts_the_fractions`) and its output
  (`KeyError: 'fractions'`, `FAILED (errors=1)`).
- GREEN: `test_news_low_fraction.py`, 8 tests `OK`, with per-test output.
- `test_news_measure.py`: 41 `OK`.
- `test_news_inputs.py`: 71 `OK`.
- The whole suite through the safe wrapper: `Ran 667 tests`, `OK`, exit 0, 95 s.

These claims fit the diff. I found nothing that makes a re-run necessary.

### Verdict

**PASS.** F1 is fixed. The only point on the fix diff is one Minor test-fidelity nit, which blocks nothing.
