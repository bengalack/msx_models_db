/**
 * Tests for chip links in the Engine columns (ColumnDef.chipLinks + MSXData.chip_links).
 *
 * Each known chip id inside the cell text becomes its own link; the rest of the
 * text stays plain. Clicking the chip follows the link, clicking elsewhere in
 * the cell selects it, and the cell keeps its source-text tooltip.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

const LINKS: Record<string, string> = {
  T9769: 'https://example.org/T9769',
  S1985: 'https://example.org/S1985',
  T7937: 'https://example.org/T7937',
};

function makeData(engineValues: (string | null)[], chipLinksOnColumn = true): MSXData {
  return {
    version: 1,
    generated: '2026-09-26',
    groups: [{ id: 0, key: 'g', label: 'G', order: 0 }],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      { id: 3, key: 'engine', label: 'Engine', groupId: 0, type: 'string', ...(chipLinksOnColumn ? { chipLinks: true } : {}) },
    ],
    models: engineValues.map((v, i) => ({
      id: i + 1,
      values: ['Maker', `M-${i + 1}`, v],
      tooltips: v ? { engine: `source text ${i + 1}` } : undefined,
    })),
    chip_links: LINKS,
  };
}

function engineCell(element: HTMLElement, modelId: number): HTMLTableCellElement {
  return element.querySelector<HTMLTableCellElement>(`tbody tr[data-model-id="${modelId}"] td[data-col-index="2"]`)!;
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

describe('chip links', () => {
  it('links each known chip and keeps the rest as text', () => {
    const { element } = buildGrid(makeData(['T9769 (C) and S1990']));
    const td = engineCell(element, 1);
    const links = Array.from(td.querySelectorAll('a.cell-link'));
    expect(links.map(a => a.textContent)).toEqual(['T9769']);
    expect((links[0] as HTMLAnchorElement).href).toBe(LINKS.T9769);
    expect((links[0] as HTMLAnchorElement).target).toBe('_blank');
    expect(td.textContent).toBe('T9769 (C) and S1990');
  });

  it('links several chips in one cell', () => {
    const { element } = buildGrid(makeData(['T9769 and S1985?']));
    const td = engineCell(element, 1);
    expect(Array.from(td.querySelectorAll('a.cell-link')).map(a => a.textContent)).toEqual(['T9769', 'S1985']);
    expect(td.textContent).toBe('T9769 and S1985?');
  });

  it('matches whole chip ids only (T7937A is not T7937)', () => {
    const { element } = buildGrid(makeData(['T7937A']));
    expect(engineCell(element, 1).querySelectorAll('a.cell-link')).toHaveLength(0);
  });

  it('leaves columns without chipLinks alone', () => {
    const { element } = buildGrid(makeData(['T9769'], false));
    expect(engineCell(element, 1).querySelectorAll('a.cell-link')).toHaveLength(0);
  });

  it('keeps the source-text tooltip on the cell', () => {
    const { element } = buildGrid(makeData(['T9769 and S1990']));
    document.body.appendChild(element);
    const td = engineCell(element, 1);
    td.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    expect(td.title).toBe('source text 1');
  });

  it('clicking the chip does not select the cell; clicking elsewhere in the cell does', () => {
    const { element } = buildGrid(makeData(['T9769 and S1990']));
    document.body.appendChild(element);
    const td = engineCell(element, 1);
    td.querySelector('a.cell-link')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
    expect(td.classList.contains('cell--selected')).toBe(false);
    td.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, button: 0 }));
    expect(td.classList.contains('cell--selected')).toBe(true);
  });
});
