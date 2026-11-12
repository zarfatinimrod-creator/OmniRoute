"""The scheduled prompts (skills/trader/slots/) and the trader skill: fetch and merge in place of pull --rebase, the
watchdog asks the supervisor parent, the close slot reports the day, and the public repository names no session, task,
topic or address (supervisor spec 4.4, 4.5, 4.7, 8; plan Task 19). Task 19b (Ruling 57): every sync checks for a
conflict before it merges, a conflict never skips the slot's work, the woken turn acts on the parent's last line, and
the crypto push loop's exit code says whether it pushed (run with real git in throwaway repositories)."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from aitrader import ownerlines

ROOT = Path(__file__).resolve().parent.parent
SLOTS = ROOT / "skills" / "trader" / "slots"
LEAKS = (r"(session|trig|env)_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,}",     # an id has a digit in it; "session_context" is a word
         r"ntfy\.sh/(?!TOPIC\b)[A-Za-z0-9_-]+", r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[a-z]{2,}", r'"topic"\s*:\s*"(?!TOPIC")')
CHECK = "git merge-tree --write-tree --name-only HEAD origin/"   # the conflict check that touches neither index nor tree
BRANCH = "ccr-120121ba-vsvwlj"                                   # the live branch the slot texts sync with
LOOP = re.compile(r'(?:ok=; )?for i in 1 2 3 4 5; do .*?; done(?:; test -n "\$ok")?')   # the crypto push loop, one line


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
        # S2 belongs to the closing block, after the slot's work (brief; spec 4.7): a conflict at the start must not
        # skip the work - the close-time stock stop check is in it. Task 19b: the start sync checks before it merges
        # (`&& git merge-tree ...`); `git merge --abort` stays as the backstop for a merge left in progress
        checked = []
        for f in sorted(SLOTS.glob("*.md")):
            first = next(line for line in f.read_text(encoding="utf-8").splitlines() if line.startswith("1."))
            if "&& " + CHECK not in first:   # no start sync: news-watch syncs at its end, the dashboard runs no git
                continue
            checked.append(f.name)
            self.assertEqual([w in first for w in ("git merge --abort", "then go on with this slot's work on the local state", "'s rule")],
                             [True, True, False], f.name)
        self.assertEqual(checked, ["close.md", "crypto-decide.md", "crypto-fill.md", "crypto-summary.md", "midday.md", "open.md", "weekly.md"])

    # Task 19b (Ruling 57), item 8
    def test_every_slot_that_runs_git_checks_for_a_conflict_before_it_merges(self):   # (a)
        for f in sorted(SLOTS.glob("*.md")):
            t = f.read_text(encoding="utf-8")
            if "git " not in t:
                continue
            for must in (CHECK, "git merge --abort"):
                self.assertIn(must, t, f.name)

    def test_no_slot_file_stops_on_a_conflict(self):   # (b): the steps after a closing block still run
        self.assertEqual([f.name for f in sorted(SLOTS.glob("*.md")) if "and stop" in f.read_text(encoding="utf-8")], [])

    def test_the_woken_turn_acts_on_the_parents_last_line_and_a_cleared_halt_launches(self):   # (c)
        t = (SLOTS / "news-watch.md").read_text(encoding="utf-8")
        self.assertEqual([w in t for w in ("last-line table", ".cache/parent_relaunched", ownerlines.LINES["R12"][1])],
                         [True, True, True])
        halted = next(line for line in t.splitlines() if line.lstrip().startswith("- `halted`"))
        self.assertRegex(halted, r"--clear-halt.*--status --watchdog` again")

    def test_every_supervise_and_launch_command_of_the_watchdog_starts_from_a_named_directory(self):   # (d)
        t = (SLOTS / "news-watch.md").read_text(encoding="utf-8")
        n = t.count("python3 -m aitrader.supervise")
        self.assertGreaterEqual(n, 4)       # --status --watchdog, the wake's --status, --clear-halt, --relayed
        self.assertEqual(t.count("`cd /home/user/OmniRoute/ai-trader && python3 -m aitrader.supervise"), n)
        self.assertIn("`cd /home/user/OmniRoute/ai-trader && python3 -m aitrader.supervise --status`", t)   # the wake
        self.assertEqual(t.count("launch.command"), 1)
        self.assertIn("`cd /home/user/OmniRoute && ` followed by `launch.command`", t)

    def test_claude_md_syncs_without_git_pull(self):   # (e)
        self.assertNotIn("`git pull`", (ROOT / "CLAUDE.md").read_text(encoding="utf-8"))


class CryptoPushLoop(unittest.TestCase):
    """(f) The crypto push loop exactly as crypto-fill.md writes it, run with bash in one of two clones of a local bare
    remote under a temporary directory. Never origin, the network or this checkout's own .git: every git call and the
    loop run with cwd in the temporary directory, the environment is no_phone.clean_env() (no GIT_*, AITRADER_*, proxy
    or BASH_ENV variable of this process) with no user or system git config, and the remote is a local path."""

    def setUp(self):
        line = LOOP.search((SLOTS / "crypto-fill.md").read_text(encoding="utf-8"))[0]
        self.assertIn("sleep $((2**i))", line)
        self.line = line.replace("sleep $((2**i))", "true")   # the one change: the 2+4+8+16+32 s back-off would only slow the test
        self.tmp = Path(tempfile.mkdtemp(prefix="crypto-loop-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.assertNotIn(ROOT, self.tmp.parents)
        self.env = no_phone.clean_env(HOME=str(self.tmp), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                                      GIT_TERMINAL_PROMPT="0", GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="nobody",
                                      GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="nobody", LC_ALL="C")
        self.remote = self.tmp / "remote.git"
        self.git(self.tmp, "init", "-q", "--bare", "-b", BRANCH, str(self.remote))
        seed = self.tmp / "seed"
        self.git(self.tmp, "init", "-q", "-b", BRANCH, str(seed))
        self.commit(seed, "ai-trader/state/backlog.md", "first\n")
        self.git(seed, "remote", "add", "origin", str(self.remote))
        self.git(seed, "push", "-q", "origin", BRANCH)
        self.mine, self.other = self.tmp / "mine", self.tmp / "other"
        for clone in (self.mine, self.other):   # the remote is `origin` in each, the branch is checked out
            self.git(self.tmp, "clone", "-q", "-b", BRANCH, str(self.remote), str(clone))

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True, capture_output=True, text=True,
                              timeout=30).stdout.strip()

    def commit(self, clone: Path, name: str, text: str) -> str:
        (clone / name).parent.mkdir(parents=True, exist_ok=True)
        (clone / name).write_text(text, encoding="utf-8")
        self.git(clone, "add", name)
        self.git(clone, "commit", "-q", "-m", f"change {name}")
        return self.git(clone, "rev-parse", "HEAD")

    def run_loop(self) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", "-c", self.line], cwd=self.mine, env=self.env, capture_output=True, text=True,
                              timeout=60)

    def on_remote(self, sha: str) -> bool:
        return subprocess.run(["git", "--git-dir", str(self.remote), "merge-base", "--is-ancestor", sha, BRANCH],
                              cwd=self.tmp, env=self.env, capture_output=True, timeout=30).returncode == 0

    def test_a_conflict_ends_nonzero_names_the_file_and_leaves_no_merge_and_the_tree_as_it_was(self):
        self.commit(self.other, "ai-trader/state/backlog.md", "theirs\n")
        self.git(self.other, "push", "-q", "origin", BRANCH)
        mine = self.commit(self.mine, "ai-trader/state/backlog.md", "ours\n")
        done = self.run_loop()
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((self.mine / ".git" / "MERGE_HEAD").exists())
        self.assertEqual([self.git(self.mine, "status", "--porcelain"), self.git(self.mine, "rev-parse", "HEAD"),
                          (self.mine / "ai-trader/state/backlog.md").read_text(encoding="utf-8")], ["", mine, "ours\n"])
        self.assertIn("ai-trader/state/backlog.md", done.stdout)   # the conflicted file is printed: S2's {file}
        self.assertFalse(self.on_remote(mine))

    def test_a_clean_change_on_the_remote_is_merged_and_both_commits_are_pushed(self):
        theirs = self.commit(self.other, "other.txt", "theirs\n")
        self.git(self.other, "push", "-q", "origin", BRANCH)
        mine = self.commit(self.mine, "ai-trader/state/backlog.md", "ours\n")
        done = self.run_loop()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([self.on_remote(mine), self.on_remote(theirs)], [True, True])

    def test_a_remote_that_rejects_every_push_ends_nonzero_after_five_tries_with_the_commit_still_local(self):
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text('#!/bin/sh\necho try >> "$GIT_DIR/../tries"\nexit 1\n', encoding="utf-8")
        hook.chmod(0o755)
        mine = self.commit(self.mine, "ai-trader/state/backlog.md", "ours\n")
        done = self.run_loop()
        self.assertNotEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((self.tmp / "tries").read_text(encoding="utf-8").count("try"), 5)
        self.assertEqual([self.git(self.mine, "rev-parse", "HEAD"), self.on_remote(mine)], [mine, False])

    def test_the_crypto_slots_and_the_skill_carry_the_same_loop(self):   # the line run above is the one they all run
        texts = [(SLOTS / f).read_text(encoding="utf-8") for f in ("crypto-decide.md", "crypto-fill.md", "crypto-summary.md")]
        texts.append((SLOTS.parent / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual({m[0] for t in texts for m in LOOP.finditer(t)}, {LOOP.search(texts[1])[0]})


if __name__ == "__main__":
    unittest.main()
