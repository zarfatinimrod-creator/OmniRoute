### Task 14b: an honest {held}, a --clear-halt that cannot hang, refused CLI mixes, and 9b's sibling test

**Kind:** BUILD. **Authority:** the controller's Rulings 39, 41, 42, 48 and 49 in the ledger (`progress.md`), from Task 14's
plan-mandated finding and its deferred minors, Task 17's item 5 and a deferred minor of Task 16, and Ruling 38 (Task 9e). Not in the plan. It must be committed before
Task 20 lands; it changes no trading rule and touches no file the time machine loads.

**Files:** Modify `aitrader/supervise.py`, `aitrader/ownerlines.py`, `config.json` (one new key in the `supervisor`
block and its mention in that block's `_note`, nothing else), `tests/test_supervise.py`, `tests/test_ownerlines.py`,
`tests/test_news_supervised.py` (item 5 only). Read the code first: the line numbers below are from 236430fa or eacdefc5 and may
have moved; find each by its function name.

1. **`_held_now` tells "nothing held" from "cannot tell" (Ruling 39).** Today `_held_now(paths, child_pid)` returns
   `{}` both when the book holds no position and when the book cannot be read (missing, not JSON, no `positions` map,
   a position that is not a mapping). From now on it returns `None` when it has no beat of the child's own and the book
   cannot be read as a book, and `{}` only for a book that reads and holds nothing. A beat of the child's own is used
   as today. Do not fall back to a beat of another pid: it can be days old.
2. **`ownerlines.held_text(None, n)` returns `"לא ידוע"`.** `held_text({}, n)` still returns `"אין פוזיציות"`. Put the
   word where ownerlines keeps its other words (the module's own pattern), not as a literal inside the logic of
   supervise.py. Every caller of `held_text` and of `_held_now` keeps working with `None`: `status()`'s R5e block,
   `say()` inside `main` (the `if "held" in fields` branch), R2's fallback and the R5a/R5b lines. If any other caller
   would break on `None` (a `len()`, an iteration), make it handle `None` and say in the report where.
   Tests: (a) R5e from `status(..., watchdog=True)` on a halt 6 of an earlier New York day with no book file reads
   `"פתוח: לא ידוע"` and never `"אין פוזיציות"`; (b) the same with a book that is valid JSON but no book (a list);
   (c) a book that reads and holds nothing still gives `"אין פוזיציות"`; (d) in `test_ownerlines.py`, `held_text(None, 3)`
   and `held_text({}, 3)`.
3. **`--clear-halt`'s check cannot hang, and it checks the state it clears (Ruling 41, amended).** The check
   (`subprocess.run([*check, "--check"], ...)` in `clear_halt`) gets `timeout=` from a new config key
   `supervisor.clear_halt_check_timeout_seconds` = 120 (add it to the `supervisor` block, to the module's NUMBERS
   validation the same way the other seconds keys are validated, and name it in the block's `_note` in one short
   clause). A `subprocess.TimeoutExpired` prints one line naming the timeout in seconds and returns 1: the halt stays.
   Then the state dir: today the check runs with `cwd=ROOT` and its own default state, whatever `--state-dir` says, so
   `--clear-halt --state-dir DIR` checks the live state and clears DIR's halt. Read how `news-live` chooses its state
   directory (an argument or an environment variable). If it has a way, pass DIR to the check that way. If it has none,
   `--clear-halt` with a `--state-dir` other than the default refuses before the check with one line and returns 1.
   Say in the report which one you built and why. Tests: a check stand-in that sleeps past a 1 s timeout (set in the
   test's config) gives 1 and the halt stays; the state-dir case as built.
4. **Conflicting command-line forms are refused (Ruling 41).** `--status`, `--clear-halt` and `--relayed` are one
   mutually exclusive argparse group; `--watchdog` without `--status` is refused with `ap.error` (exit 2). The run form
   (none of the three) is unchanged. Test: `main(["--status", "--clear-halt", ...])` and `main(["--watchdog", ...])`
   each raise `SystemExit` with code 2; `--status --watchdog` still works.
5. **9b's sibling test reads its own value (Ruling 38, Task 9e).** In `tests/test_news_supervised.py`,
   `test_a_line_no_channel_took_is_sent_again_at_most_once_every_unsent_resend_seconds` asserts
   `self.nt.n["unsent_resend_seconds"] == 120`, so a tuned config fails it. Set the value the test's times are read
   against in the test itself, the way `test_the_steps_say_the_late_line_again_at_most_once_every_unsent_resend_seconds`
   does (`self.cfg["news"]["unsent_resend_seconds"] = 120` with its comment, or the equivalent on `self.nt.n` if the
   engine object is already built), and drop the assertion on config.json's value. No production change for this item.

6. **R6 on an unknown stop stamp (Ruling 48).** In `main`'s watch (near `supervise.py:1001-1012` at eacdefc5),
   a held name whose stamp age is unknown (`None` from `_stamp_ages`) is today stale at once, and R6's `{s}` falls back
   to `time.time() - kid["started"]`, about 0 at the boot beat: an urgent line saying "0 שניות". From now on an unknown
   age counts from the child's start (the same clock the fallback already uses), so the name is stale only when that
   age is more than `stops_stale_seconds`, exactly like a stamped name, and `{s}` is that age. Change only this stale
   check; `_stamp_ages` and `up()`'s blind_s (Ruling 36 (g)) keep their meaning. R6b's `{s}` follows from R6's as today.
   If an existing test asserts R6 at the boot beat with no stamp, change that assertion to the new behaviour and name it
   in the report. Test: no stamp anywhere (no `checked_at`, no `stops_checked_at`), one held name, market open, fresh
   beats: no `stale_stops` row and no R6 before `stops_stale_seconds` of the child's life (set it small in the test's
   config), then R6 with `{s}` >= that value.
7. **A machine pause is not a hang (Ruling 49).** When the wall-clock gap between two of the parent's own loop ticks
   is more than `hang_seconds`, the parent was paused together with its child. Measure the gap on the same clock the
   beat ages are read on (read how `main` computes `view["age_s"]`; its docstring says ages never read the injected
   `clock`), so that the gap and the beat age agree.
   It then (a) writes one row `pause` with the pause's start (`t` of the tick before), its seconds and the child's pid;
   (b) does not judge the child's beat as a hang (neither the kill nor R2 with the switch off) until `hang_seconds`
   have passed since the resume tick; a child with no beat at all keeps its `start_grace_seconds` rule; (c) when the
   pause holds `outage_report_seconds` or more of market-open seconds (`open_seconds`, the calendar the parent already
   has), sends R4 for it with `time` = the pause's start and `time2` = the resume, built by the same code `gap_line`
   uses (reuse it; do not write a second R4 builder), with its alert row's `m` as today. No new config key: the
   numbers are `hang_seconds` and `outage_report_seconds`. Tests: a real pause, made by sending SIGSTOP to the parent and to
   its child's process group (the child may run in its own group), then SIGCONT to both after a measured wait, with `hang_seconds` and
   `outage_report_seconds` set to a few seconds in the test's config and the market open in the test's calendar, the
   way the existing process tests set them: a pause of hang_seconds + 2 s with a healthy child gives one `pause` row,
   no `hang` row, no R2 and one R4; a pause shorter than hang_seconds gives none of these; a child that is SIGSTOPped
   alone (the parent keeps ticking) is still judged a hang as today. Signal only the pids and the group your own test
   started. Say in the report how long each test takes.

Not in this task (Ruling 42): the `detail` field of `news_errors.jsonl` rows and the cycle error print keep their
exception text. It is the engine's established error record (about ten sites and their tests), and notify, the only
code that holds the ntfy URL, already turns every request failure into its class (`notify.py`, the two
`except requests.RequestException` lines).

- [ ] Write the tests of items 2-7; run them: they fail (RED) for the reason each item names.
- [ ] Implement items 1-7.
- [ ] Run `tests/test_supervise.py`, `tests/test_ownerlines.py` and `tests/test_news_supervised.py` 3 times in a row,
  then the whole suite, every python command through the safe wrapper: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/supervise.py ai-trader/aitrader/ownerlines.py ai-trader/config.json ai-trader/tests/test_supervise.py ai-trader/tests/test_ownerlines.py ai-trader/tests/test_news_supervised.py`;
  message `fix(ai-trader): supervise says "unknown" when the book cannot be read, --clear-halt cannot hang and checks the state it clears, conflicting forms are refused, an unknown stop stamp and a machine pause raise no false alarm`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json
changes only the new key and its `_note` clause (show a key-by-key diff of the parsed JSON). It touches no file the
time machine loads.
