# Build claims - one builder per file at a time

Two sessions changed `aitrader/news_live.py` on 2026-11-10 without knowing of each other, and the merge cost hours.
The rule is in `CLAUDE.md` ("One builder at a time"). Claims are listed newest first. Times are UTC.

## Open

- **2026-11-11 10:20 - main session ("בוט סוחר למניות")** - files: `aitrader/news_live.py`, `aitrader/__main__.py`,
  `aitrader/notify.py`, `config.json`, new `aitrader/ownerlines.py`, `aitrader/supervise.py`, `aitrader/deadman.py`,
  `aitrader/uptime.py`, `aitrader/slots.py`, `aitrader/watch.py`, `scripts/drill_supervisor.py`, `tests/helpers/`,
  new `tests/test_ownerlines.py`, `tests/test_news_supervised.py`, `tests/test_supervise.py`, `tests/test_uptime.py`,
  `tests/test_slots.py`, `tests/test_watch.py`, `tests/test_slot_files.py`, `skills/trader/SKILL.md`,
  `skills/trader/slots/`. Purpose: the supervisor ("always on the air"), plan
  `research/plans/2026-11-10-supervisor.md`, approved by the owner on 2026-11-11. Build tasks 2-8 first (engine
  changes); nothing reaches the live engine before its gate. Tests-only additions to other test files are welcome
  from any session: say so under "Waiting" first so the two do not collide.

## Waiting

- **2026-11-11 09:05 - trader session, for the main session** (your claim of 2026-11-10 20:40 holds these files):
  1. `tests/test_loss_protocol_pins.py` is in the suite now. It extends classes of `tests/test_news_guards.py` and
     `tests/test_postmortem.py` and uses their helpers as they are at e6a82895 (`_score`, `_item`, `_verdicts`,
     `_checks`, `_second`, `_step`, `_bar`, `_sold`, `_run`, `_fill`, `self.sent`, `self.asked`, `self.asked_bars`,
     `self.bars`, `self.NOW`). If wave 3 changes a helper or a pinned behaviour, these tests will say so; the file is
     free to edit. `test_the_fallbacks_in_the_code_say_what_config_says` fails on any key of `news_live.DEFAULTS`
     that `config.json` news lacks or sets differently.
  2. Waits for `tests/test_news_*.py`: folding the 51 methods into their classes, the wait for background
     "trial-check" threads in `_Engine.setUp/tearDown`, and three old methods that fail at 23:59 or just after
     midnight New York: `research/2026-11-10-loss-protocol-pins/waiting.diff` (or `fold.py` there once the diff no
     longer applies). Fourteen more old methods fail when a day turns inside them (list in `tools/` there).
  3. Waits for `aitrader/news_live.py` and `config.json`: backlog items 46 (a day-move that is not a finite number
     is read as known), 48 (the catch-up gap note) and 49 (two observations on the heartbeat stamp and on a hold
     release with no record). None is reachable from the live loop today; buys are on hold.
  4. The mutation harness is in `research/2026-11-10-loss-protocol-pins/mutation/`; its 420 mutants are anchored on
     line numbers of e6a82895 and need new anchors after wave 3.
  5. Usage: the account's limit was reached in the night of 2026-11-10 (eleven verifier agents of this session
     failed with the limit message at about 23:00 UTC). At 08:35 UTC `logs/2026-11-11-morning-brief.md` did not
     exist; Nimrod was told by push, as the 08:00 slot asked.

## Done

- **2026-11-10 20:40 - main session ("בוט סוחר למניות")** - files: `aitrader/news_live.py`, `aitrader/__main__.py`,
  `aitrader/backtest.py`, `aitrader/metrics.py`, `aitrader/report.py`, `aitrader/crypto_sweep.py`, `config.json`,
  `tests/test_news_*.py`, `tests/test_time_machine_honesty.py`, `skills/strategy-time-machine/SKILL.md`.
  Purpose: bring wave 3 (the engine records its own speed, cost and misses; exit-lever follow-ups; time machine
  ranges and run records - 9 local commits made on base 0215537a, gated there) on top of e6a82895 (the loss
  protocol and engine repairs). Until this line is marked done, other sessions do not edit these files; operations,
  state, logs, lessons and postmortem records go on as usual.
  **Done 2026-11-11 10:20 UTC**: merged and gated (PASS), 546 tests, pushed.

- **2026-11-11 08:50, done 09:05 - trader session** - files: `tests/test_loss_protocol_pins.py` (a NEW file; no existing file
  under a claim is edited). Purpose: 51 test methods that pin the loss protocol and the engine repairs of
  e6a82895. A mutation run found 68 one-line changes to `news_live.py`, `postmortem.py` and `__main__.py` that
  change what the engine does and pass the landed suite; each method fails on at least one of them. The classes
  extend classes of `tests/test_news_guards.py` and `tests/test_postmortem.py` and edit neither.
  Landed: 442 tests pass; with the file 412 of the 420 mutants are killed (8 left behave like the unchanged code).
  The file is free to edit.
