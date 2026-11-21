# Judge's report: what ai-trader should take from 24 deep reads + 385 catalog repos

**Bottom line.** Not one of the 385 repos shows validated, out-of-sample alpha from an LLM; the famous ones (TradingAgents, ai-hedge-fund, DSA, Vibe-Trading) make no return claims or back-test inside the model's training window. What they do offer is engineering and process discipline, and reading them surfaced **three concrete defects in our own bot** (items 1-3). Everything below must still pass the strategy-time-machine sweep and quant-critic (CLAUDE.md rule 4), and every ported line gets a THIRD_PARTY.md entry.

## 1. Ranked take list (integrate now)

1. **Fix: rebalance band skips risk-reducing trims.** Source: virattt/ai-hedge-fund `brokers/costs.py`, `pipeline/execution.py::build_orders` ("a trim or a close always goes through"). Our `aitrader/broker.py::rebalance` has `if not exiting and abs(tw-cw) < band: continue` with band 0.02, so a Claude `shrink SYM 0.8` on an 8% name (1.6pp delta) silently does nothing. Change: apply `rebalance_band_pct`/`min_trade_value` only when `|target| > |current|`. Sweep before/after.
2. **Fix: learning label credits the overnight gap.** Source: microsoft/qlib `contrib/data/handler.py:152`, `rolling/base.py:166`, `workflow/task/gen.py:307` (label `Ref(close,-(h+1))/Ref(close,-1)`, leak gap 2). Our `learn.py::forward_excess` measures close(d)→close(d+h) but we fill at open(d+1). Change to open(d+1)→open(d+1+h) minus cross-sectional mean; mature rows at `asof_pos-horizon-1`. Rerun `placebo_gate`. Add FinRL-Trading's label assertion (label == return the backtest actually earns) as a test.
3. **Fix: live/backtest parity + holiday bug.** `backtest.py` never applies `earnings_blackout_days`/`earnings_max_position_pct`; `cycle.py::_execute_pending` uses `BDay` (ignores NYSE holidays) while backtest uses the panel index. Source for PIT earnings dates: day-trader-skill `trader-analyst/facts.py::latest_filings` (8-K Item 2.02 `acceptanceDateTime`). Change: `data.py` builds a point-in-time earnings table from 2.02 history; backtest applies the same blackout; cooldown uses the trading-day index.
4. **Hard-code the veto/shrink-only invariant.** Source: ZhuLinsen/daily_stock_analysis `src/agent/risk_override.py` (`_VALID_DOWNGRADE_TRANSITIONS`, reason enum) + ai-hedge-fund `portfolio/validation.py::validate_targets`, `risk/limits.py` ClampEvent. Change: after `_apply_overrides` in `cycle.py`, assert `set(final) ⊆ set(raw)`, `final[s] ≤ raw[s]`, caps, gross; log `clamps[]` and a reason code (anthropics/financial-services kyc-rules pattern: `BINARY_EVENT_5D`, `OFFERING_DILUTION`, `DESK_HOLD`…) in `decisions.jsonl`. Add a test proving each gate CAN reject (nofx's R:R gate was mathematically vacuous).
5. **Untrusted-reader tier for news.** Source: anthropics/financial-services `gl-reconciler/subagents/reader.yaml` + `news-reader.yaml` (schema with `maxLength`, char pattern, enum), `scripts/validate.py`; FinRobot `compute/coordinators/news.py::sanitize_untrusted_text` + `<untrusted_news_item>` wrapper. Change: new `agents/news-reader.md` (WebSearch/WebFetch only, returns validated JSON); bull/bear lose web tools; `desk.brief()` moves headlines under `untrusted_news`, sanitized and length-capped; one critic agent re-verifies any news-driven veto against EDGAR/Nasdaq calendar.
6. **WebSearch canary + offline banner.** Source: xbtlin/ai-berkshire `skills/investment-team.md` step 1.75 (background agents fall back to training memory silently). Change: trading-desk step 2 runs a canary (today's SPY close) before spawning; agents print `OFFLINE` if search failed; PM then caps at Hold, prob 0.50.
7. **Data-quality gate, stale-quote guard, abstain.** Sources: TradingAgents-astock `agents/quality_gate.py::_hard_check_report` (A-F grades), DSA `analysis_context_builder.py` (status scores/weights), atilaahmettaner/tradingview-mcp `yahoo_finance_service._quote_is_stale`, qlib `scripts/check_data_health.py`. Change: `data.py::load_market` quarantines symbols with gaps or |pct_change|>0.5; `live_prices` marks a quote stale if `regularMarketTime` < last candle-86400; `brief()` gets `data_quality` + `missing_fields`; grade D/F → desk emits ABSTAIN (no override, no graded prediction) instead of Hold→×0.5 (ai-hedge-fund `_abstain`).
8. **Residual-edge / factor attribution gate.** Source: tradermonty/claude-trading-skills `residual-edge-analyzer/scripts/analyze_residual_edge.py` (stdlib, Newey-West HAC, verdicts at lines 845-881); OpenBB `quantitative/attribution.py`, `famafrench/utils/constants.py` (FF5+MOM+STR daily zips, values in percent). Change: `metrics.py::residual_edge(daily_ret, baselines)` with pre-declared baselines (SPY, equal-weight universe, 12-1 momentum basket, gross-matched SPY+cash) and FF factors; require alpha NW-t>2 in the time-machine report; quant-critic step.
9. **Scorecard that grades the desk.** Sources: TradingAgents-astock `performance.py` (`rating_monotonicity`, n<20 warnings, direction on excess), ai-hedge-fund `scorecard/analysts.py` (slugging, IC t-stat, n_abstained), tradermonty signal-postmortem taxonomy (re-based on excess vs SPY). Change: `journal.scorecard` adds per-rating table for `source=desk`, a **veto-value line** (20d excess of vetoed vs passed names), slugging, MISSED_OPPORTUNITY/REGIME_MISMATCH tags.
10. **Sealed holdout, PBO, BH, cost break-even.** Sources: HKUDS/Vibe-Trading `research_lab/studies.py::walk_forward` (sealed_plan.json hashes), `quantlib/multipletesting.py` (PBO/CSCV ~100 lines, benjamini_hochberg); QuantDinger `strategy_evolution/statistics.py` (block bootstrap, segment concentration). Change: `backtest.py --holdout-from`, plan hash in `trials.jsonl`, PBO over sweep variants, BH over the 8 signals' IC p-values, break-even bps bracket in the sweep table.
11. **Turnover throttle + shrunk covariance.** Source: qlib `contrib/strategy/signal_strategy.py:74-294` (n_drop, hold_thresh), `model/riskmodel/shrink.py:126-229` (LW constant-correlation; skip OAS). Change: `risk.max_replacements_per_rebalance` (2-4) and `risk.min_hold_days` (5-10) as sweep variants; LW shrinkage for the 60-day covariance in vol targeting.
12. **8-K event classifier in the brief.** Source: day-trader-skill `trader-news/news.py` (`ITEMS_8K`, `IMPORTANT_ITEMS`, `parse_sec_atom`, `dedupe`, 30-day `seen`); OpenBB `sec/utils/ratelimit.py` (9 req/s). Change: `brief()` gets `filings_8k_30d`; `news_headlines` gets tagging + `state/news_seen.json`; SEC rate limiter.
13. **Point-in-time universe mask.** Source: FinRL-Trading `data/sp500_historical_constituents.csv` (1996-2026 daily; verify license) or qlib `scripts/data_collector/us_index/collector.py`. Change: a stock is eligible for NEW entry only while an S&P member; ETFs always; report the return drop as our survivorship bias.
14. **Number grounding lint.** Sources: Vibe-Trading `agent/context.py:223-300` + `grounding/figures.py` (figures block, 0.5% rounding band); FinRobot `audit/report_drift.py`; ai-berkshire `tools/report_audit.py`. Change: `aitrader/grounding.py` resolves every number in desk output/lessons.md against brief JSON/state; `aitrader audit-report` CLI.
15. **Thesis records with tripwires.** Sources: financial-services `thesis-tracker/SKILL.md`, dexter `write-memo/SKILL.md` (asymmetry ≥2x, machine-checkable tripwires), tradermonty `thesis.schema.json` (kill_criteria, time_stop_days, MAE/MFE), ai-berkshire `thesis-tracker.md` health score. Change: `state/theses.jsonl` via `journal.append`; desk gets `--assumption/--redline`, `--invalidation-hard/-soft`; post-close recomputes status in code; score ≤4 → shrink only.
16. **Small hygiene.** Sortino uses `sqrt(mean(min(r-MAR,0)²))` + omega (OpenBB `performance.py`); config sha256 + git sha on every decision (ai-hedge-fund `session.py`, FinRL AuditLog); state snapshot/restore around `cycle` + duplicate-date guard (LIBB `model.py`); proposal fingerprint bound to each override (nofx `plan.go`, day-trader-skill `check.py::fingerprint`); `risk.no_review_policy` when the desk is missing (nofx safe mode); Yang-Zhang vol and Clenow momentum as logged trials only.

## 2. Skills / MCP servers worth installing

- **Already vendored and unused:** Jakeschincariol/day-trader-skill (commit 3d0f4ef). Wire `/trader-analyst` and `/trader-news` into `skills/trader/SKILL.md`; keep `trader-broker` excluded; run its tests in a sandbox once.
- **Vendor two files only** from tradermonty/claude-trading-skills @163ceb48: `analyze_residual_edge.py` (stdlib) and `edge-strategy-reviewer/assets/bias_checklist.yaml` (into quant-critic). Do not install trader-memory-core/circuit-breaker/exposure-coach (second source of truth; `uv run` self-exec).
- **Port text, don't install** anthropics/financial-services equity-research skills (thesis-tracker, catalyst-calendar, morning-note). The financial-analysis plugin registers 11+ paid MCPs.
- **No MCP is needed for the trading loop.** For Nimrod's ad-hoc questions, keyless and localhost-only candidates: `claude mcp add sec-edgar -- uvx sec-edgar-mcp` (stefanoamorelli), `narumiruna/yfinance-mcp`, `btopn/OpenInsider-MCP`. Catalog-only, not deep-read: verify before use.
- **Deep-read next (catalog only):** quantskills/skill-backtest-overfit (DSR/PBO/MinTRL), botjockie-lab/lookahead-detector, fangdididi/backtest-autopsy, valuein/valuein (PIT fundamentals incl. delisted), LuxAlgo/market-trackers, waylonli/FINSABER (evidence LLM strategies lose long-run), rakeshchada/portfolio-autopsy (reflection hurt quality).

## 3. Designs to port as Claude-run prompts

**Trading-desk upgrade (TradingAgents roles, our rules):**
- Analysts first list 2-4 cited factors `[Positive]/[Concerns]` (FinGPT `data.py` schema), with as-of dates on every number (Vibe `context.py:34-75` output principles; worker.py citation rule).
- Bull/bear stay independent round 1, then **one sequential rebuttal** (astock `conditional_logic.py`); in later rounds a side may only answer `unchanged|softened`, never `reversed`; softening ×0.9, floor 0.3 (DSA `deliberation.py`). Add FinGPT's consistency rule: if bull/bear probs differ >0.25, pull the 8-K/10-Q before the PM step.
- Research manager outputs `{view, confidence, core_evidence[3-5], uncertainties, invalidation_conditions, watch_items}` and a disagreement block (`conflict_type`, `decision_path_hint`; DSA `disagreement.py`). Rewrite TradingAgents-CN's version in our words (proprietary paths).
- Step 4.5: **Munger inversion**, veto-only (Vibe `investor-lenses/references/munger-inversion.md`: ≥5 failure paths from distinct families, each with trigger); plus Druckenmiller "deteriorating fundamentals + leverage = pass" (ai-hedge-fund personas) as red-flag lenses, never bullish voters.
- Risk officer scores each bull/bear point 1-5, lists blind spots, states a size cap (Vibe `investment_committee.yaml`); sorts risks confirmed/to-verify/hypothetical → veto/shrink/ignore (astock risk_manager).
- PM returns QuantDinger's typed 5-check schema (`data_quality, signal_alignment, market_regime, risk_check, execution_quality`, probabilities summing to 1, min confidence 0.55): `block`→veto, `caution`→shrink, `insufficient` never vetoes. Each veto carries `reassess_when` (nofx deferred contract) and FinRobot judge's `swing_factor`/`change_my_mind`.
- Bias check: run PM once on the named brief and once blind (ticker/dates withheld, series indexed to 100; ai-hedge-fund `_render_blind`); log flips.

**Post-close review:** four lenses (timing, sizing, discipline, attribution computed in code with beta vs SPY and sector ETF; TradingAgents-CN design), 2-4 sentence reflection citing alpha (astock), deterministic issue codes before any LLM annotation (QuantDinger `strategy_review_evidence.py`), ReviewMemory injected only at PM step after ≥10 graded outcomes, slug-sanitized (DSA), behaviour tags for Claude's overrides (tradermonty, Vibe `trade_journal_tool.py`).

**Weekly signal-research session:** RD-Agent `core/proposal.py` trace (`state/research_trace.jsonl`), proposal rules from `scenarios/qlib/prompts.yaml` (1-5 simple factors, never re-implement library factors), Spearman dedup at 0.7 + marginal IC, test inside the ensemble not alone, tradermonty hypothesis card with kill_criteria and banned phrases, graveyard entries counted in DSR trials.

**Alert discipline:** dexter heartbeat suppression regexes and `HEARTBEAT_OK`; morning note opens with yesterday's graded call.

## 4. Skip, and why

- **The-Swarm-Corporation/AutoHedge**: ~1k lines of generic prompts, LLM-made VaR, unattached hot-wallet swap tool, broken historical pipeline. Nothing to learn.
- **tradesdontlie/tradingview-mcp**: needs a GUI TradingView Desktop; `ui_evaluate` runs arbitrary JS in the logged-in session; ToS forbids algorithmic use.
- **ValueCell**: crypto-perp loop, no backtester, risk flags referenced but never computed. Keep only the prompt-contract test idea.
- **Kronos**: competent forecaster, zero US evidence, only ~16 months of guaranteed-unseen data; defer the sidecar until core fixes land.
- **nofx code** (AGPL): re-implement the replay-harness idea only. **TradingAgents-CN** `core/`, `app/`, bootstrap prompts: proprietary, design reference only.
- **Strategy content**: DSA `strategies/*.yaml` (A-share TA lore), qlib DDG-DA/RL, FinGPT models, DCF/LBO operators, TradingView scanner ratings (not point-in-time), breadth CSV in backtests (survivorship + find_peaks look-ahead), intraday ORB skills, replay-practice (Claude grading remembered history), trade-order Monte Carlo (uninformative), 478-alpha zoo mining.
- **Anti-patterns to keep out**: LLM sizing or quantities, keyword/regex parsing of free text into orders, Sharpe-banded self-feedback on a handful of trades, hindsight-rationalized labels, "any small improvement = SOTA".
- **GouveRoger12/milan-capital** is a malware lure; never download.

## 5. Catalog (385 repos)

Cat: MA=llm-multi-agent, SA=llm-single-agent, SK=claude-skill/plugin, MCP, QF=quant-framework, RP=research-paper, DT=data-tool, O=other. ★ = deep-read.

| Repo | ★s | Cat | Why |
|---|---|---|---|
| virattt/ai-hedge-fund ★ | 64584 | MA | shrink-only risk stages, scorecard, blind render |
| ZhuLinsen/daily_stock_analysis ★ | 68402 | SA | risk-override contract, data-quality score |
| HKUDS/Vibe-Trading ★ | 37931 | SA | figures grounding, sealed walk-forward, PBO |
| virattt/dexter ★ | 27802 | SA | memo self-critique, heartbeat suppression |
| chrisworsey55/atlas-gic | 2434 | MA | autoresearch scored vs outcomes |
| chase-manning/ai-hedge-fund | 97 | SA | Claude proposes, code disposes |
| HimanshuMohanty-Git24/RakshaQuant | 72 | SA | veto-only AI experiment |
| pradnyaw25/ai-portfolio-manager | 1 | MA | PM must answer bear case |
| 45ck/llm-quant | 48 | SA | Claude PM, HMM regime prompt |
| az9713/self-improving-trading-agent | 2 | SA | weekly S&P rebalance, signal plugins |
| alex-jb/orallexa-ai-trading-agent | 73 | MA | bull/bear/judge, adaptive weights |
| tradermonty/claude-trading-skills ★ | 3705 | SK | residual-edge analyzer, bias checklist |
| Jakeschincariol/day-trader-skill ★ | 6263 | SK | already vendored; 8-K parser |
| mnemox-ai/tradememory-protocol | 1441 | MCP | memory/brake for agents |
| LuckyOne7777/LLM-Trading-Lab ★ | 7548 | SA | failure-mode record, behaviour metrics |
| TraderAlice/OpenAlice | 7442 | O | local Claude Code orchestrator |
| ginlix-ai/LangAlpha | 2254 | SA | thesis + invalidation as Bayesian |
| kyky2347/ALTA | 1076 | MA | evidence-first research firm |
| ZhuLinsen/alphaevo | 214 | QF | self-evolving YAML strategies |
| renee-jia/trading-bot | 93 | QF | 0-100 conviction ensemble |
| zubair-trabzada/ai-trading-claude | 323 | SK | 16 skills, 5 subagents, keyless |
| AI4Finance-Foundation/FinRobot ★ | 8396 | MA | evidence-ID prompts, news sanitizer |
| HKUDS/AI-Trader | 23199 | O | agent paper-trading arena |
| pipiku915/FinMem-LLM-StockTrading | 971 | RP | layered memory paper |
| LLMQuant/awesome-trading-agents | 990 | O | curated list |
| YizhiSong/FriesTrader | 301 | SK | two scheduled sessions/day |
| UncertaintyDeterminesYou4ndMe/flintrade | 8 | SA | code disposes, revenge cooldown |
| jkspeaks/deterministic-trader | 2 | SA | Claude is hands only |
| highwatermark/apex | 1 | SA | cron-woken Claude sessions |
| pedrobraiti/vizier-trading-skill | 8 | SK | thesis memory across sessions |
| qrak/LLM_trader | 141 | SA | public ledger, rejected signals |
| longsizhuo/openInvest | 139 | MA | isolated committee agents |
| HephaestLab/TraderHarness | 42 | QF | leakage-resistant LLM backtest |
| ryanfrigo/kalshi-ai-trading-bot | 650 | SK | Brier/log-loss edge layer |
| kevmyung/swing-trading-agent | 26 | MA | quant screen → research → risk |
| ProjectDXAI/continuous-record-llm-trading-agents | 51 | RP | 6 months in production |
| The-FinAI/FinCon | 72 | RP | manager-analyst, verbal reinforcement |
| AskElira/newswave | 4 | SA | claude CLI classifies news only |
| staskh/trading_skills | 406 | SK | scanners, Greeks |
| wshobson/maverick-mcp | 721 | MCP | keyless Yahoo tools |
| huygiatrng/AlpacaTradingAgent | 284 | MA | TradingAgents on Alpaca |
| caius72/berkshire | 0 | SK | roles as Claude subagents |
| malda231125/TradingAgents-KR | 8 | MA | per-decision self-improvement |
| yaorenliang/trading-agents-skill | 2 | SK | TradingAgents as one SKILL.md |
| 0-Captain/trading-analysis-skill | 0 | SK | 12 roles as subagents |
| Caesar-ZZh/cosmos | 7 | MA | decision-evaluation layer |
| hsliuping/TradingAgents-CN ★ | 32856 | MA | post-mortem lenses; mixed license |
| simonlin1212/TradingAgents-astock ★ | 3937 | MA | quality gate, rating monotonicity |
| KylinMountain/TradingAgents-AShare | 893 | MA | claim-ID debate |
| TNT-Likely/PanWatch | 2415 | MA | portfolio-first TradingAgents |
| MarvekG/BestAITrader | 45 | MA | living markdown memory |
| Skopaq-AI/skopaqtrader | 22 | MA | Indian fork via MCP |
| Erinqi/tradingagents-codex-native | 15 | SK | stdlib codex port |
| namikos/claude-tradingagents | 0 | SK | plugin port + personas |
| lucemia/trading-agents-plugin | 14 | SK | original slash-command port |
| chenhab03/multiagent-stock-research | 0 | SK | 3-round debate |
| cuteyuchen/TradingAgents-HoldingsSkill | 2 | SK | holdings-level skill |
| Kiyo5hi/quanterback | 1 | MA | Alpaca paper harness |
| dbbbbm/kimi-stock-agent | 12 | SA | public trading diary |
| PYJ0915/Stock_agent | 0 | SA | 4-stage Claude pipeline |
| davidalmeida90/glassbench | 31 | O | 3 frameworks side by side |
| jinicoding/samsung-stock-agent | 1 | SA | self-evolving analyst |
| jiwoomap/TradingAgents-Dashboard | 15 | MA | Obsidian memory |
| Roisters/trading-agents-claude | 0 | SK | engine + fact checker |
| Oft3r/agentic-trading-desk | 333 | SK | AI fetches, stdlib scores |
| anthropics/financial-services ★ | 41166 | SK | reader/critic tiers, thesis tracker |
| fangdididi/backtest-autopsy | 0 | SK | 8-layer backtest audit |
| deBilla/project-10x-trader | 0 | SA | LLM intraday lost 50% |
| ivanprague90/claude-trader | 0 | SA | four fresh daily wake-ups |
| Jakeschincariol/trader-skill | 1578 | SK | 13F copycat, stdlib |
| himself65/finance-skills | 3517 | SK | finance data skills |
| ml4t/skills | 41 | SK | WRONG/CORRECT leakage patterns |
| tradermonty/hermes-trading-research-agent-work-package | 49 | SK | always-on research routines |
| samchatterley/investor-bot | 2 | RP | pre-registered LLM-value study |
| kensongan-prog/trading-advisor | 2 | SA | 12-gate doctrine |
| questflowai/investorskills | 1916 | SK | investor-method packs |
| frizille/trading-performance-and-risk | 0 | SK | stdlib risk metrics |
| alpacahq/alpaca-mcp-server | 1072 | MCP | official, paper default |
| intoApex/tas-guard | 0 | MCP | proxy guard before Alpaca |
| pedrobraiti/agentic-trading-mcp | 14 | MCP | IBKR/crypto execution |
| pedrobraiti/market-research-mcp | 7 | MCP | 62 keyless tools |
| btopn/OpenInsider-MCP | 104 | MCP | Form 4, 8-K, dilution |
| jsconiers/quiver-quant-mcp | 1 | MCP | keyless Quiver feeds |
| liquid-public/coinvest-mcp | 0 | MCP | thin execution proxy |
| osauer/canary | 11 | MCP | IBKR risk desk |
| FarzamHejaziK/claude-investment-assistant | 9 | SK | markdown strategies + Alpaca |
| massive-com/mcp_massive | 401 | MCP | Polygon official, key |
| stefanoamorelli/sec-edgar-mcp | 386 | MCP | keyless EDGAR |
| Alex2Yang97/yahoo-finance-mcp | 368 | MCP | full Yahoo MCP |
| financial-datasets/mcp-server | 2321 | MCP | paid data |
| alphavantage/alpha_vantage_mcp | 226 | MCP | free key |
| daniel3303/Equibles | 243 | MCP | self-hosted SEC/13F store |
| stefanoamorelli/fred-mcp-server | 131 | MCP | FRED macro |
| atilaahmettaner/tradingview-mcp ★ | 5244 | MCP | stale-quote guard; fake "debate" |
| code-rabi/interactive-brokers-mcp | 228 | MCP | IBKR TS |
| tastytrade/tastytrade-mcp | 37 | MCP | official, dry-run gate |
| waylonli/FINSABER | 153 | RP | LLM strategies lose long-run |
| BichengWang/RL-pricing | 339 | RP | reproducibility lab |
| liuyime2/autopoiesis | 0 | SA | rule first, LLM override w/ reason |
| ChenYXxxx/stockbench | 186 | RP | post-2024 Dow benchmark |
| felis33/INVESTOR-BENCH | 35 | RP | ACL benchmark |
| ulab-uiuc/live-trade-bench | 167 | RP | forward-only live eval |
| HKUSTDial/DeepFund | 303 | MA | short role prompts |
| Harvard-AI-and-Robotics-Lab/TradingAgent | 1 | MA | TrustTrade |
| FinStep-AI/ContestTrade | 680 | MA | internal agent contest |
| Y-Research-SBU/QuantHarness | 2894 | MA | HFT; off-horizon |
| microsoft/RD-Agent ★ | 15295 | RP | research-loop trace format |
| rozwer/Qlib-with-Claudex | 4 | SK | Claude drives Qlib |
| QuantaAlpha/QuantaAlpha | 1654 | RP | self-evolving factor mining |
| RndmVariableQ/AlphaAgent | 431 | QF | factor DSL + FactorZoo |
| Yanlewen/TradeTrap | 83 | RP | injection stress tests |
| wquguru/nof0 | 2754 | O | Alpha Arena crypto |
| MingyuJ666/Stockagent | 717 | RP | market simulator |
| AI4Finance-Foundation/FinGPT ★ | 21542 | RP | PIT basics.py; weak forecaster |
| dragon1086/prism-insight | 795 | MA | 13-agent live report |
| Bader-Aloqily/claude-code-stock-picker | 11 | SK | weekly picks + memory |
| AshJha0/agentic-trader | 17 | MA | desk + rules incumbent |
| KCNyu/clawock | 23 | SK | AI argues, code settles |
| kingabzpro/BetterTradingAgents | 36 | MA | 6 parallel analysts |
| rahulmkarthik/AlphaCouncil | 10 | MA | committee as risk overlay |
| bettyguo/agent-backtest-lab | 7 | O | leakage firewall |
| ParadooxAI/TradeLens | 8 | RP | cost of agent intelligence |
| JingHao-Leon/dsh-alpha-desk | 168 | SK | research desk pack |
| ZhuLinsen/alphasift | 432 | DT | YAML filters for agents |
| OpenByteInc/QuantDinger ★ | 13646 | QF | typed veto schema, PBO stats |
| Lumiwealth/lumibot | 2219 | QF | backtest=paper=live class |
| olaxbt/ai-market-maker | 2108 | MA | risk guard veto |
| EthanXiang777/circuit-framework | 244 | MA | deterministic gate after PM |
| BijectiveLabs/bitra | 47 | SA | typed judge |
| general-liquidity/gordon | 17 | SA | deny-first harness |
| yanziqing25/Tragent | 100 | MA | research + critic |
| Agentic-Analyst/stock-analyst | 130 | SA | code owns every number |
| myc0576/SmartMoney-Cub | 26 | O | read-only journal harness |
| simonro/Trading-Journal-AI | 110 | O | SQLite journal metrics |
| cruisekkk/trading-ledger | 5 | SK | thesis/stop at entry |
| gael55x/LayeredMemoryTrader | 35 | MA | TradingGPT memory |
| minihellboy/factorminer | 128 | RP | symbolic alpha search |
| Open-Finance-Lab/AgenticTrading | 891 | RP | survey + lab |
| TauricResearch/Trading-R1 | 607 | RP | Tauric research terminal |
| yebof/quant-agent | 14 | MA | Alpaca paper, 8 agents |
| jtfernandezi/stocks-investment-agent | 0 | MA | headless weekly audit |
| dylanmccavitt/agentic-trader | 1 | SA | headless claude -p |
| simonro/ai-research-desk | 8 | MA | claude CLI teams |
| m-np/RobinhoodTrader | 0 | SA | thesis gates buys |
| youngseongshin/thesis-investment-os | 15 | O | offline accountability |
| flysheep-ai/NoAlpha | 3 | O | leakage-resistant eval |
| rajib2k5/llm-lookahead-probe | 0 | O | masked vs unmasked |
| Pangqiang-Gary/tradingagents-blind-eval | 0 | O | forward blind harness |
| Toomi16011601/tradeoff | 2 | O | intent vs execution evidence |
| Handshakeworm/TradeHive-TradingAgents | 3 | MA | hard code + soft LLM |
| Hydr0neFN/trader | 1 | MA | retired, honest post-mortem |
| Reformatic-ai/repete-bot | 0 | SA | daily paper swing |
| udayjain2102/agentic-paper-trading | 0 | SA | rules vs LLM side by side |
| kirosli00tuff/AiTrader | 2 | MA | multi-LLM consensus |
| joesaiagent/claude-portfolio | 1 | SA | one Haiku call/day |
| vikd1000/investment-council | 84 | SK | 21 persona council |
| xbtlin/ai-berkshire ★ | 17066 | SK | WebSearch canary, thesis schema |
| flash131307/multi-agent-investment | 207 | MA | FinBERT + RAG |
| simonlin1212/global-stock-data | 1849 | DT | zero-auth US data |
| fafawlf/thesis-agent | 1 | MA | LLMs reason, math decides |
| saifkn1ai/wasptrader | 0 | SK | TradingAgents without key |
| lxcong/TradingFlow | 4 | SK | pipeline as workflow script |
| UnbelievableT/topxai-equity-research | 0 | SK | append-only call ledger |
| AhSirJoe/agentic-investing-stack | 0 | SK | numbers locked pre-debate |
| Kantamaniprakash/trading-agents-lab | 0 | RP | anonymized reproduction |
| alfred1994/alpha-pilot | 32 | SA | self-healing paper loop |
| HenryLinyy/hedge-fund-committee | 8 | SK | data-sufficiency rating |
| xiongcp/stock-skill | 114 | SK | LLM never guesses prices |
| ShousenZHANG/trading-copilot | 0 | SK | MCP + SQLite journal |
| yangchiehkang/PortfolioResearchCockpit | 0 | MA | five gates after AI |
| xzliuxz/Trading-agents-extension | 0 | MA | pit_guard, fact_checker |
| oficcejo/aiagents-stock | 2080 | MA | Chinese analyst team |
| qusong0627/QuantMind | 1896 | QF | Qlib + RD-Agent |
| jundizhou/easy-stock | 1794 | O | A-share workbench |
| run-bigpig/jcp | 1321 | MA | think-tank desktop |
| lzwme/finance-quant-skills | 477 | SK | A-share skills |
| liangdabiao/Claude-Code-Stock-Deep-Research-Agent | 378 | SK | 8-phase due diligence |
| guangxiangdebizi/TradingAgents-MCPmode | 340 | MA | agents via MCP |
| 0xethanq/astra-quant-agent | 413 | MA | crypto committee + Python risk |
| edinetdb/dexter-jp | 317 | SA | dexter for Japan |
| Hi-Zgc/PersonalTradingAgents | 23 | MA | starts from holdings |
| mrhustlex/TradingSpy-TradingAgentService | 51 | O | loop engineering |
| krish-shahh/quorum | 0 | SK | Claude-Code-only, hooks |
| aabrole/claude-trading-desk | 36 | SK | three-arm honest testing |
| christianjohnston-ai/claude-paper-trading | 1 | SK | daily paper-morning loop |
| Gussyy/claude-autotrade | 0 | SK | LLM-free MCP, Claude brain |
| ilasek/trading-autoresearch | 4 | QF | Karpathy loop |
| naplesblue/riskbound | 23 | QF | evidence-boundary sizing |
| austin-starks/Public-Portfolio-Challenge | 82 | MA | real $25K runbook |
| rgg81/crypto-trade-claude-code | 2 | SK | single SKILL.md desk |
| quantskills/skill-backtest-overfit | 41 | SK | DSR, PBO, MinTRL |
| zhangsensen/backtest-analysis-skill | 7 | SK | backtest profiler |
| y0n1n1/financial-skills | 1 | SK | disprove-a-thesis tools |
| lucemia/investment-autoresearch | 5 | SK | parallel hypothesis agents |
| nikosmitsopoulos/trading-routine | 0 | SA | scheduled routines |
| alexlarcheveque/bull-trading-routine | 0 | SA | pre-flight guardrail |
| galleonlabs/hypergrok-trading-desk | 450 | SK | 7 roles, 17 skills |
| agiprolabs/claude-trading-skills | 516 | SK | 68 skills, walk-forward |
| brainbytes-dev/everything-claude-trading | 135 | SK | 18 role prompts |
| yennanliu/InvestSkill | 281 | SK | prompt-only frameworks |
| apeabody007/Quant-toolkit | 3 | SK | calibration audit |
| ThesisInstitute/thesis | 4 | SK | Brier forecasting harness |
| komako-workshop/digital-oracle | 910 | SK | macro probabilities |
| star23/Day1Global-Skills | 1063 | SK | sentiment/positioning |
| HimanshuJ16/Algo-Trading-Skills | 50 | SK | 501 tested skills |
| zjzJoez/trading-agent | 3 | MA | Moomoo paper, RAG |
| narumiruna/yfinance-mcp | 208 | MCP | keyless yfinance |
| ferdousbhai/investor-agent | 348 | MCP | hosted keyless research |
| dgunning/edgartools | 2844 | DT | EDGAR library |
| LuxAlgo/market-trackers | 44 | DT | 18 keyless datasets |
| JakeNesler/OpenProphet | 116 | SA | heartbeat loop, Alpaca |
| Stepuuu/portfolio-daily-tracker | 47 | O | journal + research |
| jkoelker/schwab-mcp | 68 | MCP | read-only, human approval |
| marc-shade/world-intel-mcp | 1066 | MCP | macro composite |
| OpenBB-finance/OpenBB ★ | 75262 | DT | factor attribution, free feeds |
| mphinance/momentum-mcp | 31 | MCP | keyless scan tools |
| mphinance/alpha-skills | 32 | SK | companion skills |
| quant-sentiment-ai/claude-equity-research | 754 | SK | research plugin |
| tradesdontlie/tradingview-mcp ★ | 7127 | MCP | desktop bridge; skip |
| jackson-video-resources/claude-tradingview-mcp-trading | 617 | SA | one-shot prompt with caps |
| MangroveTechnologies/mangrove-agent | 7 | MCP | guardrails MCP |
| cplj/axiocairn-mcp | 101 | MCP | backtest-discipline tools |
| tradermonty/finviz-mcp-server | 62 | MCP | Finviz (paid) |
| Hellek1/ib-mcp | 19 | MCP | read-only IBKR |
| rcontesti/IB_MCP | 141 | MCP | IBKR Web API |
| imbenrabi/Financial-Modeling-Prep-MCP-Server | 149 | MCP | 267 FMP tools |
| twelvedata/mcp | 86 | MCP | official Twelve Data |
| erikmaday/unusual-whales-mcp | 78 | MCP | options flow (paid) |
| hanlulong/openecon-data | 92 | DT | macro indicators |
| kjpou1/forexfactory-mcp | 15 | MCP | economic calendar |
| upstash/botstreet | 112 | SA | Claude PM in scheduled box |
| dabeille/jerome | 1 | SA | quant + LLM veto |
| aahl/ai-trading | 6 | SA | GitHub Actions Claude |
| MTMQuantAI/Agent-Trading-Arena | 147 | RP | agents prefer text |
| horizon-llm/AlphaQuanter | 81 | RP | RL single agent beats multi |
| The-FinAI/Agent_Market_Arena | 9 | RP | live benchmark |
| xsunsim/AgentStockBenchmarkResults | 17 | RP | daily arena incl. Claude |
| benstaf/lookaheadbench | 8 | RP | memorization alpha decay |
| finbrain-lab-hkustgz/AlphaForgeBench | 21 | RP | sandboxed factor bench |
| mamawai/wtfibought | 143 | SA | BYOK live arena |
| KairosPan/gravit-agent | 2 | SA | strategy lifecycle yaml |
| CamusGIT/EvoQuant | 144 | O | research wiki ideation |
| AI4Finance-Foundation/FinRL-Trading ★ | 3922 | QF | PIT S&P CSV; buggy engine |
| benstaf/FinRL_DeepSeek | 332 | RP | LLM risk modulates RL |
| shiyu-coder/Kronos ★ | 47380 | RP | K-line model; shadow only |
| LLMQuant/quant-mind | 3126 | DT | typed knowledge |
| harrypapadakis/StockSim | 40 | RP | LLM + algo sim |
| effective-p/FinAgent | 4 | RP | reimplementation |
| paperswithbacktest/pwb-alphaevolve | 132 | RP | AlphaEvolve strategies |
| ScottDongKhang/Ascent_Capital | 5 | MA | sleeves + Claude PM |
| BichengWang/financial-agent | 47 | QF | earn way to capital |
| kohoj/finstack | 8 | SK | sense/judge/act skills |
| Codehagen/hodget | 21 | MA | one-way stages |
| OpenTradeOSS/OpenTrade | 248 | SK | self-scheduling harness |
| 2033121/astock-trading-agents | 4 | MA | 15-role LangGraph |
| ymj8903668-droid/trading-review-wiki | 293 | O | predict then validate |
| El-Bach/claude-trader | 27 | MA | 14 agents on MT5 demo |
| SilvioBaratto/optimizer | 177 | QF | skfolio optimizes |
| iAmGiG/OptionsCommander | 23 | O | Alpaca paper routines |
| howdymary/autopredict | 110 | QF | proper scoring rules |
| l3lackcurtains/trading-ops | 58 | SK | dated verdicts |
| Shali12/ASTP-Autonomous-Swing-Trading-Pipeline- | 6 | SA | screen + SignalTracker |
| The-Swarm-Corporation/AutoHedge ★ | 6662 | MA | skip |
| ValueCell-ai/valuecell ★ | 11054 | MA | reference only |
| jason8745/llm-agent-trader | 498 | SA | bar-by-bar LLM (leaky) |
| FareedKhan-dev/multi-agent-trading-system | 121 | MA | notebook re-impl |
| ischencheng/Attention-Agent | 99 | RP | time-gated evidence |
| Ashwin-Iyer1/GPTvsGeminiTrader | 2 | O | frozen decisionAt |
| hugoguerrap/crypto-claude-desk | 102 | SK | markdown desk |
| zhound420/swarm-trader | 64 | MA | 20-analyst fork |
| 7thDrag0n/AutoEvolve | 11 | O | FreqTrade loop |
| ivebotunac/PrimoAgent | 388 | MA | 4-agent signals |
| jackson-video-resources/paperclip-zero-human-trading-firm | 137 | SK | 6-agent firm prompt |
| GouveRoger12/milan-capital | 59 | O | MALWARE LURE |
| PkLavc/Autotrader | 35 | QF | close-decide, next-open fill |
| PredictionMarketTrader/openthomas | 25 | SA | risk engine disposes |
| merjua14/ai-momentum-trader | 25 | SA | claude CLI, one pick |
| 0xArchiveIO/0xarchive-quant | 93 | SK | trial ledger |
| mirror29/inalpha | 53 | MA | Rank IC governance |
| SilentFleetKK/riskguard | 68 | O | dependency-free risk layer |
| sonhany/xuanji | 22 | QF | retired AI control plane |
| kbhujbal/AlphaAnalyst-open-source-autonomous-equity-research-agent | 51 | MA | LLM writer not knower |
| byteseek/Mira | 284 | SK | operating contracts |
| Benboerba620/daily-watchlist | 66 | SK | keyless watchlist |
| rollingSirius/TradeGit | 12 | SK | trade journal skill |
| sbauwow/schwagent | 29 | MA | quant scan + LLM overlay |
| arimanyus/warrenduffer | 103 | SA | code sizes |
| heranliu/AlphaResearchOS | 112 | QF | Codex CLI research |
| wanshuiyin/ARIS-Anything | 58 | SK | auto research in sleep |
| joansongjr/investor-harness | 27 | SK | anti-invented-data |
| immortalhowwl/gptheist | 76 | MA | ten-agent veto chain |
| alpacahq/alpaca-skills | 165 | SK | official Alpaca skills |
| microsoft/qlib ★ | 50151 | QF | label fix, throttle, shrinkage |
| NoFxAiOS/nofx ★ | 13243 | SA | replay design; AGPL |
| Mach-Chan/trading-panel | 0 | SK | claude -p as endpoint |
| TLSRUF/ai-trader-team | 3 | SK | personas → deterministic |
| YutaroSugaya/stock-bot | 0 | O | isolation test on orders |
| BlackmodeN/trading-agents-java | 281 | MA | two-layer memory |
| cyecho-io/A-Daily-TradingAgents | 64 | MA | machine scoring first |
| bmigette/BA2TradePlatform | 12 | MA | experts vs brokers |
| joshua-jingu-lee/ante | 4 | QF | py3.13 engine |
| KelvinYou/ai-stock-analysis | 1 | MA | Agent SDK pipeline |
| RaviRanjan0812/tradingagents-reproduction | 1 | RP | PIT reproduction |
| AoleiC/ai-mock-trade | 32 | SK | code runs state machine |
| alphacat0/tesuta-stock-judge | 1 | SK | single SKILL.md rules |
| shaohk/TradingAgents-CN-SKILL | 20 | SK | 13 subagents |
| gonewx/TradingAgents | 13 | SK | early Claude port |
| simonguo/evidenceloom | 33 | MA | saves sanitized inputs |
| Shadowell/Alpha | 35 | SA | candidate funnel |
| FeiCoder/BreadFree-Simu | 166 | QF | daily LLM committee |
| pradeepsiddappa/indian-trading-agent | 32 | MA | daily verdict |
| IvanWng97/TradingAgents-Telegram | 47 | O | watchlist wrapper |
| keerhee/ai-native-hedge-fund | 0 | RP | KR case study |
| katsushi2441/TradingAgents-JP | 0 | MA | JP implementation |
| ajtgjmdjp/japan-trading-agents | 0 | MA | archived JP |
| HuaYaoAI/FinGenius | 2720 | MA | research-battle env |
| 24mlight/A_Share_investment_Agent | 2489 | MA | debate room |
| PatrickSUDO/fadacai-portfolio | 145 | SK | journal-lessons loop |
| Saivikaskillamsetty/tradingdesk | 0 | MA | narrow subagents |
| tycoon2323/investment-committee | 3 | SK | CIO + 10 subagents |
| fjordskii/sidecar | 0 | SA | mandate + journal |
| GirishVerm/ai-hedge-fund | 0 | MA | Claude agents on Alpaca |
| rakeshchada/portfolio-autopsy | 0 | RP | reflection hurt quality |
| botjockie-lab/lookahead-detector | 1 | SK | 12-point lookahead audit |
| highwatermark/cortexcore | 0 | MA | code decides |
| highwatermark/reward_hacking_research | 0 | RP | documented reward hack |
| kurarensu777-sys/ralph-for-hedge-fund | 0 | O | write-scope guard |
| Yijia-Xiao/FinanceHarness | 215 | RP | Tauric research harness |
| quantskills/quantskills | 2618 | SK | skills registry |
| reddygopalkrishna/tradingkit-skills | 1 | SK | tested deterministic numbers |
| VictorVVedtion/trading-skills | 24 | SK | tilt detector |
| truongdatdev/junto | 2 | MCP | local committee |
| AlphaGBM/investment-masters | 637 | SK | 15 manager methods |
| JoelLewis/finance_skills | 223 | SK | TWR/MWR math |
| Kulaxyz/self-learning-skills | 969 | SK | saves golden paths |
| smetaninatv/the-bull-claude-trading-routine | 14 | SK | IBKR routines |
| Blave-TW/blave-agent | 333 | QF | idea → backtest → paper |
| ALAGENT-HKU/x2strategy | 283 | RP | paper → strategy spec |
| NatBrian/auto-research-finance | 0 | MA | markdown state board |
| Trade-With-Claude/cbt-framework | 78 | QF | walk-forward commands |
| johnamcruz/futures-trading-harness | 1 | SA | code facts, markdown skills |
| chiefsmurph/alpaca-ai-agents-hackathon | 1 | SA | bounded AI overlay |
| alidaftar1/robinhood-agent | 6 | SA | shortlist gate + momentum |
| satyamdas03/alpaca-trading-agent | 2 | SA | stateless scheduled sessions |
| trycoin-ai/agentrisk | 3 | MCP | YAML fail-closed gate |
| jinxiy1104/MockTrader_MCP | 9 | MCP | sandbox with costs |
| valuein/valuein | 4 | DT | PIT survivorship-free fundamentals |
| mphinance/awesome-broker-mcp | 1 | O | broker directory |
| BlockRunAI/awesome-finance-mcp | 259 | O | MCP list |
| xang1234/stock-screener | 417 | MCP | keyless screens |
| grahammccain/chart-library-mcp | 23 | MCP | free remote market_state |
| lzinga/us-gov-open-data-mcp | 112 | MCP | gov APIs |
| bxxd/mcp-edgar-ux | 4 | MCP | filings to disk |
| danishashko/yahoo-finance-mcp | 24 | MCP | read-only Yahoo |
| naga-k/mock-rh-mcp | 1 | MCP | paper broker mirror |
| talocode/tradia | 2 | O | proposals w/ invalidation |
| openpitkit/officer | 3 | MCP | pre-trade risk engine |
| unitz007/aegis | 2 | O | execution safety gateway |
| alan-d-smith/synthetix-alpha | 4 | MA | model never sees broker key |
| cloudQuant/backtrader-mcp | 1 | MCP | content-addressed backtests |
| srivardhanjalan/trading-desk | 1 | SK | wires 4 MCPs |
| ferdousbhai/tasty-agent | 89 | MCP | broker safety patterns |
| wildsurfer/cnn-fear-and-greed-parse | 2 | MCP | Fear&Greed history |
| aslcai/OpenPM-Bench | 4 | RP | PIT S&P PM bench |
| dsjwong/stockagent-backtester | 0 | RP | no-lookahead replay |
| AutoResearch-Factory/AgonAlpha | 11 | SK | proposer vs reviewer |
| Yijiu37/Adaptive-FinMem-LLM-StockTrading | 1 | RP | regime-gated retrieval |
| colinalexander/procedural-drift-in-financial-agents | 0 | RP | procedural drift |
| OnePunchMonk/AgentQuant | 220 | QF | explicit-failure loop |
| ICT-FinD-Lab/alphagen | 1293 | RP | formulaic alphas |
| DulyHao/AlphaForge | 444 | RP | factor mining |
| FinStep-AI/Alpha-R1 | 106 | RP | market-memory LLM |
| Miasyster/QuantGPT | 507 | MCP | factor-factory tools |
| NVIDIA-AI-Blueprints/quantitative-signal-discovery-agent | 105 | O | signal discovery loop |
| Aroesler1/Alpha-Factor-Mining-Framework | 4 | RP | CRSP PIT mining study |
| jeonnoin-alt/finance-ai-lookahead-leakage | 0 | RP | leakage experiment |
| HKUSTDial/DeepEar | 291 | MA | usable as skill |
| gta0804/MASS | 181 | RP | scaled simulated investors |
| forecastingresearch/forecastbench | 94 | O | contamination-free bench |
| DVampire/FinAgent | 77 | RP | dual reflection |
| koa-fin/sep | 171 | RP | Summarize-Explain-Predict |
| Tom-roujiang/Awesome-LLM-Quantitative-Trading-Papers | 260 | O | paper index |
| Xtra-Computing/CryptoTrade | 166 | RP | reflective crypto trader |
| etrobot/open-alpha-arena | 601 | SA | nof1 reproduction |
| ulab-uiuc/coinjure | 35 | O | CLI trading harness |
