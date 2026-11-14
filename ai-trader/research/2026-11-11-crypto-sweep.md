# Crypto sweep - 2026-11-11

Source: `aitrader/crypto_sweep.py` run_sweep (spec 2026-11-09-crypto-book-design section 7). Window 2018-01-01 to 2026-11-10, halves split at 2022-01-01; 7 paired rebalance phases (7-day cycle). Fees 50 / 100 bp per side, plus slippage 5 bp and exec delay 10 bp (backtest only). Sharpe = annualised (365 days), excess over cash.

**Ship: crypto_base.** A pass rule failed, so crypto_base ships.

DSR of crypto_base: 0.294 (N=236 trials: 145 seeded, 0 from earlier sweeps, 91 per-phase runs here; per-period Sharpe spread 0.01843; daily series: phase 0 excess returns of the shipped profile at 50 bp). No proven edge (DSR below 0.95).

## Ablations (candidate at 50 bp; dropped when the paired median delta Sharpe >= 0)

| component | run | median dSharpe vs candidate | dropped |
|---|---|---:|---|
| no ETH | abl:no_eth | -0.056 | no |
| no ATR stop | abl:no_atr_stop | -0.155 | no |
| no -25% halving step | abl:no_halve | 0.057 | yes |

Final candidate: candidate, no -25% halving step (run `abl:no_halve`). Config change needed before it can ship: `{"risk.dd_halve": -1.0}`.

## Pass rule (final candidate vs crypto_base)

| rule | value | needs | pass |
|---|---|---|---|
| paired phases won (Sharpe, 50 bp) | 3/7 | >= 6/7 | NO |
| block-bootstrap P(dSharpe > 0) | 0.491 | >= 0.95 | NO |
| median maxDD, points worse | 0.0667 | <= 0.02 | NO |
| median paired dSharpe at 100 bp | -0.0884 | > 0 | NO |
| median paired dSharpe, each half | [0.5382, -0.5251] | > 0 each | NO |

## Runs

| run | profile | universe | fee bp | lag | window | Sharpe med [min, max] | maxDD med | CAGR med | vs | dSharpe med | wins |
|---|---|---|---:|---:|---|---|---:|---:|---|---:|---|
| base@50 | crypto_base | BTC | 50 | 1 | 2018-01-01..2026-11-10 | 0.786 [0.767, 0.813] | -0.319 | 0.169 | - | n/a | - |
| cand@50 | crypto | BTC+ETH | 50 | 1 | 2018-01-01..2026-11-10 | 0.713 [0.626, 0.797] | -0.342 | 0.124 | base@50 | -0.065 | 0/7 |
| abl:no_eth | crypto | BTC | 50 | 1 | 2018-01-01..2026-11-10 | 0.708 [0.466, 0.739] | -0.323 | 0.121 | cand@50 | -0.056 | 1/7 |
| abl:no_atr_stop | crypto | BTC+ETH | 50 | 1 | 2018-01-01..2026-11-10 | 0.563 [0.522, 0.647] | -0.316 | 0.101 | cand@50 | -0.155 | 1/7 |
| abl:no_halve | crypto | BTC+ETH | 50 | 1 | 2018-01-01..2026-11-10 | 0.803 [0.721, 0.873] | -0.385 | 0.156 | cand@50 | 0.057 | 7/7 |
| base@100 | crypto_base | BTC | 100 | 1 | 2018-01-01..2026-11-10 | 0.724 [0.704, 0.741] | -0.334 | 0.152 | - | n/a | - |
| final@100 | crypto | BTC+ETH | 100 | 1 | 2018-01-01..2026-11-10 | 0.652 [0.565, 0.725] | -0.423 | 0.120 | base@100 | -0.088 | 1/7 |
| base:h1 | crypto_base | BTC | 50 | 1 | 2018-01-01..2021-12-31 | 0.799 [0.761, 0.886] | -0.319 | 0.174 | - | n/a | - |
| final:h1 | crypto | BTC+ETH | 50 | 1 | 2018-01-01..2021-12-31 | 1.392 [1.232, 1.494] | -0.214 | 0.335 | base:h1 | 0.538 | 7/7 |
| base:h2 | crypto_base | BTC | 50 | 1 | 2022-01-01..2026-11-10 | 0.772 [0.737, 0.794] | -0.217 | 0.165 | - | n/a | - |
| final:h2 | crypto | BTC+ETH | 50 | 1 | 2022-01-01..2026-11-10 | 0.236 [0.182, 0.353] | -0.259 | 0.027 | base:h2 | -0.525 | 0/7 |
| control:btc_xrp | control | BTC+XRP | 50 | 1 | 2018-01-01..2026-11-10 | 0.750 [0.637, 0.939] | -0.384 | 0.145 | base@50 | -0.032 | 3/7 |
| final:missed_night | crypto | BTC+ETH | 50 | 2 | 2018-01-01..2026-11-10 | 0.690 [0.615, 0.733] | -0.389 | 0.129 | base@50 | -0.106 | 0/7 |

BTC buy&hold over the window (a benchmark, not a trial): Sharpe 0.621, maxDD -0.8153, CAGR 0.2095.

## Ranges (95% stationary block bootstrap: mean block 30 days, 2000 resamples, seed 0; shortest run 1460 days / 30 = 48.7 blocks, floor 40)

| run | Sharpe med [95% range] | CAGR med [95% range] | maxDD med [95% range] | P(Sharpe > BTC hold) | vs | P(Sharpe > vs) |
|---|---|---|---|---:|---|---:|
| base@50 | 0.786 [-0.059, 1.564] | 0.1685 [-0.0351, 0.4307] | -0.3187 [-0.6660, -0.2425] | 0.723 | - | - |
| cand@50 | 0.713 [-0.067, 1.478] | 0.1238 [-0.0248, 0.3246] | -0.3425 [-0.5633, -0.2127] | 0.604 | base@50 | 0.395 |
| abl:no_eth | 0.708 [-0.112, 1.425] | 0.1210 [-0.0318, 0.3100] | -0.3227 [-0.5718, -0.2061] | 0.552 | cand@50 | 0.350 |
| abl:no_atr_stop | 0.563 [-0.262, 1.378] | 0.1006 [-0.0693, 0.3246] | -0.3159 [-0.7064, -0.2498] | 0.411 | cand@50 | 0.157 |
| abl:no_halve | 0.803 [-0.009, 1.582] | 0.1559 [-0.0195, 0.3861] | -0.3853 [-0.5879, -0.2274] | 0.692 | cand@50 | 0.806 |
| base@100 | 0.724 [-0.128, 1.505] | 0.1516 [-0.0502, 0.4086] | -0.3336 [-0.6963, -0.2514] | 0.640 | - | - |
| final@100 | 0.652 [-0.196, 1.445] | 0.1203 [-0.0542, 0.3467] | -0.4226 [-0.6518, -0.2486] | 0.503 | base@100 | 0.361 |
| base:h1 | 0.799 [-0.665, 2.136] | 0.1742 [-0.1502, 0.6951] | -0.3187 [-0.6504, -0.1936] | 0.488 | - | - |
| final:h1 | 1.392 [0.191, 2.460] | 0.3347 [0.0183, 0.8209] | -0.2140 [-0.4021, -0.1444] | 0.901 | base:h1 | 0.970 |
| base:h2 | 0.772 [-0.097, 1.638] | 0.1652 [-0.0416, 0.4488] | -0.2169 [-0.5002, -0.1681] | 0.818 | - | - |
| final:h2 | 0.236 [-0.745, 1.200] | 0.0272 [-0.1375, 0.2584] | -0.2587 [-0.6104, -0.2009] | 0.350 | base:h2 | 0.021 |
| control:btc_xrp | 0.750 [-0.060, 1.561] | 0.1447 [-0.0265, 0.4031] | -0.3838 [-0.5943, -0.2277] | 0.641 | base@50 | 0.446 |
| final:missed_night | 0.690 [-0.192, 1.490] | 0.1286 [-0.0540, 0.3595] | -0.3891 [-0.6537, -0.2415] | 0.536 | base@50 | 0.309 |

Each estimate is followed by the range it falls in on 95% of the resampled histories. A Sharpe range that reaches below 0 means even the sign is not established.
P(Sharpe > BTC hold) and P(Sharpe > vs) are the share of resamples in which the row's Sharpe was the higher one on the same resampled days (paired; a tie counts half). They are probabilities under resampling, not verdicts: 0.5 means no difference was seen.
A row is the median over its rebalance phases; the phases hold nearly the same book, so they are not independent tests. The maxDD range is approximate: reshuffled days break the path the drawdown breaker reacted to.
These ranges are informative: the pass rule above is unchanged and reads none of them (its own block-bootstrap P is the moving-block one of the spec).

## Run record

run 2026-11-11-b35ca714d673: state/crypto/trial_runs/2026-11-11-b35ca714d673.json.gz (1,142,478 bytes) - every run's daily returns, the per-phase rows and the table rows.
code commit 7d580f8cab7fd28902964b690844321384cf0d3d (uncommitted code changes: no) | config sha256 f4bf7381702d | closes sha256 c5d674fd6381
compare two runs row by row: python3 -m aitrader --book crypto backtest --compare <run A> <run B>

## Merged configs

### crypto_base

```json
{
 "account": {
  "starting_cash": 100000,
  "cash_yield_annual": 0,
  "paper_only": true,
  "dividend_withholding": 0.25
 },
 "calendar": {
  "_note": "NYSE full-day holidays and 13:00 ET early closes (source: vendor/jake-trader-skill-v2/trader-alerts/alerts.py). Years not listed in 'years' count as closed (the news engine will not trade). Extend before 2028; a test fails from October of the last listed year.",
  "years": [
   2026,
   2027
  ],
  "holidays": [
   "2026-01-01",
   "2026-01-19",
   "2026-02-16",
   "2026-04-03",
   "2026-05-25",
   "2026-06-19",
   "2026-07-03",
   "2026-09-07",
   "2026-11-26",
   "2026-12-25",
   "2027-01-01",
   "2027-01-18",
   "2027-02-15",
   "2027-03-26",
   "2027-05-31",
   "2027-06-18",
   "2027-07-05",
   "2027-09-06",
   "2027-11-25",
   "2027-12-24"
  ],
  "early_close": [
   "2026-11-27",
   "2026-12-24",
   "2027-11-26"
  ]
 },
 "market": {
  "calendar": "utc_daily",
  "periods_per_year": 365,
  "history": "max",
  "vix": false,
  "earnings_blackout": false,
  "overlays": false,
  "corporate_actions": false,
  "news_engine": false,
  "fill_regime_on_no_picks": true,
  "equity_mark_per_bar": true,
  "delete_proposal_on_decision": true,
  "grading": "absolute",
  "stale_skips_run": true,
  "close_source": "next_open",
  "coinbase_guard_pct": 0.01,
  "report_dir": "reports/crypto",
  "intraday_alert_pct": 0.08,
  "latest_max_age_hours": 26,
  "state_subdir": "crypto",
  "etf_groups": [],
  "quiet_hours": {
   "tz": "Asia/Jerusalem",
   "from": "23:00",
   "to": "08:00"
  },
  "frozen_alert_runs": 2,
  "revised_close_alert_bps": 5,
  "fill_max_wait_hours": 24,
  "fill_urgent_after_hours": 3
 },
 "benchmark": "BTC-USD",
 "universe": {
  "BTC-USD": "Crypto"
 },
 "costs": {
  "slippage_bps": 5,
  "commission_per_share": 0.0,
  "fee_bps": 50,
  "exec_delay_bps": 10,
  "qty_step": 1e-06
 },
 "risk": {
  "target_vol_annual": 0.3,
  "max_gross": 1.0,
  "max_position_pct": 1.0,
  "max_etf_position_pct": 0.2,
  "max_sector_pct": 1.0,
  "max_positions": 2,
  "min_score": -1.0,
  "regime_sma_days": 200,
  "risk_off_gross_mult": 0.0,
  "dd_halve": -1.0,
  "dd_flat": -0.5,
  "atr_days": 14,
  "atr_stop_mult": 0.0,
  "rebalance_band_pct": 0.05,
  "min_trade_value": 100,
  "vol_lookback_days": 60,
  "exit_score": -1.01,
  "keep_rank_mult": 2.0,
  "rebalance_every_days": 7,
  "stop_cooldown_days": 14,
  "defensive_vix_pct": 0,
  "defensive_gross_mult": 0.75,
  "earnings_blackout_days": 4,
  "lowvol_exclude_top_pct": 0.0,
  "lowvol_exclude_lookback": 252,
  "earnings_max_position_pct": 0.05,
  "regime_band_pct": 0.02,
  "regime_band_mode": "hysteresis",
  "dd_reentry_days": 20,
  "lowvol_exclude_min_names": 10,
  "max_position_pct_by_symbol": {
   "BTC-USD": 1.0,
   "ETH-USD": 0.6,
   "XRP-USD": 0.6
  },
  "dd_reentry_ref": -0.25
 },
 "signals": {
  "tsmom": {
   "lookback": 365,
   "skip": 30
  },
  "xsmom": {
   "lookback": 252,
   "skip": 21
  },
  "trend": {
   "fast": 50,
   "slow": 200
  },
  "reversal": {
   "lookback": 5
  },
  "lowvol": {
   "lookback": 60
  },
  "high52": {
   "lookback": 252
  },
  "breakout": {
   "lookback": 80
  },
  "rsi2": {
   "period": 2,
   "trend_sma": 200
  }
 },
 "prior_weights": {
  "tsmom": 0.0,
  "xsmom": 0.0,
  "trend": 1.0,
  "breakout": 0.0,
  "high52": 0.0,
  "reversal": 0.0,
  "rsi2": 0.0,
  "lowvol": 0.0
 },
 "learning": {
  "horizons_days": [
   7,
   30,
   90
  ],
  "primary_horizon_days": 20,
  "default_horizon": 30,
  "ic_half_life_days": 504,
  "eta": 0.3,
  "weight_floor": 0.02,
  "weight_cap": 0.35,
  "max_step": 0.02,
  "update_every_days": 21,
  "tau": 0.02,
  "ic_sd_floor": 0.15,
  "z_cap": 2.5,
  "min_n_eff": 12,
  "enabled": false,
  "ic_min_names": 10
 },
 "alerts": {
  "ntfy_topic_env": "AITRADER_NTFY_TOPIC",
  "telegram_token_env": "AITRADER_TELEGRAM_TOKEN",
  "telegram_chat_env": "AITRADER_TELEGRAM_CHAT"
 },
 "sec_user_agent": "ai-trader-research-bot contact@example.com",
 "news": {
  "_note": "Owner's rules 2026-11-09: buy only if Claude's headline score > 8; max 5% of the account per trade; sell at -3% from entry, no exceptions. sell_on_score_at_most and max_hold_days are Claude's additions (set to 0 to disable). block_buys_until_loss_reviewed: Claude's reduce-only addition that keeps the owner's order of 2026-11-10 (Basic law, item 3: every loss is studied). While a realized news loss has no review in state/postmortems.jsonl the engine opens no new position; sales and stops are never held back; false switches it off. Exit lever: `python3 -m aitrader news-exit SYMBOL --reason TEXT` asks the engine to sell a held name at its next live quote and keeps it from buying that name that day (state/news_exits.json; `--cancel` takes a waiting request back); it never buys and never weakens the stop.",
  "poll_seconds": 20,
  "fresh_minutes": 30,
  "buy_min_score": 8,
  "max_position_pct": 0.05,
  "stop_loss_pct": 0.03,
  "sell_on_score_at_most": 2,
  "max_hold_days": 5,
  "max_gross": 1.0,
  "slippage_bps": 10,
  "starting_cash": 100000,
  "model": "claude-haiku-5-5",
  "trade_outside_hours": false,
  "batch_max": 12,
  "max_quote_age_minutes": 3,
  "chain_check_seconds": 300,
  "alert_after_errors": 5,
  "stop_blind_alert_seconds": 300,
  "block_buys_until_loss_reviewed": true,
  "_note_guards": "Added after the MU loss of 2026-11-10 (state/postmortems.jsonl). Each can only refuse a buy or bring a sale forward. guards: the no-chase limit (max_day_move_pct_to_buy), the second check (verify_*) and the stop cooldown (rebuy_cooldown_sessions) are new rules, not repairs, and they rest on one loss: with guards = log (the default) they only write to state/news_checks.jsonl what they would have refused and change no trade; with guards = enforce they refuse. Enforcing is a rule change: on evidence it may be proposed only after 30 or more graded above-the-line headlines in news_checks.jsonl with |t| > 2 for the guard (skills/trader/SKILL.md section 3, item 5), through rule 4 and with the owner's answer; before that it is only the owner's own choice to reduce risk, and is put to him as such (one case, no forward record). Do NOT set enforce yet: in that mode the second check runs inside the batch and can age the quote of a bad-news sale behind it (state/backlog.md, item 35); the batch must first be handled in two passes, sales before buys. require_known_move is a repair (Basic law, item 1: missing data, no trade) and is always enforced: no buy in session when today's move of the stock is not known. max_day_move_pct_to_buy: the stock is already up this many percent today (3 = the stop distance, not a measured number; 0 switches it off). rebuy_cooldown_sessions: a name sold at its stop, until this many sessions have opened since (1 = the day of the stop). verify_buys: with guards = enforce, before a buy or a place in the queue, verify_calls independent checks must each call the headline a new, confirmed event of one of verify_allow_kinds (verify_model null = news.model), and with verify_rescore the same scorer, asked again, must still score it above buy_min_score; a check that fails or does not answer within verify_timeout_seconds is a refusal. With guards = log the same questions are asked after the buy, in the background (verify_parallel at a time), and only written down; they hold up no buy, no sale and no look at a stop, and an answer that is still out when a run ends in market hours is dropped, not waited for. stop_catchup: when a held name's stop was not looked at for more than stop_catchup_gap_seconds (engine down, a stalled step, no live quote), today's 1-minute bars of that stretch are read once at least stop_catchup_min_seconds of it have passed; a bar that closed at or under the stop, or stop_catchup_min_lows bars with a low at or under it, means the stop was traded through unseen (bars are trusted only when, for a stretch of stop_catchup_min_minutes or more, at least stop_catchup_min_bar_share of its minutes are there). alert (default until the owner decides): he is told at once and the position stays on its normal stop. sell: it is also sold at its first live quote that day. off: no look.",
  "require_known_move": true,
  "max_day_move_pct_to_buy": 3.0,
  "rebuy_cooldown_sessions": 1,
  "verify_buys": true,
  "verify_calls": 2,
  "verify_rescore": true,
  "verify_timeout_seconds": 60,
  "verify_model": null,
  "verify_allow_kinds": [
   "company_announcement",
   "regulator_or_counterparty"
  ],
  "guards": "log",
  "stop_catchup": "alert",
  "stop_catchup_gap_seconds": 90,
  "stop_catchup_min_seconds": 120,
  "stop_catchup_min_lows": 2,
  "stop_catchup_min_minutes": 4,
  "stop_catchup_min_bar_share": 0.5,
  "verify_parallel": 1,
  "health_log_seconds": 300,
  "seen_keep_days": 3,
  "exits_lock_wait_seconds": 1.0,
  "exits_lock_retry_seconds": 0.05
 },
 "postmortem": {
  "_note": "Basic law, item 3 (loss reviews, aitrader/postmortem.py). min_chars: the shortest text a review may have in each answer, so a one-word review cannot clear a loss (fix_ref: where the fix lives, a commit or a backlog item; not asked of a planned loss). min_key_chars: how many characters of a sale's hash a review must give to name it.",
  "min_chars": {
   "what": 40,
   "lesson": 20,
   "fix": 10,
   "fix_ref": 7
  },
  "min_key_chars": 8
 },
 "bootstrap": {
  "block_days": 20,
  "draws": 2000,
  "seed": 0,
  "level": 0.95,
  "min_blocks": 40
 },
 "drift": {
  "pause_seconds": 1.5
 },
 "profile": "crypto_base"
}
```

### crypto (candidate)

```json
{
 "account": {
  "starting_cash": 100000,
  "cash_yield_annual": 0,
  "paper_only": true,
  "dividend_withholding": 0.25
 },
 "calendar": {
  "_note": "NYSE full-day holidays and 13:00 ET early closes (source: vendor/jake-trader-skill-v2/trader-alerts/alerts.py). Years not listed in 'years' count as closed (the news engine will not trade). Extend before 2028; a test fails from October of the last listed year.",
  "years": [
   2026,
   2027
  ],
  "holidays": [
   "2026-01-01",
   "2026-01-19",
   "2026-02-16",
   "2026-04-03",
   "2026-05-25",
   "2026-06-19",
   "2026-07-03",
   "2026-09-07",
   "2026-11-26",
   "2026-12-25",
   "2027-01-01",
   "2027-01-18",
   "2027-02-15",
   "2027-03-26",
   "2027-05-31",
   "2027-06-18",
   "2027-07-05",
   "2027-09-06",
   "2027-11-25",
   "2027-12-24"
  ],
  "early_close": [
   "2026-11-27",
   "2026-12-24",
   "2027-11-26"
  ]
 },
 "market": {
  "calendar": "utc_daily",
  "periods_per_year": 365,
  "history": "max",
  "vix": false,
  "earnings_blackout": false,
  "overlays": false,
  "corporate_actions": false,
  "news_engine": false,
  "fill_regime_on_no_picks": true,
  "equity_mark_per_bar": true,
  "delete_proposal_on_decision": true,
  "grading": "absolute",
  "stale_skips_run": true,
  "close_source": "next_open",
  "coinbase_guard_pct": 0.01,
  "report_dir": "reports/crypto",
  "intraday_alert_pct": 0.08,
  "latest_max_age_hours": 26,
  "state_subdir": "crypto",
  "etf_groups": [],
  "quiet_hours": {
   "tz": "Asia/Jerusalem",
   "from": "23:00",
   "to": "08:00"
  },
  "frozen_alert_runs": 2,
  "revised_close_alert_bps": 5,
  "fill_max_wait_hours": 24,
  "fill_urgent_after_hours": 3
 },
 "benchmark": "BTC-USD",
 "universe": {
  "BTC-USD": "Crypto",
  "ETH-USD": "Crypto"
 },
 "costs": {
  "slippage_bps": 5,
  "commission_per_share": 0.0,
  "fee_bps": 50,
  "exec_delay_bps": 10,
  "qty_step": 1e-06
 },
 "risk": {
  "target_vol_annual": 0.3,
  "max_gross": 1.0,
  "max_position_pct": 1.0,
  "max_etf_position_pct": 0.2,
  "max_sector_pct": 1.0,
  "max_positions": 2,
  "min_score": 0.15,
  "regime_sma_days": 200,
  "risk_off_gross_mult": 0.0,
  "dd_halve": -0.25,
  "dd_flat": -0.5,
  "atr_days": 14,
  "atr_stop_mult": 3.0,
  "rebalance_band_pct": 0.05,
  "min_trade_value": 100,
  "vol_lookback_days": 60,
  "exit_score": 0.0,
  "keep_rank_mult": 2.0,
  "rebalance_every_days": 7,
  "stop_cooldown_days": 14,
  "defensive_vix_pct": 0,
  "defensive_gross_mult": 0.75,
  "earnings_blackout_days": 4,
  "lowvol_exclude_top_pct": 0.0,
  "lowvol_exclude_lookback": 252,
  "earnings_max_position_pct": 0.05,
  "regime_band_pct": 0.02,
  "regime_band_mode": "hysteresis",
  "dd_reentry_days": 20,
  "lowvol_exclude_min_names": 10,
  "max_position_pct_by_symbol": {
   "BTC-USD": 1.0,
   "ETH-USD": 0.6,
   "XRP-USD": 0.6
  }
 },
 "signals": {
  "tsmom": {
   "lookback": 365,
   "skip": 30
  },
  "xsmom": {
   "lookback": 252,
   "skip": 21
  },
  "trend": {
   "fast": 50,
   "slow": 200
  },
  "reversal": {
   "lookback": 5
  },
  "lowvol": {
   "lookback": 60
  },
  "high52": {
   "lookback": 252
  },
  "breakout": {
   "lookback": 80
  },
  "rsi2": {
   "period": 2,
   "trend_sma": 200
  }
 },
 "prior_weights": {
  "tsmom": 0.3846,
  "xsmom": 0.0,
  "trend": 0.3077,
  "breakout": 0.3077,
  "high52": 0.0,
  "reversal": 0.0,
  "rsi2": 0.0,
  "lowvol": 0.0
 },
 "learning": {
  "horizons_days": [
   7,
   30,
   90
  ],
  "primary_horizon_days": 20,
  "default_horizon": 30,
  "ic_half_life_days": 504,
  "eta": 0.3,
  "weight_floor": 0.02,
  "weight_cap": 0.35,
  "max_step": 0.02,
  "update_every_days": 21,
  "tau": 0.02,
  "ic_sd_floor": 0.15,
  "z_cap": 2.5,
  "min_n_eff": 12,
  "enabled": false,
  "ic_min_names": 10
 },
 "alerts": {
  "ntfy_topic_env": "AITRADER_NTFY_TOPIC",
  "telegram_token_env": "AITRADER_TELEGRAM_TOKEN",
  "telegram_chat_env": "AITRADER_TELEGRAM_CHAT"
 },
 "sec_user_agent": "ai-trader-research-bot contact@example.com",
 "news": {
  "_note": "Owner's rules 2026-11-09: buy only if Claude's headline score > 8; max 5% of the account per trade; sell at -3% from entry, no exceptions. sell_on_score_at_most and max_hold_days are Claude's additions (set to 0 to disable). block_buys_until_loss_reviewed: Claude's reduce-only addition that keeps the owner's order of 2026-11-10 (Basic law, item 3: every loss is studied). While a realized news loss has no review in state/postmortems.jsonl the engine opens no new position; sales and stops are never held back; false switches it off. Exit lever: `python3 -m aitrader news-exit SYMBOL --reason TEXT` asks the engine to sell a held name at its next live quote and keeps it from buying that name that day (state/news_exits.json; `--cancel` takes a waiting request back); it never buys and never weakens the stop.",
  "poll_seconds": 20,
  "fresh_minutes": 30,
  "buy_min_score": 8,
  "max_position_pct": 0.05,
  "stop_loss_pct": 0.03,
  "sell_on_score_at_most": 2,
  "max_hold_days": 5,
  "max_gross": 1.0,
  "slippage_bps": 10,
  "starting_cash": 100000,
  "model": "claude-haiku-5-5",
  "trade_outside_hours": false,
  "batch_max": 12,
  "max_quote_age_minutes": 3,
  "chain_check_seconds": 300,
  "alert_after_errors": 5,
  "stop_blind_alert_seconds": 300,
  "block_buys_until_loss_reviewed": true,
  "_note_guards": "Added after the MU loss of 2026-11-10 (state/postmortems.jsonl). Each can only refuse a buy or bring a sale forward. guards: the no-chase limit (max_day_move_pct_to_buy), the second check (verify_*) and the stop cooldown (rebuy_cooldown_sessions) are new rules, not repairs, and they rest on one loss: with guards = log (the default) they only write to state/news_checks.jsonl what they would have refused and change no trade; with guards = enforce they refuse. Enforcing is a rule change: on evidence it may be proposed only after 30 or more graded above-the-line headlines in news_checks.jsonl with |t| > 2 for the guard (skills/trader/SKILL.md section 3, item 5), through rule 4 and with the owner's answer; before that it is only the owner's own choice to reduce risk, and is put to him as such (one case, no forward record). Do NOT set enforce yet: in that mode the second check runs inside the batch and can age the quote of a bad-news sale behind it (state/backlog.md, item 35); the batch must first be handled in two passes, sales before buys. require_known_move is a repair (Basic law, item 1: missing data, no trade) and is always enforced: no buy in session when today's move of the stock is not known. max_day_move_pct_to_buy: the stock is already up this many percent today (3 = the stop distance, not a measured number; 0 switches it off). rebuy_cooldown_sessions: a name sold at its stop, until this many sessions have opened since (1 = the day of the stop). verify_buys: with guards = enforce, before a buy or a place in the queue, verify_calls independent checks must each call the headline a new, confirmed event of one of verify_allow_kinds (verify_model null = news.model), and with verify_rescore the same scorer, asked again, must still score it above buy_min_score; a check that fails or does not answer within verify_timeout_seconds is a refusal. With guards = log the same questions are asked after the buy, in the background (verify_parallel at a time), and only written down; they hold up no buy, no sale and no look at a stop, and an answer that is still out when a run ends in market hours is dropped, not waited for. stop_catchup: when a held name's stop was not looked at for more than stop_catchup_gap_seconds (engine down, a stalled step, no live quote), today's 1-minute bars of that stretch are read once at least stop_catchup_min_seconds of it have passed; a bar that closed at or under the stop, or stop_catchup_min_lows bars with a low at or under it, means the stop was traded through unseen (bars are trusted only when, for a stretch of stop_catchup_min_minutes or more, at least stop_catchup_min_bar_share of its minutes are there). alert (default until the owner decides): he is told at once and the position stays on its normal stop. sell: it is also sold at its first live quote that day. off: no look.",
  "require_known_move": true,
  "max_day_move_pct_to_buy": 3.0,
  "rebuy_cooldown_sessions": 1,
  "verify_buys": true,
  "verify_calls": 2,
  "verify_rescore": true,
  "verify_timeout_seconds": 60,
  "verify_model": null,
  "verify_allow_kinds": [
   "company_announcement",
   "regulator_or_counterparty"
  ],
  "guards": "log",
  "stop_catchup": "alert",
  "stop_catchup_gap_seconds": 90,
  "stop_catchup_min_seconds": 120,
  "stop_catchup_min_lows": 2,
  "stop_catchup_min_minutes": 4,
  "stop_catchup_min_bar_share": 0.5,
  "verify_parallel": 1,
  "health_log_seconds": 300,
  "seen_keep_days": 3,
  "exits_lock_wait_seconds": 1.0,
  "exits_lock_retry_seconds": 0.05
 },
 "postmortem": {
  "_note": "Basic law, item 3 (loss reviews, aitrader/postmortem.py). min_chars: the shortest text a review may have in each answer, so a one-word review cannot clear a loss (fix_ref: where the fix lives, a commit or a backlog item; not asked of a planned loss). min_key_chars: how many characters of a sale's hash a review must give to name it.",
  "min_chars": {
   "what": 40,
   "lesson": 20,
   "fix": 10,
   "fix_ref": 7
  },
  "min_key_chars": 8
 },
 "bootstrap": {
  "block_days": 20,
  "draws": 2000,
  "seed": 0,
  "level": 0.95,
  "min_blocks": 40
 },
 "drift": {
  "pause_seconds": 1.5
 },
 "profile": "crypto"
}
```
