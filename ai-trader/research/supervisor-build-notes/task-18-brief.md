### Task 18: The scheduled prompts into git, as they stand

**Kind:** OPS - the owner's main chat session. **Spec:** 7.1 ("the first commit of each file is the task's text as it stands that day"; the three crypto tasks), 4.7 (the rule is in every scheduled prompt), 11.2 (the undo of steps 2 and 4).

**Files:** Create `ai-trader/skills/trader/slots/news-watch.md`, `dashboard.md`, `open.md`, `midday.md`, `close.md`, `weekly.md` (and `news-watch-37.md` only if the :37 task's text differs from the :07 task's); and `crypto-decide.md`, `crypto-fill.md`, `crypto-summary.md` for each crypto task that exists and is bound to the trader session.

- [ ] `list_triggers`. Proof: the seven trader tasks of the spec's table (two for `news-watch`) are in the reply, and the three crypto tasks if the go-live task of 2026-11-11 has made them; keep the reply in the scratch folder, not in the repository.
- [ ] Write into "Baseline record", for each task: its name, its cron, and "trader session" or "another session" by its `persistent_session_id` (never the id itself). The no-rebase rule is about the checkout the engine writes to: a crypto task bound to another session gets no slot file and keeps its prompt; one bound to the trader session is treated like the seven from here on.
- [ ] Write each of those prompts, unchanged, into its file.
- [ ] `grep -n -i -E "(session|trig|env)_[a-z0-9]{6}|ntfy\.sh/[a-z0-9]|[a-z0-9._-]+@[a-z0-9-]+\.[a-z]" ai-trader/skills/trader/slots/*.md`: no hit. A hit (a session id, a task id, a topic, an address) stops this task: the repository is public. The owner is asked, in one message, how that prompt should name the thing. Task 19 turns this check into a test.
- [ ] `git add ai-trader/skills/trader/slots/`; message `trader: the scheduled prompts as they stand, one file per slot`; fetch, merge, push. Write the commit into "Baseline record" as "prompt baseline": the undo of Tasks 20 and 24 restores every task from it.

