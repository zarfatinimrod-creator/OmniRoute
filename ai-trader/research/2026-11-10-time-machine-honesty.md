# Time machine honesty: ranges, paired probabilities, run record (2026-11-10)

What changed in the code (commit 75d58d97, branch tm-wave): every sweep row now carries a 95% block-bootstrap range
and two paired probabilities, every registered sweep leaves a run record, and the Deflated Sharpe is printed in
both readings (the fill-drift command at the end came in the commit after it). Nothing that existed before moves: the first 12 columns, the `trials.jsonl` line and the golden
stock outputs are pinned by `tests/test_time_machine_honesty.py` and `tests/test_golden_stock.py`.

**The run below.** One sweep, run once to see the new output: the code path of
`python3 -m aitrader backtest --start 2018-01-01 --sweep`, 2026-11-10 18:37-18:45 UTC, 485 s wall on 4 cores.
Prices: the cached panel, 2016-11-07 to 2026-11-06, 2,514 days x 93 symbols (closes sha256 `330ebc3e8302...`);
config sha256 `f89a4f5df3b7...`; code commit `75d58d97`, no uncommitted code changes. It ran in an isolated clone
against a scratch copy of `state/`, so **it is not registered in `state/trials.jsonl`** and its record (run
`2026-11-10-f99a6a8d0bee`) is not in the repository. It repeats the 12 configurations of the registered v4 sweep
(`research/2026-11-09-time-machine-sweep-v4-paired.txt`); no new configuration was tried. Every number below is
from this run unless a file is named. None of it is evidence of an edge.

## Before: what the sweep printed, and still prints in the same columns

```
                                 variant  phases  sharpe_med  sharpe_min  sharpe_max wins_vs_base  d_sharpe_med  cagr_med  maxdd_med  calmar_med  turnover_med  psr_med
                                    base     5.0       0.399       0.283       0.504            -         0.000    0.0720    -0.1152       0.611         14.72    0.880
             prior weights (no learning)     5.0       0.399       0.283       0.504          0/5         0.000    0.0720    -0.1152       0.611         14.72    0.880
                             costs 15bps     5.0       0.187       0.053       0.377          0/5        -0.187    0.0492    -0.1226       0.400         14.86    0.710
                             costs 30bps     5.0      -0.236      -0.470       0.052          0/5        -0.635    0.0085    -0.1313       0.066         14.05    0.240
                         daily rebalance     1.0       0.418       0.418       0.418          0/1        -0.077    0.0755    -0.1234       0.612         18.59    0.890
                       monthly rebalance     5.0       0.401       0.304       0.477          2/5        -0.018    0.0687    -0.1047       0.674         11.31    0.881
                          target vol 10%     5.0       0.388       0.237       0.480          0/5        -0.015    0.0671    -0.1054       0.637         12.70    0.873
                          target vol 16%     5.0       0.339       0.125       0.436          0/5        -0.106    0.0684    -0.1320       0.533         16.83    0.842
                        no regime filter     5.0       0.226       0.141       0.327          0/5        -0.207    0.0526    -0.1315       0.393         14.89    0.748
                   no VIX defensive mode     5.0       0.389       0.101       0.427          0/5        -0.077    0.0733    -0.1208       0.606         15.52    0.874
                         8 positions max     5.0       0.432       0.199       0.534          2/5        -0.037    0.0773    -0.1109       0.707         17.73    0.899
ETF-only universe (no survivorship bias)     5.0       0.368       0.257       0.379          1/5        -0.091    0.0589    -0.0770       0.751         13.01    0.861
                            SPY buy&hold     NaN       0.594         NaN         NaN          NaN           NaN    0.1378    -0.3372       0.409           NaN    0.960
                   Equal-weight universe     NaN       0.812         NaN         NaN          NaN           NaN    0.1853    -0.3287       0.564           NaN    0.991
               DSR of base (N=74 trials)     NaN         NaN         NaN         NaN          NaN           NaN       NaN        NaN         NaN           NaN    0.547
```

Against the registered v4 table, 10 of the 15 rows are identical to the last digit. Four differ in the third
decimal of one to three cells (base median Sharpe 0.402 -> 0.399, CAGR 0.0723 -> 0.0720; costs 30bps dSharpe
-0.638 -> -0.635; monthly minimum 0.301 -> 0.304; 8 positions minimum 0.201 -> 0.199), and the DSR row moves from
0.565 (N=59) to 0.547 (N=74 = the 62 rows registered by now + 12 variants). The v4 run stored no per-phase rows, no
prices hash and no commit, so nobody can say which bar moved. That is the gap the run record closes. I did not
run the old code on the real panel (one sweep was allowed); the unit test pins the old columns on a synthetic one.

## After: the same run, with what the old output could not say

New columns at the end of the same table (`sharpe_lo/hi`, `cagr_lo/hi`, `maxdd_lo/hi`, `p_gt_bench`,
`p_gt_base`) and this block under it. Method: stationary block bootstrap of the daily returns, mean block 20
days, 2,000 resamples, seed 0, 2,224 days; every row is read on the same resampled days.

| row | Sharpe [95% range] | CAGR [95% range] | maxDD [95% range] | P(Sharpe > SPY) | P(Sharpe > base) |
|---|---|---|---|---:|---:|
| base | 0.399 [-0.181, 0.982] | 0.0720 [0.0107, 0.1355] | -0.1152 [-0.2824, -0.1023] | 0.200 | - |
| prior weights (no learning) | 0.399 [-0.181, 0.982] | 0.0720 [0.0107, 0.1355] | -0.1152 [-0.2824, -0.1023] | 0.200 | 0.500 |
| costs 15bps | 0.187 [-0.394, 0.768] | 0.0492 [-0.0094, 0.1117] | -0.1226 [-0.3190, -0.1079] | 0.043 | 0.000 |
| costs 30bps | -0.236 [-0.808, 0.360] | 0.0085 [-0.0361, 0.0647] | -0.1313 [-0.3768, -0.1159] | 0.001 | 0.000 |
| daily rebalance | 0.418 [-0.154, 1.005] | 0.0755 [0.0123, 0.1412] | -0.1234 [-0.2948, -0.1036] | 0.228 | 0.146 |
| monthly rebalance | 0.401 [-0.216, 0.941] | 0.0687 [0.0108, 0.1221] | -0.1047 [-0.2513, -0.0928] | 0.172 | 0.376 |
| target vol 10% | 0.388 [-0.193, 0.967] | 0.0671 [0.0131, 0.1230] | -0.1054 [-0.2503, -0.0903] | 0.189 | 0.228 |
| target vol 16% | 0.339 [-0.243, 0.886] | 0.0684 [0.0014, 0.1345] | -0.1320 [-0.3129, -0.1145] | 0.127 | 0.027 |
| no regime filter | 0.226 [-0.345, 0.819] | 0.0526 [-0.0068, 0.1136] | -0.1315 [-0.3298, -0.1105] | 0.047 | 0.003 |
| no VIX defensive mode | 0.389 [-0.190, 0.953] | 0.0733 [0.0073, 0.1394] | -0.1208 [-0.3138, -0.1133] | 0.168 | 0.061 |
| 8 positions max | 0.432 [-0.183, 0.977] | 0.0773 [0.0085, 0.1424] | -0.1109 [-0.2936, -0.1070] | 0.220 | 0.411 |
| ETF-only universe (no survivorship bias) | 0.368 [-0.273, 0.935] | 0.0589 [0.0136, 0.1004] | -0.0770 [-0.1998, -0.0716] | 0.142 | 0.364 |
| SPY buy&hold | 0.594 [0.011, 1.221] | 0.1378 [0.0145, 0.2595] | -0.3372 [-0.5418, -0.1697] | - | - |
| Equal-weight universe | 0.812 [0.214, 1.483] | 0.1853 [0.0583, 0.3099] | -0.3287 [-0.4946, -0.1591] | 1.000 | - |

| Deflated Sharpe reading (base, phase 0, N=74) | variants in the spread | spread (annual Sharpe) | DSR |
|---|---:|---:|---:|
| 1. every swept variant, cost-stress rows included: **the rule** | 12 | 0.1877 | 0.547 |
| 2. cost-stress rows (15bps, 30bps) left out of the spread | 10 | 0.0585 | 0.851 |

Record: `state/trial_runs/2026-11-10-f99a6a8d0bee.json.gz`, 1,215,982 bytes on disk (3,017,705 bytes of JSON
before gzip): 58 daily-return series (56 runs + 2 benchmarks) x 2,224 days, 56 per-phase rows, the 15 table rows,
the two hashes and the commit. The trials line gains seven keys and keeps `logged_at`, `start`, `rows`.

## What the new numbers say

- The base Sharpe of 0.399 has a 95% range of -0.181 to 0.982: the sign is not established. Its CAGR of 7.20%
  ranges from 1.07% to 13.55%. SPY's Sharpe of 0.594 ranges from 0.011 to 1.221.
- The chance that the base beats SPY on Sharpe on the same resampled days is 0.200. No strategy row is above 0.228.
- No variant is above the base with any weight: the best, 8 positions max, reads 0.411 (0.5 = no difference).
  "prior weights" is the same series as the base and reads 0.500, where the old table printed "0/5 wins".
- The paired reading separates rows whose ranges overlap almost fully: costs 15bps reads 0.000 against the base,
  no regime filter 0.003, target vol 16% 0.027. On this history those three were below the base in at least 97%
  of the resamples; their own ranges alone would have read "about the same".
- The Deflated Sharpe is 0.547 by the rule and 0.851 by the other reading: under 0.95 both ways. With the v4
  count (N=59) the same data gives 0.566 and 0.854 (registered: 0.565).
- The realised max drawdown of -11.52% sits at the shallow end of its range (-28.24% to -10.23%): reshuffled
  days break the path the drawdown breaker reacted to, so that range is approximate and leans deep.

## How soft the ranges themselves are (same run, base row, recomputed from the saved daily returns)

| mean block (days) | 5 | 10 | 20 | 40 | 60 |
|---|---:|---:|---:|---:|---:|
| base Sharpe range | -0.221 to 1.048 | -0.205 to 1.038 | -0.181 to 0.982 | -0.137 to 0.941 | -0.074 to 0.892 |
| P(Sharpe > SPY) | 0.222 | 0.227 | 0.200 | 0.185 | 0.184 |

Seeds 1, 2 and 3 at block 20 move the bounds by at most 0.03 and the probability between 0.199 and 0.207. The
five base phases' daily returns correlate 0.971 on average, so a win count over phases is not five tests. On
synthetic returns with a known Sharpe the range held the truth in 191 of 200 seeds (unit test).

## Limits

- 8.8 years of daily data cannot narrow these ranges; only more independent data can.
- The closes hash is "dates x symbols x closes". A revised open would change fills without changing it; the
  record also stores a hash over every price field and the VIX (`panel.inputs_sha256`).
- The default settings (block 20, 2,000 resamples, seed 0, 95%) are `metrics.BOOT_DEFAULTS`; `config.json` has no
  `bootstrap` block yet (it was outside this change), so the config hash does not show them. The record does.
- One record is about 1.2 MB. `state/` is tracked by git, so every registered sweep adds that much to the repository.
- The crypto sweep got the same ranges section and record; it was not run here (no crypto run is on record).
- `backtest --drift` (new, read-only) on the 14 fills of 2026-11-09 in `state/trades.jsonl`, run 2026-11-10 about
  18:41 UTC against Yahoo's settled daily opens: 14 of 14 priced, notional $50,171.29, total drift -$2.67
  (-0.53 bp), largest 6.5 bp (UNP: paper 292.5562, time machine 292.7463). One day of fills.
