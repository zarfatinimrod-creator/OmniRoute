# Lessons (semantic memory)

Format: date | observation | evidence | confidence | what would change my mind.
A lesson changes behaviour only after the time machine + quant-critic confirm it (CLAUDE.md rule 4).

- 2026-11-09 | VIX-percentile defensive mode (VIX >= 80th pct of trailing year -> gross x0.75) improves risk-adjusted results | time machine 2018-01-02..2026-11-06, 93 symbols: Sharpe 0.70 -> 0.85, maxDD -13.9% -> -11.5%, Calmar 0.51 -> 0.77 (research/2026-11-09-time-machine-sweep.txt) | medium | a sweep where the gain disappears at 15bps costs or on the ETF-only universe
- 2026-11-09 | Learned signal weights beat fixed priors | same sweep: Sharpe 0.73 (prior) vs 0.85 (learned), same turnover | medium | live forward months where learned weights trail the prior book
- 2026-11-09 | Costs dominate: turnover ~15x/yr; at 15bps Sharpe falls to 0.55, at 30bps to 0.36 | same sweep | high | lower-turnover variant keeping Sharpe >= 0.8 at 15bps
- 2026-11-09 | Much of the stock-universe edge may be survivorship bias: ETF-only (bias-free) Sharpe 0.52 vs equal-weight ETFs 0.81 | same sweep | medium | point-in-time S&P 500 universe backtest showing Sharpe >= SPY
- 2026-11-09 | The bot is "calmer, not better": maxDD -11.5% vs SPY -33.7%, but CAGR 8.9% vs 13.8% | same sweep | high | forward paper results beating SPY risk-adjusted for 3+ months
- 2026-11-09 | The earlier "learned weights beat priors" (Sharpe 0.85 vs 0.73) was noise-fitting: with an empirical-Bayes learner and a placebo gate (signals shuffled across stocks, K=100, noise z95=1.06), no signal passes (max |z| 0.86 lowvol, 0.41 xsmom) and learned == prior | state/placebo.json; research/2026-11-09-time-machine-sweep-v2.txt (base Sharpe 0.76, identical rows) | high | a signal whose shrunk |z| exceeds the gate on a later recompute
- 2026-11-09 | Research-based priors (reversal/high52/rsi2 demoted, lowvol as a new-entry filter) generalize better: ETF-only Sharpe 0.52 -> 0.70, 15bps Sharpe 0.55 -> 0.59; stock-universe Sharpe 0.76 (vs SPY 0.78) with maxDD -11.9% (vs -33.7%) | sweep v2 vs v1 | medium | forward paper months diverging from these numbers
- 2026-11-09 | Both risk gates carry real weight: without the SMA200 regime filter Sharpe 0.59, without the VIX defensive mode 0.55 (base 0.76) | sweep v2 | medium | a point-in-time universe test where the gates stop helping
