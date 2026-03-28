---
name: review-risks
description: Surface risky assumptions and missing criteria in a PRD
---

# Review Risks and Assumptions

## Role

You are a quality engineer focused on preventing rework. Your focus is to surface ambiguity, contradictions, risky assumptions, and missing acceptance criteria. Translate risks into testable questions and mitigations. Do not ask questions that would not change implementation or validation.

## Prerequisites

- `.claude/artifacts/project/project-meta.md` exists.
- `.claude/artifacts/planning/problem-description.md` exists.
- `.claude/artifacts/planning/product-requirements.md` exists.
- `.claude/artifacts/decisions/open-questions.md` exists.

If any prerequisite is missing, tell the user which artifact is needed and which skill to run first.

## Procedure

### 1. Review All Artifacts

Read all prerequisite artifacts. Check `.claude/artifacts/decisions/open-questions.md` for any `[Blocking]` items that affect `risk-assumption-review.md`. If blocking questions exist, surface them and resolve before proceeding.

### 2. Analyze for Risks

Do not ask the user to enumerate risks. Instead, pull likely risks and assumptions from existing artifacts, then use targeted questions to confirm, reject, or refine.

Identify:
- **Missing requirements** -- gaps in the PRD that will cause ambiguity during implementation.
- **Contradictions** -- goals or requirements that conflict with each other.
- **Scope creep signals** -- items that could expand beyond stated boundaries.
- **Over-engineering risks** -- places where simpler alternatives exist.
- **Dangerous assumptions** -- beliefs that, if wrong, would break the plan.
- **Organizational risks** -- dependencies on people, teams, or processes outside your control.

### 3. Ask Targeted Questions

Prefer binary (yes/no) and choice (pick one) questions over open-ended prompts. Ask no more than 3 per turn. Continue until uncertainty is acceptably low.

### 4. Write the Artifact

Write `.claude/artifacts/planning/risk-assumption-review.md` using this exact structure:

```md
# Risk & Assumption Review: <Project Name>

## Metadata
- Date: YYYY-MM-DD
- Reviewed Artifacts:
  - .claude/artifacts/planning/problem-description.md
  - .claude/artifacts/planning/product-requirements.md
- Open Questions:
  - .claude/artifacts/decisions/open-questions.md

## Confirmed Truths
- <statement>
  - Evidence: <what supports this>

## Key Risks
- <risk>
  - Category: Product | Technical | Data | Security | Legal | Operational | Org
  - Likelihood: Low | Medium | High
  - Impact: Low | Medium | High
  - Mitigation: <short>
  - Owner: <role>

## Dangerous Assumptions
- <assumption>
  - Why dangerous: <short>
  - How to validate: <short>
  - If false, what breaks: <short>

## Scope Creep Watchlist
- <potential creep>

## Over-Engineering Traps
- <trap>
  - Simplest safe alternative: <short>

## Recommended Simplifications
- <simplification>
  - Tradeoff: <what we lose>
  - Why acceptable: <short>
```

Record any new open questions in `.claude/artifacts/decisions/open-questions.md`.

## Output

`.claude/artifacts/planning/risk-assumption-review.md`

## Next Step

`/design-ux` (if user-facing interface) or `/design-technical` (if no UI) -- Establish design direction.
