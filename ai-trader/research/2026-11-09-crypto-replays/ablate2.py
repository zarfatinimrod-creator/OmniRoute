"""Read-only: cost of keeping the drawdown breaker in crypto_base (same approximations as power.py)."""
import sys, statistics
sys.path.insert(0, "/tmp/claude-0/-home-user/8a7e2b07-38b8-554f-b854-0fa4d66f5fd9/scratchpad/specreview2")
from ablate import run
for name, tw in {"base + breaker -25/-50": {"dd_halve": -0.25, "dd_flat": -0.50}}.items():
    rows = [run("base", ph, tweak=tw) for ph in range(7)]
    sh = [r[0]["sharpe"] for r in rows]; dd = [r[0]["maxdd"] for r in rows]; cg = [r[0]["cagr"] for r in rows]
    print(f"{name:22s} sharpe med {statistics.median(sh):.3f} [{min(sh):.3f},{max(sh):.3f}] maxdd med {statistics.median(dd):.3f} [{min(dd):.3f},{max(dd):.3f}] cagr med {statistics.median(cg):.3f}", flush=True)
