# Improvement backlog (the weekly review takes the top open item)

Every item: implement behind a config switch -> paired sweep before/after (strategy-time-machine) -> quant-critic
PASS -> only then merge. Sources: research/2026-11-09-repo-sweep-take-list.md, research/*.md, critic notes.

## Open (priority order)
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

## Done
- 2026-11-10: news scorer input fixed (day move from the daily bars, in percent, journaled; null before the
  session); blind-stop alert (news.stop_blind_alert_seconds); second engine watchdog at minute 37; the dashboard
  session no longer starts the engine (exactly one engine, in the trader session).
- 2026-11-09: overrides bypass the rebalance band (explicit shrinks always trade); reduce-only invariant asserted
  in code; untrusted_news + data_quality in the brief; desk canary, rebuttal round, Munger inversion.
