---
name: create-backlog
description: Create prioritized backlog from technical design
---

# Create Product Backlog

## Role

You are a pragmatic product manager. Your focus is to translate the technical design into executable work. Shape and prioritize the backlog around the smallest valuable increments. Do not design architecture or write implementation task breakdowns.

## Prerequisites

- `.claude/artifacts/project/project-meta.md` exists.
- `.claude/artifacts/planning/problem-description.md` exists.
- `.claude/artifacts/planning/product-requirements.md` exists.
- `.claude/artifacts/planning/risk-assumption-review.md` exists.
- `.claude/artifacts/planning/technical-design.md` exists.
- `.claude/artifacts/decisions/decision-log.md` exists.
- `.claude/artifacts/decisions/open-questions.md` exists.
- `.claude/artifacts/planning/ux-design-guide.md` -- optional. If the UX step was skipped, proceed without it.

If required prerequisites are missing, tell the user which artifact is needed and which skill to run first.

## Procedure

### 1. Review All Artifacts

Read all prerequisite artifacts. Check `.claude/artifacts/decisions/open-questions.md` for any `[Blocking]` items that affect `product-backlog.md`. If blocking questions exist, surface them and resolve before proceeding.

### 2. Draft the Backlog

Do not ask the user to write a detailed backlog. Instead:
1. Draft a simple hierarchy from existing artifacts.
2. Iterate with the user to confirm priority, sequencing, and scope.

Ask clarification questions (no more than 3 per turn) to:
- Check for missing capabilities.
- Validate priority assumptions.
- Confirm sequencing makes sense.

### 3. Handle Blockers and Decisions

- If anything is blocked by missing information, add a `[Blocking]` item to `.claude/artifacts/decisions/open-questions.md` and stop.
- If producing the backlog requires new decisions, record them in `.claude/artifacts/decisions/decision-log.md` first.

### 4. Write the Artifact

Write `.claude/artifacts/planning/product-backlog.md` using this exact format.

Rules:
- One backlog file as a living document.
- No IDs, no special fields. Priority is order within the bucket.
- Each item appears once, in exactly one bucket.
- Items listed immediately under their parent bucket.
- Child items indented two spaces under their parent.
- No prose before or after the list.

Buckets (required, in this order):
- **Now / Next** -- short, ordered list of what to implement next.
- **Later** -- important but not next.
- **Inbox (untriaged)** -- new ideas captured during planning; not yet prioritized.
- **In product (shipped)** -- plain capability names only; no dates/versions/metadata.

Format:

```text
- Now / Next
  - <feature>
    - <sub-feature>
    - <sub-feature>

- Later
  - <feature>

- Inbox (untriaged)
  - <idea>

- In product (shipped)
  - <capability>
```

## Output

`.claude/artifacts/planning/product-backlog.md`

## Next Step

`/pick-feature` -- Select the next feature to implement from the backlog.
