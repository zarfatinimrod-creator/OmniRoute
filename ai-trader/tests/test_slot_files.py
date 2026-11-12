"""The scheduled prompts (skills/trader/slots/) and the trader skill: fetch and merge in place of pull --rebase, the
watchdog asks the supervisor parent, the close slot reports the day, and the public repository names no session, task,
topic or address (supervisor spec 4.4, 4.5, 4.7, 8; plan Task 19)."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import re
import unittest
from pathlib import Path

from aitrader import ownerlines

ROOT = Path(__file__).resolve().parent.parent
SLOTS = ROOT / "skills" / "trader" / "slots"
LEAKS = (r"(session|trig|env)_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,}",     # an id has a digit in it; "session_context" is a word
         r"ntfy\.sh/(?!TOPIC\b)[A-Za-z0-9_-]+", r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[a-z]{2,}", r'"topic"\s*:\s*"(?!TOPIC")')


class SlotFiles(unittest.TestCase):
    def test_no_prompt_rebases_and_every_prompt_fetches_merges_and_knows_s2(self):
        files = sorted(SLOTS.glob("*.md"))
        self.assertGreaterEqual(len(files), 6)
        for f in files:
            t = f.read_text(encoding="utf-8")
            self.assertNotIn("pull --rebase", t, f.name)
            if "git " not in t:          # the dashboard prompt runs no git until Task 24
                continue
            for must in ("git merge --no-edit origin/", "git merge --abort", ownerlines.LINES["S2"][1].split("{file}")[0]):
                self.assertIn(must, t, f.name)

    def test_no_prompt_and_no_fixture_names_a_session_a_task_a_topic_or_an_address(self):   # Review Focus 5: the repository is public
        # ruling P19: a price panel (*.pkl) is binary and cannot carry a topic or an id; every text fixture is read
        for f in [*SLOTS.glob("*.md"), *(p for p in (ROOT / "tests" / "fixtures").rglob("*") if p.is_file() and p.suffix != ".pkl")]:
            t = f.read_text(encoding="utf-8", errors="replace")
            self.assertEqual([pat for pat in LEAKS if re.search(pat, t)], [], f.name)

    def test_the_watchdog_asks_status_and_no_longer_starts_the_bare_engine(self):
        t = (SLOTS / "news-watch.md").read_text(encoding="utf-8")
        self.assertEqual([m in t for m in ("aitrader.supervise --status --watchdog", "--relayed", "aitrader postmortem", "--minutes 110")], [True, True, True, False])
        self.assertFalse((SLOTS / "news-watch-37.md").exists())

    def test_the_close_slot_reports_and_the_skill_carries_r8_and_r12(self):
        self.assertIn("uptime-report --day --notify", (SLOTS / "close.md").read_text(encoding="utf-8"))
        skill = (SLOTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual([ownerlines.LINES[i][1] in skill for i in ("R8", "R12")] + ["pull --rebase" in skill], [True, True, False])

    def test_the_close_slot_copies_the_days_uptime_block_into_its_log(self):   # ruling P37 (Task 28's list A reads it)
        t = (SLOTS / "close.md").read_text(encoding="utf-8")
        copy = [line for line in t.splitlines() if "longest_blind_s" in line]
        self.assertEqual(len(copy), 1, "one step names the day's numbers")
        self.assertEqual([w in copy[0] for w in ("uptime-report --day", "`uptime`", "`commits`", "logs/YYYY-MM-DD-close.md")],
                         [True, True, True, True])

    def test_a_conflict_at_the_start_sync_is_aborted_and_the_slot_still_does_its_work(self):   # Task 19 review, F1
        # S2 and "stop" belong to the closing block, after the slot's work (brief; spec 4.7): a conflict at the start
        # must not skip the work - the close-time stock stop check is in it
        checked = []
        for f in sorted(SLOTS.glob("*.md")):
            first = next(line for line in f.read_text(encoding="utf-8").splitlines() if line.startswith("1."))
            if "&& git merge --no-edit origin/" not in first:   # no start sync: news-watch syncs at its end, the dashboard runs no git
                continue
            checked.append(f.name)
            self.assertEqual([w in first for w in ("git merge --abort", "then go on with this slot's work on the local state", "'s rule")],
                             [True, True, False], f.name)
        self.assertEqual(checked, ["close.md", "crypto-decide.md", "crypto-fill.md", "crypto-summary.md", "midday.md", "open.md", "weekly.md"])


if __name__ == "__main__":
    unittest.main()
