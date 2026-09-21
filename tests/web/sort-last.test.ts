/**
 * Tests for ColumnDef.sortLast — sentinel values that sort after real values.
 *
 * Used by the Engine columns so "None" does not sort among the chip names.
 * Order in both directions: real values, then sortLast values, then blanks.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

const SENTINEL = 'None';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-21',
    groups: [{ id: 0, key: 'g', label: 'G', order: 0 }],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      { id: 3, key: 'engine', label: 'Engine', groupId: 0, type: 'string', sortLast: [SENTINEL] },
      { id: 4, key: 'plain', label: 'Plain', groupId: 0, type: 'string' },
    ],
    models: [
      { id: 1, values: ['A', 'm1', SENTINEL, 'x'] },
      { id: 2, values: ['B', 'm2', 'S3527', 'x'] },
      { id: 3, values: ['C', 'm3', null, 'x'] },
      { id: 4, values: ['D', 'm4', 'FPGA', 'x'] },
      { id: 5, values: ['E', 'm5', SENTINEL, 'x'] },
    ],
  };
}

function columnValues(element: HTMLElement, colIndex: number): (string | null)[] {
  return Array.from(
    element.querySelectorAll<HTMLTableCellElement>(`tbody td[data-col-index="${colIndex}"]`)
  ).map(td => td.textContent);
}

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
  document.body.innerHTML = '';
});

function sorted(direction: 'asc' | 'desc'): (string | null)[] {
  const data = makeData();
  const idx = data.columns.findIndex(c => c.sortLast);
  const { element } = buildGrid(data, {
    initialState: {
      sortColumnId: data.columns[idx].id,
      sortDirection: direction,
      filters: new Map(),
      hiddenColumnIds: new Set(),
      hiddenRowIds: new Set(),
      collapsedGroupIds: new Set(),
      selectedCells: new Set(),
    },
  });
  return columnValues(element, idx);
}

describe('sortLast', () => {
  it('puts sentinel values after real values ascending', () => {
    expect(sorted('asc')).toEqual(['FPGA', 'S3527', SENTINEL, SENTINEL, '—']);
  });

  it('keeps sentinel values after real values descending too', () => {
    expect(sorted('desc')).toEqual(['S3527', 'FPGA', SENTINEL, SENTINEL, '—']);
  });

  it('leaves columns without sortLast sorting normally', () => {
    const data = makeData();
    const idx = data.columns.findIndex(c => c.key === 'manufacturer');
    const { element } = buildGrid(data, {
      initialState: {
        sortColumnId: data.columns[idx].id,
        sortDirection: 'desc',
        filters: new Map(),
        hiddenColumnIds: new Set(),
        hiddenRowIds: new Set(),
        collapsedGroupIds: new Set(),
        selectedCells: new Set(),
      },
    });
    expect(columnValues(element, idx)).toEqual(['E', 'D', 'C', 'B', 'A']);
  });
});
