"""The Time Machine: replay history day by day with the exact live decision code.

Decisions use data up to the close of day t and execute at the open of day t+exec_lag (default 1), with slippage
(plus costs.exec_delay_bps, a backtest-only cost of the delay between the close and the fill).
Signal weights are learned walk-forward (only from outcomes matured before each date).
Never trust one run: `sweep()` re-runs under different cost/parameter assumptions; if the
conclusion flips between reasonable assumptions there is no conclusion, only sensitivity.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, journal
from .broker import PaperBroker
from .learn import walk_forward_weights
from .metrics import boot_cfg, boot_error, boot_rows, summary
from .signals import compute_all
from .strategy import build_targets, periods_per_year, precompute_aux


def _px(row: pd.Series) -> dict:
    return {k: float(v) for k, v in row.items() if pd.notna(v) and v > 0}


def run(panel: dict, cfg: dict, start: str, end: str | None = None, weights_mode: str = "learned",
        rebalance_every: int | None = None, signals: dict | None = None, aux: dict | None = None, phase: int = 0,
        exec_lag: int = 1) -> dict:
    """exec_lag: bars from the decision close to the fill open. 1 = the next open (live); 2 = one bar later (the
    crypto sweep's missed-night run). Every decision fills exactly exec_lag bars after it, in order."""
    if exec_lag < 1:
        raise ValueError(f"exec_lag must be >= 1, got {exec_lag}")
    close = panel["close"]
    dates = close.loc[start:end].index if end else close.loc[start:].index
    if len(dates) < 30:
        raise ValueError("not enough dates in range")
    signals = signals or compute_all(panel, cfg)
    aux = aux or precompute_aux(panel, cfg)
    rebalance_every = rebalance_every or cfg["risk"].get("rebalance_every_days", 5)
    prior = cfg["prior_weights"]
    if weights_mode == "learned" and cfg["learning"].get("enabled", True):
        gate = (journal.load_json("placebo.json", {}) or {}).get("gate_z95")  # noise level, not return direction
        wmap = walk_forward_weights(signals, close, prior, cfg, list(dates), gate=gate)
    else:
        wmap = {d: prior for d in dates}

    r = cfg["risk"]
    costs = cfg["costs"]
    broker = PaperBroker(cfg["account"]["starting_cash"], costs["slippage_bps"] + costs.get("exec_delay_bps", 0),
                         costs["commission_per_share"], None, costs.get("qty_step", 1), costs.get("fee_bps", 0.0))
    queue = []  # (fill bar index, targets or None = exits only, stopped symbols)
    equity, turnover, all_fills = {}, {}, []
    prev_regime, prev_dd = None, None
    for i, d in enumerate(dates):
        ds = str(d.date())
        cpx = _px(close.loc[d])
        while queue and queue[0][0] <= i:
            _, pending, pending_stopped = queue.pop(0)
            exits_only = pending is None
            if exits_only:  # built at fill time: positions bought after the decision (exec_lag > 1) are kept
                pending = {s_: 1.0 for s_ in broker.positions if s_ not in pending_stopped}
            opx = _px(panel["open"].loc[d])
            exec_px = {**cpx, **opx}  # trade at the open; fall back to close if the open is missing
            eq_before = broker.equity(exec_px)
            cool = str(dates[min(i + r.get("stop_cooldown_days", 10), len(dates) - 1)].date())
            fills = broker.rebalance(pending, exec_px, ds, r["rebalance_band_pct"], r["min_trade_value"], pending_stopped, cool, exits_only)
            turnover[d] = sum(f["value"] for f in fills) / max(eq_before, 1e-9)
            all_fills.extend(fills)
        equity[d] = broker.mark(cpx, ds, cfg["account"]["cash_yield_annual"], periods_per_year(cfg))
        blocked = set(broker.state.get("blocked", {}))
        on_cycle = (i + phase) % rebalance_every == 0
        broker.maybe_reset_peak(prev_regime or "", ds, r.get("dd_reentry_days", 20), r["dd_halve"], r["dd_flat"], r.get("dd_reentry_ref"))
        targets, diag = build_targets(d, panel, signals, wmap[d], cfg, broker.peak_ratio(cpx), broker.positions, blocked, aux)
        # same trigger as live: scheduled rebalance, or any regime / drawdown-state change, or a flat breaker
        changed = (prev_regime is not None and diag.get("regime") != prev_regime) or (prev_dd is not None and diag.get("dd_state") != prev_dd)
        broker.state["dd_state"] = diag.get("dd_state")
        prev_regime, prev_dd = diag.get("regime", prev_regime), diag.get("dd_state", prev_dd)
        if on_cycle or changed or diag.get("dd_state") == "flat":
            queue.append((i + exec_lag, targets, diag.get("stopped", [])))
        elif diag.get("stopped"):  # off-cycle day: act on stops only (exits-only, like live)
            queue.append((i + exec_lag, None, diag["stopped"]))

    eq = pd.Series(equity)
    to = pd.Series(turnover, dtype=float)
    bench = cfg.get("benchmark", "SPY")
    spy = close[bench].loc[dates] if bench in close else None
    ew = close.loc[dates].pct_change(fill_method=None).mean(axis=1).fillna(0).add(1).cumprod() * cfg["account"]["starting_cash"]
    rf = cfg["account"]["cash_yield_annual"]
    res = {
        "strategy": summary(eq, to, rf, periods_per_year(cfg)),
        "benchmark_spy": summary(spy / spy.iloc[0] * cfg["account"]["starting_cash"], rf_annual=rf, periods_per_year=periods_per_year(cfg)) if spy is not None else {},
        "benchmark_equal_weight_universe": summary(ew, rf_annual=rf, periods_per_year=periods_per_year(cfg)),
        "n_trades": len(all_fills),
        "final_weights": wmap[dates[-1]],
        "final_positions": {k: v["qty"] for k, v in broker.positions.items()},
    }
    res["_equity"] = eq
    res["_fills"] = all_fills
    res["_bench_equity"] = {"benchmark": spy, "equal_weight": ew}  # the day series behind the two benchmark summaries
    return res


_G: dict = {}


def _variants(cfg: dict) -> list[tuple]:
    base_every = cfg["risk"].get("rebalance_every_days", 5)
    return [
        ("base", {}, "learned", base_every),
        ("prior weights (no learning)", {}, "prior", base_every),
        ("costs 15bps", {"costs": {"slippage_bps": 15}}, "learned", base_every),
        ("costs 30bps", {"costs": {"slippage_bps": 30}}, "learned", base_every),
        ("daily rebalance", {}, "learned", 1),
        ("monthly rebalance", {}, "learned", 21),
        ("target vol 10%", {"risk": {"target_vol_annual": 0.10}}, "learned", base_every),
        ("target vol 16%", {"risk": {"target_vol_annual": 0.16}}, "learned", base_every),
        ("no regime filter", {"risk": {"risk_off_gross_mult": 1.0}}, "learned", base_every),
        ("no VIX defensive mode", {"risk": {"defensive_gross_mult": 1.0}}, "learned", base_every),
        ("8 positions max", {"risk": {"max_positions": 8}}, "learned", base_every),
        ("ETF-only universe (no survivorship bias)", {"_etf": True}, "learned", base_every),
    ]


def _job(args):
    name, override, mode, every, phase = args
    c = copy.deepcopy(_G["cfg"])
    panel, signals = _G["panel"], _G["signals"]
    if override.get("_etf"):
        etf = [k for k, v in c["universe"].items() if v in ("Index", "SectorETF", "Bonds", "Gold")]
        panel = {k: (v[etf] if isinstance(v, pd.DataFrame) else v) for k, v in panel.items()}
        c["universe"] = {k: c["universe"][k] for k in etf}
        c["risk"]["max_positions"] = 6
        signals = None
    for sec, kv in override.items():
        if not sec.startswith("_"):
            c[sec].update(kv)
    res = run(panel, c, _G["start"], _G["end"], mode, every, signals=signals, aux=precompute_aux(panel, c), phase=phase)
    out = {"variant": name, "phase": phase, "trades": res["n_trades"], **res["strategy"]}
    out["_daily"] = res["_equity"].pct_change().dropna()  # every run: the ranges and the run record are built from these
    if name == "base" and phase == 0:
        out["_bench"] = {"SPY buy&hold": res["benchmark_spy"], "Equal-weight universe": res["benchmark_equal_weight_universe"]}
        be = {"SPY buy&hold": res["_bench_equity"]["benchmark"], "Equal-weight universe": res["_bench_equity"]["equal_weight"]}
        out["_bench_daily"] = {label: eq.dropna().pct_change().dropna() for label, eq in be.items() if eq is not None}
    return out


def sweep(panel: dict, cfg: dict, start: str, end: str | None = None, workers: int = 4, detail: dict | None = None) -> pd.DataFrame:
    """Every variant x every weekly rebalance phase, compared PAIRED with the base at the same phase.
    Read the median and the win count, never one row: a change is real only if it wins in most phases.
    Each row also carries its bootstrap range (sharpe/cagr/maxdd _lo, _hi) and the paired probabilities p_gt_bench and
    p_gt_base (metrics.boot_rows; settings: config "bootstrap" over metrics.BOOT_DEFAULTS), unless the window is
    shorter than the floor: then the rows stay as they were and detail["ranges_error"] says why. `detail`, when given,
    is filled with what register() saves: per-phase rows, every run's daily returns, the bootstrap settings and the
    Deflated-Sharpe readings (the rule, the cost-rows-out reading, the rule on every base phase)."""
    from concurrent.futures import ProcessPoolExecutor

    info = {} if detail is None else detail
    info["code"] = code_commit()  # read before the runs: the code that is loaded now, not what the tree holds later
    _G.update({"panel": panel, "cfg": cfg, "start": start, "end": end, "signals": compute_all(panel, cfg)})
    base_every = cfg["risk"].get("rebalance_every_days", 5)
    jobs = []
    for name, ov, mode, every in _variants(cfg):
        phases = [0] if every == 1 else list(range(base_every)) if every == base_every else [k * (every // base_every) for k in range(base_every)]
        jobs += [(name, ov, mode, every, k) for k in phases]
    with ProcessPoolExecutor(max_workers=workers) as ex:  # fork: workers share the panel without pickling
        results = list(ex.map(_job, jobs))
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in results])
    base = df[df.variant == "base"].set_index("phase")
    rows = []
    for name, g in df.groupby("variant", sort=False):
        g = g.set_index("phase")
        paired = [(g.at[k, "sharpe"] - base.at[k % base_every, "sharpe"]) for k in g.index if (k % base_every) in base.index]
        rows.append({
            "variant": name, "phases": len(g), "sharpe_med": round(g.sharpe.median(), 3), "sharpe_min": round(g.sharpe.min(), 3),
            "sharpe_max": round(g.sharpe.max(), 3), "wins_vs_base": f"{sum(x > 0 for x in paired)}/{len(paired)}" if name != "base" else "-",
            "d_sharpe_med": round(float(pd.Series(paired).median()), 3) if name != "base" else 0.0,
            "cagr_med": round(g.cagr.median(), 4), "maxdd_med": round(g.max_drawdown.median(), 4), "calmar_med": round(g.calmar.median(), 3),
            "turnover_med": round(g.turnover_annual.median(), 2), "psr_med": round(g.psr_vs_0.median(), 3)})
    b0 = next(r for r in results if r["variant"] == "base" and r["phase"] == 0)
    for label, bm in b0["_bench"].items():
        rows.append({"variant": label, "sharpe_med": bm.get("sharpe"), "cagr_med": bm.get("cagr"), "maxdd_med": bm.get("max_drawdown"),
                     "calmar_med": bm.get("calmar"), "psr_med": bm.get("psr_vs_0")})
    try:  # Deflated Sharpe of the base: deflated by every configuration ever registered + this sweep
        from .metrics import dsr
        n_prev = sum(len(t.get("rows", [])) for t in journal.read("trials.jsonl") if "rows" in t)
        srs = df.groupby("variant").sharpe.median() / (periods_per_year(cfg) ** 0.5)
        rf_d = (1 + cfg["account"]["cash_yield_annual"]) ** (1 / periods_per_year(cfg)) - 1
        daily = pd.Series(b0["_daily"]) - rf_d
        rows.append({"variant": f"DSR of base (N={n_prev + len(srs)} trials)", "psr_med": round(dsr(daily, n_prev + len(srs), float(srs.std())), 3)})
    except Exception as e:  # noqa: BLE001 - informative only
        rows.append({"variant": f"DSR unavailable: {type(e).__name__}"})
    ppy = periods_per_year(cfg)
    rf_d = (1 + cfg["account"]["cash_yield_annual"]) ** (1 / ppy) - 1
    try:  # the DSR row above is the rule (same inputs here); the second reading shows how far the convention moves it
        cost = [name for name, ov, *_ in _variants(cfg) if set(ov) == {"costs"}]  # the same trades at another cost

        def reading(s: pd.Series) -> dict:
            return {"value": round(dsr(daily, n_prev + len(srs), float(s.std())), 3), "rows_in_spread": len(s),
                    "spread_annual": round(float(s.std()) * ppy ** 0.5, 4)}

        own = {r["phase"]: pd.Series(r["_daily"]) - rf_d for r in results if r["variant"] == "base"}  # each phase's days
        info["dsr"] = {"series": "base, phase 0, daily excess returns", "n": n_prev + len(srs), "n_prior_rows": n_prev,
                       "n_sweep": len(srs), "rule": reading(srs), "alt": {**reading(srs.drop(cost)), "left_out": cost},
                       # the rule's N and spread on every base phase (index = phase): phase 0 is the registered one
                       "base_phases": [round(dsr(own[k], n_prev + len(srs), float(srs.std())), 3) for k in sorted(own)]}
    except Exception as e:  # noqa: BLE001 - informative only, like the DSR row (which names its own failure)
        info["dsr_error"] = type(e).__name__
    # new columns only: a failure here, building the frame of daily returns included, must not cost the table above
    # or the registration of the sweep
    try:
        runs = pd.DataFrame({**{(r["variant"], r["phase"]): r["_daily"] for r in results},
                             **{(label, 0): s for label, s in b0["_bench_daily"].items()}}).dropna()  # the days every run has
        info.update({"daily": runs, "phase_rows": df.to_dict("records")})
        pairs = {name: "base" for name, *_ in _variants(cfg) if name != "base"}
        boot = boot_rows(runs, rf_d, ppy, boot_cfg(cfg), pairs, "SPY buy&hold")
        for row in rows:
            row.update(boot["rows"].get(row["variant"], {}))
        info.update({"boot": boot["settings"],
                     "phase_rows": [{**r, **boot["phases"][(r["variant"], r["phase"])]} for r in info["phase_rows"]]})
    except Exception as e:  # noqa: BLE001 - named in the report (report.sweep_report), never silent
        info["ranges_error"] = boot_error(e)  # a refusal gives its reason (short history, no seed)
    return pd.DataFrame(rows)


def panel_hash(panel: dict, fields=("close",)) -> str:
    """sha256 of the prices a run read: dates x symbols x values of each field (default: the closes). A revised bar, a
    slid history window or a renamed symbol gives another hash, so a re-run that differs can be told from a code change."""
    h = hashlib.sha256()
    for f in fields:
        x = panel[f].to_frame() if isinstance(panel[f], pd.Series) else panel[f]
        h.update(json.dumps([f, [str(d) for d in x.index], [str(c) for c in x.columns]]).encode())
        a = x.to_numpy(dtype="float64")
        h.update(np.where(np.isnan(a), np.nan, a).tobytes())  # one bit pattern for every missing value
    return h.hexdigest()


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()


GIT_TIMEOUT_S = 10  # seconds per git call that names the code: plumbing, not a model assumption


def code_commit() -> dict:
    """git rev-parse HEAD of the code that ran ("unknown" when git cannot say: no repository, no git, a call over
    GIT_TIMEOUT_S, any other failure), and whether aitrader/ or config.json held uncommitted changes (None when
    unknown): the commit names the code only when code_dirty is False. Never raises: it must not cost a sweep."""
    root = Path(__file__).resolve().parent.parent

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True,
                              timeout=GIT_TIMEOUT_S).stdout.strip()

    try:  # --no-optional-locks: a status that takes the index lock could fail a commit the live trader makes meanwhile
        return {"commit": git("rev-parse", "HEAD"),
                "code_dirty": bool(git("--no-optional-locks", "status", "--porcelain", "--", "aitrader", "config.json"))}
    except Exception:  # noqa: BLE001 - the commit is a label on the record; a sweep runs without it
        return {"commit": "unknown", "code_dirty": None}


def save_record(kind: str, meta: dict, rows: list, phase_rows: list, daily: pd.DataFrame, panel: dict, cfg: dict) -> dict:
    """Write one sweep as <state>/trial_runs/<run_id>.json.gz, beside the trials.jsonl line that names it: what ran
    (code commit, config hash, price-panel hash and shape), the table rows, the per-phase rows and every run's daily
    returns (columns (row, phase) -> "row|phase"), so a later re-run can be compared row by row (diff_records).
    meta["code"]: code_commit() as read when the sweep started (read now when absent). Returns the keys the trials
    line carries."""
    close = panel["close"]
    prices = sorted(k for k, v in panel.items() if isinstance(v, (pd.DataFrame, pd.Series)))
    meta = dict(meta)
    ident = {"kind": kind, **(meta.pop("code", None) or code_commit()), **meta, "config_sha256": config_hash(cfg),
             "panel": {"sha256": panel_hash(panel), "inputs_sha256": panel_hash(panel, prices), "fields": prices,
                       "first": str(close.index[0].date()), "last": str(close.index[-1].date()),
                       "days": len(close), "symbols": len(close.columns)}}
    run_id = f"{meta['logged_at'][:10]}-{config_hash(ident)[:12]}"
    body = {"run_id": run_id, **ident, "rows": rows, "phase_rows": phase_rows,
            "daily": {"days": [str(d.date()) for d in daily.index],
                      "series": {f"{r}|{k}": daily[(r, k)].tolist() for r, k in daily.columns}}}
    path = journal.STATE / "trial_runs" / f"{run_id}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(body, f, default=str)
    tmp.replace(path)
    return {"run_id": run_id, "record": f"trial_runs/{path.name}", "record_bytes": path.stat().st_size,
            "panel_sha256": ident["panel"]["sha256"], "config_sha256": ident["config_sha256"],
            "commit": ident["commit"], "code_dirty": ident["code_dirty"]}


def register(df: pd.DataFrame, detail: dict, panel: dict, cfg: dict, start: str, end: str | None = None) -> dict:
    """Register a sweep: the trials.jsonl line every later Deflated Sharpe counts (logged_at, start, rows - as before)
    plus the keys of its run record. A record that cannot be written never costs the registration: the line is
    appended either way and names the failure (record_error)."""
    rec = {"logged_at": journal.now_utc(), "start": start, "rows": df.to_dict("records")}
    if detail.get("daily") is not None:
        try:
            meta = {"logged_at": rec["logged_at"], "start": start, "end": end, "code": detail.get("code"),
                    "boot": detail.get("boot"), "dsr": detail.get("dsr")}
            rec.update(save_record("stock_sweep", meta, rec["rows"], detail["phase_rows"], detail["daily"], panel, cfg))
        except Exception as e:  # noqa: BLE001 - the trial still counts
            rec["record_error"] = type(e).__name__
    journal.append("trials.jsonl", rec)
    return rec


def load_record(path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def diff_records(a: dict, b: dict) -> list[dict]:
    """Two run records row by row: what differs in what ran (commit, config, prices) and in each run's daily returns.
    An empty list means the re-run reproduced the registered run exactly."""
    out = [{"what": k, "a": a.get(k), "b": b.get(k)} for k in ("commit", "code_dirty", "config_sha256", "panel")
           if a.get(k) != b.get(k)]
    da, db = a["daily"], b["daily"]
    for key in sorted(set(da["series"]) | set(db["series"])):
        if key not in da["series"] or key not in db["series"]:
            out.append({"what": "run", "row": key, "only_in": "a" if key in da["series"] else "b"})
            continue
        x, y = (pd.Series(d["series"][key], index=d["days"], dtype=float) for d in (da, db))
        gap = (x - y).abs()  # aligned by day; a day only one run has is a difference too
        bad = gap[~((gap == 0) | (x.reindex(gap.index).isna() & y.reindex(gap.index).isna()))]
        if len(bad):
            out.append({"what": "daily", "row": key, "days_differing": len(bad), "first": bad.index[0],
                        "max_abs_diff": float(gap.max())})
    return out


DRIFT_DEFAULTS = {"pause_seconds": 1.5}  # between Yahoo chart calls, which throttle a burst; config "drift" overrides


def raw_opens(sym: str, rng: str) -> dict:
    """{day: the daily open as it traded that day} from one Yahoo chart call. The cached panel cannot serve here: it
    scales old opens down after every dividend, and a fill is compared at the price of its own day. Yahoo's raw opens
    are already divided by later splits, so each is multiplied back by the splits after its day."""
    res = data._chart(sym, rng, "1d")
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    days = [str(d.date()) for d in pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert(tz)]
    splits = data._events_from_chart(res)["splits"]
    return {day: float(o) * math.prod(s["ratio"] for s in splits if s["date"] > day)
            for day, o in zip(days, res["indicators"]["quote"][0].get("open") or []) if o}


def _settled(day: str, cfg: dict, now) -> bool:
    """Is the daily open of `day` final? A stock's is trusted once its session has closed (early in a session Yahoo's
    daily bar can carry a wrong open: data.official_opens); a UTC-daily bar's open is its first print."""
    hours = journal.session_hours(day) if cfg["market"]["calendar"] == "nyse" else None
    return hours is None or now >= pd.Timestamp(day, tz="America/New_York") + pd.Timedelta(hours=hours[1][0], minutes=hours[1][1])


def drift(trades: list[dict], cfg: dict, now=None) -> dict:
    """Paper versus time machine, fill by fill (read-only). For every live fill: its time-machine bar (tm_bar) - the
    symbol's first daily bar after the fill's decision_date, the bar run() fills that decision on at exec_lag 1,
    whatever day the paper fill landed on - the official open of that bar, the price a replay fills at (the open moved
    against the trade by costs.slippage_bps + costs.exec_delay_bps, as run() does) and the gap in basis points and
    dollars with a running total. Positive: the paper book paid more (buy) or received less (sell) than the time
    machine assumes. A row without a decision_date is compared with the open of its own day and says so. A fill whose
    bar's open is not settled yet is listed but left out of the totals. One Yahoo call per symbol, paced."""
    bps = cfg["costs"]["slippage_bps"] + cfg["costs"].get("exec_delay_bps", 0)
    pause = {**DRIFT_DEFAULTS, **cfg.get("drift", {})}["pause_seconds"]
    now = now or pd.Timestamp.now(tz="UTC")
    opens: dict = {}
    for i, sym in enumerate(sorted({t["symbol"] for t in trades})):
        if i:
            time.sleep(pause)
        try:
            opens[sym] = raw_opens(sym, cfg["market"]["history"])
        except Exception as e:  # noqa: BLE001 - a symbol without data is reported in its rows, the others still print
            opens[sym] = type(e).__name__
    rows, total, notional = [], 0.0, 0.0
    for t in trades:
        got = opens[t["symbol"]]
        days = got if isinstance(got, dict) else {}
        dec = t.get("decision_date")
        bar = min((d for d in days if d > dec), default=None) if dec else t["date"]
        o = days.get(bar)
        if isinstance(got, str):
            note = f"no data ({got})"
        elif not o:
            note = f"no daily bar after the decision of {dec}" if dec else "no daily bar for this day"
        elif not dec:
            note = "no decision date on the row: the open of its own day is used"
        else:
            note = "" if bar == t["date"] else f"filled {t['date']}, not on the time-machine bar"
        row = {**{k: t[k] for k in ("date", "symbol", "side", "qty", "price")}, "tm_bar": bar if o else None,
               "official_open": o, "tm_fill": None, "drift_bps": None, "drift_usd": None, "running_usd": None, "note": note}
        if o:
            sign = 1 if t["side"] == "BUY" else -1
            tm = o * (1 + sign * bps / 1e4)
            usd = sign * (t["price"] - tm) * t["qty"]
            row.update({"tm_fill": round(tm, 4), "drift_usd": round(usd, 2) + 0.0,  # + 0.0: never print "-0.0"
                        "drift_bps": round(sign * (t["price"] / tm - 1) * 1e4, 1) + 0.0})
            if _settled(bar, cfg, now):
                total, notional = total + usd, notional + tm * t["qty"]
                row["running_usd"] = round(total, 2) + 0.0
            else:
                row["note"] = "session still open: the daily open is not settled, left out of the totals"
        rows.append(row)
    priced = [r for r in rows if r["running_usd"] is not None]
    return {"rows": rows, "slippage_bps": bps,
            "total": {"fills": len(rows), "priced": len(priced), "notional": round(notional, 2), "drift_usd": round(total, 2),
                      "drift_bps": round(total / notional * 1e4, 2) if notional else None,
                      "max_abs_bps": max((abs(r["drift_bps"]) for r in priced), default=None)}}


def to_json(res: dict) -> str:
    return json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2, default=str)
