### Task 9b: The gate's follow-ups, owed before rollout step 2

**Kind:** BUILD. **Authority:** the quant-critic's verdict and the independent whole-step review of rollout step 1
(`task-9-critic.md`, `task-9-review.md` in this directory), and the controller's ruling in the ledger ("Owed BEFORE
rollout step 2"). Not in the plan. It must be committed before Task 20 lands; it changes no trading rule.

**Files:** Modify `aitrader/news_live.py`, `aitrader/notify.py`, `aitrader/__main__.py` (only if item 4 needs it),
`config.json` (one new key under `news`, with its `DEFAULTS` twin), `skills/trader/SKILL.md` (section 3ב).
Test: `tests/test_news_supervised.py` (class `GateFollowUps`).

Each item below is one behaviour with one test (at least) in `GateFollowUps`. Keep each change as small as it can be.

1. **The late line is retried.** Today `say_late()` runs only at a start; if its send fails, the late rows stay in
   `_unsent` and `told_through` is frozen for the rest of the process (review M3). From now on, while `self._late` is
   not empty, `step()` calls `say_late()` again once per step, after the step's own closing message. A delivered late
   line marks its rows told as before. Test: the first `say_late()` fails, the next step's call is delivered, the
   rows are told once and `told_through` moves.
2. **No channel configured is "said" to the log.** `notify.send` returns `[]` both when every channel failed and when
   no channel is configured at all (no topic and no Telegram pair in the environment). Add
   `notify.channels(cfg) -> list[str]` (the channels that are configured; standard library and the existing env
   names only). Where the engine decides whether a line was taken (the look's message, the closing message, the late
   line, E1), an empty `channels(cfg)` counts as taken: the line was printed to the log, which is all this setup has
   (review M4). With a channel configured and a failed send, nothing changes. Test both cases.
3. **A resent line backs off.** While a trade line stays untaken, each step's closing message sends it again (Task
   6); in an outage that costs up to 15 s per channel every step (critic N5). From now on such a line is resent at
   most once every `news.unsent_resend_seconds` (new key, 120, also in `DEFAULTS`); a step inside that wait leaves it
   out of the message but keeps it in `_unsent`. The first send of a new line is never delayed. Test: two failed
   sends 30 s apart send the old line once; after 120 s it is sent again; a new trade line in between is sent at once.
4. **The start's sends and writes never turn a code into a traceback.** Guard, the way E1 and E2 are guarded (an
   error goes to `news_errors.jsonl` with its own `where`, the start goes on to the code it would have returned):
   the calendar alert before exit 5, the R5d line before exit 6, the broken-chain alert before exit 4, the write of
   the holder's name into the lock file (an `OSError` there: the lock is still held, the engine runs), and
   `_set_pdeathsig()` (a failure: one printed line, the supervised start goes on). Test: each of the five raises in
   its stand-in and the start still returns 5, 6, 4, 0 and 0 respectively (the last two run a short loop).
5. **`news.sleep_slice_seconds` is clamped.** A value that is not a positive number (0, negative, text) would make
   the wait loop spin for ever with no step and no stop look (critic N6). It is replaced by the `DEFAULTS` value and
   one `news_errors.jsonl` row with `where` "config" is written at the start. Test: 0 and -1 each give one row and a
   loop that still ends.
6. **A planned stop does not wait on work it will throw away.** Once `STOP` is set: the trial-check drain at the end
   waits 0 s (not `verify_timeout_seconds`); the priming poll stops taking feed results (the ones not yet read are
   simply not primed); and the keys of a scorer batch that failed while `STOP` was set are taken back out of `seen`
   and the pending record, as the never-scored keys already are (review m1, m3, m4; critic N4). Test each.
7. **Three calls get their beat.** A `_beat(<phase>)` after the benchmark quote of a step, after the step's closing
   send, and after the second check inside `run_queue_at_open` (critic N12). Test: the beat count rises across each.
8. **SKILL.md 3ב.** Replace the line that says to `kill <pid>` and start again with: `kill <pid>` sends SIGTERM, which
   is now a planned stop: the engine finishes the call in flight and a stop look, saves and exits 143, which can take
   up to about two minutes; wait until the process is gone (or the heartbeat's phase is "stopping" and then the
   process is gone); a new start before that exits 3; `kill -9` only if it is still there after two minutes. And add
   one paragraph "E1 (התיק לא תואם ליומן העסקאות)": the session does not edit `news_book.json` by hand; it runs
   `python3 -m aitrader verify`, writes the owner one Hebrew message with the last journal row and the book's
   positions (exact numbers, "כסף נייר") and one question (א: to restore the position from the journal row / ב: to
   leave the book as it is and mark the row reviewed / ג: to keep buys blocked and look again tomorrow; recommend
   ג), and until he answers buys stay blocked (they are). Text in Hebrew where the section is Hebrew.

- [ ] Write the tests of `GateFollowUps`; run `-k GateFollowUps`: they fail (RED) for the reason each item names.
- [ ] Implement items 1-8.
- [ ] Run the test file and `tests/test_supervise.py` 3 times in a row, then the whole suite through the safe
  wrapper: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/aitrader/notify.py ai-trader/config.json ai-trader/skills/trader/SKILL.md ai-trader/tests/test_news_supervised.py`
  (and `ai-trader/aitrader/__main__.py` if item 4 touched it); message
  `fix(ai-trader): the gate's follow-ups before the supervisor's step 2 - retries, guards, a clamp, a planned stop that waits on nothing, three beats, the SKILL procedures`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look is delayed or skipped; show where
each new beat and each guard stands. It touches no file the time machine loads.
