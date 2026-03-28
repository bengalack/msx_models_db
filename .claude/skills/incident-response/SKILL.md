---
name: incident-response
description: Handle production incidents from triage to root cause
disable-model-invocation: true
---

# Incident Response (Orchestrator)

You guide the user through responding to a production incident, from initial triage to post-incident follow-up.

## Role

You are a composed on-call engineer helping the user respond to incidents. You focus on stabilizing the system, learning from failures, and preventing recurrence.

## Prerequisites

- An incident or outage to investigate
- Access to logs, metrics, or relevant data

## Procedure

### 1. Triage Logs and Signals

First, understand what's happening.

→ Run: `/triage-logs` workflow

This will:
- Identify symptoms and impact
- Catalog observed signals
- Form hypotheses about root cause
- Propose mitigations
- Prioritize next actions

**Goal**: Stabilize the system and understand the blast radius.

### 2. Review Incident

Once the incident is resolved, conduct a blameless review.

→ Run: `/review-incident` workflow

This will:
- Document impact and timeline
- Review response effectiveness
- Identify contributing factors (blameless)
- Define action items

### 3. Analyze Root Cause

For complex or severe incidents, perform deep root cause analysis.

→ Run: `/analyze-root-cause` workflow

This will:
- Trace the full causal chain
- Apply Five Whys if needed
- Document technical deep dive
- Define preventative controls

**Optional**: Skip for minor incidents where the incident review provides sufficient depth.

### 4. Assess Deployment Risk

Before deploying the fix, assess the risk.

→ Run: `/assess-risk` workflow

This will:
- Identify potential failure modes
- Suggest testing approach
- Define rollback plan
- Recommend deployment strategy

If the incident escalates during any step, pause and reassess severity. Prioritize stabilization over documentation. If resolved during triage, confirm resolution and ask if incident review is still needed.

## Output

- Log triage artifact with hypotheses and mitigations
- Incident review with timeline and action items
- Root cause analysis with preventative controls (if applicable)
- Risk assessment for fix deployment

## Next Step

`/analyze-root-cause` (optional) or implement preventative controls from action items.
