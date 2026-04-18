/**
 * Tests for the "Reset view" feature.
 *
 * resetView() must clear all active view state in one shot:
 *   - sort removed
 *   - all manually hidden rows revealed
 *   - all collapsed groups expanded
 *   - all individually hidden columns restored
 *   - all filters cleared and filter row hidden
 *   - all cell and row selections deselected
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData, ViewState } from '../../src/types.js';

// ── Minimal test fixture ───────────────────────────────────────────────────

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
      { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number' },
      { id: 4, key: 'ram',          label: 'RAM',          groupId: 1, type: 'number' },
    ],
    models: [
      { id: 1, values: ['Sony',    'HB-F1XD',   1987,  64] },
      { id: 2, values: ['Philips', 'NMS-8250',   1986, 128] },
      { id: 3, values: ['Sanyo',   'MPC-25FD',   1988,  64] },
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

function colHeader(wrap: HTMLElement, colIndex: number): HTMLElement | null {
  return wrap.querySelector<HTMLElement>(`th.col-header[data-col-index="${colIndex}"]`);
}

function filterInput(wrap: HTMLElement, colIndex: number): HTMLInputElement | null {
  return wrap.querySelector<HTMLInputElement>(`input.filter-input[data-col-index="${colIndex}"]`);
}

function filterRow(wrap: HTMLElement): HTMLElement | null {
  return wrap.querySelector<HTMLElement>('tr.filter-row');
}

function isHidden(el: HTMLElement | null): boolean {
  return !el || el.style.display === 'none';
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('resetView', () => {
  it('clears an active sort', () => {
    const init: ViewState = {
      sortColumnId: 3, // Year
      sortDirection: 'asc',
      filters: new Map(),
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set(),
      selectedCells: new Set(),
    };
    const { element, resetView } = buildGrid(makeData(), { initialState: init });
    expect(colHeader(element, 2)?.classList.contains('col-header--sort-asc')).toBe(true);
    resetView();
    expect(colHeader(element, 2)?.classList.contains('col-header--sort-asc')).toBe(false);
    expect(colHeader(element, 2)?.classList.contains('col-header--sort-desc')).toBe(false);
  });

  it('reveals all manually hidden rows', () => {
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map(),
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set([1, 2]), // hide two of three rows
      collapsedGroupIds: new Set(),
      selectedCells: new Set(),
    };
    const { element, resetView } = buildGrid(makeData(), { initialState: init });
    expect(element.querySelectorAll('.row-gap-indicator').length).toBeGreaterThan(0);
    resetView();
    expect(element.querySelectorAll('.row-gap-indicator').length).toBe(0);
    expect(element.querySelectorAll('tr[data-model-id]').length).toBe(3);
  });

  it('expands all collapsed groups', () => {
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map(),
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set([0, 1]), // collapse both groups
      selectedCells: new Set(),
    };
    const { element, resetView } = buildGrid(makeData(), { initialState: init });
    expect(groupHeader(element, 0)?.classList.contains('collapsed')).toBe(true);
    expect(groupHeader(element, 1)?.classList.contains('collapsed')).toBe(true);
    resetView();
    expect(groupHeader(element, 0)?.classList.contains('collapsed')).toBe(false);
    expect(groupHeader(element, 1)?.classList.contains('collapsed')).toBe(false);
  });

  it('shows all individually hidden columns', () => {
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map(),
      hiddenColumnIds: new Set([3, 4]), // hide Year (col id=3→idx=2) and RAM (col id=4→idx=3)
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set(),
      selectedCells: new Set(),
    };
    const { element, resetView } = buildGrid(makeData(), { initialState: init });
    expect(isHidden(colHeader(element, 2))).toBe(true);
    expect(isHidden(colHeader(element, 3))).toBe(true);
    resetView();
    expect(isHidden(colHeader(element, 2))).toBe(false);
    expect(isHidden(colHeader(element, 3))).toBe(false);
  });

  it('clears active filters and hides the filter row', () => {
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map([[1, 'Sony']]), // column id=1 (Manufacturer) → idx=0
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set(),
      selectedCells: new Set(),
    };
    const { element, toggleFilters, resetView } = buildGrid(makeData(), { initialState: init });
    toggleFilters(); // show the filter row (as main.ts does on init when filters are active)
    expect(isHidden(filterRow(element))).toBe(false);
    expect(filterInput(element, 0)?.value).toBe('Sony');

    const { filtersWereOn } = resetView();

    expect(filtersWereOn).toBe(true);
    expect(isHidden(filterRow(element))).toBe(true);
    expect(filterInput(element, 0)?.value).toBe('');
    expect(filterInput(element, 0)?.classList.contains('filter-input--active')).toBe(false);
  });

  it('returns filtersWereOn=false when filter row was already hidden', () => {
    const { resetView } = buildGrid(makeData());
    const { filtersWereOn } = resetView();
    expect(filtersWereOn).toBe(false);
  });

  it('deselects all cell selections', () => {
    const init: ViewState = {
      sortColumnId: null,
      sortDirection: 'asc',
      filters: new Map(),
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set(),
      selectedCells: new Set(['1:1', '1:2']), // modelId:colId
    };
    const { element, resetView } = buildGrid(makeData(), { initialState: init });
    expect(element.querySelectorAll('.cell--selected').length).toBeGreaterThan(0);
    resetView();
    expect(element.querySelectorAll('.cell--selected').length).toBe(0);
  });

  it('fires onStateChange after reset', () => {
    let callCount = 0;
    const { resetView } = buildGrid(makeData(), { onStateChange: () => { callCount++; } });
    resetView();
    expect(callCount).toBe(1);
  });

  it('resets all state simultaneously', () => {
    // Build a maximally dirty state
    const init: ViewState = {
      sortColumnId: 3,
      sortDirection: 'desc',
      filters: new Map([[1, 'Sony']]),
      hiddenColumnIds: new Set([4]), // RAM (col id=4→idx=3)
      hiddenRowIds: new Set([2]),
      collapsedGroupIds: new Set([1]),
      selectedCells: new Set(['1:1']),
    };
    const { element, toggleFilters, resetView } = buildGrid(makeData(), { initialState: init });
    toggleFilters();

    resetView();

    // Sort cleared
    expect(element.querySelector('.col-header--sort-asc, .col-header--sort-desc')).toBeNull();
    // No hidden rows
    expect(element.querySelectorAll('.row-gap-indicator').length).toBe(0);
    expect(element.querySelectorAll('tr[data-model-id]').length).toBe(3);
    // No collapsed groups
    expect(element.querySelector('.group-header.collapsed')).toBeNull();
    // No hidden columns
    expect(element.querySelector('th.col-header[style*="display: none"]')).toBeNull();
    // Filter row hidden and inputs empty
    expect(isHidden(filterRow(element))).toBe(true);
    expect(Array.from(element.querySelectorAll<HTMLInputElement>('input.filter-input'))
      .every(inp => inp.value === '')).toBe(true);
    // No selection
    expect(element.querySelectorAll('.cell--selected').length).toBe(0);
  });
});
