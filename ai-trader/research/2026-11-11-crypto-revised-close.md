# Crypto revised-close check (plan Task 11 step 1, spec section 4)

Fetched 2026-11-11 16:09 UTC from the Yahoo chart API (`/v8/finance/chart/<SYM>?period1=..&period2=now&interval=1d`,
`meta.dataGranularity` = "1d").

| Bar (UTC) | BTC open | BTC close | ETH open | ETH close |
|-----------|---------:|----------:|---------:|----------:|
| 2026-11-07 | 75,746.93 | 75,747.58 | 2,235.05 | 2,236.32 |
| 2026-11-08 | 75,747.58 | 74,584.65 | 2,236.32 | 2,120.98 |
| 2026-11-09 | 74,584.65 | 75,223.15 | 2,120.98 | 2,131.50 |
| 2026-11-10 | 75,223.15 | 73,720.12 | 2,131.50 | 2,050.18 |
| 2026-11-11 (open bar) | 73,708.88 | 74,018.42 (partial) | 2,050.65 | 2,072.90 (partial) |

## Answer
On 2026-11-09 15:56 UTC the 11-08 close was 74,584.65 and the 11-09 open was 74,719.82
(`research/2026-11-09-crypto-research.json`, critic fact). Today the 11-08 close is still 74,584.65 and the 11-09
open is now 74,584.65. **The open moved; the close did not.** ETH the same: the 11-08 close stayed 2,120.98 and the
11-09 open became 2,120.98 (it was 2,124.33).

The same pattern shows on the newest pair today: the 11-10 close is 73,720.12 and the fresh 11-11 open is 73,708.88
(1.5 bp apart; ETH 2,050.18 vs 2,050.65, 2.3 bp). The open of the newest row is a provisional value that Yahoo later
overwrites with the prior close.

## Consequence (spec section 4)
"If the open moved, use Yahoo's close_D as fetched, and the look-ahead exception falls away."
`books.crypto.market.close_source` must be `"yahoo"`, not `"next_open"`. With `next_open` the live decision would use
a provisional open that history never keeps, which is the live/replay divergence the check exists to prevent.

One observation, two coins, one date pair plus the newest pair. The live audit (`market.revised_close_alert_bps`)
keeps checking every decision close against later history.
