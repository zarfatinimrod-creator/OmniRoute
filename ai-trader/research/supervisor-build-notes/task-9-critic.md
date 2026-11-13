QUANT-CRITIC VERDICT, rule 4, rollout step 1 of the supervisor plan
Commit: landing-step1 at 9e110251, reviewed as the diff origin/ccr-120121ba-vsvwlj..HEAD (16 files, +3058/-74).
VERDICT: PASS. Nothing blocks the landing.
(The file task-9-critic.md was not written: the critic role says "Do not modify files" and the harness forbids report files. This text is the verdict.)

1. TIME-MACHINE FILES: NOT TOUCHED
- `git diff --name-only origin/ccr-120121ba-vsvwlj..HEAD | grep -E '^ai-trader/aitrader/(backtest|strategy|signals|learn|metrics|broker|data)\.py$'` found nothing.
- config.json compared as parsed JSON at both refs:
  - risk, signals, costs and books are identical;
  - changed: news._note and the new news.sleep_slice_seconds 0.5 (config.json:244);
  - added: a top-level `supervisor` block (config.json:301-306).
- None of the seven modules reads news_live, ownerlines, `news` or `supervisor`.
- state/trials.jsonl is unchanged (4 rows) and no sweep was registered. Under the owner's rulings, no sweep is owed.
- Side effect: backtest.config_hash (backtest.py:247-248) hashes the whole config, so the next registered run shows a new config_sha256. Provenance only.
- Look-ahead: nothing historical changed. test_core.NoLookahead: 3 OK, run through the safe wrapper.

2. 8b MATCHES THE OWNER'S DECISION (backlog 62), AND NOTHING MORE
- What the scorer answer becomes:
  - A finite fraction goes only into .fractions and never into the scores (news_live.py:258-260). nan and inf are skipped; text is skipped (Ruling 13).
  - A fraction becomes a score only when all of these hold: no whole answer for that key, the name is held, and raw <= sell_on_score_at_most (686-690).
  - The stored score is max(1, floor(raw)), a whole int. raw_score keeps what the scorer said, and the news_scores row carries it (1270).
- What it cannot do:
  - It never buys: a buy needs a score above 8 (1283).
  - It never queues: the queue is inside the buy branch (1312).
  - It never passes a second check: the re-score of a fraction is None, which refuses (328, 1372-1373).
- How it sells: only through the existing branch, which needs a held name, a price and a live quote (1319-1322), then the unchanged _sell and _log_trade.
- The off switch still works: with the setting at 0 the score is 1, which is above 0, so nothing sells.
- No new knob.
- The forward measurement can be computed from what the code writes:
  - news_scores.jsonl rows with raw_score (the field cannot exist before this landing, so it dates itself);
  - news_scorer_calls.jsonl `fractions` (668; 0 on every engine row);
  - SELL rows of news_trades.jsonl with the reason "bad news score N: why" (1320).
  - "Same step" is not a written field. Join on: same symbol; the trade's reason equals f"bad news score {score}: {why}" of the raw_score row; the trade's logged_at comes after the score row's.
  - The 'before' figure needs a correction (note N10).
- Tests: test_news_low_fraction 8 OK.

3. SPEC 12 LIST AND THE ADDITIONS: EACH ONE ACCEPTED
- A stop look before git and priming at every start. The order of _run (1829-1897):
  1. start_checks
  2. NewsTrader (makes no network call, 591-619)
  3. adopt_previous
  4. "boot" beat
  5. chain check (1848)
  6. first look (1852)
  7. beat
  8. E2 (1867), E1, say_late (1887)
  9. code_stamp (1889)
  10. priming (1893)
- Calendar not covered gives exit 5 (1830-1834). An idle engine checked no stop either. Under the old watchdogs, every relaunch repeats the urgent line.
- A missing or unreadable book, or a file that parses but is not a book, gives exit 6 (1712-1721). The old engine would crash, or build an empty book on top of real trades.
- A merge or rebase in progress gives exit 7. tree_busy (1675-1692) only looks at files, no git command. See N2.
- Book versus journal mismatch: that process opens no position (786-788). The block is enforced in _buy (885) for every buy path. Sales and stops are untouched. See N7.
- SIGTERM and SIGINT are a planned stop (93-96, 1783, 1903-1905, 1932):
  - the end-of-step look still runs (1573);
  - headlines never handed to the scorer are unmarked as seen (1566-1571);
  - see N3 and N4.
- An engine under a parent dies with it (99-103, 1785-1789, 1901-1902). Not used in production until step 2.
- The lock file is opened with "a+" and names its holder (1790-1806). A refused start writes no state.
- Ruling on a lock call that fails (not a held lock): keep running unlocked, with E2. This is the old behaviour, now said out loud. Refusing would leave the stops unwatched. See N1.
- A stop look's lines go out after every sale and the save, never before (1169-1186).
- The blind clock survives a restart (1610).
- _beat never raises (1630-1673). Not literally after every network call: see N12.
- Additions:
  - start_checks before the book is built: safer than the order in spec 5.1.
  - --check also reads the chains (1747). It is read-only and takes no lock.
  - E1, E2 and the late line come after the first look, so no send can delay it.
  - The bare engine sends R5d itself on exit 6 (1837). See N8.
  - The between-batch look is skipped after a planned stop is asked (1562, Ruling 22). Nothing that calls out stands between the batch loop and the end-of-step look, so no look is lost.
- Exit 4 on a broken chain, at start (1848-1858) and in the loop (1918). Still no stop is sold on a broken chain (owner question 2 is still ב).
- 8c: --cancel is refused without --said, before anything changes (__main__.py:388-392). The row is written after the request is dropped (408); a failure is said, with exit 1. The file is not chained (Ruling 24). This only makes a cancel harder. Tests: test_news_exit_cancel 6 OK.

4. DELAY, SKIP, REORDER, WEAKEN, RISK, MISSING DATA, LOOK-AHEAD, CHAINS, TESTS: NOTHING BLOCKING
- The stop rule is unchanged (946-947). The new calls inside the stop loop are guarded and come after the sale and its save.
- The first look now comes earlier than before this change.
- No new chained file. Adding raw_score keeps the chain valid.
- Tests cannot reach the phone, the network or the model:
  - helpers/no_phone is imported first in every new test module;
  - _Engine and TempState redirect journal.STATE and stub notify, live_price and the scorer;
  - engine_child installs a tripwire for non-127.0.0.1 traffic and for claude and git processes;
  - the --check tests fail at once if a trader is built.

NON-BLOCKING NOTES (the full text of each is in `notes`)
- N1. Backlog: an unlocked engine should open no new position.
- N2. Exit 7 is silent to the owner in step 1 (no parent, no R3c).
- N3. SKILL.md "kill <pid>, then start" is now stale: after a planned stop the next start exits 3 for a while.
- N4. A stop signal sent to the whole process group loses the scorer batch in flight.
- N5. Unsent trade lines are resent every step, up to 15 s per channel each time.
- N6. sleep_slice_seconds <= 0 makes the wait loop spin forever.
- N7. The mismatch check reads only the last row, and the first look can sell twice.
- N8. R5d send has no guard, and its wording can be false.
- N9. The lock-holder write has no guard.
- N10. Backlog 62's 'before' figure cites a file that could never hold a fraction. The real figure: news_seen_log.jsonl has 0 scorer_no_answer in 729 rows.
- N11. Prediction rows made from fractions are graded with the rounded-down score.
- N12. Three network calls still have no beat of their own.
- N13. The merge kept the live branch's edits.

NOTES
- The verdict file /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/task-9-critic.md was NOT written. agents/quant-critic.md:27 says 'Do not modify files', and this harness forbids report .md files. Those outrank the workflow's request. The full verdict is in `report`; the controller can save it from there.
- Tests run, all through the safe wrapper with PYTHONDONTWRITEBYTECODE=1, and the clone stayed clean: test_core.NoLookahead 3 OK, test_news_low_fraction 8 OK, test_news_exit_cancel 6 OK. The whole suite was not re-run, as instructed (the controller reports 677 OK).
- N1. Ruling on spec 5.2 (the lock call itself fails, as opposed to a held lock): keep the start going, unlocked. This is the old behaviour; the new code only adds the E2 line and `lock:false` in the heartbeat. Refusing would leave held names with no stop look (news_live.py:1799-1801, 1866-1870). Recommended for the backlog, reduce-only: an unlocked engine opens no new position (add 'no_lock' to `_buys_blocked`). That removes the double-buy risk and the stops still run.
- N2. In step 1 there is no parent, so exit 7 (merge or rebase half done, news_live.py:1710-1711) only prints; the owner gets no line. If a turn is cut mid-pull, there is no engine and no stop look until a session follows the new SKILL.md line. I accept it for step 1, because the old engine started on a half-merged tree, which is worse. Step 2 must bring R3c, or the bare engine should send one line on 7 when the book holds a name.
- N3. SIGTERM no longer ends the engine at once. SKILL.md:191-193 still says 'kill <pid>, then start'. That start now exits 3 until the old engine finishes its step: up to one scorer call (about 90 s) plus a look, and after the close drain_trial waits verify_timeout_seconds. Add to the step-2 SKILL table: wait for exit 143 or heartbeat phase 'stopping', and use kill -9 only if it never ends. The old engine keeps checking stops meanwhile, so there is no protection gap.
- N4. If the stop signal also reaches the scorer child (which signal the platform sends is not documented), the batch in flight fails as scorer_failed. Its headlines stay marked seen and are saved by the step's save and the final nt.save(); only the keys never handed to the scorer are unmarked (news_live.py:1566-1571). They are never scored again: a bad-news exit can be missed, though the -3% stop still holds. Consider also unmarking the keys of a failed batch when STOP is set.
- N5. A trade line nobody received is sent again by every step's closing message (news_live.py:1503-1521). If a channel hangs, each step pays up to 15 s per channel. The gap between stop looks then grows from about 20 s to about 35-50 s for as long as that outage lasts. Add a back-off.
- N6. If sleep_slice_seconds is 0 or less, the wait loop at news_live.py:1932-1934 never ends (`left` never falls): no further steps, no stop looks. The config value is 0.5. Add a floor or a validation.
- N7. The book-mismatch check reads only the last journal row (news_live.py:1722-1727). A later row, for example a stop sale of another name, hides an unrepaired BUY mismatch from the next process, and buys open again. In the SELL case, the first look can sell the same name a second time: a second SELL row, so journal-based P&L and the postmortem list count it twice. In effect both were true before this change; they are now detected and said. Repair stays with the session (spec K 43). SKILL.md still has no E1 procedure.
- N8. The R5d send (news_live.py:1837-1838) has no guard, unlike E1 and E2: a render error turns exit 6 into a traceback with exit 1. Also, R5d says 'ויש עסקאות ביומן' (there are trades in the journal), which is false for a non-book file with an empty journal (Ruling 18).
- N9. Writing the holder's name into the lock file (news_live.py:1803-1805) has no guard. An OSError there ends the start with a traceback after the lock was already taken.
- N10. Backlog 62's 'before' figure cites news_scores.jsonl (1,190 rows, 0 fractions). That file could never hold a fraction: the old score_batch dropped fractions before anything was written (origin news_live.py:221). The informative before figure is news_seen_log.jsonl outcome 'scorer_no_answer': 0 of 729 rows at this commit (293 scored, 436 stale). news_scores.jsonl now has 1,483 rows. Correct this at the next Saturday review, and write down the 'after' start date (the landing date) and the join rule given in the report.
- N11. A score made from a fraction also writes two news_predictions rows, graded with the rounded-down score (prob 0.32 for an answer of 1.6, news_live.py:1275-1282). When reading forecast accuracy, separate those rows through raw_score.
- N12. Spec 5.5 asks for a heartbeat after every network call, and that is not met to the letter. Three calls have no beat of their own: the benchmark quote (news_live.py:1254), the step's closing send (1520), and the second check inside run_queue_at_open. Trading is not affected. It matters for step 2's hang rule.
- N13. The merge kept the live branch's edits: the `books` block is identical, cycle.py and state/ are not in the diff, and origin/ccr-120121ba-vsvwlj is an ancestor of HEAD.