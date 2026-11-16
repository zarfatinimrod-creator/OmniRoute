# Insider purchases book, log-only - design spec (2026-11-16, rev 1)

Status: a design for the owner's review. Nothing here is built or has been run, and no trial is registered. It
follows the owner's decision of 2026-11-16: the stock and crypto parameters are frozen, and the improvement effort
moves to finding a measured edge, starting with opportunistic insider purchases. The sources are CLAUDE.md hard
rule 1, `research/2026-11-16-real-money-review.md` fix 4, and backlog items 3, 5 and 6. Paper money only.

This spec was written before this project had computed any insider return for any period. Section 6 is the
pre-registration: its text is hashed into the seal record (6.7) before the first replay runs, and any later edit to
section 6 makes a new experiment. The book touches none of the frozen books' files (8.2).

## Evidence tags

- [C file:line]: code under `ai-trader/` at commit fec70554, read 2026-11-16.
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
- [M]: measured for this spec from files in this repo (command in Appendix A).
- (U): unverified, meaning not checked against its primary source.
- (dv): design value. The number was chosen here with no evidence behind its exact size. This spec fixes it, and it
  is not tuned.

## 1. Hypothesis and the evidence for it

### 1.1 Hypotheses (written before any look)

**H1 (the edge).** Take every US common stock bought at the first regular-session open after the filing date of an
SEC Form 4 that reports:
- an open-market purchase (non-derivative table, code P, acquired),
- by an individual officer or director,
- who is classified as opportunistic by the Cohen-Malloy-Pomorski rule (3.2).

Hold each one for 63 trading days. Over the sealed holdout (2019-01-02 to 2026-09-30), the equal-weight event
portfolio of these stocks has a positive abnormal return after costs: the intercept of the regression in 6.4 is above
0 with a Newey-West t of at least 2. H0: the intercept is at most 0.

**H2 (the money).** A paper book with a limited number of slots, built from the same events (section 5), beats SPY's
Sharpe and the return of an exposure-matched SPY/T-bill mix. Each comparison needs a bootstrap probability of at
least 0.8 on the same holdout.

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
- **Survivorship.** "26% of insider-event tickers returned 404" on Yahoo [SS line 72] (the researcher's own test, U).
  See section 4.
- **Power (6.6).** A real effect at its decayed size can still give t < 2 over 7.75 years.
- **Prior.** My guess, not a measurement: the holdout passes every bar with a probability well under one half. The
  kill criterion (6.8) is written so that this outcome ends the work cleanly and cheaply.

## 2. Data

### 2.1 History: the SEC Insider Transactions Data Sets [W1, W2]

- **What they are:** flat files "extracted from EDGAR Ownership XML submissions" of Forms 3, 3/A, 4, 4/A, 5 and 5/A,
  "provided as-filed". They "may contain redundancies, inconsistencies, and discrepancies relative to prior
  submissions" [W2 sections 1, 3].
- **Coverage:** January 2006 to September 2026 [W1]. That is 83 quarterly ZIPs, 2006q1 to 2026q3.
- **Cadence:** published quarterly. "Data contained in documents filed after 5:30pm EST on the last business day of
  the quarter will be included in the next quarterly posting" [W2 section 1]. How long after quarter end a file
  appears is not stated (U). These files are for history only; the forward book reads live filings (2.2).
- **Where they are:** recent quarters sit under `/files/datastandardsinnovation/data/insider-transactions-data-sets/`
  and older ones under `/files/structureddata/data/insider-transactions-data-sets/` [W1]. The loader takes each
  quarter's link from the listing page and never builds a URL itself.
- **Format:** eight tab-delimited UTF-8 files per quarter, plus a W3C tabular-data metadata file [W2 sections 3-4]:
  SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS, NONDERIV_HOLDING, DERIV_TRANS, DERIV_HOLDING, FOOTNOTES and
  OWNER_SIGNATURE.
- **Fields used** (exact names from [W2 section 5]):
  - SUBMISSION:
    - `ACCESSION_NUMBER` (the key)
    - `FILING_DATE` ("Filing date with the Commission", a date with no time)
    - `PERIOD_OF_REPORT`
    - `DATE_OF_ORIG_SUB` (the original filing's date, for amendments)
    - `DOCUMENT_TYPE` (3, 3/A, 4, 4/A, 5 or 5/A)
    - `ISSUERCIK`, `ISSUERNAME`, `ISSUERTRADINGSYMBOL`
    - `NOT_SUBJECT_SEC16`
  - REPORTINGOWNER:
    - `ACCESSION_NUMBER` + `RPTOWNERCIK` (the key)
    - `RPTOWNERNAME`
    - `RPTOWNER_RELATIONSHIP`: "OFFICER, DIRECTOR, TENPERCENTOWNER, OTHER"
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
- **Not in the data set** (from the field list):
  - **No time of day.** There is no acceptance time anywhere; only `FILING_DATE`.
  - **No 10b5-1 field.**
    - The readme PDF is dated 2022-08-23 by its metadata, which is before the Form 4 Rule 10b5-1 checkbox.
    - Whether later files added a column is unknown (U). Plan task 1 reads the metadata file of one 2024+ quarter to
      find out.
  - **No SIC code and no exchange.**
  - **No link from a transaction to one owner.** Transactions are keyed by accession and owners by accession +
    owner CIK, so when a filing has several owners a transaction row cannot be tied to any one of them.
- **Size of the 83 ZIPs:** not measured (U). They are kept under `.cache/insider/`, which is gitignored
  [C .gitignore:1], and never under `state/`.
- **Terms and cost:**
  - The page says "we cannot guarantee the accuracy of the data sets" [W1].
  - SEC filings are public records; their copyright status was not checked (U).
  - Access follows the SEC's fair-access rules (2.5). Cost: $0.

### 2.2 Forward: live Form 4 filings

- **Sources**, the same family spec 65 uses [S65 2.1]:
  - (a) The daily form index of the previous business day: the complete list of Form 4 accessions. When it is
    published is unverified (U).
  - (b) The current-filings Atom feed for type 4: the filings of the current day before the open. This is the address
    `data.sec_recent_form4` already builds; that function has no caller [C data.py:304-321].
  - (c) Per filing: the ownership XML.
- **What the XML adds:**
  - It carries the fields of 2.1.
  - Since 2023 it also carries the Form 4 checkbox for transactions under a Rule 10b5-1(c) plan. The element's name
    is unverified (U).
  - The current specification is "Ownership (Forms 3, 4, 5)" version 5.5 of 2026-03-18, which adds new elements
    [W4]. The parser ignores elements it does not know.
- **Acceptance time:** read from the filing index, forward only.
  - Spec 65 found that the clock of the stamp (New York or UTC) is not known [S65 4.4].
  - This book never uses the stamp for a decision (2.3), only for a latency figure. That figure is printed only
    after spec 65 calibrates the clock.
- **One row format** (`form4.py`) serves both the bulk TSV and the XML, so the history replay and the forward book
  run the same event code. A parity test checks that on fixture filings the XML path and the TSV path give the same
  events.
- **Volume:** the number of Form 4s per business day is not measured here (U). The build counts it from the
  quarterly files before the feed is sized (8.1, U1). At one request per filing and at most 1 request a second
  (2.5), 1,000 filings take about 17 minutes.

### 2.3 Point-in-time availability: the one rule

- Availability is never decided by the transaction date.
- **The law** [W3]:
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
- **Filters:** liquidity and price filters use bars up to the close before the entry session.
- **Sessions:** the history takes NYSE sessions from SPY's daily bars. `config.json` `calendar` lists only 2026 and
  2027, and its note says years not listed count as closed [C config.json calendar].

### 2.4 Known gaps and how each is handled

| Gap | Handling |
|---|---|
| Amendments (4/A) restate earlier filings "as filed" | Events come only from original Forms 4 (3.1 step 1). 4/A rows are counted in the rejects. What the market saw at the original filing date is what the replay uses |
| Late filers | Allowed, dated by the filing date: the information arrives when filed. Report lag over 30 days is dropped as a data-sanity rule (3.1 step 6). `TRANS_TIMELINESS` is self-reported, so the lag is computed from the dates |
| Derivative vs non-derivative tables | Only NONDERIV_TRANS makes events. DERIV_TRANS is ignored (option and warrant purchases are not stock purchases) |
| Several owners on one accession | Transactions cannot be tied to one owner, so the accession is used only if every owner passes (3.1 step 3) |
| Code P includes private purchases | A footnote filter (3.1 step 5) plus the price sanity check (3.4) |
| The symbol is self-reported | Used as filed. A price mismatch makes the event unpriced (4.3), never dropped |
| Tickers reused at the price source | The price sanity check (3.4) |
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
    refused with 403 "Request Rate Threshold Exceeded" and was not retried.
  - So the contact address blocks the history study too, not only the live feed.
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
- **Factors:** Ken French daily factors. "Fama/French 3 Factors [Daily]", "Fama/French 5 Factors (2x3) [Daily]",
  "Momentum Factor (Mom) [Daily]" and "Short-Term Reversal Factor (ST Rev) [Daily]" are all listed [W5].
  - The page says "Copyright Eugene F. Fama and Kenneth R. French" and shows no separate terms [W5].
  - The factors are built from CRSP, so they include delisted firms.
  - Their publication lag is U.
- **T-bill:** FRED DTB3, free with no key ([DB] section 2 for FRED).
- **SPY, IWM and RSP:** total return from the Yahoo adjusted close.

### 2.7 Pages and documents read for this spec (2026-11-16)

- [W1] `https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets`: coverage, cadence, format,
  disclaimer, file paths.
- [W2] `https://www.sec.gov/files/insider_transactions_readme.pdf`: 7 pages, created 2022-08-23. Its sha256 begins
  eaa4c0526b2ec92f. Text extracted locally.
- [W3] 17 CFR 232.13(a), read on law.cornell.edu. ecfr.gov redirected to a block page, and that was not worked
  around.
- [W4] `https://www.sec.gov/submit-filings/technical-specifications`: the Ownership XML specification v5.5,
  2026-03-18. No note on the 10b5-1 element was seen in the part read.
- [W5] `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html`
- [W6] `https://eodhd.com/pricing` (4.4)
- [P] `https://www.nber.org/papers/w16454.pdf`

## 3. Event definition (exact)

### 3.1 Rows kept

The filters run in this order, and every drop is counted by its reason (7.3, `rejects.jsonl`).

1. **Form:** `DOCUMENT_TYPE` = "4". Originals only.
2. **Transaction:**
   - Keep NONDERIV_TRANS rows with `TRANS_CODE` = "P" and `TRANS_ACQUIRED_DISP_CD` = "A".
   - Drop a row with `EQUITY_SWAP_INVOLVED` true.
   - DERIV_TRANS makes no events.
3. **Owners:** every reporting owner on the accession must pass all three tests.
   - An individual: `RPTOWNERNAME` matches none of the entity patterns (dv: LLC, L.P., LP, FUND, CAPITAL, PARTNERS,
     HOLDINGS, MANAGEMENT, ADVISORS, INC, CORP, TRUST). A trust here is an owner, not an issuer.
   - `RPTOWNER_RELATIONSHIP` contains OFFICER or DIRECTOR.
   - `RPTOWNER_RELATIONSHIP` does not contain TENPERCENTOWNER.

   If any owner fails, the accession is dropped: a joint filing with a fund or a 10% holder counts as the fund's
   trade. OTHER on its own also drops.
4. **Section 16:** `NOT_SUBJECT_SEC16` = 1 drops.
5. **Plans and private deals.** The same patterns apply in every year (footnotes exist from 2006), so the design and
   holdout periods use one rule. The checkbox only adds recall after 2023. A row is dropped when any of these holds:
   - its 10b5-1 checkbox is set, where the XML has one;
   - a footnote of the row or of the accession matches a plan pattern (dv: "10b5-1", "10b5 1", "trading plan");
   - a footnote matches a private-deal pattern (dv: "private placement", "subscription agreement", "registered
     direct", "rights offering", "public offering", "underwritten").
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
9. **Price:** at least $5 (dv).
   - Priced events use the close of the session before entry.
   - Unpriced events use the Form 4's own `TRANS_PRICEPERSHARE` (4.3).

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
- **Fields of an event:** `n_insiders` (distinct owners), `value` (the sum), first and last `TRANS_DATE`, the
  accessions, and the symbol as filed.
- **Minimum size:** the event's value is at least $25,000 (dv). No evidence-based default exists ([DB] "Insider
  filter"). Variant V5 tests $100,000.
- **Clustering:** none in the primary, as in CMP. Variant V4 requires at least 2 distinct opportunistic insiders on
  the same issuer within 30 calendar days.
- **Double reporting:** the same purchase reported by two owners in separate filings (a shared indirect holding)
  raises `value`. `n_insiders` counts distinct owners only. The build reports how often two filings on one
  issuer-day carry identical (date, shares, price).

### 3.4 Symbol and price sanity

- **Symbol:** `ISSUERTRADINGSYMBOL` as filed, which is point-in-time by construction.
  - It is upper-cased, with "." and "/" turned into "-".
  - A blank, "NONE" or "N/A" symbol makes the event unpriced.
- **Never today's ticker file.** `company_tickers.json` is never used for history: it maps today's tickers and would
  leak renames and survival.
- **Price check:**
  - Compare the Form 4's `TRANS_PRICEPERSHARE` with the price source's close on `TRANS_DATE`, with splits undone (or
    the nearest earlier session).
  - At least one row of the event must have a ratio in [0.75, 1.33] (dv).
  - Otherwise the event is a `price_mismatch`: the series belongs to another company (a reused ticker), another share
    class or an ADR ratio, or the units are wrong.
  - A mismatched event becomes unpriced (4.3). It is not dropped, so a bad mapping cannot select survivors.
- **Why:** in the current overlay, 14 of 145 rows sit outside [0.67, 1.5] [M]:
  - TSM: 2.9-3.2x
  - PAM: about 5.3x
  - LUCK: about 0.2x

## 4. Universe and survivorship

### 4.1 Universe
- Every issuer with an event (3.3). There is no index membership and no hand-picked list.
- **Liquidity floor:** a 20-session median dollar volume of at least $1,000,000 before entry (dv).
  - It applies to the book (section 5) and to priced events in the event portfolio.
  - Unpriced events cannot be checked against it (4.3).

### 4.2 The problem
Yahoo serves today's tickers, which causes three problems:
- A delisted name answers 404. An earlier test, not verified, found this for 26% of insider-event tickers
  [SS line 72].
- A reused ticker returns another company's history.
- Its terms allow personal use only [DB] section 2.

The forward book has no survivorship bias, since it trades at the time. The history does.

### 4.3 Treatment, fixed before coverage is known

| Case | Primary (T1) | Upper bound (T0, reported) | Stress (T2, reported) |
|---|---|---|---|
| Priced event: passes 3.4 and has its entry open | real prices | real prices | real prices |
| Unpriced event: 404, `price_mismatch`, blank symbol, or a series that starts after entry | earns IWM's total return over its hold window, minus costs at the highest bucket: zero alpha, a dilution | dropped | IWM − 30% over the hold |
| The series ends during the hold (delisted or acquired) | exit at the last close | exit at the last close | last close − 30% |

- **The −30%:** Shumway's (1997) average delisting return for performance delistings, from memory (U). It is an
  extreme bound and never a pass bar.
- **The book under T1:** an unpriced event is taken or skipped by the same ranking as any other event (5.3). So the
  book's picks never depend on whether a name survives at Yahoo today.
- **Coverage** = priced events / eligible events (after 3.1-3.3).
  - It must be at least 85% (dv) in the design period and in the holdout.
  - It is computed before any return is computed (6.7 step 3).
  - Below 85%, the test is "not measurable with this data": the owner makes the data decision (9.2) and the holdout
    stays sealed. This is not a kill.

### 4.4 Ways to raise coverage (owner decision 9.2)

| Source | Cost | Delisted names | Notes |
|---|---|---|---|
| Yahoo only | $0 | no | personal use; reused tickers |
| Stooq | $0 (U) | U | not checked |
| EODHD "Historian" (EOD All-World) | $19.99/month, $16.58/month billed yearly [W6] | not stated on the pricing page (U) | terms not read; check coverage on its free tier or with support first |
| Norgate Data | U (the pricing page I tried answered 404) | known for delisted US history (U) | not checked |
| Nasdaq Data Link, Sharadar SEP | U | U | not checked |
| CRSP through WRDS | institutional | yes | the academic standard; not open to an individual (U) |

Recommendation:
1. Build on Yahoo and measure coverage.
2. If coverage is below 85%, test one paid source on a sample of 200 unpriced design events (a free tier if one
   exists).
3. Buy one month only if that source lifts coverage above 85%.

## 5. Portfolio rules (the book)

Every number below lives in `config.json` `books.insider` (Appendix B). The numbers are dv unless a source is given.

### 5.1 Entry
- At the open of the entry session (2.3). Fill = open x (1 + cost per side).
- The open is Yahoo's daily open in both history and forward. The forward book also records the 09:30 one-minute bar
  as a cross-check.

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
- At most 30 names. Each new position is 1/30 of current equity, in whole shares. The rest stays in T-bills.
- **More events than free slots on a day:** rank by `n_insiders` (descending), then `value` (descending), then
  `ISSUERCIK` (ascending). No ranking uses returns. Skipped events are logged.

### 5.4 Limits
- **Position size:** at most 1% of the 20-session median dollar volume at entry.
  - At $3,333 positions and the $1M floor this does not bind.
  - It starts to bind if the book grows past about $300,000.
- **Sectors:** no sector cap in v1, because the data have no sector field (2.1). Known gap.

### 5.5 Exits planned before entry (Basic law, item 2)
- **Time exit:** 5.2.
- **Catastrophe stop:** when a close is at or below entry x (1 − 0.30), exit at the next open. The law asks for a
  planned limit on every loss. No evidence exists for any stop on this signal, so variant V6 measures the book
  without it.
- **Book breaker,** the same three settings as the stock book:
  - at −10% from the peak, new positions are half size;
  - at −20%, everything is sold at the next open;
  - after 20 sessions, re-entry with the peak reset.

### 5.6 Costs
- Per side, by 20-session median dollar volume:

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
- Cash earns DTB3, day by day.

### 5.7 Taxes
- The report shows an after-tax line at 25% of net realized gains per calendar year (the Israeli rate, U [Rv]).
- That line feeds no bar until the owner gives the real rate.

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
  - events whose entry session falls from 2009-01-02 to 2018-12-31;
  - daily returns over the same dates;
  - positions still open on 2018-12-31 are marked at that close and closed.
- **Holdout (sealed):**
  - events whose entry falls from 2019-01-02 to 2026-09-30;
  - daily returns over the same dates, about 1,950 sessions (an estimate);
  - positions open at the end are marked at the last close;
  - the holdout portfolio starts empty, with no position carried over from the design period.
- **Forward:** from the seal (6.7 step 4) onward. See section 7.

### 6.2 What has been seen already
- Nobody in this project has computed an insider return for any period.
- Earlier looks, disclosed here:
  - the roadmap's unverified claim about 2020-2025 [RM line 69];
  - the literature, whose samples end in 2007;
  - general knowledge of index returns. Benchmarks are not the test, but one fact matters to P2: small caps lagged
    SPY over much of 2019-2026 (U; checked from prices before the unseal, a look at benchmarks, not at the book).
- The 290 overlay rows of 2026-11-06 to 2026-11-13 [M] come after the holdout and have no grades.

### 6.3 Runs allowed (all count in N for the Deflated Sharpe)
All eight runs are listed in the seal record before the first one starts:

| Run | What changes from V0 |
|---|---|
| V0 | nothing: the primary (sections 3-5) |
| V1 | hold 21 sessions |
| V2 | hold 126 sessions |
| V3 | unclassified insiders count as opportunistic |
| V4 | cluster: at least 2 opportunistic insiders within 30 days |
| V5 | minimum event value $100,000 |
| V6 | no per-position stop (book only) |
| V7 | every officer/director purchase, of any class (shows what the CMP filter adds) |

- **Each run happens once,** on the design period only.
- **Defect re-runs:**
  - Allowed only for a defect: a bug that the quant-critic agrees is a bug, not a rule change.
  - The affected runs are repeated, and every repeat adds to N.
  - At most 2 rounds; more needs the owner's word.
- **N for the holdout DSR:** the number of registered design runs (8 or more) + 1.
- **Only V0 is ever unsealed.** A design variant that looks better changes nothing. It can come back only as a new
  written hypothesis, tested on data after 2026-09-30.

### 6.4 Measurements

- **E, the event portfolio (the edge):**
  - Every eligible event, priced or T1, holds one unit from its entry open to its exit open.
  - Each position's daily segment is: open to close on the entry day, close to close in between, close to open on
    the exit day.
  - The daily return is the equal-weight mean of the active segments, net of costs on entry and exit days. Days with
    no position earn DTB3.
  - No stop, no slots and no breaker: E measures the signal, not the book.
- **B, the book (the money):** section 5, exactly.
- **R1, the residual-edge gate (backlog 5) for this book:**
  - Daily regression: (E − rf) = α + b·[Mkt−RF, SMB, HML, Mom, ST Rev] + ε, by OLS.
  - t is Newey-West with 10 lags (dv). α is annualized x 252.
  - It covers backlog 5's size, equal-weight and momentum terms. It adds value and short-term reversal, because
    "insiders are contrarian, buying after low past returns" [P p. 13].
- **R2, an ETF cross-check (reported, not a bar):** the same regression on SPY−rf, RSP−SPY, IWM−SPY and Mom.
- **Sharpe and CAGR:**
  - Both use returns in excess of DTB3.
  - The comparison is a paired block bootstrap with the repo's settings (20-day blocks, 2,000 draws, seed 0
    [C config.json:293]).
  - It runs through `metrics.boot_rows` [C metrics.py:121], imported and not edited.
- **Benchmarks:**
  - SPY.
  - M, the exposure-matched mix: M_t = g_t x SPY + (1 − g_t) x T-bill, where g_t is the book's invested fraction at
    the previous close. M's Sharpe equals SPY's by construction [Rv], so M is compared on CAGR.
  - IWM, RSP and an IWM/T-bill mix, reported only.
- **DSR:** `metrics.dsr` [C metrics.py:48] on B's holdout daily excess returns, with N from 6.3. The trial Sharpe
  spread comes from the registered design runs.

### 6.5 Bars

**Design gate G0** (before the unseal), on V0 over 2009-2018:
- E's R1 α > 0 with NW t ≥ 1.5 (dv);
- coverage ≥ 85%.

**Holdout PASS.** All five must hold, on V0, under T1, at base costs:

| Bar | Book | Test |
|---|---|---|
| P1 | E | R1 α > 0 with NW t ≥ 2.0 |
| P2 | B | P(Sharpe_B > Sharpe_SPY) ≥ 0.8 **and** P(CAGR_B > CAGR_M) ≥ 0.8 |
| P3 | B | DSR ≥ 0.95 |
| P4 | E | R1 α point estimate > 0 in each half (2019-01-02 to 2022-10-31; 2022-11-01 to 2026-09-30) |
| P5 | E | R1 α > 0 at 2x costs |

- **Why two tests are fine:** P1 tests the edge on E, which has the most power. P2 tests the money on B, which is
  what would be traded. Requiring both together lowers the false-pass rate, so this is not multiple testing that
  needs a correction.
- **Reported, not bars:**
  - T0 and T2;
  - R2;
  - the IWM, RSP and IWM-mix lines;
  - drawdown and turnover;
  - counts by reject reason and by year;
  - the event-time return curve from day 1 to day 126, on the design period only.

### 6.6 Power (estimates before any look)

- **Formula:** t ≈ (α / σ_ε) x √T, with monthly α and monthly residual volatility σ_ε. The holdout has T = 93
  months, so √T = 9.64.
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
- **Power line before the unseal:**
  - After the design runs, the build prints the smallest annual α the holdout can show at t = 2, from the design
    σ_ε: α_min = 2 σ_ε / √93 per month.
  - The owner sees this line before the unseal (9.6). He may choose to wait for more forward data instead.
    Waiting changes nothing else.

### 6.7 Order of operations and the seal

1. The contact address exists. Units U0-U5 are built (section 8).
2. **Event table:** built for 2006 to 2026Q3. It prints:
   - counts per year;
   - drops per reason;
   - the share of each class.

   No price is touched in this step.
3. **Price panel:** built, with coverage per period.
   - No return is computed in this step.
   - The return code refuses any date on or after 2019-01-02 while no unseal record exists.
4. **Seal.** `insider-replay --seal` writes one record to `state/insider/trials.jsonl` (hash-chained). The record
   holds:
   - the sha256 of this file's section 6 (the text between its heading and section 7's) and of `books.insider`, at
     the named commit;
   - the 8 declared runs;
   - the input hashes of the event table and the price panel;
   - the coverage.

   The seal is written once. A section 6 or config that changes after the seal is a new experiment. The forward
   clock (section 7) starts here.
5. **Design runs:** at most 8, each registered with its result. Then the design report and G0. If G0 fails: K1.
6. **Power line** (6.6). The owner decides whether to unseal now.
7. **Unseal**, once only. `insider-replay --unseal`:
   - checks the seal hashes against the files;
   - writes the unseal record;
   - runs V0 on the holdout;
   - writes the result and the verdict (PASS or KILL) to the same chain;
   - prints the report.

   A second unseal is refused.
8. **Review and verdict:** the quant-critic reviews the run (rule 4). The owner gets the verdict in one message.

### 6.8 The KILL criterion

The experiment ends, and backlog item 3 closes as "no measured edge", on any one of these:

- **K1:** G0 fails. The holdout is never opened.
- **K2:** any of P1-P5 fails on the holdout.
- **K3, forward (section 7):**
  - (a) After 6 months, the forward E's R1 α point estimate is below 0 **and** B's return is below M's.
  - (b) After 12 months, P(Sharpe_B > Sharpe_SPY) < 0.5.
  - (c) At any time, B falls 25% below its peak (dv). New entries stop and the loss protocol reviews the drawdown.
    It is a kill unless the review finds a defect.

**After a kill:**
- no new variant on the 2006-2026Q3 data;
- no new holdout cut from those years for opportunistic insider purchases;
- the book and the feed stop, unless the owner keeps the feed for spec 65's purpose;
- one line in `lessons.md` with the numbers;
- the book's rows leave the dashboard.

Re-opening needs a new written hypothesis and data from after 2026-09-30.

**Not a kill (the clock waits):**
- coverage below 85% (the data decision, 4.3);
- a missing contact address;
- a feed outage. The forward clock pauses when the feed is down more than 10 sessions in a calendar month (dv).

**A defect found after the verdict:** the run is repeated once with the fix. Both results are kept, N grows, and the
quant-critic must agree that it was a defect and not a rule change.

## 7. Forward paper book

### 7.1 Stages

- **Stage 1, log-only.**
  - Starts at the seal (6.7 step 4), when the feed exists, so the forward record builds while the history study is
    still running.
  - The book runs on paper from the frozen config. No one acts on it.
  - The owner gets only the weekly and monthly lines (7.6).
  - On K1 or K2 it stops.
- **Stage 2, after a holdout PASS.**
  - The same book, now named in the daily summary.
  - Veto and shrink are allowed, with the no-veto shadow (5.8).
- **Stage 3, the real-money gate (CLAUDE.md hard rule 1).**
  - Conditions: at least 6 months forward on one frozen config hash, after real costs (the owner's broker fees,
    measured) and tax.
  - The book must beat SPY with P(Sharpe) ≥ 0.8 and beat the exposure-matched SPY/T-bill mix.
  - Only then is real money proposed, and it starts with a small slice.
  - Any change to `books.insider` restarts the clock.

### 7.2 Daily operation: two runs, both idempotent

- **Close slot (the existing 16:22 ET slot):**
  - poll the day's filings so far (Atom pages, then each XML) and cache them;
  - record the morning's fills at the official open (Yahoo daily bar);
  - mark the book at the close and check the stops;
  - journal everything and feed the dashboard.
- **Pre-open run** (an existing slot between 08:45 and 09:25 ET, or a new task; 9.8):
  - read the previous business day's daily index (the complete list) and fetch any XML still missing;
  - build the day's events;
  - write the decision (entries, exits due, stops from yesterday's close) before 09:30.

  A decision written after 09:30 applies to the next session and is tagged `late_decision`.
- **Running twice changes nothing:** a second run in one day makes no second trade and no second mark (tested).

### 7.3 Journals (new, under `state/insider/`)

- **Hash-chained** through `journal.append`, like the other books: `events.jsonl`, `decisions.jsonl`, `trades.jsonl`,
  `trials.jsonl`.
- **Plain files:**
  - `equity.jsonl`, one row per day: equity, cash, g_t, SPY, M, IWM.
  - `feed_health.jsonl`, one row per poll:
    - requests;
    - filings seen against the daily index count;
    - parse failures;
    - 403 and 429 answers seen;
    - `late_feed` and `late_decision` counts;
    - the delay from acceptance to `first_seen`, once spec 65 has calibrated the clock.
  - `rejects.jsonl`, one row per day: counts per drop reason.
- **Verification:**
  - A new `INSIDER_CHAINED` set lives outside `journal.CHAINED` [C journal.py:58-61], so the stock and crypto
    `verify` results do not change.
  - `insider-status --verify` checks the insider chains, and `verify` prints one extra line about them.
- **Out of git:** raw filings and XML stay in `.cache/insider/`.

### 7.4 Losses
Every losing sale of the book goes through the loss protocol: `postmortem` learns the book "insider". In stage 1 the
expected volume is high. Roughly 40-50% of exits lose (U), at about 120 exits a year. See owner decision 9.7.

### 7.5 Dashboard line
- One KPI row and one curve, titled "insider book (experiment, log-only)":
  - equity against SPY and against M, since the seal;
  - open positions and today's events;
  - feed status: last poll, filings seen against expected, errors;
  - days into the forward record;
  - the label "no proven edge", until the holdout passes and the forward DSR is at least 0.95.
- Rows tagged `ikpi`, `ieq` and `ipos` in the snapshot (`dashboard.py`), plus a section in `dashboard/index.html`.

### 7.6 Reports, and the problem with a 6-month probability
- **Weekly:** one line in the Saturday report.
- **Monthly:**
  - the forward E's R1 α and its NW t;
  - P(Sharpe_B > Sharpe_SPY);
  - CAGR against M;
  - coverage and feed health.
- **The probability on a short record:**
  - The repo's bootstrap prints no range below `min_blocks` x `block_days` = 40 x 20 = 800 sessions
    [C config.json:293].
  - 6 months is about 126 sessions, so the real-money gate's P(Sharpe > SPY) cannot be computed with the house
    settings at 6 months.
  - The method must be decided (9.10).
- **Expectation:**
  - The SE of an annual Sharpe estimate is about 1/√years, so about 1.4 over half a year.
  - At a correlation of 0.6 with SPY (U), the SE of the Sharpe difference is about √(2 x 0.4) x 1.4 ≈ 1.27.
  - P ≥ 0.8 then needs a measured Sharpe gap of about 0.84 x 1.27 ≈ 1.07.
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
| U1 | `form4.py`: TSV loader (links from the listing page), XML parser, one row format | TSV/XML parity on fixtures (a P with two owners, a 4/A, a derivative-only filing); unknown XML elements ignored |
| U2 | `insider_events.py`: filters 3.1, class 3.2, events 3.3, availability 2.3, rejects | synthetic histories (Jan-Jan-Jan routine; a gap year; a December trade filed in January; a joint filing with a 10% owner; the 22:00 rule; NYSE holidays from SPY sessions); **no look-ahead**: events with entry ≤ t are identical when every filing after t is removed |
| U3 | `insider_prices.py`: its own Yahoo client (period1/period2; `data.py` not edited), split-undo for the sanity check, coverage; DTB3, the Ken French files, SPY, IWM, RSP; cache in `.cache/insider/` | price check on the TSM, PAM and LUCK cases; a series that ends mid-hold; a reused ticker |
| U4 | `residual.py`: OLS and Newey-West (numpy); also the core of backlog 5 | known answer: synthetic series with known α and AR(1) errors |
| U5 | `insider_replay.py`: E and B, T0/T1/T2, seal and unseal, trials chain, report | the seal refuses holdout dates; a second unseal is refused; a config changed after the seal is refused; N counts every registered run; **nothing is written to `state/trials.jsonl`** (the stock DSR keeps N = 74 [K Done 2026-11-14]) |
| U6 | `insider_book.py` and CLI (`insider-run --preopen/--close`, `insider-status`): journals, the `first_seen` rule, `late_decision`, the breaker, mid-hold delisting | two runs in one day make one trade; a filing seen after the open enters a session later; the breaker steps |
| U7 | dashboard rows and page section; `postmortem` book "insider"; `INSIDER_CHAINED` in `journal.py`; a section in `skills/trader/SKILL.md` (the two runs, the verdict message, the bans) | the stock and crypto `verify` outputs are unchanged; the golden stock tests stay byte-identical |
| U8 | The runs (6.7): download, event table and coverage report to the owner, seal, design runs, power line, unseal, verdict | (operations, not code) |

### 8.2 Files

- **New:**
  - `aitrader/form4.py`, `aitrader/insider_events.py`, `aitrader/insider_prices.py`, `aitrader/residual.py`,
    `aitrader/insider_replay.py`, `aitrader/insider_book.py`
  - `aitrader/sec.py`, if spec 65 has not built it
  - `tests/test_form4.py`, `tests/test_insider_events.py`, `tests/test_insider_replay.py`, `tests/test_residual.py`,
    `tests/test_insider_book.py`
  - `tests/fixtures/insider/`
- **Edited** (none of them on the time-machine list): `aitrader/__main__.py` (CLI), `aitrader/journal.py`
  (`INSIDER_CHAINED`), `aitrader/dashboard.py`, `dashboard/index.html`, `aitrader/postmortem.py`,
  `skills/trader/SKILL.md`, and `config.json` (`books.insider` only).
- **Untouched:**
  - The frozen list: `backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py`, `broker.py`, `data.py`, and
    the `risk`, `signals` and `costs` blocks of `config.json`.
  - `metrics.dsr`, `metrics.psr` and `metrics.boot_rows` are imported read-only.
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
| U2 | 5-7 |
| U3 | 4-6 |
| U4 | 2-3 |
| U5 | 5-7 |
| U6 | 6-8 |
| U7 | 3-4 |
| Gate rounds (critic, fixes) | 3-5 |
| **Total** | **about 33-47** |

- **Wall time on top of that:**
  - the 83 downloads: sizes unknown (U);
  - Yahoo histories for a few thousand symbols at about 1 request a second: 1-2 hours (U on the count).
- **Queue:**
  - after the defects and owner items at the top of the backlog (72, 33, 44, 34, 35, 39, 40 [K header]);
  - after the contact address;
  - in the one-builder-at-a-time order of CLAUDE.md.
- **Time to a verdict:** once the builder is free, about one week of sessions (an estimate).

## 9. Open decisions for the owner (one line each, with a recommendation)

1. **The SEC contact address** (already decided [K 65], still missing). It blocks both the history study and the
   feed. Rec: open it now; spec 65 needs it too.
2. **Price data for delisted names** (4.4). Rec: Yahoo with the T1 rule first. Buy one month of a delisted-inclusive
   source (about $20, U) only if coverage is below 85% and a sample check shows the source fixes it.
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
10. **How P(Sharpe > SPY) is computed on a 6-month record** (7.6). Rec: a 5-day-block bootstrap marked "short
    record", with the Memmel-corrected Jobson-Korkie test as a cross-check (U on the exact method). Real money only
    when both are at least 0.8.
11. **The SPY bar on the holdout** (P2). Rec: keep it, even though small caps lagged SPY in these years (U). A book
    that cannot beat SPY is of no use for his money.
12. **Real-money gate length.** CLAUDE.md says at least 6 months; the review proposed 12 [Rv]. Rec: 6 as the minimum,
    with the expectation of 7.6 that it will take longer.
13. **Tax rate for the after-tax line** (5.7). Rec: the rate his accountant confirms. 25% is unverified.
14. **Book size and slots.** Rec: $100,000 paper and 30 names, like the other books.

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
  "data":   {"first_quarter": "2006q1", "listing_page": "<W1 url>", "max_req_per_s": 1.0},
  "event":  {"forms": ["4"], "trans_code": "P", "acq_disp": "A",
             "relationship_any": ["OFFICER", "DIRECTOR"], "relationship_none": ["TENPERCENTOWNER"],
             "owner_entity_patterns": [...], "issuer_exclude_patterns": [...],
             "plan_footnote_patterns": [...], "private_deal_footnote_patterns": [...],
             "max_report_lag_days": 30, "min_event_value_usd": 25000, "routine_lookback_years": 3,
             "class_unit": "owner_issuer_pair", "price_sanity_band": [0.75, 1.33], "min_price": 5.0,
             "min_median_dollar_volume_20d": 1000000, "cluster_min_insiders": 1, "cluster_window_days": 30},
  "book":   {"starting_cash": 100000, "max_names": 30, "hold_sessions": 63, "rank": ["n_insiders", "value", "cik"],
             "stop_from_entry": -0.30, "dd_halve": -0.10, "dd_flat": -0.20, "dd_reentry_days": 20,
             "max_pct_adv": 0.01, "tax_rate_realized": 0.25},
  "costs":  {"bps_by_adv": [[50000000, 10], [10000000, 25], [0, 50]], "unpriced_bps": 50, "stress_mult": 2.0},
  "eval":   {"design": ["2009-01-02", "2018-12-31"], "holdout": ["2019-01-02", "2026-09-30"],
             "split": "2022-11-01", "nw_lags": 10, "t_design": 1.5, "t_holdout": 2.0, "p_min": 0.8,
             "dsr_min": 0.95, "coverage_min": 0.85, "runs": ["V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7"],
             "max_defect_rounds": 2, "delist_stress": -0.30},
  "forward":{"kill_dd": -0.25, "pause_outage_sessions": 10, "late_decision_cutoff_et": "09:30"}
}
```
