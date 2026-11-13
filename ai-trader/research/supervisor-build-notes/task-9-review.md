# Task 9: whole-branch review of rollout step 1 (the news-engine changes)

Reviewed: `git diff origin/ccr-120121ba-vsvwlj..HEAD` in the gate clone (`landing-step1` at 9e110251, the live branch
merged into supervisor-build at 15c8c4e4). 16 files, +3058 / -74. I read all of `aitrader/news_live.py` as it now
stands (1942 lines), the diff of `__main__.py`, `ownerlines.py`, `config.json`, `skills/trader/SKILL.md`, the four
edited existing tests, the new test files (by structure, then closely for the told-through, planned-stop, fraction and
cancel classes), spec sections 5 and 12, and the deferred items in progress.md. No test was run. Nothing was changed.

## Verdict: ready to land

I found no Critical and no Important defect that blocks this landing. The stop path stays as it was: the live look
first, then the catch-up, then the alerts. Every new call in that path (the beats, the look's own message, the hash
read-back) is guarded, so none of it can raise out of the loop. Trading rules change only where the owner decided
(8b, the fraction exit; 8c, the cancel needs his words) and where spec 12 lists a change for the critic. The edits to
existing tests change only expectations (exit code 0 -> 4 on a broken chain, `**k` on stand-ins, the heartbeat file
allowed in two save-order pins, `--said` added to cancel calls). No test about a trade, stop, buy, sale or hold lost an
assertion.

The list below is Minor findings plus four items to do before rollout step 2, when kills and restarts become routine.

## Time-machine files touched

- `config.json` is the only file in the diff that the time machine loads (`data.load_config`). It changes `news._note`,
  adds `news.sleep_slice_seconds` and adds a top-level `supervisor` block. No time-machine code reads either block:
  `backtest`, `strategy`, `signals`, `learn` and `metrics` do not read `news` or `supervisor`, and `dashboard.py`
  reads only `news.starting_cash`. But `backtest.config_hash(cfg)` hashes the whole config (backtest.py:247-248,
  280). So every run record made after this landing carries a new `config_sha256`, and `diff_records`
  (backtest.py:320-324) lists that as a difference by design. The daily series do not move.
- `aitrader/news_live.py`, `aitrader/__main__.py` and the new `aitrader/ownerlines.py` are not imported by any
  time-machine module. `skills/trader/SKILL.md` is procedural memory, not code.

## Findings

### Critical
None.

### Important (blocking)
None.

### Minor, and should be done before rollout step 2

M1. `skills/trader/SKILL.md:191-193`: the restart steps still say "`kill <pid>`, then start". SIGTERM is now a planned
stop. The engine finishes its current call, which can be a scorer call of up to 90 s or, under "enforce", a second
check of up to 65 s per headline. Then it makes the end look, saves and exits 143. A start made right after the kill
gets exit 3, and the next line of the procedure (exit 3 -> kill -> start) loops until the old engine is gone. The old
engine still checks stops the whole time, so stops are never left unwatched. The fix is one line: after kill, wait
until the process is gone or the heartbeat says `"phase": "stopping"` (up to about 2 minutes); use `kill -9` only if it
is still there after that.

M2. SKILL.md has no procedure for E1 (book and journal disagree). The E1 line (ownerlines.py:62-63, sent at
news_live.py:1871-1886) tells the owner that the trader session must reconcile this, but the session has no steps for
it. Until a new trade row or a repaired book clears the mismatch, buys stay blocked on every start, which is the safe
side. This is rare in step 1, because the window is the milliseconds between the journal append and the book save.
It becomes likelier once a parent sends `kill -9`. This item was already deferred in progress.md line 207.

M3. news_live.py:1477-1491, 1503-1504, 1467-1475 (the late line). Late rows are tried only once, at the start. If that
send fails:
- the rows stay in `_unsent` for the whole process, and no step retries them (`step()` leaves `_late` out of
  `earlier`);
- `told_through` never moves again in that process;
- so the next start re-says every trade of the day after the old mark, including the ones this process did deliver.

Nothing is lost; trades are said twice. The fix: let `step()` retry `say_late()` while `_late` is not empty. D8a.3
(an earlier hash that is not a readable journal row) freezes `told_through` the same way.

M4. news_live.py:1460-1465 with notify.py:28-67: the line is not delivered when no channel is configured.
`notify.send` returns `[]` when no topic or Telegram variable is set, which the module calls a supported setup
("alerts are only printed, the Claude session relays them"). `_say` then reads every message as not delivered, so:
- every trade line is printed again at every step for the rest of the process (about 330 times in a 110-minute run);
- `told_through` never moves.

Production has a topic, so this is Minor. Count "no channel configured" as delivered to the log (D8a.2).

### Minor

m1. news_live.py:1551-1571 and 242-245: a group signal loses the batch that was in flight. A SIGINT or SIGTERM sent to
the whole process group (Ctrl-C, or a TaskStop that signals the tree) also kills the `claude -p` child. That batch
then ends as "scorer_failed", is marked seen and saved, and is never scored. Before this change, a kill left the batch
unseen, because seen is saved only at the end of a step, so the next engine scored it. The spec's parent signals the
engine alone, so this matters only for manual stops and for step 1's TaskStop. Fix: when STOP is set after a batch
whose call failed, put that batch back out of the seen-list as well. The -3% stop is not affected.

m2. news_live.py:1932-1934: `sleep_slice_seconds` of 0 or less loops forever. `left` never shrinks, so the engine
writes no beat and checks no stop. Clamp it (for example `max(0.05, ...)`) or check it at start. It is config only,
but one wrong digit hangs the engine.

m3. news_live.py:1938: after the close, `drain_trial(wait=verify_timeout_seconds)` also runs on a planned stop (143).
That adds up to 60 s to a stop that the parent's 120 s grace must cover. Use `wait=0` when `code == 143`.

m4. news_live.py:1893-1896: priming does not look at STOP. A planned stop during a first start waits for the whole
priming poll. With 93 feeds, 8 at a time and 10 s timeouts, that is up to about 120 s, the whole grace.

m5. news_live.py:1802-1805: if the holder's name cannot be written into the lock file (full disk), the error raises
out of `run()` and the engine does not start, even though the name is only for display. Wrap the write.

m6. news_live.py:99-104 and 1786: `_set_pdeathsig()` is not guarded. A ctypes failure ends a supervised start with a
traceback (exit 1) before the lock. Wrap it and rely on the check at the top of each step.

m7. news_live.py:93-96 and 1901-1902: `threading.Event.set()` is called from the signal handler. If the signal lands
while the main thread is inside `STOP.set()` (the parent-gone path), the handler blocks on the Event's own lock.
This can only happen right after the parent died, when PDEATHSIG kills the engine anyway. A plain module flag would
remove the case.

m8. news_live.py:1080 and 1104: when the bars cannot be read, the catch-up stamps `_covered[sym] = now`. That stamp
then shows as `held[sym].checked_at` and in `stops_checked_at`, although no price was seen. Readers have to go by
`blind` (the plan's `first_look_done` and its R6 rule already do). Say so where Task 12 reads the file. This was
already true before for `stops_checked_at`; `held[sym].checked_at` is new.

m9. journal.py:235-239 and .gitignore: the heartbeat is now written dozens of times per step through
`state/news_heartbeat.tmp`, which is not git-ignored. A `git add state/` at that instant, or a kill between the write
and the replace, leaves the temporary file to be committed. Its content is harmless, but the heartbeat was meant to
stay out of git. Add `state/*.tmp`.

m10. news_live.py:1830-1834, 1837-1838, 1855-1858: the start's sends for exit 5, R5d (exit 6) and the start's broken
chain are not guarded. `notify.send` can raise during quiet hours (its queue write). Then the start ends with a
traceback (exit 1) instead of its code (D5.2).

m11. news_live.py:1848-1851 against 1529: `_chain_checked` is not set after the start's chain check, so step 1 reads
every chain again (D7.2). This does not delay the first look.

m12. news_live.py:1845 and 1889: the boot beat and every beat up to `code_stamp` carry `code: null`. SKILL.md tells the
session to read `code.started` (D4.5). It is a short window, but a session that reads the file then gets a null.

m13. `aitrader/__main__.py:394-413`: `--cancel` drops the request first and writes the record second. If the record
fails, the request is already gone; the owner is told on stderr with exit 1, and the exception class is dropped
(D8c.3). Writing the record first (marked as an attempt) would keep "on record" true in every case. The tests do not
pin that `--said` is cleaned, nor that the drop really happened in the append-failure test (D8c.1, D8c.2).

m14. For the bare engine in step 1, exit 7 (merge in progress) is silent to the owner, unlike 4, 5 and 6. This matches
the spec: R3c belongs to the parent. Exit 7 now also refuses for a conflict in a file the engine never reads. SKILL.md
covers it (finish the pull, then start).

m15. Tests: the process tests use the spec's bounds (exit 3 within 2 s, which includes the interpreter's import of
pandas; gone within 1 s), and `test_priming_asks_its_feeds_in_parallel` asserts less than 1.6 s. These are tied to the
machine's speed. They pass here and are spec-mandated, but they can flake on a loaded host. The in-process classes
pin their clocks or turn the catch-up off, where the hour would matter.

## Checked and found sound

- Heartbeat writes and the engine's threads: every `_beat` runs on the main thread. Feed workers run only `_feed`, the
  priming poll's beats come from the calling thread (8d), and trial-check threads only ask. There is one writer of
  `news_heartbeat.json` and its `.tmp`. The `news-exit` CLI and the engine share only `news_exits.json`, under the
  directory flock, as before.
- Signals: the handler only sets STOP. PEP 475 retries an interrupted sleep, wait or read, so a call in flight and a
  journal write always complete; there is no torn write and no exception from the handler. Handlers are installed for
  the length of `run()` only and are restored, including in a refused start.
- Lock: a held lock is refused with exit 3, writes nothing and sends no alert. Another `OSError` runs unlocked, with
  E2 after the first look and `lock: false` in every beat. The "a+" mode keeps the holder's name. Opened files are not
  inherited by children (PEP 446), so an orphaned scorer cannot hold the lock.
- `adopt_previous`:
  - the blind clocks and the E1 pair are taken over only from today's file (New York);
  - `told_through` reads only today's rows;
  - a heartbeat from before this field, or a mark that is not in the journal, says nothing late, so the first start
    after landing re-sends nothing;
  - a damaged field costs only itself.
- told_through and the late line: within a process, the prefix of `_unsent` is never removed in the middle of a step,
  so `self._unsent[mine:]` in `step()` and `_look_at_stops` names exactly that step's or look's rows. The mark moves
  only when nothing is owed, so it never passes a row whose line nobody got. The design chooses "said twice" over
  "never said" (see M3).
- Order of `_run`: the start checks (5, 7, 6) come before the trader is built. Then adopt, boot, chains, first look,
  "stops", the lines that can wait (each followed by a beat), git, priming, the loop. No git call, feed or sendable
  line comes before the first look.
- Regressions: stops, sales, buys, the queue, the exit lever, the holds and the catch-up are unchanged except for
  beats and the look's own message. `_buys_blocked` gains "book_mismatch" first, which can only block. A missing or
  broken book now stops the engine with exit 6. Before, it was replaced by an empty book or crashed the start, so this
  is safer.
- 8b: a fraction becomes a whole score only for a held name at or under `sell_on_score_at_most`. Every buy, queue and
  second-check path requires the name not to be held, so a fraction cannot buy even with a misconfigured line.
  Infinity and NaN are skipped. The live-quote rule still holds for the sale.
- Leaks: no topic, token or session id in the diff or in any commit message. New log lines carry exception class names
  only. The `news_errors.jsonl` rows keep `str(e)[:300]` as before (D3.2), and that file is not tracked. No commit has
  a Co-Authored-By trailer, a "Generated with" line or a session link. The author identity is the same as on every
  live-branch commit.

## Deferred minors and parked findings (progress.md): which block this landing

None of them blocks this landing. I would close these before rollout step 2, when the parent starts killing and
restarting the engine routinely:
- SKILL.md has no E1 procedure (line 207). Same as M2 above.
- D8a.2: an owed line is re-sent every step, and with no channel configured it prints every step. Same as M4.
- D8a.3: an earlier hash that cannot be read freezes `told_through`. Same family as M3.
- D5.2: the R5d send is not guarded. Same as m10, together with the exit-5 and chain sends.

The rest are fine to leave or to fold into later tasks:
- D2.1-D2.7: ownerlines; only E1, E2 and R5d render today.
- D3.x: harness and test style; Ruling 16 ratified the quick poll.
- D4.2: `blind_told` as a string, which only a damaged file can produce.
- D4.3 and D4.4: style and error-row volume.
- D5.1: R5d's words are untrue for a damaged book with an empty journal, a state that practically cannot happen.
- D5.3-D5.11: no impact on this landing.
- D7.x: one extra chain read and `_run`'s length.
- D8a.4-D8a.12: beat placement, report accuracy, author identity.
- D8b.1-D8b.8: the forward measurement is restated by Ruling 25. The old scorer-call rows need `row.get("fractions",
  0)`.
- D8c.1-D8c.5: see m13.
- D8d.1-D8d.3.
- "No size limit against ntfy's 4,096 bytes": a failed oversized step message carries only its trade lines into the
  next step, so it recovers on its own.
- "A heartbeat that cannot be written no longer fails the step": acceptable, because the parent's hang rule is the
  net.
