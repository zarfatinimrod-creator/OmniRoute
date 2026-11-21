"""Count no-picks days in the stock backtest (where diag['regime'] == 'n/a') and what the regime was. Read-only (runs on a scratch copy)."""
import sys
sys.path.insert(0, sys.argv[1])
import pandas as pd
from aitrader import backtest, strategy
from aitrader.data import load_config, load_market
cfg = load_config()
panel = load_market(cfg, "10y", 1e9)
log = []
orig = strategy.build_targets
def bt(date, panel_, *a, **k):
    t, d = orig(date, panel_, *a, **k)
    if d.get("regime") == "n/a":
        log.append(str(pd.Timestamp(date).date()))
    return t, d
backtest.build_targets = bt
for ph in range(5):
    log.clear()
    res = backtest.run(panel, cfg, "2018-01-01", None, "learned", 5, phase=ph)
    print("phase", ph, "no-picks days:", len(log), log[:12], "sharpe", res["strategy"]["sharpe"])
