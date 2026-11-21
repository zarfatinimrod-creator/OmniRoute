# Brief: skills, repos and plugins for the AI paper trader (2026-11-09)

**Bottom line:** none of the frameworks, benchmarks or live tests we reviewed shows an autonomous LLM trader beating the market reliably, after costs, with statistical significance.
- FINSABER (2004–2024, delisted names included): no significant alpha; LLMs were too cautious in bull markets and too aggressive in bear markets. https://arxiv.org/abs/2505.07078
- Profit Mirage: returns fall 50–72% once trading moves past the model's knowledge cutoff. https://arxiv.org/abs/2510.07920
- StockBench: 8 of 13 LLMs beat passive, but before costs and over only 82 days. https://arxiv.org/abs/2510.02209

Our working assumption is **no edge** until the forward paper record shows one. So we build our own thin pipeline where Claude proposes and code decides. We copy about 30 license-clean skills into it at pinned commits, and we take Age of Blood's working habits generously.

---

## 1. Ranked recommendations

1. **Move `ai-trader` into its own GitHub repo before anything else.**
   - Today it is a subfolder of the OmniRoute fork, and the root `/.claude/` is gitignored.
   - The nested `ai-trader/.claude/skills` only loads if a session starts in that folder or touches a file there.
   - `.mcp.json` is resolved from the session's working directory.
   - Every cloud run loads OmniRoute's ~62 KB of rules (worktrees, release freezes), which clash with unattended trading.
   - Cloud sessions load the repo's `.claude/skills`, `.claude/agents` and `.mcp.json`. They do **not** load plugins (https://code.claude.com/docs/en/cloud-environments.md).
   - Fallback if we stay in the fork: an environment setup script that runs `bin/install-skills.sh`. This is inferred and unverified.

2. **Claude proposes, code decides.**
   - Claude outputs a structured view: 5-tier rating, `p_outperform_SPY`, `target_weight`, `stop_pct`, `horizon_days`, a thesis of at most 5 sentences, and 2–4 conditions that would prove it wrong.
   - Deterministic code owns sizing, limits, orders and keys. Decide at T's close, fill at T+1's open.
   - If Claude's output can't be parsed, the result is `REVIEW`, never a silent Hold (from TradingAgents `rating.py`).
   - Design references:
     - chase-manning (MIT, 97 stars): https://github.com/chase-manning/ai-hedge-fund. Correction from the fact-check: it trades leveraged Hyperliquid perps and has no live record, so its limits must be re-derived for a long-only cash account.
     - aihf v2 principles: https://github.com/virattt/ai-hedge-fund/blob/main/hedge_fund/README.md

3. **An immutable journal, graded only going forward.**
   - Append-only JSONL, each record SHA-256-chained to the previous one. Key is (date, ticker).
   - Log HOLD and no-trade decisions too. A change is a new record linked to the old one, never an edit.
   - Verify the chain at startup and halt if it breaks.
   - Store `prompt_sha256`, `model_id` and a hash of the input data. Yahoo revises bars after the fact: 9 of 3,526 five-minute bars changed.
   - Backtests must refuse any `llm=True` signal dated before the model cutoff + 30 days. Opus 5.5's cutoff is June 2026. Models memorise pre-cutoff data, and neither masking nor instructions prevent it (https://arxiv.org/abs/2504.14765).

4. **A settlement and reflection loop**, ported from TradingAgents `memory/{log,settlement,reflection}.py` (Apache-2.0, about 400 lines, https://github.com/TauricResearch/TradingAgents).
   - Grade each view at its own horizon (5 and 20 days) on raw return, alpha vs SPY, and a regime tag. This avoids the reported flaw where right calls in a falling market were scored as losses.
   - Keep its warning that a short settlement window can be shorter than the view's horizon.
   - Never write a lesson from truncated output (anything where `finish_reason` is not `stop`).

5. **A deterministic risk gate plus Knight-style pre-trade guards** (numbers in §4).
   - Clamps can only shrink a position, and removed exposure stays in cash.
   - Knight Capital sent more than 4 million orders in 45 minutes and lost more than $460M (https://www.sec.gov/newsroom/press-releases/2013-222).

6. **Learning has to pass statistical gates.**
   - Scorecard per signal source: hit rate, slugging, Spearman IC with a t-stat.
   - A veto audit for Claude's vetoes.
   - Shadow baselines: SPY buy-and-hold, equal-weight universe, 20-day trend, random.
   - A "shadow P&L" that adds costs, because Alpaca paper ignores market impact, fees and dividends (https://docs.alpaca.markets/docs/paper-trading).

7. **Copy skills into the repo; don't install plugins.** Pin each to a commit SHA and keep its LICENSE. List in §2.

8. **Bring over Age of Blood's working habits.** Details in §2. ("age of blood" is the user's own private repo, `zarfatinimrod-creator/age-of-blood`. It contains no trading skill.)

9. **Free data first:** edgartools, House trade disclosures, the breadth CSV. Quiver only once the free signals have earned it.

10. **Prompt hygiene, from Alpha Arena's failures.**
    - Feed series oldest to newest with ISO dates. Models misread newest-first data.
    - Python computes all indicators; Claude gets labelled numbers.
    - Version-lock prompts. Models were "highly sensitive to seemingly trivial prompt changes" (https://news.ycombinator.com/item?id=45976832).
    - Treat all external text as data, never as instructions. This rule is missing from Jake's skills **and** from our own `trader` and `trading-desk` skills.

---

## 2. What to adopt

### Skills to copy into the repo

- **tradermonty/claude-trading-skills** (MIT, 3,705★, pushed 2026-11-09): https://github.com/tradermonty/claude-trading-skills
  - Copy: trader-memory-core, signal-postmortem, drawdown-circuit-breaker, position-sizer, pre-trade-discipline-gate, market-breadth-analyzer, uptrend-analyzer, exposure-coach, macro-regime-detector, weekly-performance-digest, backtest-expert, edge-strategy-reviewer.
  - Install: `pip install pyyaml jsonschema requests`.
  - Pitfall: `trader_memory_cli.py` finds the repo root with `parents[3]`, which breaks once copied. Set `CLAUDE_TRADING_SKILLS_REPO`.
  - This subset contains no subprocess calls.
- **ml4t/skills** (Apache-2.0; the skills are Markdown-only): https://github.com/ml4t/skills
  - Install: `scripts/install.sh <dest> --copy`.
  - Keep: lookahead-bias, point-in-time, backtest-overfitting, transaction-costs, cost-model, walk-forward-cv, purging-embargo, cpcv (deflated-sharpe depends on it), deflated-sharpe, sensitivity-analysis, kill-switch, risk-metrics, drift-detection, monitoring-alerting, agent-governance, agent-state-memory.
  - Their `paths:` globs don't match `learn.py` or `metrics.py`. Edit them, or call the skills explicitly from time-machine.
- **Vibe-Trading SKILL.md files only** (MIT): https://github.com/HKUDS/Vibe-Trading `agent/src/skills/`
  - Copy: research-discipline, thesis-tracker, trade-journal, backtest-diagnose, quant-statistics.
  - Use **one** journal schema across all of them (trader-memory-core's YAML).
- **CFA bias-detection** (Apache-2.0): https://github.com/CFA-Institute-RPC/skills/tree/main/skills/bias-detection. Run it on desk theses and on new `lessons.md` entries.
- **Anthropic FSI** `thesis-tracker` and `earnings-preview` SKILL.md (Apache-2.0): templates only.
- **edgartools skill:** `python -c "from edgar.ai import install_skill; install_skill()"`, then copy the folder from `~/.claude/skills/edgartools` into the repo.
- **Jake Schincariol's packs.** I'm about 95% confident these are the "Trader skill" and "מכונת הזמן" (Time Machine) the user named.
  - trader-skill at SHA `5189e79b9a480755a3733ac9713f5353981dbe18`; day-trader-skill at SHA `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd`.
  - MIT, standard-library Python only. The only subprocess is `pdftotext`.
  - Each repo is a single commit that was never updated, so treat them as unmaintained code drops.
  - Put them under `vendor/`. Copy v1 first, then v2, because 7 folder names overlap.
  - **Do not overwrite** our own `ai-trader/skills/{trader,time-machine,trading-desk}`. Rename ours to `strategy-time-machine`.
  - Run their offline tests (175 and 315) before enabling.
  - Don't wire the intraday opening-range flow.
  - `trader-broker`'s SKILL.md walks Claude into placing orders through the Alpaca MCP, so keep it disabled.
- **ECC skills.** Age of Blood's logs show these on the user's PC (they are not in the repo): council (4-voice go/no-go), eval-harness, agent-self-evaluation, silent-failure-hunter, loop-operator. Source: https://github.com/affaan-m/everything-claude-code (MIT). Pin a SHA.

### From Age of Blood (`/home/user/age-of-blood`, `age-of-blood-unity`)

- `web-researcher` agent: every number carries its URL. Already in ai-trader.
- `ponytail.md` (MIT): minimal-code rules.
- `caveman.md`: terse Hebrew style. It is **Apache-2.0, not MIT**, so keep its attribution. Use it for chat replies only; buy/sell alerts stay as full Hebrew sentences.
- `superpowers-bootstrap`: TDD, verification and debugging process skills.
- Builder → critic → judge loop: becomes the **weekly self-review** of predictions against outcomes.
- GateCanary (a test that fails on purpose to prove the gate ran) becomes a **leakage canary**:
  - a signal that peeks at the t+1 return must show an absurd Sharpe;
  - a shuffled signal must show Sharpe ≈ 0;
  - shifting the whole pipeline +1 day must not improve results.
- Stryker mutation testing becomes `mutmut` on `risk.py`. Golden/parity fixtures for the indicators.
- `decisions-unity.md` becomes `state/decisions.md`: date, change, numbers, source, who decided, for every config change.
- The "art-round brake" becomes a research brake: stop after 2 rounds with no gain.
- teamwatch becomes a watchdog: heartbeat every 60s, restart after 2 misses, at most 4 restarts per hour, then a 30-minute back-off.
- Non-urgent questions batched into one daily message at 08:00. The 8-heading Hebrew log format.
- headless-playtest's rule "always sweep; if the conclusion flips, it's sensitivity" (already in time-machine).
- `agentcairn` memory MCP (Apache-2.0, 73★): optional. Its config uses Windows paths, so point `CAIRN_VAULT` at a folder inside the repo.

### Python stack
These installed and ran together on Python 3.13. Use a uv lockfile, and allow **no `pandas<3` package** in the main environment.

```
yfinance==1.8.0 pandas-market-calendars==5.6.0 ta-lib==0.8.3 vectorbt==1.2.0
backtesting==0.6.6 skfolio==1.12.8 quantstats==0.0.86 empyrical-reloaded==0.7.2
scikit-learn==1.9.1 lightgbm==4.7.0 "edgartools[ai]"==5.62.1 pyyaml jsonschema
# optional: alphalens-reloaded==0.5.1 arch==8.0.0 pandas-ta-classic==0.9.0 xgboost-cpu==3.4.1
```

- Our own next-open simulator is the source of truth. vectorbt is for fast screening; backtesting.py and bt are cross-checks.
- Every reported metric comes from quantstats or empyrical, so all numbers share one implementation.
- Licenses: vectorbt is Commons Clause and backtesting.py is AGPL. Both are fine for private use.

### Data and APIs

- **SEC via edgartools** (MIT, 2,844★): call `set_identity("Name email")`. In `.mcp.json`, add `"env":{"EDGAR_IDENTITY":"Name email"}`. Covers Form 4 insider buys, 8-Ks, XBRL financials and 13F. No key needed, but a contact User-Agent is mandatory (data.sec.gov answered 200 from this machine).
- **House trade disclosures:** port `trader-pelosi/ptr.py` (MIT) into `aitrader/alt.py`.
  - Steps: download `{YEAR}FD.zip`, keep FilingType `P`, run `pdftotext -layout` (already installed).
  - Use it as a log-only `congress_ptr` overlay, graded by **filing date**. Disclosures can lag trades by up to 45 days.
- **Breadth regime:** https://tradermonty.github.io/market-breadth-analysis/market_breadth_data.csv (returned 200, data through 2026-11-06).
- **Alpaca paper:** trading at `https://paper-api.alpaca.markets`, data at `https://data.alpaca.markets`.
  - Auth is the `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY` headers or HTTP Basic. Alpaca's docs label both "Legacy", but they are still the only option for trading.
  - Free data plan: real-time IEX only, 200 requests/min. Algo Trader Plus (full SIP) is $99/month.
  - In the cloud: `request_credential(host, suggested_type=basic)` for each host, then plain `requests` with no auth header. Don't use alpaca-py: it sends APCA headers, which the proxy can't replace.
  - Alpaca MCP v2.4.1 is for local or interactive sessions only, with `ALPACA_TOOLSETS="account,assets,stock-data,news"` (no trading toolset).
- **Quiver:** Bearer token auth.
  - Hobbyist $30/month: congress trades, no insider data. Trader $75/month: adds insider trades.
  - Rate-limit groups: 100/min, 10/min, 200/hour, 5/hour.
  - Prefer the claude.ai "Quiver Quant" connector, passed to the scheduled task through `connectors`.
  - **Defer** until the free congress and insider signals prove themselves on paper.
- **Optional:**
  - tradememory-protocol (MIT): borrow its "show past losses first" recall idea. If we run it, set `TRADEMEMORY_TSA=off`.
  - TradingAgents as an on-demand deep dive in its own venv, only for finalists (about 12+ LLM calls per ticker). Pick a pin deliberately: tag v0.7.1 is `c454491`, main HEAD is `9fa1196`.

---

## 3. Avoid, and why

- **Installing as packages:** aihf (needs numpy<2 and pandas<3; fails on 3.13), Vibe-Trading (pandas<3, 59 dependencies), pyqlib (no 3.13 wheels and no sdist), zipline-reloaded (pandas<3), the original pandas-ta (dead upstream; its numba pin downgrades the stack), uni2ts/Moirai (torch<2.5), LEAN (needs Docker), FinRL (stale, broken packaging), backtrader (unmaintained since 2023), plain `xgboost` (about 363 MB including CUDA; use `xgboost-cpu`).
- **License problems:** TradingAgents-CN (proprietary `core/`, `app/`, `frontend/`); HKUDS/AI-Trader (no license, and it tells agents to fetch a remote `SKILL.md`, which is an injection risk); LLM-Trading-Lab and `marketcalls/vectorbt-backtesting-skills` (no license); TimesFM 3.0 weights (non-commercial; stay on 2.5); `sec-edgar-mcp` (AGPL).
- **Dead or empty:** FinCon (no code released), FinMem and FinAgent (last pushed 2024), FinGPT (2023 Llama-2 models), `financial-datasets/mcp-server` (stale).
- **Catalog plugins:** TradeOS, TradingCalc, StockPortfolio.pro, FSI `financial-analysis` (institutional connectors), and the TradingView desktop MCP. They send our data to third parties or don't fit a headless cloud bot.
- **Alpha Arena clones** (nofx, open-nof1.ai, Hyper-Alpha-Arena): leveraged crypto, affiliate incentives, drawdown breakers at 30–50%.
- **Practices:**
  - LLM backtests on dates before the model cutoff.
  - Leverage, margin, shorts or options.
  - Intraday or minute-level trading.
  - Time-series foundation models as a signal. My test found no detectable edge over always guessing "up", and Kronos is stale with only self-reported results.
  - Judging anything on a 2-week window. In Alpha Arena Season 1, a crypto buy-and-hold basket returned about −5.2% while the models averaged −28% to −35%. Their own over-betting caused most of the loss. Per-model figures are unverified.
  - Choosing a model by general leaderboards (LiveTradeBench).
  - Trusting GitHub stars or published Sharpes. TradingAgents reported a Sharpe of 8.21 over 3 months.

---

## 4. Parameters to hard-code (defaults; tune in the time machine)

- **Position limits (long-only, cash):**
  - Per name ≤10%, per sector ≤30%, gross ≤100%.
  - Risk 1% of equity per trade, measured at the stop.
  - Every entry gets an ATR-based stop. The LLM never sets the stop.
- **Trading discipline:**
  - Minimum hold 5 trading days, except stops.
  - Wait 12h after a direction flip. No re-entering a ticker for 10 days after a stop-out.
  - Cap exposure going into earnings and other binary events.
  - Minimum market cap $2B and 20-day average dollar volume ≥$20M (no micro-caps).
- **Halts:**
  - Daily loss ≥3%: no new risk that day.
  - Drawdown tiers: warn at −8%, no new entries at −12%, cut risk at −15%, full halt at −20%.
- **Pre-trade guards:**
  - At most 10 orders per cycle, plus a daily notional cap.
  - Reject an order priced more than 5% from the last close.
  - Refuse to trade on data older than 20 minutes during the session.
  - A `state/HALT` kill-switch file, checked before every order.
- **Costs:**
  - Trade only if expected excess return > 2× the round-trip cost.
  - Shadow P&L: slippage swept at 5/15/30 bps, SEC/TAF fees on sells, no fill above 1% of 20-day volume, dividends credited.
- **Calibration and scoring:**
  - Cap stated probabilities at 0.65. Brier skill = 1 − BS/0.25.
  - Hit-rate standard error = √(0.25/n). With n = 30 the 95% interval is about ±18 points.
- **Learning gates:**
  - Re-weight a signal source only after ≥30 *non-overlapping* graded views with |t| > 2 (or Newey-West with lag = horizon). No auto-tuning before about 100 graded decisions.
  - Veto audit: after ≥30 settled vetoes, if vetoed names did not underperform (one-sided t < −2), switch the desk to log-only.
- **Overfitting checks:**
  - Probability of Backtest Overfitting via CSCV with S = 16 blocks; reject a change if PBO > 0.5.
  - Deflated Sharpe computed over everything logged in `trials.jsonl`.
  - Years to prove an edge = (1.96/SR)². A Sharpe of 0.4 needs about 24 years.
- **Memory retrieval:**
  - Score = similarity + exp(−Δdays/Q) + importance/100, with Q = 3, 90 and 365 for the short, mid and long layers (decay 0.92, 0.967, 0.988).
  - Inject 5 same-ticker records, 3 cross-ticker lessons, and the top losses in similar conditions.
- **ML defaults:**
  - `TimeSeriesSplit(n_splits=5, gap=horizon)`.
  - `LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=15, n_jobs=4)`.
  - Wrap with `CalibratedClassifierCV` before journaling any probability.
- **Realistic targets:**
  - SPY-like returns with smaller drawdowns.
  - A 20-day hit rate vs SPY of 52–55%, sustained, counts as success. Above 60% is more likely a bug or a leak.

---

## 5. Questions only the user can answer

1. May we move `ai-trader` into its own repo? This is the main fix for cloud loading.
2. Are the Jake Schincariol packs (Instagram @opusjake) the "Trader skill" and "מכונת הזמן" you meant? Install both (recommended), only the Time Machine, or only v1?
3. Which contact email should go in the SEC User-Agent (`SEC_USER_AGENT` / `EDGAR_IDENTITY`)?
4. Can you, as an Israeli resident, open an Alpaca paper account? I couldn't verify eligibility. For a later live phase, IBKR is the usual broker for Israeli residents.
5. What's the budget for paid data: Quiver $30 or $75, Alpaca SIP $99, or none? And how many LLM calls per day should we allow (this decides how many tickers get the deep-dive committee)?
6. What paper account size should we assume (Alpaca's default is $100k), and what is your preferred trading horizon?
7. Will the bot or its alerts ever be shared or sold? The Commons Clause and AGPL licenses then need review.
8. The Age of Blood logs mention both "Michael" and "Nimrod". Who makes the decisions, and whose style rules should we copy?
9. May we run Kronos and Jake's test suites? The sandbox blocked running downloaded code.

**Still unverified:** Alpaca eligibility for Israel, the FMP free-tier limit, Financial Datasets pricing, per-model Alpha Arena results, and whether anyone has independently replicated Kronos.
