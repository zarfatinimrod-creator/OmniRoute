"""Human report (Hebrew labels, English tickers) written to <market.report_dir>/YYYY-MM-DD.md after every cycle
(stocks: reports/, crypto: reports/crypto/)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DISCLAIMER = "> כסף נייר בלבד. זו לא המלצת השקעה. אף מודל לא יודע לחזות את השוק בוודאות."


def _pct(x) -> str:
    return "n/a" if x is None else f"{x:+.2%}"


def _fills(rows: list[dict]) -> str:
    if not rows:
        return "- (אין)\n"
    return "".join(f"- {f['side']} {f['qty']} {f['symbol']} @ {f['price']} (${f['value']:,.0f}) - {f.get('reason', '')}\n" for f in rows)


def write_daily_report(s: dict, cfg: dict | None = None) -> Path:
    """cfg (the book's config) makes the report book-aware: market.report_dir, the benchmark label, the holdings
    label, and the overlays section only where market.overlays is on. Without cfg: the stock report."""
    mk = s.get("market", {})
    book = (cfg or {}).get("market", {})
    bench = (cfg or {}).get("benchmark", "SPY")
    base = s.get("baselines") or {}
    lines = [
        f"# AI Trader - דוח {s['date']}",
        "",
        DISCLAIMER,
        "",
        "## מצב",
        f"- שוק: {'פתוח' if mk.get('is_open') else 'סגור'} (מחיר אחרון {bench}: {mk.get('price')}, עדכון: {mk.get('last_trade_utc')})",
        f"- משטר: **{s.get('regime')}** | ירידה מהשיא: {s.get('drawdown')} ({s.get('dd_state')})",
        f"- שווי תיק: **${s['equity']:,.0f}** ({s['return_since_start']:+.2%} מההתחלה) | מזומן ${s['cash']:,.0f} | חשיפה {s['gross']:.0%}",
        f"- ספר צל (אותו בוט בלי התערבויות Claude): {_pct(s.get('shadow_return_since_start'))}",
        f"- מול קווי בסיס מאז {s.get('started')}: {bench} {_pct(base.get('bench_since_start', base.get('spy_since_start')))} | שווה-משקל יקום {_pct(base.get('equal_weight_since_start'))}",
        "",
        "## בוצע עכשיו (במחיר הפתיחה)",
        _fills(s.get("executed", [])),
        f"## החלטה אחרונה ({(s.get('pending') or {}).get('decision_date')}) - סטטוס: {(s.get('pending') or {}).get('status')}"
        + (" | ריבלנס" if (s.get('pending') or {}).get('rebalance') else " | רק סטופים"),
        _fills((s.get("pending") or {}).get("preview_at_close") or []),
        "## החזקות",
    ]
    pos = s.get("positions", {})
    if pos:
        lines.append(f"| {'מטבע' if book.get('calendar') == 'utc_daily' else 'מניה'} | כמות | מחיר קנייה | אחרון | רווח/הפסד | מאז |")
        lines.append("|---|---|---|---|---|---|")
        for sym, p in sorted(pos.items(), key=lambda kv: -kv[1]["qty"] * kv[1]["last"]):
            lines.append(f"| {sym} | {p['qty']} | {p['avg_cost']} | {p['last']} | {p['pnl_pct']:+.1%} | {p['since']} |")
    else:
        lines.append("- (אין - הכל במזומן)")
    pend = s.get("pending") or {}
    lines += [
        "",
        "## יעדים (משקל בתיק)",
        ", ".join(f"{k} {v:.1%}" for k, v in sorted((pend.get("targets") or {}).items(), key=lambda kv: -kv[1])) or "(אין)",
        "",
        "## הדירוג הגבוה / הנמוך היום",
        "חזקות: " + ", ".join(f"{k} {v:+.2f}" for k, v in (s.get("top_scores") or {}).items()),
        "",
        "חלשות: " + ", ".join(f"{k} {v:+.2f}" for k, v in (s.get("bottom_scores") or {}).items()),
        "",
        "## משקלות האותות (נלמדים)",
        ", ".join(f"{k} {v:.0%}" for k, v in (s.get("weights") or {}).items()),
        "",
        "## כרטיס ציונים (תחזיות שהבשילו)",
    ]
    card = s.get("scorecard", {})
    lines.append(f"- פתוחות: {card.get('open', 0)} | נבדקו: {card.get('evaluated', 0)}")
    for k, v in card.items():
        if isinstance(v, dict):
            lines.append(f"- {k}: n={v['n']}, אחוז פגיעה {v['hit_rate']:.0%}, תשואה עודפת ממוצעת לקריאות עלייה {v['avg_excess_up_calls']}")
    ov = s.get("overlays") or {}
    if book.get("overlays", True):  # market.overlays off (crypto): no overlay lines at all
        if ov.get("insider_cluster"):
            lines += ["", "## קניות קבוצתיות של בעלי עניין (OpenInsider) - נרשם לבדיקה, בלי כסף עדיין"]
            lines += [f"- {x['ticker']} ({x['company'][:30]}): {x['insiders']} בעלי עניין, ${x['value']:,.0f}, {x['trade_date']}" for x in ov["insider_cluster"][:8]]
        if ov.get("congress_buy"):
            lines += ["", "## קניות של חברי קונגרס (Quiver, 30 יום) - נרשם לבדיקה"]
            lines += [f"- {x['ticker']}: קונים {x['buyers']}, מוכרים {x['sellers']}, אחרון {x['last']}" for x in ov["congress_buy"][:8]]
        elif ov.get("congress_buy") is None:
            lines += ["", "- Quiver: לא מחובר (צריך מפתח API)"]
    if pend.get("overrides"):
        lines += ["", "## התערבויות של Claude (וטו/הקטנה)"] + [f"- {o['symbol']}: {o['action']} - {o['reason']}" for o in pend["overrides"]]
    if pend.get("earnings_blackout"):
        lines += ["", "## חסימת דוחות (לא נכנסים לפני דוח רבעוני)"] + [f"- {k}: {v}" for k, v in pend["earnings_blackout"].items()]
    if s.get("day_moves"):
        lines += ["", "## תנועה היום (החזקות)", ", ".join(f"{k} {v:+.1%}" for k, v in sorted(s["day_moves"].items(), key=lambda kv: kv[1]))]
    if s.get("stopped"):
        lines += ["", "## סטופים", ", ".join(s["stopped"])]
    path = ROOT / book.get("report_dir", "reports") / f"{s['date']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _seen(x) -> bool:
    return x is not None and x == x  # not None, not NaN


def est(x, lo, hi, nd: int = 3) -> str:
    """An estimate next to its range: 0.402 [-0.210, 1.020]."""
    return "n/a" if not _seen(x) else f"{x:.{nd}f}" + (f" [{lo:.{nd}f}, {hi:.{nd}f}]" if _seen(lo) and _seen(hi) else "")


def prob(x) -> str:
    return f"{x:.3f}" if _seen(x) else "-"


def range_notes(level: str, bench: str, base: str = "base") -> list[str]:
    return [
        f"Each estimate is followed by the range it falls in on {level} of the resampled histories. A Sharpe range that "
        "reaches below 0 means even the sign is not established.",
        f"P(Sharpe > {bench}) and P(Sharpe > {base}) are the share of resamples in which the row's Sharpe was the higher "
        "one on the same resampled days (paired; a tie counts half). They are probabilities under resampling, not "
        "verdicts: 0.5 means no difference was seen.",
        "A row is the median over its rebalance phases; the phases hold nearly the same book, so they are not "
        "independent tests. The maxDD range is approximate: reshuffled days break the path the drawdown breaker "
        "reacted to.",
    ]


def record_lines(rec: dict, cfg: dict) -> list[str]:
    """Where a sweep's run record is and what ran (backtest.save_record), or that it could not be saved."""
    if not rec.get("record"):
        return ["## Run record", "", f"NOT saved ({rec.get('record_error', 'no detail kept')}): the sweep is registered in "
                "trials.jsonl without its daily returns, so a later re-run cannot be compared with it."]
    book = cfg.get("market", {}).get("state_subdir", "")  # "" = the stock book; a book's state folder carries its name
    path = "/".join(x for x in ("state", book, rec["record"]) if x)
    dirty = {True: "yes", False: "no"}.get(rec.get("code_dirty"), "unknown")
    return ["## Run record", "",
            f"run {rec['run_id']}: {path} ({rec['record_bytes']:,} bytes) - every run's daily returns, the per-phase rows "
            "and the table rows.",
            f"code commit {rec['commit']} (uncommitted code changes: {dirty}) | config sha256 {rec['config_sha256'][:12]} | "
            f"closes sha256 {rec['panel_sha256'][:12]}",
            f"compare two runs row by row: python3 -m aitrader{' --book ' + book if book else ''} backtest --compare <run A> <run B>"]


def sweep_report(df, detail: dict, rec: dict, cfg: dict) -> str:
    """What a stock time-machine sweep prints under its table: each estimate next to its range, the paired
    probabilities, both Deflated-Sharpe readings (the registered one is the rule) and where the run record is."""
    bench = cfg.get("benchmark", "SPY")
    b, d = detail.get("boot"), detail.get("dsr")
    if b:
        lvl = f"{b['level']:.0%}"
        lines = [f"## Ranges ({lvl} stationary block bootstrap: mean block {b['block_days']} days, {b['draws']} resamples, "
                 f"seed {b['seed']}, {b['days']} days)", "",
                 f"| row | Sharpe [{lvl} range] | CAGR [{lvl} range] | maxDD [{lvl} range] | P(Sharpe > {bench}) | P(Sharpe > base) |",
                 "|---|---|---|---|---:|---:|"]
        lines += [f"| {r['variant']} | {est(r['sharpe_med'], r['sharpe_lo'], r['sharpe_hi'])} | "
                  f"{est(r['cagr_med'], r['cagr_lo'], r['cagr_hi'], 4)} | {est(r['maxdd_med'], r['maxdd_lo'], r['maxdd_hi'], 4)} | "
                  f"{prob(r['p_gt_bench'])} | {prob(r['p_gt_base'])} |" for r in df.to_dict("records") if _seen(r.get("sharpe_lo"))]
        lines += ["", *range_notes(lvl, bench)]
    else:
        lines = [f"## Ranges: not computed ({detail.get('ranges_error', 'the sweep kept no detail')})"]
    if d:
        lines += ["", f"## Deflated Sharpe of the base - two readings (N={d['n']}: {d['n_prior_rows']} rows registered "
                  f"earlier + {d['n_sweep']} variants here; {d['series']})", "",
                  "| reading | variants in the Sharpe spread | spread (annual Sharpe) | DSR |", "|---|---:|---:|---:|",
                  f"| 1. every swept variant, cost-stress rows included | {d['rule']['rows_in_spread']} | "
                  f"{d['rule']['spread_annual']:.4f} | {d['rule']['value']:.3f} |",
                  f"| 2. cost-stress rows left out of the spread ({', '.join(d['alt']['left_out']) or 'none'}) | "
                  f"{d['alt']['rows_in_spread']} | {d['alt']['spread_annual']:.4f} | {d['alt']['value']:.3f} |", "",
                  "The first reading is the rule: it is the number registered in trials.jsonl and the only one a decision "
                  "may use (skills/strategy-time-machine/SKILL.md). The second is printed to show how far the number moves "
                  "with the convention; it is never used to claim an edge, whichever of the two is higher."]
    else:
        lines += ["", f"## Deflated Sharpe readings: not computed ({detail.get('dsr_error', 'the sweep kept no detail')})"]
    return "\n".join(lines + ["", *record_lines(rec, cfg)])


def drift_report(d: dict, cfg: dict) -> str:
    """Paper versus time machine (backtest.drift): every live fill next to the official open a replay fills at."""
    def num(x, fmt):
        return "-" if x is None else format(x, fmt)

    t = d["total"]
    lines = ["# Paper versus time machine - fill drift", "",
             f"Time-machine fill = the official daily open of the fill day, moved {d['slippage_bps']:g} bp against the trade "
             "(costs.slippage_bps + costs.exec_delay_bps): the price a replay of that day fills at. Drift above 0: the paper "
             "book paid more (buy) or received less (sell) than the time machine assumes. The open is the price of that "
             "day itself, not scaled for later dividends or splits.", "",
             "| date | symbol | side | qty | paper fill | official open | time-machine fill | drift bp | drift $ | running $ | note |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    lines += [f"| {r['date']} | {r['symbol']} | {r['side']} | {r['qty']:g} | {r['price']:.4f} | {num(r['official_open'], '.4f')} | "
              f"{num(r['tm_fill'], '.4f')} | {num(r['drift_bps'], '+.1f')} | {num(r['drift_usd'], '+.2f')} | "
              f"{num(r['running_usd'], '+.2f')} | {r['note']} |" for r in d["rows"]] or ["(no fills)"]
    if t["priced"]:
        lines += ["", f"Total: {t['priced']} of {t['fills']} fills priced, notional ${t['notional']:,.2f}, drift "
                  f"{t['drift_usd']:+.2f} $ ({t['drift_bps']:+.2f} bp of notional), largest single drift {t['max_abs_bps']:.1f} bp."]
    else:
        lines += ["", f"Total: 0 of {t['fills']} fills priced."]
    return "\n".join(lines)
