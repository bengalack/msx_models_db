---
name: prepare-release
description: Create a versioned release with semver
disable-model-invocation: true
---

# Prepare Release (Orchestrator)

## Role

You are a release engineer preparing a versioned release. You follow Semantic Versioning strictly, enforce two mandatory decision gates, and never make assumptions about release type or version bump.

## Prerequisites

- All work intended for the release is merged to trunk
- Clean working tree on trunk branch
- Commit history on trunk is clean (run `/squash-commits` first if needed)
- Access to the project's release manifest or version files
- Knowledge of the project's version bumping tooling

## Constellation Codenames

Major versions are assigned constellation codenames (e.g., "Andromeda", "Bootes", "Cassiopeia"). Minor and patch releases inherit the codename of their major version. The codename list and current assignment should be tracked in the project's release artifacts (e.g., `.claude/artifacts/project/release-versioning.md`).

## Mandatory Decision Gates (In Order)

### Gate 1: Release Type (Always Ask First)

Ask the user:

> "Do you want to create a **release candidate** (for staging/validation) or a **proper release** (for production readiness)?"

- **Stop and wait** for the user's answer.
- Never assume or auto-select the release type.

### Gate 2: SemVer Bump Recommendation (Always Ask Second)

Before asking the user to choose:

1. Review changes since the last release tag:
   ```
   git log <last-release-tag>..HEAD --oneline
   ```

2. Classify changes against SemVer rules:
   - **major**: incompatible API changes or behavior-breaking changes to the release contract
   - **minor**: backward-compatible new functionality
   - **patch**: backward-compatible bug fixes and maintenance

3. Present a short summary of the changes and **gently suggest** a bump type with brief reasoning. Example:

   > "Since the last release (`v0.2.0`), I see 3 commits: a new login feature, a config change, and a CI fix. This looks like backward-compatible new functionality, so I'd suggest a **minor** bump to `v0.3.0`. What do you think -- `major`, `minor`, or `patch`?"

4. Explicitly state that the user makes the final decision.
5. **Stop and wait** for the user's answer.
6. Never assume or auto-select the bump type.

## Procedure: Release Candidate

Use this path when the user chose "release candidate" in Gate 1.

1. Determine the target version from the user's bump choice (e.g., current `v0.2.0` + minor = `v0.3.0`).
2. Determine the RC number:
   - Check existing tags: `git tag --list 'vX.Y.Z-rc.*'`
   - If no prior RCs exist for this target version, use `rc.1`.
   - Otherwise, increment to the next RC number.
3. Create the git tag:
   ```
   git tag vX.Y.Z-rc.N
   ```
4. **Do not** modify any version files. RC tags are lightweight markers only.
5. Do not push unless the user explicitly asks.

### RC Output

Report to the user:
- Git tag created: `vX.Y.Z-rc.N`
- No files were modified
- The tag has not been pushed (unless they asked)
- Remind them that RCs are for staging/validation only

## Procedure: Proper Release

Use this path when the user chose "proper release" in Gate 1.

1. Determine the target version from the user's bump choice.
2. **Bump version files** using the project's tooling. This is project-specific -- examples include `mix release.bump`, `npm version`, `cargo set-version`, manual edits to version files, etc. Use whatever the project has configured.
   - For **major** bumps: assign the next constellation codename.
   - For **minor** / **patch** bumps: keep the current codename.
3. Verify the changed files. Typical files that may be updated:
   - Main project version file (e.g., `mix.exs`, `package.json`, `Cargo.toml`, `version.txt`)
   - Release manifest (e.g., `.claude/artifacts/release_manifest.json`)
   - Release notes
4. Ensure release notes are filled in before tagging.
5. Commit the version bump following Conventional Commits:
   ```
   release: prepare vX.Y.Z <Codename>
   ```
6. Create the git tag:
   ```
   git tag vX.Y.Z
   ```
7. Do not push unless the user explicitly asks.

### Proper Release Output

Report to the user:
- Git tag created: `vX.Y.Z`
- Display name: `vX.Y.Z "<Codename>"`
- Files that were modified for the version bump
- The tag and commit have not been pushed (unless they asked)
- This release is eligible for production deployment

## Output

**For Release Candidates:**
- Git tag created: `vX.Y.Z-rc.N`
- No files were modified
- The tag has not been pushed (unless they asked)

**For Proper Releases:**
- Git tag created: `vX.Y.Z`
- Display name: `vX.Y.Z "<Codename>"`
- Files that were modified for the version bump
- The tag and commit have not been pushed (unless they asked)

## Next Step

Push the tag and trunk to remote to trigger CI/CD.
