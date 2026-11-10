"""Crypto sweep: the time-machine gate that decides between crypto_base and the candidate profile.

Spec 2026-11-09-crypto-book-design section 7 ("Sweep", "Pass rule", "DSR") and plan 2026-11-09-crypto-book-v1
planning decision 14. Written down before it runs:
- Window: `start` (CLI default 2018-01-01) to `end` (the last final bar); the halves split at `split` (2022-01-01).
- Each profile runs on its own universe panel, and its signals and aux are recomputed on that panel (crypto_base
  never sees an ETH column). Every run has `phases` paired rebalance phases (default 7: the 7-day cycle).
- Runs: base vs candidate at 50 and at 100 bp fee per side; each half at 50 bp; leave-one-out ablations of the
  candidate (no ETH, no ATR stop, no -25% halving step; the -50% catastrophe step is never ablated); a BTC+XRP
  hindsight control (an in-sweep universe override, never through load_config; XRP's cap is the config's
  risk.max_position_pct_by_symbol["XRP-USD"]); one missed-night run (exec_lag 2).
- Order: ablations first. A component is dropped when the paired median delta Sharpe (ablated - candidate) >= 0. Two
  or more dropped: the combined final candidate runs once more, and that run counts toward N. Then the pass rule on
  the final candidate; any failed rule ships crypto_base. Dropped components are reported as the config change
  books.crypto needs before it can ship (config_change_needed, overrides).
- DSR of the shipped profile on its phase-0 daily returns (the one phase a live book trades; the conservative
  choice, as in the stock sweep): N = every look already in state/crypto/trials.jsonl (the 145 seeded by
  scripts/seed_crypto_trials.py, required, plus any earlier sweep) + this sweep's per-phase runs. The Sharpe spread
  is the std of per-period Sharpes, benchmark rows excluded.
The constants below are that pre-registration (spec 7), not tunable strategy assumptions: the strategy's numbers
stay in config.json (the 50 bp leg must equal the profiles' costs.fee_bps).
"""

from __future__ import annotations

import copy
import functools
import importlib.util
import json
import math
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest, data, journal, report
from .metrics import boot_cfg, boot_rows, dsr
from .signals import compute_all
from .strategy import periods_per_year, precompute_aux

SYMBOLS = ("BTC-USD", "ETH-USD", "XRP-USD")  # XRP only for the hindsight control
SPLIT = "2022-01-01"
FEES_BP = (50, 100)  # fee per side; slippage and exec delay stay the profile's; the first is the profiles' own fee
BOOT_SEED, BOOT_BLOCK, BOOT_DRAWS = 0, 30, 2000  # replays/power.py
WINS_NEED, WINS_OF = 6, 7
P_BOOT_MIN = 0.95
DD_GAP_MAX = 0.02  # median maxDD no more than 2 points worse
FIELDS = ("open", "high", "low", "close", "volume")


def _no_eth(c: dict) -> None:
    c["universe"] = {s: v for s, v in c["universe"].items() if s != "ETH-USD"}


def _no_atr_stop(c: dict) -> None:
    c["risk"]["atr_stop_mult"] = 0.0  # <= 0: no stop check (build_targets)


def _no_halve(c: dict) -> None:
    c["risk"]["dd_halve"] = -1.0  # never reached; the -50% flat step stays
    c["risk"].pop("dd_reentry_ref", None)  # re-entry follows the broker default: dd_flat / 2 without a halving step


@functools.lru_cache(maxsize=1)
def seed_script():
    """scripts/seed_crypto_trials.py as a module (SEED_ID, SEED_ROWS, seed())."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "seed_crypto_trials.py"
    spec = importlib.util.spec_from_file_location("seed_crypto_trials", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _seeded(trials: list[dict]) -> int:
    """Rows of the DSR seed record(s) in a trials log; the sweep refuses to run unless this is exactly SEED_ROWS."""
    return sum(len(t.get("rows", [])) for t in trials if t.get("seed") == seed_script().SEED_ID)


ABLATIONS = {  # component -> (run name, label, how to remove it from a config)
    "eth": ("abl:no_eth", "no ETH", _no_eth),
    "atr_stop": ("abl:no_atr_stop", "no ATR stop", _no_atr_stop),
    "halve": ("abl:no_halve", "no -25% halving step", _no_halve),
}


def _sub(panel_all: dict, syms) -> dict:
    return {f: panel_all[f][list(syms)] for f in FIELDS}


def _rf_daily(cfg: dict) -> float:
    return (1 + cfg["account"]["cash_yield_annual"]) ** (1 / periods_per_year(cfg)) - 1


def _sharpe(eq: pd.Series, cfg: dict) -> float:
    """Annualised Sharpe of returns in excess of cash; an all-cash run (zero variance) is 0."""
    ex = eq.pct_change().dropna() - _rf_daily(cfg)
    sd = ex.std()
    return float(ex.mean() / sd * math.sqrt(periods_per_year(cfg))) if sd > 0 else 0.0


def _run(name: str, cfg: dict, panel_all: dict, start: str, end: str | None, phases: int, exec_lag: int = 1) -> dict:
    """One configuration over `phases` rebalance phases, on the panel of its own universe."""
    p = _sub(panel_all, cfg["universe"])
    sig, aux = compute_all(p, cfg), precompute_aux(p, cfg)
    rows, daily, res = [], {}, {}
    for k in range(phases):
        res = backtest.run(p, cfg, start, end, "prior", cfg["risk"]["rebalance_every_days"], signals=sig, aux=aux,
                           phase=k, exec_lag=exec_lag)
        eq = res["_equity"]
        daily[k] = eq.pct_change().dropna()
        rows.append({"phase": k, "sharpe": _sharpe(eq, cfg), "maxdd": float((eq / eq.cummax() - 1).min()),
                     "cagr": float(res["strategy"].get("cagr", float("nan"))), "n_fills": len(res["_fills"]),
                     "symbols": sorted({f["symbol"] for f in res["_fills"]})})
    hold = res["_bench_equity"]["benchmark"]  # buy&hold of the benchmark coin over the run's window
    return {"phases": rows, "daily": pd.DataFrame(daily), "bench": res.get("benchmark_spy", {}),
            "bench_daily": None if hold is None else hold.dropna().pct_change().dropna()}


def _ranges(runs: dict, daily: dict, hold: dict, cfg: dict) -> tuple[dict, dict]:
    """Bootstrap range and paired probabilities of every run (metrics.boot_rows): Sharpe, CAGR and maxDD of the
    median over its phases, P(Sharpe above buy&hold of the benchmark coin) and P(Sharpe above its paired run), each
    phase against the same phase. Runs over the same window share one set of resampled days. Block length, resample
    count and seed are the sweep's pre-registered bootstrap constants; the level is config "bootstrap" (boot_cfg).
    Returns (settings, {run: {"range": ..., "phases": {phase: ...}}}). Informative only: no pass rule reads it."""
    st = {**boot_cfg(cfg), "block_days": BOOT_BLOCK, "draws": BOOT_DRAWS, "seed": BOOT_SEED}
    windows: dict = {}
    for name, rec in runs.items():
        windows.setdefault(tuple(rec["window"]), []).append(name)
    out = {}
    for names in windows.values():
        cols = {(n, k): daily[n][k] for n in names for k in daily[n].columns}
        if hold.get(names[0]) is not None:
            cols[("hold", 0)] = hold[names[0]]
        boot = boot_rows(pd.DataFrame(cols), _rf_daily(cfg), periods_per_year(cfg), st,
                         {n: runs[n]["pair"] for n in names if "pair" in runs[n]}, "hold")
        for n in names:
            out[n] = {"range": boot["rows"][n], "phases": {k: boot["phases"][(n, k)] for k in daily[n].columns}}
    return st, out


def bootstrap_p(base: pd.Series, cand: pd.Series, ppy: int, seed: int = BOOT_SEED, block: int = BOOT_BLOCK,
                draws: int = BOOT_DRAWS) -> float:
    """Block-bootstrap P(Sharpe_cand - Sharpe_base > 0) on paired daily returns: replays/power.py's loop (moving
    blocks, numpy default_rng(seed)). A resample with zero variance has Sharpe 0."""
    dfr = pd.concat([base, cand], axis=1).dropna().values
    rng = np.random.default_rng(seed)
    n, diffs = len(dfr), []
    if n <= block:
        raise ValueError(f"bootstrap needs more than {block} paired days, got {n}")
    for _ in range(draws):
        starts = rng.integers(0, n - block, n // block + 1)
        x = dfr[(starts[:, None] + np.arange(block)).ravel()[:n]]
        m, sd = x.mean(0), x.std(0)
        s = np.divide(m, sd, out=np.zeros_like(m), where=sd > 0) * math.sqrt(ppy)
        diffs.append(s[1] - s[0])
    return float((np.array(diffs) > 0).mean())


def pass_rule(d50: list, dd_final: list, dd_base: list, p_boot: float, d100: list, d_h1: list, d_h2: list) -> dict:
    """Spec 7's four rules; all must hold. d* are paired per-phase delta Sharpes (final - base), dd_* per-phase maxDD.
    The win count needs 6 of 7 phases (ceil(6/7 of the phases) when a test runs fewer)."""
    n = len(d50)
    need = math.ceil(n * WINS_NEED / WINS_OF)
    wins = sum(x > 0 for x in d50)
    gap = statistics.median(dd_base) - statistics.median(dd_final)  # > 0: the candidate's drawdown is deeper
    m100, h1, h2 = statistics.median(d100), statistics.median(d_h1), statistics.median(d_h2)
    return {
        "phases_won": {"value": f"{wins}/{n}", "need": f">= {need}/{n}", "pass": wins >= need},
        "p_boot": {"value": round(p_boot, 4), "need": f">= {P_BOOT_MIN}", "pass": p_boot >= P_BOOT_MIN},
        "dd_gap": {"value": round(gap, 4), "need": f"<= {DD_GAP_MAX}", "pass": gap <= DD_GAP_MAX},
        "cost100": {"value": round(m100, 4), "need": "> 0", "pass": m100 > 0},
        "halves": {"value": [round(h1, 4), round(h2, 4)], "need": "> 0 each", "pass": h1 > 0 and h2 > 0},
    }


def _diff(ref: dict, c: dict) -> dict:
    """What a run's config changes against its profile (universe, risk, costs)."""
    out = {"universe": list(c["universe"])} if list(ref["universe"]) != list(c["universe"]) else {}
    for blk in ("risk", "costs"):
        for k in sorted(set(ref[blk]) | set(c[blk])):
            if ref[blk].get(k, "unset") != c[blk].get(k, "unset"):
                out[f"{blk}.{k}"] = c[blk].get(k, "unset")
    return out


def run_sweep(panel_all: dict, start: str, split: str, end: str | None = None, phases: int = 7,
              report_path: str | Path | None = None) -> dict:
    """The whole sweep (module docstring). panel_all: wide OHLCV panels holding every symbol in SYMBOLS.
    Writes <crypto state>/dsr.json, appends this sweep's per-phase rows to <crypto state>/trials.jsonl, saves the run
    record beside it (<crypto state>/trial_runs/, backtest.save_record) and writes the report (default
    research/<date>-crypto-sweep.md under report.ROOT), which also carries each run's bootstrap range (_ranges)."""
    base = data.load_config("crypto", "crypto_base")
    cand = data.load_config("crypto", "crypto")
    missing = (set(base["universe"]) | set(cand["universe"]) | {"XRP-USD"}) - set(panel_all["close"].columns)
    if missing:
        raise ValueError(f"crypto sweep: panel lacks {sorted(missing)}")
    if {base["costs"]["fee_bps"], cand["costs"]["fee_bps"]} != {FEES_BP[0]}:
        raise ValueError(f"crypto sweep: the {FEES_BP[0]} bp leg must be the profiles' costs.fee_bps, got "
                         f"{base['costs']['fee_bps']} / {cand['costs']['fee_bps']}")
    with journal.use_book("crypto"):  # fail before ~15 minutes of runs, not after
        if _seeded(journal.read("trials.jsonl")) != seed_script().SEED_ROWS:
            raise RuntimeError("seed missing: run scripts/seed_crypto_trials.py")
    code = backtest.code_commit()  # read before the runs: the code that is loaded now
    ppy = periods_per_year(cand)
    h1_end = str((pd.Timestamp(split) - pd.Timedelta(days=1)).date())
    lo, hi = FEES_BP
    runs: dict = {}
    daily: dict = {}
    bench: dict = {}
    hold: dict = {}  # run -> daily returns of buy&hold of the benchmark coin over the run's window (None: not kept)

    def fee(cfg: dict, bp: int) -> dict:
        c = copy.deepcopy(cfg)
        c["costs"]["fee_bps"] = bp
        return c

    def go(name, cfg, profile, ref, desc, pair=None, s=start, e=end, lag=1):
        out = _run(name, cfg, panel_all, s, e, phases, lag)
        r = cfg["risk"]
        by_sym = r.get("max_position_pct_by_symbol", {})
        sh = [ph["sharpe"] for ph in out["phases"]]
        rec = {"profile": profile, "desc": desc, "universe": list(cfg["universe"]),
               "caps": {s_: by_sym.get(s_, r["max_position_pct"]) for s_ in cfg["universe"]},
               "fee_bps": cfg["costs"]["fee_bps"], "exec_lag": lag, "window": [s, e], "overrides": _diff(ref, cfg),
               "phases": out["phases"], "sharpe_med": statistics.median(sh), "sharpe_min": min(sh), "sharpe_max": max(sh),
               "maxdd_med": statistics.median(ph["maxdd"] for ph in out["phases"]),
               "cagr_med": statistics.median(ph["cagr"] for ph in out["phases"])}
        if pair:
            d = [a["sharpe"] - b["sharpe"] for a, b in zip(out["phases"], runs[pair]["phases"])]
            rec.update({"pair": pair, "d_sharpe": d, "d_sharpe_med": statistics.median(d), "wins": f"{sum(x > 0 for x in d)}/{len(d)}"})
        runs[name], daily[name], bench[name], hold[name] = rec, out["daily"], out["bench"], out.get("bench_daily")
        return rec

    go("base@50", fee(base, lo), "crypto_base", base, "crypto_base")
    go("cand@50", fee(cand, lo), "crypto", cand, "candidate", pair="base@50")
    ablations = {}  # 1. ablations, each paired with the candidate
    for key, (name, label, remove) in ABLATIONS.items():
        c = fee(cand, lo)
        remove(c)
        d = go(name, c, "crypto", cand, f"candidate, {label}", pair="cand@50")["d_sharpe_med"]
        ablations[key] = {"run": name, "label": label, "d_sharpe_med": d, "dropped": d >= 0}
    dropped = [k for k, a in ablations.items() if a["dropped"]]
    final = copy.deepcopy(cand)
    for k in dropped:
        ABLATIONS[k][2](final)
    label = "candidate" + "".join(f", {ABLATIONS[k][1]}" for k in dropped)
    if len(dropped) > 1:  # an untested combination: one more run, counted in N
        go("final@50", fee(final, lo), "crypto", cand, label, pair="base@50")
    final_run = "final@50" if len(dropped) > 1 else ABLATIONS[dropped[0]][0] if dropped else "cand@50"

    # 2. the pass rule on the final candidate
    go("base@100", fee(base, hi), "crypto_base", base, f"crypto_base at {hi} bp")
    go("final@100", fee(final, hi), "crypto", cand, f"{label} at {hi} bp", pair="base@100")
    go("base:h1", fee(base, lo), "crypto_base", base, "crypto_base, first half", e=h1_end)
    go("final:h1", fee(final, lo), "crypto", cand, f"{label}, first half", pair="base:h1", e=h1_end)
    go("base:h2", fee(base, lo), "crypto_base", base, "crypto_base, second half", s=split)
    go("final:h2", fee(final, lo), "crypto", cand, f"{label}, second half", pair="base:h2", s=split)
    ctl = fee(final, lo)
    ctl["universe"] = {"BTC-USD": "Crypto", "XRP-USD": "Crypto"}
    caps = {s: v for s, v in final["risk"]["max_position_pct_by_symbol"].items() if s in ctl["universe"]}
    if "XRP-USD" not in caps:
        raise ValueError("crypto sweep: books.crypto.risk.max_position_pct_by_symbol needs an XRP-USD cap (control)")
    ctl["risk"]["max_position_pct_by_symbol"] = caps
    go("control:btc_xrp", ctl, "control", cand, f"hindsight control: BTC+XRP (XRP cap {caps['XRP-USD']})", pair="base@50")
    go("final:missed_night", fee(final, lo), "crypto", cand, f"{label}, missed night (fill one bar later)", pair="base@50", lag=2)

    fin, b50 = runs[final_run], runs["base@50"]
    d50 = [a["sharpe"] - b["sharpe"] for a, b in zip(fin["phases"], b50["phases"])]
    rf = _rf_daily(cand)
    p_boot = bootstrap_p(daily["base@50"].mean(axis=1) - rf, daily[final_run].mean(axis=1) - rf, ppy)
    pr = pass_rule(d50, [ph["maxdd"] for ph in fin["phases"]], [ph["maxdd"] for ph in b50["phases"]], p_boot,
                   runs["final@100"]["d_sharpe"], runs["final:h1"]["d_sharpe"], runs["final:h2"]["d_sharpe"])
    ship = "crypto" if all(v["pass"] for v in pr.values()) else "crypto_base"
    overrides = _diff(cand, final)  # what books.crypto must change before the final candidate can ship
    final_candidate = {"run": final_run, "label": label, "dropped": dropped, "overrides": overrides}
    change = {"config_change_needed": bool(dropped), "overrides": overrides}

    # 3. trials and the Deflated Sharpe of the shipped profile
    rows = [{"run": name, "profile": rec["profile"], "phase": ph["phase"], "fee_bps": rec["fee_bps"],
             "exec_lag": rec["exec_lag"], "window": rec["window"], "sharpe": round(ph["sharpe"], 6),
             "sharpe_pp": ph["sharpe"] / math.sqrt(ppy), "maxdd": round(ph["maxdd"], 6), "benchmark": False}
            for name, rec in runs.items() for ph in rec["phases"]]
    honest: dict = {}  # ranges for the report and the run record: new numbers only, no rule above or below reads them
    try:
        honest["boot"], ranges = _ranges(runs, daily, hold, cand)
        for name, r in ranges.items():
            runs[name]["range"] = r["range"]
    except Exception as e:  # noqa: BLE001 - named in the report; never costs the sweep its verdict or its registration
        honest["ranges_error"], ranges = type(e).__name__, {}
    phase_rows = [{"run": name, **ph, **ranges.get(name, {}).get("phases", {}).get(ph["phase"], {})}
                  for name, rec in runs.items() for ph in rec["phases"]]
    shipped = final_run if ship == "crypto" else "base@50"
    day = daily[shipped][0] - rf  # phase 0: the single phase a live book trades (conservative vs the phase average)
    with journal.use_book("crypto"):
        prior = journal.read("trials.jsonl")
        prior_rows = [r for t in prior for r in t.get("rows", [])]
        n_seeded = _seeded(prior)
        if n_seeded != seed_script().SEED_ROWS:  # N without the seeded looks would overstate the DSR
            raise RuntimeError("seed missing: run scripts/seed_crypto_trials.py")
        n = len(prior_rows) + len(rows)
        pps = [r["sharpe_pp"] for r in prior_rows + rows if not r.get("benchmark") and r.get("sharpe_pp") is not None]
        spread = float(pd.Series(pps, dtype=float).std())
        value = dsr(day, n, spread)
        out = {"profile": ship, "value": round(value, 4) if math.isfinite(value) else None, "n": n}
        date = journal.now_utc()[:10]
        path = Path(report_path) if report_path else Path(report.ROOT) / "research" / f"{date}-crypto-sweep.md"
        journal.save_json("dsr.json", {**out, **change, "n_seeded": n_seeded, "n_prior": len(prior_rows), "n_sweep": len(rows),
                                       "sr_std_pp": round(spread, 6), "daily_series": f"{shipped}, phase 0 daily excess returns",
                                       "window": [str(day.index[0].date()), str(day.index[-1].date())],
                                       "computed_at": journal.now_utc(), "report": str(path)})
        line = {"logged_at": journal.now_utc(), "kind": "crypto_sweep", "start": start, "split": split,
                "end": end, "phases": phases, "ship": ship, "rows": rows}
        try:  # the run record beside trials.jsonl: every run's daily returns (NaN outside its window), what ran
            meta = {k: line[k] for k in ("logged_at", "start", "split", "end", "phases", "ship")}
            meta |= {"code": code, "boot": honest.get("boot")}
            frame = pd.DataFrame({(n, k): daily[n][k] for n in runs for k in daily[n].columns})
            honest["record"] = backtest.save_record("crypto_sweep", meta, rows, phase_rows, frame,
                                                    {f: panel_all[f] for f in FIELDS}, {"crypto_base": base, "crypto": cand})
        except Exception as e:  # noqa: BLE001 - the trials still count
            honest["record"] = {"record_error": type(e).__name__}
        journal.append("trials.jsonl", {**line, **honest["record"]})
    res = {"runs": runs, "ablations": ablations, "final_candidate": final_candidate, "pass_rule": pr, "ship": ship,
           **change, "dsr": out, "report": str(path), **honest}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_report(res, base, cand, bench["base@50"], date, start, split, end, phases, n_seeded, len(prior_rows),
                            len(rows), spread, day), encoding="utf-8")
    return res


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _report(res, base, cand, btc, date, start, split, end, phases, n_seeded, n_prior, n_sweep, spread, day) -> str:
    pr, d, fc = res["pass_rule"], res["dsr"], res["final_candidate"]
    costs = cand["costs"]
    lines = [
        f"# Crypto sweep - {date}", "",
        f"Source: `aitrader/crypto_sweep.py` run_sweep (spec 2026-11-09-crypto-book-design section 7). Window {start} to "
        f"{str(day.index[-1].date())}, halves split at {split}; {phases} paired rebalance phases (7-day cycle). Fees "
        f"{FEES_BP[0]} / {FEES_BP[1]} bp per side, plus slippage {costs['slippage_bps']} bp and exec delay "
        f"{costs.get('exec_delay_bps', 0)} bp (backtest only). Sharpe = annualised ({periods_per_year(cand)} days), "
        "excess over cash.", "",
        f"**Ship: {res['ship']}.** " + ("Every pass rule holds." if res["ship"] == "crypto" else "A pass rule failed, so crypto_base ships."),
        "",
        f"DSR of {d['profile']}: {_f(d['value'])} (N={d['n']} trials: {n_seeded} seeded, {n_prior - n_seeded} from earlier "
        f"sweeps, {n_sweep} per-phase runs here; per-period Sharpe spread {_f(spread, 5)}; daily series: phase 0 "
        "excess returns of the shipped profile at 50 bp)."
        + (" No proven edge (DSR below 0.95)." if d["value"] is None or d["value"] < 0.95 else ""),
        "", "## Ablations (candidate at 50 bp; dropped when the paired median delta Sharpe >= 0)", "",
        "| component | run | median dSharpe vs candidate | dropped |", "|---|---|---:|---|",
    ]
    lines += [f"| {a['label']} | {a['run']} | {_f(a['d_sharpe_med'])} | {'yes' if a['dropped'] else 'no'} |"
              for a in res["ablations"].values()]
    lines += ["", f"Final candidate: {fc['label']} (run `{fc['run']}`)."
              + (f" Config change needed before it can ship: `{json.dumps(fc['overrides'])}`." if res["config_change_needed"] else ""),
              "", "## Pass rule (final candidate vs crypto_base)", "", "| rule | value | needs | pass |", "|---|---|---|---|"]
    names = {"phases_won": "paired phases won (Sharpe, 50 bp)", "p_boot": "block-bootstrap P(dSharpe > 0)",
             "dd_gap": "median maxDD, points worse", "cost100": "median paired dSharpe at 100 bp",
             "halves": "median paired dSharpe, each half"}
    lines += [f"| {names[k]} | {v['value']} | {v['need']} | {'yes' if v['pass'] else 'NO'} |" for k, v in pr.items()]
    lines += ["", "## Runs", "",
              "| run | profile | universe | fee bp | lag | window | Sharpe med [min, max] | maxDD med | CAGR med | vs | dSharpe med | wins |",
              "|---|---|---|---:|---:|---|---|---:|---:|---|---:|---|"]
    for name, r in res["runs"].items():
        lines.append(f"| {name} | {r['profile']} | {'+'.join(s.split('-')[0] for s in r['universe'])} | {r['fee_bps']} | "
                     f"{r['exec_lag']} | {r['window'][0]}..{r['window'][1] or 'last'} | {_f(r['sharpe_med'])} "
                     f"[{_f(r['sharpe_min'])}, {_f(r['sharpe_max'])}] | {_f(r['maxdd_med'])} | {_f(r['cagr_med'])} | "
                     f"{r.get('pair', '-')} | {_f(r.get('d_sharpe_med'))} | {r.get('wins', '-')} |")
    lines += ["", f"BTC buy&hold over the window (a benchmark, not a trial): Sharpe {btc.get('sharpe', 'n/a')}, "
              f"maxDD {btc.get('max_drawdown', 'n/a')}, CAGR {btc.get('cagr', 'n/a')}.", ""]
    b = res.get("boot")
    if b:
        lvl, coin = f"{b['level']:.0%}", cand.get("benchmark", "BTC-USD").split("-")[0]
        lines += [f"## Ranges ({lvl} stationary block bootstrap: mean block {b['block_days']} days, {b['draws']} resamples, "
                  f"seed {b['seed']})", "",
                  f"| run | Sharpe med [{lvl} range] | CAGR med [{lvl} range] | maxDD med [{lvl} range] | "
                  f"P(Sharpe > {coin} hold) | vs | P(Sharpe > vs) |",
                  "|---|---|---|---|---:|---|---:|"]
        for name, r in res["runs"].items():
            g = r["range"]
            lines.append(f"| {name} | {report.est(r['sharpe_med'], g['sharpe_lo'], g['sharpe_hi'])} | "
                         f"{report.est(r['cagr_med'], g['cagr_lo'], g['cagr_hi'], 4)} | "
                         f"{report.est(r['maxdd_med'], g['maxdd_lo'], g['maxdd_hi'], 4)} | "
                         f"{report.prob(g['p_gt_bench'])} | {r.get('pair', '-')} | {report.prob(g['p_gt_base'])} |")
        lines += ["", *report.range_notes(lvl, f"{coin} hold", "vs"),
                  "These ranges are informative: the pass rule above is unchanged and reads none of them (its own "
                  "block-bootstrap P is the moving-block one of the spec).", ""]
    else:
        lines += [f"## Ranges: not computed ({res.get('ranges_error', 'no detail')})", ""]
    lines += [*report.record_lines(res.get("record") or {}, cand), "", "## Merged configs", ""]
    for title, cfg in (("crypto_base", base), ("crypto (candidate)", cand)):
        shown = {k: v for k, v in cfg.items() if not k.startswith("_")}
        lines += [f"### {title}", "", "```json", json.dumps(shown, indent=1, default=str), "```", ""]
    return "\n".join(lines)
