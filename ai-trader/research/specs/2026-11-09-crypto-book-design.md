# Crypto book v1 - design spec (2026-11-09, rev 3.2)

Status: design approved by Nimrod in chat on 2026-11-09 (approach B, BTC + ETH, quiet nights, $100k).
- Rev 2 adds the fixes from the adversarial review of rev 1 (two reviewers, quant-critic and feasibility; workflow
  wf_1dd43fdd-358).
- Rev 3 adds the fixes from the quant-critic's review of rev 2. Their replay scripts are in
  `research/2026-11-09-crypto-replays/`.
This written spec still waits for his review. Paper money only.

Research behind every number: `research/2026-11-09-crypto-research.json` (workflow wf_123167eb-028). It has 7
entries: code impact, data, evidence, repos, risk, synthesis and critic.

## 1. Owner decisions (chat, 2026-11-09)

| # | Question | Answer |
|---|----------|--------|
| 1 | How to trade crypto | ג: in stages. v1 is a separate trend-following quant book. Crypto news comes in v2, after about a month of data and his decision on the stop rules |
| 2 | Alerts at night | א: only 08:00-23:00 Israel time. Night events go into one morning summary |
| 3 | Coins | א: BTC and ETH only (ETH ships only if it earns its place in the sweep, section 7) |
| 4 | Design (sections 1-3 in chat) | א: approved |
| 5 | Book size | א: $100,000 paper (asked 2026-11-09 with the worst-day example: BTC -37% on 2020-03-12) |

These are assumptions he has not been asked about. Each one is a config key:
- fees 0.50% per side, with a robustness run at 1.00%;
- cash yield 0%;
- BTC buy-and-hold is a research benchmark only.

The real-money gate stays CLAUDE.md rule 1: 3 months of paper results that beat SPY risk-adjusted.

## 2. Goal and success criteria

Goal: a paper crypto book that runs every night unattended. It uses the same engine as the stock book: the journal, the shadow book, reduce-only overrides and forward grading. Nimrod gets a morning summary of what happened.

v1 is done when all of these hold:
1. **The stock book is unchanged, except for the bar-final fix in section 4.** Every other behaviour change listed
   here (regime always filled, one equity mark per bar, deleting proposal.json) is gated to the crypto book by its
   `market` flags.
   - All existing tests pass.
   - Golden outputs recorded on the code before the refactor (section 7, step 0) still match byte for byte: a backtest equity curve and a scripted live-cycle run.
2. **The sweep has run and the gate is passed.**
   - A time-machine sweep on real history has decided between base and candidate by the pass rule in section 7.
   - The quant-critic returned PASS.
   - The revised-close check (section 4) is done.
3. **The night runs work end to end.**
   - Scheduled runs decide, fill, journal and commit state.
   - The morning summary arrives at 08:00 Israel time, winter and summer.
   - The dashboard shows the crypto book.

Expectation to set with Nimrod: "calmer, not richer". No performance number is shown to him before the sweep runs.
Where crypto P&L reaches him (morning summary, dashboard), "no proven edge" appears until DSR >= 0.95. The reviewers'
approximate replays (`research/2026-11-09-crypto-replays/power.py`, `ablate.py`) are design inputs, not results.

## 3. Architecture: one engine, two books

### 3.1 Config and the book switch
- `config.json` gains `"books": {"crypto": {...}, "crypto_base": {...}}`.
  - A book block is merged over the base config. These keys are **replaced, not merged**: `universe`, `prior_weights`, `signals`, `benchmark`.
  - `risk`, `costs`, `learning`, `market` and `alerts` merge key by key.
- At load time, assert that the crypto universe is exactly {BTC-USD, ETH-USD}, or {BTC-USD} for crypto_base. Also assert that the priors name every registered signal (zeros explicit) and sum to 1.
- The stock book gets an explicit `"market"` block with today's constants, so its defaults reproduce current behaviour (rule 5).
- **One switch.** `journal.use_book(book)` is a context manager.
  - On entry it captures the current `journal.STATE`. For stocks it leaves STATE as is; for crypto it sets
    `STATE = captured / "crypto"`. On exit it restores the captured value.
  - Tests keep swapping `journal.STATE` exactly as today (test_cycle, test_audit_fixes, test_critic_fixes,
    test_news_rules, and the subprocess in test_audit_fixes), and a book switch stays inside the temp dir.
  - `load_config()` with no argument returns the active book's merged config. Config and state cannot be mismatched.
  - Test: the whole suite writes nothing under the real `state/`.
- CLI: `--book crypto` on `cycle, status, scorecard, backtest, verify, predict, context, veto, shrink, summary`. The default is stocks.
  - `desk`, `brief` and `news*` are stock-only in v1 and refuse `--book crypto`. The crypto veto checklist lives in the trader skill instead (section 6.3).
  - The dashboard builds both books in one process via `use_book` (section 8), so it takes no `--book`.

### 3.2 Calendars (`aitrader/market.py`, new)
- `NyseCalendar` holds today's `_bar_is_final` (16:05 NY), `_market_opened` (09:31), `official_opens` (the 09:30 1-minute bar), BDay cooldown and the override cutoff. The logic is moved verbatim. cycle.py keeps thin module-level shims with the same names that delegate to the active calendar, so tests that patch `cycle._bar_is_final` etc. keep working unchanged.
- `UtcDailyCalendar`: bars close at 00:00 UTC, 7 days a week.
- Shared interface:
  - `periods_per_year`
  - `bar_is_final(bar, now, fetched_at)`
  - `exec_time(decision_logged_at)`
  - `fill_prices(names, exec_ts)`
  - `cooldown_until(fill_bar, n_bars)`
  - `override_cutoff_utc(exec_ts)`
  - `is_open(now)`

### 3.3 Engine changes
- **periods_per_year** (252 stocks, 365 crypto) goes into strategy.py:148 (cov), metrics.py:10, backtest.py:170-171
  and broker.mark. signals.py:29 annualizes with 252, but every use is scale-invariant, so it is left alone. desk.py
  is stock-only in v1. Using 252 understates crypto vol by 1.2035x (BTC, measured), so positions come out about 20% too big.
- **PaperBroker** gets two new config keys, `costs.qty_step` (stocks 1, crypto 1e-6) and `costs.fee_bps` (stocks 0, crypto 50). Rules:
  - **qty** = floor to qty_step of `min(delta_value, cash) / (px * (1+slip) * (1+fee) + commission_per_share)`.
    Cash never goes negative.
  - **Fees** are charged to cash and to realized P&L, and added to a running `fees_paid`.
  - **Dust:** sells round to the step, and a remainder below qty_step is deleted.
  - **Same costs everywhere:** the main, shadow and backtest brokers use the same settings. Stocks keep integer quantities, so their JSON is unchanged.
- **Backtest-only cost:** `costs.exec_delay_bps` (crypto 10). Measured: the 00:00 -> 01:00 UTC move, signed by trade side, averaged -12 bp (SE 6-9 bp, 78 trades; spec reviewer, specreview/code/delay.py). That makes 10 bp conservative.
- **Per-book feature flags** in `market`: `vix`, `earnings_blackout`, `overlays`, `corporate_actions`, `news_engine`.
  - All off for crypto, all on for stocks.
  - With earnings on, a Nasdaq outage sets "*", which blocks every crypto entry.
  - With VIX on, every live weekend goes defensive(no-vix).
- **Moved to config:** the group/ETF lists (strategy.py:10, news_live.py:34, dashboard.py:21, backtest.py:122) and the 10-name minimums (learn.py:21, strategy.py:120).
  - Learning gets an explicit `learning.enabled` flag, checked in backtest.run and cycle._learn. It is false for crypto.
  - Per-coin caps: `risk.max_position_pct_by_symbol` (BTC 1.0, ETH 0.6, XRP 0.6 for the hindsight control), applied
    where strategy.py:142 builds caps.
  - **The crypto `risk` block lists every key it uses**, so nothing is silently inherited from the stock values:
    `target_vol_annual, max_gross, max_position_pct, max_position_pct_by_symbol, max_sector_pct, max_positions,
    min_score, exit_score, keep_rank_mult, regime_sma_days, regime_band_pct, regime_band_mode,
    risk_off_gross_mult, dd_halve, dd_flat, dd_reentry_days, atr_days, atr_stop_mult, rebalance_band_pct,
    min_trade_value, vol_lookback_days, rebalance_every_days, stop_cooldown_days, lowvol_exclude_top_pct` (0).
    `atr_stop_mult = 0` means no stop: strategy.py skips the stop check when `atr_stop_mult <= 0`. Today a 0 would
    put the stop at the peak close, so every dip would fire it. `dd_halve = -1.0` means no halving step.
    New key `risk.dd_reentry_ref`: the drawdown the re-entry peak reset implies (broker.py:93).
    - It defaults to `(dd_halve + dd_flat) / 2`, so the stock book is byte-identical; crypto sets -0.25.
    - Without it, `dd_halve = -1.0` resets the peak to a -75% drawdown, which is still below -50%, so after the
      catastrophe step fires the book would stay in cash forever.
    - Crypto values: candidate `min_score` 0.15, `exit_score` 0.0; both profiles `vol_lookback_days` 60,
      `dd_reentry_days` 20 (the values the replays used).
    The sweep report prints the
    merged config of each profile.
  - **Each profile's panel is limited to its own universe** (`combine()` scores every panel column). Test:
    crypto_base never holds ETH.
- **Regime.** A new key, `risk.regime_band_mode`:
  - **"offset"** (stocks, today): risk-off while px < SMA x 0.98.
  - **"hysteresis"** (crypto): goes off below SMA x 0.98 and comes back on only above SMA x 1.02.
  - **Where it is computed:** in `precompute_aux`, as a causal state series built only from the benchmark close and its SMA200. It does not depend on picks or diag, and nothing is persisted: live recomputes it from full history each run. `build_targets` reads `aux["regime"].loc[date]` **before** the no-picks return and always fills `diag["regime"]`.
  - **Why hysteresis:** the evidence was measured with it. The offset rule switches 7.7-9.7 times/yr on BTC/ETH, against 3.5-4.3 for hysteresis (critic, band_check.txt).
- **Grading.** Crypto calls are graded on absolute return, i.e. excess over 0% cash; a BTC call graded against BTC means nothing. Horizons are in calendar days: 7 / 30 / 90.
- **Reports and labels.**
  - Reports go under `market.report_dir` (crypto: `reports/crypto/<date>.md`).
  - Benchmark labels are book-aware in report.py, dashboard.py and desk.py.
  - `proposal.json` is deleted when a decision is saved, so a stale proposal cannot misdate a veto.
- **Equity log (crypto):** one mark per decision bar D, written at decision time. Runs that do nothing write nothing,
  so Sharpe and the rule-1 measurement are not distorted by 2-3 rows a day. The stock book keeps writing every run.
- **Hard-coded alert numbers move to config:** the intraday -6% alert (cycle.py:382) becomes `market.intraday_alert_pct`
  (crypto 0.08). The dashboard's risk-off label is book-aware (crypto risk-off = cash).

## 4. Data
- **Source:** Yahoo chart API, which data.py already reads. Daily bars in UTC, weekends included, no gaps, adjclose == close, no corporate actions (data lens).
- **History:** fetched with `period1=0&period2=now`, asserting `meta.dataGranularity == "1d"`. `range=max` returns monthly bars, and `range=10y` starts in 2016-11.
- **Revised last close.** Yahoo rewrites the latest completed close.
  - On older bars close equals the next open exactly. The latest bar differed by 15.8-18.1 bp (BTC/ETH; critic and spec-reviewer re-fetches).
  - **Precondition to going live:** on or after 2026-11-11 16:00 UTC, re-fetch and record which value moved. Did the 11-08 close become 74,719.82 (the 11-09 open), or did the 11-09 open become 74,584.65? The answer goes in the config note.
  - The live rule follows the answer:
    - if the close moved, close_D = the open of the D+1 row, applied once, right after loading;
    - if the open moved, use Yahoo's close_D as fetched, and the look-ahead exception falls away.
  - If the D+1 row is missing at decision time, there is no decision; a later run retries.
  - Live logs both values. An alert fires if a stored decision close later differs from history by more than `market.revised_close_alert_bps` (config).
- **Partial bars from a stale cache.** A bar counts as final only if its symbol's data was fetched after the bar's end plus 5 minutes (cache file mtime).
  - A stale benchmark skips the run; a later run retries.
  - A stale symbol is frozen for that run. It is neither bought nor sold, and a held one keeps its current weight.
    Setting its bar to NaN would unscore it, and on a rebalance day that sells it (strategy.py:115, broker.py:128-137).
  - In the crypto book, any stale universe symbol skips the run (a later run retries).
  - The stock book has the same latent bug after intraday runs, and it is fixed there too. That is the one intended change to stock behaviour.
- **Live sanity guard:** Yahoo's decision close is compared with Coinbase's public candle (no key).
  - Gap above `market.coinbase_guard_pct` (1%): exits only. Stops and regime-off still run; no new entries.
  - Coinbase unreachable: proceed and log a warning.
- **Universe hindsight:** BTC + ETH is a choice made after the fact (XRP was top-3 by market cap in 2018). The report says so, and BTC+XRP runs as a hindsight control (section 7). A point-in-time universe (data.binance.vision) is v2.

## 5. Strategy profiles

**Lookback rule:** a stock lookback counted in months becomes calendar days (252 -> 365, 21 -> 30, 55 -> 80). Moving-average lengths stay as in the evidence (SMA200 on daily crypto bars, trend 50/200).

| Item | crypto (candidate) | crypto_base |
|------|--------------------|-------------|
| Universe | BTC-USD, ETH-USD | BTC-USD |
| Regime | BTC vs SMA200, hysteresis 2%, risk_off_gross_mult 0 | same |
| Signals / priors | tsmom 365/30, trend 50/200, breakout 80. Priors are the stock priors renormalised: 0.385 / 0.308 / 0.308. xsmom, high52, reversal, rsi2, lowvol all 0 | trend 1.0 (all others 0), min_score -1 and exit_score -1.01: hold BTC whenever the regime is on |
| Vol target | 30% annual (BTC 2y vol 44.1%, ETH 68.5%) | 30% |
| Caps | max_gross 1.0 (no leverage); BTC <= 1.0, ETH <= 0.6 of the book; max_sector_pct 1.0 | BTC <= 1.0 |
| Stop | 3x ATR14 trailing, judged at the daily close. About 9.9% for BTC and 13.9% for ETH; a fixed -3% is touched within 3 days by 37.8% / 51.4% of random entries | off (`atr_stop_mult` 0) |
| Drawdown breaker | halve at -25% (ablatable); **catastrophe step: flat at -50%**, re-entry via `dd_reentry_ref` -0.25 | **catastrophe step only: flat at -50%** (`dd_halve` -1.0, `dd_reentry_ref` -0.25) |
| Rebalance | every 7 days, band 0.05, min trade $100, stop cooldown 14 bars | same |
| Costs | fee 50 bp/side, slippage 5 bp, exec delay 10 bp. About 13x stock costs. Venues: Kraken Pro taker 80 bp; Coinbase Advanced 90 bp (secondary source); Alpaca 25 bp; Binance 10 bp; eToro publishes 1% | same |
| Cash yield / learning | 0 / off | 0 / off |

Book size (owner Q5: $100k) is set in `account.starting_cash`. Caps are fractions of the book, so they do not depend
on its size.

The catastrophe step (flat at -50%) is in both profiles and outside every comparison and ablation. Replays put maxDD
near -32%, so it costs nothing in-sample; it exists for the tail. Removing it needs Nimrod's explicit decision.

## 6. Live operation

### 6.1 Schedule
Three scheduled tasks run in the persistent trader session (session_012EDbLj2H3vpAR9xTMneEYo). Every task first runs the same idempotent command, `python3 -m aitrader cycle --book crypto`, so a missed task is caught up by the next one.

1. **00:12 UTC — decide.** The bar closes at 00:00 UTC, so this is UTC year-round.
   - Verify the crypto chains; on a break, stop (fail closed).
   - Fetch prices. Bar D counts as final when fetched after 00:05 UTC. Set close_D from the D+1 open.
   - Run stops, regime and breaker; rebalance if due.
   - Write the pending orders with exec_ts = max(01:00 UTC, the next full hour after the decision is logged).
   - Claude reads BTC/ETH headlines and may veto or shrink, reduce-only, with a concrete reason, until exec_ts (the override cutoff).
   - Commit and push.
2. **01:07 UTC — fill.**
   - Fill the pending orders at the open of the 1-hour bar starting at exec_ts.
   - If that bar is missing, use the 1-minute bar at exec_ts.
   - If both are missing, keep the orders pending and fill at the next available hourly open (02:00, ...). Never use the daily open: that is the price the signal saw.
   - Log where every fill price came from.
   - Then run the shadow book, grade predictions, commit and push.
3. **08:03 Asia/Jerusalem (`CRON_TZ=Asia/Jerusalem`) — morning summary.**
   - Runs `cycle --book crypto`, then `summary --book crypto`. That command prints the summary text and checks
     verify, the expected decision_date and the age of latest.json. Urgent items lead the text. It exits non-zero
     while any urgent item is queued.
   - **Delivery:** `notify.send` to ntfy (AITRADER_NTFY_TOPIC, configured 2026-11-09). If ntfy is not among the
     channels returned, the session sends the text with PushNotification.
   - Only after a confirmed delivery: `summary --book crypto --ack` clears the queue.
   - Rebuilds and uploads the dashboard snapshot.

### 6.2 Quiet hours
- `books.crypto.alerts.quiet_hours = {"tz": "Asia/Jerusalem", "from": "23:00", "to": "08:00"}`. Crypto only.
- During quiet hours every crypto message waits in `state/crypto/alert_queue.json`, urgent ones included (owner decision 2), and goes out in the morning summary.
- Test: the stock book still sends at 23:22.

### 6.3 Trader skill: new "crypto night" section
- The `--book crypto` commands.
- The crypto veto checklist: exchange or protocol hack, stablecoin depeg, regulatory action, chain halt. Reduce-only, with a concrete reason.
- **No PushNotification between 23:00 and 08:00 Israel time.** This crypto-night rule wins over the general "push
  Nimrod when a question or approval is needed" rule (SKILL.md section 5). A question that comes up at night goes into
  the morning summary.
- One log per night: `logs/YYYY-MM-DD-crypto-night.md`.
- Pushes use the corrected retry loop. `verify` is never piped.

Scheduled-task prompts (stored verbatim when created):
- **decide:**
  - "Crypto decide (paper). cd /home/user/OmniRoute && git pull --rebase. cd ai-trader && python3 -m aitrader verify --book crypto (if it exits 1, stop: cycle halts itself and the morning summary reports it).
  - python3 -m aitrader cycle --book crypto.
  - If new entries are pending: read BTC/ETH headlines (trader-news skill). Veto or shrink only with a concrete reason from the checklist, before exec_ts.
  - Commit + push with the retry loop. No PushNotification at night."
- **fill:** the same, minus the headline step.
- **summary:**
  - "Crypto morning summary (paper). cd /home/user/OmniRoute && git pull --rebase. cd ai-trader &&
    python3 -m aitrader cycle --book crypto.
  - python3 -m aitrader summary --book crypto. It exits non-zero if urgent items are queued; deliver the text anyway.
  - Deliver with notify.send (ntfy). If 'ntfy' is not among the returned channels, send the text with PushNotification.
  - Only after delivery: python3 -m aitrader summary --book crypto --ack.
  - Then refresh the dashboard (see the dashboard refresh task) and commit + push with the retry loop."

## 7. Testing and the gate (rule 4)

**Step 0, before any refactor.**
- Freeze small fixtures under `tests/fixtures/`: a stock panel, and BTC/ETH daily + 1h.
- Record golden outputs on the current code:
  - (a) the stock backtest equity curve;
  - (b) a scripted stock live-cycle run (synthetic panel, N days, pinned priors, tmp STATE), comparing the final
    state files byte for byte. `journal.now_utc` is frozen and the network is stubbed as tests/test_cycle.py:19-31
    does, because `logged_at` is inside every hashed record.

**Unit tests:**
- UtcDailyCalendar (bar final per symbol, exec_ts, cooldown in bars);
- the fractional broker with fees: no negative cash, fees in realized P&L, dust removed;
- the hysteresis series: switch counts on a synthetic series, and the same regime on the same date in main, shadow, proposal and backtest;
- the revised-close substitution (both branches), and no decision without the D+1 row;
- the fill source chain and the exec_ts / override cutoff. "Missing" means no row or a null open; volume is ignored,
  because 54% of 01:00 UTC hourly bars report volume 0 but carry real prices;
- the stale-symbol freeze (a held stale coin is not sold);
- `atr_stop_mult <= 0` means no stop check;
- drawdown re-entry: the -50% step fires, and after `dd_reentry_days` risk-on decisions the book trades again, in
  both profiles;
- the cache-mtime bar-final rule (both books);
- the Coinbase guard: exits only on a breach, proceed when unreachable;
- the quiet-hours queue and the summary command;
- book isolation, merge-rule asserts, CLI `--book`;
- absolute-return grading for crypto calls;
- a report written under reports/crypto;
- one equity mark per bar.

**Look-ahead tests:**
- Targets and the regime state at t are identical when all data after t is removed. The only exception is the D+1 open used as close_D.
- Run for both calendars.

**Sweep.** It is written down here, before it runs.
- **Window:** `--start 2018-01-01` to the last final bar. The two halves split at 2022-01-01. ETH signals need 365 bars, so ETH contributes from late 2018.
- **Profiles:** `crypto_base` and `crypto` (section 5). The sweep code treats crypto_base as its base.
- **Phases:** 7 paired rebalance phases (7-day cycle).
- **Runs:**
  - base vs candidate at 50 bp and at 100 bp;
  - each half separately;
  - leave-one-out ablations: no ETH, no ATR stop, no -25% halving step;
  - a BTC+XRP hindsight control;
  - one missed-night robustness run, with execution at t+1.
- **Order:** ablations first, then the pass rule on the final candidate.
  - Ablations: any component (ETH, ATR stop, -25% halving step) whose removal does not lower the median Sharpe is
    dropped from the candidate. The catastrophe step is never ablated.
- **Pass rule.** The final candidate ships only if **all** of these hold. Otherwise crypto_base ships.
  1. It beats the base on Sharpe (excess over cash) in at least 6 of 7 paired phases.
  2. One significance test: block-bootstrap P(Sharpe_candidate - Sharpe_base > 0) >= 0.95, on the phase-averaged
     daily returns, with 30-day blocks, 2,000 resamples and seed 0 (as in replays/power.py). A single test is
     needed because the phases correlate 0.95-0.995.
  3. Its median maxDD is no more than 2 points worse.
  4. The median paired Sharpe difference is > 0 at 100 bp per side, and > 0 in each half.
- **DSR**
  - The shipped profile's DSR is computed with N = the seeded trials plus this sweep's rows.
  - `state/crypto/trials.jsonl` is seeded with every look already taken, N = 145:
    - risk lens a4_regime: 8 variants x 3 coins x 4 windows = 96;
    - spec review 1 (power.py): 2 profiles x 7 phases = 14;
    - spec review 2 (ablate.py, ablate2.py): 35.
    The list goes in `research/2026-11-09-crypto-dsr-seed.md`, with Sharpes where known.
  - For paper trading DSR is reported, as it is for the stock book (DSR 0.57 today). A DSR below 0.95 means the report says "no proven edge". DSR is a requirement only for any real-money discussion.
- **Final check:** the quant-critic returns PASS or HOLD, and only PASS goes to paper.

## 8. Dashboard
- The snapshot builder runs both books in one process (`use_book`). Crypto rows: `ckpi`, `cpos`, `corder`, `ctrade`, `ceq`, `cregime`.
- index.html gets a crypto section:
  - equity vs the no-Claude shadow vs BTC buy-and-hold;
  - holdings in fractional units;
  - the regime gauge: distance to the go-to-cash line and the current hysteresis state;
  - fees paid;
  - the next decision time.
- The 08:03 Israel task rebuilds the snapshot on weekends too.
- `lessons.md` stays one shared file in the stock-book state directory, and each lesson names its book.
  `journal.context` reads lessons from the `STATE` that `use_book` captured on entry, not from `ROOT/"state"`, so tests
  never touch the real file. A nested `use_book("crypto")` is a no-op, so the path never becomes `crypto/crypto`.

## 9. Rollout and timeline (estimates; review rounds can add time)

| Step | Duration (estimate) | Earliest |
|------|---------------------|----------|
| Spec review by Nimrod | his time | 2026-11-09 evening |
| Implementation plan (writing-plans) | ~30 min | 2026-11-09 |
| Step 0: fixtures + golden outputs | ~30 min | 2026-11-09 |
| Build: config/books + state isolation + market.py shims + broker + regime + grading + reports + data rules, each with tests | ~4-6 h of agent work | 2026-11-10 |
| Revised-close check (precondition) | 10 min | 2026-11-11 16:00 UTC |
| Sweep + ablations + quant-critic (+1 round if HOLD) | ~1-2 h | 2026-11-11 |
| Scheduled tasks + dashboard section + skill section | ~1 h | 2026-11-11 |
| **First live paper decision** | | **2026-11-12 00:12 UTC = 02:12 Israel (Wed->Thu night)** |
| First morning summary | | 2026-11-12 08:03 Israel |

## 10. Out of scope for v1
- crypto news trading (v2; needs his decision on stop rules);
- intraday stops (v2, Binance 1-hour archive);
- coins beyond BTC/ETH;
- desk and brief for crypto;
- any exchange or broker connection, Liquid, and real money.

## 11. Decisions made while planning (rev 3.2)

A code map of the real interfaces (`research/2026-11-09-crypto-codemap.json`) showed where this spec did not fit the
code as written. The resolutions are the "Planning decisions" section of
`research/plans/2026-11-09-crypto-book-v1.md`; they take precedence over this spec where the two differ. The main
ones:
- **Re-entry reference:** the candidate uses the midpoint -0.375; crypto_base uses -0.25.
- **Priors:** exact fractions 5/13, 4/13, 4/13.
- **`account`:** merges key by key, with a crypto cash yield of 0.
- **Shipping:** `books.crypto.ship_profile` picks which profile ships.
- **`market` flags:** named for every crypto-only behaviour.
- **Hysteresis:** an initial-state rule, and no-data handling.
- **Stale data:** stocks freeze a stale symbol; crypto skips the run.
- **Fills:** all-or-nothing across coins, with `expired_unfilled` records.
- **Sweep:** a dedicated `crypto_sweep` module.
- **Summary:** exit codes and ack.
- **ETH:** it can be scored from about bar 200 (2018-05), on trend and breakout alone, before tsmom exists. That is
  earlier than "late 2018".

