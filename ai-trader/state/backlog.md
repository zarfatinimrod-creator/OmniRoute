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
26. [news][ops] news-exit follow-ups from the gate of 2026-11-10 (PASS with should-fix). Until they land, do not
    rely on an exit request made off-hours: the engine must not wait without limit on the requests lock (non-blocking
    lock with a bounded retry); save the book right after a sale and before the request is cleared; an unreadable
    requests file must reach the owner as an event, not only news_errors.jsonl; add `news-exit SYMBOL --cancel`;
    validate the symbol; document the lever in the skill and in the config note; test a re-request made during the
    price loop.
27. [news][measurement] Mark every score and prediction with the scorer model and a hash of the prompt. The forward
    record now pools three scorer versions (broken input on 2026-11-09, fixed input, session-gated null), so
    "before and after" can only be told apart by timestamp.
28. [news][risk] The priced-in rule now really softens negative scores on a stock that already fell, so the
    bad-news exit (score <= 2) on a held name fires less. Owner/critic decision: never soften a negative score.
29. [news][signal] Before the open and after the close the scorer gets no move (null), and in session the brake uses
    the stock's own move with no market reference (on 2026-11-09, 39 of the 74 names were up 2% or more). Pass a
    pre-market move and the benchmark's move; ties to item 15.
30. [news][model] Compare scorer models on the same headlines (agreement, delay, cost). Haiku 5.5 today; the owner's
    standing order is Fable 5.2 for all work, and the scorer is his decision with these numbers.
31. [tests] The suite leaves its temporary state directories in /tmp (13,155 found on 2026-11-10): remove them in
    tearDown.
32. [news] Small ones from the gate: a non-numeric quote time still loses the price; a reply with no quote time
    keeps the previous stamp; news-score should gate the move like the engine does; the "price is back" line still
    says the stop "is checked again"; a failed move calculation leaves no record.

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

## Done
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
