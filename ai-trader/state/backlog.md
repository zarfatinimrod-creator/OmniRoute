# Improvement backlog (the weekly review takes the top open item)

Every item: implement behind a config switch -> paired sweep before/after (strategy-time-machine) -> quant-critic
PASS -> only then merge. Sources: research/2026-11-09-repo-sweep-take-list.md, research/*.md, critic notes.

## Open (priority order)
Owner's decision 2026-11-16 (research/2026-11-16-real-money-review.md): stock and crypto strategy parameters FROZEN;
the improvement effort goes to item 3 (opportunistic insider purchases, log-only book, sealed holdout, kill criterion
written first) after defects; real-money gate = 6 months forward (CLAUDE.md hard rule 1).

First, from the MU loss review of 2026-11-10 (defects and owner decisions): 72 (crypto data defect, found 2026-11-14), 33, 44, 34, 35, 39, 40 - then the list below.
1. [defect] Learning label credits the overnight gap: learn.forward_excess uses close(d)->close(d+h) but fills are
   at open(d+1). Use open(d+1)->open(d+1+h); mature at asof-h-1; rerun placebo; add a test that the label equals
   the return the backtest earns (qlib leak-gap 2; FinRL-Trading label assertion).
2. [parity] Backtest ignores earnings_blackout/earnings_max_position_pct; build a point-in-time earnings table from
   SEC 8-K Item 2.02 acceptance times (day-trader-skill trader-analyst/facts.py) and apply in both paths. Live
   cooldown uses BDay (ignores NYSE holidays) - use the trading-day index.
3. [signal] SEC Form 4 opportunistic insider purchases (officers/directors, code P, Cohen-Malloy-Pomorski routine
   filter, cluster count) - strongest evidence in the research; start as a log-only overlay, promote only after a
   forward record + placebo gate.
   2026-11-24: owner approved spec rev 2 (research/specs/2026-11-16-insider-book-design.md) with all 16
   recommendations of its section 9 (answer א, in chat). Blocked only on owner actions: AITRADER_SEC_CONTACT (env var)
   and a free Tiingo key (network secret). Build plan next (Fable builds, Opus gates, claims first), starting with the
   parts that need neither.
4. [measurement] Desk scorecard: per-rating table for source=desk, veto/shrink value line (20d excess of
   shrunk/vetoed names vs passed names = Claude vs shadow), slugging, n<20 warnings.
5. [measurement] Residual-edge gate: alpha vs SPY + equal-weight + 12-1 momentum basket + gross-matched SPY/cash,
   Newey-West t (tradermonty residual-edge-analyzer, stdlib).
6. [robustness] Sealed holdout (--holdout-from, plan hash in trials.jsonl), PBO over sweep variants, BH over the
   signals' IC p-values, cost break-even bps.
7. [turnover] max_replacements_per_rebalance (2-4) and min_hold_days (5-10) as sweep variants; Ledoit-Wolf
   shrinkage for the 60-day covariance (qlib riskmodel/shrink.py).
8. [data] Data-quality gate in load_market (quarantine gaps / |move|>50%), stale-quote guard in live_prices.
9. [desk] 8-K event classifier in the brief (day-trader-skill trader-news ITEMS_8K), SEC rate limiter.
10. [universe] Point-in-time S&P membership mask for NEW entries (survivorship), report the bias.
11. [desk] Number-grounding lint for desk output and lessons (every number must match the brief within 0.5%).
12. [desk] Thesis records with machine-checkable tripwires (state/theses.jsonl), recomputed post-close.
13. [overlay] House PTR overlay via trader-pelosi (free Quiver substitute), graded by filing date.
14. [ops] Move ai-trader to its own private repo + GitHub Actions "body" (needs Nimrod).
15. [news][risk] Queue-at-open has no priced-in guard: a pre-market headline scored > 8 is bought at the 09:30
    open whatever the gap, and before the open the scorer's move input is null. Needs the owner's rule (for example:
    skip when the open is more than X% above the previous close) and forward evidence for X.
16. [news][risk] Code-level "no chase" guard: the priced-in brake lives only in the scorer's reading of the day
    move (broken on 2026-11-09, see lessons). Decide with the owner whether a buy is skipped in code when the stock
    is already up more than X% today.
17. [news][ops] Engine supervisor that restarts a dead engine within seconds (today: two scheduled watchdogs,
    worst case about 30 minutes; the 2026-11-09 17:26 UTC death left no trace). Journal scorer failures and
    headlines dropped unscored (147 on 2026-11-09 with no logged reason) instead of printing them.
18. [news][measurement] De-duplicate the same article across ticker feeds before grading (371 distinct headlines
    in 524 scored rows on 2026-11-09; 53 of the 126 one-day calls are one NVDA story); 81 of 126 calls are "down"
    calls the long-only news book never trades; the scoring cost (claude -p per batch) is recorded nowhere.
19. [desk] Claude's shrinks expire at the next rebalance: overrides.json is tied to one decision date
    (cycle._apply_overrides) and the desk reviews only new entries, while its calls run 20 days. Decide (critic)
    whether an open desk Hold keeps shrinking a held name. The four shrinks of 2026-11-06 (KO, UNP, CVX, PM) end
    at the next rebalance, which can come as early as the first close where VIX leaves its top-20% band.
20. [risk] A sector ETF does not count toward its sector cap: Health stocks 19.54% + XLV 7.32% = 26.86% of equity
    (53.4% of the invested money) on 2026-11-09, with risk.max_sector_pct 30% applied to the stocks only.
21. [learning] Graded predictions feed nothing automatically (scorecard, dashboard and desk context only). Decide
    whether a source's hit rate should gate its size (desk, news rule).
22. [docs] lessons.md still lists superseded sweep numbers without a marker (v1/v2 Sharpe in the first lessons;
    the "learned weights beat priors" lesson is retracted by the placebo lesson below it).
24. [crypto] Parked and deferred minors from the crypto build (6 parked, 20 open minors, rulings R1-R19):
    research/2026-11-09-crypto-deferred-and-rulings.txt.
25. [alerts] Engine alerts are written in English; the owner reads Hebrew. Translate the urgent ones.
28. [news][risk] The priced-in rule now really softens negative scores on a stock that already fell, so the
    bad-news exit (score <= 2) on a held name fires less. Owner/critic decision: never soften a negative score.
29. [news][signal] Before the open and after the close the scorer gets no move (null), and in session the brake uses
    the stock's own move with no market reference (on 2026-11-09, 39 of the 74 names were up 2% or more). Pass a
    pre-market move and the benchmark's move; ties to item 15.
30. [news][model] Compare scorer models on the same headlines (agreement, delay, cost). Haiku 5.5 today; the owner's
    standing order is Fable 5.2 for all work, and the scorer is his decision with these numbers.

33. [news][defect] Seal the scorer call. `score_batch` starts `claude -p` in the project directory with the default
    tools, so the project's instruction files are part of every scoring call: the same headline and input gave a 9
    in 12 of 18 calls from the engine's directory against 2 of 18 from an empty one, and every edit of CLAUDE.md is
    an untested change to what is bought. Fix: an empty directory and no tools (the second check already runs that
    way: `--tools "" --`), after a side-by-side run on real headlines at both thresholds (> 8 buys, <= 2 sells).
    It is a scorer change: rule 4 and the owner's approval (ties to 30 and to the lean-scorer trial in
    research/2026-11-10-upgrade-roadmap.txt). Until then every score row carries `context`, a stamp of those files.
34. [news][risk][owner] The queue at the open buys on a score that was given with no move input (replays of the MU
    headline with a null move: a 9 in 10 of 17 calls), at the 09:30 price even when the queue is processed later.
    Options for the owner: no queued buys until a gap-at-open measure exists; or an expiry and a fill window (use
    the 09:30 open only within N seconds of it, else the first live quote). Ties to 15 and 29. Covered by the news
    hold while it lasts.
35. [news][rule][owner] The three guards on trial (`news.guards` = log: no_chase, second_check, stop_cooldown).
    Read state/news_checks.jsonl against the graded predictions once it holds 30+ above-the-line headlines; a guard
    is proposed for enforcing only with |t| > 2, through rule 4 and with the owner's answer. Before `enforce` can be
    switched on at all: handle a batch in two passes (scores and bad-news sales first, then buys and checks), or an
    enforced check ages the quote of a sale behind it (quant gate, 2026-11-10). Known limits: 3.0% is the stop
    distance, not a measured number, and on 2026-11-09 half the universe was up 2% or more (29); the stop cooldown
    reads the sale's reason text, key it on realized_pnl < 0.
36. [news][rule][owner] Catch-up stop. When a stop was traded through unseen the owner is only told
    (`stop_catchup` = alert). Whether such a position is then sold at the first live quote (`sell`) is his reading
    of "sell at -3%, no exceptions". Evidence so far: one case (MU 2026-11-10: a sale at 14:38 UTC would have
    realized about -120.7 against -137.70).
37. [news][risk][owner] The -3% stop is inside ordinary movement for about half the news universe (median
    14-session range 3.0%; next-session low 3%+ under the close on 12.7% of stock-days, MU 35%). Options: skip
    names above a volatility line, or size down (MU: 2 shares, about -46 instead of -137.70). The measure and the
    number are the owner's; he gets the coverage table first (logs/2026-11-10-loss-postmortem.md).
38. [news][risk][owner] Overnight holds: MU opened 2.15% under its close and stops are not checked outside the
    session by design. Decide: flat by the close, or accept. Also numeric brakes after losses (daily loss limit,
    burst limit): his numbers, built when he chooses.
39. [news][ops] Engine availability beyond the watchdogs (extends 17; research/2026-11-10-upgrade-roadmap.txt,
    project 1): an uptime ledger, a supervisor that restarts within seconds, a standby before the 2-hour cap, and
    a check from outside the container. Today: tracked background task, `--minutes 110`, two watchdogs, the session
    is woken when the task ends (but waits behind a running turn). No watchdog visit after 15:37 New York. The
    three crypto slots created on 2026-11-11 do not run `postmortem`: add the step to them.
40. [news][ops] The engine and the checkout. Every start loads the working tree as it is (the 16:54 UTC start of
    2026-11-10 loaded code that had not passed its gate), and `git pull --rebase` in the directory the engine
    writes to can check out an older journal for a moment. Run the engine from a checkout that only moves on a
    gated commit, or refuse to start on a dirty tree; today the heartbeat only shows it (`code.commit`,
    `code.dirty`). Heavy jobs (a sweep, a gate) on the engine's machine slow its loop: load average 8 on 4 cores
    on 2026-11-10 while the book was flat.
41. [news][measurement] A time machine for the news rules: archive every headline with its first-seen time and the
    one-minute bars (Yahoo keeps them 30 days and changes them between fetches: the 14:30 UTC bar of 2026-11-10 was
    seen with lows 709.90 and 710.22), then replay entry and exit rules. A fresh quote right before every fill
    (today: the quote from before scoring, up to max_quote_age_minutes old) and the move since publication as a
    logged field (MU: +0.09%).
42. [postmortem] Crypto: the entry fee sits on the BUY row, so `losses()` estimates a sale's loss as realized_pnl
    less one more fee of its own size. Replace it with the true round-trip P&L when the crypto book has sales.
    A loss review after a chain repair shows its cause under REPEATED CAUSES (README): count reviews of live keys.
43. [news] Smaller ones from the gates of 2026-11-10: the 10-day look-back for the previous session and the default
    timeouts are still literals; the catch-up reads today's bars only (a stretch of an earlier day is only said);
    a journal row and the book are written one after the other (a kill between them: reconcile at start); the
    30-minute freshness rule measures Yahoo's stamp, not the age of the news; a latency cap can be studied from
    `latency_s` once grades exist; whether an engine alert reached the phone is recorded nowhere; `news-exit`
    sales and refusals still say "operator"/"owner" also when the session asked (ties to 25, 26).
44. [news][ops] Should-fix items of the last gate (2026-11-10, PASS on the pushed tree), in its order: (1) a held
    name with no live quote has its minute bars asked for at every look when the answer is empty or short (up to
    350 reads an hour per name; a read slower than about 9.5 s doubles the gap between live stop looks): ask the
    same stretch again only after stop_catchup_gap_seconds; (2) an engine started before the open writes the
    heartbeat with no stop stamp and then falls back to the equity curve, so the "not checked since yesterday"
    alert can still fire when the last equity point is more than 90 s before the bell; (3) enforce only: a thread
    that cannot start raises out of the step instead of being a refusal; (4) the last unpublished minute of a
    down-stretch is not read back once the name has a live quote again; (5) on a new container the engine primes
    and never scores fresh bad news on a name it holds (news_seen.json is not in git): do not prime away the
    headlines of held names; (6) one waiting thread per pending trial check, and up to three scorer processes
    outlive an engine that ends in market hours: one worker with a queue, kill them at the end; (7) after a kill
    in the middle of a step the headlines already scored are scored again (duplicate score rows, never a
    duplicate buy).

45. [desk][docs] The trading-desk skill disagrees with itself on cost: its steps ask for six agent calls a name
    (bull, bear, one rebuttal each, the inversion lens, the risk team) and its cost guard says three. The COP desk
    of 2026-11-10 used six, about 120k tokens each, most of it context. Decide which is meant, and give the roles
    only the brief. The skill file is under the one-builder rule (BUILD_CLAIMS.md): claim it first.
46. [news][defect] A day-move that is not a finite number is read as known. `_buy` treats only None as "not
    known": on trial the moves '5.8', 'n/a', NaN, [5.8] and True are all bought, and NaN and True are bought even
    with the guards enforced (probe in research/2026-11-10-loss-protocol-pins/NOTES.md, section 8). Not reachable
    from the live loop today (`live_price` gives a rounded float or None, and any error becomes None), and buys
    are on hold. Fix: read anything that is not a finite number as None, before `if move is None`; rule 4. The
    file is under the main session's claim.
47. [tests] Fold `tests/test_loss_protocol_pins.py` into the classes it extends and delete it
    (research/2026-11-10-loss-protocol-pins/waiting.diff or fold.py), with the wait for background "trial-check"
    threads in `_Engine.setUp/tearDown`. Old tests that fail by the clock and are still in the suite: three at 23:59
    or just after midnight New York (in the diff), fourteen when a day turns inside them (eleven in CatchUpStop at
    UTC midnight: one fixed day in its setUp closes them; list in tools/ there). `tests/test_audit_fixes.py` starts
    git once a run; the Checker tests leave an empty aitrader-scorer directory in the temp directory.
48. [news][docs] config.json `news._note_guards`: with stop_catchup_gap_seconds 90 under stop_catchup_min_seconds
    120 the minimum decides alone when minute bars are read back (any gap from 0 to 119 behaves the same). The 90
    is in force in a second role the note does not name: how close to the closing bell the last look of an earlier
    day must be for no "not checked since" alert. Say both in the note.
49. [news] Two observations from the review of the pins, not yet looked into: (a) in the default catch-up mode a
    held name with no live quote and unreadable minute bars still gets a "looked at" stamp in the heartbeat (the
    owner is told once), so a restart does not read that stretch back; (b) `news-hold --release` takes effect even
    when its record in news_holds.jsonl cannot be written (the command says so and exits 1): decide whether the
    record should come first.
50. [process] The mutation harness (research/2026-11-10-loss-protocol-pins/mutation/) is not wired to anything and
    its 420 mutants are anchored on line numbers of e6a82895. After the next change to news_live.py, postmortem.py
    or __main__.py: re-anchor them, run them, and treat a survivor in a guard, a sale or a stop look as a missing
    test. Eight survivors behave like the unchanged code (K14, K22, K27, PM64, PM75, X02, X03, BY1).
51. [news][measurement] Health row: a stop-check gap still open when the row is cut is not in it, and the open
    window is lost when the engine stops (second gate: 4 s with no check read stop_gap_max_s 0.0; 4 steps, 0 rows).
52. [news][measurement] A headline whose score is already journaled gets "step_failed" when a later write in the
    same chunk fails (second gate): write its "scored" row right after its news_scores row.
53. [news] Small ones (second gate): a book save that fails before a request is cleared is journaled with where
    "news_exits"; a headline older than seen_keep_days leaves no news_seen_log row; an undated quote leaves the
    blind-stop alert without its price time.
54. [review] No gate round is on record for the fix commits after the gates' last round (made on base 0215537a as
    cf2b2832 and 3f88543a), nor for the merge of wave 3 onto e6a82895 (the three engine commits are one there; the
    tests of both sides pass). The fixer's list: requests matched by the sale's reason; `except Exception` round the
    scorer call; first health window. From the merge: the facts of a scorer call ride on its answer (Scores.facts);
    the health row's stop gap reads _stops_checked_at; the book save before a request is cleared is save(seen=False).
55. [tests] tests/test_crypto_sweep.py and tests/test_books.py run real git through backtest.code_commit (16 and 4
    calls per suite run, measured 2026-11-10; local, read-only, 10 s timeout): patch code_commit in their setUp.
56. [time-machine] Probabilities print 0.000 and 1.000, which 2,000 resamples cannot show: print "<0.001" and
    ">0.999". Keep numpy.__version__ in the run record (gate of 2026-11-10, the part of its finding not done).
57. [time-machine] "prior weights (no learning)" equals the base on all 2,224 days of the gate's run: one of the 12
    counted variants is a duplicate inside the Deflated Sharpe spread. Find why the learner changes nothing in replay.
58. [time-machine] The ranges floor (bootstrap.min_blocks 40) is a margin, not a measured threshold: the fixer's and
    the gate's coverage differ at 250 and 500 days, neither script is in the repo. block_days stays fixed meanwhile.
59. [crypto] The crypto sweep's ranges section and run record have unit tests only: no real crypto sweep has run
    with them (research/2026-11-10-time-machine-honesty.md, Limits). Read them at the next crypto sweep.
60. [news][measurement] The calls of the second check are in no cost journal: two checker calls and one re-score for
    every headline over the buy line that reaches a buy or the queue (in the background while the guards are on
    trial). news_scorer_calls.jsonl holds the loop's scorer calls and the news-score check only (seen at the merge
    of wave 3 onto e6a82895).
61. [news] `news-exit` now fails when config.json cannot be read (it reads the two lock numbers first): on any
    error fall back to the defaults and still write the request. One test. (merge gate of 2026-11-11)
62. [news][owner] A scorer answer that is not a whole number is skipped. For buys that is the safe side; for the
    bad-news exit it is not: a score of 1.6 on a held name no longer sells (the stop still holds). Accept
    whole-number text ("1", "9") as that number, and decide with the owner what a fraction at the low end does.
    **Owner's decision (Nimrod, 2026-11-11, answer א):** for the bad-news exit a fraction is compared as it is: 2 or
    less sells (1.6 sells, 2.4 does not). Buys do not change: only a whole number above 8 buys. Evidence before the
    change: 1,190 rows in `state/news_scores.jsonl` on 2026-11-11, all whole numbers, 0 fractions, so no sale was
    missed so far. Forward measurement (as built in Task 8b of the supervisor build): "after" = the SELL rows of
    `state/news_trades.jsonl` that match a `news_scores.jsonl` row carrying `raw_score` (same symbol, same step); a
    `raw_score` row with no matching sale (blocked by the live-quote rule, or the name already sold) is its own figure;
    and the sum of `fractions` in `state/news_scorer_calls.jsonl`. Read at every Saturday review.
    Correction (quant-critic, gate of 2026-11-11): the informative "before" figure is `state/news_seen_log.jsonl`
    outcome `scorer_no_answer` (0 of 729 rows on 2026-11-11), not `news_scores.jsonl` (the old parser dropped
    fractions before anything was written). The "after" starts on the landing date of rollout step 1. Prediction
    rows made from a fraction are graded with the rounded-down score: separate them by `raw_score` when reading
    forecast accuracy. Waits for its build slot (one builder at a time: after Task 8 of the supervisor plan) and for
    rule 4.
63. [news][owner] The law says a news-exit is not undone, and the merge added `news-exit --cancel`. One sentence in
    CLAUDE.md and SKILL.md 3ב: a waiting request is cancelled only on the owner's word, and the cancel is logged.
    **Owner's decision (Nimrod, 2026-11-11, answer א):** the command stays; a waiting request is cancelled only on
    his word and the cancel is written down. In CLAUDE.md since 2026-11-11 (the loss protocol and hard rule 3).
    Still to build (queued after Task 8b of the supervisor plan, same gate): `--cancel` refuses without
    `--said TEXT` (his words) and writes a row to `state/news_exit_cancels.jsonl`; the SKILL.md 3ב lines with it.
64. [news][owner] The hold on new buys in the news book (set 2026-11-10 19:42 UTC, `state/news_hold.json`) stays.
    **Owner's decision (Nimrod, 2026-11-11, answer א):** no buys until there is a record; the engine keeps scoring
    and grading every headline. Review trigger: 10 graded headlines with a score above `news.buy_min_score` since
    the hold began (`state/news_predictions.jsonl` with `state/news_grades.jsonl`; what each guard would have said
    is in `state/news_checks.jsonl`). Then the main session brings him the count, the hit rate, the mean excess
    return against SPY at the grading horizon and what each guard would have refused, and he decides. Evidence for
    the pace: 1 headline of 1,190 scored above 8 on 2026-11-09 and 2026-11-10 (`state/news_scores.jsonl`), so
    about a month. The hold is lifted only on his word. The Saturday review writes the running count in the
    weekly report.
    Running count 2026-11-19 close: the first scores above 8 since the hold, 5 headlines of 6,133 scored since
    2026-11-10 19:42 UTC, all score 9 (`state/news_scores.jsonl`): WMT x3 (13:37, 13:58, 14:03 UTC, FY27 outlook
    raised), PANW (14:00, results beat, forecast raised), MSFT (17:56, "Microsoft Stocks Rise 3.16% as Anthropic
    Commits $47.2 Billion Minimum to Azure"). All refused by the hold (`state/news_checks.jsonl`); the log-mode
    guards would also have refused PANW (no_chase +4.55%, second_check move_recap) and MSFT (second_check
    move_recap); WMT passed the second check. None graded yet: 0 of the 10 graded headlines the review needs.
    2026-11-21: all five have 1-day grades in state/news_grades.jsonl (graded 2026-11-20 21:36Z): WMT x3 hit (excess
    +5.16%), PANW miss (-1.45%), MSFT miss (-0.08%); the 5-day grades in state/news_predictions.jsonl are pending.
    The item does not name the grading horizon: say which one when the count reaches 10.
65. [news][source] SEC filings as a faster news source, log-only first (roadmap 2026-11-10, sub-project 4).
    **Owner's decision (Nimrod, 2026-11-11, answer א):** the SEC contact address for the User-Agent is a new address
    used only by the bot; he opens it himself and gives it in chat. It lives only in the environment variable
    `AITRADER_SEC_CONTACT` (never in a file, a log, a journal, an error text or the repository; the repository is
    public). Until it exists nothing calls the SEC. Next: the design spec (being written from the roadmap), his
    approval, a plan, then the build in the one-at-a-time queue. The source moves no money until it has a forward
    record and passes rule 4 (Basic law 2, item 3).
    **Spec approved by the owner on 2026-11-11 (answer א):** `research/specs/2026-11-11-sec-filings-feed-design.md`.
    Next: its implementation plan; the build joins the one-at-a-time queue after the supervisor and the trading room.
69. [crypto][gate] Deferred by the quant-critic at the go-live gate of 2026-11-11 (PASS, round 2;
    `logs/2026-11-11-crypto-go-live.md`). None is blocking for paper. (Renumbered from 66, which another
    session also used.)
    - N1: after an expired order the next decision is a full rebalance even when the expired one was exits-only
      (`aitrader/cycle.py` `redo`). Inside caps and vol target, but the backtest always fills, so it is a live/replay
      difference. Narrower option: `expiring and old.rebalance`. Needs its own gate.
    - N2: a veto or shrink on an expired decision date does not carry to the decision that replaces it (within the
      rules); say so in the expiry alert.
    - N3: no live-cycle test on crypto_base beyond the expiry test (regime-on entry, -50% flat and re-entry through
      the cycle); `costs.exec_delay_bps` 10 is an assumption - measure it from the first fills (the backtest fills at
      open[D+1], which Yahoo rewrites to close[D]); dust below one lot is dropped without credit (under $0.10).
    - Not measured: whether Yahoo's close of bar D is final at 00:12 UTC. The R6 audit
      (`market.revised_close_alert_bps` 5) checks every decision; read `close_audit` in `state/crypto/pending.json`
      and `revised_close` rows in `state/crypto/decisions.jsonl` after the first week.
72. [crypto][defect] The backlog 70 rebuild accepts a complete but not final 23:00 1h bar: a wrong close reached a
    decision. On 2026-11-14 Yahoo's 1h bars of 11-13 were complete at 00:13:47, 00:14:14 (the rerun that decided) and
    01:08:44, all with BTC close 67,881.85; the settled 23:00 1h close is 68,223.01 and Yahoo's daily close 68,249.27,
    so the decision close was -53.8 bp off (regime_sma 73,033.55: risk_off either way, no trade changed). Two agreeing
    tries 30 s apart or a 00:30 UTC floor would both have accepted the stale bar (backlog 71 gate, commit 99d51558).
    Candidate checks, log-only first: the 1h 23:00 close equals the close of the 23:55 5m bar (matched exactly on
    settled data 11-09..11-13; not yet measured live at 00:13); or a Coinbase cross-check tighter than the 1% guard
    (backlog 70 option b). Measure at the next 00:13 runs, then rule 4. Until fixed, 71 (d) stays off. The R6 audit
    should flag the 11-13 close (about -54 bp, over the 5 bp line) at the next decision.
    2026-11-15 measurement (logs/2026-11-15-crypto-night.md): the 23:00 1h bar of 11-14 first appeared at 00:45:40
    (64,113.45) and then alternated null/value between successive fetches until at least 01:12 (Yahoo replicas
    disagree); the 5m 23:55 close equalled the 1h close in every non-null reply (same reply, so not an independent
    finality check). Settled 11-14 daily close 64,128.05: the 1h close decided on (64,113.45) was -2.3 bp off (under R6).
    2026-11-16 00:13:42: the 11-15 1h 23:00 bar had a value (65,174.53, decided on) while the 5m 23:55 bar was still
    null - a '1h 23:00 == 5m 23:55' check would have held that decision back; compare with the settled close.
    Tally so far (rebuilt close vs settled daily): 11-12 -3.8 bp, 11-13 -53.8 bp, 11-14 -2.3 bp, 11-15 -20.0 bp
    (decided 00:13 on 65,174.53 with the 5m 23:55 bar null; settled daily 65,305.06, read 2026-11-17 00:13:42; the
    final 1h 23:00 close 65,316.69 = the 5m close, +1.8 bp vs daily). The '1h 23:00 == 5m 23:55' check: would have
    held 11-15 back (right), passed 11-14 (first value final, right); 11-13 unknown (no 5m reading at the time).
    Two of two so far; keep counting. The R6 audit of the 11-15 decision runs only once a decision on 11-16 exists
    (`_audit_revised_close` needs decision_date < dec_bar); expect an alert of about -20 bp then.
    2026-11-17 00:13:28: the 11-16 rebuild declined (null_value); 1h 23:00, 5m 23:55 and daily all null at 00:13:41.
    The 1h 23:00 bar first appeared at 00:36:08 (64,816.79 = the 5m 23:55 close in the same reply), was null again at
    00:36:39 (a cycle at 00:36:21 declined too) and back at 00:38:44; the cycle at 00:38:46 decided on 64,816.79
    (Coinbase guard gap ~0). The R6 audit of the 11-15 decision fired then: +20.0 bp (decisions.jsonl revised_close).
    11-16: settled daily 64,855.84 (read 2026-11-18 00:13:08) vs 64,816.79 decided = -6.0 bp; the R6 audit fired +6.0 bp
    at 00:13:05. The 1h 23:00 close was still 64,816.79 = the 5m close a day later, so the decided value WAS final:
    the gap is the basis between Yahoo's daily close and its last 1h close (12 settled days 10-31..11-11: 1.93 to
    140.28 USD, up to 0.19%; 11-15 final 1h vs daily +1.8 bp), not finality. So the finality check (right 3 of 3 so
    far: 11-14 pass, 11-15 hold, 11-16 pass) cannot by itself stop R6 alerts on rebuilt closes; a fix must also say
    whether R6 on a yahoo_1h close should allow the basis (owner/rule-4 question), or rebuild from the 1d row's own
    source. 2026-11-18 00:13:06: the 11-17 rebuild succeeded first try (64,856.98 = 5m 23:55), daily null.
    2026-11-18 06:04:38: the 11-17 1h 23:00 close is now 64,873.18 (+2.5 bp vs the 64,856.98 decided on), and the 5m
    23:55 close moved with it (equal at 00:13 and at 06:04). So the '1h 23:00 == 5m 23:55' check PASSED a value that
    was not final: both bars come from the same reply and revise together. Tally of the check: 11-14 pass (final),
    11-15 hold (not final), 11-16 pass (final), 11-17 pass (NOT final, +2.5 bp). It is not a finality test; drop it as
    the candidate. Remaining options: a time floor measured on how late Yahoo's last revision lands, or the Coinbase
    close as the decision close (backlog 70 option b, a data-source change through rule 4).
    2026-11-19 00:14: 11-17 settled daily 64,893.95: decided 64,856.98 = -5.7 bp (over R6 5 bp); final 1h 64,873.18 =
    -3.2 bp vs daily (the basis again). Tally decided-vs-daily: 11-12 -3.8, 11-13 -53.8, 11-14 -2.3, 11-15 -20.0,
    11-16 -6.0, 11-17 -5.7 bp: 4 of 6 over the 5 bp R6 line. 11-18 rebuild declined at 00:13 (all null).
    11-18's 1h 23:00 bar first appeared at 01:28:47 UTC (null at 01:23:46); the decision ran at 01:29 (62,981.71).
    First-appearance times so far: 11-14 00:45, 11-16 00:36, 11-17 00:13 (first try), 11-18 01:28 - a fixed time floor
    before 01:30 would not always work, and a value can still be revised after it appears (11-17 +2.5 bp).
    2026-11-20 00:13: 11-18 settled daily 62,987.27; decided 62,981.71 (1h close, first seen 01:28) = -0.9 bp (under
    R6). Tally decided-vs-daily now 11-12 -3.8, 11-13 -53.8, 11-14 -2.3, 11-15 -20.0, 11-16 -6.0, 11-17 -5.7,
    11-18 -0.9 bp: 4 of 7 over 5 bp. The latest-appearing value (01:28) was the closest so far, which fits a time
    floor, but n=7. 11-19 rebuild declined at 00:13 (1h 23:00 and 5m 23:55 null).
    11-19 night (final72.py probes every ~30 s, 2026-11-20): the 1h 23:00 bar came back as 62,041.00 in 1 of 9
    replies 00:14-00:18, 4 of 72 in 00:19-00:54 and 17 of 226 in 01:08-02:58; the next reply 5 s later was null every
    time; the value never changed; the 5m 23:55 bar never appeared. Three cycle runs (00:13, 00:18, 01:08) declined;
    no decision by 02:58. A rebuild that takes the value from any of several tries would have decided at 00:18; a
    finality rule would need the same value seen more than once. Data only: a code change goes through rule 4.
    Correction 2026-11-20 06:05: the flickering value was NOT the final one. At 06:04:59 the 1h 23:00 bar and the 5m
    23:55 bar both read 61,911.17 (daily row still null), and the cycle decided on that (06:05, exec_ts 07:00). The
    62,041.00 seen 22 times overnight was +21.0 bp off it. Taking the value from any one of several tries would have
    decided on a stale replica, so the null-declines protected the decision this time; a value seen once is not
    final, and neither is a value seen repeatedly from one replica.
    2026-11-21: 11-19 settled daily 61,901.82 vs decided 61,911.17 = +1.5 bp (under R6). 11-20 was decided at 00:13:45
    on the first try on 58,868.49 (1h 23:00; 5m 23:55 null). At 06:04 the 1h and 5m bars both read 58,811.77 (daily
    still null), so the decided value is +9.6 bp off the newer one: the second night running that a value with the 5m
    bar null moved later. Candidate finality rule for rule 4: decide only when the 1h 23:00 and 5m 23:55 bars agree
    in the same reply (both nights, the agreeing pair is the later value); tally decided-vs-daily now 4 of 8 over 5 bp.
    WEEKLY PICK 2026-11-21 (the week's one improvement; build waits for Fable, back 2026-11-22 06:00 UTC, standing
    order). Evidence for a Coinbase cross-check of the decision close (data, not a parameter; the strategy freeze
    allows a data fix through rule 4): Coinbase BTC-USD daily candle close vs Yahoo's final daily close over 103 days
    since 2026-08-01 (api.exchange.coinbase.com candles granularity 86400 vs .cache/BTC-USD_10y.csv): median |diff|
    1.4 bp, 95% of days within 5 bp, mean -3.1 bp; the outliers (11-08 +22.7, 11-12 -327) sit on days the cache
    holds a non-final Yahoo value. The two non-final values of this week would have been caught: 11-19 flicker
    62,041.00 = +20.6 bp vs Coinbase 61,913.23 (the final 61,911.17 = -0.3 bp); 11-20 decided 58,868.49 = +9.1 bp vs
    Coinbase 58,814.99 (the later 58,811.77 = -0.5 bp). Plan: accept a rebuilt or daily Yahoo close only when it is
    within `crypto.close_xcheck_bp` (5) of the Coinbase daily close; otherwise decline as a rebuild_declined with
    reason xcheck and let the late run retry (log mode first: write what it would have declined, change no
    decision). Gate: unit tests + quant-critic; the change touches the crypto data path, so the critic names the
    files and the crypto sweep runs before/after if data.py is touched.
    2026-11-22 00:13: 11-20 settled daily 58,798.98; decided 58,868.49 = +11.8 bp (over R6; the audit fires at the
    next decision). Coinbase 58,814.99 = Yahoo daily -2.7 bp. Tally decided-vs-daily: 11-12 -3.8, 11-13 -53.8,
    11-14 -2.3, 11-15 -20.0, 11-16 -6.0, 11-17 -5.7, 11-18 -0.9, 11-19 +1.5, 11-20 +11.8 bp: 5 of 9 over 5 bp. The
    Coinbase cross-check (5 bp) would have held the 11-20 decision (+9.1 bp vs Coinbase at decision time).
    2026-11-22 06:04: 11-21 was decided at 00:53:33 on 60,086.00 after a confirmed poll (two probes 5 s apart). The
    Coinbase daily close of 11-21 is 60,086.00 (+0.0 bp; api.exchange.coinbase.com candles, granularity 86400);
    the Yahoo daily row of 11-21 is still null at 06:04:24, so the R6 audit of 11-21 waits for it.
    2026-11-23 00:13: 11-21 settled daily 60,094.09; decided 60,086.00 = -1.3 bp (under R6). Coinbase 60,086.00 =
    Yahoo daily -1.3 bp. Tally decided-vs-daily: 11-12 -3.8, 11-13 -53.8, 11-14 -2.3, 11-15 -20.0, 11-16 -6.0,
    11-17 -5.7, 11-18 -0.9, 11-19 +1.5, 11-20 +11.8, 11-21 -1.3 bp: 5 of 10 over 5 bp. The two decisions taken
    only once the 1h 23:00 and 5m 23:55 bars agreed (11-19 at 06:05; 11-21 at 00:53 after a confirmed poll) are
    +1.5 and -1.3 bp; the 11-20 decision (00:13, 5m 23:55 bar still null) is +11.8 bp. Two cases, not proof.
    2026-11-23 01:00 UTC: LOG MODE SHIPPED (commit cc173cf3, merged d9bc73f7). books.crypto.market close_xcheck_bp 5,
    close_xcheck_mode "log"; every crypto decision row in state/crypto/decisions.jsonl now carries diag.close_xcheck
    {mode, bp, symbols{close, coinbase, gap_bp}, would_decline, unreachable}, reusing the Coinbase guard's fetch. It
    changes no decision. Gate: builder (Fable, separate worktree) suite 930 -> 941 OK; quant-critic PASS and live-path
    review PASS (workflow wf_41efa60e-d60); no file the time machine loads touched, so no sweep (third ruling).
    Forward read: from the first decision row logged after the merge, compare would_decline with the revised_close
    row of the same date (R6, 5 bp): caught / false alarm / miss / unreachable, per day. Replay on the 11 logged
    decisions (guard gaps, decision/Coinbase - 1): would_decline on 11-13 (-52.0), 11-15 (-21.6), 11-20 (+9.1); R6
    fired on 11-13, 11-15, 11-16, 11-17, 11-20: 3 caught, 2 missed (11-16 guard 0.0 vs R6 +6.0; 11-17 -2.5 vs +5.7),
    0 false alarms. The 5 bp line was chosen on this same sample: only the forward record counts. Notes before any
    enforce mode (gate, nonblocking): (1) the boundary |gap| == bp is untested (a '>=' mutant survives); (2)
    'unreachable' mixes "Coinbase gave nothing" with "decision close missing": tally them apart; (3) the guard gap is
    exactly 0.0 on 11-12, 11-16, 11-18, 11-21, so Coinbase seems to track Yahoo's 1h close: the check catches a 1h
    close that is not final yet, but cannot see Yahoo's hourly-vs-daily basis behind the 11-16/11-17 R6 alerts; split
    misses by cause (compare with the final 1h 23:00 close too); (4) a book with the check on and coinbase_guard_pct 0
    would fetch inside _decide, outside any try, before exec_ts is set: refuse that combination first. The reviewers
    could not find '+20.6 bp' in the journal: it is the 11-19 flicker value 62,041.00 vs Coinbase 61,913.23, which
    never reached a decision, so the figure is right but is not a journal row.
    First live row 2026-11-23 06:04 (decision 11-22, a 1h rebuild): close 61,160.70 vs Coinbase 61,163.01 = -0.378 bp,
    would_decline [], unreachable [] (state/crypto/decisions.jsonl row 17).
    FIRST FLAG 2026-11-24 00:13:36 (decision 11-23, first try, 1h rebuild): close 61,424.91 vs Coinbase 61,189.97 =
    +38.4 bp, would_decline [BTC-USD] (row 18). At 00:13:37 the 1h 23:00 bar read 61,424.91 while the 5m 23:55 bar was
    null (final72.py), the same pattern as 11-20. Log mode: the decision stood (risk_off either way: 61,424.91 vs SMA
    72,233.15). The R6 audit of 11-23 at the next decision says whether this was a catch or a false alarm.
    11-22 settled daily 61,161.91 (read 2026-11-24 00:13:38); decided 61,160.70 = -0.2 bp (under R6).
    2026-11-24 06:04:44: the 11-23 1h 23:00 and 5m 23:55 bars now agree at 61,206.75 (daily row still null): the
    decided 61,424.91 is +35.6 bp off it, and the agreeing value is +2.7 bp off Coinbase 61,189.97 (at 01:08:33 the 1h
    bar read 61,274.46 with the 5m bar null). So the first flag looks like a true catch; the R6 audit against the
    settled daily close decides it.
    2026-11-25 00:13:18: 11-23 settled daily 61,210.98 (final72.py). Decided 61,424.91 = +34.9 bp off the settled
    close (above R6's 5 bp); Coinbase 61,189.97 = -3.4 bp off it. FIRST FLAG = TRUE CATCH: the check would have
    declined a close that was 35 bp wrong, and the Coinbase value was within 5 bp of the settled close. Tally of the
    live check so far: 2 rows, 1 flag, 1 true catch, 0 false alarms (one case, not proof). The code's own R6
    revised_close row for 11-23 is not written yet: the 11-24 decision is deferred (11-24 daily null at 00:13), and
    the audit runs at the next decision (backlog 71 (a): it is lost if the 11-24 row stays null past 24 h).
    2026-11-25 00:49:47: the code's R6 row confirms it: revised_close 11-23, decision_close 61,424.91 (yahoo_1h) vs
    history_close 61,210.98, gaps_bps -34.83, limit 5 (state/crypto/decisions.jsonl). The 11-24 decision (00:49:48,
    1h rebuild after the 1h 23:00 and 5m 23:55 bars agreed at 59,740.87 on two probes) logged close_xcheck 0.0 bp vs
    Coinbase 59,740.87, would_decline []. Tally: 3 rows, 1 flag, 1 true catch, 0 false alarms.
    2026-11-26 00:14:02: 11-24 settled daily 59,747.77 (final72.py); decided 59,740.87 = -1.15 bp (under R6), Coinbase
    59,740.87 = -1.15 bp: the unflagged row is confirmed. Tally: 3 rows, 1 flag (true catch), 0 false alarms, 2 clean
    rows confirmed by the settled close.
    2026-11-26 06:04:15: the 11-25 decision (1h rebuild, close 60,384.14) logged close_xcheck 0.104 bp vs Coinbase
    60,383.51, would_decline [], unreachable []. Its settled daily close is still null (final72.py 06:04:28); confirm at
    the next decision. Overnight the 1h 23:00 bar flapped: 9 probes showed 60,384.14 between 02:32 and 03:04 UTC, and
    the confirm probe 5 s later was null each time, so the two-probe rule ran no cycle. Tally: 4 rows, 1 flag (true
    catch), 0 false alarms, 2 clean rows confirmed, 1 awaiting its settled close.
    2026-11-27 00:13:52: 11-25 settled daily 60,378.20 (final72.py 00:14:03); decided 60,384.14 = +0.98 bp (under R6),
    Coinbase 60,383.51 = +0.88 bp: the unflagged row is confirmed clean. The 11-26 decision (1h rebuild at the first
    run, close 60,455.83; the 5m 23:55 bar was still null at 00:14:02) logged close_xcheck -6.569 bp vs Coinbase
    60,495.57, would_decline [BTC-USD]: the second flag. Book risk_off and in cash, so no trade effect. Judge it at the
    next decision against the settled 11-26 close. Tally: 5 rows, 2 flags (1 true catch, 1 awaiting), 0 false alarms,
    3 clean rows confirmed.
71. [crypto][follow-ups of 70] Non-blocking notes of the backlog 70 gate (quant-critic and live-path review,
    2026-11-13, commit d2e0c77e): (a) the R6 audit of a rebuilt close is lost when Yahoo's daily row stays null
    for more than 24 hours, because the next decision replaces pending.json first (log when a decision carrying
    hourly_rebuild is replaced before its close_audit exists); (b) DONE 2026-11-14 (7bbb1957): a declined rebuild prints a reason tag and a deciding run that ends in
    the skip writes a rebuild_declined row to skips.jsonl (note: the morning summary counts these rows as skipped
    runs; a live bar is tagged misaligned_stamp - a separate live_bar tag would read better); (c) with a two-coin profile the R6 tag "yahoo_1h" is set for the whole decision close
    even when only one coin was rebuilt - tag per symbol; (d) the in-run wait is BUILT but OFF (7bbb1957 + 99d51558): it
    needs market.rebuild_wait_seconds/rebuild_poll_seconds in books.crypto.market plus tests/test_books.py CRYPTO_MARKET
    and the pin test in test_crypto_rebuild_wait.py; do not switch it on before item 72 (on 2026-11-14 the bars the
    rerun accepted were complete but not final); a try in progress can overrun the budget by up to one try (about
    66 s per symbol on a hanging Yahoo) and the latency on a hanging Yahoo (up to about 66 s per symbol per
    run; the retry count would be the tunable); (e) when two daily rows are missing (D and D-1) only D is rebuilt
    and the decision runs on a history with a one-day hole; (f) expect a "סגירה מתוקנת" R6 alert after most rebuilt
    days (1h close vs daily close measured 1.93-140.28 USD, about 0.3-19 bp; the alert is at 5 bp).
66. [news][rule 4] An engine whose lock call fails (not a held lock) runs unlocked and checks the stops, as before;
    the quant-critic (gate of 2026-11-11) recommends that such an engine opens no new position ("no_lock" in
    `_buys_blocked`), which removes a double-buy risk. A new check: log mode first, then rule 4 and the owner.
67. [news][owner] The R5d line says "ויש עסקאות ביומן" also for a book file that parses but is no book while the
    journal is empty (critic N8, review Ruling 18). Reword the line through the owner, or narrow the case.
73. [news][measurement][owner 2026-11-15] Score each headline a second time with the company name and ticker hidden,
    beside the normal score, and journal both (log only: the normal score alone still decides; no trade changes).
    After enough graded headlines, compare the two scores' forward returns. Why: an LLM recalls what it knows about a
    named company (arXiv 2504.14765, memorization) and attention to famous names drives LLM picks (NBER w35153).
    Source: research/2026-11-14-claude-portfolio.md, idea d. Gate: rule 4 (quant-critic, unit suite, a forward
    measurement written down with it). Cost: one more scorer call per headline. Owner's answer א of 2026-11-15:
    after the supervisor build.
74. [stocks][time-machine][owner 2026-11-15] A control book with no LLM: rank by news count, 12-1 momentum and size
    on point-in-time data, rebalance on the quant book's schedule, and compare it with the quant book and the news
    book. If the Claude layers cannot beat this control, they add nothing. Why: NBER w35153 finds LLM picks load on
    attention, momentum and size, with no significant abnormal return. Source: research/2026-11-14-claude-portfolio.md,
    idea b. Gate: rule 4 (time machine sweep before and after, quant-critic, unit suite; every variant counted for
    the Deflated Sharpe). Owner's answer א of 2026-11-15: after the supervisor build.

75. [supervisor][spec 13] An alert on dead headline feeds. A failed fetch returns an empty list, so a dead feed looks like
    "no news" (news_live.py). Basic law 2 says nothing fails silently. Not designed in the supervisor spec (section 13).
76. [supervisor][spec 13] An alert on repeated scorer failures. Today they are only written down.
77. [supervisor][spec 13] A standby parent that takes over with no model turn (extends item 39). It is the next step if
    the long-timeout proof of spec section 9 fails and the four daily handovers stay.
78. [supervisor][spec 13] A short lock inside `journal.append` for chained files, so two writers can never interleave a
    row.
79. [supervisor][spec 13] `slot-done` and `postmortem` lines in the three crypto prompts (item 39).
80. [supervisor][step 2 review minors, landed 2026-11-15] Known small gaps of the parent, none of which can lose money or
    skip a stop check:
    (a) An R2 sent at the parent's end says "killed and restarted" even when no restart followed (the kill tripped the
        parent, or a planned stop came first). Give R2 an end-of-parent form.
    (b) A handover whose mark pair spans more than mark_gap_max_seconds is booked from the earlier mark. Book it from
        the handover's sup_stop.
    (c) A machine pause of 160-180 s is not detected as a pause (the threshold is hang_seconds). With hang kill on, it
        gives one needless restart and an R2. Detect a pause from a smaller tick gap.
    (d) A kill between a SELL's journal row and the book's save can leave the book holding the name; the next engine
        sells again, so the journal gets two SELL rows for one position (the book's cash is right; realized P&L read
        from the journal is doubled). At start, on a SELL mismatch, let the book follow the journal, or tag the second
        sale.
    (e) A pause whose R4 was skipped for a pending first up gets no line if that up never comes (a trip, a halt or a
        planned stop first); R11 counts it at the close.
    (f) S2 has no once-per-conflict rule: a lasting git conflict repeats S2 from each slot in market hours.
    (g) R4c names the positions of the day's last up, not the book.
    (h) No "back" line after an urgent R3, R3c or R5c when the relaunch comes back within outage_report_seconds.
    (i) Drill e never produces a book mismatch, so its PASS is not coverage of check 4 and E1 (unit tests pin them).
    (j) `--status` prints engine.stop_age_s in wall-clock seconds (about 63,000 at 09:30 with a name held overnight); no
        prompt reads it.
    (k) supervise.MAX_AGE_S (30 days) is a literal: move it to a supervisor key with Task 22, the next change to
        config.json.


81. [report][accuracy] The market line of reports/YYYY-MM-DD.md can show a stale benchmark quote after the close:
    2026-11-18 close report said 'SPY 728.565, updated 15:52:53 UTC' while the close was 730.20 (Yahoo 1d,
    regularMarketTime 21:00 UTC; equity.jsonl bench_price 730.20). Display only: decisions and the baseline returns use
    the close. Basic law 2 (price age is tracked): find where market_status gets that quote and show its age or the close.
82. [stocks][risk][rule] The sector cap (`risk.max_sector_pct` 0.30) does not count a sector ETF with its sector:
    `universe` labels XLV 'SectorETF', so on 2026-11-19 the cap saw Health at 19.1% (TEVA 3.8, JNJ 3.9, ABBV 4.0,
    LLY 2.8, MRK 2.4, AMGN 2.2) while XLV added 9.9% more health exposure (~29% together; weights from
    reports/2026-11-19.md targets). That day's health sell-off stopped out XLV, TEVA and MRK together (fills
    2026-11-20 open: -425.10, -413.17, -241.08 of the -1,532.54 total; state/trades.jsonl; loss review of
    stocks:f854cc7b, 95900f0b, c03e84a5, f4b5248b, planned_loss). One day, one case: a rule change, not a defect, and the strategy freeze of
    2026-11-16 holds. Candidate for rule 4 when the freeze allows: map each sector ETF to its sector for the cap.
83. [desk][sizing] A desk 'Hold' on a new entry is documented as "shrink to 50%" (skills/trading-desk/SKILL.md step 5),
    but for a new name it can act as a veto: the halved target falls under the rebalance band
    (`risk.rebalance_band_pct` 0.02) and `broker.rebalance` skips any non-exit order with |target - current| < band
    (the `force` path covers only shrinks of held names). 2026-11-20 close: raw targets PG 2.36%, V 2.38%, COST 2.66%
    (state/pending.json targets_raw) were halved to 1.18%, 1.19%, 1.33% by three desk Holds, and none of them is in
    the orders for the 2026-11-23 open (preview_at_close: only the XLP 32 entry is a buy). Reduce-only, so allowed by
    hard rule 3, but the record says shrink while the effect is veto. Options for rule 4: let a desk shrink of a new
    entry bypass the band (like `force`), or document that Hold on a sub-2x-band entry vetoes it.
84. [crypto][defect, pre-existing, latent] Two gaps in the Coinbase guard path, found by the backlog 72 gate
    (live-path review and quant-critic, 2026-11-23, workflow wf_41efa60e-d60), not added by it:
    (a) data.coinbase_close (data.py:237-241) catches only RuntimeError/TypeError/ValueError/IndexError; a reply shaped
    like [{...}] raises KeyError at r[0] and an infinite timestamp raises OverflowError at int(r[0]); either escapes
    _coinbase_guard and aborts the crypto decision (checked by the reviewer with a stubbed KeyError: modes log and off
    fail the same way). (b) _coinbase_guard writes unrounded gaps (cycle.py:244); with a NaN decision close it would
    write NaN into the hash-chained decisions.jsonl (journal.py uses json.dumps with the default allow_nan). Neither
    seen live (a stale or absent close skips the run first). data.py is on the rule-4 list: the fix gets the crypto
    sweep before and after, the quant-critic and the unit suite.


## Done
- 2026-11-24: backlog 85 done (loss review stocks:09c0dbc4, verdict bad_data): the live trailing-stop peak is now scaled on each cash-dividend ex-date by the feed's own factor (broker.apply_corporate_actions, merged 72968ef9 from c74ff3c8 + 623dee70; 952 tests OK; registered sweep identical before/after; quant-critic, live-path and re-review PASS). Owner's answer א (2026-11-24): one-off peak_close correction in portfolio.json and shadow_portfolio.json (CVX 219.89 -> 218.08, AMGN 468.11 -> 465.42, COP 142.28 -> 141.35; commit 48452a39). XOM was kept by the ranking without the defect (rank 24 of the keep limit 30). Leftover nonblocking: the shadow-book call has no test; a non-finite dividend amount could reach cash; a stale events file still advances ca_applied_through.
- 2026-11-14: backlog 23 done (weekly review): the paired sweep re-run on code 3d5b1109 (run 2026-11-14-59a459da5016,
  state/trial_runs/): base Sharpe median 0.418 (registered 2026-11-09: 0.402), CAGR 7.40% (7.23%), maxDD -11.52%
  (-11.52%); the change is the five new trading days at the end of the history, the stock book is unchanged by the
  crypto build (the golden tests agree). DSR 0.559 (N=74); P(Sharpe > SPY) 0.195. Placebo not re-run (first
  Saturday of December). Original item: [measurement] No stock sweep or placebo run is registered after the crypto-build changes to strategy.py,
      backtest.py and learn.py (the golden tests show the stock book byte-identical): re-run the paired sweep at the
      weekly review so the evidence matches the code.
- 2026-11-13: backlog 70 fixed (d2e0c77e, quant-critic PASS + live-path review PASS, 696 tests): on the UTC
  daily calendar a daily row that Yahoo returns all-null is rebuilt from Yahoo's 24 complete 1h bars of the same
  day (all coins or none, never overwriting a daily value, logged in decisions/pending, R6 tagged yahoo_1h); any
  other case keeps the backlog 68 skip. Follow-ups: item 71. Original item:
  70. [crypto][defect-timing] Yahoo's daily row for the day that just closed has close null at 00:12 UTC, two nights
      running (2026-11-12 for bar 11-11, backlog 68; 2026-11-13 for bar 11-12: the chart call at 00:14 UTC returned the
      11-12 timestamp with close None, which `_bars_from_chart` drops). Since the backlog 68 fix the 00:12 decide slot
      then makes no decision, and the decision waits for a later run. On 2026-11-13 this delayed a rule exit: with the
      Coinbase close of 11-12 (71,369.90) BTC was -2.34% under its 200-day average (73,081.1), below the 2% hysteresis
      band (71,619.5) -> risk_off -> flat under crypto_base (`logs/2026-11-13-crypto-night.md`). Options, each through
      rule 4: (a) the cycle retries inside the slot until the row fills or a deadline before exec_ts; (b) take the
      Coinbase daily close when Yahoo's row is null (a data-source change: log-only first, compare the two closes);
      (c) move the decide slot later (the owner's schedule; measure first when Yahoo fills the row - the poll of
      2026-11-13 is in the night log). Answers the "not measured" line of item 69.
- 2026-11-12: backlog 68 fixed (df8042e2, quant-critic PASS, 679 tests): on the UTC daily calendar a decision bar
  that is not yesterday's (a daily row missing from Yahoo's reply) is no decision; the pending fill still runs.
  Built on Opus with the owner's approval (Fable limit reached). Critic's non-blocking follow-ups: write the reason
  to skips.jsonl so the morning summary says why and counts repeats; one alert per run while the row is missing
  (queued at night); an urgent alert when no decision holds while a pending order is past its fill cap.
- 2026-11-10 (final gate of wave 3, PASS on base 0215537a; the merge onto e6a82895 has had no gate round: item 54):
  two documented changes in behaviour on bad input, both toward safety. With a quote whose time cannot be read, the
  stop and the time exit now act on the price (before, that name had no stop check in that step) while buys and
  operator exits treat it as not live; a scorer answer that is not a whole number (text, null, 9.5) is no longer
  taken as a score.
- 2026-11-10 (third wave, item 26): news-exit follow-ups. The engine waits at most news.exits_lock_wait_seconds
  (1.0) on the requests lock, after its sales; the book is on disk before a request is cleared (a save that fails
  keeps the request); an unusable requests file reaches the owner once; `news-exit SYMBOL --cancel`; the symbol is
  checked; a request made during the price loop stays (tested); the lever is in the config note and in
  skills/trader/SKILL.md 3ב.
- 2026-11-10 (third wave, item 27): news_predictions rows carry the scorer's model and prompt stamp under the names
  the score rows use (`context` stays on the score row). Three measurement files, outside the hash chains:
  news_scorer_calls.jsonl (per call: sent, answered or error type, time, cost, tokens), news_seen_log.jsonl (what
  became of every new headline), news_health.jsonl (the engine's own speed, one row per news.health_log_seconds).
  Covers the journaling half of item 17 and the cost half of item 18.
- 2026-11-10 (third wave, item 31): the suite removes its temporary state and report directories. One run of the
  495 tests in an isolated TMPDIR left one entry: the second check's own empty directory (aitrader-scorer), which
  is kept on purpose.
- 2026-11-10 (third wave, item 32): the price is kept when the quote time is odd; an undated price drops the old
  stamp; news-score gates the move by the session; "price is back" wording; a failed move calculation is journaled
  once per day per error type. Also: no scorer reply can fail a step any more. Trading changes, on bad input only:
  an undated price buys nothing and fires no bad-news or operator exit (the stop still fires on any price); a score
  that is not a whole number is skipped ("9" as text, 8.6, 9.5 and true used to be read as 9, 8, 9 and 1).
- 2026-11-10 (third wave, time machine): every sweep row prints a seeded 95% block-bootstrap range and paired
  probabilities against SPY and the base (config "bootstrap"; none under min_blocks x block_days days); the
  Deflated Sharpe is printed in both readings and on every base phase; a registered sweep keeps a run record under
  state/trial_runs/ (out of git) for `backtest --compare`; `backtest --drift` lists every live fill against the
  open a replay fills at (read-only). No registered number or existing column changed
  (research/2026-11-10-time-machine-honesty.md).
- 2026-11-10 (third wave, a gate finding closed by e6a82895): a step that fails after its stop check no longer
  loses the sale's report. The step says what it already did also when it fails.
- 2026-11-11 (after the MU loss review): 51 test pins for the loss protocol and the engine repairs landed as
  tests/test_loss_protocol_pins.py (442 tests; 412 of 420 mutants killed, 76 survived the suite before). Tests only.
- 2026-11-10 (loss review, MU -137.70; commit e6a82895): the loss protocol is law (CLAUDE.md, skills/trader/SKILL.md
  3א-3ב) and has a tool (`postmortem`, state/postmortems.jsonl) wired into the five trading slots and the weekly
  one; news buys wait for the review of a news loss; `news-hold`; no buy on an unknown move, and a day missing from
  Yahoo's reply is an unknown move; stops are looked at first in every step, between batches and after any slow
  call; the book is saved with every trade; an alert when a stop traded while nobody looked (`stop_catchup`);
  one engine per book; the engine is started as a tracked background task (both watchdog prompts); score rows carry
  link, description, model, prompt and context stamps, the heartbeat carries the code stamp (item 27: done for
  score rows; predictions join by id); three new guards in log mode (items 15, 16: in code as no_chase, not
  enforced).
- 2026-11-10 (second wave): the price is never lost to the move calculation; no fallback to an older close; the
  blind-stop alert is retried until delivered and cannot abort a step; the scorer gets null outside the session;
  operator exit lever (`news-exit`, state/news_exits.json, live quote only, no buy-back that day); the unit suite
  can no longer reach the owner's phone; scheduled tasks moved off the main session (it can only be used from the
  owner's trusted devices now).
- 2026-11-10: news scorer input fixed (day move from the daily bars, in percent, journaled; null before the
  session); blind-stop alert (news.stop_blind_alert_seconds); second engine watchdog at minute 37; the dashboard
  session no longer starts the engine (exactly one engine, in the trader session).
- 2026-11-09: overrides bypass the rebalance band (explicit shrinks always trade); reduce-only invariant asserted
  in code; untrusted_news + data_quality in the brief; desk canary, rebuttal round, Munger inversion.
