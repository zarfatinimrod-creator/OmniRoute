# Strategy-science brief: ai-trader (paper), 2026-11-09

**Context.** The bot already exists at `/home/user/OmniRoute/ai-trader`. It has `config.json`, the `aitrader/` package, three skills (`time-machine`, `trader`, `trading-desk`) and two agents (`quant-critic`, `web-researcher`). Every recommendation below names the config key it would change. Any change still goes through the time machine, the placebo gate and quant-critic before it is adopted. The fact-checks have been applied throughout: refuted numbers were replaced with the corrected ones, and anything still unverified is marked (U). Sharpe means excess-over-T-bill Sharpe everywhere.

## 1. Top recommendations, ranked

1. **Fix the learner before adding any signal.** On the bot's own 10-year cache, no signal has an IC with |t| above 1.5. When signals are assigned to the wrong stocks (a placebo), the learner moves weights as much as it does on real data: mean drift 0.015-0.018 vs 0.013. The live cycle and the backtest also behave differently in three ways:
   - `cycle.py` updates weights every day, while `walk_forward_weights` updates every 21 days. The step cap is therefore applied about 21 times a month live, so the time machine does not validate the live learner.
   - Live trades and logged predictions use Yahoo's partial intraday bar.
   - `predictions.jsonl` is rewritten in place and is not hash-chained.

   Fix: update only on completed sessions, every 21 trading days, using empirical-Bayes shrinkage plus a placebo gate that must pass before any tilt (§4).
2. **Treat the trend gate as insurance, not alpha.** The 10-month SMA gate on French market data, 2007-2026: max drawdown -17.6% vs -50.3%, Sharpe 0.75 vs 0.65, but CAGR 9.4% vs 11.0%. Over 2015-2026 it gave up more: 9.0% vs 13.5% (https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing). Most of the gain comes from checking less often. A month-end SMA200 check reaches Sharpe 0.66 at 1.3x turnover a year; a daily check whipsaws. So keep `regime_sma_days` 200, but evaluate it only on rebalance days, with a band.
3. **Re-weight toward signals that survived publication.**
   - Quality is the only long-only alpha source that clears a high significance bar. The long legs of CBOperProf and OperProf earn about 0.3-0.7%/month with t ≈ 2.6-2.9 (corrected figures; https://www.openassetpricing.com/).
   - Momentum (6-1 and 12-1) survives in long-short form but has an insignificant long leg. Vol-scaling it does not remove crashes over the full sample (worst month -28%).
   - Demote `reversal` (0.01%/month after publication) and `high52` (-0.01%/month after publication). Also demote `rsi2` until it proves itself, since it belongs to the reversal family.
   - Turn `lowvol` from a weighted score into an exclusion filter. Its in-universe IC is -0.039; its value is in avoiding the highest-volatility quintile.
4. **Cap position size into earnings.** Earnings days are 1.6% of trading days but carry a median 11.9% of return variance. 77% of overnight down-gaps larger than 3 ATR fall on earnings days, so ATR stops cannot protect there. Keep the existing `earnings_blackout_days` 4 and add a 5% cap for positions held through a release.
5. **The LLM may only veto, shrink, explain and tag post-mortems.** LLMs recall prices from before their training cutoff (https://arxiv.org/abs/2504.14765). Prior LLM-trading claims fade over 20 years and 100+ symbols (FINSABER, https://arxiv.org/abs/2505.07078). Agent Sharpe ratios drop 51-62% after the cutoff (Profit Mirage, https://arxiv.org/abs/2510.07920). The credible pattern is a news filter on top of momentum: out-of-sample Sharpe 0.79 → 1.06, using GPT-4o-mini, significant only at the 10% level (https://arxiv.org/abs/2510.26228).
6. **Build honest measurement:** a write-once prediction log, a separate grades log, Platt calibration, a ledger of every config tried (`trials.jsonl`), the Deflated Sharpe Ratio, and a baseline panel.
7. **ETF relative-strength sleeve as a journaled experiment only.** The corrected replication for 2007-2026 gives Sharpe 0.84 and max drawdown -21.4%, and the result is sensitive to the exact spec, which points to data snooping. GEM underperformed after publication (CAGR 7.6% vs 13.5%).
8. **Set honest expectations.** Realistic long-only alpha is 0-3% a year gross. Skill cannot be proven within a year: at a true Sharpe of 1.0, 80% statistical power takes about 6.2 years of data.

## 2. Tools, data and repos to adopt

| Item | URL / install | Auth / price | How we use it |
|---|---|---|---|
| Yahoo chart API | `query1.finance.yahoo.com/v8/finance/chart/SYM` | Keyless, unofficial | Prices and `^IRX` cash rate. The quoteSummary endpoint (used by `eps_trend`) needs a cookie and crumb, so add retries. |
| yfinance 1.8.0 | `pip install yfinance` (Apache-2.0) | Free | `Ticker.eps_trend` (current / 7 / 30 / 60 / 90 days ago). Snapshot every day to build our own point-in-time revisions history. |
| SEC XBRL | `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, `/submissions/` | Header `User-Agent: Name email`, max 10 requests/s | Quality and issuance signals; 8-K item 2.02 earnings history. **Config still holds `contact@example.com`; replace it with a real email.** Data starts around 2009-11. Keep the earliest `filed` value per period and use tag fallback chains. Handle predecessor CIKs (XOM: old CIK 34088, new 2115436). |
| Nasdaq earnings calendar | `api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` (browser User-Agent) | Keyless, undocumented | Upcoming report dates. Treat `time-not-supplied` as unknown and cap on both sides of the date. Fallback: last 8-K 2.02 date plus about 91 days. |
| Chen-Zimmermann data | `pip install openassetpricing` (GPLv2; pulls in `wrds`, needs polars and pyarrow); data on Hugging Face `OpenSourceAP/CrossSection` | Free, no token | Research only: survivorship-free priors for each signal. Not a runtime dependency. |
| Ken French data / AQR factors | `mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/<Name>_CSV.zip`; AQR BAB xlsx | Free | Regime diagnostics, factor attribution of P&L, learner priors. French values are percent; AQR values are decimals. |
| LightGBM | `pip install lightgbm` (MIT) | Free | Optional cross-sectional ranker later. It must beat OLS-3 (size, B/M, momentum), not just buy-and-hold. In GKX Table 7, boosted trees reached value-weighted Sharpe of only 0.81 vs 0.61 for OLS-3 (https://www.nber.org/papers/w25398.pdf). |
| statsmodels 0.15.0, scikit-learn 1.9.1 | `pip install statsmodels scikit-learn` | BSD-3 | Diebold-Mariano test (`harvey_adj=True`, lag h-1); calibration (Platt, Brier, reliability). |
| skfolio | `pip install skfolio` (BSD-3) | Free | `CombinatorialPurgedCV` as an open replacement for the now-closed mlfinlab: purged CV with embargo, PBO. |
| pandas_market_calendars, quantstats, alpaca-py | `pip install ...` (MIT / Apache-2.0) | Free | Trading-day arithmetic, report metrics, broker SDK. |
| Alpaca paper | `https://paper-api.alpaca.markets`; headers `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` | Free | Order mechanics only. Paper-only accounts get IEX data only, so don't use their bars as signals. No dividends, fees or impact are simulated. Wash-trade check returns 403: cancel resting stops before sending the opposite side. Accounts can't be reset; a new account means new keys. Use `multiplier` and `non_marginable_buying_power`; there is no PDT field any more. |
| FINSABER | github.com/waylonli/FINSABER (Apache-2.0) | Free | Reference baselines and bull/bear/sideways sub-period tests. |
| TradingAgents | Copy the pattern from `tradingagents/memory/{reflection,log}.py`; do not pip-install | Apache-2.0 | 2-4 sentence reflection with the "a week doesn't disprove a months-long thesis" caveat, and an `as_of` point-in-time filter on lessons. Its paper results cover only 3 stocks over 3 months. |
| tradermonty/claude-trading-skills | github.com/tradermonty/claude-trading-skills (MIT, about 3.7k stars) | Free | Borrow ideas only: block new entries after a 2% daily or 5% weekly loss, and fail closed on corrupt state. |

**Age of Blood: reuse everything that transfers.** The repo is private: `zarfatinimrod-creator/age-of-blood`, local copy `/home/user/age-of-blood`. This resolves the risk researcher's "not found".

- **web-researcher agent** (every number carries the URL it was read on; estimates are flagged). Already copied to `ai-trader/agents`. Make it mandatory for all signal research.
- **ponytail** (MIT): stdlib and pandas/numpy first, no new dependency, one runnable self-check per signal.
- **caveman** (Apache-2.0 from v3.0.0; MIT only before that): terse Hebrew alerts.
- **headless-playtest → time-machine** is already done: same seed and same dates before and after each change, numbers read from the live code.
- **Overseer "sham twin" → placebo gate.** Also plant 2 sham lessons from shuffled data every month. If either passes, stop all learning and alert the owner.
- **c_bind → `evidence_hash`** on every lesson and weight update; the verdict is BLOCKED if the underlying rows change. The file is not in the local checkout, so reimplement it.
- **"A HOW ruling that rests on a measurement waits for C's numbers" → no promotion** before the time machine and the placebo have run.
- **Builder / Critic / Overseer and the D/A/B/C roles:** Claude proposes, quant-critic plus the statistics gate judges, the overseer plants shams. One model writes a lesson; a different model or lens tries to refute it. Optionally, Gemini as an outside reviewer using the user's own API key.
- **Vetting external repos:** two stages (scanner, then Opus judge), plus "grep for risky calls and read every SKILL.md before installing" (logs/2026-11-01).
- **Owner communication:** one Hebrew question per message with א/ב/ג options and a recommendation. Approval only after the owner has SEEN a preview, e.g. an equity-curve chart of shadow vs champion vs SPY.
- **Log template for post-mortems:** request / done / decisions / failures / verification / files changed / manual repeated work → automation / token waste.
- Also worth reading: `.claude/superpowers-bootstrap.md`.
- Skip the game-only pieces (economy-designer, ui-finish-gate-reviewer).

## 3. Avoid, and why

- **Signals:** short-term reversal (dead, and cost-killed); 52-week high; calendar effects (turn-of-month t≈0.3 since 2008; no pre-FOMC premium, although the researcher's own FOMC numbers did not reproduce); HML value as an engine (-0.11%/month 2015-25); levered BAB; GEM. Liquid-stock issuance evidence is weak (ShareIss1Y 2015+ 0.37%/month, t 1.3), so give it a small weight only.
- **Paid "alternative" data:** congress copy-trading (NBER w35041; NANC's outperformance is beta 1.08). Insider clusters only as a small bonus for small and mid caps; the researcher's own test is unverified (U). Don't pay for Quiver.
- **LLM as a price oracle, or any pre-cutoff LLM backtest.** Star counts are not evidence (TradingAgents has 121k stars on a 3-month, 3-stock test). Off-the-shelf time-series foundation models (Chronos, TimesFM) have negative R² on returns. Kronos's "+93%" sits on a RankIC of 0.027. Reasoning models did not trade better in LiveTradeBench. Alpha Arena numbers come only from secondary trackers (U).
- **Sizing:** Kelly or any edge-based sizing, and any learning step that raises gross exposure or vol. Under a GBM idealisation, full Kelly gives a 50% chance of ever falling to half of current wealth.
- **The all-time-peak drawdown breaker with no re-entry rule.** On buy-and-hold it cut Sharpe from 0.51 to 0.28, with average exposure 0.40.
- **Daily regime checks.** Turnover 3.3x vs 0.5x a year.
- **Methods:** isotonic calibration below about 1,000 effective samples; bandits or river (paper trading sees every strategy's outcome, so this is not a bandit problem); hmmlearn smoothed or Viterbi labels (they leak the future).
- **Reporting raw accuracy.** Always-up SPY 2005-26 was right on 55.0% of days, 59.6% of rolling 5-day windows and 67.2% of rolling 21-day windows.
- **PDT logic.** FINRA Regulatory Notice 26-10 removed it, effective 2026-06-04 (https://www.finra.org/rules-guidance/notices/26-10).
- **Parking cash in SGOV/BIL inside Alpaca paper.** It shows about 0% because dividends are not simulated.
- **Backtesting on Yahoo single stocks.** It misses delisted names: 26% of insider-event tickers returned 404.

## 4. Parameters to hard-code (config.json)

**Risk (keep unless noted):**
- `target_vol_annual` 0.12, `vol_lookback_days` 60, `max_gross` 1.0, `max_position_pct` 0.10, `max_etf_position_pct` 0.20, `max_positions` 15, `atr_stop_mult` 3.0 for stocks (ADD `etf_atr_stop_mult` 4.0, or no stop for ETFs), `stop_cooldown_days` 10, `rebalance_every_days` 5, `rebalance_band_pct` 0.02, `min_trade_value` 500.
- ADD:
  - `earnings_max_position_pct` 0.05 (ETFs exempt).
  - `max_cluster_pct` 0.35: average-linkage clusters on 252-day correlation, threshold 0.55, recomputed weekly. Today SPY, QQQ, XLK, SMH, NVDA, AVGO, AMD, MU, AMAT, INTC and CAT form one cluster.
  - Apply `max_sector_pct` 0.30 with ETF look-through (QQQ, XLK and SMH count as Tech; XLC as Comm).
  - `veto_daily_loss` 0.02, `veto_weekly_loss` 0.05.

**Regime:** ADD `regime_band_pct` 0.02. Go risk-off when SPY < 0.98 × SMA200 and back to risk-on when SPY > 1.02 × SMA200, evaluated on rebalance days only. Keep `risk_off_gross_mult` 0.5. Optional second leg, TSMOM12 = SPY 252-day return minus BIL 252-day return: gross 1.0 if both legs are on, 0.5 if one is, 0.2 if neither.

**Drawdown:** keep `dd_halve` -0.10 and `dd_flat` -0.20. ADD `dd_peak_window_days` 252, or a re-entry rule: after going flat, come back at 0.5x once SPY is risk-on and 20 days have passed, then reset the reference peak. Test a smooth alternative in the time machine: scale = clip((E/peak - 0.75)/0.25, 0, 1).

**Costs:**
- `slippage_bps` 5 for mega caps and ETFs; ADD a 12 bps override for CHKP, NICE, WIX, MNDY and TEVA.
- Alpaca fees: SEC fee 20.6e-6 × sell notional (the rate can change with appropriations), plus CAT $0.000003 per share on buys AND sells. No TAF term, because Alpaca charges TAF at $0.
- Stress runs at 15 and 30 bps are pass/fail.
- Cash accrues at the live `^IRX` rate (4.00% on 2026-11-06), falling back to the config value of 0.035.

**Signal formulas:**
- MOM12_1 = P[t-21]/P[t-252] - 1; MOM6_1 = P[t-21]/P[t-126] - 1. Combine as z-scores winsorised at ±3. Enter in the top 10%, exit below the top 30%. Crash guard: halve the momentum weight when the market's 24-month return is below 0 AND its 126-day vol is above the 80th percentile.
- Corrected CBOP for XBRL data: (Rev - COGS - SG&A) - ΔAR - ΔInv - ΔPrepaid + ΔDeferredRevenue + ΔAP + ΔAccrued, all divided by total assets. Do **not** add R&D back, because XBRL SG&A usually excludes it. The XBRL `IncreaseDecreaseIn*` tags are positive when the balance grows. GP = (Rev - COGS)/Assets. Don't mix Fama-French OP (which subtracts interest and divides by book equity) with Ball et al. Use the `filed` date as the availability date, rebalance quarterly, and exclude financials.
- ShareIss1Y = ln(split-adjusted shares_t / shares_{t-12m}); lower is better.
- Low-vol filter: exclude the top 20% of VOL252 (252-day daily-return vol, annualised); size positions ∝ 1/VOL63.
- Revisions proxy: REV90 = (FY1 EPS now - FY1 EPS 90 days ago)/Price.

**Learner (replaces current values):**
- `update_every_days` 21.
- `ic_half_life_days` 504 (now 60).
- Shrinkage: `tau` 0.02, `ic_sd_floor` 0.15, prior mean mu0 = 0. λ = n_eff/(n_eff + σ²/τ²); μ = λ·ICbar; s = (n_eff/σ² + 1/τ²)^-0.5; z = clip(μ/s, ±2.5).
- Tilt: target = prior × exp(0.3·z). So `eta` 0.3 (now 0.5) and `z_cap` 2.5.
- Bounds: band [max(0.02, 0.5×prior), min(0.35, 2×prior)]; `weight_cap` 0.35 (now 0.4); `max_step` 0.02 (now 0.05).
- `min_n_eff` 12: no tilt before then. `max_l1_drift` 0.30: freeze and ask the owner beyond that.
- `horizon_by_signal`: reversal and rsi2 at 5 days; momentum, trend, high52 and breakout at 20; lowvol at 60. `horizons_days` [5, 20, 60].
- Placebo gate: K ≥ 100 permutations (about 8 minutes), recomputed quarterly, and it must pass before any tilt.
- **This is a bounded heuristic, not a Hedge algorithm with a regret guarantee.** Under pure noise it still moves weights about ±10-20% of prior before the caps, which is why the gate comes first.

**Calibration:**
- Platt scaling, monthly, per horizon, on the last 504 days of matured rows. Effective sample = distinct dates × about 17. Switch to isotonic only above 1,000 effective samples.
- Claude's stated probability: p = 0.5 + 0.5·(p_raw - 0.5) until 50 of its calls are graded, then Platt.
- Alarm if ECE > 0.1.
- Sanity check: hit rate ≈ 0.5 + arcsin(IC)/π. Treat a sustained hit rate above 55%, or IC above 0.10 for 3 months, as a probable leak or bug.

**Lessons:**
- Decay half-lives Q = 14 / 90 / 365 days for observation / hypothesis / rule, as in FinMem (https://arxiv.org/pdf/2311.13743). Purge after 3Q. Inject at most 5 lessons into the prompt.
- T1 (risk-reducing only): n_eff ≥ 20 and t ≥ 2; expires after 90 days.
- T3 (new signal, structure or risk limit): n_eff ≥ 30 distinct non-overlapping dates; date-clustered |t| ≥ 3, or BH-FDR q ≤ 0.10 together with permutation p < 0.01; same sign in at least 2 of 3 sub-periods; DSR ≥ 0.95; quant-critic PASS; the owner's yes.

**Promotion (champion vs challenger):**
- At least 126 shadow days.
- Paired HAC t-test on the daily IC difference (lag h-1): ≥ 2 in the shadow period and ≥ 3 in the 10-year walk-forward.
- DSR ≥ 0.95, counting every config in `trials.jsonl`.
- Drawdown no worse than 1.25× the champion's; turnover no more than 1.5×.
- At most one promotion per quarter.
- CUSUM only on non-overlapping periods; overlapping daily IC false-alarms.

**Statistical bars:**
- A new signal needs t > 3 (Harvey-Liu-Zhu, https://nber.org/papers/w20592).
- Cut published ICs by at least 50% (returns fall 58% after publication, McLean-Pontiff).
- To tell a 55% from a 50% hit rate with 80% power takes 620-780 independent calls; 52% takes about 4,900.
- LLM signals: `llm_eval_start` = model cutoff + 1 month. Log `model_id`, `prompt_hash` and timestamp before the open.
- Baseline panel in every report: SPY total return, always-up, equal-weight universe, 12-1 momentum, OLS-3, and random entry with matched turnover.

## 5. Open questions only Nimrod can answer

1. Is shorting allowed, even on paper? Most anomaly alpha is in the short leg: GP long-short earns 0.94%/month, but its long leg only about 0.2%.
2. Universe: keep the 93 hand-picked names (which carry survivorship bias, including the Israeli names TEVA, CHKP, NICE, WIX and MNDY), or move to a point-in-time S&P 500/1000 or all US stocks above $20M a day?
3. Pay for historical analyst estimates (FMP/Zacks), or wait months while we self-journal Yahoo snapshots?
4. The real-money gate: will you accept that 3 months proves nothing? The proposed replacement is process checks, PSR ≥ 0.95 and small risk limits. What is your timeline?
5. Will you accept the trend gate's insurance cost (about 1.5-4.5 percentage points of CAGR a year in bull markets)? What drawdown would make you quit?
6. Which live broker, and what are your FX costs? This sets turnover. Tax: 25% Israeli capital-gains tax (U), 25% US treaty withholding on dividends, W-8BEN.
7. Should we pin one Claude model version so the journal stays comparable?
8. Are you OK with a weight-learner that stays almost static for years (credibility about 8% after 1 year)?
9. Which real contact email should go in the SEC User-Agent?
10. What share of capital for the ETF relative-strength sleeve: 0, 30 or 50%?

**Still unverified (U):** Fischer-Krauss figures (source returns 503; cite EJOR DOI 10.1016/j.ejor.2017.11.054), Alpha Arena S1/S1.5 results, the researcher's own insider and ETF tests, the meta-labeling JFDS sizing claim, the CUHK "62% microcap" figure, Israeli capital-gains specifics, and Alpaca's real CAT pass-through in practice.
