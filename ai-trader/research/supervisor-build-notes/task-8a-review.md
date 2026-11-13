# Task 8a review: four follow-ups from the reviews of Tasks 4-7

Reviewed: `3366396f..11e7e693` in the gate clone, one commit. I read it from the review package
`review-task-8a.diff` (one pass). I made focused reads outside the diff, one for each named risk (listed under "Checks run").

### Spec Compliance

Not compliant. One requirement is missing:

- `ai-trader/aitrader/news_live.py:1084-1091` (`_catchup_unread`) and `:1093-1110` (`_earlier_days_unread`): both
  send an urgent owner alert from inside a stop look (called only from `catch_up_stops`, lines 1036, 1056, 1080), and
  neither send is followed by a beat. Brief item 1 is titled "A beat after every send of a stop look" and its rule is
  "a `_beat("stops")` follows each owner alert that a stop look sends". The commit message says "a beat after every
  send of a look", so the message is wrong. The implementer built only to the list in brackets (concern 1 of the
  report).

The rest is as briefed:
- Item 1: the blind alert and the price-back line (`news_live.py:1176`, `:1190`), the catch-up alert (`:1075`), and the
  look's own message (`:1158-1159`; when a channel took it, `_mark_told` already writes the beat) are each followed by
  a beat.
- Item 2: the closing condition at `:1121-1122` and `:1145-1150`.
- Item 3: `step()` at `:1471-1497`.
- Item 4: `_run` at `:1842`, `:1858`, `:1860`, `:1862`, and the priming poll at `:729-735`. Task 7's order is unchanged
  and nothing new stands before the first look.
- All six brief tests exist under their names with the brief's assertions (`tests/test_news_supervised.py:1166-1277`).
  Two more tests cover brief requirements (`:1220`, `:1279`).
- Only the two listed files changed.
- The commit message matches the brief and carries no trailer or attribution line.
- The one edited expectation (`:292-294`) is in an extra test of Task 4, not one of Task 4's brief tests. Item 2 makes
  that test's first look end with a closing beat. The edit is reported.

Cannot verify from this diff:
- That the brief tests of Tasks 4, 6 and 7 pass unchanged, including the three-batch test reading "quotes", "score",
  "score". The diff touches none of them, so this rests on the reported suite run.
- The real seconds of any stretch. Beats are counted, not timed, and the bounds below depend on live Yahoo and ntfy.
- That the line `_trade_line(row)` rebuilds from a journal row matches the line `_log_trade` built from the fill. The
  row is `{**f, "logged_at": ...}`, so it should.

### Strengths

- Every new beat stands after a send. None stands between a quote and the sale it leads to, or between a sale and its
  own save. Checked in `check_stops`: the `_stop_sight` calls are in the tail (`:965-978`), after every sale
  (`_log_trade` saves the book) and after the exits save.
- Item 3 keeps the `_mark_told` contract (`:1439-1447`). `told_through` moves only when `_unsent` is empty.
  - `earlier` is a snapshot taken before the step.
  - Rows adopted from the run before (`_late`) are left out of it.
  - `mine` still indexes correctly after a look's `_mark_told` rebuilds `_unsent`. I traced three cases: the look took
    its line; the look failed and the closing message took it; the journal could not be read.
- E1's beat now follows the send whether a channel took it or not. `_run`'s docstring gained the two lines that say so.
- The tests are hour-independent: fixed clocks, `_quote_is_live` toggled per look, and the "23:59" start of the 11:10
  ruling. Every stand-in that a test assigns directly (`notify.send`, `live_price`, `bars_since`) is restored by
  `_Engine.tearDown`. No test reaches the network, the model or the phone.
- The strictly rising counters detect a missing beat. RED shows the expected failures, for example
  `[12, 12, ...] != [12]`. The implementer planted 19 defects and all were caught. The 5 ms feed stand-in is what
  catches parallel priming.
- The report states its readings and concerns openly, and its table places each new beat against sales and saves.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

1. **`ai-trader/aitrader/news_live.py:1089` and `:1108`: no beat after the catch-up's "could not be read" and
   "earlier day not looked back at" alerts (spec: missing requirement).**
   - What is wrong: two once-per-name urgent sends of a stop look have no `_beat("stops")` after them.
   - Why it matters: this is the brief's own rule ("each owner alert that a stop look sends"). The implementer
     estimates the longest stretch it leaves at about 126 s with two channels: one name's unread alert, then the next
     name's earlier-day alert, then that name's bar read. That fits under `hang_seconds` (180) only while the defaults
     hold. A start in the morning after a lost afternoon with Yahoo bars down is exactly when these sends happen.
   - Fix:
     - Add `self._beat("stops")` after each of the two `notify.send` calls.
     - In `test_a_look_that_stamped_a_held_name_ends_with_a_beat_so_the_file_has_the_stamp_at_once`, change the
       `look(0, False)` expectation from 3 beats to 4. That test is controller-ruled, so ask for the ruling, as was
       done for the other expectation edit.
     - Add one test: each of the two sends is followed by a beat.

2. **`ai-trader/aitrader/news_live.py:729-735`: the priming poll now asks its feeds one at a time (plan_mandated: the
   brief's test forces it).**
   - What is wrong: priming now asks its 93 feeds one at a time (`ThreadPoolExecutor(max_workers=1 if prime else 8)`).
     The brief's prose asks only for a beat after each feed call. Its test, `seen == sorted(set(seen))` over 30 feed
     calls, can pass only when no two feed calls overlap.
   - When it runs: `news_seen.json` is git-ignored (`.gitignore:5`), `news_book.json` is tracked, and `run()` defaults
     to `prime=True` (`:1735`). So every start on a new or rebuilt VM primes while names are held, after the first
     look and before the first step (Review Focus 1).
   - Cost:
     - Typical: 93 feeds at 0.2-0.5 s each, about 20-45 s, against roughly 3-6 s with eight threads. `poll_seconds`
       is 20.
     - With Yahoo at its 10 s feed timeout (`:132`): up to about 15 min, against about 2 min with eight threads.
   - Why it matters: during priming no stop look runs, and no planned stop is seen. A planned stop is checked only at
     the top of a round or in the wait, and a SIGTERM during priming waits it out. That delays stop looks beyond what
     the brief's prose says.
   - Fix, by controller ruling:
     - (a) Accept it as a known ceiling, with a `ponytail:` comment.
     - (b) Or keep eight threads and write the beat from the calling thread as each feed completes
       (`as_completed`). The assertion then becomes "a beat follows each feed call": feed calls ≤ beats in the
       priming window, and a beat after the last feed. The longest stretch without a beat stays one call's time.

#### Minor (Nice to Have)

- `ai-trader/aitrader/news_live.py:734`: a one-worker `ThreadPoolExecutor` is a loop in disguise. For `prime`,
  `[fed(s) for s in self.universe]` is simpler and keeps `_beat` on the main thread. This is moot if Important 2
  changes the design.
- `ai-trader/aitrader/news_live.py:1490` (`step`): while a line stays owed, every step sends it again. A channel that
  times out adds up to 15 s per channel to every step (`poll_seconds` 20). With no channel configured, `notify.send`
  prints `ALERT:` and the line at every step. The brief mandates this ("every trade line ... no channel has taken
  yet"). It is listed for the controller (the report's concern 2).
- `ai-trader/aitrader/news_live.py:1485`:
  - What happens: an earlier hash that is not a readable journal row (for example a torn row) is dropped from the
    message with no error row. It stays in `_unsent` for the rest of the process.
  - Effect: `told_through` is frozen and the journal is re-read at every step.
  - Fix: a `_note_error` once.
- `ai-trader/aitrader/news_live.py:1486`: only trade lines are carried. If a first-look message went untaken, its
  loss-pause notice ("נמכר בהפסד: ... אין קניות חדשות") and any "exit request ... dropped" line reach only the engine
  log. This is within the brief's wording, but the owner may not learn that buys are paused.
- `ai-trader/aitrader/news_live.py:1075`, `:1176`, `:1190`: the brief says "no beat is added before any sale or save".
  - The catch-up beat stands before the "sell"-mode re-check sale and before `_look_at_stops`'s `save(seen=False)`.
    The `_stop_sight` beats also stand before that save.
  - This is inherent in the brief's own list: each beat follows a send that already preceded those, and adds about
    0.5 ms.
  - The report's table leaves out the `_stop_sight` beats' place relative to the look's save.
- `ai-trader/tests/test_news_supervised.py`: no test covers the unreadable-journal path of the carried lines (`where`
  "step_alert"): the earlier rows stay owed and the step's own lines still go out.
- Report accuracy: the "whole suite, on the committed files" run and the three-in-a-row runs finished before the commit.
  - `suite-final.txt` is stamped 17:17:28 and the commit 17:17:46.
  - The output reads "engine started on commit 3366396f + uncommitted changes".
  - So the working tree was tested, not the commit. Its content is very likely the same.
- The commit's author is "Claude", the clone's configured identity, as on earlier commits. The constraint bans
  attribution lines, and there are none. Whether the author name is acceptable is the controller's call.
- The reported suite output contains older tests' prints (`[news] engine started ...`,
  `[journal] skipped unreadable line ...`). They were there before this task; it added none.

### Checks run

- The review package command: exit 0, 1 commit, 35042 bytes.
- Risk "a new beat stands before a sale": read `check_stops` (`news_live.py:902-982`). The `_stop_sight` calls are in
  the tail, after every sale and the exits save.
- Risk "`told_through` passes a carried row": read `_mark_told` and `say_late` (`:1439-1463`). `told_through` moves
  only when `_unsent` is empty, and `_late` is cleared only on delivery.
- Risk "the blind set in `_look_at_stops` differs from the file's": read `_beat` (`:1602-1644`). The file's `blind` is
  `_blind` ∩ held, the same set as `blind()`. `_beat` never raises.
- Risk "the catch-up has more sends than were given beats": read `catch_up_stops`, `_catchup_unread` and
  `_earlier_days_unread` (`:1003-1110`). `bars_since` never raises (`:429-445`). `notify.send` catches
  `RequestException` and uses `timeout=15` per channel (`notify.py:28-58`).
- Risk "test stand-ins leak to other tests": read `_Engine.setUp` and `tearDown` (`tests/test_news_guards.py:33-59`).
  `live_price`, `notify.send` and `bars_since` are saved and restored.
- Risk "serial priming affects live starts": checked the universe size in `config.json` (93) and `poll_seconds` (20),
  `git ls-files state` (no `news_seen.json`), `.gitignore:5`, and `run(prime=True)` (`:1735`).
- Risk "the time machine loads `news_live`": `grep -rln news_live aitrader/` finds only `__main__.py`.
- Risk "the edited expectation is a brief test": no task brief names
  `test_each_look_beats_after_each_quote...`.

### Assessment

Task quality: **Needs fixes.** Items 2-4 and the tests are correct and careful, but item 1 misses the beats after two
sends of a stop look that the brief's rule covers. The serial priming the brief's test forces delays stop looks on
every fresh-VM start, so the controller needs to rule on it before this lands.
