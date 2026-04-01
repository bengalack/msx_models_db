/**
 * Tests for the group filter indicator.
 *
 * When any column in a group has an active filter, the group header <th>
 * receives class `group-header--filtered` and reveals its `.filter-indicator`
 * icon. The indicator must work in both expanded and collapsed states.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData, ViewState } from '../../src/types.js';

// ── Minimal test fixture ───────────────────────────────────────────────────

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-04-01',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'specs',    label: 'Specs',    order: 1 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number' },
      { id: 4, key: 'ram',          label: 'RAM',          groupId: 1, type: 'number' },
    ],
    models: [
      { id: 1, values: ['Sony', 'HB-F1XD', 1987, 64] },
      { id: 2, values: ['Philips', 'NMS-8250', 1986, 128] },
    ],
    slotmap_lut: {},
  };
}

// ── Setup ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => {
    cb(0);
    return 0;
  };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

// ── Helpers ────────────────────────────────────────────────────────────────

function groupHeader(wrap: HTMLElement, groupId: number): HTMLElement | null {
  return wrap.querySelector<HTMLElement>(`th.group-header[data-group-id="${groupId}"]`);
}

function filterInput(wrap: HTMLElement, colIndex: number): HTMLInputElement | null {
  return wrap.querySelector<HTMLInputElement>(`input.filter-input[data-col-index="${colIndex}"]`);
}

function typeFilter(input: HTMLInputElement, value: string): void {
  input.value = value;
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('group filter indicator', () => {
  it('filter-indicator icon is present in each group header', () => {
    const { element } = buildGrid(makeData());
    const g0 = groupHeader(element, 0);
    const g1 = groupHeader(element, 1);
    expect(g0?.querySelector('.filter-indicator')).not.toBeNull();
    expect(g1?.querySelector('.filter-indicator')).not.toBeNull();
  });

  it('group-header--filtered class is absent initially', () => {
    const { element } = buildGrid(makeData());
    expect(groupHeader(element, 0)?.classList.contains('group-header--filtered')).toBe(false);
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('adds group-header--filtered when a filter is typed in a column', () => {
    const { element, toggleFilters } = buildGrid(makeData());
    // Show filter row first
    toggleFilters();
    const input = filterInput(element, 2); // 'Year' column, groupId=1
    expect(input).not.toBeNull();
    typeFilter(input!, '1987');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Other group unaffected
    expect(groupHeader(element, 0)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('removes group-header--filtered when filter is cleared', () => {
    const { element, toggleFilters } = buildGrid(makeData());
    toggleFilters();
    const input = filterInput(element, 2)!;
    typeFilter(input, '1987');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Clear by typing empty
    typeFilter(input, '');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('removes group-header--filtered when clear button is clicked', () => {
    const { element, toggleFilters } = buildGrid(makeData());
    toggleFilters();
    const input = filterInput(element, 2)!;
    typeFilter(input, '1987');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Click the clear button (next sibling of input)
    const clearBtn = input.nextElementSibling as HTMLButtonElement;
    clearBtn.click();
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('keeps group-header--filtered if another column in the group still has a filter', () => {
    const { element, toggleFilters } = buildGrid(makeData());
    toggleFilters();
    const yearInput = filterInput(element, 2)!;  // groupId=1
    const ramInput = filterInput(element, 3)!;    // groupId=1
    typeFilter(yearInput, '1987');
    typeFilter(ramInput, '64');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Clear only year — ram still active
    typeFilter(yearInput, '');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Clear ram too
    typeFilter(ramInput, '');
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('removes all group-header--filtered when toggleFilters hides the filter row', () => {
    const { element, toggleFilters } = buildGrid(makeData());
    toggleFilters(); // show
    typeFilter(filterInput(element, 0)!, 'Sony');
    typeFilter(filterInput(element, 2)!, '1987');
    expect(groupHeader(element, 0)?.classList.contains('group-header--filtered')).toBe(true);
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    // Toggle to hide — should clear all
    toggleFilters();
    expect(groupHeader(element, 0)?.classList.contains('group-header--filtered')).toBe(false);
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('restores group-header--filtered from initialState', () => {
    const data = makeData();
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map([[3, 'Year filter']]), // column id 3 = Year, groupId=1
      hiddenColumnIds: [],
      hiddenRowIds: [],
      collapsedGroupIds: [],
      selectedCells: new Set(),
    };
    const { element } = buildGrid(data, { initialState: init });
    expect(groupHeader(element, 1)?.classList.contains('group-header--filtered')).toBe(true);
    expect(groupHeader(element, 0)?.classList.contains('group-header--filtered')).toBe(false);
  });

  it('filter indicator works when group is collapsed', () => {
    const data = makeData();
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map([[3, '1987']]),
      hiddenColumnIds: [],
      hiddenRowIds: [],
      collapsedGroupIds: [1], // Specs group collapsed
      selectedCells: new Set(),
    };
    const { element } = buildGrid(data, { initialState: init });
    const g1 = groupHeader(element, 1)!;
    expect(g1.classList.contains('collapsed')).toBe(true);
    expect(g1.classList.contains('group-header--filtered')).toBe(true);
  });
});
