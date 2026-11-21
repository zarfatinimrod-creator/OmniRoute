# Data brokers brief: AI trader (2026-11-09)

**What already exists:** the repo has a working data and broker layer, so everything below is a change to that, not a new build.
- `/home/user/OmniRoute/ai-trader/aitrader/data.py`: Yahoo v8 prices, Yahoo and Google News RSS, the SEC Form 4 Atom feed, Nasdaq earnings.
- `/home/user/OmniRoute/ai-trader/aitrader/alt.py`: OpenInsider cluster buys, and Quiver `live/congresstrading` sent with a Bearer header and dated by `ReportDate`.
- `/home/user/OmniRoute/ai-trader/aitrader/broker.py`: an internal `PaperBroker` with 5 bps slippage.
- **Urgent finding:** every request from this container to api.quiverquant.com gets `401 "Invalid token."`, even with no header at all. The environment proxy is most likely injecting a Quiver secret that Quiver rejects. `quiver_get()` returns `None` on 401/403, so **the congress overlay is silently switched off.**

## 1. Ranked recommendations

1. **Make SEC Form 4 opportunistic insider buying the main alternative-data signal. It is free.**
   - The evidence is the strongest on the list. Opportunistic insider trades earn +82 bp/month (value-weighted) and routine ones about 0 (Cohen, Malloy & Pomorski 2012, JF 67(3)). Purchases earn more than 6%/yr and sales about 0 (Jeng, Metrick & Zeckhauser 2003).
   - **Timing (corrected):** about 1/6 of that return comes in the first 5 days and about 1/3 in the first month (NBER w6913). Since Form 4 is filed within 2 business days, there is still time to act.
   - Do not hard-code extra weight for small caps. Jeng, Metrick & Zeckhauser found no small-vs-large difference, and the Lakonishok-Lee 7.8%/4.8% figures are unverified.
   - **Code change:** extend `sec_recent_form4` to parse `ownership.xml`. Keep OpenInsider only as a pre-filter. Its rows are dominated by 10% owners and funds, so filter to officers and directors.
2. **Make fills realistic before adding more data.**
   - Keep the internal PaperBroker as the system of record and make its fill model pessimistic.
   - Add Alpaca paper as a second venue and log the gap between the two fills.
   - Alpaca paper does not model dividends, fees, latency slippage, market impact or order size against NBBO, and it randomly part-fills 10% of eligible orders. It also gives paper accounts IEX-only data while matching fills against full NBBO.
   - The learning loop should score on the pessimistic ledger.
3. **Buy Quiver Hobbyist ($30/mo, billed monthly) for a low-confidence congress sleeve that can be removed.** Do this only after items 1 and 2 are working.
   - **Evidence is mostly null since the 2012 STOCK Act:**
     - Belmont et al. 2022: stocks House members bought did 26 bp worse over 6 months, and stocks they sold did 11 bp worse. So a short leg is not supported either.
     - Chen & Sacerdote (NBER w35041, 2026): legislators' portfolios did no better than the market, and their positions track analyst recommendations and retail sentiment.
   - **The only part you can copy is post-disclosure drift on Senate purchases.**
     - Lazzaretto 2024 reports about 90 bp in the month after disclosure. I could not read the primary paper.
     - A QuantConnect draft (still "pending review", in-sample) shows Sharpe 1.05 against SPY's 0.36.
   - **"Leaders +47 pp/yr" does not apply to us.** It is measured against matched peers and from trade dates, so you cannot copy it through a 45-day disclosure lag.
   - **Benchmark against SPY and the real-money NANC/GOP ETFs.**
     - Feb 2023 to Nov 2026 CAGR: NANC 18.9%, GOP 14.2%, SPY 18.0%.
     - Trailing year: NANC +6.0%, GOP +13.1%, SPY +10.9%.
     - The result is mixed and shows no edge.
4. **Build a free macro/regime layer and our own fear/greed score.** Inputs: Treasury yield CSV, CBOE VIX/VVIX/SKEW, FRED (works without a key), NY Fed SOFR, HYG vs LQD, SPY vs its 125-day average. CNN's Fear & Greed endpoint returns 418 to bots. Rebuild the index ourselves; do not scrape it.
5. **News and events, in priority order:**
   1. SEC 8-K via EDGAR full-text search
   2. Google News RSS
   3. Yahoo RSS
   4. BusinessWire (it works; the researcher's timeout was wrong) and PR Newswire
   5. Benzinga, CNBC, Nasdaq and Seeking Alpha RSS
   - Also add a free Finnhub key (insider sentiment MSPR, recommendation trends, earnings backup) and Massive's free per-ticker sentiment.
6. **Add Israel-resident handling to the journal now.**
   - Record each lot in USD and ILS using the Bank of Israel rate.
   - Report after-tax P&L.
   - Exclude publicly traded partnerships (PTPs; IRC 1446(f) withholds 10% of gross sale proceeds from a non-US seller).
   - Track the W-8BEN expiry.
   - Run the scheduler in America/New_York.
   - Keep alerts private.
7. **Liquid (liquid.trade): optional, read-only or paper only, and only after the user confirms this is what he meant.** Its "stocks" are perpetual futures with funding and liquidation risk, not shares.

## 2. Tools to adopt

| Tool | URL / install | Auth & price | How we use it |
|---|---|---|---|
| SEC EDGAR + edgartools | `pip install edgartools` (MIT, 2,844★, pushed 2026-11-08). Feed: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=include&count=100&output=atom` | Free. `User-Agent: AITrader <real email>`. Max 10 req/s; going over gets a ~10-minute block (sec.gov/privacy) | Poll every 5-10 min, then `<dir>/index.json`, then `ownership.xml`. Quarterly `form345.zip` for backtests. EFTS full-text search for 8-K |
| OpenInsider | `http://openinsider.com/latest-cluster-buys` (HTTP only; HTTPS fails) | Free, no API or terms | Pre-filter, at most one poll per 30 min; cross-check against EDGAR |
| yfinance / Yahoo v8 | `pip install 'yfinance>=1.8'` (Apache-2.0; 8 releases since April, so it breaks often) | Free, personal use only. Needs a browser UA (curl or python UA gets 429) | Primary daily OHLCV. Save 1-minute bars daily; Yahoo serves only the last 30 days |
| Alpaca paper | `pip install alpaca-py` (0.45.0, Python ≥3.10). Base `https://paper-api.alpaca.markets/v2` | Free; email plus MFA. Headers `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` (Alpaca now labels these "Legacy"). 200 req/min | Second paper venue. Bracket orders in whole shares so stops sit at the broker between sessions. Real-time data is IEX only; SIP bars older than 15 min are free |
| alpaca-mcp-server 2.4.1 | `claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server --env ALPACA_API_KEY=… --env ALPACA_SECRET_KEY=…`, plus `ALPACA_TOOLSETS=account,trading,stock-data` | MIT | Inspection only. Order tools under `permissions.ask`; deny `close_all_positions` and `cancel_all_orders` |
| Quiver REST | `https://api.quiverquant.com/beta/…`. `/docs/openapi.json` has a YAML body, so parse it as YAML | `Authorization: Bearer <key>` (`Token` also documented). Hobbyist $30/mo. Personal use, no redistribution (ToS §6) | `live/senatetrading` and `live/housetrading` (100/min group) every 15-60 min. One bulk backfill via `bulk/congresstrading?version=V2` (5/hr). Use our own thin client |
| Quiver MCP | `claude mcp add --transport http quiverquant https://mcp.quiverquant.com/ --header "Authorization: Bearer $QUIVER_API_KEY"` (URL needs the trailing slash, no `/mcp`) | Hobbyist gets 10 of 18 tools. OAuth sign-in must use the same email as the API account | Qualitative research for alert explanations only |
| Finnhub | `pip install finnhub-python` | Free key in `X-Finnhub-Token`. Hard cap 30/s; the 60/min free figure is unverified | insider-transactions, insider-sentiment, recommendation, company-news, calendar/earnings. Congress and news sentiment are Premium |
| FRED | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2` | Works without a key if the UA is not a browser UA. Free key optional; 120 req/min (primary source) | HY OAS, T10Y2Y, NFCI. One series per request (several ids return a zip). ICE series give only ~3 years without a key |
| Treasury / CBOE / NY Fed / BoI | Treasury daily par yield CSV. `cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` (follow the 307). BoI `edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/RER_USD_ILS?format=csv` | Free | Regime features; the ILS tax journal |
| Nasdaq API | `api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD` | Free but undocumented; site terms restrict automation | Next 14 days, pulled once a day; health-check it |
| Massive (formerly Polygon) | `pip install massive`; `/v2/reference/news?ticker=` | Free tier: 5 calls/min, 2 years of history | Per-ticker sentiment feature |
| api.congress.gov | `api_key=DEMO_KEY` | Free | Legislative-risk monitor for the congress sleeve |

**Skills and repos to reuse:**
- **Jakeschincariol/trader-skill** (MIT, last push 2026-10-14): `trader-broker` puts three gates in front of an order (risk check PASS, the user types yes, an Allow-once card) and keeps a ticket log. Copy that pattern into our order path.
- **HimanshuJ16/Algo-Trading-Skills `alpaca-paper-live-key-separation`** (Apache-2.0): exact-match base-URL allow-list, a `/v2/account` probe, an `ALLOW_LIVE_TRADING=true` flag, and fail-closed when the mode is unknown.
- **HKUDS/Vibe-Trading `data-routing` SKILL.md** (MIT): adapt it into our own `data-router` skill that maps each data need to primary, fallback, then cache. Strip the China and crypto sources.
- **skills-il/tax-and-finance `israeli-foreign-broker-tax-report`** (MIT, 39★): year-end Forms 1325/1322/1324. Keep it out of the trading loop and read its files before installing.
- **Age of Blood** (read locally at `/home/user/age-of-blood`):
  - Already ported, per `/home/user/OmniRoute/ai-trader/THIRD_PARTY.md`: headless-playtest became time-machine, plus the web-researcher agent, the 8-heading log, the four-layer memory and the caveman style.
  - **Still worth taking:** the web-researcher rule "retry a blocked page at most once and never look for another way in". Hard-code it into the data layer, so CNN, GDELT and Finviz are skipped rather than worked around.
  - Its `.mcp.json` (blender, recraft, agentcairn) has nothing for market data.

## 3. What to avoid

- **Quiver Trader ($75/mo) at the start.** Its insider data is repackaged Form 4, which is free from EDGAR.
- **The PyPI `quiverquant` package.** It prints every URL, ignores 429 and HTTP errors, sends a hard-coded CSRF header and calls removed endpoints.
- **Quiver data traps:**
  - Fields that leak the future: `ExcessReturn`, `PriceChange`, `SPYChange`, `excess_return`.
  - Rows carry `last_modified`, so records get revised after publication. Backtest on first-seen time.
  - Legacy routes (wallstreetbets, twitter, politicalbeta, etfholdings): undocumented, no support promise.
  - Strategy-page returns: hypothetical backtests whose metrics contradict each other, and Quiver takes a share of Quantbase fees on them.
- **Using date filters on Quiver live endpoints.** They accept none; only `bulk/` takes a single `date` parameter.
- **Blocked or dead sources:**
  - Do not work around CNN's 418.
  - Finviz: robots.txt allows about 20 preset screens only; skip it.
  - GDELT returns 429 even on the first call from this shared IP.
  - CBOE put/call CSVs stopped in 2019.
  - Stooq, iShares, Invesco and the MediaWiki API all fail from here.
- **One global User-Agent, or a Mozilla UA sent to FRED.** FRED resets the HTTP/2 stream on browser UAs.
- **Alpha Vantage as anything but an emergency fallback.** Free is 25 calls/day, the demo key serves only IBM, and errors come back inside HTTP 200.
- **Other execution venues for now:**
  - Webull, Schwab (tokens expire every 7 days), TradeStation, Tradier (15-minute delayed sandbox), Binance (HTTP 451 here) and the Hyperliquid testnet.
  - The tastytrade sandbox wipes positions every 24 hours.
  - IBKR as the first paper broker: its Web API needs a funded IBKR Pro account. The IB Gateway Docker image depends on IBC, which was archived on 2026-09-01.
- **Liquid's On-request and Automated modes, and scraping app.liquid.trade (its ToS bans it).** Paper and live share one account and the mode is switched in chat, while the server feeds in untrusted news text, so a prompt injection could reach real orders.
- **Unusual Whales ($99, $150 or $375/mo) and FMP until the journal shows an edge.** FMP's pricing could not be verified (403 from here).
- **Israeli brokers (Meitav, IBI, Psagot):** no retail API.
- **Posting Quiver-derived rows or alerts anywhere shared:** Quiver's ToS bans redistribution, and alerts to others likely count as unlicensed investment advice.

## 4. Parameters to hard-code (put them in `config.json`, per project rule 5)

**Rate limits:**
- SEC: at most 8 req/s.
- Quiver groups: 100/min, 10/min, 200/hr, 5/hr; on 429, sleep for `Retry-After`.
- Alpaca: 200/min.
- Finnhub: at most 55/min and under 30/s.
- FRED: at most 100/min.
- Google News: about 1 request per 3 s.
- Massive: 5/min.
- Nasdaq: one daily batch only (www.nasdaq.com sets Crawl-delay 30).
- Backoff when no Retry-After: 30 s, 60 s, 120 s, then a circuit breaker and the fallback source.

**User-Agent per host:**
- Yahoo: `Mozilla/5.0`
- SEC: `AITrader <real email>`
- FRED and Wikipedia: `ai-trader/1.0 <email>` (no Mozilla)

**Insider filter:**
- Transaction code `P` with acquired code `A`; officer or director only.
- Drop rows that are only a 10% owner, and drop funds and closed-end funds.
- A "routine" insider (traded in the same calendar month in each of the prior 3 years) gets dropped.
- Enter 1-5 trading days after `fileDate`; grade at 20 and 60 days, as the code already does.
- The cluster threshold is a tunable to sweep in time-machine; no evidence-based default exists.

**Congress sleeve:**
- Signal time is `ReportDate` or `Quiver_Upload_Time`, never `TransactionDate`.
- Keep `Transaction=='Purchase'`, `TickerType` in {ST, CS}, and options=false.
- Hold 25-30 days; the QuantConnect draft shows the effect fading after about 33 days.
- `Amount` is the low end of the disclosed range.
- Dedupe keys per endpoint:
  - `congresstrading`: (BioGuideID, Ticker, TransactionDate, Transaction, Range, ReportDate)
  - `senate`/`house`: (Senator|Representative, Ticker, Date, Transaction, Range) plus our own `first_seen_utc`
  - bulk V2: (Name, Ticker, Traded, Filed, Transaction)
- Benchmarks: SPY, NANC, GOP.

**Fill model:**
- Buy price = max(last, mid) + half-spread (2-5 bps for large caps, wider for small caps or extended hours) + 5 bps slippage.
- Limit orders fill only when price trades through the limit, not when it touches it.
- Apply dividends from Yahoo `events=div`.

**Data checks:**
- Flag a bar when the Yahoo close and the Tencent close differ by more than 0.5%.
- Yahoo 1-minute data: request in 8-day chunks, at most 30 days back. 5-minute: 60 days. 1-hour: 730 days.

**Tax (Israel):**
- Capital gains 25%. Surtax 3% + 2% on income above ILS 721,560 (2026).
- Real gain = max(0, P − max(A, C)); allowable loss = max(0, min(A, C) − P). C is the cost in ILS at the purchase-date rate, A is the USD cost converted at the sale-date rate, and P is the proceeds in ILS.
- US dividend withholding is 25% with a W-8BEN (treaty Art. 12(2)(a)) and 30% without. Flag any dividend withheld above 25%.
- A W-8BEN expires on 31 Dec of the 3rd calendar year after signing.
- When the BoI publishes no rate for a date, use the last published rate.

**Time:**
- Schedule in America/New_York; display in Asia/Jerusalem.
- The US session is normally 16:30-23:00 Israel time. It is 15:30-22:00 on 2026-03-08 to 03-26, 2026-10-25 to 10-31, 2027-03-14 to 03-25 and 2027-10-31 to 11-06.
- 2026 holidays: closed 26 Nov; early close 13:00 ET (20:00 Israel) on 27 Nov and 24 Dec; closed 25 Dec.

**Liquid, if used:** baseline equity-perp funding is 0.00000625 per hour, about 5.5%/yr paid by longs. Single-stock leverage caps at 10-20x; 50x applies only to a few index and FX markets.

## 5. Open questions only Nimrod can answer

1. **Quiver:** is a key saved as a network secret in this environment? Quiver currently rejects it as invalid, so it needs replacing. Will he pay $30/mo, billed monthly?
2. **SEC contact email:** `config.json` has `contact@example.com`, and the SEC requires a real contact. Which email should go there?
3. **Alpaca paper:** will he sign up (email plus MFA) and save the keys as network secrets?
4. **Free keys:** will he register Finnhub, Massive, and optionally FRED and BLS v2?
5. **Monthly data budget:** $0, $30, about $60, or $150 or more?
6. **"Liquid trade":** did he mean liquid.trade or Hyperliquid? If liquid.trade, read-only access only?
7. **Alerts:** only to him, or also family? Family is exempt under the 1995 Investment Advice Law, s.3(a)(7); anyone else is not.
8. **Shabbat quiet hours:** the Friday US session runs 16:30-23:00 Israel time. Should alerts be held then?
9. **Future live broker:** does he already have IBKR or eToro? Should we ask Alpaca support in writing whether Israel is supported for live accounts? This is unconfirmed; the `ISR_TAX_ID` field in their Broker API is weak evidence.
10. **Before any live money:** a CPA should review the half-year reporting duty (it applies only with a s.131 filing duty), whether frequent trading could be taxed as business income, and US estate-tax exposure above $60k in US assets (Israel has no US estate-tax treaty).
11. **Age of Blood:** its useful patterns are already ported. Is there anything else specific he wants from it (for example the agentcairn memory vault)? It contains nothing data- or broker-related.
