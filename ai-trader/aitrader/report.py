"""Human report (Hebrew labels, English tickers) written to reports/YYYY-MM-DD.md after every cycle."""

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


def write_daily_report(s: dict) -> Path:
    mk = s.get("market", {})
    lines = [
        f"# AI Trader - דוח {s['date']}",
        "",
        DISCLAIMER,
        "",
        "## מצב",
        f"- שוק: {'פתוח' if mk.get('is_open') else 'סגור'} (מחיר אחרון SPY: {mk.get('price')}, עדכון: {mk.get('last_trade_utc')})",
        f"- משטר: **{s.get('regime')}** | ירידה מהשיא: {s.get('drawdown')} ({s.get('dd_state')})",
        f"- שווי תיק: **${s['equity']:,.0f}** ({s['return_since_start']:+.2%} מההתחלה) | מזומן ${s['cash']:,.0f} | חשיפה {s['gross']:.0%}",
        f"- ספר צל (אותו בוט בלי התערבויות Claude): {_pct(s.get('shadow_return_since_start'))}",
        f"- מול קווי בסיס מאז {s.get('started')}: SPY {_pct((s.get('baselines') or {}).get('spy_since_start'))} | שווה-משקל יקום {_pct((s.get('baselines') or {}).get('equal_weight_since_start'))}",
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
        lines.append("| מניה | כמות | מחיר קנייה | אחרון | רווח/הפסד | מאז |")
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
    path = ROOT / "reports" / f"{s['date']}.md"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path
