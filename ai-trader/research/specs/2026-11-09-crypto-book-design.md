# Crypto book v1 - design spec (2026-11-09)

Status: design approved by Nimrod in chat on 2026-11-09 (approach B, BTC + ETH, quiet nights). This written
spec is waiting for his review. Paper money only. Research behind every number:
`research/2026-11-09-crypto-research.json` (7-agent workflow wf_123167eb-028: code impact, data, evidence, repos,
risk, synthesis, adversarial critic). The key results are copied below, with their sources.

## 1. Owner decisions (chat, 2026-11-09)

| # | Question | Answer |
|---|----------|--------|
| 1 | How to trade crypto | ג: in stages. v1 is a separate trend-following quant book. Crypto news comes in v2, after about a month of data and his decision on the stop rules |
| 2 | Night alerts | א: only 08:00-23:00 Israel time; night events go into one morning summary |
| 3 | Coins | א: BTC and ETH only |
| 4 | Design (sections 1-3 in chat) | א: approved |

Assumptions he has not been asked about. Each is listed in config and can be changed:
- book size $100,000 paper (the figure in the option he picked);
- fees 0.50% per side, with a robustness run at 1.00%;
- cash yield 0%;
- BTC buy-and-hold is a research benchmark only.

The real-money gate stays CLAUDE.md rule 1 (3 months of paper results that beat SPY on a risk-adjusted basis).

## 2. Goal and success criteria

Goal: a paper crypto book that runs every night unattended. It uses the same engine, journal, shadow book,
reduce-only overrides and forward grading as the stock book, and tells Nimrod in the morning what happened.

v1 is done when all of these hold:
1. The stock book is unchanged. All existing tests pass, and a golden test shows the stock backtest's equity curve is
   identical before and after the refactor, on a frozen panel fixture.
2. A time-machine sweep on real history (BTC from 2014-09-17, ETH from 2017-11-09) has decided between the base rule
   and the candidate by the pass rule in section 7, and the quant-critic returned PASS.
3. Scheduled night runs decide, fill, journal and commit state. The morning summary arrives at 08:00 Israel time.
   The dashboard shows the crypto book.

Expectation to set with Nimrod: "calmer, not richer". In-sample, the regime filter cut BTC's max drawdown from -83%
to -67% at about the same CAGR (63.2% -> 61.1%) (risk lens `risk/out/a4_regime.txt`, 8 variants, no DSR). These
in-sample numbers are not expectations; the sweep re-measures them.

## 3. Architecture: one engine, two books

- `config.json` gains `"books": {"crypto": {...}}`, deep-merged over the base config. The stock book also gets an
  explicit `"market"` block holding today's constants, so its defaults reproduce current behaviour exactly (rule 5).
- `load_config(book="stocks")` returns the merged config. `journal.use_book("crypto")` points `journal.STATE` at
  `state/crypto/`, so portfolio, shadow, pending, overrides, predictions, grades, trials, weights and placebo files
  never mix. Each book has its own hash chains and its own DSR trial count.
- The CLI takes `--book crypto` on cycle, status, scorecard, backtest, verify, veto, shrink, context and dashboard.
  The default is `stocks`.
- New `aitrader/market.py` with two calendars behind one interface:
  - `NyseCalendar`: today's `_bar_is_final` (16:05 NY), `_market_opened` (09:31), `official_opens` (the 09:30
    1-minute bar), BDay cooldown and override cutoff, moved verbatim;
  - `UtcDailyCalendar`: bars close at 00:00 UTC, 7 days a week;
  - interface: `periods_per_year`, `bar_is_final(bar, now, fetched_at)`, `exec_time(decision_bar)`,
    `fill_prices(names, exec_ts)`, `cooldown_until(fill_bar, n)`, `override_cutoff_utc(exec_ts)`, `is_open(now)`.
- `periods_per_year` (252 stocks / 365 crypto) is threaded through signals.py:13/29/44, strategy.py:148 (cov),
  metrics.py:10, backtest.py:170-171 and broker.mark. Using 252 understates crypto vol 1.2035x (BTC, measured), so
  positions would come out about 20% too big.
- `PaperBroker` gains `qty_step` (stocks 1 = today's floor; crypto 1e-6) and `fee_bps` (stocks 0). Today a 10% target
  of $100k buys 0 BTC at $74,914 (code lens probe).
- Per-book feature flags, all off for crypto and on for stocks: `vix`, `earnings_blackout`, `overlays`,
  `corporate_actions`, `news_engine`. With earnings on, a Nasdaq outage sets "*", which would block every crypto entry.
  With VIX on, every live weekend would go defensive(no-vix).
- The group/ETF lists copied in four places (strategy.py:10, news_live.py:34, dashboard.py:21, backtest.py:122) move
  to config. The 10-name minima (learn.py:21, strategy.py:120) move to config. Learning is explicitly off for crypto,
  because with 2 coins it would be silently inert.
- Regime: new `risk.regime_band_mode`.
  - `"offset"` (stocks, today's memoryless rule): risk-off only while px < SMA x 0.98.
  - `"hysteresis"` (crypto): go off below SMA x 0.98, come back on only above SMA x 1.02, using the `prev_regime`
    that backtest.py and cycle.py already track.
  - The critic measured the offset rule switching 7.7-9.7 times a year on BTC/ETH, against 3.5-4.3 for hysteresis.
    The in-sample evidence was produced with hysteresis, so crypto must run hysteresis.

## 4. Data

- Source: Yahoo chart API, the feed data.py already reads. Daily bars, UTC, weekends included, no gaps, adjclose ==
  close, no corporate actions (data lens).
- History back to 2014: fetch with `period1=0&period2=now` and assert `meta.dataGranularity == "1d"`. `range=max`
  silently returns monthly bars, and `range=10y` starts at 2016-11.
- **Revised last close.** Yahoo rewrites the latest completed close. On older bars, close == next open exactly; on
  the latest one they differed by 8.5-15.8 bp (critic re-fetch). Live, the decision for bar D uses the open of the
  D+1 row as close_D, which is what history will later store. Confirm this after 48 h of live data.
- **Partial bars from the stale cache.** A bar counts as final only if the data was fetched after the bar's end plus
  5 minutes (the cache file's mtime). Otherwise the run skips and retries next time. This latent bug also exists in the
  stock book after intraday runs and is fixed there too.
- Live sanity guard: if Yahoo's decision close differs from Coinbase's public candle (no key) by more than 1%, skip
  the decision and alert.
- Universe hindsight: BTC + ETH is chosen after the fact (XRP was #2 by market cap in 2018). The report says so.
  Value-weighted survivorship bias is small (secondary source); a v2 point-in-time universe would use the
  data.binance.vision archive.

## 5. Strategy: the crypto profile (sweep base values)

| Item | Value | Why |
|------|-------|-----|
| Universe | BTC-USD, ETH-USD | owner Q3 |
| Benchmark / regime | BTC-USD close vs SMA200, hysteresis band 2% | risk lens a4_regime |
| Risk-off | `risk_off_gross_mult` 0 (cash) | regime evidence |
| Signals | tsmom 365/30, trend 50/200, breakout 55; priors 0.35 / 0.35 / 0.30; cross-sectional signals 0 | time-series families with the best evidence (evidence lens); lookbacks translated 252->365, 21->30, not tuned |
| Vol target | 30% annual | BTC 2y vol 44.1%, ETH 68.5% (risk lens) |
| Caps | max_gross 1.0 (no leverage); BTC <= 1.0, ETH <= 0.6 of the book; max_sector_pct 1.0 | the stock value 0.30 would cap the whole book at 30% |
| Stop | 3x ATR14 trailing, judged at the daily close (about 9.9% BTC, 13.9% ETH) | a fixed -3% is touched within 3 days by 37.8% (BTC) / 51.4% (ETH) of random entries |
| Drawdown breaker | halve at -25%, flat at -50% (stock thresholds scaled by vol 30/12) | the -10/-20% stock values would leave the book flat most of the time |
| Rebalance | every 7 days; band 0.05; min trade $100; stop cooldown 14 bars | fees are about 10x stock costs |
| Costs | fee 50 bp per side, slippage 5 bp, exec delay 10 bp; robustness at 100 bp | Kraken Pro taker 80 bp, Coinbase Advanced 90 bp (secondary source), Alpaca 25 bp, Binance 10 bp; eToro publishes 1% |
| Cash yield | 0 | assumption |
| Learning | off | 2 coins < the 10-name minimum |

## 6. Live schedule (UTC; Israel winter = UTC+2)

Three scheduled tasks in the persistent trader session (session_012EDbLj2H3vpAR9xTMneEYo). Each is idempotent: a late
or missed run catches up on the next one.

1. **00:12 UTC (02:12 IL): decide.**
   - verify the crypto chains (fail closed);
   - fetch; bar D is final when fetched after 00:05;
   - set close_D = open of D+1;
   - run stops, regime and breaker, then rebalance if due;
   - write pending with exec_ts = 01:00 UTC;
   - Claude reads BTC/ETH headlines and may veto or shrink only, with a concrete reason, before 01:00 UTC;
   - commit and push.
2. **01:07 UTC (03:07 IL): fill.** Fill pending at the open of the 01:00 UTC 1-hour bar, falling back to the
   1-minute bar, then to the daily open with a logged warning. Then journal, run the shadow book, grade predictions
   whose horizon passed, commit and push. No push alerts.
3. **06:03 UTC (08:03 IL): morning summary.** One message covering fills, stops, regime, equity vs BTC and vs the
   shadow book, and any failures overnight. Notify gets quiet hours (Israel 23:00-08:00) for the crypto book: messages
   in that window go to `state/crypto/alert_queue.json` and are sent here.

Push commands use the corrected retry loop (`git push ... && break; git pull --rebase ...`). Verify is never piped.

## 7. Testing and the gate (rule 4)

Unit tests:
- UtcDailyCalendar (bar final, exec time, cooldown in bars);
- fractional broker + fee_bps;
- hysteresis band (switch counts on a synthetic series);
- revised-close rule;
- bar-final cache-mtime rule (both books);
- quiet-hours queue;
- book isolation (crypto writes never touch state/ root files);
- CLI --book plumbing.

Golden tests on frozen fixtures committed under `tests/fixtures/`:
- (a) the stock backtest's equity curve is identical before and after the refactor;
- (b) the crypto backtest on a small frozen BTC/ETH panel matches a stored result.

The `.cache` refreshes every 6 h, so no test reads it.

Time-machine sweep (paired phases: 7 rebalance phases for a 7-day cycle):
- **Base:** BTC only, SMA200 hysteresis 2%, 30% vol target, cash 0, costs as in section 5.
- **Candidate:** the full profile (BTC + ETH, tsmom/trend/breakout ensemble, ATR stop, breaker).
- **Pass rule for the candidate:**
  - beats the base on Sharpe (excess over cash) in at least 6 of 7 paired phases;
  - median maxDD no worse than the base's by more than 2 points;
  - median PSR >= 0.95;
  - the sign holds at 100 bp per side and in both halves of history.
- **Otherwise the base ships** (fewer knobs).
- **Trials:** `state/crypto/trials.jsonl` is seeded with the in-sample looks already taken (risk lens a4_regime: 8
  variants x 2 coins), so the DSR counts them.

quant-critic returns PASS / HOLD. Only PASS goes to paper.

## 8. Dashboard

The snapshot gains crypto rows (`ckpi`, `cpos`, `corder`, `ctrade`, `ceq`, `cregime`). Index.html gets a crypto
section:
- equity vs the no-Claude shadow book vs BTC buy-and-hold;
- holdings in fractional units;
- a regime gauge (distance to the go-to-cash line);
- fees paid;
- the next decision time.

## 9. Rollout and timeline (target; review rounds can add a night)

1. Spec review by Nimrod (now).
2. Implementation plan (writing-plans), then build in this order, each step with tests:
   - market.py + periods_per_year + broker;
   - book config + state isolation;
   - hysteresis + data rules;
   - backtest variants;
   - golden tests.
3. Sweep + quant-critic.
4. Schedule the three night tasks and the dashboard section. The first live decision is the first 00:12 UTC after PASS.
5. Report to Nimrod with the sweep result and the date of the first paper decision.

## 10. Out of scope for v1

Crypto news trading (v2, needs his decision on stop rules), intraday stops (v2, Binance 1-hour archive), coins beyond
BTC/ETH, any exchange or broker connection, Liquid, real money.
