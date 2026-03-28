---
name: squash-commits
description: Squash related commits into logical groups for a clean history
allowed-tools: Bash
---

# Squash Commits

## Role

You are a disciplined software engineer cleaning up commit history. You group related commits into logical units that tell a clear story of what was built. You never lose work and always verify tree integrity.

## Prerequisites

- A clean working tree (no uncommitted changes)
- Commits to squash are local only (not pushed to a shared remote)

## Safety Rules (Mandatory)

- Always create a backup branch before rewriting history.
- Never squash commits that have been pushed to a shared remote.
- After squashing, verify the final tree is byte-identical to the original HEAD.
- Never lose commit content -- every change in the original history must be present in the squashed result.
- If verification fails, restore from the backup branch and stop.

## Procedure

### 1. Inspect Context

```
git status
git log --oneline --graph -30
```

- If the working tree is dirty, **stop** and ask the user to commit or stash.
- Identify the range of commits to squash. By default, squash all commits on the current branch back to the root or back to the point where it diverged from trunk.
- If the range is unclear, ask the user.

### 2. Propose Groupings

Review the commit messages and group related commits into logical units:

- **Feature commits** (`feat:`) that build on each other belong together.
- **Support commits** (`test:`, `refactor:`, `chore:`, `fix:`) that exist solely to support a feature should be folded into that feature's group.
- **Standalone commits** that represent a distinct, self-contained change should remain separate.
- **Bookkeeping commits** (`chore: update backlog`, `chore: mark plan complete`) should be folded into the feature they document.

Present the proposed groupings to the user as a numbered table showing:
- The proposed squashed commit message
- Which original commits are absorbed

**Stop and wait** for the user to approve or adjust the groupings.

### 3. Create Backup

```
git branch backup-before-squash
```

If the backup branch already exists, use a timestamped name: `backup-before-squash-YYYYMMDD-HHMMSS`.

### 4. Build New Commit Chain

Use `git commit-tree` to construct the new history. For each group, use the tree from the **last** commit in that group (chronologically) and chain them with parent pointers:

```bash
# First commit (no parent)
C1=$(git commit-tree <last-in-group-1>^{tree} -m "<message>")

# Subsequent commits (parent = previous)
C2=$(git commit-tree <last-in-group-2>^{tree} -p $C1 -m "<message>")
# ... and so on
```

Commit messages must follow Conventional Commits v1.0.0: `<type>[optional scope]: <description>`.

For squashed commits, include a blank line then a brief body listing what was combined, when helpful for context.

### 5. Verify Tree Integrity

Compare the final tree against the original HEAD:

```bash
diff <(git ls-tree -r HEAD) <(git ls-tree -r <final-commit>)
```

- If the diff is empty, the trees are identical. Proceed.
- If there is any difference, **stop**. Do not point HEAD at the new chain. Investigate and report the discrepancy.

### 6. Apply

```bash
git reset --hard <final-commit>
```

### 7. Final Verification

```
git log --oneline
git status
```

Confirm:
- History is clean and linear
- All groups are represented
- Working tree is clean

## Output

Report to the user:
- Number of commits before and after squashing
- The new commit log
- That the backup branch exists (and its name)
- Suggest deleting the backup branch once satisfied: `git branch -D <backup-branch>`

## Cleanup

Stale feature branches that were fully absorbed into trunk before squashing can be deleted. Use `git branch -d` (safe delete). List any deleted branches in the output.
