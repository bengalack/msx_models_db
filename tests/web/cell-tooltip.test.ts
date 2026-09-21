/**
 * Tests for per-model cell tooltips (ModelRecord.tooltips).
 *
 * A tooltip shipped for a cell (e.g. the scraped Engine text behind the parsed
 * value) is shown on hover whether or not the cell text is clipped, and takes
 * precedence over the overflow tooltip.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

const SOURCE_TEXT = 'Toshiba T9769 model B or C and gate array Mitsubishi M50014';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-21',
    groups: [{ id: 0, key: 'g', label: 'G', order: 0 }],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      { id: 3, key: 'engine', label: 'Engine (full-custom ASIC)', groupId: 0, type: 'string' },
      { id: 4, key: 'plain', label: 'Plain', groupId: 0, type: 'string' },
    ],
    models: [
      { id: 1, values: ['Panasonic', 'FS-A1FX', 'T9769 (B or C)', 'x'], tooltips: { engine: SOURCE_TEXT } },
      { id: 2, values: ['Sony', 'HB-75P', null, 'y'], tooltips: { engine: '?' } },
      { id: 3, values: ['Canon', 'V-25', 'S3527', 'z'] },
    ],
  };
}

function cell(element: HTMLElement, modelId: number, colIndex: number): HTMLTableCellElement {
  const row = element.querySelector<HTMLTableRowElement>(`tbody tr[data-model-id="${modelId}"]`)!;
  return row.querySelector<HTMLTableCellElement>(`td[data-col-index="${colIndex}"]`)!;
}

function hover(td: HTMLTableCellElement): void {
  td.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
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

describe('per-model cell tooltips', () => {
  it('shows the shipped tooltip on hover even when the text is not clipped', () => {
    const { element } = buildGrid(makeData());
    document.body.appendChild(element);
    const td = cell(element, 1, 2);
    expect(td.dataset.tooltip).toBe(SOURCE_TEXT);
    hover(td);
    expect(td.title).toBe(SOURCE_TEXT);
  });

  it('shows the tooltip on an empty cell too', () => {
    const { element } = buildGrid(makeData());
    document.body.appendChild(element);
    const td = cell(element, 2, 2);
    hover(td);
    expect(td.title).toBe('?');
  });

  it('leaves cells without a tooltip untitled', () => {
    const { element } = buildGrid(makeData());
    document.body.appendChild(element);
    const td = cell(element, 3, 2);
    hover(td);
    expect(td.hasAttribute('title')).toBe(false);
  });

  it('does not add tooltips to other columns of the same model', () => {
    const { element } = buildGrid(makeData());
    document.body.appendChild(element);
    expect(cell(element, 1, 3).dataset.tooltip).toBeUndefined();
  });
});
