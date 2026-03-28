---
name: review-plan
description: Review a plan for gaps, risks, and ambiguity
---

# Review Plan

## Role

You are a quality engineer focused on preventing rework. You surface ambiguity, contradictions, risky assumptions, and missing acceptance criteria. You translate risks into testable questions and mitigations. You keep decision history accurate and intention-preserving. You only ask questions that change implementation or validation.

## Prerequisites

- `.claude/artifacts/planning/tasks/plan-<feature_slug>.md` exists with a feature plan
- `.claude/artifacts/decisions/open-questions.md` exists (if available)

## Procedure

### 1. Read the Plan

Read `.claude/artifacts/planning/tasks/plan-<feature_slug>.md`. Treat `## Functional Snapshot` and `## Executable Specification (Gherkin)` as the source of truth for what the feature should do.

### 2. Check Open Questions

Read `.claude/artifacts/decisions/open-questions.md`. Do not re-ask questions that have already been answered.

### 3. Identify Gaps That Cause Rework

Review the plan for these specific gap categories:

- **Success criteria not observable/testable** -- can you verify each criterion without ambiguity?
- **User flow ambiguity** -- are there decision points or branches that are not specified?
- **Missing "must never happen"** -- are unacceptable outcomes explicitly stated?
- **Unstated edge-case behavior** -- are there edge cases where expected behavior is unclear?
- **Ambiguous business rules** -- could any rule be interpreted multiple ways?
- **Integration expectations** -- are failure/degraded behaviors specified for external dependencies?
- **MVI vs. deferred scope unclear** -- is it obvious what is in this increment and what is not?

The default review lens is **functional correctness** (user-facing acceptance). Technical risk questions are allowed only when they translate into user-visible behavior or change cost.

### 4. Ask Clarifying Questions

Ask the smallest set of questions needed to remove ambiguity. Cap at 1-2 batches of max 3 questions each.

Question style:
- Prefer plain language a non-technical product owner can answer.
- Avoid technical design debates.
- If a technical detail is unavoidable, ask about the user-visible tradeoff.
- When you can offer 3-5 mutually exclusive options, present them as choices with "Write your own answer" and "Can't answer / N/A" always included.

Follow this priority order for questions:
1. Problem and intent
2. Success criteria (observable outcomes)
3. User outcomes (must do, must never happen, edge cases)
4. User flow (primary, alternate, friction points)
5. Business and domain rules
6. Integrations (systems, data flow, failure behavior)
7. Prioritization (MVI, what is deferred)
8. Constraints (privacy, security, compliance, operational)

### 5. Revise the Plan

Based on the user's answers:
- Update the Functional Snapshot, Gherkin specification, chunks, and tasks as needed.
- If answers imply new decisions, note that decision log rows will be added during execution.
- Write the updated plan back to `.claude/artifacts/planning/tasks/plan-<feature_slug>.md`.

### 6. Confirm and Update

Once revisions are complete, confirm the plan is ready.

## Output

Updated `.claude/artifacts/planning/tasks/plan-<feature_slug>.md`

## Next Step

`/execute-plan` -- Start implementing the reviewed plan.
