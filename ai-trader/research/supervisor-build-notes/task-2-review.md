# Task 2 review - the owner's lines in one table

Diff `e3be9447..c6bec0f7` (one commit, 4 new files, 231 lines), read once from `review-task-2.diff`.
No changed file was read outside the package. Nothing was run in the clone; HEAD and `git status --short` are as found.

### Spec Compliance

Verdict: compliant with the brief as the controller's rulings of 2026-11-11 10:50 UTC amend it. Nothing missing, nothing extra, nothing misunderstood.

- Files: all four of the brief are in the commit and nothing else (`ownerlines.py` 141 lines, `helpers/__init__.py` empty, `helpers/no_phone.py` 19, `test_ownerlines.py` 71).
- Interfaces: `PHONE_VARS`, `clean_env(**extra)`, `LINES`, `PARTS` (5 keys), `WORDS` (5 lists, the brief's values, `R5e.why` keyed by int), `FREE`, `held_text`, `sold_text`, `hhmm`, `priority`, `render` - every name with the brief's signature (`ownerlines.py:98,107,116,121,126`; `no_phone.py:11,16`).
- Tests: the brief's five exist under their names with the brief's assertions (`test_ownerlines.py:23,26,34,43,53`); the sixth stays by ruling (`:59`). `IDS`, `LIM` and `fill` are the brief's text.
- Rulings applied and nothing beyond them: `max_bytes=80` in the one W4 call (`test_ownerlines.py:55`); the tail of `sold_text` is ` ועוד {n}.` and the assertion is `endswith("ועוד 2.")` (`ownerlines.py:113`, `test_ownerlines.py:41`); two decimals in both texts (`ownerlines.py:103,111`); a form the line does not have is a `KeyError` (`ownerlines.py:132,135`).
- One assertion added to a test of the brief (`test_ownerlines.py:38-39`, the cap of `held_text`): it strengthens, removes nothing. Not counted as extra.
- The test module begins with `from helpers import no_phone  # noqa: F401` (`test_ownerlines.py:3`).
- Commit message: the brief's line exactly, no body, no trailer, no session link (check 5 below).

Checks I ran (one per named risk, all on a scratch copy made with `git show c6bec0f7:<path>`, bytecode off, phone variables unset):
1. Risk: a template, a priority or a part differs from spec 8 by a character. Parsed the 38 rows of spec section 8 and compared them with `LINES` and `PARTS` (times to `{time}`/`{time2}`, `{DD.MM}` to `{date}`, `R4.cold` to `{cold_time}`, `R2.off` rebuilt from R2's head and the spec's "switch off" text): 38 rows, 38 lines, 5 parts, 0 differences; every text ends with "כסף נייר"; no doubled space; no character outside printable ASCII and the Hebrew letters.
2. Risk: R1 with real parts overflows the limit (the 20-names test fills `{falls}`, `{sold}`, `{code}` with 99999). Rendered R1 with 20 held names and 20 sales at cap 6, six-digit prices, the falls part and the code part: 915 bytes, under 1,200.
3. Risk: `no_phone` drops fewer variables than the senders read. `notify.py:37,47,48` reads exactly the three names, `config.json:235` names `AITRADER_NTFY_TOPIC`, and `tests/test_core.py:19` pops the same three. Equal.
4. Risk: importing `aitrader.ownerlines` pulls a third-party module into the parent. `aitrader/__init__.py` has no code at c6bec0f7. Standard library only holds.
5. Risk: attribution in the commit. `git log -1 --format=%B`: one subject line, nothing else.
6. Edge probes: a note with braces and a line break stays text (no second formatting pass); a line of exactly `max_bytes` (87 of 87) is returned; `held_text` with a `None` stop raises `TypeError`; `held_text` with cap 0 returns ` ועוד 2`.

Cannot verify from this diff:
- That every later caller (engine, parent, dead-man, watcher, slots) renders through `render` with the limits read from `config.json`: the keys `supervisor.max_line_bytes`, `held_names_in_line` and `free_text_max_chars` do not exist yet (no `supervisor` block in `config.json` at c6bec0f7).
- That a caller never loses an urgent line, or dies, on the `ValueError` or `KeyError` that `render` raises (`ownerlines.py:137,140`).
- That the dead-man takes DM1's and DM2's priority from `priority(id, held=...)` and not from `LINES[id][0]`, which holds "high" for both (`ownerlines.py:53,56,123`).
- That callers pass a float stop for every held name and an aware datetime to `hhmm` (`ownerlines.py:103,118`).
- That every later test module imports `helpers.no_phone` first and every process a test starts gets `clean_env()`.
- The mutation result (19 planted, 0 survived) and the implementer's own table check: their scripts are not in the commit. I repeated the table comparison independently (check 1); the mutation count stays a claim.
- The whole-suite result (552 tests, `OK`, 60 s): taken from the report, not re-run.
- Whether the commit's author name ("Claude", the clone's identity, the same on the six commits before the base) is acceptable: the constraint names trailers and lines of the message, not the author field. The controller's call.

### Strengths

- The table is the spec's table, character for character, and the priorities match row by row (check 1).
- `ownerlines.py` holds data and five small functions; no number sits in the logic, the three limits arrive as arguments (`ownerlines.py:98,107,126`).
- The `ValueError` text carries the id and two sizes, never the line or a field (`ownerlines.py:140`).
- `clean_env` is built from nothing (`PATH`, `HOME`, then three fixed keys), so no `AITRADER_*` and no proxy variable can leak through by inheritance (`no_phone.py:18-19`).
- The tests call the real functions, no stand-in anywhere; the 700-letter case really forces the cut (700 Hebrew letters are 1,400 bytes, over the limit by themselves).
- The sixth test gives each "no such form" case every field the line needs, after showing that the plain line renders, so the `KeyError` can only come from the form (`test_ownerlines.py:65-71`).
- TDD evidence is complete: the brief's expected first failure, the plan defect shown failing once, the ruling's RED, then GREEN.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

1. `ai-trader/aitrader/ownerlines.py:53` (DM1), `:56` (DM2), `:44` (R8) - plan-mandated.
   What: four numbers that `config.json` owns are fixed text in three owner lines: DM1 "יותר מ-6 דקות" (`supervisor.deadman.delay_seconds` 360), DM2 "כבר 10 דקות" (`deadman.handover_delay_seconds` 600), R8 "9 שעות" (`long_timeout_ms` 32,400,000) and "4 פעמים ביום" (the four `handover_times_ny`). R3b's "עד חצי שעה" (`:25`) is tied to the watchdog schedule the same way.
   Why: rule 5 says every number lives in `config.json`. Spec 10 marks `handover_delay_seconds` as "dt", a value the drills tune. After such a change the dead-man line tells the owner a wrong number of minutes without checked stops, and no test notices. The implementer copied the spec's text as the brief orders; the defect is the spec's.
   Fix: a controller ruling. Either (a) keep the text and add a pin test in the task that adds the `supervisor` block (none exists at this commit): the four config values equal the numbers the texts say; or (b) amend spec 8 so these become placeholders filled from the config. Task 2's templates should not change without that ruling.

#### Minor (Nice to Have)

1. `ai-trader/tests/test_ownerlines.py:57` - `clean_env`, the environment of every process the later tests start, is pinned by one assertion (`NO_PROXY`). Nothing committed checks that an `AITRADER_*` or proxy variable set in the parent stays out, or that the keys are exactly `PATH, HOME, PYTHONPATH, NO_PROXY`; the report measured it by hand only. Fix: one assertion under `mock.patch.dict(os.environ, ...)`.
2. `ai-trader/tests/test_ownerlines.py:26-32` - the cut's length is not pinned: the test passes if a FREE field is cut to any length that fits, zero included. Fix: `render("S1", **LIM, what="א" * 700).count("א") == 200`.
3. `ai-trader/aitrader/ownerlines.py:116-118` - `hhmm` reads a naive datetime as the machine's local time. Fix: refuse `t.tzinfo is None`, or say it in the docstring.
4. `ai-trader/aitrader/ownerlines.py:95,136` - `{he}` (a slot name from the config), `{sym}` (a journal row) and `{commit}` also come from outside the table and are not cut (the brief fixes `FREE`); an over-long one is a `ValueError`, not a shorter line. A line break inside a note stays in the line.
5. `ai-trader/aitrader/ownerlines.py:102-104,110-113` - a cap of 0 gives ` ועוד N` with a leading space, a negative cap drops names from the end. Config sanity only.
6. `ai-trader/aitrader/ownerlines.py:134-135` - if a later line gets a ".cold" part and its template has no " שעון ישראל", `rpartition` puts the part at the very start without a word. Only R4 has one today, and its place is tested.
7. Report, "Whole suite": the suite's output carries `[news] ...` and `[journal] ...` lines from earlier engine tests. Not from this diff; the six new tests print nothing.

### Assessment

Task quality: Needs fixes - one item, and it is the plan's, not the implementer's.
The implementation is faithful, small and well tested, and I would approve it as built; the open point is a ruling on the config-owned numbers that spec 8 writes into DM1, DM2 and R8, which this task had to copy.
