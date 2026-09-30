/**
 * Tests for groups that start collapsed (GroupDef.defaultCollapsed).
 *
 * Same contract as defaultOff columns:
 *   - Defaults seed the *initial* view only; the URL hash stays absolute, so a
 *     hash written before a group gained the flag still opens it expanded.
 *   - "Reset view" returns to the defaults: flagged groups collapsed, others expanded.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import { defaultViewState, decodeFromHash, encodeToHash, emptyViewState } from '../../src/url/codec.js';
import type { ColumnDef, GroupDef, MSXData } from '../../src/types.js';

const GROUPS: GroupDef[] = [
  { id: 0, key: 'identity', label: 'Identity', order: 0 },
  { id: 1, key: 'specs', label: 'Specs', order: 1 },
  { id: 2, key: 'detail', label: 'Detail', order: 2, defaultCollapsed: true },
];

const COLS: ColumnDef[] = [
  { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
  { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
  { id: 3, key: 'year', label: 'Year', groupId: 1, type: 'number' },
  { id: 4, key: 'a', label: 'A', groupId: 2, type: 'string' },
  { id: 5, key: 'b', label: 'B', groupId: 2, type: 'string' },
];

const DEFAULT_COLLAPSED = GROUPS.filter(g => g.defaultCollapsed).map(g => g.id);

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-30',
    groups: GROUPS.map(g => ({ ...g })),
    columns: COLS.map(c => ({ ...c })),
    models: [
      { id: 1, values: ['Sony', 'HB-F1XD', 1987, 'x', 'y'] },
      { id: 2, values: ['Philips', 'NMS-8250', 1986, 'x', 'y'] },
    ],
    slotmap_lut: {},
  };
}

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  }
});

function groupHeader(el: HTMLElement, groupId: number): HTMLTableCellElement {
  return el.querySelector<HTMLTableCellElement>(`th.group-header[data-group-id="${groupId}"]`)!;
}

function isCollapsed(el: HTMLElement, groupId: number): boolean {
  return groupHeader(el, groupId).classList.contains('collapsed');
}

describe('defaultViewState', () => {
  it('collapses the defaultCollapsed groups and nothing else', () => {
    expect([...defaultViewState(COLS, GROUPS).collapsedGroupIds].sort()).toEqual([...DEFAULT_COLLAPSED].sort());
  });

  it('without groups it collapses nothing (callers that only pass columns)', () => {
    expect(defaultViewState(COLS).collapsedGroupIds.size).toBe(0);
  });

  it('is the fallback for an empty hash, and a readable hash wins', () => {
    const known = [new Set(COLS.map(c => c.id)), new Set(GROUPS.map(g => g.id)), new Set([1, 2])] as const;
    const fresh = decodeFromHash('', ...known, defaultViewState(COLS, GROUPS));
    expect([...fresh.collapsedGroupIds].sort()).toEqual([...DEFAULT_COLLAPSED].sort());
    // A URL shared with every group expanded stays expanded.
    const shared = { ...emptyViewState(), sortColumnId: 3 };
    const decoded = decodeFromHash(encodeToHash(shared), ...known, defaultViewState(COLS, GROUPS));
    expect(decoded.collapsedGroupIds.size).toBe(0);
  });
});

describe('grid', () => {
  it('opens with the defaultCollapsed groups collapsed', () => {
    const { element } = buildGrid(makeData(), { initialState: defaultViewState(COLS, GROUPS) });
    for (const g of GROUPS) expect(isCollapsed(element, g.id), g.key).toBe(DEFAULT_COLLAPSED.includes(g.id));
  });

  it('Reset view re-collapses the default groups and expands the others', () => {
    const { element, resetView, getViewState } = buildGrid(makeData(), { initialState: defaultViewState(COLS, GROUPS) });
    const expandable = GROUPS.find(g => !g.defaultCollapsed && g.id !== 0)!;
    groupHeader(element, DEFAULT_COLLAPSED[0]).click();    // user expands a default-collapsed group
    groupHeader(element, expandable.id).click();            // and collapses another
    expect(isCollapsed(element, DEFAULT_COLLAPSED[0])).toBe(false);
    expect(isCollapsed(element, expandable.id)).toBe(true);
    resetView();
    for (const g of GROUPS) expect(isCollapsed(element, g.id), g.key).toBe(DEFAULT_COLLAPSED.includes(g.id));
    expect([...getViewState().collapsedGroupIds].sort()).toEqual([...DEFAULT_COLLAPSED].sort());
    // Body cells of a collapsed group: only the first column's stub is shown.
    const bodyCells = Array.from(element.querySelectorAll<HTMLElement>(`tbody td[data-col-group="${DEFAULT_COLLAPSED[0]}"]`));
    expect(bodyCells.filter(td => td.style.display !== 'none').every(td => td.classList.contains('col-group-stub'))).toBe(true);
  });
});
