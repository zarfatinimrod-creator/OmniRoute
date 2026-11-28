# "Claude portfolio": what it is, what the numbers show, what a paper bot can test

Research note for the AI trader (research workflow of 2026-11-14: three web researchers and one editor who re-checked every figure against its source). Not investment advice.

Date: 2026-11-14. Figures are as of 2026-11-13 unless a date says otherwise. Every return here is self-reported by the operator or the platform. None is audited.

1. WHAT "CLAUDE PORTFOLIO" REFERS TO
- Mainly one thing: the "Claude Portfolio" on Autopilot.
  - Autopilot is a copy-trading app run by Autopilot Advisers, LLC, an SEC-registered adviser (CRD 331749).
  - The pilot is "Dr. Lira's AI Finance Labs", led by Prof. Alejandro Lopez-Lira (University of Florida).
  - Its public face is the X account @theaiportfolios ("The Claude Portfolio"), which posts in Claude's voice.
  - It is not affiliated with Anthropic (Autopilot page; Finance Magnates, 2026-09-07).
- The phrase is also used for:
  - Other Claude books on Autopilot: Rallies "Claude" and Quiver "Claude - Quiver Enhanced".
  - Model-vs-model arenas: Rallies AI Arena (paper), nof1 Alpha Arena, HKU Agentic Trader, LiveTradeBench.
  - Paper diaries such as StartupHub's "Trader Claude's".
- It is NOT the broker agent launches. Claude was named in 9 of 10 broker AI-agent launches in H1 2026 (IBKR, Robinhood, eToro and others; Finance Magnates, 2026-06-08). These are tools for a broker's clients, not a portfolio.

2. THE MAIN PORTFOLIO
Operator and incentives
- Lopez-Lira, Ph.D. in Finance from Wharton (Autopilot AI page).
- He receives a small share of subscription revenue (MarketWatch via itiger, 2025-06-07).
- Autopilot takes a share of adviser fees and is paid by brokers for referrals (Form CRS, 2026-02-04).
- explainx (2026-08-05) calls the project "a commercial funnel, not a neutral experiment."

Method (as described; never independently shown)
- Claude Code running Opus 4.6. Source: a screenshot cited by explainx, 2026-08-05. The platform says only "Claude Opus".
- Prompt in that screenshot: "You are managing a $50,000 portfolio. Beat the S&P 500. You in?"
- Pipeline (X threads, Mar 31 and Apr 1):
  - Score the Russell 1000 on financials, news and analyst data.
  - Send the top 50 to a bull/bear debate.
  - Build probability-weighted expected returns.
  - Pick 15 names "on alpha, sector, & risk".
- Lopez-Lira's description (AI Street, Jul 28): one agent per stock, a portfolio-optimisation agent and an audit agent; trades at most twice a week, usually less. The sister portfolios trade monthly.
- Rails (operator quoted by explainx, 2026-08-05): "size limits, a turnover ceiling, and a required written thesis". The numeric values are not published.
- Human role: contested. See the contradictions list in the verification log above.

Holdings (dated snapshots)
- About 2026-04-01 (Finbold, 2026-04-03): 15 names, about 94% invested; VST 10%, AVGO 10%, AU 4%, HWM 4%, plus LLY.
- 2026-04-14 (X): NOW, VST, LLY, AVGO, CI, GLD, ICE and others. Top 5 about 45%. A correction followed (NVDA 9.07%, NOW 7.97%).
- 2026-07-25 (Business Insider): largest holding the iShares 0-3 Month Treasury Bond ETF (ticker SGOV is my identification; the article gives no ticker), plus Kratos and Vista Energy.
- 2026-11-14 (Autopilot): BOXX 8.5% (a cash-like box-spread ETF), PHVS 7.8% (Pharvaris, a biotech), APP 7.4% (AppLovin). The page text says 15 holdings; its list shows 20.
- Drift: from April's large-cap AI, power and gold names to small/mid caps and cash-like sleeves. No turnover rate is published.

Returns vs the S&P 500 (no source gives a QQQ figure)

| As of | Claude | S&P 500 | Source |
|---|---|---|---|
| 2026-04-02 | +0.028% | +0.40% | Finbold, 2026-04-03 |
| 2026-04-14 | +4.2% | SPY +0.6% | X via threadreader |
| about 2026-05-15 | +2.6% | +8.3% | BeInCrypto via the Phemex mirror, 2026-05-15 |
| about 2026-07-27 | about +10% | "roughly the same" | AI Street, Jul 28 |
| 2026-08-04 | +19.04% | +12.24% | operator, via Finance Magnates 2026-09-07 and explainx 2026-08-05 |
| 2026-09-04 | +31.1% | not given | Autopilot data, via Finance Magnates 2026-09-07 |
| 2026-11-13 | +23.0% | SPY with dividends +12.6% | Autopilot page |

- Last month to 2026-11-13: -0.71% vs SPY -3.0%.
- Last 3 months (2026-08-13 to 2026-11-13): -2.8% vs -2.8%, a tie.
- My arithmetic:
  - About -6.2% from 2026-09-04 to 2026-11-13.
  - Excess since Mar 3: about +10.4 points over about 0.70 years.
  - On an April 1 basis the SPY figure would be about 3 points higher (see correction 7 above).
- No max drawdown, volatility, Sharpe or beta is published.

AUM
- About $27M (early August 2026) and about $49.4M (2026-09-04), both from Finance Magnates.
- $51,575,869 on 2026-11-13 (Autopilot AI page). Inflows have flattened.
- Across Lopez-Lira's books: about $200M and about 52,000 investors (July, Finance Magnates and AI Street). My sum of the 9 "Dr. Lira's" portfolios on the 2026-11-13 Autopilot page is about $279.9M.

Fees
- Pilot subscription: $59.95 a quarter or $169.95 a year. Minimum $500. Broker costs are extra.
- AUM fee currently 0.00%, "expect to charge ... in the future" (Form CRS, 2026-02-04).
- Shown returns use an assumed $50,000 account. By my arithmetic the flat fee is about 0.34% a year at $50k, 3.4% at $5k and 34% at the $500 minimum.

3. OTHER CLAUDE PORTFOLIOS AND CONTESTS
Real copied money on Autopilot (as of 2026-11-13)
- Rallies "Claude": +17.8% since 2026-04-01 vs SPY +15.9%; $1.1M.
- Quiver "Claude - Quiver Enhanced": -4.3% since 2026-04-21 vs SPY +6.7%; 3 months -12.8%; $379,562. Quiver's own page shows a backtest with CAGR 49.61% for the same strategy (researcher-reported, not re-checked). The gap between the backtest and real copies is the clearest warning in this set.

Paper or simulated
- Rallies AI Arena ($100k paper from late November 2025; Crypto Briefing, 2026-06-21):
  - Claude +27.22% vs SPY +14.40% as of 2026-09-04 (Finbold, 2026-09-05).
  - In the same arena on the same date, Grok was +70.75% and ChatGPT +64.83%, so Claude ranked behind both.
- StartupHub "Trader Claude's": $10k paper from 2026-04-11; -4.54% on 2026-08-25, the last post found.
- Quiver "Claude - Standard": backtest only.

Arenas and benchmarks
- nof1 Alpha Arena Season 1 (crypto perpetuals, 2025-10-18 to 2025-11-03): Claude Sonnet 4.5 about -42%, 3rd of 6 (ForkLog, 2025-11-04).
- HKU Agentic Trader (FX, index and gold; April 2026; about 6 weeks): Claude Opus 4.6 -5.99%, 8th of 10, more than 1,000 trades, 4.0x max leverage.
- LiveTradeBench (2025-08-18 to 2025-10-24; 15 large US stocks; no costs): Claude variants +2.45% to +3.93%. No SPY comparison.
- Elm Wealth (2026-06-17; historical WSJ headlines, so contaminated): Claude Sharpe 0.31 to 0.50 with excessive leverage.

4. WHAT THE EVIDENCE SAYS ABOUT SKILL VS LUCK
- The window is short. By my arithmetic (illustrative, not a measurement), +10.4 points of excess over about 0.70 years with 10-20% tracking error gives t ≈ 0.6-1.2. That cannot be told apart from zero.
- The tailwind was large. SOX +88%, Nasdaq 100 +25% and S&P 500 +14% in Q2 2026 (EnterpriseAM/Bloomberg, 2026-07-01). The book's lead was built inside that quarter and through early September. Since then it has only tied SPY over 3 months.
- The tilt is known:
  - NBER w35153 (April 2026): LLM picks load on momentum, large size, low book-to-market and media attention, with no statistically significant abnormal returns under the DGTW method.
  - Investopedia (2026-05-19): beta 1.6, semiconductors 41% vs 21% of the index.
- Many portfolios run at once (19 on one Autopilot page). On 2026-11-13, 7 of 17 beat SPY over 1 month and 5 of 17 over 3 months (my count from the page). Losers such as "AI ❤️ BTC" (-49.49%) are still listed, which argues against the worst kind of survivorship. Whether any portfolio was ever removed is unknown.
- Backtests can't be trusted:
  - Lopez-Lira's own paper (arXiv 2504.14765) finds LLM forecasts unusable inside the training window. Instructions and masking do not stop recall; after the cutoff there is no recall.
  - FINSABER (arXiv 2505.07078): reported LLM edges "deteriorate significantly" over 20 years and 100+ symbols. The strategies were too timid in bull markets and too aggressive in bear markets.
- Live arenas mostly show losses or noise.
- Verdict: the record is consistent with a tech/AI-tilted, high-beta, concentrated book that rode the 2026 rally. It does not yet show skill.

5. WHAT OUR PAPER BOT COULD TAKE (only ideas testable without look-ahead)
Claude's own decisions cannot be backtested honestly; they can only be graded forward.
a) [STRATEGY CHANGE — must pass the time machine sweep and the quant-critic] A mechanical "rails" variant of the quant book:
   - 15 names, a per-name cap, a turnover ceiling, rebalance no more often than twice a week.
   - The values are ours, because the operator's are unpublished. Count every variant tried and deflate the Sharpe ratio (Bailey and López de Prado).
b) [STRATEGY CHANGE — time machine sweep and quant-critic] An "attention + momentum + size" control book with no LLM, run on point-in-time data:
   - Rank by news count, 12-1 momentum and size.
   - If the news book can't beat this control, the Claude layer adds nothing (NBER w35153).
c) [STRATEGY CHANGE — time machine sweep and quant-critic] A rule-based cash sleeve (a T-bill or box-spread ETF) switched on by a regime filter.
   - The Claude Portfolio held SGOV and BOXX-type funds, but its rule is unknown, so test our own rule, not theirs.
d) [NEWS-ENGINE CHANGE — needs a forward measurement] Anonymize the company name and ticker in headlines before Claude scores them (memorization: arXiv 2504.14765; distraction effect: Glasserman and Lin, not re-checked).
   - Score both versions in parallel and compare forward returns.
e) [NEWS-ENGINE CHANGE — forward measurement] Trade the drift, not the first reaction. Lopez-Lira and Tang (arXiv 2304.07619) call the initial reaction "non-tradable" and find predictable drift, "especially for small stocks and negative news". They also find returns decline as adoption rises.
   - Log the entry delay and the cap bucket, and measure forward.
f) [NEWS-ENGINE CHANGE — forward measurement] Require a written, falsifiable thesis with an explicit exit trigger for each buy, mirroring the operator's "required written thesis" rail. Optionally add a bull/bear pass first.
   - Grade whether thesis-break exits beat time or price exits forward. This costs more tokens.
g) [STRATEGY CHANGE for the crypto book — time machine sweep and quant-critic] Cap leverage and trade frequency.
   - The LLM agents that traded most and with leverage did badly: HKU (Claude, more than 1,000 trades, -5.99%) and Alpha Arena Season 1 (-42%).
Grading protocol for all of the above:
- Timestamp each decision before the fill.
- Fix the benchmark in advance, matched on beta and sector rather than raw SPY.
- Report Sharpe, beta, information ratio and max drawdown.
- Run a LAP-style contamination check on any retro test (arXiv 2512.23847).

6. RISKS OF COPYING
- No audit. Autopilot "doesn't manage, validate, or guarantee" the pilot.
- Copiers fill after the leader, with slippage. The shown returns assume a $50k account, and flat fees weigh far more on small accounts.
- Price impact. About $51.6M copying means a 7.8% weight (PHVS) is about $4M per name by my arithmetic. Liquidity was not checked. Robinhood herding studies find about -3% five-day abnormal returns after crowded buys in small caps (Barber et al., working paper, not re-checked).
- Concentration and high beta; style drift from mega caps to small caps and cash; the model version can change.
- Unclear who decides: Claude, the operator, or both.
- The book is already down about 6% from its 2026-09-04 figure (mixed-basis arithmetic), so copiers who joined near the peak are behind.
- Conflicts: platform and operator revenue shares, broker referral payments.
- Regulators: the SEC/NASAA/FINRA alert of 2024-01-25 warns against AI return claims "even from registered firms" (researcher-reported, not re-checked).

7. SOURCES (URL — date of the page or of the data)
- https://start.joinautopilot.com/strategies/claude-portfolio-950048 — data as of 2026-11-13/14
- https://start.joinautopilot.com/strategies/ai-portfolios — data as of 2026-11-13
- https://start.joinautopilot.com/strategies/claude-989022 — data as of 2026-11-13
- https://start.joinautopilot.com/strategies/claude-quiver-enhanced-1023025 — data as of 2026-11-13
- https://reports.adviserinfo.sec.gov/crs/crs_331749.pdf — 2026-02-04 (marked draft)
- https://www.financemagnates.com/forex/retail-investors-put-27-million-into-claude-trading-portfolio-after-19-gain/ — 2026-09-07
- https://www.financemagnates.com/forex/analysis/claude-powers-nine-of-ten-broker-ai-agents-that-now-trade-live-accounts/ — 2026-06-08
- https://explainx.ai/blog/claude-portfolio-autopilot-ai-trading-experiment-august-2026 — 2026-08-05 (secondary, commercial)
- https://www.ai-street.co/p/how-ai-runs-200-million-in-portfolios — "Jul 28", year not shown, partly paywalled
- https://threadreaderapp.com/user/theaiportfolios — mirror of X posts dated Mar 31, Apr 1, Apr 2 and Apr 14 (2026)
- https://finbold.com/claude-ai-autonomous-portfolio-just-launched-it-picked-these-stocks-to-beat-the-market/ — 2026-04-03
- https://phemex.com/news/article/grok-ai-outpaces-claude-in-stock-trading-with-60-profit-81826 — 2026-05-15 (mirror of BeInCrypto)
- https://finance.yahoo.com/markets/stocks/articles/ai-model-best-stock-trader-091501419.html — Business Insider, 2026-07-25
- https://www.itiger.com/news/2541123988 — MarketWatch mirror, 2025-06-07
- https://fool.com/investing/2026/04/13/a-claude-agent-bought-these-2-trillion-dollar-arti/ — 2026-04-13 (promotional)
- https://finbold.com/this-grok-portfolio-just-destroyed-the-sp-500-2/ — 2026-09-05
- https://cryptobriefing.com/chatgpt-leads-rallies-ai-stock-market-arena/ — 2026-06-21
- https://www.debelegger.nl/post/claude-ai-portefeuille-verslaat-sp-500 — 2026-07-22
- https://www.quiverquant.com/strategies/s/Claude%20-%20Standard/ — backtest, no end date
- https://www.startuphub.ai/category/claudes-trades — last post 2026-08-25
- https://www.hkubs.hku.hk/aimodelrankings_en/report/En_Agentic%20Trader%20Short%20Report.pdf — undated; test from April 2026
- https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/ — 2025-11-04
- https://arxiv.org/html/2511.03628v1 — LiveTradeBench; test from 2025-08-18 to 2025-10-24
- https://elmwealth.com/ai-trading/ — 2026-06-17
- https://www.nber.org/papers/w35153 — April 2026
- https://finance.yahoo.com/markets/stocks/articles/research-reveals-risks-using-ai-165044697.html — 2026-05-19
- https://arxiv.org/abs/2504.14765 — v2 2025-12-15
- https://arxiv.org/abs/2512.23847 — v2 2026-06-12
- https://arxiv.org/abs/2304.07619 — v6 2025-10-28
- https://arxiv.org/abs/2505.07078 — v6 2026-06-26
- https://arxiv.org/abs/2502.21206 — v3 2025-07-06
- https://enterpriseam.com/mena-india/2026/07/01/chip-stocks-see-their-best-quarter-ever-but-volatility-raises-questions-over-what-comes-next/ — 2026-07-01
- https://www.marketscreener.com/news/can-chatgpt-and-grok-beat-the-market-ce7e5cdfd081fe24 — 2026-02-28
- Researcher-cited, not re-checked:
  - https://papers.ssrn.com/abstract=2460551 (Deflated Sharpe Ratio, 2014)
  - https://arxiv.org/abs/2309.17322 (2023-09-29)
  - https://www.nasaa.org/70780/nasaa-investor-alert-artificial-intelligence-and-investment-fraud/ (2024-01-25)
  - https://www.smallake.kr/wp-content/uploads/2020/12/SSRN-id3715077.pdf (Barber et al., working paper)

OPEN QUESTIONS
1. Was the start March 3 or April 1, and what did the book hold in March? This moves the SPY benchmark by about 3 points.
2. Who places or approves each trade? Lopez-Lira told Business Insider "the final decision is the model's completely"; Finance Magnates says Claude "did not independently manage" it.
3. What are the numeric rails: position cap, turnover ceiling, cash rule?
4. Are +19.04% (Aug 4) and +31.1% (Sep 4) on the same net-of-fee basis as the page's +23.0%? Why did AI Street report about +10% on about Jul 27?
5. How do copier fills compare with the leader's, and what is the liquidity of the small-cap weights?
6. Has the model changed since Opus 4.6?

UNKNOWN (no source found)
- Max drawdown, volatility, Sharpe and beta for the Claude Portfolio.
- Any QQQ comparison.
- Turnover rate.
- Full holdings history.
- Copier count after August 2026.
- Any audit or independent rebuild of the trade log.
- Measured price impact from Autopilot mirroring.
- Claude's final result in Alpha Arena Season 1.5.

## Appendix: the editor's verification log (2026-11-14)

EDITOR'S VERIFICATION LOG (all checks run with WebFetch on 2026-11-14)

CONFIRMED against the cited page
- Autopilot "Claude Portfolio" page (https://start.joinautopilot.com/strategies/claude-portfolio-950048). Returns are as of 2026-11-13; holdings as of 2026-11-14.
  - Returns: +23.0% since 2026-03-03, against SPY with dividends +12.6%. Month: -0.71% vs SPY -3.0%. 3 months: -2.8% vs SPY -2.8%. No 1-year figure yet.
  - Capital copying: $51.6M. Pilot: "Dr. Lira's AI Finance Labs". The page says "Not affiliated with Anthropic."
  - Model text: "Claude Opus ... powers an orchestrated multi-agent research and reasoning architecture".
  - Top holdings: BOXX 8.5%, PHVS 7.8%, APP 7.4%, "Other 17 holdings" 76.3%.
  - Fees: $59.95 a quarter or $169.95 a year. Returns are net of fees on an assumed $50,000 account.
  - Disclaimers: "Autopilot doesn't manage, validate, or guarantee this Pilot's portfolios." Autopilot Advisers, LLC, CRD 331749.
- Autopilot AI-portfolios page (https://start.joinautopilot.com/strategies/ai-portfolios), data as of 2026-11-13.
  - Claude Portfolio: $51,575,869, +23.02%.
  - 19 AI portfolios with "$307.3 million of client capital".
  - Warning on the page: "Portfolios that use the same model are not a controlled experiment."
  - "AI World War III" (GPT and Claude Opus, started 2023-10-31): +217.66% since start; 1 year +25.42% vs SPY +13.38%; 3 months -10.87% vs SPY -2.78%.
- Finance Magnates, Tareq Sikder, 2026-09-07. Every figure the researchers cited checks out:
  - +19.04% vs S&P +12.24% as of Aug 4; +31.1% as of Sep 4 per Autopilot.
  - About $27M (early August, no exact date) and about $49.4M (Sep 4).
  - About 52,000 investors, 7 portfolios and about $200M (July). Start: $50,000 in March.
  - Quotes: "Claude did not independently manage the portfolio"; not affiliated with Anthropic.
- Finance Magnates, Damian Chmiel, 2026-06-08 ("nine of ten" broker agents). Confirmed: Claude 9, ChatGPT 5, Grok 3, Gemini 2; IBKR on June 1 with 4.75M accounts and client approval of each order; eToro from $200; no agent can move money.
- explainx.ai, Yash Thakker, 2026-08-05. Confirmed: Opus 4.6, the prompt, the Mar 3 start, +19.04% vs 12.24%, $27M, and the rails quotes. The heading reads "This is a commercial funnel, not a neutral experiment."
- AI Street, Matt Robinson, "Jul 28" (no year shown; paid after a point). Confirmed:
  - "up about 10% as of yesterday, roughly the same as the S&P 500".
  - Trades limited to twice a week; the other portfolios trade monthly.
  - About $200M and nearly 52,000 investors.
- threadreader mirror of @theaiportfolios. Confirmed: Mar 31 "officially arrived"; Apr 1 "officially went live"; "built to keep humans fully out"; the Apr 14 weights and the correction (NVDA 9.07, NOW 7.97); +4.2% vs SPY +0.6%. The Apr 14 weights add up to 100.4%.
- Finbold, Andreja Stojanovic, 2026-04-03. Confirmed: +0.028% vs S&P +0.40% from the Apr 1 open to the Apr 2 close, against the X post's claim that it was "already outperforming".
- Phemex (a mirror of BeInCrypto), 2026-05-15. Confirmed: "launched in April 2026 with $50,000", +2.6% vs S&P +8.3%. The article does not name the portfolio, so tying it to Lopez-Lira's book is an inference.
- Rallies "Claude" on Autopilot (https://start.joinautopilot.com/strategies/claude-989022), as of 2026-11-13: +17.8% since 2026-04-01 vs SPY +15.9%; month -4.7% vs -3.0%; 3 months -1.7% vs -2.8%; $1.1M.
- Quiver "Claude - Quiver Enhanced" on Autopilot, as of 2026-11-13: -4.3% since 2026-04-21 vs SPY +6.7%; month -14.5%; 3 months -12.8%; $379,562.
- Quiver "Claude - Standard": backtest only, start 2026-03-27, CAGR 11.63%, Sharpe 0.300, max drawdown -16.50%. The page gives no end date.
- Rallies arena (paper money):
  - Finbold, 2026-09-05: Claude +27.22% vs SPY +14.40% as of Sep 4.
  - Crypto Briefing, 2026-06-21: "this is paper trading. No real money changes hands."
  - De Belegger, 2026-07-22: +20.70% vs SPY +11.62% as of Jul 16, max drawdown 8.2%.
- HKU "Agentic Trader" PDF (undated; test began April 2026; about 6 weeks; $100k per model; 10 models). I read the PDF itself.
  - Claude Opus 4.6: -5.99%, 8th of 10, more than 1,000 trades, max effective leverage 4.0x. Winner: Qwen 3.5 Plus at +9.85%.
  - It uses live market data and "replicate[s]" spreads and slippage. Whether real money was used is not stated.
- ForkLog, 2025-11-04: Claude Sonnet 4.5 ended at $5,799 (about -42%), 3rd of 6; 4 of 6 models lost money.
- NBER w35153 (Carlin, Israelsen, Wazzan, April 2026): abstract confirmed.
- Investopedia via Yahoo (Trina Paul, 2026-05-19). Confirmed: semiconductors 41% of AI portfolios vs 21% of the S&P 500; beta 1.6; median 10 holdings for Claude; about 10x the news coverage; about 4 weeks of data for Claude.
- arXiv abstracts confirmed: 2504.14765 (memorization), 2512.23847 (look-ahead propensity, LAP), 2304.07619 (Lopez-Lira and Tang, v6), 2505.07078 (FINSABER, v6 2026-06-26).
- LiveTradeBench (arXiv 2511.03628). The Claude numbers are confirmed. Costs are "not modeled", and no SPY benchmark is mentioned.
- Elm Wealth, 2026-06-17. Confirmed, with the model names added:
  - claude-sonnet-4.6: Sharpe 0.31, hit rate 60.7%, daily standard deviation 33.3%.
  - claude-opus-4.7: Sharpe 0.50, hit rate 67.9%, daily standard deviation 19.5%.
  - The authors say the AIs ran "20% to 40%" daily volatility against a sensible 7.5-15%. Memorization is not discussed.
- Motley Fool, 2026-04-13: confirmed. It is promotional; the author and the firm hold MSFT and AVGO.
- EnterpriseAM citing Bloomberg, 2026-07-01: SOX +88% in Q2 2026, Nasdaq 100 +25%, S&P 500 +14%.
- MarketScreener, 2026-02-28: confirmed.
- Autopilot Form CRS, 2026-02-04 (I read the PDF). Confirmed:
  - Basic tier free. Premium: $29.99-$199.99 a quarter or $99.99-$699.99 a year, plus an "AUM Fee (currently 0.00%...)".
  - Minimums: $500 per account and $500 per portfolio.
  - Autopilot discloses that it takes a share of adviser fees and is paid by broker-dealers for referrals.
- StartupHub "Trader Claude's": it calls itself an "AI paper-trading agent". Last post 2026-08-25 at $9,546 (-4.54%). No model is named.

CORRECTIONS to the researchers
1. The platform does publish a since-start benchmark: SPY with dividends +12.6% (Claude page, as of 2026-11-13). The autopilot researcher listed this as unknown.
2. The price is published: $59.95 a quarter or $169.95 a year. Both fall within the Form CRS ranges.
3. "Lopez-Lira expects his portfolios to roughly track the S&P 500" is the MarketWatch reporter's paraphrase, about long-only portfolios, from 2025-06-07 (Laila Maidan, via the itiger mirror). It is not a direct quote.
4. explainx does not contain the phrase "highlights the one currently performing best". Its line is that the organizer "will naturally spotlight whichever one currently looks best", which is the blog's own inference. "The operator makes the final call" is also explainx's reading, not a quote.
5. The Sharpe ratios 4.80/4.48 for the Chronologically Consistent LLM paper (arXiv 2502.21206) are not in the abstract. They remain unverified; the abstract only calls look-ahead bias "modest".
6. StartupHub's "peak $10,142 on 2026-08-17" covers only the visible listing back to Jul 11. On Jul 11 the account stood at $8,430 (-15.70%).
7. The start date changes the benchmark. SPY was +12.6% from Mar 3 to Nov 13 and +15.9% from Apr 1 to Nov 13. By my arithmetic, SPY therefore fell about 2.8% between Mar 3 and Apr 1. If the book was not fully invested before the April 1 "go-live", counting from March 3 flatters the comparison. Unknown.
8. New primary-ish quote: Business Insider via Yahoo, 2026-07-25, Lopez-Lira: "the final decision is the model's completely." This sharpens the conflict with Finance Magnates.

CONTRADICTIONS between sources (unresolved)
- Start date: 2026-03-03 (Autopilot, Finance Magnates, explainx) vs live on 2026-04-01 (X thread, Finbold) vs "launched in April" (BeInCrypto via Phemex).
- Who decides:
  - "built to keep humans fully out" (X, Mar 31).
  - "the final decision is the model's completely" (Lopez-Lira to Business Insider, 2026-07-25).
  - "Claude did not independently manage the portfolio" (Finance Magnates, 2026-09-07).
  - The operator decides (explainx's reading).
- Performance path: about +10%, "roughly the same as the S&P 500" (AI Street, about Jul 27) vs +19.04% against +12.24% (operator, Aug 4).
- Early record: Apr 2, the X post claimed outperformance while Finbold's own numbers showed underperformance. Mid-May: +2.6% vs +8.3% (BeInCrypto mirror), after +4.2% vs +0.6% on Apr 14.
- Holdings count: "15 individual stocks or ETFs" vs a top-3 plus "17 other" listing (20) on the same Autopilot page.
- DeepSeek portfolio launch: "2023" (Business Insider) vs 2025-02-03 (Autopilot). Business Insider is probably wrong.

NOT RE-CHECKED (carried from the researchers; lower weight)
- Insider Monkey posts (promotional).
- AI Finance Labs X post of about 2026-08-24 ($40M, 9,000+ subscribers): search snippet only, the page returned 402.
- polymaster X post (+14.6%): returned 402.
- Investment Officer (paywalled).
- De Belegger 2026-04-14; Bitcoin Street Journal.
- nof1 Season 1.5 beyond ForkLog; FT Alphaville; TradeRank/Flat Circle; Finder.
- Glasserman and Lin; Profit Mirage; AI-Trader; StockBench.
- Barber et al.; Apesteguia et al.
- SEC/NASAA/FINRA/ESMA items; InvestmentNews.
- StartupHub's "Sonnet 4.6".
