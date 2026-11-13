# Task 12 review - what the parent sees: marks, `up`, a hang, stale stops

Diff 9d813d54..c82097e1 (one commit), read from `review-task-12.diff` in one pass. No changed file was read beyond the
package; the hunks were whole. Checks outside the diff, one per named risk, are listed under "Checks run".

### Spec Compliance

Not compliant: one item is misread.

- `ai-trader/aitrader/supervise.py:572-576` (`up`): `blind_s` is worked out only over the names the `up` beat still
  holds. Spec 4.6 says "0 when nothing **was** held", and the brief says "when a name was held". Take the case where
  the previous engine's last beat held BBB, and the new child's first look sells BBB because its live quote is under
  the stop. The beat that makes `up` then holds `{}`, so `after == []` and `blind_s` is 0. The outage was really
  blind, and this is the restart-with-a-held-position case of spec 3, row 17.

All else I could verify is compliant:
- All four interfaces have the brief's signatures and return shapes. `beat_view` has the keys `mine`, `age_s`,
  `stop_age_s`, `held`, `open`, `blind` and `phase`.
- The hang rule matches the brief: a beat that is not mine, or one older than `hang_seconds`, with
  `start_grace_seconds` for the first beat.
- Switch on: TERM to the group, `hang_term_grace_seconds`, KILL to the group, then the core's counted crash path.
  Switch off: one `hang` row "none" per hang, and nothing is signalled.
- `stale_stops`: "start" once per episode and "end" when fresh, only on a fresh beat of this child with the market
  open.
- The `mark` fields follow spec 4.6, with `dm` and `left` null.
- `up` is gated as the brief says: at the first beat when the market is closed, else at `first_look_done`.
- `first_look_done` checks this child's beat, not "boot", and every held name either stamped at or after `started` or
  in `blind`.
- `up` has every field the brief lists. `sold` takes SELL rows only and cuts the time to the whole second (P14). Row
  times use the injected clock and `logged_at` the real one, and the two are never compared.
- `code` comes once per child, and `code_changed` compares with `last_commit`, which is updated then.
- `stop_age_s` follows P16. The `hang` row keeps `hb` (P5).
- The engine test runs with `--until 24:00` (P1).
- All 11 brief tests exist under their names with the brief's assertions, and the stand-ins in their comments are
  written in (`tests/test_supervise.py:989-1072`).
- The files and the commit message are the brief's.

Cannot verify from this diff:
- The `up` rows give per-restart values. `down_from` is the last `exit`, and `sold` counts from the previous child's
  end, both as the brief says. So a child that sells in its first look and dies before its `up` is in no `up.sold`.
  Task 13 should check that R1, which spec 8 sends once per episode, works out the episode's fall time, `down_s` and
  sales from the first fall, not from the last `up`.
- Spec 4.3 says R6 is not sent when the beat's `blind` list names every stale name. The `stale_stops` row does not
  carry that fact. Task 13 should read it from the beat at the moment of the row.
- Task 16 should read a null `mark.hb` (no beat of this child) as unprotected.
- I did not re-run the reported results: the suite (758 OK, 144 s), the three runs of the file, and the mutation pass.

### Strengths

- `beat_view`, `first_look_done`, `open_seconds` and `mark_due` are small pure functions, and they are tested
  directly, apart from the process tests. `open_seconds` runs per New York date with `session_hours`, so the
  2026-11-27 early close and weekends come out right (Review Focus 3).
- `_read_beat` takes the content and the mtime from one descriptor. Atomic writes make the two belong to the same
  beat.
- The tripwires of Review Focus 1 are tested:
  - another pid's fresh beat is no beat (`test_a_beat_left_by_another_pid_is_no_beat`);
  - `up` is written while a held name is blind.
- Stale checks need a fresh beat, so a hang is not reported twice
  (`test_a_hung_child_is_a_hang_and_not_stale_stops`).
- Error paths log class names only. No threshold is a literal: all four new numbers come from config and are added to
  `NUMBERS`, so a config without them gets exit 2 and not a `KeyError` mid-loop. The switch counts as on only when it
  is literally `true`.
- The extra tests are discriminating:
  - group reach of the hang kill (the `sleep 60` dies);
  - the KILL path with `hb` as the beat's age;
  - the market-closed `up`;
  - P14's same-second sale;
  - P16's growing stop age.
  The mutation pass shows each test kills a named mutant.
- The edit to `test_a_second_parent_returns_3...` is one wait line, and its assertions are unchanged. I checked the
  dummy's defaults: nothing is held, so `up` and `code` come in the same tick and the wait for `code` covers both.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

- `ai-trader/aitrader/supervise.py:572-576` (`up`), with the input set at `:497-500` (`spawn`).
  - What is wrong: `blind_s` is 0 when every name the previous engine held was sold in the new child's first look.
    `after` is built from `_looks(hb)`, the names held in the `up` beat. When that is `{}`, the guard
    `after and ...` returns 0, though `kid["last_look"]` was taken from a beat that held names.
  - Why it matters: spec 4.6 defines `blind_s` as 0 only when nothing was held. This case is the restart with a held
    position (spec 3, row 17), when a stop sells at the restart.
    - R1 (spec 8) prints `סטופים לא נבדקו {blind_s} שניות` next to `{sold}`.
    - R2's kill form takes the `up`'s `blind_s` (ruling P5).
    - So the owner would read "0 seconds" for a blind outage in which the stop traded.
  - No test covers a run in which the held set shrinks across the restart.
  - Fix: in `spawn`, also keep whether the previous beat held any name. In `up`, when `after` is empty but that flag
    is set, use the `up` beat's `at` as the first look after. The look that sold the name is complete by that beat.
    Add one test next to `test_blind_s_runs_from_the_last_look...` (open_seconds patched the same way): the previous
    heartbeat holds BBB, the run holds nothing, and `up.blind_s` equals the patched value, with `b` the `up` beat's
    `at`.

#### Minor (Nice to Have)

- `ai-trader/aitrader/supervise.py:595-608`, the hang stop skips the group SIGKILL in one case.
  - SIGKILL goes to the group only when the leader is still alive after the grace. Spec 4.3 and the brief say SIGKILL
    to the group after the grace.
  - A descendant that ignores TERM survives when the engine itself ends within the grace (the report's concern 2).
  - Low impact: such a process cannot trade, and Python's descriptors are not inheritable.
  - The exact form: wait without reaping (`os.waitid(..., WEXITED | WNOHANG | WNOWAIT)`), so the group id is still
    the child's, then SIGKILL the group, then reap.
- `ai-trader/aitrader/supervise.py:610`: with the switch on, the `hang` row is written after the kill. Its `t` is up to
  `hang_term_grace_seconds` (or more, on the KILL path) after the hang was found, and spec 4.3 writes the row first.
  The departure is reported. Task 16 should not take the hang's start from this row's `t`.
- `ai-trader/aitrader/supervise.py:575`, cold start: with no heartbeat on disk and no `stops_checked_at` in the `up`
  beat, `blind_s` is 0 while names are held. That reads as "protected" where spec 4.6 says "what cannot be shown as
  protected counts as unprotected". It is an edge case, and R4, not R1, covers a restored VM.
- `ai-trader/aitrader/supervise.py:598-608` and `:617-623`: the block "killpg SIGKILL, ProcessLookupError, wait" is
  now written twice in `stop`. The stop-age rounding (`None if ... else round(..., 1)`) is written twice in `look`.
  Small duplication.
- `ai-trader/aitrader/supervise.py:497-653`: `main` now holds about 150 lines of nested closures (`spawn`, `watch`,
  `look`, `up`, `stop`, `core_emit`) that share the `seen`, `kid`, `st` and `counts` dicts. This follows Task 11's
  pattern and is still readable, but the next tasks (13, 15, 21) will add to the same closures.
- `ai-trader/aitrader/supervise.py:514`: no marks are written while `stop()` blocks: up to
  `planned_stop_grace_seconds` (120 s), or the hang grace plus KILL. This is Task 11's design, and it stays under
  `mark_gap_max_seconds` (150) only while that grace stays at or under 150 s. The config note on raising the grace
  for `news.guards` "enforce" should say so.
- Commit metadata, for the controller (not this task's defect): every commit of the build has the author
  `Claude <<email>>`, from the gate clone's git config. The message has no trailer or footer. The
  "no AI attribution" constraint should be weighed against the author identity before the landing.

### Checks run

- Risk: the `look` path crashes or `last_commit` is missing in an older state file. `load_state` always merges over
  `_new_state`, which has `last_commit: None`, and `last_commit` is in `KEPT_ACROSS_DAYS`. No `KeyError`.
- Risk: `sold` is wrong when the trades file is missing. `read_rows` returns [] on `FileNotFoundError`, so
  `sold == []`. Other `OSError` gives `sold` null and a log line.
- Risk: no marks during a back-off, and how "hang" is handled. `restart_core` calls `watch(None, 0.0)` in every wait
  tick, and `look(None, ...)` writes only the mark. "hang" leads to `stop(child, "hang")`, then an exit with
  why "hang", counted. The row order is hang, exit, start.
- Risk: a torn heartbeat read gives a false hang kill. `journal.save_json` writes a tmp file and then a rename
  (journal.py:235-239). The engine's blind list is the immediate no-live-quote set restricted to held names
  (news_live.py:1702,1713), so `up` is not held back by the 300 s alert clock.
- Risk: a dummy whose `up` follows its `code` makes the edited ParentLoop test flaky. The dummy's default `held` is
  {}, so `first_look_done` holds at the first idle beat, and `up` and `code` come in one tick.
- Risk: the switch default. `config.json` has `hang_kill_enabled: false`, and the `Parents` harness pins it off
  unless a test passes it.
- Check: the commit touches exactly the two brief paths and has the brief's message. No line in `supervise.py` is
  over 120 characters.

### Assessment

Task quality: Needs fixes. The build is careful and well tested, and every brief test and ruling (P1, P5, P14, P16)
is in place. But `blind_s` misreads "0 when nothing was held": it gives 0 for a restart in which every held name
was sold at the first look, an owner-facing number in the spec's row-17 case. It needs a small guard and one test.
