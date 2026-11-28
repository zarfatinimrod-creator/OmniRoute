"""Build the "proper" form of the pins: fold every method of tests/test_loss_protocol_pins.py into the class it
belongs in (tests/test_news_guards.py, tests/test_postmortem.py), then apply the changes to what those two files
already had (the wait for background checks in the base classes; three old methods with clock defects).
Usage: fold.py <tree with the pins file> <tree to write the two folded files into>   (both are copies under pins/)"""
import ast
import sys
from pathlib import Path

src_tree, out_tree = Path(sys.argv[1]), Path(sys.argv[2])
pins = (src_tree / "tests" / "test_loss_protocol_pins.py").read_text(encoding="utf-8")
lines = pins.split("\n")
TARGET = {"g": "test_news_guards.py", "p": "test_postmortem.py"}
blocks, count = {}, 0
for node in ast.parse(pins).body:
    if not isinstance(node, ast.ClassDef) or not node.name.endswith("_"):
        continue
    base = node.bases[-1]  # (_ChecksOver, g.Hold): the class the methods belong in is the last base
    mod, cls = base.value.id, base.attr
    assert node.name == cls + "_", node.name
    body = lines[node.lineno:node.end_lineno]
    while body and body[-1].strip() == "":
        body.pop()
    names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
    assert all(n.startswith("test_") for n in names), names
    count += len(names)
    blocks.setdefault(TARGET[mod], {})[cls] = (body, names)

for fname, per in blocks.items():
    path = out_tree / "tests" / fname
    text = path.read_text(encoding="utf-8")
    tl = text.split("\n")
    have = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.ClassDef)}
    for cls, (body, names) in sorted(per.items(), key=lambda kv: -have[kv[0]].end_lineno):  # bottom-up: line numbers stay true
        old = {m.name for m in have[cls].body if isinstance(m, ast.FunctionDef)}
        assert not (old & set(names)), (cls, old & set(names))
        end = have[cls].end_lineno
        tl[end:end] = [""] + body
    path.write_text("\n".join(tl), encoding="utf-8")
    print(fname, "+", sum(len(n) for _, n in per.values()), "methods")
print("methods in the pins file:", count)


def edit(fname, old, new, times=1):
    path = out_tree / "tests" / fname
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == times, (fname, old[:60], text.count(old))
    path.write_text(text.replace(old, new), encoding="utf-8")


G, PM = "test_news_guards.py", "test_postmortem.py"
# ---- the wait for background checks, in the base classes -------------------------------------------------------
edit(G, '''MU = 'Micron Will "Buy Back a Hundred Billion Dollars" of Stock at Four Times Earnings'
''', '''MU = 'Micron Will "Buy Back a Hundred Billion Dollars" of Stock at Four Times Earnings'


def _background_checks_over(seconds=30):
    """A second check on trial is asked on a background thread (news_live._ask_later), and when that thread gets to
    run it calls whatever news_live.verify_headline is by then. So no test starts, and none ends, while one is out."""
    for t in threading.enumerate():
        if t.name == "trial-check":
            t.join(seconds)
''')
edit(G, '''class _Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
''', '''class _Engine(unittest.TestCase):
    def setUp(self):
        _background_checks_over()  # one an earlier test left out must not answer into this test
        self.tmp = Path(tempfile.mkdtemp())
''')
edit(G, '''    def tearDown(self):
        (news_live.live_price, news_live.market_open_now, news_live.verify_headline, news_live.notify.send,
''', '''    def tearDown(self):
        _background_checks_over()  # and this test's own are over before its answers are taken away
        (news_live.live_price, news_live.market_open_now, news_live.verify_headline, news_live.notify.send,
''')
edit(PM, '''import tempfile
import unittest
''', '''import tempfile
import threading
import unittest
''')
edit(PM, '''    def tearDown(self):
        news_live.live_price, news_live.market_open_now = self._lp, self._mo
''', '''    def tearDown(self):
        for t in threading.enumerate():  # a second check asked in the background (news.guards "log") is over
            if t.name == "trial-check":  # before the next test puts its own answers in
                t.join(30)
        news_live.live_price, news_live.market_open_now = self._lp, self._mo
''')
# ---- three old methods with clock defects ----------------------------------------------------------------------
# 1. the alert of a failing engine: its own clock ends the loop; "23:59" ended it before the first round for one
#    minute of every New York day
edit(G, '''                with mock.patch.object(news_live.time, "time", lambda: next(clock)):
                    news_live._run("23:59", 3.0, False)
''', '''                with mock.patch.object(news_live.time, "time", lambda: next(clock)):
                    news_live._run("24:00", 3.0, False)  # "24:00" never comes: the patched clock ends the loop
''')
# 2. the gap measured from the look before the step: the fixture's own time instead of the wall clock
edit(G, '''        self.nt._stops_checked_at = datetime.now(timezone.utc) - timedelta(minutes=10)  # the engine was away ten minutes
        asked = []
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), \\
                mock.patch.object(news_live, "bars_since", lambda sym, since, now: (asked.append(since), [])[1]), \\
                mock.patch.object(journal, "session_hours", lambda d: ((0, 0), (23, 59))):
            self.nt.step()
        self.assertEqual(len(asked), 1)  # the live look at the top of the step did not hide the gap
        self.assertAlmostEqual((datetime.now(NY) - asked[0]).total_seconds(), 600, delta=90)
''', '''        at = datetime(2026, 11, 10, 11, 0, 30, tzinfo=NY)  # a Tuesday in session: the fixture's own time, not the wall clock
        self.nt._stops_checked_at = (at - timedelta(minutes=10)).astimezone(timezone.utc)  # the engine was away ten minutes
        asked, look = [], self.nt._look_at_stops
        with mock.patch.object(self.nt, "poll_headlines", lambda: []), \\
                mock.patch.object(news_live, "bars_since", lambda sym, since, now: (asked.append(since), [])[1]), \\
                mock.patch.object(self.nt, "_look_at_stops", lambda ev, guarded=False: look(ev, guarded, now=at)):
            self.nt.step()  # every look of this step is made at 11:00:30
        # the live look at the top of the step did not hide the gap: read once, from the minute of the look before it
        self.assertEqual([t.strftime("%H:%M") for t in asked], ["10:50"])
''')
# 3. the lock that is free again: the run must not start git
edit(G, '''        with mock.patch.object(news_live.NewsTrader, "step", lambda self: []), \\
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \\
                mock.patch.object(news_live.time, "sleep", lambda s: None):
            self.assertEqual(news_live.run(max_minutes=0.0001, prime=False), 0)
''', '''        with mock.patch.object(news_live.NewsTrader, "step", lambda self: []), \\
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self: []), \\
                mock.patch.object(news_live.time, "sleep", lambda s: None), \\
                mock.patch.object(news_live, "code_stamp", lambda: {"commit": "x", "dirty": False, "started": "now"}):
            self.assertEqual(news_live.run(max_minutes=0.0001, prime=False), 0)
''')
for f in (G, PM):
    ast.parse((out_tree / "tests" / f).read_text(encoding="utf-8"))
print("base classes and three old methods edited")
