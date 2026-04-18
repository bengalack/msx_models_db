# Include Headers on Copy — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a toolbar toggle button that, when active, prepends a header row (column short labels) to the CTRL+C TSV output.

**Architecture:** `copySelection(includeHeaders?: boolean)` in `grid.ts` owns the header-prepend logic. Toggle state (`headersOnCopy: boolean`) lives in `main.ts` and is passed to `copySelection` on every keydown. `toolbar.ts` gains a new button and returns it so `main.ts` can manage its active state.

**Tech Stack:** TypeScript, Vitest (tests in `tests/web/`), FontAwesome (`fa fa-plus`)

---

### Task 1: Write failing test for `copySelection(true)`

**Files:**
- Create: `tests/web/copy-headers.test.ts`

The test fixture reuses the same minimal `MSXData` shape as `reset-view.test.ts`. Cells are seeded via `initialState.selectedCells` using the format `"modelId:colIdx"` (positional, 0-based colIdx). The grid is built with `buildGrid(data, { initialState })` — no DOM simulation needed.

**Step 1: Create the test file**

```typescript
/**
 * Tests for the "Include headers on copy" feature.
 *
 * copySelection(true) must prepend a tab-joined header row
 * (shortLabel ?? label for each selected visible column).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData, ViewState } from '../../src/types.js';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-04-18',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'specs',    label: 'Specs',    order: 1 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string', shortLabel: 'Model' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number', shortLabel: 'Yr' },
      { id: 4, key: 'ram',          label: 'RAM (KB)',     groupId: 1, type: 'number' },
    ],
    models: [
      { id: 1, values: ['Sony',    'HB-F1XD',   1987,  64] },
      { id: 2, values: ['Philips', 'NMS-8250',  1986, 128] },
    ],
    slotmap_lut: {},
  };
}

const defaultInit = (): ViewState => ({
  sortColumnId: null,
  sortDirection: 'asc',
  filters: new Map(),
  hiddenColumnIds: new Set(),
  hiddenRowIds: new Set(),
  collapsedGroupIds: new Set(),
  selectedCells: new Set(),
});

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {} unobserve() {} disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

describe('copySelection — includeHeaders', () => {
  it('returns empty string when nothing is selected (includeHeaders=true)', () => {
    const { copySelection } = buildGrid(makeData(), { initialState: defaultInit() });
    expect(copySelection(true)).toBe('');
  });

  it('omits header row when includeHeaders is false (existing behaviour)', () => {
    const init = defaultInit();
    // Select col 2 (year, shortLabel "Yr") for model 1
    init.selectedCells = new Set(['1:2']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const result = copySelection(false);
    expect(result).toBe('1987');
  });

  it('omits header row when includeHeaders is absent (existing behaviour)', () => {
    const init = defaultInit();
    init.selectedCells = new Set(['1:2']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    expect(copySelection()).toBe('1987');
  });

  it('prepends header row using shortLabel when available', () => {
    const init = defaultInit();
    // Select col 2 (year, shortLabel "Yr") for model 1
    init.selectedCells = new Set(['1:2']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const result = copySelection(true);
    const lines = result.split('\n');
    expect(lines[0]).toBe('Yr');   // shortLabel
    expect(lines[1]).toBe('1987'); // data
    expect(lines.length).toBe(2);
  });

  it('falls back to label when shortLabel is absent', () => {
    const init = defaultInit();
    // Col 3 is ram, label "RAM (KB)", no shortLabel
    init.selectedCells = new Set(['1:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('RAM (KB)');
    expect(lines[1]).toBe('64');
  });

  it('header columns match data row columns for multi-column selection', () => {
    const init = defaultInit();
    // Select cols 1 (model, shortLabel "Model") and 2 (year, shortLabel "Yr") for model 1
    init.selectedCells = new Set(['1:1', '1:2']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('Model\tYr');
    expect(lines[1]).toBe('HB-F1XD\t1987');
  });

  it('header columns match across multiple rows with same columns', () => {
    const init = defaultInit();
    // Select col 2 (year) for both models
    init.selectedCells = new Set(['1:2', '2:2']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('Yr');
    expect(lines[1]).toBe('1987');
    expect(lines[2]).toBe('1986');
    expect(lines.length).toBe(3);
  });
});
```

**Step 2: Run test to verify it fails**

```bash
rtk npx vitest run tests/web/copy-headers.test.ts
```

Expected: TypeScript error or test failure — `copySelection` signature does not yet accept a parameter.

---

### Task 2: Extend `copySelection` in `grid.ts`

**Files:**
- Modify: `src/grid.ts:333` (return-type interface)
- Modify: `src/grid.ts:1171-1196` (`copySelection` implementation)

**Step 1: Update the return-type declaration (line 333)**

Change:
```typescript
  copySelection: () => string;
```
To:
```typescript
  copySelection: (includeHeaders?: boolean) => string;
```

**Step 2: Update the implementation (line 1171)**

Replace the `copySelection` function body:

```typescript
  function copySelection(includeHeaders?: boolean): string {
    const visibleModelIds = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]'))
      .map(tr => Number(tr.dataset.modelId));
    const visibleColIdxs = data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i));

    // Group selectedCells by visible row, in visible order
    const rowMap = new Map<number, number[]>();
    for (const modelId of visibleModelIds) {
      const cols = visibleColIdxs.filter(c => selectedCells.has(selKey(modelId, c)));
      if (cols.length > 0) rowMap.set(modelId, cols);
    }
    if (rowMap.size === 0) return '';

    const lines: string[] = [];

    if (includeHeaders) {
      // Collect all selected column indices in visible order (deduplicated)
      const selectedColSet = new Set<number>();
      for (const cols of rowMap.values()) cols.forEach(c => selectedColSet.add(c));
      const headerCols = visibleColIdxs.filter(c => selectedColSet.has(c));
      lines.push(headerCols.map(c => data.columns[c].shortLabel ?? data.columns[c].label).join('\t'));
    }

    for (const [modelId, cols] of rowMap) {
      const model = data.models.find(m => m.id === modelId);
      const fields = cols.map(c => {
        const raw = model && c < model.values.length ? model.values[c] : null;
        if (raw === null || raw === undefined || raw === '') return '';
        if (typeof raw === 'boolean') return raw ? 'Yes' : 'No';
        return String(raw);
      });
      lines.push(fields.join('\t'));
    }
    return lines.join('\n');
  }
```

**Step 3: Run tests**

```bash
rtk npx vitest run tests/web/copy-headers.test.ts
```

Expected: all 6 tests PASS.

**Step 4: Run full test suite to confirm no regressions**

```bash
rtk npx vitest run
```

Expected: all tests PASS.

**Step 5: Commit**

```bash
rtk git add src/grid.ts tests/web/copy-headers.test.ts
rtk git commit -m "feat: add includeHeaders param to copySelection"
```

---

### Task 3: Add button to `toolbar.ts`

**Files:**
- Modify: `src/toolbar.ts` (entire file is 45 lines — full replacement)

**Step 1: Update `toolbar.ts`**

Add `onHeadersCopyToggle` as the 4th parameter (push `onHelpToggle` to 5th). Return `headersCopyBtn` in the result object.

```typescript
export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onResetView: () => void,
  onHeadersCopyToggle: () => void,
  onHelpToggle: () => void,
): {
  element: HTMLElement;
  colsBtn: HTMLButtonElement;
  filtersBtn: HTMLButtonElement;
  resetBtn: HTMLButtonElement;
  headersCopyBtn: HTMLButtonElement;
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
  toolbar.appendChild(helpWrap);

  return { element: toolbar, colsBtn, filtersBtn, resetBtn, headersCopyBtn, helpBtn, helpWrap };
}
```

**Step 2: Run full test suite**

```bash
rtk npx vitest run
```

Expected: all tests PASS (toolbar.ts has no direct tests; main.ts usage will be fixed in Task 4).

---

### Task 4: Wire toggle in `main.ts`

**Files:**
- Modify: `src/main.ts`

Three changes:

**Change 1** — destructure `headersCopyBtn` from `buildToolbar` call (line ~159).

Current:
```typescript
  const { element: toolbarEl, colsBtn: colsBtnEl, filtersBtn: filtersBtnEl, helpBtn: helpBtnEl, helpWrap } = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, toggleHelp);
```

Replace with:
```typescript
  const { element: toolbarEl, colsBtn: colsBtnEl, filtersBtn: filtersBtnEl, resetBtn: resetBtnEl, headersCopyBtn: headersCopyBtnEl, helpBtn: helpBtnEl, helpWrap } = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, toggleHelp);
```

**Change 2** — add toggle state and handler. Insert after `handleResetView` (around line 157), before the `buildToolbar` call:

```typescript
  // ── Include headers on copy toggle ────────────────────────────────────────
  let headersOnCopy = false;
  function handleHeadersCopyToggle(): void {
    headersOnCopy = !headersOnCopy;
    headersCopyBtnEl.classList.toggle('toolbar__btn--active', headersOnCopy);
  }
```

Note: `headersCopyBtnEl` is declared by the destructure in Change 1. Because JS hoisting doesn't apply to `const`, place the `handleHeadersCopyToggle` function definition *after* the `buildToolbar` destructure line, or use a `let` forward reference. The simplest approach: define the handler as a `let` arrow that references `headersCopyBtnEl` by closure — since JS closures capture by reference, the variable just needs to be assigned before the handler is *called* (not before it is defined). This works because the button click fires after `buildToolbar` returns.

So the order is:
1. `buildToolbar(...)` call (which references `handleHeadersCopyToggle` — must be declared before this)
2. `handleHeadersCopyToggle` function must be declared *before* `buildToolbar` is called

Therefore, declare `headersOnCopy` and `handleHeadersCopyToggle` before the `buildToolbar` call, but reference `headersCopyBtnEl` inside the handler body (which runs later, after the button exists). This is fine because `handleHeadersCopyToggle` is a closure that captures `headersCopyBtnEl` by reference — `headersCopyBtnEl` will be assigned by the time the handler fires.

Final order in `main.ts`:
```typescript
  // ── Include headers on copy toggle ────────────────────────────────────────
  let headersOnCopy = false;
  // headersCopyBtnEl is assigned below by buildToolbar; closure captures it by reference
  let headersCopyBtnEl!: HTMLButtonElement;
  function handleHeadersCopyToggle(): void {
    headersOnCopy = !headersOnCopy;
    headersCopyBtnEl.classList.toggle('toolbar__btn--active', headersOnCopy);
  }

  const { element: toolbarEl, colsBtn: colsBtnEl, filtersBtn: filtersBtnEl, headersCopyBtn: headersCopyBtnEl, helpBtn: helpBtnEl, helpWrap } = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, toggleHelp);
```

Wait — TypeScript won't allow reassigning a `const` destructured as `headersCopyBtnEl`. The cleanest approach is to use a `let` before and assign after:

```typescript
  let headersOnCopy = false;
  function handleHeadersCopyToggle(): void {
    headersOnCopy = !headersOnCopy;
    headersCopyBtnEl.classList.toggle('toolbar__btn--active', headersOnCopy);
  }

  const { element: toolbarEl, colsBtn: colsBtnEl, filtersBtn: filtersBtnEl, headersCopyBtn: headersCopyBtnEl, helpBtn: helpBtnEl, helpWrap } = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, toggleHelp);
```

TypeScript will complain about `headersCopyBtnEl` being used before assignment inside `handleHeadersCopyToggle`. To avoid: use a simple non-null assertion pattern with a `let`:

```typescript
  let headersOnCopy = false;
  let headersCopyBtnEl: HTMLButtonElement;

  function handleHeadersCopyToggle(): void {
    headersOnCopy = !headersOnCopy;
    headersCopyBtnEl.classList.toggle('toolbar__btn--active', headersOnCopy);
  }

  const toolbarResult = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, toggleHelp);
  const toolbarEl = toolbarResult.element;
  const colsBtnEl = toolbarResult.colsBtn;
  const filtersBtnEl = toolbarResult.filtersBtn;
  headersCopyBtnEl = toolbarResult.headersCopyBtn;
  const helpBtnEl = toolbarResult.helpBtn;
  const helpWrap = toolbarResult.helpWrap;
```

**Change 3** — pass `headersOnCopy` to `copySelection` in the keydown handler (line ~196):

Current:
```typescript
      const tsv = copySelection();
```

Replace with:
```typescript
      const tsv = copySelection(headersOnCopy);
```

**Step 1: Apply all three changes to `main.ts`**

**Step 2: Run full test suite**

```bash
rtk npx vitest run
```

Expected: all tests PASS.

**Step 3: Build to verify TypeScript compilation**

```bash
rtk npx vite build
```

Expected: build succeeds with no errors.

**Step 4: Commit**

```bash
rtk git add src/toolbar.ts src/main.ts
rtk git commit -m "feat: add Include headers on copy toolbar toggle"
```

---

### Task 5: Smoke-test in browser

Open `docs/index.html` (or run `npx vite preview`) and verify:

1. The "Include headers on copy" button appears between "Reset view" and "Help"
2. Clicking it toggles the active state (inverted colors, same as Filters)
3. With toggle OFF: select cells, CTRL+C, paste — no header row
4. With toggle ON: select cells, CTRL+C, paste — first row is column labels
5. Selecting non-contiguous columns: header row matches data row column order
6. "Reset view" does **not** deactivate the toggle
7. Both dark and light mode render the button correctly

Hand control back to user to verify before committing further.
