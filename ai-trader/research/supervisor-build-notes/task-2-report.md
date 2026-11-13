# Task 2 report - the owner's lines in one table

**Status: DONE.** Second dispatch. One commit on `supervisor-build` in the gate clone:

- `c6bec0f7bffae6d3880ae4a9487a4ea64830a2c3` - `feat(ai-trader): one table for every line the supervisor work sends the owner`
- base `e3be944719f0727ba9199bb9185bca1ef930eb10`; 4 files added, 231 lines; `git status --short` prints nothing.
- No trailer, no body, no attribution line in the message.

The first dispatch's parked files were the starting point. I copied them into the clone, read every line against the
brief and against the table of spec section 8 with a check of my own (not the first dispatch's scripts), applied the
three rulings of 2026-11-11 10:50 UTC, and fixed two weaknesses that my own review found in the tests (see
"Self-review").

## What is in the commit

- `ai-trader/tests/helpers/__init__.py` - empty.
- `ai-trader/tests/helpers/no_phone.py` - `PHONE_VARS` (the three phone variables), popped from `os.environ` when the
  module is imported; `clean_env(**extra)` = `PATH` and `HOME` of this process, `PYTHONPATH=<ai-trader>`,
  `NO_PROXY=127.0.0.1`, then `extra`. It is built from nothing, so no `AITRADER_*` and no proxy variable comes through.
- `ai-trader/aitrader/ownerlines.py` - standard library only (`datetime`, `zoneinfo`). `LINES` (38 ids -> priority and
  template), `PARTS` (`R1.falls`, `R1.sold`, `R1.code`, `R2.off`, `R4.cold`), `WORDS` (`cause`, `R4b.why`, `R5e.why`,
  `W0.what`, `E1.side`, the brief's values), `FREE`, and `held_text`, `sold_text`, `hhmm`, `priority`, `render` with
  the brief's signatures (checked with `inspect.signature`).
- `ai-trader/tests/test_ownerlines.py` - 6 tests: the brief's five under their names, and the sixth that the ruling
  keeps. It begins with `from helpers import no_phone  # noqa: F401`.

## The table against the spec (my own check)

`<SCRATCH>/t2b/check_table.py` (scratch, not in the
commit) reads the 38 rows of spec section 8 and the `WORDS` line of the brief and compares them with the imported
module: every template character for character (with `{HH:MM}` / `{HH:MM:SS}` -> `{time}`, `{time2}` and `{DD.MM}` ->
`{date}`), every priority (DM1 and DM2: "high" in the table, "urgent" from `priority(..., held=True)`), the five
parts (`R2.off` rebuilt from R2's head and the spec's "switch off" text; `R4.cold` with `{cold_time}`), the words of
`cause`, `R4b.why`, `R5e.why` and `W0.what` against the spec, all of `WORDS` against the brief, and that no text holds
a character that is not printable ASCII or a Hebrew letter.

```
rows 38 lines 38 parts 5 word lists 5 problems 0
```

The check is not empty: with four differences planted in a copy (a doubled space in W2b, R6b's priority, one word of
`cause`, a space in `R4.cold`) it printed `problems 5` and named each.

## TDD evidence

Every command ran from `<clone>/ai-trader` as
`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests -p 'test_ownerlines.py' -v`.
The saved outputs are in `<SCRATCH>/t2b/out/`.

**RED 1 - the test file alone** (the failure the brief expects: the helper package does not exist yet):
```
  File ".../ai-trader/tests/test_ownerlines.py", line 3, in <module>
    from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)
ModuleNotFoundError: No module named 'helpers'
Ran 1 test in 0.000s
FAILED (errors=1)
```

**RED 2 - with the helper, without the table** (expected: the module under test does not exist yet):
```
ImportError: cannot import name 'ownerlines' from 'aitrader' (.../ai-trader/aitrader/__init__.py)
Ran 1 test in 0.000s
FAILED (errors=1)
```

**RED 3 - the parked table, the test exactly as the brief wrote it (`max_bytes=100`), shown once.** Expected: the line
of that call is 87 bytes, under 100, so nothing is refused. This is the plan defect the controller ruled on.
```
test_a_template_over_the_limit_is_refused_and_the_import_leaves_no_phone_variable ... FAIL
(the other five) ... ok
  File ".../tests/test_ownerlines.py", line 52, in test_a_template_over_the_limit_is_refused_and_the_import_leaves_no_phone_variable
    with self.assertRaises(ValueError):
AssertionError: ValueError not raised
Ran 6 tests in 0.002s
FAILED (failures=1)
```

**RED 4 - the tests with the rulings (`max_bytes=80`, `endswith("ועוד 2.")`), the table still as parked.** Expected:
the over-limit test now passes, and `sold_text` fails because its tail has no full stop yet.
```
test_a_template_over_the_limit_is_refused_and_the_import_leaves_no_phone_variable ... ok
test_held_text_and_sold_text ... FAIL
AssertionError: Tuples differ: ('', 6, False) != ('', 6, True)
Ran 6 tests in 0.002s
FAILED (failures=1)
```

**GREEN - after the tail of `sold_text` became `" ועוד {n}."`** (the file as committed; run 3 times in a row, 6 ok each
time, nothing on stdout):
```
test_a_template_over_the_limit_is_refused_and_the_import_leaves_no_phone_variable ... ok
test_every_line_with_20_held_names_and_700_letter_free_text_fits_and_ends_with_paper_money ... ok
test_held_text_and_sold_text ... ok
test_r1_and_the_two_forms_read_as_the_spec_writes_them ... ok
test_the_owners_clock_the_dead_man_priority_and_the_three_key_errors ... ok
test_the_table_has_exactly_the_ids_of_spec_section_8 ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
```

Measured on the committed module:
- The W4 call of the over-limit test: 55 characters, 87 UTF-8 bytes. `max_bytes` 100 and 87 return the line; 86 and 80
  raise `ValueError: owner line W4 is 87 bytes, over the limit of 80`.
- The 20-names test: the held text is 166 bytes (six names and "ועוד 14"); the largest lines are R6 743 bytes, S2 554,
  DM1 542, against 1,200. With 200 four-byte characters in every free field the largest is R6 at 1,143.
- R1 with every part, 8 sales and 2 names in the line reads:
  `... פתוח: MU (סטופ 708.97). נמכר בהפעלה: S0 בסטופ 48.50, במחיר 48.00. נמכר בהפעלה: S1 בסטופ 48.50, במחיר 48.00. ועוד 6. נטען קוד חדש (abc1234). הפעלה מחדש מספר 2 היום. שעון ישראל. כסף נייר`
- The helper, with stand-in values set before the import: the three phone variables are gone after it;
  `clean_env()` has exactly `HOME, NO_PROXY, PATH, PYTHONPATH`; with `https_proxy`, `HTTPS_PROXY` and `no_proxy` set
  in the parent none comes through; a child started with `clean_env()` from another folder imports
  `aitrader.ownerlines`.

**Mutation check** (`.../scratchpad/t2b/mutate.py`, on a scratch copy, never in the clone): 19 defects planted one at
a time in `ownerlines.py` (a form the line does not have falls back to the plain line, free fields not cut, the size
not checked, DM1 never urgent, every held line urgent, the clock in UTC, seconds always, held names not capped, no
"ועוד", sold names not capped, the sold tail without its full stop, the cold part at the end, `off` ignored, a
missing id, a line without "כסף נייר", prices with one decimal, and others). At the commit: `mutants 19 survived 0`.

## Whole suite

`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT python3 -m unittest discover -s tests`
from `<clone>/ai-trader`, once, before the commit, on the files as committed. Wall time 60 s. Last three lines:
```
Ran 552 tests in 60.210s

OK
```
552 = 546 + 6. The new tests print nothing; the `[news] ...` and `[journal] ...` lines in the output come from earlier
engine tests. After the run `git status --short` showed only the three new paths: nothing under `state/`, `logs/`,
`reports/` or `research/`.

## Files changed

All new, all in the one commit; no existing file is touched:
- `ai-trader/aitrader/ownerlines.py` (141 lines)
- `ai-trader/tests/helpers/__init__.py` (empty)
- `ai-trader/tests/helpers/no_phone.py` (19 lines)
- `ai-trader/tests/test_ownerlines.py` (71 lines)

Against the parked files: `no_phone.py` and `__init__.py` are unchanged; `ownerlines.py` differs in `sold_text` only
(the tail and its docstring); `test_ownerlines.py` differs as listed under "Departures". The parked copy under
`.../scratchpad/t2/parked/` is now stale.

## Self-review (the diff `e3be9447..HEAD`, read again after the commit)

Found and fixed before the commit:
1. **The sixth test's "no such form" case could not fail for the reason it named.** The parked case was
   `render("R1", off=True)` with no fields: it raises `KeyError` for the missing `{time}` even if `off` were ignored.
   Now each form case gives every field the line needs (`R6b` with `s=5`, once with `off=True`, once with
   `cold_time="07:42"`), after an assertion that `R6b` with `s=5` renders. The mutants "only off falls back" and
   "only cold_time falls back" are both caught now.
2. **Nothing checked that `held_text` caps the names.** The brief's assertion is `endswith("ועוד 14")`, and the
   20-names test passes with all 20 names listed (R6 is then 1,107 bytes). The mutant "held names are not capped" survived.
   One assertion added to `test_held_text_and_sold_text`:
   `held_text({"A": 1.0, "B": 2.5, "C": 3.0}, 2) == "A (סטופ 1.00), B (סטופ 2.50) ועוד 1"`. It passed at once (the cap
   was already there); its RED is the surviving mutant, which is caught now.
3. The sixth test's name said "two key errors" and checks three; it is now
   `test_the_owners_clock_the_dead_man_priority_and_the_three_key_errors`.

Checked and left as it is:
- Completeness, line by line against the brief: every name of "Produces" exists with its signature; `LINES` has
  exactly the 38 ids; times are `{time}`, `{time2}`, `{date}`, and `{cold_time}` in `R4.cold`.
- `render`: an unknown id, a form the line does not have and a missing field are `KeyError`; a field the template
  does not name is ignored (the brief's R2 test needs that); a value is never parsed as a template (a note full of
  braces stays text); the `ValueError` text carries the id and two numbers, never the line.
- No number sits in the logic: the limits arrive as arguments. Nothing reads the environment, a file or the network.
  Importing `aitrader.ownerlines` pulls in no other `aitrader` module.
- No tab, no trailing blank. The three lines of the test file over 130 characters (140, 156, 175) are the brief's
  own, verbatim; the longest line I wrote is 128 (`news_live.py` goes to 135, `test_news_guards.py` to 164).
- The clone has no commit hook (`core.hooksPath` is not set), so nothing was skipped.

## Departures from the brief

1. **`max_bytes=100` -> `max_bytes=80`** in the one W4 call (ruling). I added the comment `# the line is 87 bytes`.
2. **`sold_text`'s tail is `" ועוד {n}."`** and the assertion is `endswith("ועוד 2.")` (ruling). The brief's interface
   comment and its test say it without the full stop.
3. **Six tests, not five; the suite is 552** (ruling: the sixth test stays). Against the first dispatch's version of
   it: renamed, and its form cases rewritten (self-review 1).
4. **One assertion added to a test of the brief**, `test_held_text_and_sold_text` (self-review 2). Nothing of the
   brief's was removed or weakened.
5. **Prices print with two decimals** in `held_text` and `sold_text` (ruling).
6. **`off=True` or `cold_time` on a line that has no such form is a `KeyError`** (ruling); the brief names `KeyError`
   only for an unknown id and a missing field.
7. The brief's step "Run the file again: 5 tests" reads 6.

## Concerns

None that blocks. Four things the next tasks should know:
1. `hhmm` expects an aware datetime. Python reads a naive one as the machine's local time, so a caller that passes a
   naive UTC time gets the right clock only while the VM runs in UTC. The engine's times are aware.
2. A free text is cut to `free_chars` and nothing else: a line break inside a trader's note stays in the line. The
   brief asks for the cut only.
3. `clean_env(**extra)` puts `extra` last, as the brief says, so a caller can pass any variable, a phone variable
   included (a later task passes a stand-in topic to the stub this way). The helper cannot tell a stand-in from the
   real one; the tripwire of Task 3 is what guards that.
4. The commit's author name is the clone's configured git identity, the same as on every earlier commit of the
   branch. I changed no git setting. The message has no trailer.

## The first attempt's contradiction (kept for the record)

The first dispatch wrote the same four files and reported BLOCKED, with nothing committed. The brief's fifth test
calls `render("W4", max_bytes=100, free_chars=200, he="x", time="12:34", note="y")` inside `assertRaises(ValueError)`,
and the brief's contract for `render` raises `ValueError` only when the line is still over `max_bytes`. That call
renders `משגיח: "x" של 12:34 רצה ונכשלה: y. שעון ישראל. כסף נייר`: 55 characters, 87 UTF-8 bytes. The rendered line
(87), the template with its placeholders (96) and its fixed text alone (80) are all under 100, and the same file's
20-names test measures `len(line.encode())`, so no reading of the brief makes the assertion hold. W4 is one of only
three lines (with R6b and S1) that fit in 100 bytes with one-letter fields. The first report also noted that the
brief's tail of `sold_text` runs into R1's next sentence with no full stop. The controller ruled on both: `max_bytes=80`
in that call, and the tail with its own full stop. Both are in the commit; RED 3 above shows the original assertion
failing once.
