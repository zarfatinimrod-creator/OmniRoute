### Task 19: The new prompt texts, the git rule, the SKILL table

**Kind:** BUILD. **Spec:** 4.4 (watchdog steps 2, 3, 4, 7; the two tables), 4.7, 4.5 (the close slot), 8 (S2, R8, R12 as written text).

**Files:** Modify every file under `skills/trader/slots/`, `skills/trader/SKILL.md` (sections 0, 3א, 3ב), `CLAUDE.md` (hard rule 8). Delete `skills/trader/slots/news-watch-37.md` if Task 18 made it. Create `tests/test_slot_files.py`.

**Interfaces:** Consumes `supervise --status`, `--relayed`, `uptime-report --day --notify`, `ownerlines`. Produces the prompt texts that Tasks 20, 24 and 26 put on the tasks. Each file is edited from its Task 18 text; only what is named here changes:

- Every file, the crypto files too: the sync step `git pull --rebase ...` becomes `git fetch origin <branch>` and `git merge --no-edit origin/<branch>`. The closing steps become one block: commit own state; fetch and merge; push; on a rejected push fetch and merge again, up to 5 tries; never end the turn with a merge in progress (complete it, or `git merge --abort`); on a conflict send the S2 line with the file's name and stop, discarding nothing. The block holds the S2 text as `ownerlines` has it.
- `news-watch.md`, one text for both tasks: (a) `python3 -m aitrader.supervise --status --watchdog`, then what `action` says, by the action table of spec 4.4, before any git work; (b) push each `unsent` text through the Claude app, then `python3 -m aitrader.supervise --relayed ID...`; (c) `python3 -m aitrader postmortem`, as today; (d) the sync block. Removed: the launch of the bare engine (`news-live ... --minutes 110`), the 3-minute heartbeat rule and the turn's own "the engine was down" push (R4 owns that line). The wake rule becomes: when the background task ends, read its last line, run `--status`, do what `action` says.
- `close.md`: after its own duty, `python3 -m aitrader uptime-report --day --notify`, and push each text under `notify`.
- `SKILL.md` 3ב: the launch paragraph gives way to the parent (launched only as `--status` says, as a tracked background command; never `nohup`, `setsid` or `&`) and to the two tables of spec 4.4 in Hebrew (action -> what the session does; the parent's last line -> meaning -> expected action), with the R8 and R12 texts as `ownerlines` has them. Sections 0 and 3א: `git pull --rebase` becomes fetch and merge.
- `CLAUDE.md` hard rule 8 gains: "In the trader session's checkout nothing is ever rebased: `git fetch`, then `git merge --no-edit`. A turn never ends with a merge in progress. A conflict is reported, never resolved by discarding."

- [ ] Write `tests/test_slot_files.py`:

```python
ROOT = Path(__file__).resolve().parent.parent
SLOTS = ROOT / "skills" / "trader" / "slots"
LEAKS = (r"(session|trig|env)_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,}",     # an id has a digit in it; "<session-id>" is a word
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
        for f in [*SLOTS.glob("*.md"), *(p for p in (ROOT / "tests" / "fixtures").rglob("*") if p.is_file())]:
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
```

- [ ] Run `-p 'test_slot_files.py'`. Expected: the first test fails on `pull --rebase` in `close.md` (or whichever file sorts first).
- [ ] Edit the files as above.
- [ ] Run the file: 4 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/skills/trader/slots ai-trader/skills/trader/SKILL.md ai-trader/CLAUDE.md ai-trader/tests/test_slot_files.py`; message `docs(ai-trader): prompts and SKILL for the supervisor parent; fetch and merge in place of pull --rebase`.

