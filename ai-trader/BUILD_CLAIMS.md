# Build claims - one builder per file at a time

Two sessions changed `aitrader/news_live.py` on 2026-11-10 without knowing of each other, and the merge cost hours.
The rule is in `CLAUDE.md` ("One builder at a time"). Claims are listed newest first. Times are UTC.

## Open

- **2026-11-11 08:50 - trader session** - files: `tests/test_loss_protocol_pins.py` (a NEW file; no existing file
  under a claim is edited). Purpose: 51 test methods that pin the loss protocol and the engine repairs of
  e6a82895. A mutation run found 68 one-line changes to `news_live.py`, `postmortem.py` and `__main__.py` that
  change what the engine does and pass the landed suite; each method fails on at least one of them. The classes
  extend classes of `tests/test_news_guards.py` and `tests/test_postmortem.py` and edit neither.

- **2026-11-10 20:40 - main session ("בוט סוחר למניות")** - files: `aitrader/news_live.py`, `aitrader/__main__.py`,
  `aitrader/backtest.py`, `aitrader/metrics.py`, `aitrader/report.py`, `aitrader/crypto_sweep.py`, `config.json`,
  `tests/test_news_*.py`, `tests/test_time_machine_honesty.py`, `skills/strategy-time-machine/SKILL.md`.
  Purpose: bring wave 3 (the engine records its own speed, cost and misses; exit-lever follow-ups; time machine
  ranges and run records - 9 local commits made on base 0215537a, gated there) on top of e6a82895 (the loss
  protocol and engine repairs). Until this line is marked done, other sessions do not edit these files; operations,
  state, logs, lessons and postmortem records go on as usual.

## Waiting

(none)

## Done

(none)
