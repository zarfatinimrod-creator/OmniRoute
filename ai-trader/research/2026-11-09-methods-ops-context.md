# Brief: methods, ops and market context (2026-11-09, fact-checks applied)

## 1. Top recommendations, ranked

1. **Code proposes, Claude judges, code disposes.**
   - Claude only chooses from an `allowed_actions` list that code computes. It can veto or shrink a trade, never enlarge one.
   - It gives P(event) for a yes/no event that code defines, and cites fact IDs from a facts table.
   - It never outputs prices, stops or share counts. A deterministic risk engine runs last and cannot be overridden.
   - WHY:
     - LLMs recall exact pre-cutoff prices, and masking names or dates does not stop it (arXiv 2504.14765).
     - Five published LLM trading agents lost 51–62% of their Sharpe after the model's cutoff (2510.07920).
     - On KalshiBench the best model's Brier skill score was only 0.057 (2512.16030).
   - This matches ai-hedge-fund's `risk/limits.py` ("hard caps the analysts cannot override") and the existing `trader` skill.

2. **Grade the Claude layer only going forward.**
   - Every Claude 5.5 model has a June 2026 training cutoff. That leaves only about 90 clean trading days, far too few for a Sharpe test.
   - The main evidence should be:
     - Brier and Brier-skill scores, measured against a base rate that code supplies, over many journaled predictions.
     - A parallel quant-only "shadow" book, to show whether the LLM adds or removes value.
   - The `time-machine` skill's historical replay grades only the quant layer.

3. **Promote strategies on a benchmark-relative gate run by a separate Critic step.**
   - The sector-momentum prototype "passed" a DSR of 0.975 against zero, but failed every SPY-relative test:
     - PSR against SPY's Sharpe: 0.24.
     - Excess Sharpe over SPY: −0.33.
     - t-stat: 2.17.
   - Its DSR is also inflated: it counted only 4 trials (the lookback grid) and used rf = 0.
   - Rule: register every configuration ever tried, and always grade against SPY.

4. **Ops: a dumb, reliable "body" plus a slow, smart "brain".**
   - **Body:** GitHub Actions cron in a PRIVATE repo, running deterministic Python. Each run has an idempotent run key and is watched by an external dead-man's switch.
   - **Brain:** one Claude scheduled task per day plus one weekly. It runs the veto pass and writes `decisions/` files to the `bot-state` branch. It opens PRs only for parameter changes.
   - If the brain fails to run, the body opens no new entries but still executes exits.
   - WHY: GitHub cron is best-effort and can drop runs. Claude tasks reject anything more frequent than hourly and consume subscription usage.

5. **Match live execution to the backtest's fill convention: decide at the close, fill at the next open.**
   - The 16:22 ET run computes signals after the close.
   - The 20:17 ET run submits OPG (market-on-open) orders. Alpaca rejects OPG orders submitted between 9:28 and 19:00 ET, so 20:17 is accepted. This tolerates hours of cron delay.
   - The 09:52 run confirms fills and attaches separate GTC stops. Alpaca brackets and trailing stops accept only `day` or `gtc`, so they cannot ride on OPG or CLS orders, and trailing stops do not trigger outside regular hours.
   - Use same-day CLS (market-on-close) orders only if the backtest also fills at the close.

6. **Start defensive.**
   - VIX is 25.6.
   - The Nasdaq is −10.9% from its high, a correction, and below its 200-day average.
   - The S&P 500 is barely above its 200-day (7,377 vs 7,325).
   - Fed funds futures price about an 80% chance of a hike on Dec 9; the figure is noisy.
   - Use half the normal risk per trade, and block new entries around NVDA earnings (Nov 17) and the FOMC (Dec 9).

7. **Data path.**
   - **v1:** SPY plus the 9 sector SPDRs. Free and free of survivorship bias.
   - **v2:** S&P 500 stocks, using fja05680 point-in-time membership patched from Wikipedia, plus a delisted-price source (trial first).

## 2. Tools, libraries, APIs and skills to adopt

| Item | Install / URL | Auth & cost | How we use it |
|---|---|---|---|
| Own numpy engine + stdlib `statistics.NormalDist` | — | free | Per bar i: fill queued orders at the open O[i], mark to the close C[i], call `strategy(i, C[:i+1].copy(), past_only_calendar)`, queue the result for O[i+1]. The numpy version runs in about 5 s; the pandas per-day loop timed out after 120 s. quantstats 0.0.86 (Apache-2.0) is optional, for tear sheets only. |
| exchange_calendars 4.13.2 (Apache-2.0, 686★) | `pip install exchange_calendars==4.13.2` | free | `get_calendar('XNYS', start='2025-01-01', end='2028-12-31')`. The default calendar ends one year from today. Cross-check with pandas_market_calendars 5.6.0 (MIT). |
| skfolio 1.12.8 (BSD-3) | `pip install skfolio` | free | `CombinatorialPurgedCV(n_folds=10, n_test_folds=2, purged_size=h, embargo_size=max(h,int(.01*T)))` for ML signal models. |
| fja05680/sp500 (MIT) + the Wikipedia article "Historical components of the S&P 500" | raw.githubusercontent.com/fja05680/sp500 ; en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500 | free | Point-in-time universe. fja05680 stops at 2026-08-18 and still lists WBD, CTVA and KVUE. Patch it from the Wikipedia page, which has changes through 2026-10-30. Start in 2001. Its "706 removed tickers" includes renames (FB→META etc.). |
| Delisted prices | Tiingo `supported_tickers.zip` (date-ranged rows; pricing unverified) ; EODHD `/api/exchange-symbol-list/US?delisted=1` | EODHD $19.99/mo, 100k calls/day. Norgate $630/yr, needs a Windows PC to export; Linux processing is allowed for personal use. | Test coverage against the point-in-time list. Resolve recycled tickers by ISIN or date range. |
| Yahoo chart API | `query1.finance.yahoo.com/v8/finance/chart/{SYM}?range=2y&interval=1d` | no key, no SLA | ETFs, ^VIX, ^TNX (now quoted in %), ^IRX (the risk-free rate), ZQX26/ZQZ26/ZQF27.CBT. Never use it for delisted names. Reject any series whose first bar is later than the ticker's membership start. |
| Alpaca paper | `paper-api.alpaca.markets`, headers `APCA-API-KEY-ID` / `APCA-API-SECRET-KEY` | free; IEX data, 200 calls/min | Primary bars and execution. Journal the official close next to each fill: paper fills are simulated and model no market impact. |
| Nasdaq earnings API | `api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD`, browser User-Agent, `Accept: application/json` | free, unofficial | Earnings blackout. Treat `time-not-supplied` rows as unconfirmed and re-pull them weekly. |
| BLS / BEA / SEC XBRL | bls.gov/schedule/news_release/bls.ics ; bea.gov/news/schedule ; data.sec.gov companyconcept with `User-Agent: name email` | free | Macro calendar. Key each fundamental to the **earliest `filed` date for that period**, usable from the next session. |
| GitHub Actions, private repo | per-cron `timezone: America/New_York`; `concurrency: bot-state` | $12/mo included on GitHub Free; this design uses about $0.5–1/mo | The body. Without a payment method, runs stop silently once the $12 is used up. |
| Claude scheduled task | code.claude.com/docs/en/routines; `CRON_TZ=America/New_York 7 17 * * 1-5` | subscription usage | The brain: veto pass, grading, Hebrew lessons, parameter PRs. Can be triggered on demand via `/fire` (`anthropic-beta: experimental-cc-routine-2026-04-01`). |
| Telegram Bot API | `POST api.telegram.org/bot<token>/sendMessage` with `requests` | free; at most 1 msg/s per chat, 4,096 chars | Primary alert channel. The token travels in the URL, so keep it, and the Alpaca keys, in GitHub Actions secrets. |
| healthchecks.io; ntfy.sh (with token); Pushover ($4.99 one-time) | hc-ping.com/<uuid>/start, /<exit> | free tiers | One dead-man check per slot, 45-minute grace. ntfy as the backup channel. Pushover priority=2 only for kill-switch events. |
| cron-job.org → `workflow_dispatch` | `POST /repos/{o}/{r}/actions/workflows/{f}/dispatches` | free; fine-grained PAT with Actions:write on one repo | Make it the primary trigger only if same-day CLS is used. The dead-man alert would fire after the 15:50 cutoff, too late to rescue the order. |
| Claude API (only if a key is used) | `client.messages.parse(output_format=Model)` | Opus 5.5 $4/$20 per MTok; Sonnet 5.5 $2/$10; Haiku 5.5 $0.10/$0.50; Batch API 50% off; minimum cacheable prefix **512** tokens | Opus at a fixed effort for the PM call. Sonnet for the critic and votes. Haiku for news digestion; it has no server-side refusal fallback. |
| Skills to adapt into `trader` / `trading-desk` | anthropics/financial-services (Apache-2.0, 41k★): equity-research skills thesis-tracker, catalyst-calendar, morning-note, earnings-preview/analysis, idea-generation. yennanliu/InvestSkill (MIT): trade-postmortem (4 quadrants, hindsight firewall, Process Score, one lesson per trade), result-validator, bear-case, fact-check, "Data & Sources" header. ai-hedge-fund (MIT, 64.6k★): RiskLimits (9 fields), abstain-on-failure, PromptCache keyed by snapshot hash, analyst scorecard, hash-chained ledger. TradingAgents (Apache-2.0, 121k★): `_coerce_optional_float`, reflection prompt, `memory/settlement.py`, point-in-time lesson filter (#1251). | free | Copy the patterns rather than depending on the repos: ai-hedge-fund releases weekly and says it is not for real trading. Skip `portfolio-monitoring` (a private-equity KPI skill) and the LSEG partner-built skills. |
| age-of-blood (`/home/user/age-of-blood`, a Unity game repo with no finance skills) | AGENTS.md, CLAUDE.md, .claude/agents/web-researcher.md, ponytail.md, caveman.md, logs/ | own | **Gates and testing:** the Critic holds the ship gate; seeded determinism (same seed must give the same NAV hash); GateCanary; gitleaks; stdlib first. **Communication:** the 8-heading Hebrew task log becomes the daily post-mortem; one question per message with options א/ב/ג plus a recommendation; terse "caveman" Hebrew for routine alerts, full sentences for irreversible actions; explicit "yes" before real money; web-researcher's rule that every number carries its URL. **Ops watchdog:** teamwatch (act after 2 misses, at most 4 restarts per hour, then a 30-minute back-off) and the pause file become `state/PAUSE`. **Failures already seen there:** a duplicate cron, so list existing tasks before creating one; hand-typed times drifted, so use machine UTC timestamps only; a workflow push was refused for lacking the `workflow` scope, so test that on day 1. The agentcairn `.mcp.json` uses Windows paths and is not portable. |

## 3. Things to avoid

- **Untrustworthy evidence:**
  - Grading Claude on history before July 2026.
  - Citing TradingAgents, FinCon or Alpha Arena returns. TradingAgents tested 3 stocks over about 60 days. FinCon's test window falls inside its model's training data. The Alpha Arena figures are unverified.
- **Multi-round bull/bear debate.** "Debate or Vote" (NeurIPS 2025) found majority voting explains most of the gains, and TradingAgents spends 11 LLM calls per prediction. Trim `trading-desk` to 1 PM call, 1 critic and a 2-of-3 vote.
- **Claude API traps:**
  - `temperature`/`top_p` return a 400 error on API version 2026-10-21.
  - A schema field named "reasoning" can trigger a refusal that is still billed.
  - `min`/`max` in a raw schema return a 400.
  - API citations cannot be combined with structured output.
  - Changing effort or schema between calls breaks the prompt cache.
- **Data traps:**
  - Yahoo for removed tickers.
  - Today's constituent list.
  - `auto_adjust=True` prices for price-level filters such as "price > $5".
  - Handing strategies a view of the arrays: `C[:i+1].base` exposes the future. The current scramble test is close to tautological and must be fixed.
- **Ops traps:**
  - Hourly Claude sessions as the polling loop.
  - Claude Desktop local tasks.
  - Gist (secret gists are not private).
  - Supabase (free projects pause after a week of inactivity).
  - Gmail drafts (they never notify).
  - SQLite files committed to git.
  - A public repo.
- **IBKR for now.** IBC was retired on 2026-09-01 and its repo is archived. No VPS until IBKR, streaming data or sub-minute reactions are needed.
- **Libraries to skip:** backtrader (last release 2023), mlfinlab (commercial), timeseriescv (2018), backtesting.py (AGPL).
- **Signals not to trade on:**
  - The Anthropic IPO rumor (unverified).
  - Post-midterm seasonality (about 20 data points).
  - Closing volume on Dec 11 (Russell reconstitution), Dec 18 (triple witching) and half days.
  - A fixed VIX > 20 rule on its own: VIX went from 16.6 to 28.2 in one day. Use percentiles.
- **Stale alerts:** never send a BUY alert more than 20 minutes after its slot.

## 4. Parameters, formulas and defaults to hard-code

```
# Stats: daily (per-period) SR; raw kurtosis = pandas .kurt()+3; γ = 0.5772156649
PSR(SR*) = Φ[(SR−SR*)·√(T−1) / √(1 − g3·SR + (g4−1)/4·SR²)]
SR0 = √V[SR_n]·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e))];   DSR = PSR(SR0)
MinTRL = 1 + [1 − g3·SR + (g4−1)/4·SR²]·(Z_α/(SR−SR*))²     # annual SR 1.0 → 684 days
MinBTL budget: ≤45 configurations per strategy family per 5 years of daily data
t = mean/std·√n on excess returns;   hit-rate z = (hit−0.5)/√(0.25/n);   Sharpe uses rf = ^IRX
GATE: DSR≥0.95 over ALL registered trials; PSR(SR*=SR_SPY)≥0.95 or t_excess≥3 (2 only if one
      pre-registered hypothesis); Sharpe>0 at 2× costs; scramble + determinism tests pass; maxDD ≤ user limit
WALK-FORWARD: train 5y / test 12m (or 3m) / step = test; embargo ≥ max(h, feature lookback, 0.01·T)
COSTS: 5 bps/side large caps & ETFs; 15–25 bps small caps or sub-$5; SEC $20.60 per $1M of sales;
       FINRA TAF $0.000166/share, cap $8.30 (official page); + Alpaca CAT fee; fill at next open
RISK (clamps only shrink): risk/trade 0.75% (0.375% while defensive); position ≤10%; ≤8 positions;
       sector ≤30%; ≤3 entries/day; no entries from 2 sessions before earnings to 1 session after;
       ADV ≥$20M, order ≤1% ADV; day −2% → no entries; DD −8% → halve sizes;
       DD −15% → go flat + human restart; day PnL in worst 5% of trailing 250 days → defensive next day
LLM: p∈[0.02,0.98]; p_adj = base + 0.5·(p−base) until n≥50, then isotonic fit; trade only if edge≥0.05;
       2-of-3 vote, median p, size down if p spread >0.15; thesis ≤60 words, placed before 'action';
       ≥1 evidence_against; every number must match its fact within 0.5%; R:R ≥1.5; stop 0.5–4 ATR;
       validator failures >20%/day → P1 alert; $3/day cost cap → quant-only;
       log usage per call (thinking tokens are billed as output; the $1/day estimate could really be about $3)
REAL MONEY only if: ≥3 months forward paper, ≥100 settled predictions, Brier skill >0,
       LLM ≥ shadow quant book, and the user's explicit yes
SLOTS (ET): 09:52 confirm fills + GTC stops + gap check | 15:32 optional exits via CLS (cutoff 15:50) |
       16:22 final bars, signals, scoring, Hebrew digest | 17:07 brain | 20:17 submit OPG orders
       Half days (Nov 27, Dec 24, close 13:00): shift all slots −3h; no CLS until the cutoff is confirmed
ISRAEL: 7h gap now (session 16:30–23:00 IL; 8:30 ET data = 15:30 IL); 6h gap 2027-03-14..03-26 and 2027-10-31..11-07
FED ODDS: r_post = (31·(100−P_Dec) − 9·(100−P_Nov))/22; 1bp of price ≈ 5.6 points of probability → noisy feature only
```

**Event calendar.**

| Date | Event |
|---|---|
| Nov 10 | CPI (Oct) |
| Nov 11 | Bond market closed: ^TNX will be stale |
| Nov 13 | PPI; Russell preliminary lists |
| Nov 17 | NVDA after the close (~23:20 IL; the CEO probe is a headline risk); HD and DIS before the open |
| Nov 18 | Expected Oct FOMC minutes |
| Nov 19 | WMT |
| Nov 25 | PCE and Q3 GDP |
| Nov 26 | Market closed |
| Nov 27 | Half day |
| Dec 4 | Jobs report (Nov) |
| Dec 9 | FOMC decision with projections, 21:00 IL |
| Dec 10 | CPI (Nov); AVGO and COST (estimated dates) |
| Dec 11 | Russell reconstitution |
| Dec 16 | MU (provisional) |
| Dec 18 | Triple witching |
| Dec 23 | PCE (Nov) |
| Dec 24 | Half day |
| Dec 25 | Market closed |

**Context.**
- September CPI was 3.7% (core 2.6%) and September PCE 3.6%.
- The Fed funds rate is 3.75–4.00% under Chair Warsh.
- Democrats are *projected* to win both houses. Their policies take effect in January 2027, so only headline risk falls inside this window.
- Not verified: current tariffs, any government funding or shutdown deadline, hyperscaler capex plans.

## 5. Open questions only the user can answer

1. Is Telegram OK as the alert channel? You would create the bot with @BotFather and send it /start. Should alerts come only during 16:30–23:00 Israel time, except emergencies?
2. What maximum drawdown would you tolerate, and how much paper capital should the bot use?
3. Long-only, or are inverse ETFs and shorts allowed?
4. Should the LLM run on your Claude subscription only (which plan, and does it have room for about 26 brain runs a month?), or also on an Anthropic API key with a $3/day cap?
5. For eventual real money, Alpaca or IBKR? IBKR would need an always-on machine and a weekly 2FA tap.
6. Is an ETF-only v1 acceptable? Later: EODHD ($19.99/mo), a Tiingo trial, or Norgate ($630/yr, needs a Windows PC)?
7. Private GitHub repo: should the session be allowed to push `.github/workflows` (needs the `workflow` scope), or will you paste the workflow file in the GitHub web UI?
8. Is "beats SPY over the horizon" (`excess_return_vs_spy_positive`) OK as the default prediction event?
9. Universe: S&P 500 only, or small caps too? Small caps mean higher costs and more recycled-ticker risk.
