"""Read-only: would the rev-2 ablation rule (drop any component whose removal does not lower median Sharpe) drop the
drawdown breaker / ATR stop? Reuses round-1 reviewer's power.py (engine in memory, approximations documented there)."""
import sys, statistics, copy
sys.path.insert(0, "/tmp/claude-0/-home-user/8a7e2b07-38b8-554f-b854-0fa4d66f5fd9/scratchpad/specreview/code")
import power
import numpy as np, pandas as pd
from aitrader import backtest
from aitrader.strategy import precompute_aux

def run(kind, phase, start="2018-01-01", tweak=None):
    c = power.mkcfg("cand" if kind != "base" else "base")
    if tweak: c["risk"].update(tweak)
    p = {k: v[list(c["universe"])] for k, v in power.panel.items()}
    aux = precompute_aux(p, c)
    st = power.hyst_state(p["close"]["BTC-USD"], aux["bench_sma"], 0.02)
    aux["bench_sma"] = pd.Series(np.where(st == 1, 1e-9, np.where(st == 0, 1e18, np.nan)), index=st.index)
    res = backtest.run(p, c, start, None, "prior", 7, aux=aux, phase=phase)
    return power.stats(res["_equity"]), len(res["_fills"])

if __name__ == "__main__":
  variants = {"base": ("base", None), "cand": ("cand", None),
              "cand no breaker": ("cand", {"dd_halve": -0.99, "dd_flat": -0.999}),
              "cand no stop": ("cand", {"atr_stop_mult": 1e9})}
  for name, (kind, tw) in variants.items():
      rows = [run(kind, ph, tweak=tw) for ph in range(7)]
      sh = [r[0]["sharpe"] for r in rows]; dd = [r[0]["maxdd"] for r in rows]; cg = [r[0]["cagr"] for r in rows]
      print(f"{name:16s} sharpe med {statistics.median(sh):.3f} [{min(sh):.3f},{max(sh):.3f}] maxdd med {statistics.median(dd):.3f} [{min(dd):.3f},{max(dd):.3f}] cagr med {statistics.median(cg):.3f} fills med {statistics.median([r[1] for r in rows])}", flush=True)
