### Task 8d: The priming poll keeps its eight threads, with a beat after each feed call

**Kind:** BUILD. **Authority:** the controller's ruling on a plan-mandated finding of Task 8a's review (ledger,
Ruling 26). Not in the plan; lands with rollout step 1.

**Why:** Task 8a's brief asked for "a beat between any two priming feed calls" and its test asserted strictly rising
beat counts, which can only hold if no two feed calls overlap; the implementer therefore made the priming poll ask
its feeds one at a time (`ThreadPoolExecutor(max_workers=1 if prime else 8)` in `poll_headlines`). A start that
primes (a new or rebuilt machine: `news_seen.json` is git-ignored) then takes about 20-45 s instead of 3-6 s, and up
to about 15 minutes when Yahoo sits at its 10 s feed timeout - time in which no stop look and no planned stop is
seen. The heartbeat's purpose (spec 5.5) is that no stretch passes one network call without a beat; it does not ask
for the calls to be serial.

**Files:** Modify `aitrader/news_live.py` (`poll_headlines`). Test: `tests/test_news_supervised.py` (the priming test
of class `FollowUps` that Task 8a added; and one new test).

**What changes:**
- `poll_headlines` uses the same pool size for priming as for a normal poll (8, as before Task 8a). The calling thread
  takes the feed results as they complete (`concurrent.futures.as_completed`) and writes `self._beat(<current
  phase>)` after each one it receives. No beat is written from a worker thread.
- The priming test of Task 8a changes its assertion from "strictly rising beat counts over the feed calls" to: the
  number of beats written during priming is at least the number of feed calls, and a beat is written after the last
  feed call returned (the beat count read in the feed stand-in at its return is always lower than the count after
  `poll_headlines` returns). Its name and its other assertions stay.
- New test `test_priming_asks_its_feeds_in_parallel`: 16 feeds whose stand-in sleeps 0.2 s; priming ends in less than
  1.6 s (serial would take 3.2 s) and leaves at least 16 beats.

- [ ] Write the new test and change the assertion; run `-k FollowUps`: the new test fails (about 3.2 s, serial).
- [ ] Implement.
- [ ] Run the test file and `tests/test_supervise.py` 3 times in a row, then the whole suite through the safe wrapper: OK.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/tests/test_news_supervised.py`; message
  `fix(ai-trader): the priming poll asks its feeds in parallel again, with a beat after each one`.

No buy, sale or stop rule changes. It touches no file the time machine loads.
