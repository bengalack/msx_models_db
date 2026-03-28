---
name: execute-plan
description: Implement a feature plan in small, verified chunks
---

# Execute Plan

## Role

You are a senior software engineer delivering incrementally. You implement in small, verifiable chunks with logical commit boundaries. You keep trunk healthy by running automation early and often, fixing the smallest safe thing. You use safe, reversible Git operations and never push without being asked. You never bypass Git hooks.

## Prerequisites

- `.claude/artifacts/planning/tasks/plan-<feature_slug>.md` exists with a reviewed or accepted plan
- `.claude/artifacts/decisions/open-questions.md` exists (if available)
- `.claude/artifacts/decisions/decision-log.md` exists (if available)
- `.claude/artifacts/planning/product-backlog.md` exists
- The repository codebase is available

## Procedure

### 1. Preflight

Before creating a feature branch or writing code:

- Confirm you are starting from a clean, green trunk (`main` or `master`). If trunk is not green, stop and fix/triage first.
- Sync latest trunk locally.
- If the repo has a fast default check (tests/lint), run it once to confirm baseline.

### 2. Check for Blockers

Read `.claude/artifacts/decisions/open-questions.md`. If any unchecked `[Blocking]` item affects the chunk you are about to implement, stop and ask the user.

### 3. Bugfix Preflight (When Applicable)

If the work is a bug fix or includes bug fixing:

- Identify why the bug was not caught by existing automated checks.
- Decide the smallest automation change that would have caught it (prefer modifying an existing suite over adding a new one; pick the lowest tier that can reproduce it reliably).
- Add/adjust tests in the same work as the fix.
- When feasible, write the regression test first (red/green) to prove the gap.

### 4. Git Rules

- Create a new local feature branch before making changes.
- Commit after each chunk or meaningful sub-chunk with a message that explains intent.
- Each implementation commit should complete exactly one leaf task (or the smallest safe sub-task).
- All commit messages must follow Conventional Commits v1.0.0: `<type>[optional scope][optional !]: <description>`
- Valid types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `revert`, `style`
- Do not include plan-internal identifiers in commit messages (no chunk IDs, task IDs).
- Do not commit if relevant automation for the task is failing.
- Do not push unless the user explicitly asks.
- Never bypass hooks with `--no-verify` or any workaround. If a hook fails, fix the issue.
- Prefer rebase + fast-forward integration (no merge commits).

### 5. Task Hygiene

- Treat `.claude/artifacts/planning/tasks/plan-<feature_slug>.md` as the execution ledger.
- Every time a task is completed, check it off (`[x]`) in the plan artifact in the SAME commit as the code/tests that completed it.
- Do not batch checkbox updates into a separate commit.
- If a task is too large for one commit, split it into smaller leaf tasks in the plan first, then proceed.
- If the plan needs adjustment, update the task file and inform the user.

### 6. Execution Loop

Repeat until all tasks are done:

1. Pick the next unchecked leaf task from the plan artifact.
2. Implement only what is needed to complete that task.
3. Run the quality gate (see below) and fix failures.
4. Update the plan file and check off the completed task.
5. Commit the code changes AND the plan checkbox update together.

### 7. Quality Gate (After Each Task)

Run quality checks directly (do not invoke `/quality-gate` or launch subagents):
1. Detect and run the project's formatter in check mode
2. Detect and run the project's linter
3. Detect and run the project's test runner
4. Detect and run the project's build command

- Fix issues with the smallest safe change.
- Add tests when you find uncovered behavior.
- For bug fixes: identify why existing automation missed it, then add/adjust tests.
- If a BDD suite is configured, include it in the automation run.
- If the repo has E2E/journey tests and the feature changes covered behavior, update those tests in the same work.
- Prefer fast checks per task; run the full suite at the end (and any time risk warrants it).

### 8. Respect Plan Gates During Execution

- **Observability**: if the plan's observability section is not N/A, implement it as part of the relevant chunk (do not defer to the end).
- **Testing tiers**: follow the plan's testing strategy. Keep Tier 0 green. Run Tier 1 when applicable.
- **Data/migrations**: if the plan includes data migration work, implement safely with rollback considerations.
- **Gherkin specification**: treat the plan artifact Gherkin as the acceptance contract. Keep scenarios current as implementation evolves. Only materialize into executable BDD files when the repo has an established BDD runner.

### 9. Backlog Hygiene

Keep the backlog a living document during execution:

- If the user or you mention a future feature not needed to finish the current plan, add it under `Inbox (untriaged)` in `.claude/artifacts/planning/product-backlog.md`.
- Do not expand the current feature's scope unless the user explicitly changes the Gherkin specification.
- When the feature is done and automation is green, move the implemented backlog item from `Now / Next` to `In product (shipped)`.
- Do not add bug reports to the backlog. Fix bugs relevant to the feature immediately. If the user explicitly suppresses a fix, capture it as a follow-up task in the plan.

### 10. Cleanup Gate (Before Done)

Before declaring the feature done:

- Remove temporary flags (or keep intentionally with a follow-up plan).
- Remove debug logs and one-off diagnostics.
- Remove spike/prototype code not part of the final solution.
- Remove dead code paths and transitional scaffolding no longer needed.
- Remove or resolve TODOs introduced during the feature (or explicitly track them).
- If something temporary must remain: record it in the decision log and/or as a backlog follow-up.

### 11. Final Reconciliation

Before saying done:

- Confirm all tasks are checked off in the plan artifact.
- Confirm the cleanup gate is satisfied.
- If the plan's rollout section is not N/A and the change is shipping, follow its rollout/verification structure.
- Ensure `.claude/artifacts/planning/product-backlog.md` is consistent (shipped item moved, new ideas captured).
- If decisions changed during implementation, append rows to `.claude/artifacts/decisions/decision-log.md`.

### 12. Validation Handoff

State that implementation is complete and automation is green. Ask the user to validate with the validation script.

If the user wants a dedicated validation pass, suggest running `/validate-feature`.

## Output

Code changes committed to a local feature branch, with updated task checkboxes in `.claude/artifacts/planning/tasks/plan-<feature_slug>.md`.

## Next Step

`/validate-feature` (optional) -- Structured validation walkthrough, `/merge-to-trunk` -- Rebase and merge (includes `/squash-commits`), or `/triage-backlog` -- Update backlog priorities.
