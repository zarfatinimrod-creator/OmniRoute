# Task 5 report - start checks and the halt codes

**Status: DONE_WITH_CONCERNS.** One commit on `supervisor-build` in the gate clone, on top of `8ed84237`:

- `001493a6` (`001493a605f438ce804408d83094dec3645d7388`)
  `feat(ai-trader): the engine checks calendar, checkout and book before it starts, and leaves with a code that says why`
- 6 files, +492 -18. `git status --short` prints nothing. No trailer, no attribution line, nothing pushed, no git
  setting changed.

Everything the brief asks for is built and its seven tests pass as written. The concerns, in short (details at the
end): **one of my own scratch experiments reached the network and the model for five minutes** (a planted defect in
a scratch copy made the brief's `--check` test start the real engine loop; nothing of the owner's was touched, and the
test is now guarded); several readings where the brief leaves a choice; and the suite is 16 s longer.

## What is in the commit

**`aitrader/news_live.py`** (+136 -13)

- `tree_busy(start=None) -> bool`: from `start` (default `journal.STATE`, resolved) upward to the first `.git`: a
  directory, or a file that begins `gitdir:` (a worktree; the path is taken from the folder that holds the file). True
  when that directory holds `rebase-merge`, `rebase-apply` or `MERGE_HEAD`. File look-ups only, no git command. A
  `.git` file that is no gitdir file is not a `.git`: the walk goes on.
- `start_checks(cfg) -> (code, why, mismatch)`: it only reads. Order: calendar (5, "calendar"), `tree_busy()`
  (7, "tree_busy"), book (6, "book"), then the mismatch `(0, "", {"side", "symbol"})`, else `(0, "", None)`.
  The last readable row = the last line of `journal.read("news_trades.jsonl")` that is a JSON object.
- `_check() -> int` (`run(check=True)`): `start_checks(load_config())`, one printed line per check, then
  `journal.broken_chains(journal.NEWS_CHAINED)`; returns the first failing code (5, 7, 6, 4) or 0. No lock, no trader,
  no write, nothing sent.
- `run(until_ny="16:05", max_minutes=None, prime=True, check=False)`.
- `_run`: `start_checks` right after `load_config()`, before `NewsTrader(cfg)`. 5: the existing calendar alert (text
  unchanged), return 5. 7: prints `[news] start refused: tree_busy (exit 7)`, returns 7, sends nothing. 6: prints
  `[news] start refused: book (exit 6)`, sends `notify.send("AI Trader - תקלה", owner_line(cfg, "R5d"), cfg, "urgent")`,
  returns 6. `ChainBroken`: the existing print and alert, then the loop ends as before (save, drain, "stopped") and
  `_run` returns 4. Else 0. The calendar alert left its old place.
- On a mismatch: `nt.book_mismatch = {...}`; one `news_errors.jsonl` row
  `{at, error: "BookMismatch", detail, where: "book_mismatch"}`; E1 with the side's word from `ownerlines.WORDS`.
- `NewsTrader._buys_blocked`: answers `("book_mismatch", <the brief's sentence, verbatim>)` first, before the loss
  review. `adopt_previous`: keeps `mismatch_told` only when it is an object whose `day` is today (New York).
  `_beat`: writes it.
- The module's own list of "what holds a buy back" names the mismatch.

**`aitrader/__main__.py`**: `news-live --check`; `run(a.until, a.minutes, check=a.check)`; one usage line.

**`skills/trader/SKILL.md`**, section 3ב: the two lines, character for character (checked by a script against the
brief), each on one line, after the bullet about exit code 3.

**`tests/test_news_supervised.py`** (+265): `_Starts` (the `start()` helper of the brief; stdout kept in `self.out`),
`StartChecks` (the brief's five tests), `WhatAStartFinds` (thirteen more).

**`tests/test_supervise.py`** (+93): `GIT_ENV` (the brief's environment, verbatim) and `PullBesideRestarts` (the
brief's two tests).

**`tests/test_loss_protocol_pins.py`**: four expectations, `0` to `4` (the 10:35 ruling).

`tests/test_news_guards.py` is not in the commit: Task 3 already gave `OneEngine`'s stand-in its `**k`.

## TDD evidence

Every command ran from `<clone>/ai-trader` as
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests ...`.
Outputs are kept in `<SCRATCH>/t5/out/`.

**RED, `-p 'test_news_supervised.py' -k StartChecks -v`** (the brief's expected failure):

```
ERROR: test_a_buy_the_book_does_not_know_blocks_buys_says_e1_once_a_day_and_the_stops_go_on
AttributeError: module 'aitrader.news_live' has no attribute 'start_checks'
ERROR: test_a_calendar_that_does_not_cover_today_ends_the_engine_with_5
AttributeError: module 'aitrader.news_live' has no attribute 'start_checks'
ERROR: test_a_pull_in_progress_is_7_and_sends_nothing
AttributeError: module 'aitrader.news_live' has no attribute 'tree_busy'
ERROR: test_check_takes_no_lock_writes_nothing_and_returns_the_code
SystemExit: 2                                   (argparse: news-live has no --check)
ERROR: test_trades_with_no_readable_book_is_6_said_once_and_the_file_is_not_written_over
AttributeError: module 'aitrader.news_live' has no attribute 'start_checks'
Ran 5 tests in 0.022s
FAILED (errors=5)
```

**RED, `-p 'test_supervise.py' -k PullBesideRestarts -v`**. The brief predicts the same `AttributeError`; these two
tests never call `start_checks` in this process, so the fact arrives as the engine's exit code:

```
test_a_merge_left_open_refuses_the_start_with_7_and_the_book_is_untouched ... FAIL
test_a_restart_loop_beside_a_fetch_and_merge_leaves_book_and_chains_as_they_were ... ok
AssertionError: 0 != 7
Ran 2 tests in 17.388s
FAILED (failures=1)
```

The second test was green before the code existed and is green after: it guards what must not change (book and
chain, and no exit code but 0 or 7), not the new code. That it can fail is shown by planted defects
(`t5/out/mutants_final.txt`, `mutants_loop.txt`): "every tree is busy" (every start answers 7), a start that writes a
trade row, a start that empties the book, and a start that dies each fail it.

`-k WhatAStartFinds` before the code: `Ran 11 tests ... FAILED (failures=5, errors=6)` (eleven of today's thirteen;
the other two came later and have their RED in the mutation run).

**GREEN** (on the files as committed):

```
-k StartChecks -v           Ran 5 tests in 0.126s    OK        (all five "... ok")
-k PullBesideRestarts -v    Ran 2 tests in 17.909s   OK
```

The brief's "7 tests, OK". `tests/test_loss_protocol_pins.py`: `Ran 51 tests in 0.728s OK`.

**Three times in a row.** `tests/test_supervise.py` (the file that starts processes), whole:
`Ran 14 tests in 26.818s OK`, `28.340s OK`, `29.397s OK`. `tests/test_news_supervised.py`:
`Ran 39 tests in 0.996s OK`, `0.931s OK`, `0.902s OK`, five lines of output each: the new tests print nothing.

**At any hour** (the 11:10 ruling).
- In-process: the first dispatches' `shifted_inproc.py` (read before use; a copy is in `t5/`), which moves every
  clock the engine and the tests ask. `Ran 39 tests ... OK` eight times: 11:00, 17:00, 09:31, 23:58 and 03:00 New
  York today, Saturday 2026-11-14 12:00, and the early close of 2026-11-27 at 12:30 and 13:30. The real clock was
  between 08:45 and 09:25 New York, before the bell.
- Processes: `evening_procs.py 17:00 PullBesideRestarts` (Task 3's script, a copy in `t5/`): every engine process the
  two tests start answers the clock as 17:00 New York. `Ran 2 tests in 18.713s OK`,
  `engine processes started at a pretended 2026-11-11T17:00:00 New York: 12`, `their --until: ['23:59']`. Both tests
  start their engines through `Procs.start_engine`, which adds `--until 23:59`.

**Mutation check** (`t5/mutate.py`, on a scratch copy made with `git archive HEAD`, never in the clone). 54 defects
planted one at a time in `news_live.py` and `__main__.py`; each run is `test_news_supervised.py`,
`test_loss_protocol_pins.py`, `OneEngine`, and for 9 of them `PullBesideRestarts`. On the committed code:
`mutants 54 survivors: 0`; three more aimed at the loop test alone: `mutants 3 survivors: 0`. Examples: each of the three marks dropped; the walk started at the package; a gitdir file
not followed, or read from the working directory; the walk going on past a clean `.git`; the checks in another order
or after the trader is built; a book that does not parse taken as no book; a line that is no row taken as the last
row; any sale of a held name a mismatch; 5 not said or going on into the loop; 7 said; R5d or E1 as "high"; E1 at
every start, never, or marked as told when no channel took it; a pair of any day kept; a broken chain leaving 0;
`--check` starting the engine, skipping the chains, failing on a mismatch; `check` not handed on, or by position.
The first run (before the last two tests existed) left three survivors: one was a mutant that changed nothing (fixed),
two were real: nothing pinned that `adopt_previous` drops a pair of another day, or a `mismatch_told` that is no pair.
`test_only_a_pair_of_today_is_taken_over_from_the_heartbeat_before` now does.

## Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, on the files as committed. Wall time 88 s. Last three lines:

```
Ran 605 tests in 87.733s

OK
```

605 = 585 + 20. The `[news] ...` lines above the dashes are those of older tests. After the run: only the six paths
changed, nothing under `state/`, `logs/`, `reports/` or `research/`, no engine child and no `sleep 60` left.

## Files changed

`ai-trader/aitrader/news_live.py`, `ai-trader/aitrader/__main__.py`, `ai-trader/skills/trader/SKILL.md`,
`ai-trader/tests/test_news_supervised.py`, `ai-trader/tests/test_supervise.py`,
`ai-trader/tests/test_loss_protocol_pins.py` (by the ruling; not in the brief's `git add` line).

## Self-review (`git diff 8ed84237..HEAD`, against the brief line by line)

Found and fixed before the commit:

1. **The brief's `--check` test could start the real engine.** `cli.main(["news-live", "--check"])` runs on the real
   `config.json` with no stand-in for the feeds or the scorer. If `--check` ever stops being a check, that test
   becomes a live engine loop inside the test run: real Yahoo feeds, real `claude -p`, until 16:05 New York. It
   happened to me (see "Concerns" 1). The test now runs with `NewsTrader` replaced by a mock that fails when built, as
   `OneEngine` does; every assertion of the brief is unchanged. The same guard is in my own `--check` test.
2. Nothing pinned what `adopt_previous` keeps (mutation survivors, above): one test added.
3. Nothing pinned that the pair is in the file when no step follows the send (a start made after `--until`): the
   `_beat("boot")` right after a delivered E1 had no test. One added, with `until="00:00"`. Without that beat such a
   start would say E1 again every time.
4. My first count in one test was wrong (8 rows expected, 7 starts made): the test was wrong, not the code.
5. The `news_errors.jsonl` row has the field order of the other rows (`at, error, detail, where`).

Checked and left:

6. Every line of the brief's interface and of its seven bullets has its code and its test (the list under "What is
   in the commit"). The two SKILL lines and the block sentence equal the brief's text (script comparison).
7. Input that is not what the engine wrote (Review Focus 4) cannot raise in `start_checks`, and each case has a test
   row: a torn last line, a line that is JSON but no object (`7`, `[1]`), a `symbol` that is a list, a row with no
   side, a book that parses but is no book. A SELL row is a mismatch only when the name is really held: for a name
   the book does not hold, a row with no `qty` is never compared as `None == None`.
8. No trade, stop, buy, sale or hold changes beyond what the brief names: a start that is refused, buys held on a
   mismatch, and the return value after `ChainBroken`. The loop, `_step` and the three looks are untouched.
9. No number was added to the code. Every new send passes the priority positionally.
10. A refused start (5, 7, 6) builds no trader and changes no file in the state directory (asserted for all three:
    no heartbeat, no row). Under `run()` the lock file is still signed by the refused process, as Task 3 left it
    (the text is a hint only).
11. No test reaches the network, the model, the live state or the phone. `start()` runs the real `code_stamp` (two
    local git calls in the clone), as the brief defines it and as `Lock` already does.

## Departures from the brief

1. **`tests/test_loss_protocol_pins.py`: four expectation edits** (ruling of 10:35), lines 538, 595, 622, 674:
   `assertEqual(news_live.run("24:00", 1, prime=False), 0)` became `..., 4)`. Nothing else in the file.
2. **`tests/test_news_guards.py` is not in the commit** (ruling: Task 3 already did it).
3. **Check 3 is wider than "does not parse".** A file that parses but is no book (not an object, or `positions` not
   an object: `[]`, `{}`, `{"positions": []}`) is 6 too. `PaperBroker` takes `[]` and `{}` for "no state" and the
   engine would write a new book over the file; with `positions: []` every step would fail. `null` counts as no file.
   And by the brief's wording a book that does not parse is 6 also when the journal has no rows (spec 5.4 row 3 asks
   for rows in both cases).
4. **Where E1 goes out, and one more beat.** E1 is sent next to E2: after the boot beat, `code_stamp` and priming,
   right before the loop (Task 7 moves both). After a send that a channel took, `_beat("boot")` is written at once,
   so the heartbeat really carries the pair; the phase is "boot" a second time. E1 is guarded like E2: a line that
   cannot be built or sent leaves a row (`where` "mismatch_line") and the engine starts.
5. **Exit 5 prints no "start refused" line.** The brief names two printed lines (7 and 6); the plan counts "the two
   printed lines of a refused start". The calendar alert prints itself (`ALERT: ...`).
6. **Words the brief does not give**: the `--check` lines (`[news] check calendar: ok`,
   `[news] check tree_busy: failed (exit 7)`, `[news] check book_mismatch: the last row of news_trades.jsonl is a BUY
   of AAA that news_book.json does not show: ...`, `[news] check chains: failed (exit 4): <names>`); the row's
   `error` "BookMismatch" and its `detail`; the usage line and the help text.
7. **`start_checks(cfg)` does not read `cfg`**: the calendar check is `journal.calendar_covers` (which the brief's
   test replaces) and it reads `config.json` itself. The parameter stays, as the interface and the tests call it.
8. **`PullBesideRestarts`**: (a) the first working copy is made with `git init` + `git remote add` and a first push,
   not by cloning the empty bare repository (what an empty clone checks out differs between git versions); the
   second is a real `git clone`. (b) In the loop test the first clone gets one commit of its own first
   (`mine.txt`), as the trader session has its state commits: every merge is then a real merge that writes
   `MERGE_HEAD` for a moment. With the fast-forwards the brief's steps give, a 7 could never happen there. (c) The
   five rounds are spread over the ten starts: a semaphore lets one round go at every second start. A plain thread
   would finish all five during the first start. (d) Added assertions, none removed: the merge really stopped with
   `MERGE_HEAD`; the refused start printed its line, built no trader and sent nothing; the thread had no failure and
   its five rounds arrived; at least one start returned 0.
9. **20 tests, not 7.** `-k StartChecks` and `-k PullBesideRestarts` are the brief's seven. `WhatAStartFinds` holds
   thirteen: each row of the start table from real files, the order of the checks, what a refused start leaves
   alone, the gitdir file and the default start, the real chain check ending with 4, when E1 is said again (no
   channel, another day, another name), the pair with no step, the SELL side of E1, a line that cannot be built, the
   block before the loss review with its sentence on a refused buy, the `--check` lines and codes, the keyword.
10. **Two lines added inside the brief's own tests**: a cleanup of the three temporary directories in the pull test,
    and the "must not be built" guard of self-review 1.

## Concerns

1. **Incident in my own scratch work: about five minutes of real feeds and four real scorer calls.** In the first
   mutation run (scratch copy `t5/copy`, never the clone) the planted defect "`--check` takes the lock and starts"
   met the brief's test as it then was (self-review 1). From 14:01:01 to about 14:06 UTC the test process ran the
   real engine loop: the real `config.json`, 15 steps, real Yahoo RSS polls for the whole universe (1,358 headlines
   primed) and 4 real `claude -p --model claude-haiku-5-5` calls on 6 public headlines (about $0.03 by the CLI's own
   figures). The run's 300 s timeout killed it. What it could not touch: the state was the test's temporary
   directory, `notify.send` was the `_Engine` stand-in and the phone variables were not in the environment, no
   position was opened (the paper book in that directory stayed empty), the gate clone and its `state/` are
   unchanged (`git status --short` empty). This broke the rule that an experiment never reaches the network or the
   model. What I did: read the directory, kept it as evidence in `t5/incident/`, removed it from `/tmp`, confirmed no
   process was left, guarded the test, and gave the mutation script an environment that cannot leave the machine (no
   `claude` on `PATH`, every proxy a dead local port, a 120 s limit). The second and the final run had no hang.
   For the controller: the same guard may be worth a line in the notes for Tasks 7, 8 and 14, whose tests also call
   `cli.main` or `run`.
2. **Under the old watchdog prompts a halt can repeat its line.** They say "start again at once" when the engine
   ends. A start that answers 6 sends R5d each time, and 5 its calendar alert, until the session follows the two
   new SKILL lines. That is why the brief adds them; nothing in code limits it before Task 20.
3. **R5d says "and there are trades in the journal" also when there are none** (a book that cannot be read and an
   empty journal: departure 3). The action is right; one clause of the sentence is not. The spec-literal alternative
   is an engine that dies on the file with a traceback.
4. **In the loop test no start has been seen to answer 7.** Three extra runs printed every exit code: ten zeros each.
   The window in which `MERGE_HEAD` exists is a few milliseconds and a round ends before the engine it runs beside has
   finished importing. The 7 itself is pinned by the first test (a merge left open) and in-process. Drill g of
   Task 17 repeats this with 50 starts.
5. **The suite is about 16 s longer**: the loop test is ten engine starts of about 1.5 s each, as the brief's
   numbers give. `tests/test_supervise.py` alone went from 11-13 s (Task 4's report) to 27-29 s; the whole suite took
   88 s here.
6. **A SELL the book does not show can be sold a second time.** The engine "checks the stops of the book it has":
   a name whose sale is in the journal and not in the book is still held, and its stop still fires. The spec leaves
   the repair to the session, and `skills/trader/SKILL.md` has no procedure for E1 yet.
7. `tree_busy` resolves symbolic links: a state directory that is a link out of the checkout is looked for where
   its files really are. A `.git` file that exists and cannot be read raises (the start ends with a traceback, exit 1).
8. `--check` calls `journal._path`, which creates the state directory when it is missing. Nothing else is written.
9. A quiet-hours answer of `notify.send` (`["queued"]`) counts as "a channel took it". The stock book has no quiet
   hours.
10. The commit's author name is the clone's configured git identity, as on Tasks 2, 3 and 4.

Scratch files, none in the clone: `<SCRATCH>/t5/`
(`out/` with every output quoted above, `mutate.py`, `codes_seen.py`, `shifted_inproc.py`, `evening_procs.py`,
`evening_child.py`, `copy/` the scratch copy the mutants ran on, `incident/` what the run of concern 1 left).

## Fix round 1

**Status: DONE_WITH_CONCERNS.** One new commit on `supervisor-build`, on top of `001493a6`; no earlier commit was
amended or rewritten:

- `67096b47` (`67096b47eea6ba5271eedeb96cf55ed0b48dbe4a`)
  `fix(ai-trader): a step's message to the owner ends with the paper-money words`
- 2 files, +11 -1. `git status --short` prints nothing. No trailer, no attribution line, nothing pushed, no git
  setting changed, no subagent.

Start state checked first: HEAD `001493a605f438ce804408d83094dec3645d7388`, branch `supervisor-build`, tree clean.

### [F1] fixed - the reviewer's suggestion (a)

**The defect, seen before any change.** A real `step()` with one headline scored 9 while `book_mismatch` is set. The
message the `notify.send` stand-in got, whole:

```
AAA ציון 9: לא קונים. התיק לא תואם ליומן העסקאות. עד שסשן הסוחר מיישב את זה אין קניות חדשות. סטופים ומכירות עובדים כרגיל
תיק חדשות (נייר): $100,000 (+0.00%)
```

It ends with the book line, as the review says. The path is the one the review names: `_buys_blocked`
(`aitrader/news_live.py:719-721`) -> `_buy` (818-821) -> `_refuse` (771) -> the closing body of `step()`.

**The change.** `aitrader/news_live.py:1372-1373`, in `NewsTrader.step`: the closing body is now
`<the step's lines>` + `\nתיק חדשות (נייר): $<equity> (<pct>). כסף נייר`. The same message after the fix ends:

```
תיק חדשות (נייר): $100,000 (+0.00%). כסף נייר
```

**Why there.** The closing body is the one place where the lines of a step become a message to the owner. The
sentence itself stays word for word as the brief gives it (`_buys_blocked` is untouched): a suffix on the sentence
alone would still leave the book line after it, as the review notes. The form `. כסף נייר` is the one the plan gives
Task 6's late line (`... + ". כסף נייר"`).

**What else this one line changes - said openly, because it is wider than the mismatch sentence.** The same message
carries every line of a step: a BUY, a SELL, the `loss_review` and `hold` refusals, the other guards' refusals. All
of them now reach the owner in a message that ends with "כסף נייר". The line is older than this plan (base
`8ed84237`, news_live.py:1368). Spec 8's "the engine's existing lines stay as they are" lists the crossing alert,
the unread-stretch alert, the blind-quote alert and the chain and calendar alerts; the step's message is not in
that list, and the Global Constraint ("Every line the owner gets ends with "כסף נייר"") asks for exactly this. Not
changed: the title, the priority, when the message is sent, the event lines, what `_run` prints to stdout (the
events without the book line), any trading rule.

**Departed from the brief:** `step` is not in Task 5's list of functions (`tests/test_news_supervised.py` is in its
file list). No existing test was edited: no test pinned the old ending (grep for the book line, for `endswith`
and for whole-body comparisons of `self.sent` over `tests/`), and the suite confirms it.

**For the controller, about Task 6.** Its brief has `_look_at_stops` send its lines "the way the closing message is
sent today (`<lines + the book line>`)". That book line now ends with `. כסף נייר`; the look's own send must carry
the same ending, or a sale said at once would again reach the owner without it. One sentence in Task 6's brief (or
its review focus) would pin it. `say_late` already ends with the words.

### The covering test

`tests/test_news_supervised.py:549-556`, in `WhatAStartFinds`:
`test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money`. A real `step()` (the
module's `step` helper replaces the poll and the scorer; `_quote_is_live` answers True), one AAA headline scored 9,
`book_mismatch` set. It reads the message as the phone gets it (`self.sent`): exactly one message holds the
sentence, its priority is "high", no position was opened, and its last line begins `תיק חדשות (נייר): $` and ends
`%). כסף נייר`.

Every command ran from `<clone>/ai-trader`. Outputs are kept in
`<SCRATCH>/t5/out/` (`fix1_*.txt`).

**RED** - the final test on the code of `001493a6` (a scratch copy made with `git archive HEAD`, the new test file
copied over it; no `claude` on `PATH`, every proxy a dead local port, a 120 s limit; the copy is removed):

```
python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money -v

test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money ... FAIL
    self.assertTrue(last.startswith("תיק חדשות (נייר): $") and last.endswith("%). כסף נייר"), told[0][1])
AssertionError: False is not true : AAA ציון 9: לא קונים. התיק לא תואם ליומן העסקאות. עד שסשן הסוחר מיישב את זה אין קניות חדשות. סטופים ומכירות עובדים כרגיל
תיק חדשות (נייר): $100,000 (+0.00%)
Ran 1 test in 0.008s
FAILED (failures=1)
```

**GREEN** - the same command in the clone, on the files as committed:

```
env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests -p 'test_news_supervised.py' -k test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money -v

test_the_message_that_tells_the_owner_of_a_buy_refused_on_a_mismatch_ends_with_paper_money ... ok
Ran 1 test in 0.015s
OK
```

**The tests that cover the amended code** (each with the same `env -u ...` prefix):

- `python3 -m unittest discover -s tests -p 'test_news_supervised.py'`, three times in a row:
  `Ran 40 tests in 1.117s OK`, `1.089s OK`, `1.145s OK` (40 = 39 + 1).
- `python3 -m unittest discover -s tests -p 'test_supervise.py'` (the file that starts processes; its engine children
  run the changed `step()` and their messages are read back with `sent_rows()`), three times in a row:
  `Ran 14 tests in 30.011s OK`, `33.488s OK`, `35.403s OK`. No engine child was left afterwards.
- `python3 -m unittest discover -s tests -p 'test_news_guards.py' -k SaidWhateverHappens` (the tests of the step's
  message when the step fails): `Ran 11 tests in 0.355s OK`.
- At any hour (the 11:10 ruling; the new test starts no process and passes no `--until`):
  `python3 <scratch>/t5/shifted_inproc.py HH:MM <days>` (the first dispatch's script, read before use) runs the
  whole module with every clock moved. `Ran 40 tests ... OK` six times: 17:00, 11:00, 23:58 and 03:00 New York
  today, Saturday 2026-11-14 12:00 (no session) and the early close of 2026-11-27 at 13:30. The real clock was 09:35
  New York.

### Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, before the commit, on the files as committed. Wall time 104 s. Last three lines:

```
Ran 606 tests in 104.015s

OK
```

606 = 605 + 1. After the run only the two paths of the commit were changed: nothing under `state/`, `logs/`,
`reports/` or `research/`.

### Concerns of this round

1. **The fix is one line, and it changes the ending of every message a step sends**, not only of the mismatch
   refusal (above, "What else"). I read the Global Constraint as asking for that and the review's suggestion (a) as
   naming it. If the controller prefers ruling (b) of the review - the book line "תיק חדשות (נייר)" already meets
   the constraint - the commit is undone by one `git revert 67096b47`; the sentence and everything else of Task 5
   are untouched by it.
2. **Task 6 must carry the ending into the look's own send** (above, "For the controller").
3. The book line now reads `(נייר)` at its start and `כסף נייר` at its end: said twice in one line. I left the
   existing words as they are; shortening an owner line is the owner's or the controller's choice.
4. The commit's author name is the clone's configured git identity, as on every earlier commit of this branch.
5. Nothing else of the review was touched: its Minor points 1-8 are not on this round's list.
