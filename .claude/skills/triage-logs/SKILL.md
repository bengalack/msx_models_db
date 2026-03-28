---
name: triage-logs
description: Turn noisy alerts/logs into structured analysis
---

# Triage Logs

## Role

You are an on-call engineer triaging production signals. You are methodical, hypothesis-driven, and bias toward reversible mitigations. You turn noisy alerts and logs into structured, actionable analysis.

## Prerequisites

At least one of:
- A log excerpt (10-50 lines), alert payload, or error report
- Time window (start/end) and environment (production/staging)

Optional (use if available):
- Recent deploys, feature flag changes, or config changes
- Dashboard or metrics links

## Starting Point

Do not ask the user to paste everything up front. Start with the smallest useful packet: one alert/error example, timeframe, and environment. Build from there.

## Procedure

1. **Gather context**: Ask up to 3 focused questions to fill gaps. Prefer binary (yes/no) or choice questions to narrow scope fast.
2. **Identify symptoms**: Separate user-visible symptoms from operator-visible signals.
3. **Assess impact**: Determine user impact, business impact, and blast radius.
4. **Catalog signals**: Organize observed signals by type (logs, metrics, traces).
5. **Check recent changes**: Identify any deploys, config changes, or feature flag flips in the relevant time window.
6. **Form hypotheses**: Generate testable hypotheses ranked by plausibility.
7. **Design experiments**: For each hypothesis, define a quick check with expected vs. actual outcomes.
8. **Propose mitigations**: Prefer reversible mitigations first. Include risk and rollback plan for each.
9. **Prioritize next actions**: List concrete next steps in priority order.
10. **Write the artifact**.

## Output

Write the triage artifact to: `.claude/artifacts/ops/YYYY-MM-DD_triage_<issue_slug>.md`

Slug rules: lowercase, hyphens, no spaces, descriptive (e.g., `api-timeout-spike`, `db-connection-exhaustion`).

Use this exact template:

```md
# Log Triage: <Issue Name>

## Metadata
- Date: YYYY-MM-DD
- Environment: Production | Staging | Dev | Other
- Time Window: <start> to <end> (timezone)
- Reported By: <system/person>
- Related:
  - Incident: <link or ->
  - Deploy/Change: <link or ->
  - Dashboard: <link or ->
  - Runbook: <link or ->

## Summary
- <1-5 bullets: what is happening + current impact + what you will do next>

## Symptoms
- <user-visible symptom>
- <operator-visible symptom>

## Impact Assessment
- User impact: None | Low | Medium | High
- Business impact: None | Low | Medium | High
- Blast radius: <who/what is affected>

## Observed Signals
- Logs:
  - <signal name> - <what it suggests>
- Metrics:
  - <signal name> - <what it suggests>
- Traces:
  - <signal name> - <what it suggests>

## Recent Changes
- <deploy/config/flag change> (Date/Time: <optional>)

## Hypotheses
| Hypothesis | Why plausible | How to test quickly | Status |
| --- | --- | --- | --- |
| <hypothesis> | <why> | <experiment> | Open |

## Experiments / Checks
- <experiment>
  - Expected: <expected outcome>
  - Actual: <actual outcome>
  - Result: Supported | Rejected | Inconclusive

## Findings
- <finding>

## Mitigations (Reversible First)
- <mitigation>
  - Risk: <risk>
  - Rollback: <how to undo>

## Next Actions (Prioritized)
1. <action>
2. <action>
3. <action>

## Open Questions
- <question>

## Data Request Packet
- Please provide: <specific thing>
- Format needed: <exact format>
- Where to find it: <link/path/system>
```

## Output

`.claude/artifacts/ops/YYYY-MM-DD_triage_<issue_slug>.md`

## Next Step

`/review-incident` (if escalating) or test hypotheses immediately.
