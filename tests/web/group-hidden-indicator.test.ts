/**
 * Tests for the group hidden-columns indicator (⊘).
 *
 * While any column of a group is hidden the group header gets class
 * `group-header--partial`, which reveals its `.hidden-indicator`; the
 * indicator's title names the hidden columns ("Hidden column: X" /
 * "Hidden columns: X, Y").
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-27',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'specs',    label: 'Specs',    order: 1 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number' },
      { id: 4, key: 'ram',          label: 'Main RAM',     groupId: 1, type: 'number' },
      { id: 5, key: 'vram',         label: 'VRAM',         groupId: 1, type: 'number' },
    ],
    models: [{ id: 1, values: ['Sony', 'HB-F1XD', 1987, 64, 128] }],
    slotmap_lut: {},
  };
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

function header(wrap: HTMLElement, groupId: number): HTMLElement {
  return wrap.querySelector<HTMLElement>(`th.group-header[data-group-id="${groupId}"]`)!;
}

function indicator(wrap: HTMLElement, groupId: number): HTMLElement {
  return header(wrap, groupId).querySelector<HTMLElement>('.hidden-indicator')!;
}

describe('group hidden-columns indicator', () => {
  it('is present in every group header, without a tooltip while nothing is hidden', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    for (const group of data.groups) {
      expect(header(element, group.id).classList.contains('group-header--partial')).toBe(false);
      expect(indicator(element, group.id).title).toBe('');
    }
  });

  it('names a single hidden column', () => {
    const data = makeData();
    const { element, setColumnVisible } = buildGrid(data);
    setColumnVisible(3, false);
    expect(header(element, 1).classList.contains('group-header--partial')).toBe(true);
    expect(indicator(element, 1).title).toBe(`Hidden column: ${data.columns[3].label}`);
  });

  it('lists several hidden columns in column order', () => {
    const data = makeData();
    const { element, setColumnVisible } = buildGrid(data);
    setColumnVisible(4, false);
    setColumnVisible(3, false);
    expect(indicator(element, 1).title).toBe(`Hidden columns: ${data.columns[3].label}, ${data.columns[4].label}`);
  });

  it('clears the tooltip when the columns are shown again', () => {
    const { element, setColumnVisible } = buildGrid(makeData());
    setColumnVisible(3, false);
    setColumnVisible(3, true);
    expect(header(element, 1).classList.contains('group-header--partial')).toBe(false);
    expect(indicator(element, 1).title).toBe('');
  });

  it('only describes its own group', () => {
    const { element, setColumnVisible } = buildGrid(makeData());
    setColumnVisible(3, false);
    expect(indicator(element, 0).title).toBe('');
  });
});
