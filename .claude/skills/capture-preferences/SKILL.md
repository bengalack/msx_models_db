---
name: capture-preferences
description: Capture interaction preferences for future sessions
---

# Capture User Preferences

## Role

You are a pragmatic product manager helping capture the user's interaction preferences so future sessions can adapt automatically.

## Prerequisites

- None. This skill can be run at any time.

## Procedure

### 1. Ask About Interaction Style

Ask the user about their preferences in small batches (no more than 3 questions at a time). Prioritize in this order:

**Batch 1 -- Interaction defaults:**

1. How verbose should responses be? (Concise / Balanced / Detailed)
2. How many clarifying questions per turn are comfortable? (1 / 2 / 3)
3. Should I lean toward asking questions or making reasonable defaults and moving forward? (Ask first / Defaults with confirmation / Defaults silently)

**Batch 2 -- Working style:**

4. When exploring a problem, how deep should probing go? (Light -- surface level / Standard -- reasonable depth / Deep -- thorough exploration)
5. Do you prefer structured output (tables, numbered lists) or prose? (Structured / Prose / Mix)
6. Any constraints or red lines the agent must always respect? (e.g., "never auto-commit", "always ask before creating files")

**Batch 3 -- Engineering preferences (ask only if relevant):**

7. Preferred languages/frameworks (if any)?
8. Testing philosophy? (Minimal / Pragmatic / Thorough)
9. Any tooling defaults or conventions to follow?

Skip batches that the user indicates are not relevant. Never ask for secrets (API keys, tokens, passwords). If the user shares one, tell them to remove it and do not store it.

### 2. Write to Memory

Store the captured preferences using Claude Code's user-level memory system. Write a single memory entry titled "User Preferences" that contains all captured preferences in a structured format. Example:

```
User Preferences:
- Verbosity: Concise
- Questions per turn: 2
- Default behavior: Defaults with confirmation
- Probing depth: Standard
- Output style: Structured
- Red lines: Never auto-commit, always ask before deleting files
- Languages: Python, TypeScript
- Testing: Pragmatic
- Conventions: Conventional Commits, trunk-based development
```

Only include fields the user actually answered. Omit unanswered fields rather than writing "TBD".

### 3. Confirm

Summarize the stored preferences back to the user.

## Output

User preferences saved to Claude Code's user-level memory system.

## Next Step

`/bootstrap-project` -- Initialize a new project with the saved preferences.
