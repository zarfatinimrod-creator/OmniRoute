# Can the bot make real money? Evidence review, 2026-11-16

Asked by the owner on 2026-11-16. Four independent read-only analysts (stocks, news, crypto, alternatives) and
one red team, all Opus, wrote nothing and registered no trial. The full analyst output is in the workflow journal
(wf_26bd6128-c07). Every number below comes from a file in this repo.

## Verdict
No, not in its current form. The bot does make money in the backtest. But it earns about half of what a
cheap index fund earns, it carries more operational risk, and real costs and taxes are not modelled yet.

## Stock book
- **Sweep (2026-11-14, run 59a459da5016, `state/trials.jsonl`):**
  - Sharpe 0.418 against SPY's 0.608.
  - CAGR 7.40% against 14.07%.
  - maxDD -11.5% against -33.7%.
  - P(Sharpe > SPY) is 0.195.
  - Sharpe drops to 0.204 at 15 bp of costs and to -0.224 at 30 bp, where CAGR is 0.97%, below cash.
- **Exposure, not skill:**
  - Beta to SPY is 0.33. Alpha is about +0.5% a year, t about 0.2 (computed from the run record).
  - A static 35% SPY / 65% cash mix gives CAGR 7.53% and maxDD -12.6% with no trading.
  - Its Sharpe equals SPY's by construction (the red team's correction).
  - The drawdown is also partly the -10% breaker setting. The bootstrap maxDD range is -28.6% to -10.2%.
- **No selection edge:**
  - The placebo gate passes no signal: max |z| 0.86 against a 1.056 gate (`state/placebo.json`).
  - Learned weights equal the priors on all 2,229 days.
  - The combined score's 5-day IC is 0.015 (t 1.15).
  - breakout (20% weight) and high52 point the wrong way.
  - tsmom and xsmom correlate 0.94.
- **Frictions not yet modelled, all against the bot:**
  - The universe is today's survivors. Equal-weight is 18.8% a year, and 15.4% without the top 10 winners.
  - Cash earns a flat 3.5% a year.
  - Costs are 5 bp all-in.
  - Gains realized every year would be taxed (Israel, about 25%, unverified).
  - Turnover is 14.73x a year, about 340 trades.

## News book
- **No trades on correct data:** 0 of 2,604 correctly fed scores were above 8. The only trade, MU, came from the
  data bug.
- **No measured information:**
  - The score repeats today's move (correlation 0.54).
  - After controlling for the move, there is no significant extra information.
  - Grading covers only 4 dates, and NVDA is 283 of 578 graded rows.
- **Feed latency:** Yahoo RSS is about 10 minutes late (median). The published evidence says the first 15 minutes
  cannot be traded.

## Crypto book
- **Backtest against BTC:**
  - CAGR 16.9% against 20.95% for holding BTC.
  - maxDD -31.9% against -81.5%.
  - DSR 0.294.
- **The one fair comparison it wins:** against an exposure-matched static 33% BTC mix, timing came out ahead
  (Sharpe 0.693 against 0.619). It is still unproven.
- **What hurts it:**
  - Fees of 50 bp per side.
  - Whipsaw: the 2% band is about one daily sigma.
  - Yahoo data defects (backlog 68, 70, 72).

## Gaps the red team found
- **The real-money gate can pass by luck.** The current gate is "3 months beating SPY" (CLAUDE.md hard rule 1).
  On the backtest's own daily returns, the bot beats SPY's Sharpe in 33.6% of rolling quarters.
- **The phase spread is a noise floor.** It moves Sharpe from 0.303 to 0.527 just by changing the rebalance day.
- **Effort goes mostly to infrastructure** (supervisor, about 700 tests, a 407-line backlog), not to finding an
  edge.

## Fixes, ordered by evidence per effort
1. **Real money goes to a low-cost broad index fund.** Choose the stock/T-bill split by the drawdown the owner
   can tolerate. Freeze the strategy parameters: no new looks at 2018-2026.
2. **Replace the real-money gate (owner's decision).** At least 12 months forward. Compare the paper bot with SPY
   and with an exposure-matched SPY/T-bill paper mix, after real costs. Pass only at P(Sharpe > SPY) >= 0.8.
3. **Build the residual-edge gate (backlog 5)** with matched static-mix rows. It can be computed on the existing
   run record with no new trial.
4. **Edge search, log-only, with a sealed holdout (backlog 6):** opportunistic insider purchases from SEC Form 4
   (backlog 3: code P, officers and directors, the Cohen-Malloy-Pomorski routine filter), using point-in-time
   data. Then post-earnings drift (backlog 2). Write the kill criteria before looking at any result.
5. **News:** keep the hold. Seal the scorer (33). Test the score as a cross-sectional IC across all headlines
   only after 40 or more distinct dates. Consider it as a veto on quant entries, forward only.
6. **Crypto:**
   - Use a cheaper venue, 25 bp or less.
   - Take the venue's own daily candle as the source, with Yahoo as the cross-check.
   - Pre-register at most 3 anti-whipsaw variants.
   - Add a static-mix control to the sweep.
   - Judge it as a way to hold BTC with limited drawdown, not as a money-maker.
7. **Measure the owner's real broker costs and taxes** and the break-even bps for each path.
