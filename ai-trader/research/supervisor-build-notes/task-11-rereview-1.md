# Task 11 re-review, fix round 1

Fix range 62fc1622..9d813d54 (one commit, `9d813d54 fix(ai-trader): the supervisor parent starts the engine on a weekday
the calendar does not cover`), gate clone `sup`. Package: `review-task-11-fix1.diff` (2 files, +20 -1).

### Finding Verdicts

- **F1: ADDRESSED.**
  - `ai-trader/aitrader/supervise.py:386` now reads
    `if session_hours(day, cal) is None and (day.weekday() >= 5 or day.year in cal.get("years", [])):`.
    `session_hours` (supervise.py:38-47) is unchanged, so the Foundations equality with `journal.session_hours` still holds.
  - Every case of the combined condition:
    - A weekend: closed_today.
    - A holiday of a listed year: closed_today.
    - A weekday of an unlisted year, holiday or not: the child path.
    - A calendar with no `years` key: the child path on every weekday.
  - The year clause tests the same thing as the engine's own check, `journal.calendar_covers`
    (journal.py:71-73: `year in set(years)`). The config years are ints (`[2026, 2027]`), so list membership and set
    membership agree.
  - On the child path the real engine's `start_checks` returns `(5, "calendar")` first (news_live.py:1757-1758). `_run`
    sends the urgent line and returns 5 whether or not it runs under a parent (news_live.py:1885-1891).
  - `restart_core` maps 5 to `(5, "halt")` with no restart. `main` then writes `halt {code 5, why HALT_WHY[5] = "calendar"}`
    (supervise.py:289, 431-432) and `sup_stop` "halt". That is spec 4.3's code-5 row. The silent skip from the first
    weekday of 2028 is gone.
- **The new test**
  (`tests/test_supervise.py:970-985`, `ParentLoop.test_a_weekday_of_a_year_the_calendar_does_not_list_starts_the_engine_and_halts_on_its_5`):
  - It derives the year from the config copy: `Parents.config` copies `config.json`'s calendar unchanged
    (test_supervise.py:768-776).
  - It covers both branches:
    - The weekend day gives rc 0 and no child.
    - The weekday gives rc 5, one `start` row in total, `sup_stop` `[("closed_today", 0), ("halt", 5)]`, and halt `(5, "calendar")`.
  - The weekend run uses an exit-5 child, so a mutant that starts a child on the weekend fails fast instead of hanging.
  - The report records that both mutants were killed: the old condition (`0 != 5`) and the condition without the
    weekend clause (`5 != 0`).

### New Breakage in the Fix Diff

None.

- `cal.get("years", [])` holding a non-list cannot raise here first. `session_hours` is evaluated before the `and` and
  already builds `set(cal.get("years", []))`, so this behaviour has not changed.
- The comment at supervise.py:384-385 states the behaviour correctly.

### Out-of-Scope Observations

- The parent decides from its `clock()`, but the engine's calendar check reads the real New York date
  (news_live.py:1757). The two disagree only when a drill or a test moves the parent's clock to another year. That was
  already true before this fix, and the design accepts it: the brief says only the parent's calendar questions read
  `clock()`.
- Spec text: neither spec 4.5 ("a day with no session") nor 4.3 says what a weekday of an uncovered year means. A
  one-line note in spec 4.5 that such a day is not closed_today, and goes to the engine's code 5, would stop the
  question from coming back.
- A `halt` "calendar" written on an uncovered weekday is kept across days (Task 10's "keeps the halt"). Clearing it once
  the calendar is extended belongs to `--status` and its action (Task 14), not to this task.

### Verdict

APPROVED. F1 is fixed at its root, at the one decision point in `main`. The engine's own start check is the single
source of the code-5 answer and its urgent line. The covering test exercises both the weekend and the weekday branch.

The fix report gives:
- the RED run;
- the two killed mutants;
- the command for the covering tests, run 3 times in a row with `-k ParentLoop -k RestartCore -k Foundations`, each `Ran 33 tests ... OK`;
- the whole suite, `Ran 738 tests ... OK` (737 + 1).

The counts agree with the diff: the earlier RestartCore + ParentLoop count of 20, plus this test, plus Foundations.
