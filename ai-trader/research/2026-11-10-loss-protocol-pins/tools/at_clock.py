"""Run a test file with the wall clock moved so that the run starts at a given instant in New York.
usage (from an ai-trader copy): at_clock.py <YYYY-MM-DDTHH:MM:SS[.ffffff]> [pattern] [fold] [part of a test's name]
Only the name `datetime` inside the aitrader modules and the test modules is replaced (their datetime.now() answers
the moved clock, which goes on ticking at the real speed); time.time() stays real."""
import datetime as real
import sys
import unittest
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
NY, UTC = ZoneInfo("America/New_York"), real.timezone.utc
start = real.datetime.fromisoformat(sys.argv[1]).replace(tzinfo=NY, fold=int(sys.argv[3]) if len(sys.argv) > 3 else 0)
pattern = sys.argv[2] if len(sys.argv) > 2 else "test_loss_protocol_pins.py"
sys.path.insert(0, ".")
suite = unittest.defaultTestLoader.discover("tests", pattern=pattern)  # imported at the real time
OFFSET = [None]
if len(sys.argv) > 4:  # only the tests whose id has this text in it
    def flat(s):
        for t in s:
            yield from (flat(t) if isinstance(t, unittest.TestSuite) else [t])
    suite = unittest.TestSuite(t for t in flat(suite) if sys.argv[4] in t.id())


class Clock(real.datetime):
    @classmethod
    def now(cls, tz=None):
        t = (real.datetime.now(UTC) + OFFSET[0]).astimezone(tz) if tz else (real.datetime.now(UTC) + OFFSET[0]).astimezone().replace(tzinfo=None)
        return cls(t.year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond, tzinfo=t.tzinfo, fold=t.fold)


n = 0
for name, mod in list(sys.modules.items()):
    if (name.startswith("aitrader") or name.startswith("test_")) and getattr(mod, "datetime", None) is real.datetime:
        mod.datetime = Clock
        n += 1
OFFSET[0] = start.astimezone(UTC) - real.datetime.now(UTC)
res = unittest.TextTestRunner(verbosity=0, stream=open("/dev/null", "w")).run(suite)
end = Clock.now(NY)
line = f"{start.strftime('%a %Y-%m-%d %H:%M:%S.%f')[:-3]} -> {end.strftime('%H:%M:%S.%f')[:-3]} NY | ran {res.testsRun} failures {len(res.failures)} errors {len(res.errors)}"
print(line, flush=True)
for kind, lst in (("FAIL", res.failures), ("ERROR", res.errors)):
    for t, tb in lst:
        last = [l for l in tb.strip().splitlines() if l.strip()][-1]
        print(f"   {kind}: {t.id()}\n         {last[:260]}", flush=True)
sys.exit(0 if res.wasSuccessful() else 1)
