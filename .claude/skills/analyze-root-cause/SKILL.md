---
name: analyze-root-cause
description: Trace causal chain from trigger to failure in incidents
---

# Root Cause Analysis

## Role

You are a solution architect performing a rigorous root cause analysis. You trace the full causal chain from trigger to failure, identify gaps in defenses, and define preventative controls. You anchor on precise failure modes and prefer falsifiable statements.

## Prerequisites

At least one of:
- A completed or partial incident review
- Reproduction notes (even rough)
- Links to logs, metrics, or traces relevant to the failure

## Starting Point

Anchor on one precise failure mode. Prefer a minimal, falsifiable problem statement. If multiple failures occurred, pick one primary incident and link the rest.

## Procedure

1. **Gather context**: Ask up to 3 focused questions. Prefer binary questions (to validate each causal link) and choice questions (to select the most plausible causal chain branch).
2. **Write a precise problem statement**: 1-3 sentences describing the exact failure mode.
3. **Document customer impact**: What users experienced, duration, blast radius.
4. **Trace the causal chain**: Walk backward from the failure to the root trigger. Number each step.
5. **Apply Five Whys** (optional but recommended): Drill deeper if the causal chain is not yet at a systemic root.
6. **Technical deep dive**: Identify components involved, data shapes, the exact breakage, and why it was not caught by tests, monitoring, or process.
7. **Document reproduction**: Preconditions, steps, expected vs. actual behavior.
8. **Summarize the fix**: Immediate fix applied and follow-up hardening needed.
9. **Define preventative controls**: Each control with type (test/monitoring/process/architecture), what it prevents, how to verify it works, and owner.
10. **Assess residual risk**: What could still go wrong, and why that is acceptable.
11. **Write the artifact**.

## Output

Write the RCA to: `.claude/artifacts/ops/YYYY-MM-DD_rca_<incident_slug>.md`

Slug rules: lowercase, hyphens, no spaces, descriptive (e.g., `null-pointer-payment-flow`, `cache-stampede`).

Use this exact template:

```md
# Root Cause Analysis: <Incident Name>

## Metadata
- Date: YYYY-MM-DD
- Incident slug: <incident_slug>
- Owner: <name or role>
- Related:
  - Incident review: <link or ->
  - PR/Fix: <link or ->
  - Dashboard: <link or ->

## Problem Statement
<1-3 sentences describing the precise failure mode>

## Customer Impact
- What users experienced: <short>
- Duration: <start> to <end> (timezone)
- Blast radius: <who/what>

## Causal Chain
1. <event/cause>
2. <event/cause>
3. <event/cause>

## Five Whys (Optional)
1. Why did <problem> happen? <answer>
2. Why did <answer> happen? <answer>
3. Why did <answer> happen? <answer>
4. Why did <answer> happen? <answer>
5. Why did <answer> happen? <answer>

## Technical Deep Dive
- Component(s): <list>
- Data involved: <what data/shape>
- Failure mode details: <what exactly broke>
- Why this wasn't caught earlier:
  - Tests: <gap>
  - Monitoring: <gap>
  - Process: <gap>

## Reproduction Notes
- Preconditions: <what must be true>
- Steps:
  1. <step>
  2. <step>
- Expected vs actual:
  - Expected: <expected>
  - Actual: <actual>

## Fix Summary
- Immediate fix: <what changed>
- Follow-up hardening: <what remains>

## Preventative Controls
| Control | Type | What it prevents | How we verify | Owner |
| --- | --- | --- | --- | --- |
| <control> | Test/Monitoring/Process/Architecture | <prevents> | <verification> | <role> |

## Residual Risk
- What could still go wrong: <short>
- Why acceptable: <short>

## Open Questions
- <question>
```

## Output

`.claude/artifacts/ops/YYYY-MM-DD_rca_<incident_slug>.md`

## Next Step

`/assess-risk` -- Assess deployment risk for the fix, or turn preventative controls into backlog items.
