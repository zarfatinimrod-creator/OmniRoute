# Improvement backlog (the weekly review takes the top open item)

Every item: implement behind a config switch -> paired sweep before/after (strategy-time-machine) -> quant-critic
PASS -> only then merge. Sources: research/2026-11-09-repo-sweep-take-list.md, research/*.md, critic notes.

## Open (priority order)
First, from the MU loss review of 2026-11-10 (defects and owner decisions): 33, 44, 34, 35, 39, 40 - then the list below.
1. [defect] Learning label credits the overnight gap: learn.forward_excess uses close(d)->close(d+h) but fills are
   at open(d+1). Use open(d+1)->open(d+1+h); mature at asof-h-1; rerun placebo; add a test that the label equals
   the return the backtest earns (qlib leak-gap 2; FinRL-Trading label assertion).
2. [parity] Backtest ignores earnings_blackout/earnings_max_position_pct; build a point-in-time earnings table from
   SEC 8-K Item 2.02 acceptance times (day-trader-skill trader-analyst/facts.py) and apply in both paths. Live
   cooldown uses BDay (ignores NYSE holidays) - use the trading-day index.
3. [signal] SEC Form 4 opportunistic insider purchases (officers/directors, code P, Cohen-Malloy-Pomorski routine
   filter, cluster count) - strongest evidence in the research; start as a log-only overlay, promote only after a
   forward record + placebo gate.
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
23. [measurement] No stock sweep or placebo run is registered after the crypto-build changes to strategy.py,
    backtest.py and learn.py (the golden tests show the stock book byte-identical): re-run the paired sweep at the
    weekly review so the evidence matches the code.
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
63. [news][owner] The law says a news-exit is not undone, and the merge added `news-exit --cancel`. One sentence in
    CLAUDE.md and SKILL.md 3ב: a waiting request is cancelled only on the owner's word, and the cancel is logged.

## Done
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
