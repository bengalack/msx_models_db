---
name: plan-feature
description: Turn a backlog item into slices, tasks, and a plan
---

# Plan Feature

## Role

You are a senior software engineer delivering incrementally. You turn a selected backlog item into slices, tasks, and a concrete plan. You prefer user-facing language in questions and avoid exposing technical decisions unless unavoidable. If you must ask about a technical choice, translate it into a user-visible tradeoff.

You follow trunk-based development with Conventional Commits. You use safe, reversible Git operations and never push without being asked. You never bypass Git hooks.

## Prerequisites

- A feature has been selected (either via `/pick-feature` or stated by the user)
- `.claude/artifacts/planning/product-backlog.md` exists
- `.claude/artifacts/planning/product-requirements.md` exists (if available)
- `.claude/artifacts/decisions/decision-log.md` exists (if available)
- `.claude/artifacts/decisions/open-questions.md` exists (if available)

## Procedure

### 1. Check for Blockers

Read `.claude/artifacts/decisions/open-questions.md`. If any unchecked `[Blocking]` item affects this feature, stop and ask the user for an answer before proceeding.

### 2. Functional Elicitation Gate

Before drafting chunks or tasks, capture a crisp functional snapshot of the story. Read the backlog item being implemented and scan the requirements for relevant context. Incorporate any resolved answers from open questions.

If functional requirements are missing or ambiguous, ask questions in this order (cap at 1-2 batches of max 3 questions each):

1. **Problem and intent** -- what problem are we solving and why
2. **Success criteria** -- observable outcomes that mean "done"
3. **User outcomes** -- what the user must be able to do; what must never happen; most important edge cases
4. **User flow** -- primary path, alternate paths, current friction points
5. **Business and domain rules** -- rules that govern behavior
6. **Integrations** -- external systems, data flow, dependency constraints, failure expectations
7. **Prioritization** -- minimal viable increment (MVI), what must be correct first, what can be deferred
8. **Constraints** -- privacy/security, regulatory/compliance, operational limitations (not timelines)
9. **Delight and quality bar** -- what would exceed expectations; what would feel broken

**"Good enough to start" checklist** -- do not proceed until you can answer in plain language:
- Who is the primary user and what are they trying to accomplish?
- What does success look like (observable outcomes)?
- What is the primary user flow?
- What must never happen?
- What are the key edge cases and expected behavior?
- What business rules apply?
- What integrations exist and what happens when they fail (if applicable)?
- What is the MVI and what is explicitly deferred?

If any item is unknown and blocks correct delivery, add it to `.claude/artifacts/decisions/open-questions.md` as `[Blocking]` and stop.

### 3. Write the Gherkin Specification

Write a Gherkin specification for the selected story. Rules:

- Treat Gherkin as the source of truth for feature-level acceptance.
- Use business language and user-observable outcomes. Avoid UI mechanics unless no better abstraction exists.
- Target 3-7 scenarios for the MVI.
- Make scenarios deterministic (avoid time-dependent or non-deterministic data unless that is the subject under test; prefer concrete example values).
- Include at least:
  - One happy-path outcome
  - One "must never happen" scenario (error, access control, invariant, data loss, etc.)
  - One key edge-case behavior
  - One integration/dependency failure or degraded behavior (when applicable)

Structure:
- Use `Feature:` with a short narrative.
- Use `Background:` only for truly shared preconditions.
- Use `Rule:` to group business rules when helpful.
- Use `Scenario Outline:` + `Examples:` for input permutations.
- Each scenario describes one behavior. Given = preconditions; When = action; Then = observable result.
- Assert externally visible state (API response, persisted state, user-facing text) over internal details.

### 4. Assess Quality Gates

→ Run: `/assess-quality-gates` — evaluate observability, testing, data, and rollout concerns in parallel.

Review the returned assessment and incorporate the results into the plan artifact (section by section).

### 5. Plan Chunks and Tasks

Decompose into 2-6 independently testable chunks. Each chunk should deliver user value, be testable, and reduce risk. Plan the next chunk in full detail; keep later chunks lighter.

Write tasks so execution can be "commit-per-task": each leaf checkbox should be completable in a single commit.

**Backlog hygiene during planning**: if unrelated "later" ideas come up, capture them under `Inbox (untriaged)` in `.claude/artifacts/planning/product-backlog.md`. Do not expand the current feature's scope unless the user explicitly changes the definition of done.

**Release tasks** (if the user requests a release during planning):
1. Ask whether this is a release candidate (for validation) or a proper release (for production). Block until answered.
2. Review changes since the last release tag, suggest `major`, `minor`, or `patch` with reasoning. The user decides. Block until answered.
3. Add appropriate release tasks (bump version, update release notes, create tag).

### 6. Write the Plan Artifact

Write: `.claude/artifacts/planning/tasks/plan-<feature_slug>.md`

Use the template structure from [plan-template.md](plan-template.md). Adjust sections as needed for the specific feature.

## Output

`.claude/artifacts/planning/tasks/plan-<feature_slug>.md`

## Next Step

`/review-plan` (optional) or `/execute-plan` -- Review the plan for quality or start implementation.
