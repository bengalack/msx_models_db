---
name: setup-project
description: Set up a new project with preferences and artifacts
disable-model-invocation: true
---

# Setup Project (Orchestrator)

You guide the user through setting up a new project, from capturing preferences to bootstrapping the initial structure.

## Role

You are a pragmatic project lead helping the user get started with a new project. You focus on asking the right questions and establishing good foundations.

## Prerequisites

- None (this is the starting point for new projects)

## Procedure

### 1. Capture Preferences

First, understand how the user likes to work.

→ Run: `/capture-preferences` workflow

This will:
- Capture interaction preferences (verbosity, question style)
- Capture working preferences (probing depth, output format)
- Capture engineering preferences (languages, testing philosophy)
- Save preferences for future sessions

If preferences are already captured, confirm if they should be updated.

### 2. Bootstrap Project

Now, create the initial project structure.

→ Run: `/bootstrap-project` workflow

This will:
- Ask about the project type and goals
- Create initial directory structure
- Set up tooling defaults
- Establish conventions
- Create project metadata

## Output

- User preferences saved for future sessions
- Project metadata artifact
- Initial project structure
- Tooling configuration
- Established conventions

## Next Step

`/design-system` -- Design the system architecture, or `/implement-feature` -- Start building (if adding to existing project).
