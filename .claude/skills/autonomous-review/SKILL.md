# Autonomous review

Use after substantive edits when running without human approval.

Sequence:

1. Inspect `git diff` (or equivalent) for scope.
2. Run this repo’s real test/build/lint commands (discover from README, Makefile, CI, or manifests).
3. Spawn `code-reviewer` via Task.
4. Spawn `security-reviewer` via Task.
5. Apply clearly safe fixes from reviewers.
6. Re-run tests/build.
7. Report DONE only when verification has actually passed; otherwise FAILED with causes.

No approval prompts; no blocking questions to the operator.
