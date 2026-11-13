# Task 8c review: a waiting exit is cancelled only with the owner's words (backlog 63)

Diff 7c37bd53..82b2036e (one commit), read in one pass from review-task-8c.diff. Judged against task-8c-brief.md as
corrected by controller-notes.md, "Rulings added 18:41 UTC" (answer B: not chained, `at` stamped by the command,
`exit_requests()[0]`, `--said` on the seven existing `--cancel` calls, README left alone).

### Spec Compliance
Compliant.
- `ai-trader/aitrader/__main__.py:380` `--said` without `--cancel` is refused first. `a.said is not None` means `--said ""` is refused too. The message is word for word, exit 2, and it comes before any file is touched.
- `__main__.py:387-391` `said = _clean(a.said or "", 120)`, the same cleaning as `--reason`. Missing or empty `--said` gives the brief's message word for word and exit 2. Both refusals come before `ncfg(load_config())` and `update_exits`, so the requests file is never opened for writing.
- `__main__.py:401-404` Nothing waiting: the existing message and exit 1. The new append comes after this return, so no row is written.
- `__main__.py:406-413` A dropped request appends `{"at": now_utc(), "symbol", "said", "request": was[sym]}`. `was` is the file as it was, under the lock (`news_live.py:538-542`). If the append raises, the brief's message goes to stderr with exit 1.
- `journal.py` and `news_live.py` are unchanged. `NEWS_CHAINED` does not gain the file.
- Docstring usage line (`__main__.py:31-32`), SKILL.md 3ב command line and bullet (`skills/trader/SKILL.md:223`), and `config.json` `news._note` all match the brief character for character. config.json gets no new key and no number.
- `tests/test_news_exit_cancel.py` has all six named tests with the brief's assertions. Two places use the ruled forms: `exit_requests()[0]`, and the `at`-is-aware check in place of `verify_chain`. `from helpers import no_phone` is the first import, after a module docstring, like the sibling modules. The test reuses `TempState` and does not copy it.
- `tests/test_news_inputs.py`: exactly the seven `--cancel` calls got `--said "cancel it"`. No assertion was changed.
- Check: `journal.append` (`journal.py:142-164`) chains only names in `CHAINED` and adds no time key. So ruling B holds: the row is plain, its time is the command's `at`, and a write error propagates. The failure path is live, not dead code.
- Check: `TempState` (`test_news_inputs.py`) has no `test_` methods, so importing it does not run the input tests twice. This agrees with the report's count, 673 = 667 + 6.

Cannot verify from this diff:
- That the new journal reaches git before the Saturday review. It is not git-ignored (`git check-ignore` exit 1). It rides on the cycle's "commit + push of `state/`" (SKILL.md:57). Whether every session that runs a cancel ends with that commit lives in the slot prompts, not in this diff.
- The rule 4 gate for a news-engine lever (the quant-critic PASS and the unit suite at the landing). It runs at the landing, not in this task.

### Strengths
- The checks are ordered so that no refusal can reach `update_exits`. The append runs only after the "nothing waiting" return, so a no-op cancel never leaves a row.
- `"request": was[sym]` takes the entry from the lock-held read inside `update_exits`. So two racing cancels of one symbol give exactly one row, and the row is the entry as it stood.
- The append failure is not swallowed. The operator gets a specific line, exit 1, and the requests file is not printed as if all went well.
- The edits to the seven existing calls make two tests stricter. The either/or test and the ticker test now fail for their own reason (argparse group, symbol check), not for the new refusal.
- The report is candid. It names the surviving mutant, the README line and two process slips, and the diff confirms each claim.
- No threshold literal is added. Nothing touches the phone, the network or the model. No exception text or topic reaches any output. No trading rule changes.

### Issues
#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)
- `ai-trader/tests/test_news_exit_cancel.py` (whole file): nothing tests that `--said` is cleaned. The brief requires `_clean(text, 120)`, the code does it (`__main__.py:387`), but a mutant that writes the raw `a.said` survives. Why it matters: the row is read at the Saturday review, and the 120 cap plus control-character stripping are the brief's contract. Fix: one test where `--said` holds a newline and `{` and the row's `said` comes back cleaned. The brief fixed the file at six tests, so this is for the controller to decide.
- `ai-trader/tests/test_news_exit_cancel.py:60-64`: the append-failure test asserts only exit 1 and the message. It does not check that BBB is really gone, even though the message says "was cancelled", and it does not check that stdout is empty. A reorder that appended before the drop would print a false "was cancelled" and still pass. Fix: add `self.assertNotIn("BBB", news_live.exit_requests()[0])`.
- `ai-trader/aitrader/__main__.py:410`: `except Exception:` drops the exception class. The constraints allow the class in an error path, though not the text. Printing `type(e).__name__` would tell the owner and the session whether this was a disk error or an encoding error, at no leak risk.
- `ai-trader/aitrader/__main__.py:406-416`: unlike `news-hold` (`__main__.py:368-369`), a successful cancel prints no "commit and push `state/news_exit_cancels.jsonl` now" reminder. It is covered today by the cycle's `state/` commit (SKILL.md:57). The brief did not ask for one.
- `ai-trader/tests/test_news_exit_cancel.py:26`: `TestCase.enterContext` needs Python 3.11 or later. This is its first use in the suite, and the project declares no minimum version. It is fine on the VM's 3.13. Noted only in case an older interpreter ever runs the suite.

### Assessment
Task quality: Approved. Every requirement in the brief and the 18:41 ruling is in the diff, word for word where the brief gives words, with refusals that cannot touch the requests file and a failure path that really fires. What is left is test coverage and diagnostics polish.
