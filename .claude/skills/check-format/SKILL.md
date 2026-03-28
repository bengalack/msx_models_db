---
name: check-format
description: Run formatters and verify formatting
user-invocable: false
allowed-tools: Bash
---

# Check Format

You run code formatters to ensure consistent code formatting.

## Context

You will be provided with:
- Project root directory
- Formatting tool configuration (if detectable)

## Procedure

1. **Detect formatting tool**

Check for formatting configuration in the project:
- `package.json` (Prettier, etc.)
- `.prettierrc` or `.prettierrc.*`
- `.prettierignore`
- `pyproject.toml` (Black, Ruff format, etc.)
- `.rustfmt.toml` or `rustfmt.toml`
- `.gofmt` or `go fmt` configuration
- Other project-specific formatters

2. **Determine formatting command**

Based on detected configuration, determine the appropriate command:

**JavaScript/TypeScript**:
- If Prettier: `npx prettier --check .` or `npm run format:check`
- If Biome: `npx @biomejs/biome check --write .`
- Fallback: Ask user for formatting command

**Python**:
- If Black: `black --check .`
- If Ruff: `ruff format --check .`
- Fallback: Ask user for formatting command

**Rust**:
- `cargo fmt -- --check`

**Go**:
- `gofmt -l .` or `go fmt ./...`

**Other**:
- Ask user: "What command runs your project's formatter?"

3. **Run formatter**

Execute the formatting command:
- Check mode first (read-only, no changes)
- If check passes, formatting is correct
- If check fails, report what needs formatting

4. **Handle failures**

If formatter check fails:
- Report which files need formatting
- Suggest running formatter in fix mode
- Ask if you should auto-format (if safe)

## Output

Return a structured object to the parent workflow:

```yaml
format_check:
  status: pass | fail | skipped
  tool: <detected formatter name or "manual">
  command: <command that was run>
  files_needing_formatting:
    - <file1>
    - <file2>
  suggestion: <what to do next>
```

## Principles

- **Tech-stack agnostic**: Detect the formatter, don't prescribe one
- **Non-destructive**: Run in check mode first
- **Clear feedback**: Report exactly what needs formatting

## Example

**Input**: Node.js project with Prettier

**Output**:
```yaml
format_check:
  status: pass
  tool: Prettier
  command: npx prettier --check .
  files_needing_formatting: []
  suggestion: null
```
