/**
 * Tests for per-column max width (ColumnDef.maxWidth, in px).
 *
 * A column with maxWidth caps its data cells at that width (overflow is
 * already ellipsised by grid.css); columns without it keep the shared
 * stylesheet cap.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

const CAPPED_WIDTH = 87;

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-16',
    groups: [{ id: 0, key: 'g', label: 'G', order: 0 }],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      { id: 3, key: 'capped', label: 'Capped', groupId: 0, type: 'string', maxWidth: CAPPED_WIDTH },
      { id: 4, key: 'plain', label: 'Plain', groupId: 0, type: 'string' },
    ],
    models: [
      { id: 1, values: ['Sony', 'HB-75P', 'A rather long value that would overflow', 'x'] },
      { id: 2, values: ['Philips', 'NMS 8250', null, 'y'] },
    ],
  };
}

function cellsOf(element: HTMLElement, colIndex: number): HTMLTableCellElement[] {
  return Array.from(element.querySelectorAll<HTMLTableCellElement>(`tbody td[data-col-index="${colIndex}"]`));
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

describe('column maxWidth', () => {
  it('caps every data cell of a column that declares maxWidth', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    const idx = data.columns.findIndex(c => c.maxWidth !== undefined);
    const cells = cellsOf(element, idx);
    expect(cells.length).toBe(data.models.length);
    for (const td of cells) expect(td.style.maxWidth).toBe(`${data.columns[idx].maxWidth}px`);
  });

  it('leaves columns without maxWidth to the stylesheet', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    data.columns.forEach((col, i) => {
      if (col.maxWidth !== undefined) return;
      for (const td of cellsOf(element, i)) expect(td.style.maxWidth).toBe('');
    });
  });
});
