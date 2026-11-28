"""Every place a clock boundary can fall inside a test. For each test, alone: count how many times it (and the code
it runs) reads the clock; then, for every k, run it with the clock standing just BEFORE a boundary for the first k
reads and just AFTER it for the rest. That is every position of the boundary between two clock reads, which no sweep
of start times can promise to hit. The clock is the name `datetime` inside the aitrader and test modules
(journal.now_utc reads it too); time.time() stays real.
usage (from an ai-trader copy): boundary_enum.py [pattern] [part of a test's name]"""
import datetime as real
import io
import sys
import unittest
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
NY, UTC = ZoneInfo("America/New_York"), real.timezone.utc
pattern = sys.argv[1] if len(sys.argv) > 1 else "test_loss_protocol_pins.py"
only = sys.argv[2] if len(sys.argv) > 2 else ""
sys.path.insert(0, ".")
suite = unittest.defaultTestLoader.discover("tests", pattern=pattern)
STATE = {"before": None, "after": None, "flip": None, "reads": 0}


class Clock(real.datetime):
    @classmethod
    def now(cls, tz=None):
        STATE["reads"] += 1
        inst = STATE["before"] if STATE["flip"] is None or STATE["reads"] <= STATE["flip"] else STATE["after"]
        t = inst.astimezone(tz) if tz else inst.astimezone().replace(tzinfo=None)
        return cls(t.year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond, tzinfo=t.tzinfo, fold=t.fold)


for name, mod in list(sys.modules.items()):
    if (name.startswith("aitrader") or name.startswith("test_")) and getattr(mod, "datetime", None) is real.datetime:
        mod.datetime = Clock


def flat(s):
    for t in s:
        yield from (flat(t) if isinstance(t, unittest.TestSuite) else [t])


def run(t, before, after, flip):
    STATE.update(before=before, after=after, flip=flip, reads=0)
    res = unittest.TestResult()
    out, sys.stdout = sys.stdout, io.StringIO()
    try:
        type(t)(t._testMethodName).run(res)
    finally:
        sys.stdout = out
    return STATE["reads"], [tb.strip().splitlines()[-1][:150] for _, tb in res.failures + res.errors]


def at(y, mo, d, h, mi, s, us=0, fold=0):
    return real.datetime(y, mo, d, h, mi, s, us, tzinfo=NY, fold=fold).astimezone(UTC)


HALF = real.timedelta(milliseconds=500)
BOUNDS = {  # name: the instant of the boundary (the clock stands half a second before it, then half a second after)
    "New York midnight (Tue->Wed)": at(2026, 11, 11, 0, 0, 0),
    "UTC midnight (19:00 New York)": real.datetime(2026, 11, 11, 0, 0, tzinfo=UTC),
    "a minute in session (11:01)": at(2026, 11, 10, 11, 1, 0),
    "the opening bell (09:30)": at(2026, 11, 10, 9, 30, 0),
    "the closing bell (16:00)": at(2026, 11, 10, 16, 0, 0),
    "16:05, the engine's default end": at(2026, 11, 10, 16, 5, 0),
    "Friday midnight (into the weekend)": at(2026, 11, 14, 0, 0, 0),
    "Sunday midnight (into Monday)": at(2026, 11, 16, 0, 0, 0),
    "New Year (into a holiday, 2027)": at(2027, 1, 1, 0, 0, 0),
    "clocks forward (2027-03-14 02:00)": at(2027, 3, 14, 3, 0, 0),
    "clocks back (2027-11-07 02:00)": at(2027, 11, 7, 1, 0, 0, fold=1),
}
import os  # noqa: E402
if os.environ.get("BOUNDS"):  # a comma-separated list of words: only the boundaries whose name has one of them
    BOUNDS = {k: v for k, v in BOUNDS.items() if any(w in k for w in os.environ["BOUNDS"].split(","))}
tests = [t for t in flat(suite) if only in t.id()]
runs, bad, most, sampled = 0, {}, 0, set()
for t in tests:
    for label, b in BOUNDS.items():
        n, why = run(t, b - HALF, b + HALF, None)  # the whole test before the boundary: how many clock reads
        most = max(most, n)
        fails = [(-1, why[0])] if why else []
        ks = list(range(0, n + 1))  # k = 0: the whole test after it
        if n > 240:  # a test that spins an engine loop reads the clock thousands of times: the first 80 positions,
            ks = sorted(set(ks[:80] + ks[-80:] + ks[::max(1, n // 80)]))  # the last 80 and 80 spread between them
            sampled.add(t.id().split(".", 1)[1])
        for k in ks:
            _, why = run(t, b - HALF, b + HALF, k)
            runs += 1
            if why:
                fails.append((k, why[0]))
        if fails:
            bad[(t.id().split(".", 1)[1], label)] = (n, fails)
print(f"tests {len(tests)} | boundaries {len(BOUNDS)} | runs {runs} | most clock reads in one test {most} | (test, boundary) pairs that fail somewhere: {len(bad)}")
if sampled:
    print(f"   positions sampled, not all tried, for {len(sampled)} tests with more than 240 clock reads: {sorted(sampled)}")
for (tid, label), (n, fails) in sorted(bad.items()):
    ks = [k for k, _ in fails]
    print(f"   {tid}\n      {label}: fails at {len(fails)} of {n + 1} positions (after read {ks[0]}{' .. ' + str(ks[-1]) if len(ks) > 1 else ''}): {fails[0][1]}")
