# Share Button Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Share" toolbar button that copies the current URL to the clipboard and shows a 3-second toast pill anchored below the button.

**Architecture:** The Share button and its toast are wrapped in a `toolbar__btn-wrap` div inside `buildToolbar()`, mirroring the Help button pattern. The toast show/hide is self-contained in `toolbar.ts` (no external state). `main.ts` wires up the clipboard write in an `onShare` callback.

**Tech Stack:** TypeScript, Vite, Vitest, Font Awesome 6 Free (solid icons), CSS custom properties.

---

### Task 0: Create feature branch

**Step 1: Create and switch to feature branch**

```bash
git checkout -b feat/share-button
```

Expected: `Switched to a new branch 'feat/share-button'`

---

### Task 1: Write failing tests

**Files:**
- Create: `tests/web/share-button.test.ts`

**Step 1: Write the test file**

```typescript
/**
 * Tests for the Share button in the toolbar.
 *
 * The Share button (fa-arrow-up-from-bracket icon) copies the current URL to
 * the clipboard. A toast pill appears below the button for 3 seconds.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { buildToolbar } from '../../src/toolbar.js';

// Helper: build a toolbar with all no-op callbacks
function makeToolbar(onShare: () => void = () => {}) {
  return buildToolbar(
    () => {}, // onFiltersToggle
    () => {}, // onColsToggle
    () => {}, // onResetView
    () => {}, // onHeadersCopyToggle
    onShare,  // onShare  ← new param (5th)
    () => {}, // onHelpToggle
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe('Share button', () => {
  it('renders a button containing the fa-arrow-up-from-bracket icon', () => {
    const { element } = makeToolbar();
    const icon = element.querySelector('i.fa-arrow-up-from-bracket');
    expect(icon).not.toBeNull();
  });

  it('calls onShare when the share button is clicked', () => {
    const onShare = vi.fn();
    const { shareBtn } = makeToolbar(onShare);
    shareBtn.click();
    expect(onShare).toHaveBeenCalledOnce();
  });

  it('adds share-toast--visible to the toast immediately on click', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(true);
  });

  it('removes share-toast--visible from the toast after 3000 ms', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    vi.advanceTimersByTime(3000);
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(false);
  });

  it('toast is still visible at 2999 ms', () => {
    vi.useFakeTimers();
    const { shareBtn, shareWrap } = makeToolbar();
    shareBtn.click();
    vi.advanceTimersByTime(2999);
    const toast = shareWrap.querySelector('.share-toast');
    expect(toast?.classList.contains('share-toast--visible')).toBe(true);
  });
});
```

**Step 2: Run tests to verify they fail**

```bash
npx vitest run tests/web/share-button.test.ts
```

Expected: All 5 tests FAIL (toolbar signature mismatch / shareBtn undefined / icon not found).

---

### Task 2: Add CSS for the toast pill

**Files:**
- Modify: `src/styles/toolbar.css` (append at end of file)

**Step 1: Append the share toast CSS block**

Add to the very end of `src/styles/toolbar.css`:

```css
/* ── Share toast pill ────────────────────────────────────────────────────── */

.share-toast {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  z-index: 200;
  white-space: nowrap;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 12px;
  padding: 4px 12px;
  font-size: 11px;
  color: var(--color-text);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.share-toast--visible {
  opacity: 1;
}
```

No test run needed for pure CSS — the Vitest tests don't render CSS. Verified visually after bundle build in Task 5.

---

### Task 3: Add Share button and toast to `buildToolbar()`

**Files:**
- Modify: `src/toolbar.ts`

**Step 1: Update `buildToolbar` signature, body, and return**

Replace the entire contents of `src/toolbar.ts` with:

```typescript
export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onResetView: () => void,
  onHeadersCopyToggle: () => void,
  onShare: () => void,
  onHelpToggle: () => void,
): {
  element: HTMLElement;
  colsBtn: HTMLButtonElement;
  filtersBtn: HTMLButtonElement;
  resetBtn: HTMLButtonElement;
  headersCopyBtn: HTMLButtonElement;
  shareBtn: HTMLButtonElement;
  shareWrap: HTMLElement;
  helpBtn: HTMLButtonElement;
  helpWrap: HTMLElement;
} {
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const colsBtn = document.createElement('button');
  colsBtn.className = 'toolbar__btn';
  const colsIcon = document.createElement('i');
  colsIcon.className = 'fa fa-table';
  colsBtn.appendChild(colsIcon);
  colsBtn.appendChild(document.createTextNode(' Columns'));
  colsBtn.addEventListener('click', onColsToggle);

  const filtersBtn = document.createElement('button');
  filtersBtn.className = 'toolbar__btn';
  const filtersIcon = document.createElement('i');
  filtersIcon.className = 'fas fa-filter';
  filtersBtn.appendChild(filtersIcon);
  filtersBtn.appendChild(document.createTextNode(' Filters'));
  filtersBtn.addEventListener('click', onFiltersToggle);

  const resetBtn = document.createElement('button');
  resetBtn.className = 'toolbar__btn';
  resetBtn.textContent = '\u21bb Reset view';
  resetBtn.addEventListener('click', onResetView);

  const headersCopyBtn = document.createElement('button');
  headersCopyBtn.className = 'toolbar__btn';
  const headersCopyIcon = document.createElement('i');
  headersCopyIcon.className = 'fa fa-plus';
  headersCopyBtn.appendChild(headersCopyIcon);
  headersCopyBtn.appendChild(document.createTextNode(' Include headers on copy'));
  headersCopyBtn.addEventListener('click', onHeadersCopyToggle);

  // ── Share button ──────────────────────────────────────────────────────────
  const shareWrap = document.createElement('div');
  shareWrap.className = 'toolbar__btn-wrap';

  const shareBtn = document.createElement('button');
  shareBtn.className = 'toolbar__btn';
  shareBtn.setAttribute('title', 'Copy link to this view');
  const shareIcon = document.createElement('i');
  shareIcon.className = 'fa-solid fa-arrow-up-from-bracket';
  shareBtn.appendChild(shareIcon);
  shareBtn.appendChild(document.createTextNode(' Share'));

  const shareToast = document.createElement('div');
  shareToast.className = 'share-toast';
  shareToast.textContent = 'URL copied to your clipboard';

  let shareToastTimer: ReturnType<typeof setTimeout> | null = null;
  shareBtn.addEventListener('click', () => {
    onShare();
    if (shareToastTimer !== null) clearTimeout(shareToastTimer);
    shareToast.classList.add('share-toast--visible');
    shareToastTimer = setTimeout(() => {
      shareToast.classList.remove('share-toast--visible');
      shareToastTimer = null;
    }, 3000);
  });

  shareWrap.appendChild(shareBtn);
  shareWrap.appendChild(shareToast);

  // ── Help button ───────────────────────────────────────────────────────────
  const helpWrap = document.createElement('div');
  helpWrap.className = 'toolbar__btn-wrap';
  const helpBtn = document.createElement('button');
  helpBtn.className = 'toolbar__btn';
  helpBtn.textContent = '? Help';
  helpBtn.addEventListener('click', onHelpToggle);
  helpWrap.appendChild(helpBtn);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);
  toolbar.appendChild(resetBtn);
  toolbar.appendChild(headersCopyBtn);
  toolbar.appendChild(shareWrap);
  toolbar.appendChild(helpWrap);

  return { element: toolbar, colsBtn, filtersBtn, resetBtn, headersCopyBtn, shareBtn, shareWrap, helpBtn, helpWrap };
}
```

**Step 2: Run share-button tests**

```bash
npx vitest run tests/web/share-button.test.ts
```

Expected: All 5 tests PASS.

**Step 3: Run full test suite to catch any regressions**

```bash
npx vitest run
```

Expected: All tests PASS. (If any test calls `buildToolbar` with the old 5-arg signature it will fail — fix in Task 4.)

---

### Task 4: Wire up Share in `main.ts`

**Files:**
- Modify: `src/main.ts`

**Step 1: Add `handleShare` function and update both `buildToolbar` call sites**

There are **two** call sites for `buildToolbar` in `main.ts`:

**Call site 1** — the no-data error path (line ~38). Update from 4 no-ops to 6 no-ops:

Old:
```typescript
document.body.appendChild(buildToolbar(() => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }).element);
```

New:
```typescript
document.body.appendChild(buildToolbar(() => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }).element);
```

**Call site 2** — the main path (line ~168). Add `handleShare` function just before the `buildToolbar` call, and add `shareBtn`/`shareWrap` to the destructure:

Add this function before the `buildToolbar` call:
```typescript
  // ── Share button ──────────────────────────────────────────────────────────
  function handleShare(): void {
    const url = window.location.href;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).catch(() => execCommandFallback(url));
    } else {
      execCommandFallback(url);
    }
  }
```

Update the `buildToolbar` call to pass `handleShare` as the 5th argument (between `handleHeadersCopyToggle` and `toggleHelp`):
```typescript
  const toolbarResult = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, handleShare, toggleHelp);
```

Update the destructure to include `shareBtn` and `shareWrap` (these are returned but not used in `main.ts` directly — the toolbar manages them internally — however we still destructure them to satisfy TypeScript if needed; actually they aren't needed in main.ts so just leave the destructure as-is, TypeScript won't complain about unused returned properties).

**Step 2: Run full test suite**

```bash
npx vitest run
```

Expected: All tests PASS.

**Step 3: Type-check**

```bash
npx tsc --noEmit
```

Expected: No errors.

---

### Task 5: Build bundle and smoke-test

**Step 1: Build**

```bash
npm run build
```

Expected: Build succeeds, `docs/bundle.js` updated.

**Step 2: Open `docs/index.html` in browser**

- Verify Share button appears between "Include headers on copy" and "Help".
- Click Share — toast pill appears below the button saying "URL copied to your clipboard".
- After 3 seconds the toast fades out.
- Paste clipboard into a text field — confirm the full current URL was copied.
- Test in both dark and light themes.

---

### Task 6: Update PRD and UX guide

**Files:**
- Modify: `.claude/artifacts/planning/product-requirements.md`
- Modify: `.claude/artifacts/planning/ux-design-guide.md`

**Step 1: Add Share button requirement to PRD**

In `product-requirements.md`, find the "Include headers on copy" section (around line 156) and insert the following new section directly after it (before "Live URL state"):

```markdown
- Share button
  - Description: A toolbar button that copies the current page URL to the clipboard, allowing users to share their exact view. A 3-second toast notification pill appears below the button confirming the copy.
  - Priority: Must
  - Acceptance Criteria:
    - A button labelled "Share" with a `fa-solid fa-arrow-up-from-bracket` icon is placed between the "Include headers on copy" button and the "Help" button in the toolbar.
    - Clicking the button copies `window.location.href` to the clipboard (uses `navigator.clipboard.writeText` with `execCommand` fallback).
    - A toast pill reading "URL copied to your clipboard" appears immediately below the button on click.
    - The toast auto-dismisses after 3 seconds.
    - The toast uses CSS opacity transition for fade-in/out; no layout shift.
    - The Share button has no toggle/active state — it is always a momentary action button.
    - The Share button has no effect on URL state, Reset view, or any other view state.
```

**Step 2: Update UX guide toolbar list**

In `ux-design-guide.md`, find the toolbar `Right:` line (around line 210):

Old:
```
- Right: `[⊞ Columns]` button (opens column picker panel), `[≡ Filters]` toggle, `[↻ Reset view]` button, `[+ Include headers on copy]` toggle, `[? Help]` button, `[◑]` dark/light mode toggle
```

New:
```
- Right: `[⊞ Columns]` button (opens column picker panel), `[≡ Filters]` toggle, `[↻ Reset view]` button, `[+ Include headers on copy]` toggle, `[↑ Share]` button, `[? Help]` button, `[◑]` dark/light mode toggle
```

**Step 3: Add Share/toast interaction pattern to UX guide**

In `ux-design-guide.md`, find the `### Include headers on copy toggle` section in Interaction Patterns and add the following new section directly after it:

```markdown
### Share button

- Momentary action button — no toggle state, never highlighted active.
- Click: copies `window.location.href` to clipboard; shows `share-toast--visible` on the toast pill below the button.
- Toast pill auto-dismisses after 3 seconds (CSS opacity transition, no layout shift).
- If clicked again before 3 seconds, the timer resets and the toast remains visible for another 3 seconds.
- No interaction with URL state, Reset view, filters, or cell selection.
```

**Step 4: Commit docs**

```bash
git add .claude/artifacts/planning/product-requirements.md .claude/artifacts/planning/ux-design-guide.md
git commit -m "docs: update PRD and UX guide for share button"
```

---

### Task 7: Commit all implementation changes

**Step 1: Stage and commit**

```bash
git add src/toolbar.ts src/main.ts src/styles/toolbar.css tests/web/share-button.test.ts docs/bundle.js
git commit -m "feat: add Share button with URL copy and toast notification"
```

---

### Done

Hand off to user for testing before merge. Do NOT commit to main or create a PR until the user has verified the feature in the browser.
