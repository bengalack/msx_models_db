---
name: check-build
description: Run build and verify compilation
user-invocable: false
allowed-tools: Bash
---

# Check Build

You run the build process to verify the project compiles or bundles successfully.

## Context

You will be provided with:
- Project root directory
- Build configuration (if detectable)

## Procedure

1. **Detect build system**

Check for build configuration in the project:
- `package.json` (build scripts, webpack, vite, etc.)
- `Cargo.toml` (cargo build)
- `go.mod` (go build)
- `Makefile` (make build)
- `pyproject.toml` (build, setuptools, hatch)
- `pom.xml` or `build.gradle` (Maven/Gradle)
- Other project-specific build systems

2. **Determine build command**

Based on detected configuration, determine the appropriate command:

**JavaScript/TypeScript**:
- If package.json has "build" script: `npm run build`
- If Next.js: `next build`
- If Vite: `npm run build` or `vite build`
- If webpack: `npm run build` or `webpack --mode production`
- Fallback: Ask user for build command

**Python**:
- If setuptools: `python -m build`
- If Hatch: `hatch build`
- Fallback: Ask user for build command

**Rust**:
- `cargo build --release`

**Go**:
- `go build ./...`

**Other**:
- Ask user: "What command builds your project?"

3. **Run build**

Execute the build command:
- Capture output
- Monitor for errors
- Measure build time

4. **Handle failures**

If build fails:
- Report compilation errors
- Show relevant error messages
- Identify the root cause (type errors, missing dependencies, etc.)
- Suggest fixes

## Output

Return a structured object to the parent workflow:

```yaml
build_check:
  status: pass | fail | skipped
  build_system: <detected build system or "manual">
  command: <command that was run>
  duration_seconds: <number>
  errors:
    - file: <path>
      line: <number>
      message: <error message>
  suggestion: <what to do next>
```

## Principles

- **Tech-stack agnostic**: Detect the build system, don't prescribe one
- **Production-focused**: Build for production when applicable
- **Clear errors**: Show what failed, not just that it failed

## Example

**Input**: Rust project with compilation error

**Output**:
```yaml
build_check:
  status: fail
  build_system: cargo
  command: cargo build --release
  duration_seconds: 12.1
  errors:
    - file: src/payment.rs
      line: 42
      message: mismatched types: expected `PaymentMethod`, found `&str`
  suggestion: "Fix type error at src/payment.rs:42, then re-run 'cargo build --release'"
```
