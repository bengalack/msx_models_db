/**
 * Tests for columns that ship but start hidden (ColumnDef.defaultOff).
 *
 * Contract:
 *   - Defaults seed the *initial* view only. The URL hash stays ABSOLUTE state,
 *     never a delta from the defaults — so a hash written before a column became
 *     defaultOff still decodes to "that column is visible", exactly as its author
 *     saw it, with no codec version bump.
 *   - "Reset view" returns to the defaults, not to "show everything".
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import {
  defaultViewState,
  decodeFromHash,
  encodeToHash,
  encodeViewState,
  emptyViewState,
} from '../../src/url/codec.js';
import type { MSXData, ColumnDef } from '../../src/types.js';

// ── fixture ────────────────────────────────────────────────────────────────

const COLS: ColumnDef[] = [
  { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
  { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
  { id: 3, key: 'year', label: 'Year', groupId: 1, type: 'number' },
  { id: 4, key: 'keyboard_layout', label: 'Keyboard Layout', groupId: 1, type: 'string', defaultOff: true },
];

const OFF_COL_ID = 4;
const OFF_COL_IDX = 3;

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-19',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'other', label: 'Other', order: 1 },
    ],
    columns: COLS.map(c => ({ ...c })),
    models: [
      { id: 1, values: ['Sony', 'HB-F1XD', 1987, 'JIS'] },
      { id: 2, values: ['Philips', 'NMS-8250', 1986, 'QWERTY'] },
    ],
    slotmap_lut: {},
  };
}

const KNOWN_COL_IDS = new Set(COLS.map(c => c.id));
const KNOWN_GROUP_IDS = new Set([0, 1]);
const KNOWN_MODEL_IDS = new Set([1, 2]);

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

function cellsOf(element: HTMLElement, colIndex: number): HTMLElement[] {
  return Array.from(element.querySelectorAll<HTMLElement>(`tbody td[data-col-index="${colIndex}"]`));
}

function headerOf(element: HTMLElement, colIndex: number): HTMLElement | null {
  return element.querySelector<HTMLElement>(`th.col-header[data-col-index="${colIndex}"]`);
}

// ── codec: defaults ────────────────────────────────────────────────────────

describe('defaultViewState', () => {
  it('seeds hiddenColumnIds from the defaultOff columns', () => {
    const state = defaultViewState(COLS);
    expect([...state.hiddenColumnIds]).toEqual([OFF_COL_ID]);
  });

  it('leaves every other field at its empty value', () => {
    const state = defaultViewState(COLS);
    const empty = emptyViewState();
    expect(state.sortColumnId).toBe(empty.sortColumnId);
    expect(state.collapsedGroupIds.size).toBe(0);
    expect(state.hiddenRowIds.size).toBe(0);
    expect(state.filters.size).toBe(0);
    expect(state.selectedCells.size).toBe(0);
  });

  it('is empty when no column is defaultOff', () => {
    const state = defaultViewState(COLS.filter(c => !c.defaultOff));
    expect(state.hiddenColumnIds.size).toBe(0);
  });
});

describe('decodeFromHash fallback', () => {
  it('applies the defaults when there is no hash', () => {
    const state = decodeFromHash('', KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS, defaultViewState(COLS));
    expect([...state.hiddenColumnIds]).toEqual([OFF_COL_ID]);
  });

  it('applies the defaults when the hash is corrupt', () => {
    const state = decodeFromHash('#!!!not-base64!!!', KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS, defaultViewState(COLS));
    expect([...state.hiddenColumnIds]).toEqual([OFF_COL_ID]);
  });

  it('still returns the empty state when no fallback is supplied', () => {
    const state = decodeFromHash('', KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS);
    expect(state.hiddenColumnIds.size).toBe(0);
  });

  it('honours an old URL that hid nothing — the defaults do not leak in', () => {
    // A hash written before the column became defaultOff: nothing hidden.
    const hash = '#' + encodeViewState(emptyViewState());
    const state = decodeFromHash(hash, KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS, defaultViewState(COLS));
    expect(state.hiddenColumnIds.size).toBe(0);
  });
});

// ── grid: initial render ───────────────────────────────────────────────────

describe('grid with a defaultOff column', () => {
  it('hides the column on a fresh load', () => {
    const { element } = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    expect(headerOf(element, OFF_COL_IDX)?.style.display).toBe('none');
    for (const td of cellsOf(element, OFF_COL_IDX)) expect(td.style.display).toBe('none');
  });

  it('leaves the other columns visible', () => {
    const { element } = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    for (const idx of [0, 1, 2]) {
      expect(headerOf(element, idx)?.style.display).not.toBe('none');
    }
  });

  it('reports the column in getHiddenCols so the picker renders it unchecked', () => {
    const { getHiddenCols } = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    expect(getHiddenCols().has(OFF_COL_IDX)).toBe(true);
  });

  it('shows the column once the user turns it on', () => {
    const { element, setColumnVisible } = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    setColumnVisible(OFF_COL_IDX, true);
    expect(headerOf(element, OFF_COL_IDX)?.style.display).not.toBe('none');
    for (const td of cellsOf(element, OFF_COL_IDX)) expect(td.style.display).not.toBe('none');
  });
});

// ── grid: reset restores the defaults ──────────────────────────────────────

describe('resetView with a defaultOff column', () => {
  it('re-hides the default-off column that the user had turned on', () => {
    const { element, setColumnVisible, resetView, getHiddenCols } =
      buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    setColumnVisible(OFF_COL_IDX, true);
    resetView();
    expect(getHiddenCols().has(OFF_COL_IDX)).toBe(true);
    expect(headerOf(element, OFF_COL_IDX)?.style.display).toBe('none');
    for (const td of cellsOf(element, OFF_COL_IDX)) expect(td.style.display).toBe('none');
  });

  it('restores a manually hidden column while keeping the default-off one hidden', () => {
    const { element, setColumnVisible, resetView, getHiddenCols } =
      buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    setColumnVisible(2, false);
    resetView();
    expect(getHiddenCols().has(2)).toBe(false);
    expect(headerOf(element, 2)?.style.display).not.toBe('none');
    expect(getHiddenCols().has(OFF_COL_IDX)).toBe(true);
  });

  it('keeps the group header marked partial after reset', () => {
    const { element, resetView } = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    resetView();
    const th = element.querySelector<HTMLTableCellElement>('th.group-header[data-group-id="1"]');
    expect(th?.classList.contains('group-header--partial')).toBe(true);
    expect(th?.colSpan).toBe(1); // "other" has 2 columns, one of them default-off
  });
});

// ── end-to-end: the URL stays absolute ─────────────────────────────────────

describe('URL round-trip', () => {
  it('a shared URL of the default view re-hides the column on reload', () => {
    const first = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    const hash = encodeToHash(first.getViewState());
    const reloaded = buildGrid(makeData(), {
      initialState: decodeFromHash(hash, KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS, defaultViewState(COLS)),
    });
    expect(reloaded.getHiddenCols().has(OFF_COL_IDX)).toBe(true);
  });

  it('a shared URL with the column turned on keeps it on after reload', () => {
    const first = buildGrid(makeData(), { initialState: defaultViewState(COLS) });
    first.setColumnVisible(OFF_COL_IDX, true);
    const hash = encodeToHash(first.getViewState());
    const reloaded = buildGrid(makeData(), {
      initialState: decodeFromHash(hash, KNOWN_COL_IDS, KNOWN_GROUP_IDS, KNOWN_MODEL_IDS, defaultViewState(COLS)),
    });
    expect(reloaded.getHiddenCols().has(OFF_COL_IDX)).toBe(false);
  });
});
