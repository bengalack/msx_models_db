/**
 * Tests for icon-link columns (ColumnDef.linkIcon / headerIcon) — the Identity
 * column linking to generation-msx.nl.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { ColumnDef, MSXData } from '../../src/types.js';

const ICON = 'https://example.org/favicon.ico';
const LINK_COL: ColumnDef = {
  id: 110, key: 'generation_msx', label: 'generation-msx', groupId: 0, type: 'string',
  tooltip: 'Link to generation-msx', headerIcon: 'fa-external-link', linkIcon: ICON, filterable: false,
};

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-09-30',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'release', label: 'Release', order: 1 },
    ],
    columns: [
      { id: 1, key: 'brand', label: 'Brand', groupId: 0, type: 'string' },
      { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string', labelIcon: 'fa-external-link' },
      LINK_COL,
      { id: 3, key: 'year', label: 'Year', groupId: 1, type: 'number' },
    ],
    models: [
      { id: 1, values: ['Sony', 'HB-75P', 'HB-75P', 1985], links: { generation_msx: 'https://example.org/hb-75p/1' } },
      { id: 2, values: ['Canon', 'V-20', 'V-20', 1984], links: { generation_msx: 'https://example.org/v-20/2' },
        tooltips: { generation_msx: 'https://example.org/v-20/2 (family)' } },
      { id: 3, values: ['Maker', 'A-1', 'A-1', 1983] },
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

function cell(el: HTMLElement, modelId: number): HTMLTableCellElement {
  return el.querySelector<HTMLTableCellElement>(`tbody tr[data-model-id="${modelId}"] td[data-col-index="${COL}"]`)!;
}

describe('icon-link column', () => {
  it('a label icon follows the header label after a space', () => {
    const data = makeData();
    const col = data.columns[1];
    const { element } = buildGrid(data);
    const th = element.querySelector<HTMLElement>('th.col-header[data-col-index="1"]')!;
    const text = th.querySelector<HTMLElement>('.col-header__text')!;
    expect(text.textContent).toBe(`${col.label} `);
    expect(text.lastElementChild?.matches(`i.fas.${col.labelIcon}`)).toBe(true);
    expect(text.lastElementChild?.getAttribute('aria-hidden')).toBe('true');
    expect(th.title).toBe(col.label);
  });

  it('header shows the icon, keeps the label for screen readers and the tooltip', () => {
    const { element } = buildGrid(makeData());
    const th = element.querySelector<HTMLElement>(`th.col-header[data-col-index="${COL}"]`)!;
    expect(th.querySelector(`i.fas.${LINK_COL.headerIcon}`)).not.toBeNull();
    expect(th.textContent).toBe('');
    expect(th.getAttribute('aria-label')).toBe(LINK_COL.label);
    expect(th.title).toBe(LINK_COL.tooltip);
  });

  it('a cell with a link shows the icon as a new-tab link whose tooltip is the URL', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    const a = cell(element, 1).querySelector<HTMLAnchorElement>('a.cell-link')!;
    const url = data.models[0].links!.generation_msx;
    expect(a.href).toBe(url);
    expect(a.target).toBe('_blank');
    expect(a.rel).toContain('noopener');
    expect(a.title).toBe(url);
    expect(a.querySelector('img')!.getAttribute('src')).toBe(ICON);
    expect(cell(element, 1).textContent).toBe('');       // the value (model name) is not shown
  });

  it('a family link shows the shipped tooltip instead of the bare URL', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    const a = cell(element, 2).querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(data.models[1].tooltips!.generation_msx);
    expect(a.href).toBe(data.models[1].links!.generation_msx);
  });

  it('a cell without a link stays empty', () => {
    const { element } = buildGrid(makeData());
    expect(cell(element, 3).querySelector('a, img')).toBeNull();
  });

  it('sorts by the cell value (the model name) and has no filter input', () => {
    const data = makeData();
    const { element } = buildGrid(data);
    element.querySelector<HTMLElement>(`th.col-header[data-col-index="${COL}"]`)!.click();
    const order = Array.from(element.querySelectorAll<HTMLElement>('tbody tr[data-model-id]')).map(tr => Number(tr.dataset.modelId));
    const expected = [...data.models].sort((x, y) => String(x.values[COL]).localeCompare(String(y.values[COL]))).map(m => m.id);
    expect(order).toEqual(expected);
    expect(element.querySelector(`.filter-row td[data-col-index="${COL}"] input`)).toBeNull();
  });

  it('is frozen with the rest of the Identity group', () => {
    const { element } = buildGrid(makeData());
    expect(cell(element, 1).classList.contains('col--frozen')).toBe(true);
    expect(cell(element, 1).classList.contains('col--frozen-last')).toBe(true);
  });
});
