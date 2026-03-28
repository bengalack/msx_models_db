---
name: merge-to-trunk
description: Rebase and fast-forward merge a branch to trunk
disable-model-invocation: true
allowed-tools: Bash
---

# Merge to Trunk (Orchestrator)

## Role

You are a disciplined software engineer performing a branch integration. You enforce linear history, clean commits, and safe git operations. You never take shortcuts with version control.

## Prerequisites

- A local feature branch with work to integrate
- A clean working tree (no uncommitted changes)
- Git hooks configured and active

## Safety Rules (Mandatory)

- Never run destructive git commands (`reset --hard`, `push --force`, `checkout -- .`, `clean -f`).
- Never disable or bypass Git hooks (`--no-verify` or equivalent). If a hook fails, fix the issue and retry.
- Never push unless the user explicitly asks.
- Never use `git merge --no-ff`. Merge commits are forbidden on trunk.
- Always prefer rebase to produce linear history.
- Only delete the local feature branch after a successful merge.
- When deleting, use `git branch -d` (safe delete), never `-D` (force delete).
- Always verify you are on trunk after the merge completes.

## Procedure

### 1. Inspect Context

```
git status
git branch --show-current
git branch --list
```

- If the working tree is dirty (uncommitted changes), **stop** and ask the user whether to commit or stash before proceeding.
- Identify the trunk branch name (`main` or `master`) from repository state.
- Identify the feature branch name. If unclear, ask the user.

### 2. Review and Clean Up Commits (Mandatory)

Review all commits on the feature branch that are not yet on trunk:

```
git log <trunk>..<feature_branch> --oneline
```

**Squash related commits** into logical, meaningful groups. Invoke `/squash-commits` to interactively group and squash commits before proceeding. This covers WIP, fixup, and throwaway messages, but also folds support commits (`test:`, `refactor:`, `chore:`) into the features they belong to.

After squashing, verify that every remaining commit follows **Conventional Commits v1.0.0** format: `<type>[optional scope][optional !]: <description>`.

Valid types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `revert`, `style`.

**Task checkbox hygiene:** If the project tracks tasks in artifacts, check off completed tasks in the same commit as the code that completes them -- not in a separate commit.

### 3. Rebase onto Trunk

```
git rebase <trunk>
```

- If there are conflicts, **stop** and tell the user exactly which files have conflicts and what needs resolving. Do not auto-resolve conflicts.
- After successful rebase, verify the commit log is clean: `git log --oneline -10`

### 4. Switch to Trunk

```
git checkout <trunk>
```

### 5. Update Trunk

```
git pull --ff-only
```

If this fails (trunk has diverged), you may need to rebase the feature branch again. Go back to step 3.

### 6. Fast-Forward Merge

```
git merge --ff-only <feature_branch>
```

- If fast-forward is not possible, the feature branch needs another rebase. Go back to step 3.
- **Never** use `--no-ff`. Merge commits are not allowed on trunk.

### 7. Verify Success

```
git status
git log --oneline -5
git branch --show-current
```

Confirm:
- The merge completed cleanly
- History is linear (no merge commits)
- You are on trunk

### 8. Delete the Feature Branch

Only after confirmed success:

```
git branch -d <feature_branch>
```

### 9. Final Verification

```
git branch --show-current
git log --oneline -5
```

## Push Policy

- **Never** push feature branches to the remote.
- Only push trunk (`master`/`main`) and tags.
- Only push when the user explicitly asks.

## Output

Report to the user:
- The merged branch name
- Confirmation that fast-forward merge was used (no merge commit)
- Whether the local feature branch was deleted
- The current branch (must be trunk)
- A reminder that nothing has been pushed (unless they asked)

## Next Step

Push trunk to remote (if user wants), `/squash-commits` -- Further clean up trunk history before pushing, or `/prepare-release` -- Create a versioned release.
