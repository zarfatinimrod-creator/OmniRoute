### Task 9d: Test robustness and one guard after Task 9c

**Kind:** BUILD (small). **Authority:** the controller's Ruling 33 (progress.md), from Task 9c's review
(`task-9c-review.md`) and report (`task-9c-report.md`). Not in the plan; owed before Task 20 like 9b and 9c. No trading
rule changes; no stop look delayed or skipped.

**Files:** Modify `aitrader/news_live.py` (item 4 only), `config.json` (item 3: one `_note` text, no value),
`tests/test_news_supervised.py`. Nothing else.

1. In `tests/test_news_supervised.py` near line 1305, the late-line count that 9c turned into a hard-coded `+ 1` (it
   assumes the timed loop made at least one step) becomes robust again (for example `+ min(1, step)` with `step` read
   from the heartbeat as before). Same for the second `+ 1` that 9c's report names, if it has the same assumption.
2. The item 1 test of `GateFollowUps` (near line 1711) sets `unsent_resend_seconds` on its own `self.cfg` copy (120)
   instead of asserting the shared `config.json` value, so a tuned value does not fail it.
3. `config.json` (about line 243): the `_note` of `news.unsent_resend_seconds` also says it spaces the late-line
   retries of `step()` (Ruling 28). Text only; no value changes; the `DEFAULTS` twin and the pin test stay green.
4. `aitrader/news_live.py` (about line 1996): the loop's own `news_errors.jsonl` append for a failed step is guarded
   like the other guards (a failure to write the row prints one line with the exception class and the loop goes on;
   it never turns a failed step into a traceback). Test: the append raises once, the loop takes its next step.
5. The 45-line test at about lines 1790-1836 that drives six scenarios in sequence is split into one test per scenario
   (same assertions, same names plus a suffix), so an early failure no longer hides the later ones.

- [ ] Write item 4's test; it fails (RED) for the reason item 4 names. Items 1, 2, 3, 5 are refactors: the tests stay green.
- [ ] Implement items 1-5.
- [ ] Run `tests/test_news_supervised.py` 3 times in a row, then the whole suite through the safe wrapper: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/config.json ai-trader/tests/test_news_supervised.py`;
  message `test(ai-trader): sturdier follow-up tests and a guarded failed-step row`.

**For the report and the gate:** confirm no assertion was weakened (item 5 keeps every assertion), no value in
config.json changed, and where item 4's guard stands. It touches no file the time machine loads (config.json: a
`_note` text only).
