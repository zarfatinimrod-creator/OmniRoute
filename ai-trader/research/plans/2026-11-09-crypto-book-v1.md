# Crypto Book v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a separate 24/7 paper crypto book (BTC/ETH) on the existing ai-trader engine, gated by a time-machine sweep
and the quant-critic, with nightly scheduled runs and a morning summary. The stock book must not change.

**Architecture:** one engine, two books. The `books` profiles in config.json are merged over the base config, and
`journal.use_book()` switches state dirs. Every crypto-only behaviour sits behind a named `market` flag whose stock
value reproduces today's code. Golden outputs recorded before any refactor prove that.

**Tech Stack:** Python 3.13, pandas, numpy, requests, unittest (`python3 -m unittest discover -s tests`, run from
`ai-trader/`), Yahoo chart API, Coinbase public candles.

**Spec:** `ai-trader/research/specs/2026-11-09-crypto-book-design.md` (rev 3.1, approved by Nimrod 2026-11-09).
Code map used for this plan: workflow wf_2c7f7e08-8cd, saved as `research/2026-11-09-crypto-codemap.json`.

## Global Constraints
- Paper money only (CLAUDE.md rule 1). Claude's overrides only reduce risk (rule 3). No look-ahead (rule 7).
  Every number lives in config.json (rule 5). Never `git stash`.
- **Stock book byte-identical:** the golden outputs from Task 0 must match after every task. The only intended stock
  change is the bar-final rule in Task 5.
- **New keys only on the crypto path:** a key added to portfolio.json, trades.jsonl, pending.json, decisions.jsonl or
  latest.json is written only on the crypto path or when its value is non-default. Examples: `fee`, `fees_paid`,
  `fill_source`, `regime_px`, `bench_since_start`. Stock `qty_step` is the **int** 1 and keeps `math.floor`.
- Crypto profile values exactly as spec section 5, except the planning decisions below.
- Test command (from `ai-trader/`): `python3 -m unittest discover -s tests`. It must be all OK before every commit.
- Commit after each task. Push with `for i in 1 2 3 4 5; do git push -u origin ccr-120121ba-vsvwlj && break; git pull --rebase origin ccr-120121ba-vsvwlj; sleep $((2**i)); done`.

## Planning decisions (resolve the code-map mismatches; spec rev 3.2 records them)
1. **Re-entry reference:**
   - `risk.dd_reentry_ref` defaults to `(dd_halve + dd_flat)/2`. The candidate inherits -0.375, the middle of its
     halved band (-0.25 would sit exactly on the boundary).
   - crypto_base sets -0.25 explicitly.
2. **Priors are exact fractions:** tsmom 5/13, trend 4/13, breakout 4/13, stored as 0.3846/0.3077/0.3077. The sum
   assert allows a tolerance of 1e-3.
3. **`account` merges key by key:**
   - crypto: `starting_cash` 100000, `cash_yield_annual` 0.
   - The universe assert covers only the profiles `crypto` and `crypto_base`. The BTC+XRP control is an in-sweep
     override and never goes through load_config.
4. **Which profile ships:** `books.crypto.ship_profile` (`"crypto"` | `"crypto_base"`) picks the profile that
   `load_config("crypto")` returns. It is set in Task 11, from the sweep result. `use_book` accepts only
   `stocks` | `crypto`.
5. **The stock path is not abstracted:** cycle.py keeps its NYSE functions. A crypto branch, chosen by
   `market.calendar == "utc_daily"`, calls `UtcDailyCalendar`. `official_opens` stays in data.py, so the news_live
   import and its test patch keep working.
6. **Named market flags** (stock value first, then crypto):

   | Flag | Stocks | Crypto |
   |------|--------|--------|
   | `calendar` | `nyse` | `utc_daily` |
   | `periods_per_year` | 252 | 365 |
   | `history` | `10y` | `max` |
   | `vix` | true | false |
   | `earnings_blackout` | true | false |
   | `overlays` | true | false |
   | `corporate_actions` | true | false |
   | `news_engine` | true | false |
   | `fill_regime_on_no_picks` | false | true |
   | `equity_mark_per_bar` | false | true |
   | `delete_proposal_on_decision` | false | true |
   | `grading` | `excess` | `absolute` |
   | `stale_skips_run` | false | true |
   | `close_source` | `yahoo` | `next_open` |
   | `coinbase_guard_pct` | 0 | 0.01 |
   | `report_dir` | `reports` | `reports/crypto` |
   | `intraday_alert_pct` | 0.06 | 0.08 |
   | `latest_max_age_hours` | 30 | 26 |
   | `state_subdir` | `""` | `crypto` |
   | `etf_groups` | `["Index","SectorETF","Bonds","Gold"]` | `[]` |
   | `quiet_hours` | null | `{"tz":"Asia/Jerusalem","from":"23:00","to":"08:00"}` |

   New keys: `risk.lowvol_exclude_min_names` 10, `learning.ic_min_names` 10, `learning.enabled` (true / false),
   `learning.default_horizon` (20 / 30).
7. **Hysteresis series:**
   - The initial state is "on" if close >= SMA*(1-band) at the first valid SMA bar.
   - A NaN close or NaN SMA gives `risk_off(no-data)` for that date, and the carried state is unchanged.
   - Live and backtest both load `history: max` for crypto, so the state does not depend on the history start.
8. **No-picks days (crypto only):** with `fill_regime_on_no_picks`, the diag also carries `dd_state`, `drawdown`,
   `regime_px`, `regime_sma` and `regime_state`. Otherwise the -50% re-entry test fails on days with no picks.
9. **Fees:**
   - On a BUY, `realized_pnl = -fee` and `avg_cost` = the fill price, so pnl_pct keeps its meaning.
   - On a SELL, the fee is subtracted from realized_pnl.
   - `fees_paid` is kept in broker state.
   - qty for a float step: `round(floor(v/step)*step, 8)`, with a guard that cost <= cash.
10. **Stale data:**
    - **Stocks:** a stale benchmark makes `last` not final (`dec_bar = index[-2]`). A stale or absent symbol is
      frozen: no buy or sell, and a held one keeps its current weight. This goes through a new
      `build_targets(..., frozen: set | None = None)` and a new `rebalance(..., frozen=...)`. A held symbol frozen on
      `market.frozen_alert_runs` (2) consecutive decisions sends an urgent alert ("<SYM> no data for N runs - stop
      not checked"); `state/frozen_runs.json` counts the runs and is never written while nothing is frozen (final
      review item 4).
    - **Crypto:** any stale or absent universe symbol ends the run early with `{"skipped": reason}`.
11. **Coinbase guard breach:** book-wide clamp, `target = min(target, current weight)`, and non-held names are
    dropped. Regime-off and stops still sell.
12. **Fills:**
    - All-or-nothing across coins.
    - If a new decision would overwrite an unfilled pending order, the old one is first recorded as
      `{"event": "expired_unfilled"}` in decisions.jsonl, and what it had to sell (its `stopped`, plus the held names an
      exits-only order left out) is a forced exit of the new decision (`carried_stops`, an urgent alert; final review
      item 3).
    - The hourly walk from exec_ts stops after `market.fill_max_wait_hours` (24) hours, and at the first hour Yahoo
      does not answer (`data.Unreachable`); a 404/422 "no data" answer is a missing bar (final review item 6).
    - `exec_ts` = the first full hour strictly after `logged_at`, and never earlier than D+1 01:00 UTC.
    - It is formatted exactly like `journal.now_utc()`, because override cutoffs are compared as strings.
13. **Crypto grading:**
    - `grading: absolute` replaces the benchmark return with 0 (cash).
    - On the utc_daily calendar, `_entry_bar` treats every day as a session from 00:00 to 24:00 UTC.
14. **Sweep:** a new module, `aitrader/crypto_sweep.py`, with its own variant list. Signals are recomputed per profile
    on that profile's panel. `backtest.run` gains `exec_lag: int = 1` (2 = the missed-night run).
    - **Bootstrap:** power.py's loop (default_rng(0), L=30, 2,000 draws), on phase-averaged daily returns.
    - **Ablation:** a component is dropped if the paired median ΔSharpe (ablated - candidate) >= 0. If more than one
      is dropped, the combined final candidate runs once more, and that run counts toward N.
    - **DSR:** N = 145 seeded per-phase looks + this sweep's per-phase runs. The Sharpe spread uses per-period
      Sharpes: seeded annualised values are divided by sqrt(365), and benchmark rows are excluded. The result is
      written to `state/crypto/dsr.json`.
15. **Summary delivery:** `summary --book crypto --send` sends via notify (bypassing quiet hours). It prints JSON
    `{channels, urgent, text, newest}`. Exit codes:
    - 0: delivered;
    - 2: delivered, with urgent items;
    - 3: not delivered. The session then pushes the text with PushNotification and runs
      `summary --book crypto --ack <newest>`.

    A failed check (verify, the expected decision_date via `UtcDailyCalendar.last_final_bar(now)`, the age of
    latest.json) counts as urgent. `--ack` removes only items with `queued_at <= newest`. Final review: also urgent
    are an order pending more than `market.fill_urgent_after_hours` after exec_ts and a dsr.json result the config
    does not follow; the last `fill_source` is listed, queued times print in Israel time, and `summary` refuses
    `--book stocks` (exit 1).
16. **No change to desk.py.** Lessons are tagged `crypto: ...` inside the observation; untagged lines are stocks.
    `journal.context` reads lessons from `journal._BASE`.

## Review Focus
1. **A crypto run must never touch stock state** (a forgotten `use_book`, a direct `python -c`, the dashboard switching
   books). Task 1 adds a test that drives every crypto entry point in a temp dir and asserts that the stock state
   files are byte-identical.
2. **Yahoo returns a partial or empty latest bar, or a 429, at 00:12.** Expected: crypto skips, a later run retries,
   and no half-day close is ever used. Task 5 pins it with a stubbed panel whose latest bar's mtime is before
   bar_end+5min, and with an absent ETH.
3. **The hourly bar at exec_ts is missing for one coin.** Expected: nothing fills (all-or-nothing), the orders stay
   pending, and the next run fills them. If the pending is overwritten, an `expired_unfilled` record is written.
   Task 6 pins this.
4. **A daylight-saving switch or 08:03 summary on a weekend.** Expected: summary at 08:03 Israel time all year (CRON_TZ),
   and decide/fill in UTC. Task 8 pins `quiet_hours` across both DST dates (2026-10-25, 2027-03-26).
5. **The catastrophe step fires, then BTC recovers.** Expected: after `dd_reentry_days` risk-on bars the book trades
   again, in both profiles, including on no-picks days. Tasks 3 and 4 pin this.

---

### Task 0: Golden outputs on the current code (step 0)

**Files:**
- Create: `tests/fixtures/stock_panel.pkl` (synthetic, from `test_core.synthetic_panel(n_days=520, seed=0)`)
- Create: `tests/fixtures/golden_stock_backtest.json`, `tests/fixtures/golden_stock_cycle/` (the state files)
- Create: `tests/test_golden_stock.py`
- Create: `tests/golden_util.py` (a context manager that freezes `journal.now_utc` to a counter-based fake clock, and
  stubs `cycle.notify.send`, `cycle.corporate_actions`, `cycle.official_opens`, `cycle.market_status`,
  `cycle.earnings_on`, `cycle._overlays_once_per_day`, `cycle._market_opened` and `cycle._bar_is_final`, as
  test_cycle.py does)

**Interfaces:**
- Produces: `golden_util.frozen_env(tmp_state: Path, panel_upto: callable)`, a context manager; and
  `golden_util.run_scripted_cycle(days: int) -> dict[str, bytes]`, which returns the state files' bytes.

- [ ] Step 1: Write `tests/test_golden_stock.py::GoldenStock` with two tests:
  - `test_backtest_equity_matches`: `backtest.run(panel, cfg_for(panel), start=<bar 300>, weights_mode="prior")`.
    The equity list must equal the stored JSON exactly (round to 10 dp).
  - `test_scripted_cycle_state_matches`: run 6 scripted days (decide, fill, decide, ...). Every file in the tmp state
    must equal the stored bytes.
- [ ] Step 2: Generate the fixtures once with `GOLDEN_WRITE=1 python3 -m unittest tests.test_golden_stock` (the test
  writes the files when the env var is set), then run it again without the var. Expected: OK.
- [ ] Step 3: Commit `test(ai-trader): golden stock outputs recorded before the crypto refactor`.

### Task 1: Books, merged config and state isolation

**Files:**
- Modify: `config.json` (add `market` for stocks; `books.crypto`, `books.crypto_base` with the full blocks of spec
  section 5 plus the planning decisions; every crypto `risk` key listed explicitly)
- Modify: `aitrader/data.py:236` (`load_config`), `aitrader/journal.py` (`_BASE`, `BOOK`, `use_book`),
  `aitrader/__main__.py:41+` (the `--book` flag and the wrapper)
- Test: `tests/test_books.py`

**Interfaces:**
- Produces:
  - `data.load_config(book: str | None = None, profile: str | None = None) -> dict`. With no arguments it uses
    `journal.BOOK`. A crypto `profile` defaults to `books.crypto.ship_profile`.
  - `journal.use_book(book: str)`, a context manager: it captures `_BASE`, sets `STATE` and `BOOK`, and restores
    them. Entering the same book again is a no-op.
  - `journal.BOOK: str`.
- Replace-not-merge keys: `universe`, `prior_weights`, `signals`, `benchmark`. All other blocks merge key by key.

- [ ] Step 1: Tests:
  - `test_stock_config_unchanged`: `load_config()` == the old `json.load(config.json)` without `books`, plus the stock
    `market` block.
  - `test_crypto_universe_and_priors`: universe == {"BTC-USD","ETH-USD"}; priors name all 8 REGISTRY signals; the sum
    is 1 ± 1e-3.
  - `test_crypto_base_universe`: universe == {"BTC-USD"}.
  - `test_account_merge`: `cash_yield_annual` == 0.
  - `test_use_book_restores_and_nests`: inside a temp STATE, crypto → STATE == tmp/"crypto"; nested crypto is a no-op;
    on exit STATE == tmp.
  - `test_cli_book_flag`: `--book crypto status` runs inside use_book; `desk --book crypto` exits non-zero with a
    message.
  - `test_crypto_entry_points_never_touch_stock_state` (Review Focus 1).
  - `test_context_reads_lessons_from_base`: inside `use_book("crypto")`, `journal.context` sees the stock
    `lessons.md`.
- [ ] Step 2: Run them; expected FAIL.
- [ ] Step 3: Implement. The CLI wraps dispatch in `with journal.use_book(args.book)`. `verify --book crypto`
  iterates `MAIN_CHAINED`.
- [ ] Step 4: Run the suite, golden included. Expected: OK.
- [ ] Step 5: Commit.

### Task 2: Config-driven constants

**Files:**
- Modify:
  - `aitrader/strategy.py:10,100-107,118-122,142,148`
  - `aitrader/learn.py:21,39`
  - `aitrader/metrics.py:10`
  - `aitrader/backtest.py:62,122,170-171`
  - `aitrader/cycle.py:44,247-248,260-267,382`
  - `aitrader/news_live.py:34`
  - `aitrader/dashboard.py:21`
- Test: `tests/test_config_constants.py`

**Interfaces:**
- Produces:
  - `strategy.etf_groups(cfg) -> set[str]`, which replaces `ETF_SECTORS`. The name `ETF_SECTORS` is kept as the stock
    default for importers.
  - `metrics.summary(..., periods_per_year: int = 252)`.
- Readers:
  - `cfg["market"]["periods_per_year"]` in the strategy cov, metrics, backtest DSR/rf and the `mark` call sites
    (`trading_days=`);
  - `risk.max_position_pct_by_symbol` overrides per-name caps at strategy.py:142;
  - `risk.atr_stop_mult <= 0` skips the stop block (strategy.py:100-107);
  - `learning.enabled` false skips `walk_forward_weights` and `_learn`;
  - `market.intraday_alert_pct` replaces the 0.06 literal.

- [ ] Step 1: Tests:
  - `test_atr_mult_zero_means_no_stop`: a held name whose close is below its peak is not stopped when the mult is 0.
  - `test_symbol_cap_override`: ETH capped at 0.6.
  - `test_periods_per_year_scales_vol_target`: crypto cov uses 365; the stock value is unchanged.
  - `test_learning_disabled_keeps_priors`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run the suite, golden included. Expected: OK.
- [ ] Step 5: Commit.

### Task 3: Broker: fractional units, fees, re-entry reference

**Files:**
- Modify: `aitrader/broker.py:12-15,82-97,103-157,159-186`
- Modify: the broker construction sites (`cycle._brokers` cycle.py:172-179, `backtest.run`)
- Test: `tests/test_broker_crypto.py`

**Interfaces:**
- Produces:
  - `PaperBroker(cash, slippage_bps=5.0, commission_per_share=0.0, state=None, qty_step=1, fee_bps=0.0)`;
  - `rebalance(..., frozen: set | None = None)`;
  - `maybe_reset_peak(..., reentry_ref: float | None = None)`, where None means `(dd_halve + dd_flat)/2`.

- [ ] Step 1: Tests:
  - `test_int_step_keeps_ints`: stock quantities are `int` and the JSON is unchanged.
  - `test_fractional_qty_never_negative_cash`: a 10% target of $100k at $74,914.59 buys 0.133484 BTC (6 dp), and
    cash stays >= 0.
  - `test_fee_charged_to_cash_and_pnl`: a BUY sets realized_pnl == -fee; a round trip's realized P&L includes both
    fees; `fees_paid` == the sum.
  - `test_dust_removed`: a sell remainder below the step deletes the position.
  - `test_no_fee_keys_for_stocks`.
  - `test_reentry_after_catastrophe`: with dd_halve -1.0, dd_flat -0.5 and reentry_ref -0.25, the reset gives dd ==
    -0.25 > -0.5, so the book trades. With the candidate's defaults the reset lands at -0.375, inside the halved band.
  - `test_frozen_symbol_not_traded`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement (planning decisions 1 and 9).
- [ ] Step 4: Run the suite, golden included. Expected: OK.
- [ ] Step 5: Commit.

### Task 4: Regime series (offset / hysteresis) and no-picks diag

**Files:**
- Modify: `aitrader/strategy.py:55-68` (precompute_aux), `aitrader/strategy.py:135-137,152-159`
- Test: `tests/test_regime.py`

**Interfaces:**
- Produces: `aux["regime"]: pd.Series` of `"risk_on" | "risk_off" | "risk_off(no-data)"`, indexed by date. It is
  computed from `close[bench]` and its SMA by `risk.regime_band_mode`:
  - `offset` reproduces today's inline rule exactly;
  - `hysteresis` follows planning decision 7.
- `build_targets` reads `aux["regime"].loc[date]` before the no-picks return. The diag fill follows planning
  decision 8 and applies only when `fill_regime_on_no_picks` is set.

- [ ] Step 1: Tests:
  - `test_offset_series_equals_inline_rule` on the stock fixture.
  - `test_hysteresis_switch_counts`: on a synthetic series oscillating ±1.5% around its SMA, hysteresis gives 0
    switches and offset gives more than 0.
  - `test_truncation_invariance`: the regime and targets at t are equal when data after t is dropped (both
    calendars' panels).
  - `test_same_regime_in_main_shadow_proposal_backtest` on one panel.
  - `test_no_picks_day_keeps_dd_state_crypto` (Review Focus 5).
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run the suite, golden included. Expected: OK.
- [ ] Step 5: Commit.

### Task 5: Data rules: full history, bar-final by cache time, stale freeze, revised close, Coinbase guard

**Files:**
- Modify: `aitrader/data.py:52-57,98-116,128-154,253-263`, `aitrader/cycle.py:167-169,299-330`,
  `aitrader/strategy.py:71-125`
- Test: `tests/test_data_rules.py`

**Interfaces:**
- Produces:
  - `data.fetch_daily(sym, rng, max_age_hours) -> DataFrame` with `df.attrs["fetched_at"]` (an aware datetime). For
    `rng == "max"` it uses period1=0 and asserts `meta.dataGranularity == "1d"`.
  - `data.stale_symbols(panel, bar, bar_end_utc) -> set[str]`, which counts absent symbols as stale.
  - `data.apply_close_source(panel, source) -> panel`. For `next_open`: close[D] = open[D+1] for the last final bar,
    and the bar is dropped if the D+1 row is missing.
  - `data.coinbase_close(sym, day) -> float | None`.
- The stock bar_end is 16:00 NY + 5 min, even on early-close days.

- [ ] Step 1: Tests:
  - `test_max_history_asserts_daily`: a stubbed monthly meta raises.
  - `test_stale_bench_makes_last_not_final_stocks`.
  - `test_stale_symbol_frozen_stocks`: a held stale name is not sold on a rebalance day.
  - `test_crypto_skips_when_any_coin_stale_or_absent` (Review Focus 2).
  - `test_next_open_close_source_and_missing_row`.
  - `test_coinbase_breach_exits_only` and `test_coinbase_down_proceeds`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement (planning decisions 10 and 11).
- [ ] Step 4: Run the suite. Golden (a) is unchanged. Golden (b) changes only if its scripted panel has a stale bar
  (it does not: the stubs make every bar final). Expected: OK.
- [ ] Step 5: Commit.

### Task 6: UtcDailyCalendar and the crypto cycle path

**Files:**
- Create: `aitrader/market.py`
- Modify:
  - `aitrader/cycle.py:187-225` (fill), `228-296` (decide), `299-396` (run_cycle: gates, equity mark, proposal
    deletion, `report_dir`, the `bench_since_start` key);
  - `aitrader/data.py` (an hourly/minute bars helper);
  - `aitrader/report.py:22-92` (report_dir, labels, overlays gate).
- Test: `tests/test_crypto_cycle.py`

**Interfaces:**
- Produces, in `market.UtcDailyCalendar`:
  - `periods_per_year = 365`;
  - `bar_end(bar) -> datetime`;
  - `bar_is_final(bar, now, fetched_at) -> bool`;
  - `last_final_bar(now) -> date`;
  - `exec_time(decision_bar, logged_at) -> str` (planning decision 12);
  - `fill_prices(names, exec_ts) -> tuple[dict, str] | None` (1h open → 1m open → None; source label);
  - `session_window(day) -> tuple`.
- Produces `data.intraday_open(sym, ts, interval) -> float | None`. "Missing" means no row or a null open; volume is
  ignored.

- [ ] Step 1: Tests (stubbed data, frozen clock, temp state):
  - `test_decide_then_fill_at_0100_hour_open`;
  - `test_fill_falls_back_to_minute_then_waits`;
  - `test_all_or_nothing_fill` (Review Focus 3);
  - `test_expired_unfilled_record`;
  - `test_exec_ts_rules`: decision logged at 00:12 → 01:00; logged at 01:00:00 → 02:00;
  - `test_override_cutoff_is_exec_ts`;
  - `test_one_equity_mark_per_bar`;
  - `test_vix_earnings_overlays_corporate_actions_off`;
  - `test_report_under_reports_crypto`;
  - `test_proposal_deleted_on_decision_crypto_only`;
  - `test_idempotent_rerun_no_double_fill`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement.
- [ ] Step 4: Run the suite, golden included. Expected: OK.
- [ ] Step 5: Commit.

### Task 7: Grading for crypto calls

**Files:**
- Modify: `aitrader/journal.py:257-333` (`_entry_bar` and `evaluate_predictions` take `market: dict | None`),
  `aitrader/cycle.py` (pass the market), `aitrader/__main__.py:57` (default horizon from
  `learning.default_horizon`)
- Test: `tests/test_crypto_grading.py`

- [ ] Step 1: Tests:
  - `test_absolute_grading`: BTC +10%, so excess == 0.10 (no benchmark subtracted).
  - `test_utc_session_saturday_call_uses_logged_price`.
  - `test_stock_grading_unchanged` (re-runs the existing audit tests' cases).
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement (planning decision 13).
- [ ] Step 4: Run the suite. Expected: OK.
- [ ] Step 5: Commit.

### Task 8: Quiet hours, summary command, CLI plumbing

**Files:**
- Modify: `aitrader/notify.py:14-38` (`send(..., force: bool = False)`; queue to `alert_queue.json` under the active
  STATE when `market.quiet_hours` covers now), `aitrader/__main__.py` (`summary --book crypto [--send] [--ack TS]`)
- Test: `tests/test_quiet_hours.py`

- [ ] Step 1: Tests:
  - `test_crypto_queues_at_night_both_dst_dates` (Review Focus 4: 2026-10-25 and 2027-03-26, at 02:00 and 07:59
    Israel time queued, at 08:00 sent);
  - `test_stock_sends_at_2322`;
  - `test_summary_exit_codes` (0 / 2 / 3);
  - `test_ack_only_up_to_newest`;
  - `test_summary_flags_missing_decision_and_broken_chain_as_urgent`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement (planning decision 15).
- [ ] Step 4: Run the suite. Expected: OK.
- [ ] Step 5: Commit.

### Task 9: Crypto sweep

**Files:**
- Create: `aitrader/crypto_sweep.py`, `scripts/seed_crypto_trials.py` (writes the 145 seeded looks from
  `research/2026-11-09-crypto-dsr-seed.md` into `state/crypto/trials.jsonl`)
- Modify: `aitrader/backtest.py:28-93` (`exec_lag: int = 1`, `fee_bps`/`qty_step` broker, `costs.exec_delay_bps`
  added to slippage in the backtest only), `aitrader/__main__.py:113-118` (`backtest --book crypto` → crypto_sweep,
  `history: max`)
- Test: `tests/test_crypto_sweep.py`

**Interfaces:**
- Produces `crypto_sweep.run_sweep(panel_all: dict, start: str, split: str, end: str | None, phases: int = 7) -> dict`.
  The result holds `{runs, ablations, final_candidate, pass_rule: {phases_won, p_boot, dd_gap, cost100, halves},
  ship: "crypto"|"crypto_base", dsr: {profile, value, n}}`.
- Side effects: it writes `state/crypto/dsr.json`, appends trials and writes the report
  `research/<date>-crypto-sweep.md`.

- [ ] Step 1: Tests on a small synthetic 2-coin panel:
  - `test_profiles_use_own_panel_and_signals`: crypto_base never holds ETH.
  - `test_ablation_then_pass_rule_order`.
  - `test_pass_rule_rejects_when_bootstrap_below_095`.
  - `test_dsr_counts_seed_plus_runs`: N == 145 + runs.
  - `test_exec_lag_2_fills_one_bar_later`.
  - `test_hindsight_control_runs_without_universe_assert`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement (planning decision 14). The runs are exactly those in spec section 7: base vs candidate at
  50 and 100 bp, each half, 3 ablations, BTC+XRP control, missed night; 7 phases each. Window `--start 2018-01-01`,
  split 2022-01-01.
- [ ] Step 4: Run the suite. Expected: OK.
- [ ] Step 5: Commit.

### Task 10: Dashboard crypto section

**Files:**
- Modify: `aitrader/dashboard.py:81-281` (build both books via `use_book`; rows `ckpi`, `cpos`, `corder`, `ctrade`,
  `ceq`, `cregime`; the "no proven edge" flag from `state/crypto/dsr.json`), `dashboard/index.html` (the crypto
  section, using the one-writer rules and the existing `kv`/`rows` drawings)
- Test: `tests/test_dashboard_books.py`

- [ ] Step 1: Tests:
  - `test_snapshot_has_both_books_and_no_stock_state_written`;
  - `test_no_proven_edge_until_dsr_095`;
  - `test_lessons_tagged_crypto_shown_in_crypto_section`.
- [ ] Step 2: Run; expected FAIL.
- [ ] Step 3: Implement. Re-run the local harness (`scratchpad/harness/run.js`, desktop 1280 and phone 400), expecting
  0 errors and no horizontal overflow.
- [ ] Step 4: Run the suite. Expected: OK.
- [ ] Step 5: Commit, then upload the page with an `ArtifactData set` pinned to the current version of
  `files/index.html`. Re-read that file first.

### Task 11: Go live (operations, no new code)

- [ ] Step 1: On or after 2026-11-11 16:00 UTC, run the revised-close check: re-fetch BTC/ETH daily and record which
  value moved in the config note of `market.close_source`. If the open moved, set `close_source: "yahoo"`, then run
  the suite and commit.
- [ ] Step 2: `python3 scripts/seed_crypto_trials.py`, then `python3 -m aitrader backtest --book crypto`. Commit the
  report and state.
- [ ] Step 3: Send the quant-critic agent the sweep report and the diff since Task 0. Only PASS continues; on HOLD,
  fix and re-run.
- [ ] Step 4: Ship from the sweep result, `state/crypto/dsr.json` (its `profile` is the CLI's `ship`).
  - `profile` "crypto_base": set `books.crypto.ship_profile` to "crypto_base"; books.crypto is not changed (its
    `overrides` belong to a candidate that did not ship).
  - `profile` "crypto" and `config_change_needed` true: apply `overrides` to `books.crypto` first, in the same commit
    (the keys use crypto_sweep._diff's spelling):
    - `"universe": [symbols]`: set `books.crypto.universe` to exactly those symbols (sector "Crypto") and set
      `data.PROFILE_UNIVERSE["crypto"]` to the same set, so the load-time guard accepts the shipped universe. Never
      ship crypto_base as a stand-in for an ETH-less candidate: their priors and risk blocks differ. Update the tests
      that pin the two-coin candidate: `tests/test_books.py::test_crypto_universe_and_priors` (the universe) and the
      `universe.pop("ETH-USD")` case of `test_profile_guards_reject_a_bad_config` (break the universe some other
      way, e.g. add "XRP-USD").
    - `"risk.<key>": value` / `"costs.<key>": value`: set that key in `books.crypto.risk` / `books.crypto.costs`; the
      value "unset" means delete the key from books.crypto.
    - Then `python3 -m aitrader summary --book crypto` must show no "config change not applied" urgent item: it
      compares dsr.json `overrides` with the merged candidate (notify._ship_check).
  - Set `books.crypto.ship_profile` to "crypto" only after the overrides are in.
  - Run the suite. Tests built on the shipped profile (`data.load_config("crypto")`, e.g. tests/test_crypto_cycle.py
    and test_data_rules.CryptoRun) assume the two-coin candidate; where the applied change alone breaks one, pin it to
    an explicit fixture config instead of weakening its assertions, and investigate any other failure. Commit.
- [ ] Step 5: Add the "crypto night" section to `skills/trader/SKILL.md` (spec 6.3). Then create the 3 scheduled
  tasks bound to session_012EDbLj2H3vpAR9xTMneEYo with the spec 6.3 prompts:
  - `12 0 * * *` (UTC);
  - `7 1 * * *` (UTC);
  - `CRON_TZ=Asia/Jerusalem 3 8 * * *`.
- [ ] Step 6: After the first night (2026-11-12 02:12 Israel time), check the decision, the fill and the summary.
  Report to Nimrod in short Hebrew, with "paper money" and "no proven edge" if DSR < 0.95.
