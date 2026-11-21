"""Read-only power check of the spec's paired-phase pass rule, using the repo engine in memory.
Approximations (engine has no crypto mode yet): offset regime replaced by a hysteresis state passed
through aux['bench_sma']; 252-day annualisation compensated in the vol target (0.30/1.2035);
fee+slip+delay folded into slippage_bps (65 per side); starting cash 1e9 so whole units do not bind.
No file in the repo is written."""
import copy, json, math, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/OmniRoute/ai-trader")
from aitrader import backtest
from aitrader.strategy import precompute_aux
from aitrader.metrics import psr

DATA = "/tmp/claude-0/-home-user/8a7e2b07-38b8-554f-b854-0fa4d66f5fd9/scratchpad/crypto/risk/data/"
def daily(sym):
    res = json.load(open(DATA + f"{sym}_all_1d.json"))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).normalize().tz_localize(None)
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close", "volume")}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    return df[df.index < pd.Timestamp("2026-11-09")]

b, e = daily("BTC-USD"), daily("ETH-USD")
idx = b.index
panel = {k: pd.DataFrame({"BTC-USD": b[k], "ETH-USD": e[k].reindex(idx)}) for k in ("open", "high", "low", "close", "volume")}
CFG = json.load(open("/home/user/OmniRoute/ai-trader/config.json"))

def hyst_state(close, sma, band):
    s, out = None, []
    for c, m in zip(close, sma):
        if np.isnan(m): out.append(np.nan); continue
        if s is None: s = 1 if c >= m * (1 - band) else 0
        elif s == 1 and c < m * (1 - band): s = 0
        elif s == 0 and c > m * (1 + band): s = 1
        out.append(s)
    return pd.Series(out, index=close.index)

def mkcfg(kind, cost_bps=65):
    c = copy.deepcopy(CFG)
    c["benchmark"] = "BTC-USD"
    c["account"].update({"starting_cash": 1e9, "cash_yield_annual": 0.0})
    c["costs"].update({"slippage_bps": cost_bps})
    r = c["risk"]
    r.update({"target_vol_annual": 0.30 / math.sqrt(365 / 252), "max_gross": 1.0, "max_position_pct": 1.0, "max_etf_position_pct": 1.0,
              "max_sector_pct": 1.0, "risk_off_gross_mult": 0.0, "rebalance_band_pct": 0.05, "min_trade_value": 100,
              "rebalance_every_days": 7, "stop_cooldown_days": 14, "defensive_vix_pct": 0, "lowvol_exclude_top_pct": 0,
              "regime_band_pct": 0.0})
    if kind == "base":
        c["universe"] = {"BTC-USD": "Crypto"}
        c["prior_weights"] = {k: 0.0 for k in c["prior_weights"]}; c["prior_weights"]["trend"] = 1.0
        r.update({"min_score": -1.0, "exit_score": -1.0, "atr_stop_mult": 1e9, "dd_halve": -0.99, "dd_flat": -0.999})
    else:
        c["universe"] = {"BTC-USD": "Crypto", "ETH-USD": "Crypto"}
        c["prior_weights"] = {k: 0.0 for k in c["prior_weights"]}
        c["prior_weights"].update({"tsmom": 0.35, "trend": 0.35, "breakout": 0.30})
        c["signals"]["tsmom"] = {"lookback": 365, "skip": 30}
        r.update({"dd_halve": -0.25, "dd_flat": -0.50, "atr_stop_mult": 3.0})
    return c

def run(kind, phase, start, end=None, cost=65):
    c = mkcfg(kind, cost)
    p = {k: v[list(c["universe"])] for k, v in panel.items()}
    aux = precompute_aux(p, c)
    st = hyst_state(p["close"]["BTC-USD"], aux["bench_sma"], 0.02)
    # encode hysteresis through the engine's offset test: on -> sma tiny, off -> sma huge
    aux["bench_sma"] = pd.Series(np.where(st == 1, 1e-9, np.where(st == 0, 1e18, np.nan)), index=st.index)
    res = backtest.run(p, c, start, end, "prior", 7, aux=aux, phase=phase)
    return res["_equity"], res["_fills"]

def stats(eq):
    r = eq.pct_change().dropna()
    sh = r.mean() / r.std() * math.sqrt(365)
    dd = (eq / eq.cummax() - 1).min()
    yrs = len(r) / 365
    return {"sharpe": round(sh, 3), "maxdd": round(dd, 3), "cagr": round((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1, 3), "psr": round(psr(r), 3)}

if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2018-01-01"
    out = {"start": start, "phases": []}
    eqs = {}
    for ph in range(7):
        eb, fb = run("base", ph, start); ec, fc = run("cand", ph, start)
        sb, sc = stats(eb), stats(ec)
        eqs[ph] = (eb, ec)
        out["phases"].append({"phase": ph, "base": sb, "cand": sc, "d_sharpe": round(sc["sharpe"] - sb["sharpe"], 3),
                              "n_fills_base": len(fb), "n_fills_cand": len(fc)})
        print(json.dumps(out["phases"][-1]), flush=True)
    # correlation of daily returns across phases (how independent are the 7 'paired' tests?)
    rb = pd.DataFrame({ph: eqs[ph][0].pct_change() for ph in eqs}).dropna()
    rc = pd.DataFrame({ph: eqs[ph][1].pct_change() for ph in eqs}).dropna()
    print("min pairwise corr of daily returns across phases: base", round(rb.corr().values.min(), 4), "cand", round(rc.corr().values.min(), 4))
    # block bootstrap of the Sharpe difference at phase 0
    b0, c0 = eqs[0][0].pct_change().dropna(), eqs[0][1].pct_change().dropna()
    dfr = pd.concat([b0, c0], axis=1).dropna().values
    rng = np.random.default_rng(0); n = len(dfr); L = 30; diffs = []
    for _ in range(2000):
        starts = rng.integers(0, n - L, n // L + 1)
        ix = np.concatenate([np.arange(s, s + L) for s in starts])[:n]
        x = dfr[ix]
        s = x.mean(0) / x.std(0) * math.sqrt(365)
        diffs.append(s[1] - s[0])
    diffs = np.array(diffs)
    print("block-bootstrap d_sharpe (cand-base) phase0: mean", round(diffs.mean(), 3), "sd", round(diffs.std(), 3),
          "P(d>0)", round((diffs > 0).mean(), 3))
    d = pd.Series(dfr[:, 1] - dfr[:, 0])
    print("PSR of the daily return difference (cand-base) vs 0:", round(psr(d), 3))
