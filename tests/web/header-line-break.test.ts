/**
 * Tests for column headers whose shortLabel carries an explicit line break.
 *
 * A newline means "wrap exactly here": the header renders the text verbatim
 * (grid.css uses white-space: pre-line) and gets .col-header--wide so it sizes
 * to its widest line instead of the narrow default cap. Headers without a
 * newline are unchanged.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

const WRAPPED_LABEL = 'Engine (semi-custom ASIC)';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-21',
    groups: [{ id: 0, key: 'g', label: 'G', order: 0 }],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      {
        id: 3,
        key: 'wrapped',
        label: WRAPPED_LABEL,
        shortLabel: WRAPPED_LABEL.replace(' (', '\n('),
        groupId: 0,
        type: 'string',
      },
      { id: 4, key: 'plain', label: 'Plain', groupId: 0, type: 'string' },
    ],
    models: [{ id: 1, values: ['Sony', 'HB-75P', 'Yamaha S3527', 'x'] }],
  };
}

function header(element: HTMLElement, colIndex: number): HTMLTableCellElement {
  return element.querySelector<HTMLTableCellElement>(`th.col-header[data-col-index="${colIndex}"]`)!;
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

describe('header line break', () => {
  it('renders the short label verbatim, keeping the newline', () => {
    const data = makeData();
    const idx = data.columns.findIndex(c => c.shortLabel?.includes('\n'));
    const { element } = buildGrid(data);
    const text = header(element, idx).querySelector('.col-header__text')!.textContent;
    expect(text).toBe(data.columns[idx].shortLabel);
  });

  it('marks such headers wide so they are not clamped to the default cap', () => {
    const data = makeData();
    const idx = data.columns.findIndex(c => c.shortLabel?.includes('\n'));
    const { element } = buildGrid(data);
    expect(header(element, idx).classList.contains('col-header--wide')).toBe(true);
  });

  it('leaves headers without a line break unchanged', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    data.columns.forEach((col, i) => {
      if (col.shortLabel?.includes('\n')) return;
      expect(header(element, i).classList.contains('col-header--wide')).toBe(false);
    });
  });

  it('keeps the full label as the header tooltip', () => {
    const data = makeData();
    const idx = data.columns.findIndex(c => c.shortLabel?.includes('\n'));
    const { element } = buildGrid(data);
    expect(header(element, idx).title).toBe(WRAPPED_LABEL);
  });
});
