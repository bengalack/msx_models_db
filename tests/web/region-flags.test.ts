/**
 * Tests for value display maps (ColumnDef.displayValues) — the Region column's flags.
 * The cell shows the flags, the value stays the tooltip and sort key, and the filter
 * matches the value or the flags.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid, filterHaystack } from '../../src/grid.js';
import type { ColumnDef, MSXData } from '../../src/types.js';

const flag = (code: string): string =>
  [...code].map(c => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65)).join('');

const REGION: ColumnDef = {
  id: 4, key: 'region', label: 'Region', groupId: 1, type: 'string',
  displayValues: {
    'Japan': flag('JP'),
    'Belgium, Sweden': flag('BE') + flag('SE'),
    'Spain': flag('ES'),
    'Atlantis': 'Atlantis',
  },
};

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-10-02',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'release', label: 'Release', order: 1 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      REGION,
    ],
    models: [
      { id: 1, values: ['Sony', 'HB-75P', 'Japan'] },
      { id: 2, values: ['Philips', 'VG-8020', 'Belgium, Sweden'] },
      { id: 3, values: ['Talent', 'DPC-200', 'Spain'] },
      { id: 4, values: ['Maker', 'MX-1', null] },
    ],
    slotmap_lut: {},
  };
}

const COL = 2;

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  }
});

function cell(el: HTMLElement, id: number): HTMLElement {
  return el.querySelector<HTMLElement>(`tbody tr[data-model-id="${id}"] td[data-col-index="${COL}"]`)!;
}

function visibleIds(el: HTMLElement): number[] {
  return Array.from(el.querySelectorAll<HTMLElement>('tbody tr[data-model-id]'))
    .filter(tr => tr.style.display !== 'none')
    .map(tr => Number(tr.dataset.modelId));
}

function filterOn(el: HTMLElement, text: string): void {
  const input = el.querySelector<HTMLInputElement>(`input.filter-input[data-col-index="${COL}"]`)!;
  input.value = text;
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('display values (Region flags)', () => {
  it('the cell shows the flags and the value as its tooltip', () => {
    const { element } = buildGrid(makeData());
    expect(cell(element, 2).textContent!.replace(/\u2009/g, '')).toBe(REGION.displayValues!['Belgium, Sweden']);
    expect(cell(element, 2).dataset.tooltip).toBe('Belgium, Sweden');
    expect(cell(element, 4).classList.contains('cell-null')).toBe(true);
  });

  it('each flag is its own element; other text stays text', () => {
    const data = makeData();
    data.models[3].values[2] = 'Atlantis';
    const { element } = buildGrid(data);
    expect(Array.from(cell(element, 2).querySelectorAll('.cell-flag')).map(f => f.textContent))
      .toEqual([flag('BE'), flag('SE')]);
    expect(cell(element, 2).querySelectorAll('.cell-flag + .cell-flag-gap').length).toBe(2);   // a gap after every flag
    expect(cell(element, 4).querySelectorAll('.cell-flag').length).toBe(0);
    expect(cell(element, 4).textContent).toBe('Atlantis');
  });

  it.each([
    ['Japan', [1]],
    ['japan', [1]],
    [flag('JP'), [1]],
    [flag('SE'), [2]],
    [`${flag('JP')}|Spain`, [1, 3]],
    [`!${flag('JP')}`, [2, 3, 4]],
  ])('filter %s matches the name or the flag', (term, ids) => {
    const { element, toggleFilters } = buildGrid(makeData());
    toggleFilters();
    filterOn(element, term);
    expect(visibleIds(element)).toEqual(ids);
  });

  it('a flag never matches across two neighbouring flags', () => {
    // "BE" + "SE" contains the code points of "ES" in the middle
    expect((REGION.displayValues!['Belgium, Sweden']).includes(flag('ES'))).toBe(true);
    expect(filterHaystack(REGION, 'Belgium, Sweden').includes(flag('ES').toLowerCase())).toBe(false);
  });

  it('sorts by the value, not the flags', () => {
    const { element } = buildGrid(makeData());
    element.querySelector<HTMLElement>(`th.col-header[data-col-index="${COL}"]`)!.click();
    expect(visibleIds(element)).toEqual([2, 1, 3, 4]);       // Belgium…, Japan, Spain, then empty
  });
});
