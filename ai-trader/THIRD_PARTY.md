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
  never a single number) -> `skills/time-machine`; the `web-researcher` agent; the eight-heading session log;
  four-layer memory and end-of-session lesson capture; caveman/ponytail working style.
