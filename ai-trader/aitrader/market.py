"""Market calendars. Only the 24/7 crypto calendar lives here; the NYSE rules stay as module-level functions in
cycle.py (planning decision 5: cycle._bar_is_final, _market_opened, data.official_opens are patched by tests and the
news engine, so they are not abstracted). cycle.py picks this calendar when market.calendar == "utc_daily".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from . import data

UTC = timezone.utc


def _stamp(t: datetime) -> str:
    """The journal.now_utc() format (override cutoffs and exec_ts are compared as strings)."""
    return t.astimezone(UTC).replace(microsecond=0).isoformat()


def _utc(t) -> datetime:
    t = datetime.fromisoformat(t) if isinstance(t, str) else t
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


class UtcDailyCalendar:
    """Daily bars that end at 00:00 UTC, 7 days a week (spec 3.2). A bar is final 5 minutes after its end, and only if
    its data was fetched after that (spec 4). Decide at 00:12 UTC, execute on the hour (planning decision 12)."""

    periods_per_year = 365
    FINAL_AFTER = timedelta(minutes=5)
    EXEC_FLOOR = timedelta(hours=1)  # never execute before D+1 01:00 UTC
    INTERVALS = ("1h", "1m")  # the fill source chain; never the daily open (the price the signal saw)

    @staticmethod
    def session_window(day) -> tuple[datetime, datetime]:
        """[start, end) of the UTC day `day`."""
        d = pd.Timestamp(day)
        start = datetime(d.year, d.month, d.day, tzinfo=UTC)
        return start, start + timedelta(days=1)

    @classmethod
    def bar_end(cls, bar) -> datetime:
        return cls.session_window(bar)[1]

    @classmethod
    def bar_is_final(cls, bar, now, fetched_at=None) -> bool:
        """The clock says bar's day ended 5+ minutes ago, and its data (if a fetch time is known) was fetched after."""
        t = cls.bar_end(bar) + cls.FINAL_AFTER
        return _utc(now) >= t and (fetched_at is None or _utc(fetched_at) >= t)

    @classmethod
    def last_final_bar(cls, now):
        """The newest bar date that is final by the clock at `now`."""
        return (_utc(now) - cls.FINAL_AFTER).date() - timedelta(days=1)

    @staticmethod
    def cooldown_until(day, n_bars: int) -> str:
        """Stop-loss cooldown in calendar days (every day is a bar)."""
        return str((pd.Timestamp(day) + pd.Timedelta(days=n_bars)).date())

    @classmethod
    def exec_time(cls, decision_bar, logged_at) -> str:
        """Planning decision 12: the first full hour strictly after logged_at, never earlier than D+1 01:00 UTC."""
        t = _utc(logged_at)
        nxt = t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return _stamp(max(nxt, cls.bar_end(decision_bar) + cls.EXEC_FLOOR))

    @classmethod
    def fill_prices(cls, names, exec_ts) -> tuple[dict, str] | None:
        """Open of the bar starting at exec_ts for every name: the 1h bar, else the 1m bar. None if any name has
        neither (all or nothing: the order stays pending). The label is "1h" / "1m" when every name used the same
        interval, else each name's source ("BTC-USD:1h,ETH-USD:1m")."""
        prices, src = {}, {}
        for s in sorted(set(names)):
            for iv in cls.INTERVALS:
                px = data.intraday_open(s, exec_ts, iv)
                if px is not None:
                    prices[s], src[s] = px, iv
                    break
            else:
                return None
        kinds = set(src.values())
        label = kinds.pop() if len(kinds) == 1 else ",".join(f"{s}:{v}" for s, v in sorted(src.items())) or "none"
        return prices, label
