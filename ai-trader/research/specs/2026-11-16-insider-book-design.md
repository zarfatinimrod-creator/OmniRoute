# Insider purchases book, log-only - design spec (2026-11-16, rev 2)

**Owner's decision (Nimrod, 2026-11-24 ~17:55 UTC, in chat, answer א):** all 16 recommendations of section 9 are approved as written. Still missing, owner actions only: the SEC contact address as an environment variable (`AITRADER_SEC_CONTACT`, never in a file or log) and a free Tiingo key that he opens himself (it goes in as a network secret, never in a file).

Status: a design for the owner's review. Rev 2 answers the first review round (a quant reviewer and a data reviewer,
2026-11-16); the review log at the end lists every finding and what was done with it. Nothing here is built or has
been run, and no trial is registered. It follows the owner's decision of 2026-11-16: the stock and crypto parameters
are frozen, and the improvement effort moves to finding a measured edge, starting with opportunistic insider
purchases. The sources are CLAUDE.md hard rule 1, `research/2026-11-16-real-money-review.md` fix 4, and backlog items
3, 5 and 6. Paper money only.

This spec was written before this project had computed any insider return for any period. The data reviewer measured
price coverage on three samples of events (6.2); no return was computed. Section 6 is the pre-registration. At the
seal (6.7) the whole of this file is hashed, together with the code and the cached inputs, before the first design
run. After the seal this file is not edited: any change makes a new experiment, unless it is a registered defect
(6.7). The book touches none of the frozen books' files (8.2).

## Evidence tags

- [C file:line]: code under `ai-trader/` at commit 33e3dfb6, read 2026-11-16. The cited files are unchanged since
  fec70554, where rev 1 read them.
- [K n]: item n of `state/backlog.md`.
- Research files in this repo:
  - [Rv] `research/2026-11-16-real-money-review.md`
  - [DB] `research/2026-11-09-data-brokers.md`
  - [SS] `research/2026-11-09-strategy-science.md`
  - [PF] `research/2026-11-09-partial-findings.md`
  - [RM] `research/2026-11-10-upgrade-roadmap.txt`
  - [S65] `research/specs/2026-11-11-sec-filings-feed-design.md`
  - [CB] `research/specs/2026-11-09-crypto-book-design.md`
- [P]: Cohen, Malloy & Pomorski, "Decoding Inside Information", NBER working paper 16454. The PDF came from nber.org
  and its text was extracted locally with `pdftotext` on 2026-11-16, so quotes from it are exact. The published
  version (Journal of Finance 67(3), 2012) was not read, and its tables may differ.
- [W1]-[W6]: web pages read on 2026-11-16 (list in 2.7).
  - [W2] (the data set readme) was read as extracted PDF text, so its quotes are exact.
  - The others went through a fetch tool that summarizes a page with a small model. Their exact words must be re-read
    by the plan's first task before anything is built on them.
- [D]: measured or read by the data reviewer of rev 1 on 2026-11-16, read-only. Samples were drawn with seed 0, and
  pages were read through the same fetch tool. The writer did not re-run them. The plan's first task repeats every [D]
  measurement that a decision rests on (4.4).
- [Q]: arithmetic by the quant reviewer of rev 1, re-checked by the writer.
- [M]: measured for this spec from files in this repo (command in Appendix A).
- (U): unverified, meaning not checked against its primary source. Literature that the reviewers named and nobody read
  for this spec carries (U): Dimson (1979) on the betas of thinly traded stocks; Blume and Stambaugh (1983) and Liu and
  Strong (2008) on bid-ask bounce in rebalanced portfolios; Shumway (1997) on delisting returns.
- (dv): design value. The number was chosen here with no evidence behind its exact size. This spec fixes it, and it
  is not tuned.

## 1. Hypothesis and the evidence for it

### 1.1 Hypotheses (written before any look)

**H1 (the edge).** Take every US common stock bought at the first regular-session open after the filing date of an
SEC Form 4 that reports:
- an open-market purchase (non-derivative table, code P, acquired),
- by an individual officer or director,
- who is classified as opportunistic by the Cohen-Malloy-Pomorski rule (3.2).

Hold each one for 63 trading days. Over the sealed holdout (2019-01-02 to 2026-09-30), the event portfolio E of these
stocks (equal weight at entry, buy-and-hold after, 6.4) has a positive abnormal return after costs: the intercept of
the daily regression R1 in 6.4, which carries two lags of every factor, is above 0 with a Newey-West t of at least 2.
H0: the intercept is at most 0. The same pipeline run on a negative control C (6.4) must show no such intercept.

**H2 (the money).** A paper book with a limited number of slots, built from the same events (section 5), beats SPY's
Sharpe and the CAGR of an exposure-matched SPY/T-bill mix. Each comparison needs a bootstrap probability of at least
0.8 on the same holdout.

The forward book is promoted past log-only (stage 2, 7.1) only if both hold, together with the other bars of 6.5.

### 1.2 Evidence for it, checked where possible

| Claim | Source | Status |
|---|---|---|
| Routine trader: "placed a trade in the same calendar month for at least three consecutive years". The class is set "at the beginning of each calendar year", and an insider needs "at least one trade in each of the three preceding years" to be classified at all | [P pp. 11-12] | verified (working paper) |
| Insider data 1986-2007 from the Thomson Reuters filings database; portfolios 1989-2007. Option exercises and private transactions are excluded | [P p. 10, Table IV] | verified |
| The 82 bp/month that the repo cites ([DB] item 1, [PF]) is the value-weight 5-factor alpha of opportunistic buys **minus opportunistic sells** (t = 2.15). It is a long-short number, not the purchase signal | [P p. 5, Table IV] | verified; the repo's reading corrected |
| Long-only, opportunistic buys alone, 5-factor alpha: 1.58%/month equal-weight (t = 7.03) and 0.72%/month value-weight (t = 2.27). Carhart: 1.45 EW (t = 6.82), 0.52 VW (t = 1.73). DGTW: 1.24 EW (t = 4.99), 0.57 VW (t = 2.35) | [P Table IV] | verified |
| Routine buys also earn something in equal weight: 0.87%/month (t = 5.00) EW, against 0.09 (t = 0.34) VW. Opportunistic minus routine buys: 0.70 EW (t = 3.18), 0.63 VW (t = 1.61) | [P Table IV] | verified |
| "over half of the improvement in predictive power gained by focusing on opportunistic trades comes from the superior performance of opportunistic sells relative to routine sells". For a long-only book the routine filter is a smaller lever than the 82 bp suggests | [P p. 5] | verified |
| After the trading month, returns "continue to rise for roughly six months ... and then level off" (event-time, value-weight four-leg spread about 4% at 12 months) | [P p. 5, p. 18] | verified, but it is a spread portfolio, not buys alone |
| Formation is by trade month: hold the following calendar month, then rebalance. The result is the same with an 11th-to-10th window. The median delay from trade to report was 3 days | [P pp. 17-18 fn 15, fn 7] | verified |
| CMP describe insiders as officers, directors and 10% owners. No officer/director filter is stated in the parts read. Our filter (3.1) comes from this repo's research (OpenInsider rows "dominated by 10% owners and funds" [DB] item 1), not from CMP | [P p. 10], [DB] | our choice, stated |
| Jeng, Metrick & Zeckhauser 2003: purchases earn more than 6%/yr abnormal and sales about 0. Timing: "about 1/6 of that return comes in the first 5 days and about 1/3 in the first month" (NBER w6913) [DB], but "half of it in the first month" in [PF]. The repo disagrees with itself | [DB], [PF] | U |
| Lakonishok & Lee 2001: purchases are informative and sales are not, concentrated in small firms. The 7.8% / 4.8% figures come from a secondary source | [PF] | U |

### 1.3 Evidence against, and what lowers the expectation

- **Decay.** CMP's sample ends in 2007, so our whole window (2009 onward) is after it. Returns fall 58% after
  publication (McLean-Pontiff [SS] section 4).
  - EW: 1.58 x 0.42 ≈ 0.66%/month gross.
  - VW: 0.72 x 0.42 ≈ 0.30%/month gross.
  - This is arithmetic on cited numbers: an expectation, not a measurement.
- **Costs.** CMP's returns are before costs, and the equal-weight alpha lives in small caps. At the cost table of 5.6
  (dv), one 63-day round trip costs 20-100 bp, about 0.1-0.33%/month.
- **An unverified counter-claim in this repo.** "Insider purchases in 2020-2025 had a median one-month return of
  -1.54% against the S&P 500 (47,458 events, not peer-reviewed)" [RM line 69]. Its source was never found
  [RM line 175]. It is a median per event, not an alpha. It is disclosed because it is the only look anyone in this
  project has taken at insider returns in the holdout years (6.2).
- **[SS line 63]:** insider clusters count "only as a small bonus for small and mid caps; the researcher's own test is
  unverified (U)".
- **Survivorship and price coverage.** Yahoo cannot price most historical events. On random samples of events built
  from the SEC files, Yahoo priced 44.5% (2010q3), 46.4% (2015q3) and 61.7% (2019q3) [D]. The misses are mostly
  delisted names and reused or relisted tickers. The "26% of insider-event tickers returned 404" of [SS line 72]
  understates the problem. A delisting-inclusive source is planned from the start (4.4).
- **The factor model misprices this segment.** An equal-weight small-cap event portfolio trades out of sync with
  value-weighted factors, and a daily re-weighted one picks up bid-ask bounce. Both push α up. R1 takes lagged
  factors, E uses buy-and-hold weights, and a negative control runs through the same pipeline (6.4).
- **Power (6.6).** A real effect at its decayed size can still give t < 2 over 7.75 years.
- **Prior.** My guess, not a measurement: the holdout passes every bar with a probability well under one half. The
  kill criterion (6.8) is written so that this outcome ends the work cleanly and cheaply.

## 2. Data

### 2.1 History: the SEC Insider Transactions Data Sets [W1, W2]

- **What they are:** flat files "extracted from EDGAR Ownership XML submissions" of Forms 3, 3/A, 4, 4/A, 5 and 5/A,
  "provided as-filed". They "may contain redundancies, inconsistencies, and discrepancies relative to prior
  submissions" [W2 sections 1, 3].
- **Coverage:** January 2006 to September 2026 [W1]. All 83 quarterly ZIPs, 2006q1 to 2026q3, are listed, with none
  missing [D].
- **Size** [D]: 887 MB zipped in total; 45 ZIPs are over 10 MB; one quarter unzips to about 50 MB. The disk had 23 GB
  free. The ZIPs are kept under `.cache/insider/`, which is gitignored [C .gitignore:1], and never under `state/`. The
  TSVs are read straight from the ZIPs; nothing is unpacked.
- **Cadence:** published quarterly. "Data contained in documents filed after 5:30pm EST on the last business day of
  the quarter will be included in the next quarterly posting" [W2 section 1]. How long after quarter end a file
  appears is not stated (U). These files are for history only; the forward book reads live filings (2.2).
- **Where they are:** recent quarters sit under `/files/datastandardsinnovation/data/insider-transactions-data-sets/`
  and older ones under `/files/structureddata/data/insider-transactions-data-sets/` [W1]. The loader takes each
  quarter's link from the listing page and never builds a URL itself.
- **Format:** eight tab-delimited UTF-8 files per quarter, plus a W3C tabular-data metadata file [W2 sections 3-4]:
  SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS, NONDERIV_HOLDING, DERIV_TRANS, DERIV_HOLDING, FOOTNOTES and
  OWNER_SIGNATURE. Details the readme does not state [D]:
  - The metadata file's name changed between years: `insider_transactions_metadata.json` in 2010q3,
    `FORM_345_metadata.json` in 2026q3. The loader finds it by pattern.
  - One column is spelled `FORM3_HOLDINGS_REPORTED`, against the readme's `FORM3_HOLDING_REPORTED`.
  - Dates are DD-MON-YYYY.
  - `RPTOWNER_RELATIONSHIP` holds mixed-case comma lists ("Director,Officer"), sometimes with the commas missing
    ("TenPercentOwnerOther", "DirectorOther"). 3.1 step 3 matches it by case-insensitive substring.
- **Fields used** (exact names from [W2 section 5], plus `AFF10B5ONE`):
  - SUBMISSION:
    - `ACCESSION_NUMBER` (the key)
    - `FILING_DATE` ("Filing date with the Commission", a date with no time)
    - `PERIOD_OF_REPORT`
    - `DATE_OF_ORIG_SUB` (the original filing's date, for amendments)
    - `DOCUMENT_TYPE` (3, 3/A, 4, 4/A, 5 or 5/A)
    - `ISSUERCIK`, `ISSUERNAME`, `ISSUERTRADINGSYMBOL`
    - `NOT_SUBJECT_SEC16`
    - `AFF10B5ONE` (below)
  - REPORTINGOWNER:
    - `ACCESSION_NUMBER` + `RPTOWNERCIK` (the key)
    - `RPTOWNERNAME`
    - `RPTOWNER_RELATIONSHIP`: "OFFICER, DIRECTOR, TENPERCENTOWNER, OTHER" in the readme; see the format note above
    - `RPTOWNER_TITLE`: the readme says "required if relationship is 'DIRECTOR'", which is probably a typo for
      OFFICER (U)
  - NONDERIV_TRANS:
    - `ACCESSION_NUMBER` + `NONDERIV_TRANS_SK` (the key)
    - `TRANS_DATE`, `DEEMED_EXECUTION_DATE`, `TRANS_CODE`, `EQUITY_SWAP_INVOLVED`
    - `TRANS_TIMELINESS`: E early, L late, empty on time
    - `TRANS_SHARES`, `TRANS_PRICEPERSHARE`, `TRANS_ACQUIRED_DISP_CD`, `SHRS_OWND_FOLWNG_TRANS`
    - `DIRECT_INDIRECT_OWNERSHIP`, `NATURE_OF_OWNERSHIP`
    - the `*_FN` footnote ids
  - FOOTNOTES: `ACCESSION_NUMBER`, `FOOTNOTE_ID`, `FOOTNOTE_TXT`, used by the plan and private-deal filters of 3.1.
  - Transaction code P is "Open market or private purchase of non-derivative or derivative security" [W2 6.2]. So P
    also covers private purchases (3.1 step 5).
- **The 10b5-1 flag, `AFF10B5ONE`.** The SEC page says: "In July 2025, the 2023-2025 data sets were updated to
  include the AFF10B5ONE element in the SUBMISSION file" [D]. The 2026q3 ZIP has the column in SUBMISSION.tsv, with
  the values {'0', '1', 'true', 'false', ''}, and its bundled readme defines it [D]. It is set per accession, not per
  transaction row. 41 of 2,079 qualifying purchase accessions in 2026q3 carry it [D]. Use: 3.1 step 5.
- **Not in the data set** (from the field list):
  - **No time of day.** There is no acceptance time anywhere; only `FILING_DATE`.
  - **No SIC code, no exchange, no CUSIP and no ISIN.** The issuer is known only by `ISSUERCIK` and the symbol as
    filed. Matching an event to a price series therefore needs a written rule (3.4).
  - **No link from a transaction to one owner.** Transactions are keyed by accession and owners by accession +
    owner CIK, so when a filing has several owners a transaction row cannot be tied to any one of them.
- **Terms and cost:**
  - The page says "we cannot guarantee the accuracy of the data sets" [W1].
  - SEC filings are public records; their copyright status was not checked (U).
  - Access follows the SEC's fair-access rules (2.5). Cost: $0.

### 2.2 Forward: live Form 4 filings

- **Sources**, the same family spec 65 uses [S65 2.1]:
  - (a) The daily form index of the previous business day: the complete list of Form 4 accessions. When it is
    published is unverified (U).
  - (b) The current-filings Atom feed for type 4: the address `data.sec_recent_form4` already builds; that function
    has no caller [C data.py:304-321].
    - On 2026-11-16 this address returned 424B2 entries (GS Finance, Goldman Sachs) [D]. The type filter seems to
      match by prefix, so a 100-entry page can hold no Form 4 at all.
    - So the poller keeps only entries whose title starts with "4 - " or "4/A - ", and pages back until the entries
      are older than the day it polls.
    - The daily index (a) stays the complete list. The pre-open run fetches every accession of the index that the
      polls missed (7.2).
  - (c) Per filing: the ownership XML.
- **What the XML adds:**
  - It carries the fields of 2.1.
  - It carries the 10b5-1 flag of 2.1. Its element name is taken to match the TSV column (`aff10b5One`, U). U1 checks
    the name against the schema before the parser is written, and the TSV/XML parity test covers it.
  - The current specification is "Ownership (Forms 3, 4, 5)" version 5.5 of 2026-03-18, which adds new elements
    [W4]. The parser ignores elements it does not know.
- **Acceptance time:** read from the filing index, forward only.
  - The index page shows, for example, "Accepted 2026-09-30 16:24:20", with no time zone label [D]. Spec 65 found
    that the clock of the stamp (New York or UTC) is not known [S65 4.4].
  - This book never uses the stamp for a decision (2.3), only for a latency figure. That figure is printed only
    after spec 65 calibrates the clock.
- **One row format** (`form4.py`) serves both the bulk TSV and the XML, so the history replay and the forward book
  run the same event code. A parity test checks that on fixture filings the XML path and the TSV path give the same
  events.
- **Volume** [D]: original Form 4s per quarter were 38,478 (2010q3), 37,398 (2015q3) and 33,521 (2026q3), about
  530-610 per business day. At one request per filing and at most 1 request a second (2.5), a day's XMLs take about
  9-10 minutes.

### 2.3 Point-in-time availability: the one rule

- Availability is never decided by the transaction date.
- **The law** [W3, confirmed by D]:
  - Forms 3, 4 and 5 "submitted by direct transmission commencing on or before 10 p.m. Eastern ... shall be deemed
    filed on the same business day" (17 CFR 232.13(a)(4)).
  - Most other forms have a 5:30 p.m. cutoff ((a)(2)).
  - So a Form 4 with `FILING_DATE` d was accepted by about 22:00 ET on d. A transmission that starts just before
    22:00 may finish just after it, and the next open is later still.
- **Rule:**
  - Availability is 22:00 ET on `FILING_DATE`.
  - The entry session is the first NYSE regular session that opens after that moment, which means the first NYSE
    session after the filing date.
  - The rule is the same in history and forward. So the holdout tests exactly the rule the forward book runs.
- **What the rule costs:**
  - A filing accepted between EDGAR's opening time and 09:30 ET on d could have traded at d's open. The rule waits a
    day instead.
  - The forward book logs how often this happens and the price gap, as a measurement only. Nothing trades on it.
- **Forward guard:** when the bot first sees a filing after its entry session has opened (the feed was late or down),
  entry moves to the next session after `first_seen`, and the row is tagged `late_feed`. These rows are counted. The
  guard can only make the forward book worse than the replay, never better.
- **Known gap:** 17 CFR 232.13(b) lets the SEC adjust a filing date (how often is U). A back-dated filing date would
  make history slightly optimistic; the forward guard catches the same case live.
- **Class:** for year Y, the class (3.2) uses only rows with `FILING_DATE` on or before Y−1-12-31.
- **Filters:** liquidity and price filters use bars up to the close before the entry session, at as-traded levels
  (3.4).
- **Sessions:** the history takes NYSE sessions from SPY's daily bars. `config.json` `calendar` lists only 2026 and
  2027, and its note says years not listed count as closed [C config.json calendar].

### 2.4 Known gaps and how each is handled

| Gap | Handling |
|---|---|
| Amendments (4/A) restate earlier filings "as filed" | Events come only from original Forms 4 (3.1 step 1). 4/A rows are counted in the rejects. What the market saw at the original filing date is what the replay uses |
| Late filers | Allowed, dated by the filing date: the information arrives when filed. Report lag over 30 days is dropped as a data-sanity rule (3.1 step 6). `TRANS_TIMELINESS` is self-reported, so the lag is computed from the dates |
| Derivative vs non-derivative tables | Only NONDERIV_TRANS makes events. DERIV_TRANS is ignored (option and warrant purchases are not stock purchases) |
| Several owners on one accession | Transactions cannot be tied to one owner, so the accession is used only if every owner passes (3.1 step 3), and it counts as one owner (3.3) |
| The same purchase reported by two owners | Merged before counting (3.3) |
| Code P includes private purchases | A footnote filter (3.1 step 5) plus the price sanity check (3.4) |
| The symbol is self-reported and often dirty | The mapping rule (3.4). A blank or NONE symbol drops as `not_listed` (3.1 step 8). A failed match makes the event unpriced (4.3), never dropped |
| Tickers reused at the price source | The date range of the series and the price sanity check (3.4) |
| Form 5 (annual report; late or exempt transactions) | Not used for events |
| Foreign private issuers are exempt from Section 16 (Rule 3a12-3(b), U) | ADR events should be rare; when one appears, the price check decides |
| `DEEMED_EXECUTION_DATE` (plan trades whose date the insider did not choose) | Not used for availability. It is a plan sign, and the plan filter (3.1 step 5) covers it |
| `NOT_SUBJECT_SEC16` = 1 | Dropped |
| Filing date adjusted by the SEC | Rare (U). Forward guard (2.3) |

### 2.5 Access rules (fair access, shared with spec 65)

- **The contact address comes first.**
  - Nothing calls the SEC until `AITRADER_SEC_CONTACT` exists (owner's decision [K 65]).
  - On 2026-11-16 the variable did not exist in this session (a presence test only).
  - For this spec I made one request to `www.sec.gov` with a descriptive User-Agent and no contact address. It was
    refused with 403 "Request Rate Threshold Exceeded" and was not retried. The data reviewer saw the same 403 later
    that day [D].
  - The reviewers read the SEC pages through a fetch tool. The build cannot use that route.
  - So the contact address (U0) is the hard first step for the history study too, not only for the live feed.
- **One client.**
  - Every SEC request goes through `aitrader/sec.py`: one User-Agent builder, a host allowlist, no redirects and one
    pacer [S65 2.3-2.4].
  - If spec 65's client is not built when this build starts, this build builds exactly that part of spec 65 and
    nothing of its feed.
- **Rate.**
  - The insider code makes at most 1 request a second (dv), one at a time.
  - Together with spec 65's feed (1.23 a second [S65 2.4]) that is at most about 2.3 a second, 23% of the SEC's
    published 10 a second. The SEC limits by IP address, and the egress address may be shared [S65 2.4].
  - The bulk history is 83 downloads plus the listing page, once, then one download a quarter.
- **Blocks:** on a 403 or 429 the code stops and waits. It never looks for another way in ([DB] section 2: retry a
  blocked page at most once).

### 2.6 Other data

- **Prices:** section 4.
- **Factors:** Ken French daily files [W5].
  - "Fama/French 5 Factors (2x3) [Daily]" gives Mkt−RF, SMB, HML and RF. RMW and CMA are not used.
  - "Momentum Factor (Mom) [Daily]" and "Short-Term Reversal Factor (ST Rev) [Daily]" give Mom and ST Rev.
  - On 2026-11-16 all three ended on 2026-09-30 ("created by using the 202609 CRSP database"), the day the holdout
    ends [D].
  - The page says "Copyright Eugene F. Fama and Kenneth R. French" and shows no separate terms [W5].
  - The factors are built from CRSP, so they include delisted firms.
  - **Publication lag:** about 1-2 months. Files ending 2026-09-30 were on the page on 2026-11-16 [D]. Every
    regression window ends where the factor files end. The forward rule for this lag is in 6.9.
- **The cash rate rf:**
  - History: the RF column of the 5-factor daily file (the one-month T-bill rate).
  - Rev 1 named FRED DTB3. FRED did not answer from this container: HTTP/2 INTERNAL_ERROR, then an empty reply on
    HTTP/1.1 [D]. The repo has no FRED code. DTB3 may replace RF only if the FRED host is allowed before the seal
    (9.15).
  - Forward, where the French files do not reach yet: the Yahoo ^IRX close (the 13-week T-bill yield, quoted in
    percent, U; U3a checks the quote), as the daily rate (1 + IRX/100)^(1/252) − 1.
  - B's cash earns rf. Every excess return, Sharpe and regression in this spec uses the same rf.
- **SPY, IWM and RSP:** total return from the Yahoo adjusted close.

### 2.7 Pages and documents read for this spec (2026-11-16)

- [W1] `https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets`: coverage, cadence, format,
  disclaimer, file paths.
- [W2] `https://www.sec.gov/files/insider_transactions_readme.pdf`: 7 pages, created 2022-08-23. Its sha256 begins
  eaa4c0526b2ec92f, and the data reviewer's copy matches [D]. Text extracted locally.
- [W3] 17 CFR 232.13(a), read on law.cornell.edu. ecfr.gov redirected to a block page, and that was not worked
  around.
- [W4] `https://www.sec.gov/submit-filings/technical-specifications`: the Ownership XML specification v5.5,
  2026-03-18. No note on the 10b5-1 element was seen in the part read.
- [W5] `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html`
- [W6] `https://eodhd.com/pricing` (4.4)
- [P] `https://www.nber.org/papers/w16454.pdf`
- [D], read or measured by the data reviewer:
  - the SEC listing page, the readme, 4 quarterly ZIPs (2010q3, 2015q3, 2019q3, 2026q3), 1 Atom page and 1 filing
    index page;
  - 17 CFR 232.13(a)(4) on law.cornell.edu;
  - `tiingo.com/about/pricing` and Tiingo's public `supported_tickers.zip`; `eodhd.com/pricing`;
  - the Ken French daily files; the Yahoo chart API (coverage samples); Stooq (a proof-of-work page).

## 3. Event definition (exact)

### 3.1 Rows kept

The filters run in this order, and every drop is counted by its reason (7.3, `rejects.jsonl`).

1. **Form:** `DOCUMENT_TYPE` = "4". Originals only.
2. **Transaction:**
   - Keep NONDERIV_TRANS rows with `TRANS_CODE` = "P" and `TRANS_ACQUIRED_DISP_CD` = "A".
   - Drop a row with `EQUITY_SWAP_INVOLVED` true.
   - DERIV_TRANS makes no events.
3. **Owners:** every reporting owner on the accession must pass all three tests. `RPTOWNER_RELATIONSHIP` is matched
   by case-insensitive substring, because its lists are mixed-case and sometimes lack commas (2.1).
   - An individual: `RPTOWNERNAME` matches none of the entity patterns (dv: LLC, L.P., LP, FUND, CAPITAL, PARTNERS,
     HOLDINGS, MANAGEMENT, ADVISORS, INC, CORP, TRUST). A trust here is an owner, not an issuer.
   - `RPTOWNER_RELATIONSHIP` contains OFFICER or DIRECTOR.
   - `RPTOWNER_RELATIONSHIP` does not contain TENPERCENT.

   If any owner fails, the accession is dropped: a joint filing with a fund or a 10% holder counts as the fund's
   trade. OTHER on its own also drops.
4. **Section 16:** `NOT_SUBJECT_SEC16` = 1 drops.
5. **Plans and private deals.** A row is dropped when any of these holds:
   - its accession's `AFF10B5ONE` is set. Set means '1' or 'true', case-insensitive; '0', 'false' and blank are not
     set. The flag is per accession, so it drops the whole accession. The TSV carries it from 2023 and the forward
     XML carries the same flag, so the holdout and the forward book apply one rule. Reject reason `aff10b5one`,
     counted apart from the footnote drops;
   - a footnote of the row or of the accession matches a plan pattern (dv: "10b5-1", "10b5 1", "trading plan");
   - a footnote matches a private-deal pattern (dv: "private placement", "subscription agreement", "registered
     direct", "rights offering", "public offering", "underwritten").

   The footnote patterns apply in every year (footnotes exist from 2006). The flag adds recall from 2023 only, so the
   design period (no flag) and the later holdout years differ in this one respect. The report counts the `aff10b5one`
   drops that no footnote pattern would have caught.
6. **Dates:**
   - `TRANS_DATE` must be on or before `FILING_DATE`; otherwise the row is malformed and dropped.
   - `FILING_DATE` − `TRANS_DATE` must be at most 30 calendar days (dv). This is a data-sanity rule that drops stale or
     mistyped dates.
7. **Value:** `TRANS_SHARES` > 0 and `TRANS_PRICEPERSHARE` > 0. Value = shares x price.
8. **Issuer:**
   - `ISSUERNAME` as filed matches none of the fund or blank-check patterns (dv: " FUND", " ETF", "ACQUISITION CORP",
     "ACQUISITION CO", "CLOSED-END").
   - The list is narrow on purpose. A "TRUST" pattern would drop operating REITs, such as BXMT and NXRT in the overlay
     rows [M]. A closed-end fund such as KYN [M] is caught by " FUND".
   - **Listed:** a symbol that is blank, "NONE" or "N/A" after normalization (3.4 a) drops as `not_listed`. In the
     samples these are mostly issuers with no listed stock: Publix, non-traded BDCs and REITs (Crescent Capital BDC,
     Benefit Street Partners). They cover 3.2% (2010q3), 2.2% (2015q3) and 5.1% (2026q3) of qualifying purchase
     accessions [D]. The rule reads the filing only, so it cannot select on survival.
9. **Price:** at least $5 (dv).
   - A priced event uses the as-traded close (3.4) of the session before entry.
   - An unpriced event uses the Form 4's own `TRANS_PRICEPERSHARE` (4.3), which is as-traded by nature.
   - Every price level in this spec uses the as-traded close: the close as printed that day, i.e. the raw close with
     later splits undone. That covers this floor, the sanity ratio, share counts, and the dollar volume of the
     liquidity floor and the cost buckets. Adjusted series are used only for returns.

### 3.2 The Cohen-Malloy-Pomorski class (the rule as implemented)

- **Unit:** the pair (`RPTOWNERCIK`, `ISSUERCIK`) (dv).
  - [P] says only "for each insider", and the parts read do not say which identifier they used across firms.
  - The pair is the stricter reading, and it is fixed here.
- **History rows:**
  - Rows count when they come from NONDERIV_TRANS in an original Form 4 with `TRANS_CODE` in {P, S}. This is the
    closest match to CMP's "open-market purchases and sales" [P p. 10].
  - On a joint filing, the row counts for every individual owner on the accession.
  - The month of a row is the month of its `TRANS_DATE`.
- **Point in time:** the class for year Y uses rows that meet both conditions:
  - `TRANS_DATE` falls in Y−3, Y−2 or Y−1;
  - `FILING_DATE` is on or before Y−1-12-31.

  This is stricter than CMP, who used trade dates: a December trade filed in January does not count toward that
  January's class.
- **Classifiable for Y:** at least one history row in each of Y−1, Y−2 and Y−3 [P p. 11].
- **Routine for Y:** classifiable, and some calendar month m holds a history row in month m of each of Y−1, Y−2 and
  Y−3 [P p. 12].
  - Interpretation: the "three consecutive years" are the three years of the classification window. A pattern older
    than Y−3 does not count.
  - [P] fn 9 reports similar results with windows of one to five years. Only the three-year window is used here.
- **Opportunistic for Y:** classifiable and not routine. The class holds for the whole of Y.
- **Unclassifiable** (fewer than three years of history): excluded from the primary, as in CMP.
  - CMP's classified sample "is about one-third the size of the entire sample of insider transactions" [P p. 13].
  - Variant V3 includes these insiders (6.3).
- **Year of a trade:** the year of its `TRANS_DATE`.
- **Warm-up:** the data start in 2006, so 2009 is the first year that can be classified. Events start on 2009-01-02.
- **Sanity print:** for comparison, CMP classified 36% of purchases as opportunistic [P p. 13]. The build prints our
  share per year before any return is computed.

### 3.3 The event: one per (issuer, entry session)

- **Grouping:** all rows that pass 3.1 and whose pair is opportunistic for the trade's year are grouped by
  (`ISSUERCIK`, entry session from 2.3).
- **Double reporting, merged before counting:** within one issuer and one entry session, rows from different
  accessions with identical (`TRANS_DATE`, `TRANS_SHARES`, `TRANS_PRICEPERSHARE`) are one purchase. They count once in
  `value` and once in `n_insiders`. A shared indirect holding reported by two owners is the usual cause. The number of
  merges is reported.
- **Fields of an event:**
  - `n_insiders`: distinct purchase owners after the merge. A row's owner is its accession's single owner. A joint
    accession (several owners) counts as one owner, the lowest `RPTOWNERCIK`, because its rows cannot be tied to one
    of them (2.1). A merged purchase counts as one owner.
  - `value`: the sum after the merge.
  - first and last `TRANS_DATE`, the accessions, and the symbol as filed.
- **Minimum size:** the event's value is at least $25,000 (dv). No evidence-based default exists ([DB] "Insider
  filter"). Variant V5 tests $100,000.
- **Clustering:** none in the primary, as in CMP. Variant V4 requires at least 2 distinct opportunistic owners on the
  issuer among the filings whose `FILING_DATE` lies in the 30 calendar days up to and including the filing that
  completes the count.
  - The window looks backward only. A V4 event enters at the first session after the filing date of the second
    owner's filing (2.3).
  - Every later qualifying filing whose own backward window holds 2 or more owners makes a new V4 event.

### 3.4 Symbol mapping, price levels and price sanity

**The mapping rule** (an event to a price series). The data set carries only `ISSUERCIK` and the symbol as filed. Filed
symbols are dirty: "(CALX)", "MOGA-MOGB", "CRDA CRDB", "FKYS-OB", "BWINB - A", "NONE" [D]. Many Yahoo misses are
renamed survivors, not dead firms: JEC (now J), DPS (now KDP), PRSC, HSC, AXL [D].
- **(a) Normalize** the filed symbol: upper-case; strip parentheses and the spaces around separators; strip an -OB,
  -PK, .OB or .PK suffix; turn "." and "/" into "-". A blank, "NONE" or "N/A" result is `not_listed` (3.1 step 8).
- **(b) Candidates, tried in this order:**
  1. the normalized symbol;
  2. its first token, when a space, "-" or "," separates it from a second token of 2 or more characters. So
     "MOGA-MOGB" gives MOGA and "CRDA CRDB" gives CRDA, while "BRK-B" keeps its class letter;
  3. the CIK's current ticker from `company_tickers.json`;
  4. the price source's own symbol-change history for candidates 1-3.
- **(c) Several series under one ticker** (a reused ticker in a source keyed by ticker and date range, or a source's
  convention for old tickers): the series whose listed date range contains `TRANS_DATE` is taken. A source with a
  permanent id (Sharadar's permaticker, U) is keyed by that id once a candidate has matched.
- **(d) The guard:** a candidate is accepted only when its series passes the price check below. The first candidate
  that passes wins. If none passes, the event is unpriced (4.3).
- **(e) Today's ticker file, for lookup only.** Candidates 3 and 4 serve price lookup only. Eligibility, the class, the
  ranking and every filter are decided from the filing before any lookup.
  - Rev 1 banned `company_tickers.json` for history because it maps today's tickers and would leak renames and
    survival. Used only to find a series for an event that is already eligible, it leaks one thing: renamed
    survivors get priced and dead firms do not.
  - That is the survivorship problem of 4.2. The calibrated fill (4.3) and the control C (6.4) handle it, and C runs
    through the same mapping.
  - The match method of every event (filed, first token, CIK, history, unpriced) is counted per period.

**As-traded levels.** Every price level uses the as-traded close (3.1 step 9): the close as printed that day.
- From a source with an unadjusted close, it is that close.
- From Yahoo, it is the split-adjusted close multiplied by the ratio (numerator / denominator) of every later split,
  as `data._events_from_chart` reads the ratios [C data.py:101-111]. That Yahoo's close is split-adjusted and not
  dividend-adjusted is U; U3a checks it on a known split.
- The repo's own Yahoo client replaces close with adjclose and scales open, high and low by the same factor
  [C data.py:94-97]. Its levels carry every later split and dividend, so the insider client does not use it for
  levels.
- Dollar volume = as-traded close x as-traded volume. That equals split-adjusted close x split-adjusted volume, and is
  never adjclose x volume.
- What adjusted levels would do [Q]: a $16 stock that later split 4:1 would show $4 and be dropped. A $0.80 stock that
  later reverse-split 1:10 would show $8 and be kept. A long-time dividend payer (bank directors make many code-P
  buys) would show a lower price. The forward book sees the as-traded price, so only as-traded levels make the
  replay test the filter the book will trade.
- The forward book writes the levels it decided on into its decision rows, so a later re-read of split-adjusted data
  cannot change them.

**Returns** use the adjusted (total-return) series only: the adjusted close, and the open scaled by that day's ratio of
adjusted close to as-traded close, as `data.py` does for its own bars [C data.py:94-96]. So an ex-dividend day does
not move return from the open-to-close segment to the close-to-open segment or back.

**Price check:**
- Compare the Form 4's `TRANS_PRICEPERSHARE` with the series' as-traded close on `TRANS_DATE` (or the nearest earlier
  session).
- At least one row of the event must have a ratio in [0.75, 1.33] (dv).
- Otherwise the candidate fails. When every candidate fails, the event is a `price_mismatch`: the series belongs to
  another company (a reused ticker), another share class or an ADR ratio, or the units are wrong.
- A mismatched event becomes unpriced (4.3). It is not dropped, so a bad mapping cannot select survivors.
- **Why:** in the current overlay, 14 of 145 rows sit outside [0.67, 1.5] [M]:
  - TSM: 2.9-3.2x
  - PAM: about 5.3x
  - LUCK: about 0.2x
- The band is a guard against the wrong company, not proof of the right one: a wrong series can fall inside ±30% by
  chance. Candidates 3 and 4 name the same company by construction, and the hand check of the audit (6.7 step 9)
  samples the matches.

## 4. Universe and survivorship

### 4.1 Universe
- Every issuer with an event (3.3). There is no index membership and no hand-picked list.
- **Liquidity floor:** a 20-session median dollar volume (as-traded, 3.4) of at least $1,000,000 before entry (dv).
  - It applies to every priced event, in the book (section 5) and in the event portfolio E. The history source must
    therefore carry volume (4.4).
  - Unpriced events cannot be checked against it (4.3). Coverage counts them against the priced events that pass it
    (4.3).

### 4.2 The problem
Yahoo serves today's tickers, which causes three problems:
- A delisted name answers 404 "No data found, symbol may be delisted". A reused or relisted ticker answers 400 "Data
  doesn't exist for startDate", or returns another company's history [D].
- Measured coverage (4.4) is 44.5-61.7% [D], far under the 85% the test needs.
- Its terms allow personal use only [DB] section 2.

The forward book has no survivorship bias, since it trades at the time. The history does.

### 4.3 Treatment, fixed before coverage is known

| Case | Primary (T1) | Upper bound (T0, reported) | Stress (T2, reported) |
|---|---|---|---|
| Priced event: passes 3.4 and has its entry open | real prices | real prices | real prices |
| Unpriced event: no series, `price_mismatch`, or a series that starts after entry | IWM's total return over its hold window plus the calibrated shortfall f (below), at the highest cost bucket (50 bp per side) | dropped | IWM − 30% over the hold |
| The series ends during the hold (delisted or acquired) | exit at the last close | exit at the last close | last close − 30% |

**The fill f, calibrated on dead names before any design run.**
- **Why:** a missing series means the name left the tape after the event (failure, merger or rename), so the priced
  set is selected on what happened after the event. Names that later failed probably lost to IWM during the hold.
  Filling them with IWM (zero alpha) keeps the priced set survivor-heavy and only dilutes it. At 15% unpriced, a −5%
  shortfall per 63-session hold is about 0.25%/month of E's alpha [Q], roughly the whole expected edge (6.6).
- **Sample:** 200 design events (entry 2009-2018) drawn at random (seed 0) among those Yahoo cannot price under 3.4.
  The same sample decides the price source (4.4).
- **Pricing:** from a delisting-inclusive source, through the same mapping, price check and as-traded rules: the
  bought source where it prices an event, otherwise the Tiingo free test of 4.4.
- **Statistic:** for each priced sample event, d = its 63-session hold return (adjusted open to adjusted open; the
  last close when the series ends) minus IWM's over the same window, before costs. L is the 2.5% quantile of the
  mean of d over 2,000 cluster-bootstrap resamples (clusters: the calendar month of entry; seed 0). Then
  f = min(0, L). The cap at 0 keeps the fill from ever beating IWM.
- **Use:** an unpriced position earns IWM's daily total return, with f spread evenly in log terms over its 63
  sessions, and pays 50 bp per side. E, B and the control C use the same f.
- **When:** f is computed by the sealed code from sealed inputs, right after the seal and before the first design run,
  and written to the chain (6.7 step 6). It is the one computation on returns before the design runs; its formula is
  fixed here and its inputs are design-period returns of the sample only.
- **Uncalibrated:** if fewer than 100 sample events (dv) can be priced, or no delisting-inclusive source is used, f is
  not calibrated. T1 then keeps f = 0, and bar P6 applies (6.5).
- **What f does not cover:**
  - The sample holds events that Yahoo misses and a delisting-inclusive source prices. The events still unpriced in
    the main run (no source prices them) may be worse: obscure, OTC or dead names. The lower bound and the cap lean
    against that, and T2 bounds it.
  - A series that ends at a delisting carries no delisting return, so the last close flatters a failure. T2 shows by
    how much.
- **The −30%:** Shumway's (1997) average delisting return for performance delistings, from memory (U). It is an
  extreme bound and never a pass bar.
- **The book under T1:** an unpriced event is taken or skipped by the same ranking as any other event (5.3). It is
  sized in dollars, since it has no price to round shares to. So the book's picks never depend on whether a name
  survives at a price source today.

**Coverage.**
- Coverage = priced events that pass the liquidity floor / (priced events that pass the floor + unpriced events),
  counted after 3.1-3.3.
  - Priced events below the floor are dropped and reported apart.
  - Unpriced events cannot be floor-checked, so some of them would have been dropped if priced. The definition errs
    toward lower coverage.
- It must be at least 85% (dv) in the design period and in the holdout.
- It is computed before any return is computed (6.7 step 4).
- Design coverage is printed as numbers, per year. Holdout coverage is printed only as pass or fail against 85% until
  the unseal, because it carries survival information about holdout names.
- **Design-start fallback (dv):** if design coverage is below 85% but the years from some January Y to 2018, with Y no
  later than 2013, reach 85% together, the design period starts on the first session of the earliest such Y. At least
  6 design years remain. The holdout is unaffected.
- Otherwise, below 85%, the test is "not measurable with this data": the owner makes the data decision (9.2) and the
  holdout stays sealed. This is not a kill.

### 4.4 The price source for history (owner decision 9.2, taken before U3b)

**Measured coverage** [D]. Random samples (seed 0) of events built from the SEC quarterly files: P/A, original Form 4,
every owner an officer or director and not a 10% owner, individual owner names, lag of 30 days or less, event value of
$25k or more, Form 4 price of $5 or more, before the CMP class filter. An event counts as priced when a Yahoo series
exists, its split-undone close on the trade date lies within [0.75, 1.33] of the Form 4 price, and an entry open
exists.

| Sample | Yahoo | Yahoo misses whose ticker and date range Tiingo lists | Upper bound, Yahoo + Tiingo |
|---|---|---|---|
| 2010q3 | 49/110 = 44.5% | 42/61 | 82.7% |
| 2015q3 | 51/110 = 46.4% | 50/59 | 91.8% |
| 2019q3 (holdout; coverage only) | 37/60 = 61.7% | 12/23 | 81.7% |

- Tiingo's public `supported_tickers.zip` lists 17,458 USD stocks that ended before 2026 [D]. "Lists" is an upper
  bound: no price was checked, and reused tickers are not resolved.
- So Yahoo alone cannot reach 85%. Rev 1's path ("build on Yahoo, buy data only if needed") would almost certainly end
  in "not measurable" after U0-U5 were built. The decision to buy a delisting-inclusive source is taken now, before
  U3b.
- Said plainly: even a paid source keyed by ticker may stay under 85% in the early design years, so the bar may still
  fail for 2009-2012. Then the design-start fallback (4.3) applies, or the test is not measurable.

**Sources:**

| Source | Cost | Delisted names | Notes |
|---|---|---|---|
| Yahoo | $0 | no | ETFs, ^IRX, the forward book, and a fallback for history; personal-use terms [DB] |
| Tiingo | free tier $0: 500 unique symbols/month, 50 requests/hour, 1,000/day, "30+ Years" of history; Power $30/month [D] | yes, by ticker and date range [D] | the free tier can test a 200-symbol sample, not the full run |
| EODHD | $19.99/month, $199/year [D, W6]; free tier 20 calls/day with "1 yr" of history [D] | yes, in every package [PF] | the free tier cannot test 2009-2018, so testing it means paying the first month; an "_old" convention for reused tickers was seen only as a heading (U) |
| Sharadar SEP (Nasdaq Data Link) | about $9-39/month personal, per a vendor (U) | from 1998 (U) | the one source with a permanent id (permaticker) |
| Norgate Platinum | about $630/year from a third party (U) | yes (U) | not viable: its updater is Windows-only [PF line 168] |
| Stooq | - | - | dropped: it now answers with a JavaScript proof-of-work page [D], so it is not a scripted source |
| CRSP through WRDS | institutional | yes | the academic standard; not open to an individual (U) |

**What the bought source must carry:** delisted names; unadjusted and adjusted closes (or the splits and dividends to
rebuild them); opens; and volume, since the liquidity floor applies to every priced event (4.1). Its terms are read
before buying (U). Its data stay in `.cache/insider/`, are never committed, and serve this research only.

**Roles:** the bought source prices every event stock in history. Yahoo prices the ETFs, ^IRX and the forward book, and
is a fallback for a history event the bought source cannot map, under the same guard. Each priced event takes one
source for its whole hold. The holdout and the forward book therefore use different price sources for event stocks;
the rule they test is the same.

**Recommendation** (step P of 8.1, between U3a and U3b):
1. The owner opens a free Tiingo account and key himself (hard rule 1: no session creates accounts). The key reaches the
   session as a network secret or an environment variable, never a file.
2. Step P prices the 200-event sample of 4.3 on the free tier: $0, about 4 hours at 50 requests an hour. It gives the
   share of Yahoo misses that Tiingo prices.
3. Projected design coverage = Yahoo coverage + (share priced by Tiingo) x (1 − Yahoo coverage). If it reaches 85%,
   buy exactly one month of Tiingo Power ($30). If it does not, buy one month of EODHD ($19.99; its first month is its
   test) or of Sharadar SEP (U), and test that source on the same sample before the full download. Only one month of
   one source at a time.
4. U3b's client is written and tested on fixture files before the paid month starts. The full history panel is
   downloaded and cached inside that month. The mapping work (3.4) adds 4-8 hours (8.3).

## 5. Portfolio rules (the book)

Every number below lives in `config.json` `books.insider` (Appendix B). The numbers are dv unless a source is given.

### 5.1 Entry
- At the open of the entry session (2.3). Fill = open x (1 + cost per side).
- History: the as-traded open of the event's price source (4.4). Forward: Yahoo's daily open; the forward book also
  records the 09:30 one-minute bar as a cross-check.

### 5.2 Holding period
- 63 trading days. Exit at the open of the 64th session after entry.
- Why 63:
  - CMP test one month [P Table IV].
  - Their event-time spread keeps rising for about six months [P p. 5].
  - Costs favour longer holds.
  - V1 (21 sessions) and V2 (126) are design variants.
- **A new event on a held name** restarts the exit clock from the new entry session. Nothing is added, and the size
  stays as it was (Basic law: never average down).

### 5.3 Sizing and slots
- Starting cash: $100,000 paper, the size of the other books.
- At most 30 names. Each new position is 1/30 of current equity, in whole shares at the as-traded entry fill (3.4).
  The rest stays in cash at rf. An unpriced position is sized in dollars (4.3).
- After entry a position's value follows the adjusted series: value = shares x as-traded fill x (adjusted price now /
  adjusted entry open). Dividends stay in the position, in history and forward alike.
- **More events than free slots on a day:** rank by `n_insiders` (descending), then `value` (descending), then
  `ISSUERCIK` (ascending). No ranking uses returns. Skipped events are logged.

### 5.4 Limits
- **Position size:** at most 1% of the 20-session median dollar volume (as-traded) at entry.
  - At $3,333 positions and the $1M floor this does not bind.
  - It starts to bind if the book grows past about $300,000.
- **Sectors and volatility:** no sector cap and no vol target in v1, unlike the stock book. The data set has no sector
  field (2.1). EDGAR submissions carry SIC codes, which a later version could use for a sector cap. This is accepted
  for a log-only book. The other risk rules are intact: long-only, no leverage, whole shares, the breaker, the
  catastrophe stop, and reduce-only overrides with a no-veto shadow (5.8).

### 5.5 Exits planned before entry (Basic law, item 2)
- **Time exit:** 5.2.
- **Catastrophe stop:** when a close is at or below entry x (1 − 0.30), exit at the next open. The law asks for a
  planned limit on every loss. No evidence exists for any stop on this signal, so variant V6 measures the book
  without it.
- **Book breaker,** the same three settings as the stock book:
  - at −10% from the peak, new positions are half size;
  - at −20%, everything is sold at the next open;
  - after 20 sessions, re-entry with the breaker's peak reset.
- The breaker's peak is not the high-water mark of the forward kill K3(c), which is never reset (6.8).

### 5.6 Costs
- Per side, by 20-session median dollar volume (as-traded):

  | Median dollar volume | Cost per side |
  |---|---|
  | $50M or more | 10 bp |
  | $10M to $50M | 25 bp |
  | under $10M | 50 bp |

  These are U. For comparison, the stock book uses 5 bp, and the review counts that among frictions "not yet
  modelled" [Rv].
- Unpriced (T1) positions pay 50 bp.
- A stress run uses 2x costs.
- No commission on paper. At the real-money gate the owner's measured broker fees replace this.
- Cash earns rf (2.6), day by day.

### 5.7 Taxes
- The report shows an after-tax line at 25% of net realized gains per calendar year (the Israeli rate, U [Rv]).
- That line feeds no holdout bar. Stage 3 (6.9) uses it with the rate the owner gives.

### 5.8 Discretion
- None. The rules decide every entry, size and exit.
- **Stage 1 (log-only):** the trading session does nothing to the book.
- **From stage 2:**
  - The session may only veto or shrink a new entry, reduce-only, with a concrete reason: fraud, a halt, a
    going-concern warning or a pending offering (CLAUDE.md hard rule 3).
  - A no-veto shadow book is kept, and both books are reported.

### 5.9 What the book is not
- No shorting. Sales are not traded, and CMP's 82 bp needs a short leg [P].
- No leverage and no options.

## 6. Evaluation protocol (pre-registered)

### 6.1 Periods
- **Data:** filings from 2006-01-01 to 2026-09-30 (83 files).
- **Warm-up for the class:** 2006-2008. These years make no events.
- **Design:**
  - events whose entry session falls from 2009-01-02 (or the fallback start of 4.3) to 2018-12-31;
  - daily returns over the same dates;
  - positions still open on 2018-12-31 are marked at that close and closed.
- **Holdout (sealed):**
  - events whose entry falls from 2019-01-02 to 2026-09-30;
  - daily returns over the same dates, about 1,950 sessions (an estimate);
  - positions open at the end are marked at the last close;
  - the holdout portfolio starts empty, with no position carried over from the design period.
- **The control C** follows its own pseudo-entry dates (6.4).
- **Forward:** from the seal (6.7 step 5) onward. See 6.9 and section 7.

### 6.2 What has been seen already
- Nobody in this project has computed an insider return for any period.
- Earlier looks, disclosed here:
  - the roadmap's unverified claim about 2020-2025 [RM line 69];
  - the literature, whose samples end in 2007;
  - general knowledge of index returns. Benchmarks are not the test, but one fact matters to P2: small caps lagged
    SPY over much of 2019-2026 (U; checked from prices before the unseal, a look at benchmarks, not at the book);
  - **the rev 1 review [D]:** Yahoo price coverage on random event samples of 2010q3, 2015q3 and 2019q3. The last is
    a holdout quarter: 61.7% coverage, and Tiingo's list holds 12 of its 23 misses. No return was computed. Coverage
    says something about survival in the early holdout; that is now disclosed, and the holdout's own coverage stays
    pass/fail until the unseal (4.3);
  - format, size and flag counts from four ZIPs (41 flagged of 2,079 qualifying purchase accessions in 2026q3), with
    no prices.
- The 290 overlay rows of 2026-11-06 to 2026-11-13 [M] come after the holdout and have no grades.
- **Planned looks before the design runs:** the fill sample (4.3), design-period returns of up to 200 events that
  Yahoo cannot price, computed mechanically after the seal.

### 6.3 Runs allowed (all count in N for the Deflated Sharpe)
All eight runs are listed in the seal record before the first one starts:

| Run | What changes from V0 |
|---|---|
| V0 | nothing: the primary (sections 3-5), run together with its control C (6.4) |
| V1 | hold 21 sessions |
| V2 | hold 126 sessions |
| V3 | unclassified insiders count as opportunistic |
| V4 | cluster: at least 2 opportunistic owners within a backward 30-day window (3.3) |
| V5 | minimum event value $100,000 |
| V6 | no per-position stop (book only) |
| V7 | every officer/director purchase, of any class (shows what the CMP filter adds) |

- **Each run happens once,** on the design period only.
- **Defect re-runs:**
  - Allowed only for a defect: a bug that the quant-critic agrees is a bug, not a rule change.
  - Every changed file gets a defect record in the chain: the file, its old and new sha256, the critic's verdict and
    the runs it affects (6.7).
  - The affected runs are repeated, and every repeat adds to N.
  - At most 2 rounds; more needs the owner's word.
- **N for the holdout DSR:** the number of registered design runs (8 or more) + 1. C is a control, not a candidate
  strategy, and is not counted.
- **Only V0 is ever unsealed.** A design variant that looks better changes nothing. It can come back only as a new
  written hypothesis, tested on data after 2026-09-30.

### 6.4 Measurements

**E, the event portfolio (the edge).**
- Every eligible event, priced or T1, holds one unit from its entry open to its exit open. There is no stop, no slot
  limit and no breaker: E measures the signal, not the book.
- **Buy-and-hold weights.** Each position is weighted by its value since its entry open, and all are equal at entry.
  For position i, with adjusted opens O and adjusted closes P (3.4), cost per side c_i, entry session e_i and exit
  session x_i:
  - V_i(e_i − 1) = 1, the unit at the entry open;
  - V_i(e_i) = (1 − c_i) x P(e_i) / O(e_i): open to close on the entry day;
  - V_i(t) = V_i(t − 1) x P(t) / P(t − 1) for e_i < t < x_i: close to close;
  - V_i(x_i) = V_i(x_i − 1) x O(x_i) / P(x_i − 1) x (1 − c_i): close to open on the exit day.
- E's return on day t: R_E(t) = Σ_i V_i(t) / Σ_i V_i(t − 1) − 1, over the positions active on t
  (e_i ≤ t ≤ x_i). That is Σ w_i(t−1) r_i(t) / Σ w_i(t−1) with w = V. A day with no active position earns rf.
- **Why not equal weight every day:** re-setting every position to equal weight each day, with last-trade closes,
  picks up bid-ask bounce: about s²/4 a day, roughly 0.6%/yr at a 1% spread (Blume-Stambaugh 1983, Liu-Strong 2008,
  U) [Q]. That is an upward bias, not a cost, and neither P1 nor P5 at 2x costs removes it.

**B, the book (the money):** section 5, exactly.

**C, the negative control.** Backlog 3 says to promote "only after a forward record + placebo gate" [K 3]. Rev 1
dropped the placebo without saying so. C runs through the identical pipeline: the filters, the mapping, as-traded
levels, T1 and f, costs, E's construction and R1.
- **Pseudo-events:** for each event, C takes a pseudo-event on the same issuer 252 sessions (dv) earlier. Its entry
  session is the event's entry session minus 252 NYSE sessions. The same issuer means the same price series and the
  same survival-to-today status, so survivorship and pipeline biases reach C as they reach E.
- **Skip rule:** a pseudo-event is skipped if the issuer has any code-P row (any owner, any class, original Form 4)
  whose entry session (2.3) lies within 63 sessions before or after the pseudo-entry. The skip reads filings after the
  pseudo-entry date. C is never traded, so this is allowed for the control and only for it.
- **Fields and filters:** a pseudo-event carries its event's `value` and `n_insiders`. The price floor, the liquidity
  floor and the price check are applied at the pseudo-event's own dates; one that fails them drops out of C,
  counted.
- **Calendar time:** C is a calendar-time portfolio built like E, and a pseudo-event belongs to the period of its own
  pseudo-entry.
  - C's holdout members are the pseudo-events of events up to 252 sessions later. Events end on 2026-09-30, so C's
    holdout runs from 2019-01-02 to about 2025-12 (an estimate), when the last pseudo-position exits.
  - C's design members include the pseudo-events of 2019 events. Their identities come from the event table, built
    before the seal, and their returns are 2018 returns, so no holdout return is touched.
- **Known bias, in the safe direction:** a pseudo-event's issuer is known to survive at least until its real event a
  year later, so C never holds through a delisting and leans upward. Both C bars (6.5) are therefore harder, not
  easier, to pass.
- **Known weakness:** insiders are contrarian, "buying after low past returns" [P p. 13]. C's window (about months
  −12 to −9 before the purchase) may hold part of that decline.
  - A negative C is then not evidence of a downward pipeline bias. That is why the C test is one-sided (t < 2), as
    proposed: a two-sided test would call an honest pre-purchase decline "not measurable".
  - The same decline weakens the (E − C) bar against an upward bias. It cannot create a pass, because every bar must
    hold (6.5).
  - The pre-event return curve (day −252 to day 0, design only) is reported, to show how much of the decline falls
    in C's window.
- C is never unsealed as a candidate and does not count in N.

**R1, the residual-edge gate (backlog 5) for this book:**
- Daily regression with Dimson (1979, U) lagged betas:
  (R − rf)(t) = α + Σ over k = 0, 1, 2 of b_k · F(t − k) + ε(t), with F = [Mkt−RF, SMB, HML, Mom, ST Rev] (2.6).
  That is 15 slopes. OLS. The t is Newey-West with 10 lags (dv). α is annualized x 252. The lags of a window's first
  two days come from the factor days before it.
- **Why the lags:** an equal-weight portfolio of small caps (ADV of $1M and up) trades out of sync with the factors.
  Without lags its daily betas come out too low, and α absorbs (missed beta) x mean(Mkt−RF). A missed beta of
  0.15-0.25 against a 2019-2026 premium near 10%/yr is about 0.12-0.2%/month [Q], a third to a half of the decayed net
  edge of 6.6.
- R1 is applied to E, to C, to the daily series E − C (with E − C in place of R − rf), to each half (P4), at 2x costs
  (P5), and forward (6.9). Its window ends where the factor files end (2.6).
- It covers backlog 5's size, equal-weight and momentum terms. It adds value and short-term reversal, because
  "insiders are contrarian, buying after low past returns" [P p. 13].
- **Monthly cross-check (reported, not a bar):** the CMP-style regression on calendar-month compounded excess returns,
  with the monthly French files (the same five factors) at lags 0 and 1, Newey-West with 3 lags (dv).

**R2, an ETF cross-check (reported, not a bar):** the same Dimson regression on SPY−rf, RSP−SPY, IWM−SPY and Mom.
**R2f**, the forward fallback (6.9), drops Mom, so that it needs no French file.

**Sharpe and CAGR: the exact recipe** (P2). `metrics` is imported and not edited.
- Inputs: the holdout's daily total returns of B, SPY and M, and rf, on common days. The house floor applies: under
  800 days (40 blocks of 20 days) the test refuses, as `boot_rows` does [C metrics.py:135-139].
- idx = `metrics.boot_index(n, 20, 2000, 0)` [C metrics.py:78]: the repo's block, draws and seed
  [C config.json:293-299].
- Sharpe: S = `metrics.boot_stats(X − rf, idx, rf_daily=0)["sharpe"]` [C metrics.py:96], on the rf-excess series.
  P(Sharpe_B > Sharpe_SPY) = `metrics.p_above(S_B − S_SPY)` [C metrics.py:115].
- CAGR: G = `boot_stats(X, idx, rf_daily=0)["cagr"]`, on total returns and the same idx, so every pair shares its
  resampled days. P(CAGR_B > CAGR_M) = `p_above(G_B − G_M)`.
- `boot_rows` itself is not used: it pairs only Sharpe and subtracts one fixed rf [C metrics.py:121-165].

**Benchmarks:**
- SPY.
- M, the exposure-matched mix: M_t = g_t x SPY + (1 − g_t) x rf, where g_t is the book's invested fraction at the
  previous close.
  - With a constant g, M's Sharpe would equal SPY's [Rv]. With g_t taken from the book it does not.
  - M is compared on CAGR, in P2 and in stage 3 (6.9).
- IWM, RSP and an IWM/rf mix, reported only.

**DSR:** `metrics.dsr` [C metrics.py:48] on B's holdout daily rf-excess returns, with N from 6.3.
- `sr_trials_std` is in daily units, because `psr` computes Sharpe per period [C metrics.py:35-45].
- It is the standard deviation of the daily (not annualized) Sharpe ratios of B over every registered design run,
  each on its design-period rf-excess returns.

### 6.5 Bars

**Design gate G0** (before the unseal), on V0 over the design period:
- E's R1 α > 0 with NW t ≥ 1.5 (dv);
- coverage ≥ 85% (4.3);
- C's R1 α has NW t < 2.0. Otherwise the result is "pipeline biased, not measurable" and the holdout stays sealed, as
  with coverage. This is not a kill.
- C's line (α, t, coverage, skips) is in the design report.

**Holdout PASS.** All of these must hold, on V0, under T1, at base costs:

| Bar | Book | Test |
|---|---|---|
| P1 | E | R1 α > 0 with NW t ≥ 2.0 |
| P2 | B | P(Sharpe_B > Sharpe_SPY) ≥ 0.8 **and** P(CAGR_B > CAGR_M) ≥ 0.8 (recipe 6.4) |
| P3 | B | DSR ≥ 0.95 |
| P4 | E | R1 α point estimate > 0 in each half (2019-01-02 to 2022-10-31; 2022-11-01 to 2026-09-30) |
| P5 | E | R1 α point estimate > 0 at 2x costs |
| P6 | E | only when f is not calibrated (4.3): R1 α point estimate > 0 with every unpriced event at IWM − 15% over its hold (dv) |
| P7 | E, C | C's holdout R1 α has NW t < 2.0, **and** the R1 α of the daily series E − C, on the days both exist, is > 0 (point estimate) |

- **Why many bars are fine:** each is a further condition on the same run, so together they can only lower the
  false-pass rate. P1 tests the edge on E, which has the most power. P2 tests the money on B, which is what would be
  traded. This is not multiple testing that needs a correction.
- **Reported, not bars:**
  - T0 and T2;
  - R2 and the monthly cross-check;
  - the IWM, RSP and IWM-mix lines;
  - drawdown and turnover;
  - counts by reject reason, by year and by match method (3.4);
  - **single episodes:** March 2009 and March 2020 were waves of insider buying at crash bottoms, and P4's first half
    contains 2020 [Q]. So E's R1 α is also shown without 2009-03 to 2009-06 (design) and without 2020-03 to 2020-06
    (holdout), and as the smallest α when each calendar year is left out in turn;
  - the event-time return curve from day −252 to day 126, on the design period only.

### 6.6 Power (estimates before any look)

- **Formula:** t ≈ (α / σ_ε) x √T, with monthly α and monthly residual volatility σ_ε. The holdout has T = 93
  months, so √T = 9.64.
- **Daily against monthly:** R1 is daily. With independent residuals the daily test gives the same t, because
  (α_m / 21) / (σ_m / √21) x √(21 T_m) = (α_m / σ_m) x √T_m. So the table, in monthly units, also describes R1
  roughly. The lags and the Newey-West errors correct what that independence ignores, and the power line below uses
  the measured error.
- σ_ε of E is unknown (U). For reference, the raw (not residual) monthly standard deviation of CMP's equal-weight
  opportunistic-buy portfolio was 4.95% [P Table IV].

| Case (all numbers U) | Net α per month | σ_ε 1.5% | σ_ε 2.0% | σ_ε 3.0% |
|---|---|---|---|---|
| CMP EW buys, no decay, minus 0.30% costs | 1.28% | t ≈ 8.2 | 6.2 | 4.1 |
| CMP EW buys after 58% decay, minus 0.30% | 0.36% | 2.3 | 1.7 | 1.2 |
| CMP VW buys after decay, minus 0.10% | 0.20% | 1.3 | 1.0 | 0.6 |

- **What the table says:** the holdout can confirm only an effect near CMP's equal-weight strength. A real edge at
  half strength may well fail.
  - That outcome is acceptable under the Basic law ("no edge, no trade").
  - An edge that weak would not pass the real-money gate in a reasonable time anyway (7.6).
  - Three rev 2 changes lower the measured α further: the lags remove the missed-beta part, buy-and-hold weights
    remove the bounce, and f charges the dead names. Each removes a bias, not edge.
- **Power line before the unseal:**
  - After the design runs, the build prints α_min = 2 x SE_NW(α_design) x √(T_design / T_holdout), annualized: the
    smallest α the holdout can show at t = 2, from V0's measured Newey-West error and the ratio of day counts.
  - The owner sees this line before the unseal (9.6). He may choose to wait for more forward data instead.
    Waiting changes nothing else.

### 6.7 Order of operations, the seal and the audit

1. The contact address exists. Units U0-U2 are built (section 8).
2. **Event table:** built for 2006 to 2026Q3. It prints:
   - counts per year;
   - drops per reason (including `not_listed`, `aff10b5one` and merged double reports);
   - the share of each class.

   No price is touched in this step.
3. **Price source:** U3a is built. Step P runs (4.4): Yahoo coverage of the design events (as numbers), the 200-event
   sample, the free Tiingo test, and the owner buys one month of one source. U3b is built, and the full history
   panel is downloaded and cached.
4. **Price panel and coverage:** design coverage per year as numbers, holdout coverage as pass or fail (4.3). The
   design-start fallback is applied if needed.
   - No return is computed in this step.
   - The return code refuses any return while no seal record exists, and any date on or after 2019-01-02 while no
     unseal record exists.
5. **Seal.** `insider-replay --seal` writes one record to `state/insider/trials.jsonl` (hash-chained). The record
   holds:
   - the sha256 of this whole file;
   - the sha256 of every `aitrader` module the replay loads: every `aitrader.*` entry of `sys.modules` after
     `insider_replay` is imported, so `metrics.py`, `journal.py` and `sec.py` are included;
   - the sha256 of `books.insider` (canonical JSON);
   - the sha256 of every cached input: the event table, the price panels of both sources, the fill sample's prices,
     the French factor files, the ^IRX series and the ETF series;
   - the commit, the 8 declared runs and C, the design coverage and the holdout pass/fail.

   The seal is written once. The record is committed and pushed before the first design run, so the chain has an
   outside timestamp. The forward clock starts here (6.9).
6. **Calibration:** the fill f (4.3) is computed and written to the chain.
7. **Design runs:** at most 8, V0 together with C, each registered with its result. Then the design report and G0.
   - If G0's α bar fails: K1.
   - If coverage or the C bar fails: not measurable, and the holdout stays sealed.
   - The stage-3 threshold p* (6.9) is computed from V0's design B and written to the chain before the first forward
     look.
8. **Power line** (6.6). The owner decides whether to unseal now.
9. **Audit, whatever the design result.** Written to the chain before the unseal, by the build, and checked by the
   quant-critic:
   - the TSV/XML parity tests and the look-ahead tests (U2, U3a, U5) pass on the sealed code;
   - the reject counts per reason and year are read, and none is left unexplained;
   - a hand check of 20 design events drawn at random (seed 0): the filing on EDGAR matches the event's owners,
     roles, code, shares, price and dates; the mapped series is the right company; the entry session follows 2.3;
     the as-traded close and the floors are right;
   - the same check on 10 pseudo-events of C (their dates and the skip rule).

   `--unseal` refuses without an audit record.
10. **Unseal**, once only. `insider-replay --unseal`:
    - recomputes every hash of the seal record from the files on disk. It refuses on any mismatch, unless every
      changed file has a registered defect record in the chain, agreed by the quant-critic and each adding 1 to N;
    - writes the unseal record;
    - runs V0 and C on the holdout;
    - writes the result and the verdict (PASS, KILL, or holdout spent: 6.8) to the same chain;
    - prints the report.

    A second unseal is refused.
11. **Review and verdict:** the quant-critic reviews the run (rule 4). The owner gets the verdict in one message.
12. **Project ledger.** The seal and the verdict each append one row to `state/holdout_ledger.jsonl`: the spec path,
    the hypothesis, the seal hash and the verdict. It counts every sealed-holdout test in the project. This is test
    1; post-earnings drift (review fix 4) would be test 2. Each search at P ≥ 0.8 or t ≥ 2 adds to the chance of a
    false discovery across the project, so a later spec states the count and judges its result against it.

### 6.8 The KILL criterion

The experiment ends, and backlog item 3 closes as "no measured edge", on any one of these:

- **K1:** G0's α bar fails. The holdout is never opened.
- **K2:** any of P1-P7 fails on the holdout.
- **K3, forward** (looks and methods in 6.9):
  - (a) At the 6-month look, the forward E's R1 α point estimate is below 0 **and** B's cumulative return is below
    M's.
  - (b) At the 12-month look, P(Sharpe_B > Sharpe_SPY) < 0.5, by the short-record method of 6.9.
  - (c) At any time, B falls 25% (dv) below its all-time high-water mark since the seal. The mark is never reset. The
    breaker resets only its own peak (5.5); measured from that peak, (c) could never fire, because the breaker sells
    everything at −20%. New entries stop and the loss protocol reviews the drawdown. It is a kill unless the review
    finds a defect.
  - (d) Stage 3 (6.9) is not passed by the 24-month look (dv).
  - A restart of the forward clock (6.9) resets neither (c) nor (d): both count from the seal.

**After a kill:**
- no hypothesis based on Form 4 purchases (any class, cluster or not, any filter) is tested on 2006-2026Q3 data
  again, since the V4 and V7 design results and the V0 holdout will have been seen;
- no new holdout is cut from those years for any such hypothesis;
- the book and the feed stop, unless the owner keeps the feed for spec 65's purpose;
- one line in `lessons.md` with the numbers;
- the book's rows leave the dashboard.

Re-opening needs a new written hypothesis and data from after 2026-09-30.

**Not a kill (the clock waits):**
- coverage below 85% (the data decision, 4.3);
- C biased in the design period (G0);
- a missing contact address;
- a feed outage. The forward clock pauses when the feed is down more than 10 sessions in a calendar month (dv).

**Defects found after the unseal: the one-way rule.**
- After the unseal, a fix may only turn PASS into KILL.
- The run is repeated once with the fix. The quant-critic must agree that it was a defect and not a rule change. Both
  results are kept, and N grows.
- PASS, then a fixed run that fails: KILL.
- KILL, then a fixed run that passes: not a pass. The holdout counts as spent. The book stays in stage 1, and
  promotion needs the forward record alone, under the forward-only bars F (6.9). K3 applies as written.
- Why: bugs get hunted after a KILL, not after a PASS. Letting a fix turn KILL into PASS would be a one-way door on a
  holdout that has already been seen.

### 6.9 Forward evaluation (pre-registered)

- **Clock:** it starts at the seal, once the feed exists. It is keyed on the sha256 of `books.insider` plus the sha256
  of the insider modules (6.7 step 5), and both are written into every row of `equity.jsonl`. A change to either
  restarts the clock. The outage pause of 6.8 stretches it.
- **Looks:** at forward months 6, 12, 18 and 24, counted from the seal, with paused months not counted. At a look, the
  record is the current clock's record since its last start. A look on a record shorter than 6 months does not count.
  So a restart can remove looks and never adds one.
- **The short-record method** (K3(b), stage 3 and F): the stationary bootstrap of `metrics.boot_index` with a mean
  block of 5 sessions (dv), 2,000 draws and seed 0, through `boot_stats` and `p_above` as in 6.4, with the forward
  rf (2.6).
  - `boot_rows` would refuse under 800 days [C metrics.py:135-139], because on few blocks a range comes out narrower
    than its label. Here that problem is handled by calibrating the pass threshold under the null with this same
    method (below), so its narrowness cannot buy a pass.
- **Forward α:** R1 on the forward E. The French files lag 1-2 months (2.6), so a look's α is computed when the files
  cover its window. If they still do not cover it 90 days (dv) after the look date, R2f (6.4) is used over the whole
  window, with rf from ^IRX. The Sharpe and CAGR parts of a look do not wait.
- **Stage 3, the real-money gate (CLAUDE.md hard rule 1).** It passes at the first look where all three hold, on
  returns after real costs (the owner's measured broker fees) and after the tax line (5.7):
  - (i) P(Sharpe_B > Sharpe_SPY) ≥ p*;
  - (ii) P(CAGR_B > CAGR_M) ≥ p*;
  - (iii) the forward E's α point estimate > 0. M matches dollar exposure, not beta, so in a small-cap rally a 30-name
    small-cap book can beat M with no skill.
- **The threshold p*.** Checking the gate every month would be optional stopping. A zero-edge book clears 0.8 by luck
  about 20% of the time at one look, and much more often across many correlated looks: the red team's 33.6% of
  quarters [Rv].
  - p* is the smallest value in {0.80, 0.81, ..., 0.99} such that, under a zero-edge null, at most 20% of simulated
    forward records reach (i) at one or more of the four looks.
  - The null: V0's design-period daily rf-excess returns of B, shifted by a constant so that their Sharpe equals SPY's
    over the same days, and paired day by day with SPY's.
  - The simulation: 1,000 forward records (dv) of 24 months (504 sessions), drawn by `boot_index` with a mean block of
    20 sessions and seed 1. At each look, (i) is computed by the short-record method.
  - p* is calibrated on (i) alone; (ii) and (iii) can only lower the false-pass rate further. If even 0.99 exceeds the
    20% budget, p* = 0.99 and the report says so.
  - It is computed once after the design runs (6.7 step 7) and written to the chain before the 6-month look. p* is
    0.8 or more by construction, so the owner's P ≥ 0.8 always holds.
- **Forward-only bars F** (only when the holdout is spent, 6.8): stage 2 needs a look at 12, 18 or 24 months where
  the forward E's R1 α > 0 with NW t ≥ 2.0, and (i) and (ii) hold at p*. Stage 3 then follows the rule above.
- **Expectation:** the gate will most likely take well over 6 months (7.6). The fixed looks and a p* above 0.8 make
  it longer. That is the price of a gate that a zero-edge book passes at most one time in five.

## 7. Forward paper book

### 7.1 Stages

- **Stage 1, log-only.**
  - Starts at the seal (6.7 step 5), when the feed exists, so the forward record builds while the history study is
    still running.
  - The book runs on paper from the frozen config. No one acts on it.
  - The owner gets only the weekly and monthly lines (7.6).
  - On K1 or K2 it stops. When the holdout is spent (6.8), it continues under the F bars.
- **Stage 2, after a holdout PASS** (or the F bars).
  - The same book, now named in the daily summary.
  - Veto and shrink are allowed, with the no-veto shadow (5.8).
- **Stage 3, the real-money gate (CLAUDE.md hard rule 1).**
  - The rule is in 6.9: fixed looks at 6, 12, 18 and 24 months, the threshold p*, and the three conditions, after
    the owner's measured broker fees and tax.
  - Only then is real money proposed, and it starts with a small slice.
  - Any change to `books.insider` or to the insider modules restarts the clock (6.9).

### 7.2 Daily operation: two runs, both idempotent

- **Close slot (the existing 16:22 ET slot):**
  - poll the day's filings so far: Atom pages filtered by title (2.2), then each XML, all cached;
  - record the morning's fills at the official open (Yahoo daily bar);
  - mark the book at the close and check the stops;
  - journal everything and feed the dashboard.
- **Pre-open run** (an existing slot between 08:45 and 09:25 ET, or a new task; 9.8):
  - read the previous business day's daily index (the complete list) and fetch any XML still missing;
  - build the day's events;
  - write the decision (entries, exits due, stops from yesterday's close) before 09:30, with the as-traded levels it
    used (3.4).

  A decision written after 09:30 applies to the next session and is tagged `late_decision`.
- **Running twice changes nothing:** a second run in one day makes no second trade and no second mark (tested).

### 7.3 Journals (new, under `state/insider/`)

- **Hash-chained** through `journal.append`, like the other books: `events.jsonl`, `decisions.jsonl`, `trades.jsonl`,
  `trials.jsonl`.
- **Plain files:**
  - `equity.jsonl`, one row per day: equity, cash, g_t, rf, SPY, M, IWM, the high-water mark of K3(c), the config hash
    and the insider module hash.
  - `feed_health.jsonl`, one row per poll:
    - requests;
    - filings seen against the daily index count;
    - Atom entries dropped as not Form 4;
    - parse failures;
    - 403 and 429 answers seen;
    - `late_feed` and `late_decision` counts;
    - the delay from acceptance to `first_seen`, once spec 65 has calibrated the clock.
  - `rejects.jsonl`, one row per day: counts per drop reason.
- **Verification:**
  - A new `INSIDER_CHAINED` set lives outside `journal.CHAINED` [C journal.py:58-61], so the stock and crypto
    `verify` results do not change.
  - `insider-status --verify` checks the insider chains, and `verify` prints one extra line about them.
- **Out of git:** raw filings, XML and price data stay in `.cache/insider/`.
- **Project-wide:** `state/holdout_ledger.jsonl` (6.7 step 12).

### 7.4 Losses
Every losing sale of the book goes through the loss protocol: `postmortem` learns the book "insider". In stage 1 the
expected volume is high. Roughly 40-50% of exits lose (U), at about 120 exits a year. See owner decision 9.7.

### 7.5 Dashboard line
- One KPI row and one curve, titled "insider book (experiment, log-only)":
  - equity against SPY and against M, since the seal;
  - open positions and today's events;
  - feed status: last poll, filings seen against expected, errors;
  - days into the forward record, and the next look (6.9);
  - the label "no proven edge", until the holdout passes and the forward DSR is at least 0.95.
- Rows tagged `ikpi`, `ieq` and `ipos` in the snapshot (`dashboard.py`), plus a section in `dashboard/index.html`.

### 7.6 Reports, and the problem with a 6-month probability
- **Weekly:** one line in the Saturday report.
- **Monthly:**
  - the forward E's α and its NW t, when the factor files cover the window;
  - P(Sharpe_B > Sharpe_SPY) and P(CAGR_B > CAGR_M) by the short-record method;
  - coverage and feed health.
  - These are information only. Decisions happen only at the looks of 6.9.
- **The probability on a short record:** the house bootstrap prints no range under 800 sessions
  [C config.json:293-299], and 6 months is about 126 sessions. The method used instead, and the threshold that keeps
  it honest, are fixed in 6.9 before the seal.
- **Expectation:**
  - The SE of an annual Sharpe estimate is about 1/√years, so about 1.4 over half a year.
  - At a correlation of 0.6 with SPY (U), the SE of the Sharpe difference is about √(2 x 0.4) x 1.4 ≈ 1.27.
  - P ≥ 0.8 then needs a measured Sharpe gap of about 0.84 x 1.27 ≈ 1.07, and more at p* above 0.8.
  - So the gate will most likely take well over 6 months. This is an estimate, not a measurement.

## 8. Build plan outline and effort

### 8.1 Units

Every unit follows the same gate:
- test-driven development and the unit suite, run with `python3 -m unittest discover -s tests`;
- the quant-critic, whose verdict must say that the diff touches no file the time machine loads;
- no time-machine sweep. The owner's third ruling of 2026-11-11 exempts a change that touches no listed file, and the
  time machine never loads this book. The pre-registered protocol of section 6 replaces the sweep as this book's
  evidence;
- the forward measurement that rule 4 asks of a trading rule, which is section 7 itself.

| Unit | Content | Key tests |
|---|---|---|
| U0 | Prerequisite: `AITRADER_SEC_CONTACT` (owner). The client part of spec 65 (`aitrader/sec.py`) if not yet built | the address is never in a file or log [S65 7.3]; refused hosts; no redirects |
| U1 | `form4.py`: TSV loader that reads straight from the ZIPs (links from the listing page; metadata file found by pattern; DD-MON-YYYY dates; the `FORM3_HOLDINGS_REPORTED` spelling; `AFF10B5ONE`); XML parser (the 10b5-1 element name checked against schema 5.5 first); one row format | TSV/XML parity on fixtures from one early quarter (2010q3) and one recent quarter (2026q3): a P with two owners, a 4/A, a derivative-only filing, a flagged accession; relationship strings "Director,Officer", "TenPercentOwnerOther" and "DirectorOther" read correctly; unknown XML elements ignored |
| U2 | `insider_events.py`: filters 3.1, class 3.2, events 3.3 (the merge of double reports, the backward V4 window), availability 2.3, rejects, C's pseudo-events and skip rule | synthetic histories (Jan-Jan-Jan routine; a gap year; a December trade filed in January; a joint filing with a 10% owner; the 22:00 rule; NYSE holidays from SPY sessions); `AFF10B5ONE` '1', 'true' and 'TRUE' set, '0', 'false' and blank not set; a NONE symbol drops as `not_listed`; two filings with identical (date, shares, price) count once; a joint accession counts as one owner; the V4 window ignores a filing after the second; the C skip rule; **no look-ahead**: events with entry ≤ t are identical when every filing after t is removed |
| U3a | `insider_prices.py`, part 1: the mapping rule 3.4, as-traded levels, the price check, the $5 and liquidity floors, coverage; its own Yahoo client (period1/period2 and splits; `data.py` not edited) for the ETFs, ^IRX, the forward book and the history fallback; the French files; cache in `.cache/insider/` | each dirty symbol: "(CALX)", "MOGA-MOGB", "CRDA CRDB", "FKYS-OB", "BWINB - A" and "NONE", and "BRK-B" kept whole; a renamed survivor (JEC to J through the CIK); a reused ticker resolved by date range; the TSM, PAM and LUCK cases; **as-traded:** a $16 stock with a later 4:1 split reads $16 and is kept, and an event at $0.80 with a later 1:10 reverse split reads $0.80 and is dropped by the $5 floor; a dividend payer's level equals its printed close; dollar volume does not change across a split; a series that ends mid-hold |
| P | Step P (operations): Yahoo coverage of the design events, the 200-event sample, the free Tiingo test with the owner's key, the owner's purchase of one month (4.4) | (operations, not code) |
| U3b | `insider_prices.py`, part 2: the client of the bought source (its symbol and date-range rules, unadjusted and adjusted closes, opens, volume); the full download inside the paid month | fixtures in the source's documented format; one event priced by both sources gives the same as-traded level and return within a tolerance (dv) |
| U4 | `residual.py`: OLS, Newey-West, Dimson lags and monthly compounding (numpy); also the core of backlog 5 | known answers: synthetic series with known α and AR(1) errors; **a portfolio that responds to the market one day late:** OLS without lags shows a low beta and a biased α, and the Dimson regression recovers both |
| U5 | `insider_replay.py`: E (buy-and-hold weights), B, C, T0/T1/T2, the fill f, the P2 recipe, seal and unseal with the full hash set, defect records, the audit record, p*, the ledger, the report | **bid-ask bounce:** a price that bounces between bid and ask around a flat value earns about s²/4 a day under daily equal weight and about 0 under buy-and-hold weights; the seal refuses holdout dates; a module, config or cached input changed after the seal makes `--unseal` refuse unless a defect record names it; `--unseal` refuses without an audit record; a second unseal is refused; a KILL that a fix turns into PASS gives "holdout spent", not PASS; holdout coverage prints only pass or fail; p* on a synthetic null keeps the false-pass share at or under 0.2; N counts every registered run and not C; **nothing is written to `state/trials.jsonl`** (the stock DSR keeps N = 74 [K Done 2026-11-14]) |
| U6 | `insider_book.py` and CLI (`insider-run --preopen/--close`, `insider-status`): journals, Atom polling filtered by title, the `first_seen` rule, `late_decision`, the breaker, mid-hold delisting, the forward clock key, the high-water mark, the looks | a mixed Atom feed (424B2, 4, 4/A, 144) keeps only the Form 4s; two runs in one day make one trade; a filing seen after the open enters a session later; the breaker steps; the high-water mark is not reset at re-entry; a config or module change restarts the clock and its looks without resetting K3(c) or K3(d); every equity row carries both hashes |
| U7 | dashboard rows and page section; `postmortem` book "insider"; `INSIDER_CHAINED` in `journal.py`; a section in `skills/trader/SKILL.md` (the two runs, the verdict message, the bans) | the stock and crypto `verify` outputs are unchanged; the golden stock tests stay byte-identical |
| U8 | The runs (6.7): download, event table, step P, price panel and coverage report to the owner, seal (pushed), calibration, design runs, power line, audit, unseal, verdict | (operations, not code) |

### 8.2 Files

- **New:**
  - `aitrader/form4.py`, `aitrader/insider_events.py`, `aitrader/insider_prices.py`, `aitrader/residual.py`,
    `aitrader/insider_replay.py`, `aitrader/insider_book.py`
  - `aitrader/sec.py`, if spec 65 has not built it
  - `tests/test_form4.py`, `tests/test_insider_events.py`, `tests/test_insider_prices.py`,
    `tests/test_insider_replay.py`, `tests/test_residual.py`, `tests/test_insider_book.py`
  - `tests/fixtures/insider/`
  - `state/holdout_ledger.jsonl`, written by `insider_replay`; no frozen book reads it.
- **Edited** (none of them on the time-machine list): `aitrader/__main__.py` (CLI), `aitrader/journal.py`
  (`INSIDER_CHAINED`), `aitrader/dashboard.py`, `dashboard/index.html`, `aitrader/postmortem.py`,
  `skills/trader/SKILL.md`, and `config.json` (`books.insider` only).
- **Untouched:**
  - The frozen list: `backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py`, `broker.py`, `data.py`, and
    the `risk`, `signals` and `costs` blocks of `config.json`.
  - `metrics.dsr`, `metrics.psr`, `metrics.boot_index`, `metrics.boot_stats` and `metrics.p_above` are imported
    read-only.
  - The book has its own fill function, so `broker.py` is not used.
- **The config block is invisible to the frozen books.**
  - `load_config` pops `books` before returning the stock config, and merges only `books.crypto` (plus its profile)
    for crypto [C data.py:346-361].
  - So adding `books.insider` leaves both frozen books' configs and config hashes unchanged. A test pins this.
  - The insider code reads its block straight from `config.json`, because `load_config("insider")` would need a change
    to `data.py`.
- **The old overlay stays.** The OpenInsider overlay in `cycle.py` [C cycle.py:131-153] and the
  `sec_user_agent` placeholder [C config.json:240] stay as they are until the owner decides (9.9).

### 8.3 Effort (estimates of agent work)

| Unit | Hours |
|---|---|
| U0 (the client only) | 2-3 |
| U1 | 3-4 |
| U2 | 6-8 |
| U3a | 4-6 |
| Mapping work (3.4: dirty symbols, CIK route, date ranges) | 4-8 |
| U3b | 3-4 |
| U4 | 3-4 |
| U5 | 8-11 |
| U6 | 7-9 |
| U7 | 3-4 |
| Gate rounds (critic, fixes) | 4-6 |
| **Total** | **about 47-67** |

- **Wall time on top of that:**
  - the 83 downloads: 887 MB, once [D];
  - step P: about 4 hours at 50 requests an hour, on the owner's free Tiingo key;
  - the full history panel, inside the paid month (the number of symbols is U);
  - the forward feed: about 9-10 minutes a day at 1 request a second [D].
- **Money:** one month of one source: $30 (Tiingo Power), $19.99 (EODHD) or U (Sharadar SEP), plus Tiingo's free
  tier for step P.
- **Queue:**
  - after the defects and owner items at the top of the backlog (72, 33, 44, 34, 35, 39, 40 [K header]);
  - after the contact address, the Tiingo key and the purchase;
  - in the one-builder-at-a-time order of CLAUDE.md.
- **Time to a verdict:** once the builder is free, about two weeks of sessions (an estimate), plus the owner's three
  steps.

## 9. Open decisions for the owner (one line each, with a recommendation)

Every decision that changes section 4.3, section 6 or Appendix B must be taken before the seal. A decision not taken
by then takes the recommendation as written.

1. **The SEC contact address** (already decided [K 65], still missing). It blocks both the history study and the
   feed. Rec: open it now; spec 65 needs it too.
2. **Price data for delisted names** (4.4), now taken before U3b. Rec: open a free Tiingo key yourself; step P tests
   200 events at $0; then buy exactly one month of the source that passes (Tiingo Power $30 first, else EODHD $19.99
   or Sharadar SEP, U). The 85% bar may still fail for 2009-2012.
3. **Holdout dates** (6.1). Rec: seal 2019-01-02 to 2026-09-30 as written. The alternative is a shorter, more recent
   holdout, which has less power.
4. **Holding period of the primary** (5.2). Rec: 63 sessions. The alternatives are 21 (CMP's own test) and 126 (the
   six-month drift).
5. **Officers and directors only, no 10% owners** (3.1). Rec: yes. It departs from CMP's universe on purpose, and the
   spec says so.
6. **Unseal after seeing the power line** (6.6). Rec: unseal when α_min is at most 6%/yr; otherwise wait for forward
   data.
7. **Loss protocol in stage 1.** Rec: every losing sale gets a record. When the exit was the time exit or the stop and
   every data check passed, the record is written automatically as a planned loss with its evidence; any other exit
   gets a full review. This needs his word, because the law says "every losing sale, in any book".
8. **Pre-open slot.** Rec: add the pre-open run as a step in an existing slot between 08:45 and 09:25 ET. Create a
   new scheduled task only if no such slot exists.
9. **The old OpenInsider overlay** (Appendix A). Rec: keep its rows, but stop new ones when the new feed goes live,
   because its grades would be read as this signal and they are not.
10. **The short-record method and the fixed looks** (6.9). Rev 1 left the method open until forward data would exist.
    Rec: approve before the seal as written: 5-day blocks, 2,000 draws, seed 0; looks at 6, 12, 18 and 24 months;
    p* calibrated to a 20% false-pass budget.
11. **The SPY bar on the holdout** (P2). Rec: keep it, even though small caps lagged SPY in these years (U). A book
    that cannot beat SPY is of no use for his money.
12. **Real-money gate length.** CLAUDE.md says at least 6 months; the review proposed 12 [Rv]. Rec: the fixed looks of
    6.9, the first at 6 months and the last at 24 (K3(d)).
13. **Tax rate for the after-tax line** (5.7). Rec: the rate his accountant confirms. 25% is unverified.
14. **Book size and slots.** Rec: $100,000 paper and 30 names, like the other books.
15. **The cash rate** (2.6). Rec: the French RF for history and ^IRX forward. The other option is to allow the FRED
    host and use DTB3, decided before the seal.
16. **The design-start fallback** (4.3). Rec: approve. It keeps the test alive when only 2009-2012 lack coverage, and
    it leaves the holdout untouched.

## Appendix A. The existing overlay, measured [M]

What the review called "not the Cohen-Malloy-Pomorski signal", in numbers from `state/predictions.jsonl` (rows with
`source` = "insider_cluster", read 2026-11-16):

- **Volume:** 290 rows on 6 dates (2026-11-06 to 2026-11-13), 49 symbols. Grades: 0 rows in `state/grades.jsonl`.
- **Duplicates:** the 145 rows at horizon 20 hold 63 distinct (symbol, filing date, trade date) events, and 48 of them
  were logged on more than one day.
  - Cause: the dedupe key includes the decision date [C alt.py:100].
- **Price at cycle time:** each row carries the live price at cycle time [C cycle.py:150], not the first tradable
  open after the filing.
- **Price mismatch:** 14 of the 145 rows have the logged price outside [0.67, 1.5] x the Form 4 price (TSM, PAM,
  LUCK).
- **The source:** an HTTP scrape of OpenInsider's cluster page [C alt.py:33-57].
  - Funds are not removed: KYN, a closed-end fund (my identification), is among the names.
  - 10% owners are not removed.
  - There is no routine filter.

Command (read-only):
```
grep '"insider_cluster"' state/predictions.jsonl | python3 -c "
import sys, json, collections
rows=[json.loads(l) for l in sys.stdin]; h=[r for r in rows if r['horizon']==20]
k=collections.Counter((r['symbol'],r['evidence']['filing_date'],r['evidence']['trade_date']) for r in h)
bad=[r for r in h if r['evidence']['price'] and not 0.67<=r['price']/r['evidence']['price']<=1.5]
print(len(rows), len({r['date'] for r in rows}), len(h), len(k), sum(v>1 for v in k.values()), len(bad))"
```

## Appendix B. `books.insider` (keys; values as in the sections above, all dv unless cited)

```
"insider": {
  "state_subdir": "insider",
  "data":    {"first_quarter": "2006q1", "listing_page": "<W1 url>", "max_req_per_s": 1.0,
              "history_price_source": "<the bought source, 4.4>", "forward_price_source": "yahoo",
              "rf_history": "ff5_daily_RF", "rf_forward": "^IRX"},
  "event":   {"forms": ["4"], "trans_code": "P", "acq_disp": "A",
              "relationship_any": ["OFFICER", "DIRECTOR"], "relationship_none": ["TENPERCENT"],
              "relationship_match": "substring_casefold", "aff10b5one_set": ["1", "true"],
              "owner_entity_patterns": [...], "issuer_exclude_patterns": [...],
              "plan_footnote_patterns": [...], "private_deal_footnote_patterns": [...],
              "not_listed_symbols": ["", "NONE", "N/A"], "symbol_strip_suffixes": ["-OB", "-PK", ".OB", ".PK"],
              "max_report_lag_days": 30, "min_event_value_usd": 25000, "routine_lookback_years": 3,
              "class_unit": "owner_issuer_pair", "price_sanity_band": [0.75, 1.33], "min_price": 5.0,
              "price_level": "as_traded", "min_median_dollar_volume_20d": 1000000,
              "cluster_min_insiders": 1, "cluster_window_days": 30, "cluster_window": "backward_filing_date"},
  "book":    {"starting_cash": 100000, "max_names": 30, "hold_sessions": 63, "rank": ["n_insiders", "value", "cik"],
              "stop_from_entry": -0.30, "dd_halve": -0.10, "dd_flat": -0.20, "dd_reentry_days": 20,
              "max_pct_adv": 0.01, "tax_rate_realized": 0.25},
  "costs":   {"bps_by_adv": [[50000000, 10], [10000000, 25], [0, 50]], "unpriced_bps": 50, "stress_mult": 2.0},
  "fill":    {"sample_n": 200, "sample_seed": 0, "min_priced": 100, "cluster": "entry_month", "draws": 2000,
              "seed": 0, "quantile": 0.025, "cap": 0.0, "uncalibrated_shortfall": -0.15},
  "control": {"offset_sessions": 252, "exclusion_sessions": 63, "t_max": 2.0},
  "eval":    {"design": ["2009-01-02", "2018-12-31"], "design_latest_start": "2013-01-02",
              "holdout": ["2019-01-02", "2026-09-30"], "split": "2022-11-01",
              "dimson_lags": 2, "nw_lags": 10, "monthly_nw_lags": 3, "t_design": 1.5, "t_holdout": 2.0,
              "p_min": 0.8, "dsr_min": 0.95, "coverage_min": 0.85,
              "runs": ["V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7"], "max_defect_rounds": 2,
              "delist_stress": -0.30, "audit_events": 20, "audit_pseudo_events": 10, "audit_seed": 0},
  "forward": {"looks_months": [6, 12, 18, 24], "short_boot": {"block_days": 5, "draws": 2000, "seed": 0},
              "null": {"paths": 1000, "block_days": 20, "seed": 1, "max_false_pass": 0.2,
                       "p_grid": [0.80, 0.99, 0.01]},
              "k3b_p_min": 0.5, "kill_dd_from_hwm": -0.25, "stage3_deadline_months": 24,
              "factor_wait_days": 90, "pause_outage_sessions": 10, "late_decision_cutoff_et": "09:30"}
}
```

## Review log (round 1, 2026-11-16)

Two reviewers read rev 1: a quant reviewer (Q) and a data reviewer (D). Every finding and what rev 2 did with it.

**Blocking**

| # | Finding | Handling |
|---|---|---|
| Q1 | Look-ahead in price levels: adjusted closes carry later splits and dividends into the $5 floor, share counts and dollar volume | Done. 3.1 step 9, 3.4 "As-traded levels", 4.1, 5.3 and 5.6: every level uses the as-traded close; adjusted series only for returns. U3a tests the $0.80 / 1:10 reverse-split case (dropped), a $16 / 4:1 split (kept) and a dividend payer |
| Q2 | R1 regresses daily returns with no lagged factors, so α absorbs missed beta; the power table is monthly while the test is daily | Done. R1 takes lags 1 and 2 of every factor (Dimson), and so do R2, R2f, P4, P5, C, E − C and the forward α. Daily Dimson was chosen over the monthly option: more observations for 15 betas, and the same series as E. The CMP-style monthly regression is reported. 6.6 shows the daily and monthly t agree under independent residuals, and α_min now comes from the measured Newey-West error. U4 tests a portfolio that responds a day late |
| Q3 | E re-sets every position to equal weight each day, which earns bid-ask bounce | Done. Buy-and-hold weights with exact formulas (6.4). U5 has a bounce known-answer test |
| Q4 | Survivorship: filling unpriced events with IWM is not conservative | Done. The fill f is calibrated on the 200-event sample from a delisting-inclusive source: f = min(0, lower 95% bound of the mean hold return minus IWM), cluster bootstrap by entry month (4.3). The cap at 0 is the writer's addition. If f cannot be calibrated, bar P6 (IWM − 15%) applies. The limits of the proxy are stated, and T2 stays reported |
| Q5 | No negative control; backlog 3's placebo gate was dropped silently | Done. Control C (6.4) through the identical pipeline: same issuer 252 sessions earlier, skipped near any code-P row. G0 requires C's design t < 2 (else not measurable, holdout sealed); P7 requires C's holdout t < 2 (writer's addition) and α(E − C) > 0. Kept one-sided as proposed, with the reason (the contrarian pre-purchase decline can make C negative). C's survival bias leans the safe way, and its shorter holdout window is stated |
| Q6 | The seal pins only section 6 and the config, not the code or the inputs | Done (6.7 step 5): the whole file, every loaded `aitrader` module, `books.insider` and every cached input are hashed. `--unseal` refuses on any mismatch unless a critic-agreed defect record names each changed file (N + 1). The seal record is committed and pushed before the first design run |
| Q7 | A post-unseal defect re-run can turn KILL into PASS | Done (6.8): the one-way rule. A fix may only turn PASS into KILL; KILL turned PASS means "holdout spent", and promotion needs the forward-only bars F (6.9). A written audit runs before the unseal whatever the outcome (6.7 step 9) |
| Q8 | The forward kill can be gamed: K3(b) cannot be computed under the 800-day floor, K3(c)'s peak resets, no time limit | Done (6.8, 6.9): the short-record method is named (5-day blocks, 2,000 draws, seed 0); K3(c) uses the all-time high-water mark since the seal, never reset; K3(d) kills at 24 months without stage 3. Writer's addition: a clock restart resets neither (c) nor (d) |
| Q9 | Stage 3 checked every month is optional stopping; M is matched on dollars, not beta | Done (6.9): fixed looks at 6, 12, 18 and 24 months; p* calibrated so a zero-edge null passes the whole schedule at most 20% of the time, from design B shifted to SPY's Sharpe; the forward E's α must be > 0 at the passing look |
| D1 | Yahoo cannot reach 85%; "build on Yahoo first" ends in "not measurable" | Done. 4.4 rewritten with the measured 44.5%, 46.4% and 61.7%. The decision to buy a delisting-inclusive source comes before U3b; U3 is split into U3a (Yahoo, mapping, levels) and U3b (the bought source). The 85% gate stays |
| D2 | The cost of delisted prices is understated; the free-tier test cannot run as written | Done. Stooq dropped; the EODHD free-tier test dropped (1 year of history); Norgate marked not viable on Linux; the owner opens a free Tiingo key and step P tests 200 events at $0; then one month of the source that passes. Said plainly that 2009-2012 may stay under 85%. Mapping work adds 4-8 h in 8.3. Writer's addition: the design-start fallback (4.3), for owner decision 9.16 |
| D3 | No rule for matching a Form 4 event to a price series | Done (3.4): normalize, candidates in order (filed, first token, CIK's current ticker, the source's symbol history), date range for reused tickers, the price check as the guard on every match; `company_tickers.json` for price lookup only. U3a tests every dirty case named and JEC to J |

**Non-blocking**

| # | Finding | Handling |
|---|---|---|
| Q-n1 | P2 cannot come out of `boot_rows`; P5's test and `sr_trials_std` units unstated | Done (6.4): the recipe with `boot_index`, `boot_stats` and `p_above`; P5 is a point estimate; `sr_trials_std` is daily |
| Q-n2 | "M's Sharpe equals SPY's" holds only for constant g; stage 3's metric for M unnamed | Done: wording corrected; M is compared on CAGR in P2 and stage 3 |
| Q-n3 | The forward clock is keyed only on the config | Done (6.9, 7.3): config hash plus insider module hashes, both in every equity row |
| Q-n4 | V4's 30-day window direction | Done (3.3): backward on `FILING_DATE`; entry after the second owner's filing |
| Q-n5 | Double reporting inflates `n_insiders` | Done (3.3): identical rows merged before counting. Writer's addition: a joint accession counts as one owner |
| Q-n6 | 10b5-1 checkbox in the forward XML but maybe not the history TSV | Done with D-n2: the TSV has the flag from 2023, so both paths apply it; separate reject reason |
| Q-n7 | The kill scope is too narrow | Done (6.8): every Form 4 purchase hypothesis on 2006-2026Q3 data is banned after a kill |
| Q-n8 | Single episodes (March 2009, March 2020) could carry the result | Done (6.5), reported: α without those windows and the leave-one-year-out minimum |
| Q-n9 | Holdout coverage printed before the seal | Done (4.3, 6.7): pass or fail only until the unseal. The review's own 2019q3 coverage sample is disclosed in 6.2 |
| Q-n10 | Opens must be on the same total-return basis as closes | Done (3.4 "Returns", 6.4) |
| Q-n11 | No sector cap and no vol target | Noted in 5.4 (SIC codes from EDGAR for a later version); no change in v1, accepted for a log-only book |
| Q-n12 | Multiplicity across the project | Done (6.7 step 12): `state/holdout_ledger.jsonl`; how a later spec adjusts for the count is left to that spec |
| Q-n13 | The French files lag, so the forward R1 may lack factors | Done (6.9): wait up to 90 days, then R2f. R2f drops Mom because Mom is a French file too |
| D-n1 | Blank or NONE symbols counted as unpriced; unpriced events skip the liquidity floor | Done: `not_listed` drop (3.1 step 8); the bought source must carry volume (4.4); coverage counts unpriced events against floor-passing priced events, and the rest is reported (4.3) |
| D-n2 | `AFF10B5ONE` exists in SUBMISSION from 2023, per accession | Done (2.1, 2.2, 3.1 step 5): it drops the whole accession, with '1' and 'true' normalized; rev 1's plan task for this field is removed (U1 still checks the XML element name) |
| D-n3 | Format details: relationship strings, metadata file name, column spelling, dates | Done (2.1, U1): case-insensitive substring matching, metadata by pattern, fixtures from 2010q3 and 2026q3 |
| D-n4 | Sizes and volumes measured | Done (2.1, 2.2, 8.3); TSVs read straight from the ZIPs |
| D-n5 | The type=4 Atom feed returns 424B2 entries | Done (2.2, 7.2, U6): filter by title, page back, the daily index stays the complete list; mixed-feed test |
| D-n6 | Timestamps and the 22:00 rule check out | No change needed; [W3] marked as confirmed (2.3) |
| D-n7 | French files end 2026-09-30; FRED did not answer | Done (2.6): the French RF is the history cash rate, ^IRX forward; DTB3 only if the FRED host is allowed before the seal (9.15); the regression window is bounded by the factors' lag |
| D-n8 | SEC access still gated | No change beyond recording the second 403 (2.5); U0 stays the hard first step |
