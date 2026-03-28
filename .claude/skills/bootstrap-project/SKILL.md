---
name: bootstrap-project
description: Create .claude/artifacts/ structure and initial files
---

# Bootstrap Project Artifacts

## Role

You are a pragmatic product manager helping initialize a new project's artifact structure.

## Prerequisites

- You are in a project repository root directory.
- The `.claude/artifacts/` directory does not yet exist (or is incomplete).

## Procedure

### 1. Gather Project Identity

Ask the user for the following (ask all at once):

1. **Project name** -- the human-readable name for the project.
2. **One-sentence description** -- what the project does or aims to solve.
3. **Owner** -- name or role of the primary owner.

If the user does not provide all three, use sensible defaults:
- Owner defaults to the git user name if available.
- Description defaults to "TBD".

### 2. Create Directory Structure

Create the following directories:

```
.claude/artifacts/
  planning/
    tasks/
  decisions/
  project/
  ops/
```

### 3. Create project-meta.md

Write `.claude/artifacts/project/project-meta.md`:

```md
# Project Meta

## Identity
- Project Name: <project name>
- Description: <one-sentence description>

## Ownership
- Owner: <owner>

## Dates
- Started: <today's date, YYYY-MM-DD>

## Links
- Repository: <auto-detect from git remote, or "TBD">
- Docs: TBD

## Notes
- <any notes from the user, or remove this section>
```

### 4. Create decision-log.md

Write `.claude/artifacts/decisions/decision-log.md`:

```md
# Decision Log

| Date | Decision | Why | Tradeoff |
| --- | --- | --- | --- |
```

### 5. Create open-questions.md

Write `.claude/artifacts/decisions/open-questions.md`:

```md
# Open Questions

## Open

(No open questions yet.)

## Resolved

(No resolved questions yet.)
```

Format notes for open questions (used by other skills):
- Use `- [ ] [Blocking] [Affects: <artifact-filename>] <question> (Answer: TBD)` for blocking questions.
- Use `- [ ] [Affects: <artifact-filename>] <question> (Answer: TBD)` for non-blocking questions.
- Resolved items use `- [x] [Affects: <artifact-filename>] <question> (Answer: <answer>) (Date: YYYY-MM-DD)`.

### 6. Confirm

Show the user a summary of what was created.

## Output

- `.claude/artifacts/project/project-meta.md`
- `.claude/artifacts/decisions/decision-log.md`
- `.claude/artifacts/decisions/open-questions.md`
- Directory structure created

## Next Step

`/describe-problem` -- Start planning the project by describing the problem to solve.
