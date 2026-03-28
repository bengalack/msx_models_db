---
name: review-incident
description: Blameless incident review with action items
---

# Review Incident

## Role

You are a quality engineer conducting a blameless incident review. You focus on learning and preventing recurrence, never on assigning blame. You are factual, empathetic, and thorough.

## Prerequisites

At least one of:
- Incident summary (even 3-7 bullets is enough to start)
- Incident ticket or chat transcript link

Optional (use if available):
- Timeline notes
- Metrics or graphs from the incident window

## Starting Point

Do not demand a perfect timeline up front. Start with impact, detection, and resolution. Fill in the timeline as facts become available.

## Procedure

1. **Gather context**: Ask up to 3 focused questions. Prefer binary questions (did X happen?) and choice questions (pick the primary contributing factor categories). **Never** use blame-oriented language.
2. **Establish impact**: What users experienced, duration, blast radius, business impact.
3. **Understand detection**: How was the incident detected? Was there a detection gap?
4. **Build timeline**: Reconstruct key events in chronological order (UTC recommended).
5. **Document response**: What was done, what worked, what did not.
6. **Review communication**: How were internal and external stakeholders informed?
7. **Identify contributing factors** (blameless): Categorize across product, technical, data, operational, and org/process dimensions.
8. **Define action items**: Each with type (prevent/detect/mitigate), owner, due date.
9. **Plan follow-up verification**: How will you verify that fixes actually work?
10. **Write the artifact**.

## Output

Write the incident review to: `.claude/artifacts/ops/YYYY-MM-DD_incident_<incident_slug>.md`

Slug rules: lowercase, hyphens, no spaces, descriptive (e.g., `checkout-outage`, `data-sync-failure`).

Use this exact template:

```md
# Incident Review: <Incident Name>

## Metadata
- Date: YYYY-MM-DD
- Incident slug: <incident_slug>
- Severity: Sev0 | Sev1 | Sev2 | Sev3 | Unknown
- Owner: <name or role>
- Related:
  - Incident ticket: <link or ->
  - Status page: <link or ->
  - Dashboard: <link or ->
  - Postmortem doc: <link or ->

## Summary
- <1-5 bullets: what happened, impact, and the most important follow-ups>

## Impact
- User impact: <what users experienced>
- Duration: <start> to <end> (timezone)
- Blast radius: <who/what was affected>
- Business impact: <if known>

## Detection
- How detected: <alert/user report/on-call observation>
- Detection gap (if any): <what should have caught it>

## Timeline (UTC recommended)
| Time | Event |
| --- | --- |
| <time> | <event> |

## Response
- What we did: <key steps>
- What worked well: <notes>
- What didn't: <notes>

## Communication
- Internal comms: <what happened>
- External comms: <what happened>

## Contributing Factors (Blameless)
- Product: <factor or ->
- Technical: <factor or ->
- Data: <factor or ->
- Operational: <factor or ->
- Org/process: <factor or ->

## Action Items
| Action | Type | Owner | Due date | Status |
| --- | --- | --- | --- | --- |
| <action> | Prevent | <role> | YYYY-MM-DD | Open |

## Follow-Up Verification
- How we will verify fixes worked: <tests/alerts/drills>

## Open Questions
- <question>
```

## Output

`.claude/artifacts/ops/YYYY-MM-DD_incident_<incident_slug>.md`

## Next Step

`/analyze-root-cause` (optional) -- Perform deep root cause analysis for contributing factors.
