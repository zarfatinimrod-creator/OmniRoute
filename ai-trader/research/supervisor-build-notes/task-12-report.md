# Task 12 report - what the parent sees: marks, `up`, a hang, stale stops

Gate clone `<SCRATCH>/clones/sup`, branch
`supervisor-build`. I ran the three checks before anything else:
- HEAD `9d813d54365e57fcacaaccc0214a8114c0b6ddbb`;
- branch `supervisor-build`;
- clean tree.

Final HEAD `c82097e14d6af8758b14f025bd3c062886ff02b0`.

One commit:
- `c82097e1` feat(ai-trader): the parent logs a mark a minute, measures every restart, kills a hung engine and notes stale
  stops.
- Paths: `ai-trader/aitrader/supervise.py` and `ai-trader/tests/test_supervise.py`, exactly the brief's.
- The message has no attribution line of any kind.
- After the commit `git status --short` printed nothing.

What I did not do:
- No `git stash` in any form.
- No push, fetch, merge, rebase, reset or branch command.
- `_tasks` was not touched.

Every python command ran through the `safe` wrapper, the mutation runner included.

## What I implemented

### `aitrader/supervise.py` (standard library only, no new import)

Module functions:
- `open_seconds(a, b, cal) -> float`. The seconds of [a, b] inside regular sessions. It runs `session_hours` on each New
  York date from a's to b's, so an early close ends at 13:00 and a weekend or holiday adds nothing. It returns 0 when b
  is not after a.
- `beat_view(hb, mtime, child_pid, now) -> dict`. The keys are exactly the brief's: `mine`, `age_s`, `stop_age_s`,
  `held`, `open`, `blind`, `phase`.
  - `mine`: the beat's `pid` is this child's. A child of `None` never matches, so a beat without a pid is not "mine"
    during a wait.
  - `age_s` = `now - mtime`.
  - For a beat that is not mine, the rest stays empty: `held` {}, `open` None, `blind` [], `phase` None,
    `stop_age_s` None.
  - `stop_age_s` (ruling P16) = (the beat's `at` - the oldest per-name stamp) + `age_s`.
  - The per-name stamp is `held[sym].checked_at`. When that is null, it is the beat's `stops_checked_at`: the look the
    run before left, which the engine repeats until it has looked itself (spec 5.5).
  - `stop_age_s` is None when nothing is held or when a held name's stamp cannot be read.
  - `held` = {sym: stop}.
- `first_look_done(hb, child_pid, started) -> bool`. The beat is this child's and past "boot". Every held name has a
  `checked_at` at or after `started`, or is in the beat's `blind` list.
- `mark_due(last_mark, now) -> bool`. True when there is no mark yet or `now` is in another clock minute.
- Private helpers:
  - `_when` reads an aware ISO time, else None.
  - `_held`.
  - `_looks` gives the per-name stamps with the fallback above.
  - `_stamp_ages` gives the per-name ages by P16.
  - `_read_beat` reads the heartbeat and its mtime from one open file (`os.fstat` on the same descriptor). The file is
    replaced whole, so the content and the mtime belong to the same beat.
- `NUMBERS` also holds `hang_seconds`, `start_grace_seconds`, `hang_term_grace_seconds` and `stops_stale_seconds`. A
  config without them gets the existing exit 2 instead of a crash mid-run.

`main`:
- `began = time.time()` at the top. It is the reference for the first child's `up.sold`.
- `emit(ev, now=None, **fields)`: a row can be given its time, so the `exit` row's `t` and the time kept for `down_s`
  are one value.
- `spawn()` first reads the heartbeat still on disk, which is the previous engine's last beat. It keeps that beat's
  oldest look as `last_look`, the start of `blind_s`. It also records the child's `started` (`time.time()`) and resets
  the per-child flags.
- `watch(child, ran_s)` keeps Task 11's two orders (signal, orphaned) and then calls `look`.

`look`, once per loop tick, also during a back-off:
- **mark.** At the first tick of a new clock minute (injected clock): {`hb`, `stop`, `n`, `open`, `blind`, `dm`: null,
  `left`: null}. `hb` and `n` are null without a beat of this child. Ages have one decimal.
- **up**, once per child, with this child's beat:
  - when the beat says the market is closed: at its first beat;
  - when the market is open: at its first beat for which `first_look_done`.
  - Fields:
    - `child`;
    - `down_from`: the `t` of this parent's last `exit` row, null at its first start;
    - `down_s`: from that exit to now, injected clock, two decimals; null at the first start;
    - `blind_s`;
    - `handover_s`: null;
    - `held`, `blind`;
    - `commit`, `dirty`, `code_changed`: null;
    - `sold`.
  - `blind_s` = `open_seconds(last_look, first look after)` when a name is held, else 0.
    - The first look after is the latest of the held names' first looks by this child. For a name in `blind`, or a name
      this child has not looked at, it is the beat's `at`.
    - When no previous beat was on disk (a cold start), `last_look` falls back to the up beat's `stops_checked_at`,
      the stamp the engine adopted.
  - `sold`: the SELL rows of `news_trades.jsonl` (plain JSON lines through `read_rows`) whose `logged_at` is at or after
    `int(t)`. `t` is the real time the previous child ended, or `began` (ruling P14: the whole second).
- **code.** At the first beat of this child that carries `code.commit`: {`child`, `commit`, `dirty`, `code_changed`}.
  - `code_changed` compares with the state's `last_commit`; it is false while there is none.
  - `last_commit` is updated, and the state file is saved then (guarded; the count is taken from the core's running
    counts).
- **stale_stops.**
  - Only on a fresh beat of this child (mine and `age_s` <= `hang_seconds`).
  - The stale names are those held, with the market open, whose P16 age is above `stops_stale_seconds`, or whose stamp
    is unknown.
  - "start" {`names`, `stop`} once per episode. "end" {the episode's names, the `stop` now} when no name is stale.
- **hang.**
  - The condition: this child's beat is older than `hang_seconds`, or it has no beat of its own after
    `start_grace_seconds`.
  - The row's `hb` is the beat's age, or the run time when the child never beat (P5: R2's "{s} seconds without a beat").
  - The row's `phase` is the beat's.
  - Switch on (`supervisor.hang_kill_enabled` is `True`): `look` returns "hang" and the core calls `stop(child, "hang")`.
  - Switch off: one row with `killed_with` "none" per hang, and a log line. The flag clears on the next fresh beat.
    Nothing is signalled.
- `stop(child, "hang")`:
  - SIGTERM to the child's process group, then `hang_term_grace_seconds`.
  - If the child has not ended: SIGKILL to the group, and a wait.
  - Then the row `hang` with `killed_with` "TERM" or "KILL", and a log line.
  - The group is signalled only while the child is not yet reaped, as in Task 11's planned stop.
  - The core then takes its crash path (counted), as built in Task 11.
- `core_emit` keeps the exit's injected time and real time for `down_s` and `sold`.
- Docstrings: the module ("So far (Tasks 10-12)") and `stop`.

### `tests/test_supervise.py`

- Class `Watching(Parents)` with the helper `stop_parent(p, settle=0.5)`: a few more loop ticks, then SIGTERM; returns
  the code.
- `kill_sleep` moved unchanged from `ParentLoop` up to `Parents`, so `Watching` can use it.
- One existing test edited; see "Departures", item 1.

## Tests

**The brief's 11.** Each has the brief's name and assertion. The stand-ins its comments describe are written in.

- `test_open_seconds_is_cut_to_the_session`
- `test_a_frozen_child_is_killed_and_replaced`
  - `hang_seconds` 2, switch on, the one run "5 beats, then hang".
  - SIGTERM goes as soon as the second child beats. It would hang too, but only 2.5 s later.
- `test_with_the_switch_off_a_hang_is_logged_once_and_nothing_is_signalled`
- `test_a_new_child_has_the_start_grace_for_its_first_beat`
  - `hang_seconds` 1, `start_grace_seconds` 5, `first_after_s` 3, then 20 beats.
  - Exit 0 with `--until 10:00`, so the parent ends by itself.
- `test_a_beat_left_by_another_pid_is_no_beat`
  - A fresh heartbeat with pid 1, and a child that never beats.
  - `hang_seconds` 60 and `start_grace_seconds` 1. Read as the child's own, that beat would stay fresh for the whole
    test and no hang would come.
- `test_stale_stops_start_once_and_end_once`
- `test_up_says_what_the_restart_cost`: the child is killed with SIGKILL after its first `up`.
- `test_up_is_written_while_a_held_name_is_blind`
- `test_the_real_engine_gets_a_code_row_after_its_up_row`
  - `engine_child.py` with session "open" and BBB held (`write_book`).
  - `--until 24:00` comes from `Parents.parent_argv` (P1, controller Ruling 16).
- `test_code_changed_compares_with_the_child_before`
- `test_a_mark_is_due_once_per_clock_minute`

**Tests added by ruling** (controller's additions: a ruling that changes behaviour and names no test gets one):
- `test_the_stop_age_grows_with_the_beats_own_age` (P16). Stamps 30 s and 100 s before `at`, the file written 50 s ago:
  `stop_age_s` 150. Another pid's beat is not mine and shows nothing held; nothing held gives `stop_age_s` None.
- `test_a_sale_in_the_second_the_parent_started_is_in_up_sold` (P14). Three rows are written just after a second turns:
  - a SELL logged in the parent's starting second;
  - a BUY in that second;
  - a SELL a second earlier.

  Only the first is in `up.sold`. Without the whole-second cut it is left out.

P1 names its test, which is in the list above. P5 says "no change" (the `hang` row keeps `hb`).

**Tests added in self-review:**
- `test_a_mark_carries_the_fields_of_spec_4_6`. The parent's clock starts at 10:00:59, so a second mark falls beside a
  beating child.
  - The first mark (no child yet) is all nulls with `blind` [].
  - The second has `n` 1, `open` true, `blind` [], `dm` and `left` null, and `hb` and `stop` under 1 s.
- `test_blind_s_runs_from_the_last_look_before_the_start_to_the_first_look_after`.
  - `open_seconds` is replaced by a recorder that returns 42.0, because the real one reads real stamps against the
    calendar and would depend on the hour.
  - Asserted: `up.blind_s` 42.0; "from" = the stamp of the heartbeat the engine before left (40 s old); "to" = the up
    beat's `at`, a whole second of this run, not the blind name's 3000-s-old stamp.

**Tests added from my mutation pass** (behaviour the brief states that no test above caught):
- `test_first_look_done_wants_this_childs_own_look_at_every_held_name`: the boot phase, another pid, an old stamp, an old
  stamp with the name blind, no beat.
- `test_with_the_market_closed_up_comes_at_the_first_beat`
- `test_a_hang_kill_reaches_the_childs_whole_group`
  - `GROUP_CHILD` never beats and has a `sleep 60` in its group; `max_restarts` 0, so the kill trips the parent: one
    child and exit 75.
  - The `sleep` dies. With SIGTERM sent to the pid alone, it survives.
- `test_a_hung_child_that_ignores_sigterm_gets_sigkill_and_hb_is_its_beats_age`
  - Asserted: `killed_with` "KILL"; the exit row (rc None, signal 9, why "hang").
  - Also asserted: `hb` is the beat's age (1.0-1.5 s), not the time since the start (over 2 s).
- `test_a_hung_child_is_a_hang_and_not_stale_stops`: with the switch off, a hung child holding BBB writes no
  `stale_stops` row while its beat ages past `stops_stale_seconds`.

### RED

Command, from `ai-trader/`:
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py -k Watching`.
At that point the class had 15 tests: the 11, the 2 by ruling and the 2 from self-review. Summarised with
`sort | uniq -c`:

```
      1 AttributeError: module 'aitrader.supervise' has no attribute 'open_seconds'
      1 AttributeError: <module 'aitrader.supervise' ...> does not have the attribute 'open_seconds'   (the mock.patch)
      1 AttributeError: module 'aitrader.supervise' has no attribute 'beat_view'
      1 AttributeError: module 'aitrader.supervise' has no attribute 'mark_due'
      4 AssertionError: not within 10 s: <lambda>; engines that ended: []
      1 AssertionError: not within 20 s: <lambda>; engines that ended: []
      3 AssertionError: not within 5 s: <lambda>; engines that ended: []
      ValueError: not enough values to unpack (expected 2, got 0)   (no mark rows)
      IndexError: list index out of range                           (no up row)
      1 FAILED (failures=8, errors=6)
      1 Ran 15 tests in 83.886s
```

These failures were expected:
- The brief names `AttributeError: module 'aitrader.supervise' has no attribute 'open_seconds'`.
- The process tests waited for rows (`hang`, `up`, `code`, `stale_stops`) that the parent did not write yet.
- `test_a_new_child_has_the_start_grace_for_its_first_beat` passed in RED. It asserts the absence of a hang row, and
  nothing wrote hang rows yet. The mutation pass shows it fails when the grace is not honoured ("no start grace": 2
  failures).
- The five tests from the mutation pass were written after the code and checked against their mutants, listed below.

### GREEN

`... safe python3 -m unittest discover -s tests -p test_supervise.py -k Watching -v`, on the committed code:

```
test_a_beat_left_by_another_pid_is_no_beat ... ok
test_a_frozen_child_is_killed_and_replaced ... ok
test_a_hang_kill_reaches_the_childs_whole_group ... ok
test_a_hung_child_is_a_hang_and_not_stale_stops ... ok
test_a_hung_child_that_ignores_sigterm_gets_sigkill_and_hb_is_its_beats_age ... ok
test_a_mark_carries_the_fields_of_spec_4_6 ... ok
test_a_mark_is_due_once_per_clock_minute ... ok
test_a_new_child_has_the_start_grace_for_its_first_beat ... ok
test_a_sale_in_the_second_the_parent_started_is_in_up_sold ... ok
test_blind_s_runs_from_the_last_look_before_the_start_to_the_first_look_after ... ok
test_code_changed_compares_with_the_child_before ... ok
test_first_look_done_wants_this_childs_own_look_at_every_held_name ... ok
test_open_seconds_is_cut_to_the_session ... ok
test_stale_stops_start_once_and_end_once ... ok
test_the_real_engine_gets_a_code_row_after_its_up_row ... ok
test_the_stop_age_grows_with_the_beats_own_age ... ok
test_up_is_written_while_a_held_name_is_blind ... ok
test_up_says_what_the_restart_cost ... ok
test_with_the_market_closed_up_comes_at_the_first_beat ... ok
test_with_the_switch_off_a_hang_is_logged_once_and_nothing_is_signalled ... ok
Ran 20 tests in 32.612s
OK
```

The whole file starts processes, so I ran it three times in a row on the final code: `Ran 72 tests` `OK` each time
(71.9 s, 72.2 s, 73.9 s). An earlier set of three, before the last two edits, also passed (76.2 s, 74.4 s, 72.4 s).
The output is pristine: one dot line and the summary, no warnings, nothing printed.

### Mutation pass

Scratch runner `<SCRATCH>/t12/mutate.py`, under the safe
wrapper. Each mutant was applied to `supervise.py`, `Watching` + `ParentLoop` was run, and the file was restored. `cmp`
against the backup confirmed the restore. No stray process was left.

Killed on the first pass (15):
- `mine` ignoring the pid
- no start grace
- the hang said every tick
- `first_look_done` without the blind half
- the P16 age without the beat's own age
- P14 not cut to the second
- `sold` not only SELL rows
- `code_changed` always false
- a stale episode that never ends
- `blind_s` measured from the up beat's own stamp
- a mark every tick
- `open_seconds` without the early close
- the switch ignored
- `down_s` null
- the mark's `n` from another pid's beat

Survived the first pass and are killed by the five tests added above (6):
- the hang kill sent to the pid alone
- no "KILL" word after SIGKILL
- `first_look_done` ignoring "boot"
- stale stops judged on a beat that is not fresh
- `up` waiting for a look while the market is closed
- the hang row's `hb` taken from the run time

One survivor is left: using a blind name's own stamp instead of the beat's `at` as "the first look after". It is
equivalent for every beat the dummy can write, and for an engine blind name whose stamp predates this child. It differs
only for a name that this child looked at live and that then went blind before the parent saw the `up` beat. The code
follows the brief's wording: a blind name ends at `at`.

### The hour (P1, the 11:10 ruling)

All runs were made after 16:05 New York: the suite ended at 20:48 EST. The only engine child,
`test_the_real_engine_gets_a_code_row_after_its_up_row`, runs with `--until 24:00`, which never comes. The dummy ignores
`--until`.

The parent's calendar questions read the moved clock: 10:00 New York on 2026-11-12, or 10:00:59 in the mark test.

`blind_s` reads real stamps against the real calendar. No test asserts a real-hour value of it: the one `blind_s` test
replaces `open_seconds`. The fixed-date test of `open_seconds` checks the function itself.

## Whole suite

`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests` from
`ai-trader/`, on the committed code, just before the commit. Wall 144 s. Last three lines:

```
Ran 758 tests in 143.542s

OK
```

758 = 738 (the end of Task 11's fix round) + 20 new. An earlier run before the last two small edits also gave `Ran 758
tests in 138.617s` / `OK` (wall 139 s).

## Files changed

- `ai-trader/aitrader/supervise.py` (+219, -10; 659 lines)
- `ai-trader/tests/test_supervise.py` (+189, -8; 1166 lines). The -8 are `kill_sleep` moving from `ParentLoop` to
  `Parents`.

## Self-review (`git diff 9d813d54..HEAD`)

I went through the brief line by line against the diff. Every function, row, field, switch behaviour and the order up
-> code is there. Found and fixed before the commit:
- Three lines over 120 characters in `supervise.py` (the file had none).
- A clever two-signal loop in the hang stop, replaced by straight SIGTERM / wait / SIGKILL code.
- An unreadable `datetime.min` fallback in the `sold` filter, replaced by a walrus test.
- `_stamp_ages` with an unknown age: it now gives None instead of a `TypeError`. That would matter only to a caller of
  the public `beat_view` that passes no mtime.
- `kill_sleep` was only on `ParentLoop`: moved to `Parents`.
- `test_a_second_parent_returns_3...` would now race the first parent's `up`/`code` rows. This was Task 11's concern 4,
  in a sharper form than it guessed: the rows come at the first beat, not at a minute turn. Fixed, see "Departures",
  item 1.
- The mark at a minute turn cannot touch that test: the first mark comes before the child starts, the next 60 s later.

Checked and left:
- `killpg` is used only while the child is unreaped. Between the core's `poll()` and the hang stop nothing reaps, so the
  group id is still the child's.
- Stale checks need a fresh beat, so a hang is reported as a hang, not also as stale stops.
- The dummy writes whole-second stamps. For a child of the dummy, `up` can come up to a second after its first beat,
  after its `code` row. The engine's stamps carry microseconds, so for it `up` comes first; the engine test proves it.

## Departures from the brief, and readings where it is silent

1. **An existing test's setup.** `ParentLoop.test_a_second_parent_returns_3_names_the_holder_and_writes_nothing` now
   waits for the first parent's `code` row before it takes its snapshot of `state/`, with one added line. Its
   assertions are unchanged. Without the wait, the `up` and `code` rows written right after the child's first beat could
   land between the snapshot and the comparison.
2. **Tests: 20 in `Watching`, where the brief has 11.** The 2 by ruling, 2 from self-review and 5 from the mutation pass
   are named above.
3. **The hang and stale tests use `spawn_parent` and SIGTERM.** The brief's stand-ins need config overrides and a parent
   that keeps running. `run_parent` takes no config keywords; Task 13 adds them, with its `stop_after`.
   `spawn_parent(**sup)` already takes them. The in-process tests (P14, mark, `blind_s`) end by themselves with exit 0 at
   `--until 10:00`.
4. **The `hang` row with the switch on is written after the kill.** Its `killed_with` is known only then. The order of
   the rows is `hang`, `exit`, `start`.
5. **The `hang` row's `hb`.** It is the beat's age when the child has beaten. When it never has, it is the time since its
   start: P5 makes it R2's "{s} seconds without a beat", which must be a number.
6. **Readings of the mark.**
   - `hb` and `n` are null when there is no beat of this child: during a wait, or a beat of another pid.
   - `open` is the beat's `market_open`, null without a beat of this child.
   - Ages have one decimal.
   - Task 16 should read a null `hb` as "not shown protected".
7. **Readings of `up`.**
   - `down_s` has two decimals. With one decimal, a restart faster than 50 ms would read 0. In practice a restart costs
     more, but the brief's `assertGreater(down_s, 0)` must never flake.
   - `down_s` is null when `down_from` is null.
   - `blind_s` is 0 (int) when nothing is held.
   - `sold` is null, with a log line, when `news_trades.jsonl` exists but cannot be read. It is [] only when there is
     really nothing.
   - The sold rows are kept whole, as journaled (hash fields included). Task 13 maps `symbol`/`stop`/`price` to R1's
     {sym, stop, fill}.
8. **"The last look before the end"** is the oldest stamp of the heartbeat on disk when the child is started: the
   previous engine's last beat, also across a parent restart. When there is none, it is the up beat's
   `stops_checked_at`, the stamp the engine adopted (equity fallback). When neither is there, `blind_s` is 0.
9. **The code row saves the state file** at once, so `last_commit` is "updated then" on disk, not only at the parent's
   end. The save carries the core's running restart count, so the file never goes backwards.
10. **Stale stops.**
    - "Fresh" is this child's beat with `age_s` <= `hang_seconds`.
    - A held name whose stamp cannot be read counts as stale, with `stop` null.
    - The "end" row carries the episode's names and the `stop` at that beat. Task 13 can take R6b's "{s}" from the start
      row's `stop` plus the time between the rows.
    - An episode also ends when the market closes or nothing is held any more.
11. **The switch** counts as on only when `hang_kill_enabled` is literally `true`. A missing or misspelt key leaves it
    off.
12. **`NUMBERS`** now validates the four new numeric keys. A config without them gets exit 2 at the start, not a
    `KeyError` in the loop.

## Concerns

1. **No marks while `stop()` runs.** A hang stop blocks the loop for up to `hang_term_grace_seconds` (5 s), a planned
   stop for up to `planned_stop_grace_seconds` (120 s). Both block the loop, so no mark is written meanwhile. This is
   Task 11's design. A planned stop of 120 s or more would show as a mark gap in the uptime report; within 150 s it
   is not counted as one.
2. **Grandchildren that outlive their leader.** If the leader ends within the TERM grace but a grandchild ignores TERM,
   the grandchild is not sent SIGKILL. After the leader is reaped, its group id may no longer be the child's, and the
   parent never signals what it did not start. The engine's own children (`claude -p`, git) die on TERM.
3. **The `blind_s` survivor** (blind name: `at` versus its own stamp) is equivalent for every input the tests can make,
   as explained above.
4. **R6 right after a slow restart.** `stale_stops` follows spec 4.3 literally and does not skip the boot phase. After a
   restart that took over `stops_stale_seconds` with a name held, the new child's first beats carry the old stamp. That
   gives a `stale_stops` start, then an end at the first look. Task 13 may want R6 not to fire for such an episode,
   which R1 already reports.

## Fix round 1

Commit `5ab41f32` on `supervisor-build`, parent `c82097e1`. It is a new commit; nothing was amended. Files:
`ai-trader/aitrader/supervise.py` and `ai-trader/tests/test_supervise.py`. After the commit `git status --short` prints
nothing.

### F1 (Important, spec): blind_s was 0 when the first look sold every name held before. Fixed.

- `ai-trader/aitrader/supervise.py:500-501` (`spawn`): `kid` now also keeps `held_before = set(_held(before))`. These are
  the names that the heartbeat on disk at the child's start holds: the previous engine's last beat, also across a
  parent restart. `last_look` comes from the same `before`.
- `ai-trader/aitrader/supervise.py:571-577` (`up`): `after` is built as before, one entry per name the `up` beat holds.
  If any name in `held_before` is no longer held in the `up` beat, the beat's `at` is appended. The first look sold
  that name, and it did so by the time of this beat. That is the same upper bound that a blind name already gets.
  The guard is unchanged:
  - nothing held before or now: `after` is [] and `blind_s` is 0;
  - an unreadable `at`: None is in `after` and `blind_s` is 0.
- This fixes the root of the finding: names the `up` beat no longer holds were left out of the measure. It does not
  only fix the all-sold case. In a partial case (AAA and BBB held, the first look sold AAA, BBB is still held), `b` is
  now the beat's `at` rather than BBB's own stamp. The two differ by less than one loop tick, and `at` is the bound
  that cannot understate.
- The test is new, next to the existing one:
  `Watching.test_blind_s_counts_a_name_held_before_the_start_that_the_first_look_sold` (`tests/test_supervise.py:1124`).
  - The previous heartbeat (pid 1, 40 s old) holds BBB. The dummy run holds nothing.
  - `open_seconds` is patched as in `test_blind_s_runs_from_the_last_look...`.
  - `first_look_done` is wrapped to record the beat it first answers True for. With the market open, that is the beat
    that writes `up`, and it is never asked again after `up`.
  - Assertion: `up.held == {}`, `up.blind_s == 42.0` (the patched value), `a == last`, and `b == the up beat's at`.
- The hour does not matter for this test. It runs in process with the dummy child, which never acts on `--until`, and
  the parent's clock is the moved one (10:00 New York).

RED, run against the old `supervise.py`. That file was written from `git show HEAD:ai-trader/aitrader/supervise.py`
and then restored byte for byte. No stash was used.

```
$ /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -k test_blind_s_counts_a_name_held_before_the_start_that_the_first_look_sold
    ((a, b),), (beat,) = asked, beats
    ^^^^^^^^^
ValueError: not enough values to unpack (expected 1, got 0)
Ran 1 test in 0.965s
FAILED (errors=1)
```
`open_seconds` was never asked, so `blind_s` took the 0 branch.

GREEN:
```
$ /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -k test_blind_s -v
test_blind_s_counts_a_name_held_before_the_start_that_the_first_look_sold ... ok
test_blind_s_runs_from_the_last_look_before_the_start_to_the_first_look_after ... ok
Ran 2 tests in 1.932s
OK
```

### Covering tests

Every parent in `tests/test_supervise.py` passes through `spawn` and `up`, so the whole file was run three times in a
row, after the `Watching` class three times in a row. All commands were run from `<clone>/ai-trader`.

```
$ for i in 1 2 3; do /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -k Watching 2>&1 | tail -3; done
Ran 21 tests in 32.903s
OK
Ran 21 tests in 33.588s
OK
Ran 21 tests in 34.287s
OK

$ for i in 1 2 3; do /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests -p test_supervise.py 2>&1 | tail -3; done
Ran 73 tests in 74.470s
OK
Ran 73 tests in 76.495s
OK
Ran 73 tests in 74.441s
OK
```

### Whole suite (once, before the commit)

```
$ /home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/safe python3 -m unittest discover -s tests
Ran 759 tests in 140.645s

OK
```
Wall time: 141 s. There are 759 tests: 758 before this round, plus the one new test.

### Not on the list, so left alone

The review's Minor items were not touched:
- the group SIGKILL when the leader ends within the grace;
- the `hang` row's `t`;
- the cold-start `blind_s`;
- the duplicated kill block;
- the size of the closures;
- marks during `stop()`;
- the commit author identity.
