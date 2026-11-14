# Crypto book - DSR trial seed (looks taken before the sweep)

Every look below was taken on BTC / ETH / SOL history before the crypto sweep. They are seeded into
`state/crypto/trials.jsonl` so the sweep's Deflated Sharpe counts them (N = 145). Files are in
`research/2026-11-09-crypto-replays/`.

| Source | Looks | What | File |
|--------|------:|------|------|
| Risk lens, regime filter | 96 | 8 variants (no filter; SMA200; SMA200 band 2%; SMA100; BTC vs own-coin regime; vol target 40%; combinations) x 3 coins (BTC, ETH, SOL) x 4 windows (full, 2018+, 2020+, 2022+) | a4_regime.txt, band_check.txt |
| Spec review 1 | 14 | base and candidate x 7 phases, 2018+ | power.py |
| Spec review 2 | 35 | base, candidate, candidate without breaker, candidate without stop, base + breaker x 7 phases, 2018+ | ablate.py, ablate2.py |
| **Total** | **145** | | |

Sharpes, where the files report them, are entered with each seeded trial. A look without a Sharpe counts toward N
only. The cross-trial Sharpe spread uses the rows that have one.
