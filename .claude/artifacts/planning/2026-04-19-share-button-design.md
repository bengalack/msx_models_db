# Design: Share Button

## Metadata
- Date: 2026-04-19
- Status: Approved
- Related PRD: `.claude/artifacts/planning/product-requirements.md`
- Related UX guide: `.claude/artifacts/planning/ux-design-guide.md`

## Summary

Add a "Share" button to the toolbar between "Include headers on copy" and "Help". Clicking it copies the current page URL to the clipboard and shows a 3-second toast pill anchored below the button.

## Toolbar Placement

- Button inserted between `headersCopyBtn` and `helpWrap` in `buildToolbar()`.
- Wrapped in a `toolbar__btn-wrap` div (same as Help) to provide the positioning context for the toast.
- Icon: `fa-solid fa-arrow-up-from-bracket`; label text: `" Share"`.
- `buildToolbar()` gains one new parameter: `onShare: () => void`.
- Return value gains `shareBtn: HTMLButtonElement` and `shareWrap: HTMLElement`.

## Toast Pill

- A `<div class="share-toast">` is a child of `shareWrap`, absolutely positioned below the button.
- Default: `opacity: 0; pointer-events: none` (invisible, non-interactive).
- On click: `share-toast--visible` class added → fades in (`opacity: 1`). `setTimeout` of 3000ms removes the class.
- Text: `"URL copied to your clipboard"` (static).
- Style: `border-radius: 12px`, `white-space: nowrap`, theme tokens only, font-size 11px, padding `4px 12px`.

## Clipboard Behavior

`handleShare()` in `main.ts`:
1. `navigator.clipboard.writeText(window.location.href)` with `execCommand` fallback (same pattern as Ctrl+C).
2. Calls `showShareToast()` returned from `buildToolbar()`.

No interaction with URL state, Reset view, filters, or cell selection.

## CSS (additions to `toolbar.css`)

```css
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

## Test Coverage

`tests/web/share-button.test.ts`:
1. Share button is present in DOM with correct icon class (`fa-arrow-up-from-bracket`).
2. Clicking the button invokes `onShare` callback.
3. `share-toast--visible` is added to toast immediately after click.
4. After 3000ms (fake timers via `vi.useFakeTimers()`), `share-toast--visible` is removed.

## PRD / UX Doc Updates

- PRD: new Functional Requirement entry "Share button" inserted between "Include headers on copy" and "Live URL state."
- UX guide: toolbar right-side list updated; new subsection in Interaction Patterns for share/toast behavior.
