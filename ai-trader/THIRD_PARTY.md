# Third-party material

## TauricResearch/TradingAgents

- Source: https://github.com/TauricResearch/TradingAgents (commit 9fa1196, 2026-11-04)
- License: Apache License 2.0 - https://www.apache.org/licenses/LICENSE-2.0
- Used: the role design (bull/bear researchers, research manager, aggressive/conservative/neutral risk
  analysts, portfolio manager), the 5-tier rating vocabulary, and the reflection idea (2-4 sentence
  lessons that name the outcome window). Prompt wording in `skills/trading-desk/SKILL.md` is adapted and
  shortened from `tradingagents/agents/researchers/*.py`, `managers/*.py`, `risk_mgmt/*.py` and
  `memory/reflection.py`.
- Changed: the desk runs as Claude Code agents (no LangGraph, no external LLM key), cannot size or place
  orders, can only veto/shrink new entries, must cite only numbers from `aitrader brief`, and its calls are
  logged with probabilities for forward Brier grading.

## Age of Blood (owner's private repo)

- Patterns reused with the owner's permission: the `headless-playtest` discipline (seeded, before/after,
  never a single number) -> `skills/strategy-time-machine`; the `web-researcher` agent; the eight-heading session log;
  four-layer memory and end-of-session lesson capture; caveman/ponytail working style.

## Jake Schincariol - "The Trader skill" (v1) and its sequel with "The Time Machine" (v2)

- Sources: https://github.com/Jakeschincariol/trader-skill (commit 5189e79b9a480755a3733ac9713f5353981dbe18)
  and https://github.com/Jakeschincariol/day-trader-skill (commit 3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd).
- License: MIT (c) 2026 Jake Schincariol - kept in `vendor/*/LICENSE`.
- Vendored unmodified (tests omitted to keep the repo light; fetch them from the pinned commits) under
  `vendor/jake-trader-skill-v1` and `vendor/jake-trader-skill-v2`, installed by `bin/install-skills.sh`.
- Not installed: `trader-broker` (broker order execution - this bot is paper-only).
- Review notes (2026-11-09): standard-library Python only; the only subprocess is `pdftotext` with list args;
  network = public GETs (Yahoo, SEC, House Clerk, Nasdaq Trader, stooq, nyse.com) plus an optional OpenFIGI
  POST; writes only under ./trader/. The packs print external text (headlines, filings) into the context with
  no "treat as data" rule - our skills add that rule. Their offline test suites were not executed here (the
  session's auto-mode policy blocks running external code); run them before relying on a script.
