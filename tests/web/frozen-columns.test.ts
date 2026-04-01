/**
 * Tests for frozen (sticky) columns 0-1 in buildGrid().
 *
 * User’s column 0 = gutter (already sticky), so data columns 0–1
 * (manufacturer, model) are frozen.  Column 2+ must NOT be frozen.
 * No layout / pixel measurements are attempted — jsdom does not provide them.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid, FROZEN_COL_COUNT } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

// ── Minimal test fixture ───────────────────────────────────────────────────

function makeData(rowCount = 5): MSXData {
  return {
    version: 1,
    generated: '2026-04-01',
    groups: [
      { id: 0,  key: 'identity', label: 'Identity', order: 0 },
      { id: 12, key: 'release',  label: 'Release',  order: 1 },
      { id: 1,  key: 'memory',   label: 'Memory',   order: 2 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0,  type: 'string' },
      { id: 2, key: 'model',        label: 'Model',        groupId: 0,  type: 'string' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 12, type: 'number' },
      { id: 4, key: 'region',       label: 'Region',       groupId: 12, type: 'string' },
      { id: 5, key: 'main_ram_kb',  label: 'RAM (KB)',     groupId: 1,  type: 'number' },
    ],
    models: Array.from({ length: rowCount }, (_, i) => ({
      id: i + 1,
      values: [`Mfr${i}`, `Model${i}`, 1985 + i, 'EU', 64],
    })),
    slotmap_lut: {},
  };
}

// ── Test setup ────────────────────────────────────────────────────────────
// Vitest uses jsdom (configured in vite.config.ts test.environment) which
// provides `document` and `requestAnimationFrame` globals automatically.
// No manual setup is needed.

beforeEach(() => {
  // Provide a synchronous stub for requestAnimationFrame so deferred updates
  // (updateFrozenOffsets, updateGapVisibility) fire immediately within tests.
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => {
    cb(0);
    return 0;
  };
  // Stub ResizeObserver (jsdom doesn't implement it)
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

// ── Helper: query all cells with col--frozen in the rendered grid ──────────

function frozenCells(wrap: HTMLElement): HTMLElement[] {
  return Array.from(wrap.querySelectorAll<HTMLElement>('.col--frozen'));
}

function cellsAtIndex(wrap: HTMLElement, colIndex: number): HTMLElement[] {
  // Use :is(th, td) to exclude child elements like <input> that also carry
  // data-col-index but are not the cell themselves.
  return Array.from(wrap.querySelectorAll<HTMLElement>(`:is(th, td)[data-col-index="${colIndex}"]`));
}

// ── FROZEN_COL_COUNT constant ──────────────────────────────────────────────

describe('FROZEN_COL_COUNT', () => {
  it('equals 2', () => {
    expect(FROZEN_COL_COUNT).toBe(2);
  });
});

// ── col--frozen class assignment ───────────────────────────────────────────

describe('col--frozen assignment on initial render', () => {
  it('adds .col--frozen to all cells in column index 0', () => {
    const { element } = buildGrid(makeData());
    const cells = cellsAtIndex(element, 0);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(true));
  });

  it('adds .col--frozen to all cells in column index 1', () => {
    const { element } = buildGrid(makeData());
    const cells = cellsAtIndex(element, 1);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(true));
  });

  it('does NOT add .col--frozen to column index 2', () => {
    const { element } = buildGrid(makeData());
    const cells = cellsAtIndex(element, 2);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(false));
  });

  it('does NOT add .col--frozen to column index 3', () => {
    const { element } = buildGrid(makeData());
    const cells = cellsAtIndex(element, 3);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(false));
  });

  it('does NOT add .col--frozen to column index 4', () => {
    const { element } = buildGrid(makeData());
    const cells = cellsAtIndex(element, 4);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(false));
  });

  it('assigns .col--frozen to exactly FROZEN_COL_COUNT distinct colIndex values', () => {
    const { element } = buildGrid(makeData());
    const frozenIndices = new Set(
      frozenCells(element).map(c => c.dataset.colIndex)
    );
    expect(frozenIndices.size).toBe(FROZEN_COL_COUNT);
    for (let i = 0; i < FROZEN_COL_COUNT; i++) {
      expect(frozenIndices.has(String(i))).toBe(true);
    }
  });
});

// ── col--frozen in thead (col-header + filter rows) ───────────────────────

describe('col--frozen in thead', () => {
  it('assigns .col--frozen to col-header th at index 0', () => {
    const { element } = buildGrid(makeData());
    const th = element.querySelector<HTMLElement>('th.col-header[data-col-index="0"]');
    expect(th).not.toBeNull();
    expect(th!.classList.contains('col--frozen')).toBe(true);
  });

  it('assigns .col--frozen to col-header th at index 1', () => {
    const { element } = buildGrid(makeData());
    const th = element.querySelector<HTMLElement>('th.col-header[data-col-index="1"]');
    expect(th).not.toBeNull();
    expect(th!.classList.contains('col--frozen')).toBe(true);
  });

  it('does NOT assign .col--frozen to col-header th at index 2', () => {
    const { element } = buildGrid(makeData());
    const th = element.querySelector<HTMLElement>('th.col-header[data-col-index="2"]');
    expect(th).not.toBeNull();
    expect(th!.classList.contains('col--frozen')).toBe(false);
  });

  it('assigns .col--frozen to filter-row td at index 0', () => {
    const { toggleFilters, element } = buildGrid(makeData());
    toggleFilters();
    const td = element.querySelector<HTMLElement>('.filter-row td[data-col-index="0"]');
    expect(td).not.toBeNull();
    expect(td!.classList.contains('col--frozen')).toBe(true);
  });

  it('assigns .col--frozen to filter-row td at index 1', () => {
    const { toggleFilters, element } = buildGrid(makeData());
    toggleFilters();
    const td = element.querySelector<HTMLElement>('.filter-row td[data-col-index="1"]');
    expect(td).not.toBeNull();
    expect(td!.classList.contains('col--frozen')).toBe(true);
  });

  it('does NOT assign .col--frozen to filter-row td at index 3', () => {
    const { toggleFilters, element } = buildGrid(makeData());
    toggleFilters();
    const td = element.querySelector<HTMLElement>('.filter-row td[data-col-index="3"]');
    expect(td).not.toBeNull();
    expect(td!.classList.contains('col--frozen')).toBe(false);
  });
});

// ── col--frozen survives re-render (hidden rows) ──────────────────────────

describe('col--frozen after row hide', () => {
  it('data cells at frozen index 0 still carry .col--frozen after hiding a row', () => {
    const { element, hideRow } = buildGrid(makeData(4));
    hideRow(2); // hide model id 2
    const cells = cellsAtIndex(element, 0).filter(td => !td.classList.contains('gutter--gap-frozen'));
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(true));
  });
});

// ── col--frozen when a frozen column is hidden ────────────────────────────

describe('col--frozen when column hidden / re-shown', () => {
  it('hides a frozen column but its residual cells still carry .col--frozen', () => {
    const { element, setColumnVisible } = buildGrid(makeData());
    setColumnVisible(0, false);
    // After hiding col 0, no visible td at colIndex=0 should exist — but any
    // that do (display:none) must retain the class.
    const cells = cellsAtIndex(element, 0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(true));
  });

  it('re-showing a frozen column preserves .col--frozen', () => {
    const { element, setColumnVisible } = buildGrid(makeData());
    setColumnVisible(1, false);
    setColumnVisible(1, true);
    const cells = cellsAtIndex(element, 1);
    expect(cells.length).toBeGreaterThan(0);
    cells.forEach(td => expect(td.classList.contains('col--frozen')).toBe(true));
  });
});

// ── gap indicator rows have frozen gap cells with gutter--gap-frozen ────────

describe('col--frozen and gap indicator rows', () => {
  it('gap indicator scrollable data cell does NOT carry .col--frozen', () => {
    const { element, hideRow } = buildGrid(makeData(5));
    hideRow(3);
    // The scrollable (non-frozen) gap data cell should not have col--frozen
    const gapRows = element.querySelectorAll<HTMLElement>('.row-gap-indicator');
    gapRows.forEach(row => {
      const scrollableGap = row.querySelector<HTMLElement>('td.gutter--gap:not(.gutter--gap-frozen)');
      if (scrollableGap) {
        expect(scrollableGap.classList.contains('col--frozen')).toBe(false);
      }
    });
    // gutter--gap-gutter is the sticky gutter cell; it uses .gutter, not .col--frozen
    const gapGutter = element.querySelector<HTMLElement>('.gutter--gap-gutter');
    if (gapGutter) {
      expect(gapGutter.classList.contains('col--frozen')).toBe(false);
    }
  });

  it('gap indicator row contains FROZEN_COL_COUNT frozen gap cells', () => {
    const { element, hideRow } = buildGrid(makeData(5));
    hideRow(3);
    const gapRow = element.querySelector<HTMLElement>('.row-gap-indicator');
    expect(gapRow).not.toBeNull();
    const frozenGaps = gapRow!.querySelectorAll<HTMLElement>('.gutter--gap-frozen');
    expect(frozenGaps.length).toBe(FROZEN_COL_COUNT);
    frozenGaps.forEach((cell, i) => {
      expect(cell.getAttribute('data-col-index')).toBe(String(i));
      expect(cell.classList.contains('gutter--gap')).toBe(true);
    });
  });

  it('gap indicator scrollable data cell colSpan excludes frozen columns', () => {
    const { element, hideRow } = buildGrid(makeData(5));
    hideRow(3);
    const gapRow = element.querySelector<HTMLElement>('.row-gap-indicator');
    expect(gapRow).not.toBeNull();
    const scrollableGap = gapRow!.querySelector<HTMLElement>('td.gutter--gap:not(.gutter--gap-frozen)');
    expect(scrollableGap).not.toBeNull();
    // 5 total columns minus 2 frozen = 3
    expect(scrollableGap!.colSpan).toBe(5 - FROZEN_COL_COUNT);
  });
});

// ── Frozen group header ───────────────────────────────────────────────────

describe('group-header--frozen', () => {
  it('Identity group header gets .group-header--frozen when its columns are all frozen', () => {
    const { element } = buildGrid(makeData());
    const identityHeader = element.querySelector<HTMLElement>('.group-header[data-group-id="0"]');
    expect(identityHeader).not.toBeNull();
    expect(identityHeader!.classList.contains('group-header--frozen')).toBe(true);
  });

  it('Release group header does NOT get .group-header--frozen', () => {
    const { element } = buildGrid(makeData());
    const releaseHeader = element.querySelector<HTMLElement>('.group-header[data-group-id="12"]');
    expect(releaseHeader).not.toBeNull();
    expect(releaseHeader!.classList.contains('group-header--frozen')).toBe(false);
  });

  it('Memory group header does NOT get .group-header--frozen', () => {
    const { element } = buildGrid(makeData());
    const memoryHeader = element.querySelector<HTMLElement>('.group-header[data-group-id="1"]');
    expect(memoryHeader).not.toBeNull();
    expect(memoryHeader!.classList.contains('group-header--frozen')).toBe(false);
  });
});
