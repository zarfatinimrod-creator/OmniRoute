# AI Trader - rules for every Claude session working in `ai-trader/`

This folder is a self-contained project that lives inside the OmniRoute fork only for convenience.
The OmniRoute rules (worktrees, release freeze, Node quality gates) do NOT apply to work inside
`ai-trader/`; these do. Read `skills/trader/SKILL.md` before any trading session and
`skills/time-machine/SKILL.md` before any strategy change.

## The owner
Nimrod - Hebrew speaker, not a programmer, approves anything involving real money. Talk to him in
short plain Hebrew (terse, no fluff - the Age of Blood "caveman" style; technical terms and tickers
verbatim). One question per message, with options (א / ב / ג) and a recommendation.

## Hard rules
1. **Paper money only** until Nimrod explicitly says otherwise in chat, after at least 3 months of paper
   results that beat SPY on a risk-adjusted basis. Never place a real-money order. Never create accounts,
   type passwords, or handle payment details - he signs in himself.
2. **Never commit secrets.** API keys arrive through the environment's network secrets (proxy injection)
   or env vars - never in files, logs, reports or commit messages.
3. **Claude can only reduce risk.** Overrides (`python3 -m aitrader veto|shrink`) may veto new entries or
   shrink sizes; never add names, never increase size, never disable stops or the drawdown breaker.
4. **Every change to strategy/risk/learning** goes through the time machine sweep before and after, the
   `quant-critic` agent, and `python3 -m unittest discover -s tests` (from `ai-trader/`). No exceptions.
5. **Assumptions live in `config.json`.** Never hard-code a number in the logic.
6. **Evidence discipline.** Every number in a report or lesson cites where it came from (a file in
   `state/`, a backtest run, or a URL). Never present an estimate as a measurement. Never claim the bot
   "predicts" the market; it estimates small edges with known error rates.
7. **No look-ahead.** Values on date t use data up to the close of t. Claude's own judgement is graded only
   forward (live), never in historical replay (the model may remember the past).
8. `git stash` is banned (it is shared across worktrees). Commit state with clear messages and push.

## Memory (four layers)
- working: `state/portfolio.json`, `state/weights.json`, `state/latest.json`
- episodic: `state/predictions.jsonl`, `decisions.jsonl`, `trades.jsonl`, `learning.jsonl`, `equity.jsonl`
- semantic: `state/lessons.md` - each lesson: date, observation, evidence (numbers + file), confidence,
  what would change our mind. A lesson changes behaviour only after it is confirmed by data.
- procedural: `config.json`, `skills/*/SKILL.md` - changed only via rule 4.

## Logs
At the end of every session: `logs/YYYY-MM-DD-<slug>.md` with the eight Hebrew headings -
הבקשה · מה נעשה · קבצים ששונו · החלטות · כשלים בדרך · אימות · עבודה ידנית חוזרת → לאוטומציה · בזבוז טוקנים.
First line names the session type (cycle / pre-market / post-close review / weekly research).

## Agents and models
`agents/web-researcher.md` for research, `agents/quant-critic.md` as the gate for strategy changes.
In workflows: the session model builds and does the final check; one independent adversarial lens per
unit that ships; volume scouting can use a cheaper model. Small waves, resumable.
