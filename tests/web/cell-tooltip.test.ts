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
      { id: 1, key: 'brand', label: 'Brand', groupId: 0, type: 'string' },
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

describe('linked cell with a tooltip of its own (CPU clock)', () => {
  it('links the value and shows the shipped tooltip, not the URL', () => {
    const url = 'https://example.org/manual/page/n1';
    const text = '3.554685 MHz: Service manual: crystal 21.328125 MHz';
    const data = makeData();
    data.columns.push({ id: 5, key: 'cpu_clock', label: 'CPU Clock (MHz)', groupId: 0, type: 'number', linkable: true });
    data.models = data.models.map(m => ({ ...m, values: [...m.values, m.id === 1 ? 3.5547 : null] }));
    data.models[0].links = { cpu_clock: url };
    data.models[0].tooltips = { ...data.models[0].tooltips, cpu_clock: text };
    const { element } = buildGrid(data);
    document.body.appendChild(element);
    const td = cell(element, 1, 4);
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.href).toBe(url);
    expect(a.textContent).toBe('3.5547');
    expect(td.dataset.tooltip).toBe(text);
    expect(a.title).toBe('');                 // no second, URL-only tooltip
  });

  it('a linked cell without a tooltip of its own still shows the URL', () => {
    const url = 'https://example.org/x';
    const data = makeData();
    data.columns.push({ id: 5, key: 'cpu_clock', label: 'CPU Clock (MHz)', groupId: 0, type: 'number', linkable: true });
    data.models = data.models.map(m => ({ ...m, values: [...m.values, 3.5795] }));
    data.models[2].links = { cpu_clock: url };
    const { element } = buildGrid(data);
    const a = cell(element, 3, 4).querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(url);
  });
});

describe('number shown with fewer decimals (displayDecimals)', () => {
  function clockData(): MSXData {
    const data = makeData();
    data.columns.push({ id: 5, key: 'cpu_clock', label: 'CPU Clock (MHz)', groupId: 0, type: 'number', displayDecimals: 2 });
    const clocks = [3.5795, 3.5547, 3.5783];
    data.models = data.models.map((m, i) => ({ ...m, values: [...m.values, clocks[i]] }));
    return data;
  }

  function rowIds(element: HTMLElement): number[] {
    return Array.from(element.querySelectorAll<HTMLElement>('tbody tr[data-model-id]'))
      .filter(tr => tr.style.display !== 'none').map(tr => Number(tr.dataset.modelId));
  }

  it('the cell shows the rounded value', () => {
    const data = clockData();
    const { element } = buildGrid(data);
    const dec = data.columns[4].displayDecimals!;
    expect(cell(element, 1, 4).textContent).toBe((3.5795).toFixed(dec));
    expect(cell(element, 2, 4).textContent).toBe((3.5547).toFixed(dec));
  });

  it('the filter finds the shown and the full value; sorting uses the full value', () => {
    const data = clockData();
    const { element, toggleFilters } = buildGrid(data);
    toggleFilters();
    const input = element.querySelector<HTMLInputElement>('input.filter-input[data-col-index="4"]')!;
    input.value = '3.58';                                    // shown for 3.5795 and 3.5783
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(rowIds(element)).toEqual([1, 3]);
    input.value = '3.5783';                                  // the full value
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(rowIds(element)).toEqual([3]);
    input.value = '';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    element.querySelector<HTMLElement>('th.col-header[data-col-index="4"]')!.click();
    expect(rowIds(element)).toEqual([2, 3, 1]);              // 3.5547 < 3.5783 < 3.5795
  });
});
