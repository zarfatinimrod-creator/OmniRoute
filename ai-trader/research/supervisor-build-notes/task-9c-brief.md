### Task 9c: The last follow-ups of step 1, owed before rollout step 2

**Kind:** BUILD. **Authority:** the controller's Rulings 28 and 29 (progress.md), from Task 9b's review
(`task-9b-review.md`, items 1-8 and its plan-mandated finding F1) and the implementer's concerns in `task-9b-report.md`.
Not in the plan. It must be committed before Task 20 lands; it changes no trading rule: no buy, sale, stop or hold rule,
no stop look delayed or skipped.

**Files:** Modify `aitrader/news_live.py`, `ai-trader/.gitignore` (one line), `tests/test_news_supervised.py` (class
`GateFollowUps`, plus the two tests named in item 7). Nothing else.

1. **The late-line retry backs off (Ruling 28).** The retry that Task 9b put in `step()` (its `finally`, after the
   closing message) runs at most once every `news.unsent_resend_seconds`, measured with a monotonic stamp of the last
   attempt. The call at the start stays as it is (unthrottled). A delivered late line marks its rows told as before.
   Test: two failed retries 30 s apart make one send; after 120 s it is sent again.
2. **The loop's two alerts never turn a code into a traceback.** Guard, the way Task 9b guarded the start's sends (an
   error goes to `news_errors.jsonl` with its own `where`): the ChainBroken alert (the run still ends with 4) and the
   `alert_after_errors` alert (the loop goes on). Test both: the alert's send raises, the run returns 4 / the loop
   takes its next step.
3. **Shutdown and step error handling stay whole.** In the priming poll, the `ex.submit(...)` list moves inside the
   `try` whose `finally` shuts the executor down. In `step()`, `carried = earlier + self._unsent[mine:]` and the
   `_carried_at.update(...)` move inside the `try` that held `_unsent[mine:]` before 9b. No new test needed if the
   existing ones still pass; say so in the report.
4. **A cut priming primes again.** If a planned stop (`STOP`) cuts the priming poll of a start whose `seen` was empty,
   the state saved at the stop must make the next start prime again (today it saves a partial `seen`, the next start
   sees `seen` not empty, skips priming, and headlines from the unprimed feeds inside `fresh_minutes` are scored and,
   once the hold lifts, can be bought). Choose the smallest way (for example: do not save `seen` after a cut first
   priming). Test: STOP set during the first priming -> a fresh start with the saved state runs priming.
5. **No exception text in the new guards' rows; the errors file stays out of git.** The rows written by the guards
   Task 9b added (calendar alert, R5d line, broken-chain alert at the start, lock write; late-line send) and by item 2
   carry the exception's class name only, never `str(e)` (constraints.md line 11: logs carry a status code or an
   exception class, never a URL or an exception's text; the repository is public). Do not change what older call
   sites write. Add `state/news_errors.jsonl` to `ai-trader/.gitignore` (the file is untracked today but not
   ignored). Test: a guard whose send raises `RuntimeError("https://ntfy.example/secret-topic")` writes a row whose
   text does not contain "secret-topic".
6. **The blind-quote alert follows the channel rule.** In `_stop_sight`, an alert counts as delivered when it was
   taken by a channel OR when `notify.channels(self.cfg)` is empty (the line was printed to the log, which is all this
   setup has), as Task 9b made the other lines. With a channel configured and a failed send, nothing changes. Test both.
7. **Two weak tests made strong.** (a) `WhoWasTold.test_a_late_line_that_cannot_be_sent_costs_a_row_and_never_the_start`:
   check the row count again (9b turned the exact list into a set), with item 1's back-off in force. (b) The SKILL
   test of 3ב: also check the three options א/ב/ג of the E1 paragraph, the recommendation of ג, and the two-minute
   bound of the kill procedure.

- [ ] Write the tests; run `-k GateFollowUps` (and the two of item 7): the new ones fail (RED) for the reason each item names.
- [ ] Implement items 1-7.
- [ ] Run `tests/test_news_supervised.py` and `tests/test_supervise.py` 3 times in a row, then the whole suite through
  the safe wrapper: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/.gitignore ai-trader/tests/test_news_supervised.py`;
  message `fix(ai-trader): the last follow-ups of step 1 - a late-line back-off, the loop's alerts guarded, a cut priming primes again, no exception text in the new rows`.

**For the report and the gate:** show where each guard and the back-off stand; confirm no buy, sale, stop or hold rule
changed and no stop look is delayed or skipped. It touches no file the time machine loads.
