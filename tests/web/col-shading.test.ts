/**
 * Tests for col-shaded CSS class assignment in buildGrid() / buildDataRow().
 *
 * When a ColumnDef has shaded: true, every data cell (<td>) in that column
 * must have the class 'col-shaded'.  Columns without shaded (or shaded: false)
 * must NOT have that class.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

// ── Helpers ───────────────────────────────────────────────────────────────

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-04-01',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
    ],
    columns: [
      { id: 1, key: 'plain_col',  label: 'Plain',  groupId: 0, type: 'string' },
      { id: 2, key: 'shaded_col', label: 'Shaded', groupId: 0, type: 'string', shaded: true },
    ],
    models: [
      { id: 1, values: ['alpha', 'beta'] },
      { id: 2, values: ['gamma', 'delta'] },
    ],
    slotmap_lut: {},
  };
}

function getGrid(data: MSXData): HTMLElement {
  const { element } = buildGrid(data);
  document.body.appendChild(element);
  return element;
}

function getDataCells(wrap: HTMLElement, colIndex: number): HTMLTableCellElement[] {
  return Array.from(
    wrap.querySelectorAll<HTMLTableCellElement>(`tbody td[data-col-index="${colIndex}"]`),
  );
}

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  // Stub ResizeObserver (jsdom doesn't implement it)
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
  document.body.innerHTML = '';
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe('col-shaded class', () => {
  describe('shaded column (shaded: true)', () => {
    it('all data cells have class col-shaded', () => {
      const grid = getGrid(makeData());
      const cells = getDataCells(grid, 1); // colIndex 1 = shaded_col
      expect(cells.length).toBeGreaterThan(0);
      for (const cell of cells) {
        expect(cell.classList.contains('col-shaded')).toBe(true);
      }
    });
  });

  describe('plain column (shaded absent)', () => {
    it('data cells do not have class col-shaded', () => {
      const grid = getGrid(makeData());
      const cells = getDataCells(grid, 0); // colIndex 0 = plain_col
      expect(cells.length).toBeGreaterThan(0);
      for (const cell of cells) {
        expect(cell.classList.contains('col-shaded')).toBe(false);
      }
    });
  });

  describe('explicit shaded: false column', () => {
    it('data cells do not have class col-shaded', () => {
      const data = makeData();
      data.columns[0] = { ...data.columns[0], shaded: false };
      const grid = getGrid(data);
      const cells = getDataCells(grid, 0);
      expect(cells.length).toBeGreaterThan(0);
      for (const cell of cells) {
        expect(cell.classList.contains('col-shaded')).toBe(false);
      }
    });
  });
});
