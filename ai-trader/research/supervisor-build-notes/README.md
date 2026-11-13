# Supervisor build notes (backup snapshot, not for the live branch)

A snapshot of the controller's working folder for the supervisor plan (`research/plans/2026-11-10-supervisor.md`),
taken on 2026-11-13 so the unlanded build survives the loss of the cloud machine it was built on.

- **The code** is every commit of branch `supervisor-build-backup` below its top commit: rollout step 2
  (Tasks 10-19b), not yet landed. The top commit adds only this folder.
- **Landing:** never merge this folder into the live branch. Merge the commit below it (`supervisor-build-backup~1`),
  through the landing gate in `task-20-runbook.md` and `task-20-brief.md`.
- **Where things stand:** `progress.md` is the ledger, newest lines last (Rulings 1-60). Next: Tasks 19c, 14f, 14g
  (briefs here), then Task 20, the landing (moved to Sunday 2026-11-15 by Ruling 60). `rulings-10-28.md` holds the
  pre-flight rulings for Tasks 10-28. `reviews/` holds the two adversarial reviews of 2026-11-12 that the 14f, 14g and
  19b briefs cite. `workflows/supervisor-build-wave.js` is the build-wave script.
- **Placeholders:** scratch paths, session and run ids, background task ids, addresses and the alert topic were
  replaced before this public push: `<SCRATCH>` (the build's scratch folder, with the gate clone at
  `<SCRATCH>/clones/sup`), `<TASKS>`, `<SCRATCH-PATH>`, `<SESSION-DIR>`, `<session-id>`, `<workflow-run>`,
  `<bg-task>`, `<email>`, `<topic>`. `safe` and `bin/claude` are the test wrapper and the model-CLI stand-in the build
  ran every python command through.
