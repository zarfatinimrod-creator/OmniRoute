"""Paper broker: simulated account with realistic fills (slippage, whole shares, cash yield).

State is a plain JSON-able dict so it can be committed to git and read by humans.
"""

from __future__ import annotations

import math


class PaperBroker:
    def __init__(self, cash: float, slippage_bps: float = 5.0, commission_per_share: float = 0.0, state: dict | None = None):
        self.slippage = slippage_bps / 1e4
        self.commission = commission_per_share
        self.state = state or {"cash": float(cash), "positions": {}, "peak_equity": float(cash), "blocked": {}}

    # ---- views -------------------------------------------------------------------------------
    @property
    def cash(self) -> float:
        return self.state["cash"]

    @property
    def positions(self) -> dict:
        return self.state["positions"]

    def _price(self, sym: str, prices: dict) -> float:
        px = prices.get(sym)
        return px if px and px == px else self.positions[sym]["last_price"]

    def equity(self, prices: dict) -> float:
        return self.cash + sum(p["qty"] * self._price(s, prices) for s, p in self.positions.items())

    def weights(self, prices: dict) -> dict[str, float]:
        eq = self.equity(prices)
        return {s: p["qty"] * self._price(s, prices) / eq for s, p in self.positions.items()} if eq > 0 else {}

    # ---- daily bookkeeping ---------------------------------------------------------------------
    def mark(self, prices: dict, date: str, cash_yield_annual: float = 0.0, trading_days: int = 252) -> float:
        """End-of-day mark: accrue cash yield, update peak closes for trailing stops, track equity peak."""
        if self.state["cash"] > 0 and cash_yield_annual:
            self.state["cash"] *= (1 + cash_yield_annual) ** (1 / trading_days)
        for sym, p in self.positions.items():
            px = prices.get(sym)
            if px and px == px:
                p["last_price"] = px
                p["peak_close"] = max(p.get("peak_close", px), px)
        eq = self.equity(prices)
        self.state["peak_equity"] = max(self.state.get("peak_equity", eq), eq)
        self.state["last_mark"] = date
        # expire stop-loss cooldowns
        self.state["blocked"] = {s: d for s, d in self.state.get("blocked", {}).items() if d > date}
        return eq

    def apply_corporate_actions(self, actions: dict, upto: str, withholding: float = 0.25) -> list[str]:
        """Apply splits and cash dividends with ex-date in (last applied, upto] to held positions.
        Prices are split/dividend-adjusted by the data feed, so without this a 4:1 split would look like
        a 75% loss and trigger the stop. Dividends are credited net of US withholding (W-8BEN 25%)."""
        notes = []
        for sym, pos in list(self.positions.items()):
            ca = actions.get(sym) or {}
            since = pos.get("ca_applied_through") or pos.get("entry_date", "")
            for sp in ca.get("splits", []):
                if since < sp["date"] <= upto and sp["ratio"] > 0:
                    new_qty = pos["qty"] * sp["ratio"]
                    whole = math.floor(new_qty + 1e-9)
                    px = pos["last_price"] / sp["ratio"]
                    self.state["cash"] += (new_qty - whole) * px  # cash in lieu of a fractional share
                    pos["qty"] = whole
                    for k in ("avg_cost", "peak_close", "last_price"):
                        pos[k] = pos[k] / sp["ratio"]
                    notes.append(f"split {sym} {sp['ratio']:g}:1 on {sp['date']}")
            for dv in ca.get("dividends", []):
                if since < dv["date"] <= upto:
                    cash = pos["qty"] * dv["amount"] * (1 - withholding)
                    self.state["cash"] += cash
                    notes.append(f"dividend {sym} {dv['amount']}/sh -> ${cash:,.2f} net on {dv['date']}")
            pos["ca_applied_through"] = max(since, upto)
            if pos["qty"] <= 0:
                del self.positions[sym]
        return notes

    def maybe_reset_peak(self, regime: str, date: str, days_required: int = 20, dd_halve: float = -0.10, dd_flat: float = -0.20) -> bool:
        """Drawdown re-entry: after going flat, reset the reference peak once the market has been risk-on for
        `days_required` consecutive decisions, so the breaker is not a permanent exit (resumes at full scale)."""
        st = self.state
        if st.get("dd_state") != "flat":
            st.pop("riskon_streak", None)
            return False
        st["riskon_streak"] = st.get("riskon_streak", 0) + 1 if regime.startswith("risk_on") else 0
        if st["riskon_streak"] >= days_required:
            eq = st["cash"] + sum(p["qty"] * p["last_price"] for p in self.positions.values())
            # reference peak in the middle of the "halved" band, so a day of interest cannot flip it to normal
            st["peak_equity"] = eq / (1 + (dd_halve + dd_flat) / 2)
            st["riskon_streak"] = 0
            st.setdefault("peak_resets", []).append(date)
            return True
        return False

    def peak_ratio(self, prices: dict) -> float:
        return self.equity(prices) / max(self.state.get("peak_equity", 1.0), 1e-9)

    # ---- execution ---------------------------------------------------------------------------
    def rebalance(
        self,
        targets: dict[str, float],
        prices: dict,
        date: str,
        band: float = 0.02,
        min_trade_value: float = 500.0,
        stopped: list | None = None,
        cooldown_until: str | None = None,
        exits_only: bool = False,
    ) -> list[dict]:
        """Move toward target weights. Sells first, then buys. exits_only: only close positions whose target
        is 0 (off-cycle days: act on stops, never re-trade gaps). Returns executed fills."""
        eq = self.equity(prices)
        cur = self.weights(prices)
        fills = []
        stopped = set(stopped or [])
        syms = sorted(set(cur) | set(targets))
        orders = []
        for s in syms:
            px = prices.get(s)
            if not px or px != px:
                continue
            tw, cw = targets.get(s, 0.0), cur.get(s, 0.0)
            exiting = tw == 0 and cw > 0
            if exits_only and tw >= cw:  # off-cycle: never buy; exits, stops, shrinks and earnings caps still sell
                continue
            if not exiting and abs(tw - cw) < band:
                continue
            delta_val = (tw - cw) * eq
            if not exiting and abs(delta_val) < min_trade_value:
                continue
            orders.append((s, px, delta_val, exiting))
        for s, px, delta_val, exiting in sorted(orders, key=lambda o: o[2]):  # sells (negative) first
            if delta_val < 0:
                held = self.positions.get(s, {}).get("qty", 0)
                qty = held if exiting else min(held, math.floor(-delta_val / px))
                if qty <= 0:
                    continue
                f = self._fill(s, -qty, px, date)
                f["reason"] = "stop" if s in stopped else ("exit" if exiting else "trim")
                fills.append(f)
                if s in stopped and cooldown_until:
                    self.state.setdefault("blocked", {})[s] = cooldown_until
            else:
                buy_px = px * (1 + self.slippage)
                qty = math.floor(min(delta_val, self.cash) / (buy_px + self.commission))
                if qty <= 0:
                    continue
                f = self._fill(s, qty, px, date)
                f["reason"] = "add" if s in cur else "entry"
                fills.append(f)
        return fills

    def _fill(self, sym: str, qty: int, px: float, date: str) -> dict:
        side = "BUY" if qty > 0 else "SELL"
        fill_px = px * (1 + self.slippage) if qty > 0 else px * (1 - self.slippage)
        cost = qty * fill_px + abs(qty) * self.commission
        self.state["cash"] -= cost
        pos = self.positions.get(sym)
        realized = 0.0
        if qty > 0:
            if pos:
                new_qty = pos["qty"] + qty
                pos["avg_cost"] = (pos["avg_cost"] * pos["qty"] + fill_px * qty) / new_qty
                pos["qty"] = new_qty
            else:
                self.positions[sym] = {"qty": qty, "avg_cost": fill_px, "entry_date": date, "peak_close": px, "last_price": px}
        else:
            realized = (fill_px - pos["avg_cost"]) * (-qty)
            pos["qty"] += qty
            if pos["qty"] <= 0:
                del self.positions[sym]
        return {
            "date": date,
            "symbol": sym,
            "side": side,
            "qty": abs(qty),
            "price": round(fill_px, 4),
            "value": round(abs(qty) * fill_px, 2),
            "realized_pnl": round(realized, 2),
        }
