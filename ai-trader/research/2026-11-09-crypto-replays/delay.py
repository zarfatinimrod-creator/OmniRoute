"""Exec-delay check: daily open (00:00 UTC, what the backtest fills at) vs the 01:00 UTC hourly open (what live fills at).
Signed by the side of the simulated candidate/base fills in the last 730 days. Read-only."""
import json, sys, math
import numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-0/-home-user/8a7e2b07-38b8-554f-b854-0fa4d66f5fd9/scratchpad/specreview/code")
import power
DATA = power.DATA
def hourly(sym):
    res = json.load(open(DATA + f"{sym}_730d_1h.json"))["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_localize(None)
    df = pd.DataFrame({k: q[k] for k in ("open", "close", "volume")}, index=idx).astype(float)
    return df[~df.index.duplicated(keep="last")]
out = {}
for sym in ("BTC-USD", "ETH-USD"):
    h = hourly(sym)
    o0 = h["open"][h.index.hour == 0]; o1 = h["open"][h.index.hour == 1]
    o0.index = o0.index.normalize(); o1.index = o1.index.normalize()
    r = (o1 / o0 - 1).dropna()
    v1 = h["volume"][h.index.hour == 1]; v1.index = v1.index.normalize()
    out[sym] = r
    print(sym, "00->01 UTC: n", len(r), "mean bp", round(r.mean() * 1e4, 1), "sd bp", round(r.std() * 1e4, 1),
          "mean|r| bp", round(r.abs().mean() * 1e4, 1), "| 01:00 bars with volume 0:", int((v1 == 0).sum()), "of", len(v1),
          "null open:", int(h["open"][h.index.hour == 1].isna().sum()))
start = str(min(out["BTC-USD"].index.min(), out["ETH-USD"].index.min()).date())
for kind in ("base", "cand"):
    _, fills = power.run(kind, 0, "2018-01-01")
    signed = []
    for f in fills:
        r = out.get(f["symbol"])
        d = pd.Timestamp(f["date"])
        if r is not None and d in r.index:
            signed.append(r[d] * (1 if f["side"] == "BUY" else -1))
    s = pd.Series(signed)
    if len(s):
        print(kind, "fills inside the hourly window:", len(s), "mean adverse move bp", round(s.mean() * 1e4, 1),
              "median", round(s.median() * 1e4, 1), "sd", round(s.std() * 1e4, 1), "se of mean", round(s.std() / math.sqrt(len(s)) * 1e4, 1))
