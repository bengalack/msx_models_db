/**
 * Tests for the Slotmap Overview column (src/slotmap-overview.ts + grid wiring).
 *
 * jsdom has no canvas, so getContext is replaced by a recording stub. Expected
 * colours and categories are read from data/slotmap-colors.json and the slot
 * map symbols from data/scraper-config.json — never hardcoded.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import colorConfig from '../../data/slotmap-colors.json';
import { buildGrid } from '../../src/grid.js';
import {
  drawPopup, drawThumbnail, THUMB, POPUP, POPUP_CELL_OVERLAP, POPUP_CLOSE_DELAY_MS, boxRect, canvasSize, categoryOf, cellIndex, clearThumbnailCache,
  colorFor, hitTest, isExpanded, slotKey, textColorOn, type SlotCells,
} from '../../src/slotmap-overview.js';
import { SLOTMAP_ABSENT, SLOTMAP_EMPTY_PAGE, SLOTMAP_MIRROR_SUFFIX } from '../../src/symbols.js';
import type { ColumnDef, MSXData } from '../../src/types.js';

// ── Canvas stub ────────────────────────────────────────────────────────────

let drawCalls = 0;
const callsByMethod = new Map<string, number>();
/** fillRect calls with the fillStyle in effect: [style, x, y, w, h]. */
let fills: [string, number, number, number, number][] = [];

function stubCanvas(): void {
  const ctx = new Proxy({} as Record<string, unknown>, {
    get(target, prop) {
      if (prop in target) return target[prop as string];
      return (...args: unknown[]) => {
        if (prop === 'fillRect') fills.push([String(target.fillStyle), ...(args as [number, number, number, number])]);
        drawCalls++;
        callsByMethod.set(String(prop), (callsByMethod.get(String(prop)) ?? 0) + 1);
      };
    },
    set(target, prop, value) { target[prop as string] = value; return true; },
  });
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ctx as unknown as CanvasRenderingContext2D);
}

beforeEach(async () => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  }
  document.body.innerHTML = '';
  document.documentElement.setAttribute('data-theme', 'light');
  // Let theme-change redraws of popups left open by earlier tests finish before counting.
  await new Promise(r => setTimeout(r, 0));
  clearThumbnailCache();
  drawCalls = 0;
  callsByMethod.clear();
  fills = [];
  stubCanvas();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// ── Fixture ────────────────────────────────────────────────────────────────

/** A model whose slot 0-0 holds a main ROM in pages 0-1; everything else as given. */
function cellsWith(entries: Record<string, string>): SlotCells {
  const cells: SlotCells = Array(64).fill(SLOTMAP_ABSENT);
  for (let p = 0; p < 4; p++) cells[cellIndex(0, 0, p)] = SLOTMAP_EMPTY_PAGE;
  for (const [key, value] of Object.entries(entries)) {
    const [ms, ss, p] = key.split('_').map(Number);
    cells[cellIndex(ms, ss, p)] = value;
  }
  return cells;
}

function makeData(models: { id: number; name: string; cells: SlotCells | null; key: string | null }[]): MSXData {
  const columns: ColumnDef[] = [
    { id: 1, key: 'brand', label: 'Brand', groupId: 0, type: 'string' },
    { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
    { id: 109, key: 'slot_overview', label: 'Overview', groupId: 13, type: 'string', renderer: 'slotmap', filterable: false },
  ];
  for (let ms = 0; ms < 4; ms++) for (let ss = 0; ss < 4; ss++) for (let p = 0; p < 4; p++) {
    columns.push({ id: 1000 + cellIndex(ms, ss, p), key: slotKey(ms, ss, p), label: `${ss}/P${p}`, groupId: 8 + ms, type: 'string' });
  }
  return {
    version: 1,
    generated: '2026-09-29',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 13, key: 'slotmap', label: 'Slotmap', order: 1 },
      ...[0, 1, 2, 3].map(ms => ({ id: 8 + ms, key: `slotmap_${ms}`, label: `Slot ${ms}`, order: 2 + ms })),
    ],
    columns,
    models: models.map(m => ({ id: m.id, values: ['Maker', m.name, m.key, ...(m.cells ?? Array(64).fill(null))] })),
    slotmap_lut: { CS1: 'Cartridge slot 1', MAIN: 'MSX BIOS with BASIC ROM' },
  };
}

const OVERVIEW_COL = 2;

function overviewCell(el: HTMLElement, modelId: number): HTMLTableCellElement {
  return el.querySelector<HTMLTableCellElement>(`tbody tr[data-model-id="${modelId}"] td[data-col-index="${OVERVIEW_COL}"]`)!;
}

// ── Geometry ───────────────────────────────────────────────────────────────

describe('geometry', () => {
  it('the thumbnail is 90×21 CSS pixels', () => {
    expect(canvasSize(THUMB)).toEqual({ w: 90, h: 21 });
  });

  it.each([['thumbnail', THUMB], ['popup', POPUP]])('%s: grid lines are equally thick both ways', (_n, g) => {
    const a = boxRect(g, 0, 0, 0);
    const right = boxRect(g, 0, 1, 0);
    const above = boxRect(g, 0, 0, 1);
    expect(right.x - (a.x + a.w)).toBe(a.y - (above.y + above.h));
  });

  it('slot 0 is on the left, sub-slot 0 on the left of its block, page 0 at the bottom', () => {
    expect(boxRect(POPUP, 0, 0, 0).x).toBeLessThan(boxRect(POPUP, 1, 0, 0).x);
    expect(boxRect(POPUP, 0, 0, 0).x).toBeLessThan(boxRect(POPUP, 0, 1, 0).x);
    expect(boxRect(POPUP, 0, 0, 0).y).toBeGreaterThan(boxRect(POPUP, 0, 0, 3).y);
  });

  it('hitTest finds the box under a point and nothing on grid lines', () => {
    const r = boxRect(POPUP, 2, 1, 3);
    expect(hitTest(POPUP, r.x + 1, r.y + 1)).toMatchObject({ ms: 2, ss: 1, page: 3 });
    expect(hitTest(POPUP, r.x - 1, r.y + 1)).toBeNull();
  });
});

// ── Colours ────────────────────────────────────────────────────────────────

describe('colours', () => {
  it('every configured category pattern is recognised, mirror suffix ignored', () => {
    const samples: Record<string, string> = {};
    for (const [name, patterns] of Object.entries(colorConfig.categories as Record<string, string[]>)) {
      // Build a label from the first pattern: strip anchors / optional parts.
      samples[name] = patterns[0].replace(/^\^|\$$/g, '').replace(/\\d\*/g, '1').replace(/\\\+\?|!\?/g, '');
    }
    for (const [name, label] of Object.entries(samples)) {
      expect(categoryOf(label)).toBe(name);
      expect(categoryOf(label + SLOTMAP_MIRROR_SUFFIX)).toBe(name);
    }
    expect(categoryOf('SOMETHING-ELSE')).toBe('other');
  });

  it("every category has a colour; unknown categories use 'other'", () => {
    const colors = colorConfig.colors as Record<string, unknown>;
    for (const category of Object.keys(colorConfig.categories)) expect(colors, category).toHaveProperty(category);
    expect(colorFor('not-a-category', 'light')).toBe(colorFor('other', 'light'));
  });

  it('the grid colour follows the theme', () => {
    const grid = colorConfig.colors.grid as { light: string; dark: string };
    expect(colorFor('grid', 'light')).toBe(grid.light);
    expect(colorFor('grid', 'dark')).toBe(grid.dark);
  });

  it('text is white on dark boxes and black on bright ones', () => {
    expect(textColorOn('#000000')).toBe('#ffffff');
    expect(textColorOn('#ffffff')).toBe('#000000');
    expect(textColorOn('#f5d400')).toBe('#000000');
  });

  it('a slot is expanded when a page of sub-slot 1-3 is present', () => {
    expect(isExpanded(cellsWith({}), 0)).toBe(false);
    expect(isExpanded(cellsWith({ '3_2_0': SLOTMAP_EMPTY_PAGE }), 3)).toBe(true);
  });
});

// ── Grid wiring ────────────────────────────────────────────────────────────

describe('Overview column in the grid', () => {
  const models = [
    { id: 1, name: 'B', cells: cellsWith({ '0_0_0': 'MAIN', '1_0_0': 'CS1' }), key: '8000800000000000' },
    { id: 2, name: 'A', cells: cellsWith({ '0_0_0': 'MAIN' }), key: '8000000000000000' },
    { id: 3, name: 'C', cells: null, key: null },
  ];

  it('draws a thumbnail canvas instead of the sort key', () => {
    const { element } = buildGrid(makeData(models));
    const td = overviewCell(element, 1);
    expect(td.querySelector('canvas.slotmap-thumb')).not.toBeNull();
    expect(td.textContent).toBe('');
    expect(td.querySelector('canvas')!.getAttribute('aria-label')).toContain('B');
  });

  it('a model without a slot map shows the blank marker and no canvas', () => {
    const { element } = buildGrid(makeData(models));
    const td = overviewCell(element, 3);
    expect(td.querySelector('canvas')).toBeNull();
    expect(td.classList.contains('cell-null')).toBe(true);
  });

  it('the column has no filter input', () => {
    const { element } = buildGrid(makeData(models));
    const filterCell = element.querySelector(`.filter-row td[data-col-index="${OVERVIEW_COL}"]`)!;
    expect(filterCell.querySelector('input')).toBeNull();
    expect(element.querySelector(`.filter-row td[data-col-index="0"] input`)).not.toBeNull();
  });

  it('sorts by the sort key, like any other column', () => {
    const { element } = buildGrid(makeData(models));
    const header = element.querySelector<HTMLElement>(`thead th[data-col-index="${OVERVIEW_COL}"]`)!;
    header.click();
    const order = Array.from(element.querySelectorAll<HTMLElement>('tbody tr[data-model-id]')).map(tr => tr.dataset.modelId);
    const keyed = models.filter(m => m.key).sort((a, b) => a.key!.localeCompare(b.key!)).map(m => String(m.id));
    expect(order.slice(0, keyed.length)).toEqual(keyed);
  });

  it('thumbnails are painted once per model and theme; row rebuilds only copy them', () => {
    const { element } = buildGrid(makeData(models));
    const painted = callsByMethod.get('fillRect') ?? 0;
    const copies = callsByMethod.get('drawImage') ?? 0;
    expect(painted).toBeGreaterThan(0);
    const header = element.querySelector<HTMLElement>(`thead th[data-col-index="${OVERVIEW_COL}"]`)!;
    header.click();     // sorting rebuilds every row
    expect(callsByMethod.get('fillRect') ?? 0).toBe(painted);
    expect(callsByMethod.get('drawImage') ?? 0).toBeGreaterThan(copies);
  });
});

// ── Popup ──────────────────────────────────────────────────────────────────

describe('popup', () => {
  const models = [{ id: 1, name: 'B', cells: cellsWith({ '0_0_0': 'MAIN', '1_0_0': 'CS1' }), key: '1' }];

  function popup(): HTMLElement {
    return document.querySelector<HTMLElement>('.slotmap-popup')!;
  }

  it('opens on hover with the model name, and closes after leaving the cell', () => {
    vi.useFakeTimers();
    const { element } = buildGrid(makeData(models));
    document.body.appendChild(element);
    const td = overviewCell(element, 1);
    td.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    expect(popup().hidden).toBe(false);
    expect(popup().textContent).toContain('B');
    td.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: document.body }));
    vi.advanceTimersByTime(POPUP_CLOSE_DELAY_MS + 1);
    expect(popup().hidden).toBe(true);
  });

  it('starts at the edge of the cell, leaving no gap to cross', () => {
    const { element } = buildGrid(makeData(models));
    document.body.appendChild(element);
    const td = overviewCell(element, 1);
    vi.spyOn(td, 'getBoundingClientRect').mockReturnValue(new DOMRect(100, 50, 80, 20));
    td.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    expect(parseFloat(popup().style.top)).toBe(70 - POPUP_CELL_OVERLAP);
    expect(parseFloat(popup().style.left)).toBe(100);
  });

  it('opens above the cell, touching it, when there is no room below', () => {
    const { element } = buildGrid(makeData(models));
    document.body.appendChild(element);
    const td = overviewCell(element, 1);
    vi.spyOn(td, 'getBoundingClientRect').mockReturnValue(new DOMRect(100, 600, 80, 20));
    vi.spyOn(popup(), 'offsetHeight', 'get').mockReturnValue(300);
    td.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    expect(parseFloat(popup().style.top) + 300).toBe(600 + POPUP_CELL_OVERLAP);
  });

  it('stays open while the pointer moves from the cell into the popup', () => {
    vi.useFakeTimers();
    const { element } = buildGrid(makeData(models));
    document.body.appendChild(element);
    const td = overviewCell(element, 1);
    td.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    td.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: popup() }));
    popup().dispatchEvent(new MouseEvent('mouseenter'));
    vi.advanceTimersByTime(POPUP_CLOSE_DELAY_MS * 3);
    expect(popup().hidden).toBe(false);
  });

  it('shows the slot map tooltip of the box under the pointer', () => {
    const data = makeData(models);
    const { element } = buildGrid(data);
    document.body.appendChild(element);
    overviewCell(element, 1).dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    const canvas = popup().querySelector('canvas')!;
    vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 900, 200));
    const r = boxRect(POPUP, 1, 0, 0);
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: r.x + 2, clientY: r.y + 2 }));
    const tip = popup().querySelector<HTMLElement>('.slotmap-popup__tip')!;
    expect(tip.hidden).toBe(false);
    expect(tip.textContent).toBe(data.slotmap_lut!.CS1);
    const empty = boxRect(POPUP, 0, 0, 3);    // empty page: no tooltip entry in this fixture
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: empty.x + 2, clientY: empty.y + 2 }));
    expect(tip.hidden).toBe(true);
  });

  it("joins a cell's own detail to the box tooltip", () => {
    const data = makeData(models);
    data.models[0].slot_details = { [slotKey(1, 0, 0)]: 'Painter ROM' };
    const { element } = buildGrid(data);
    document.body.appendChild(element);
    overviewCell(element, 1).dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    const canvas = popup().querySelector('canvas')!;
    vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 900, 200));
    const tip = popup().querySelector<HTMLElement>('.slotmap-popup__tip')!;
    const r = boxRect(POPUP, 1, 0, 0);
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: r.x + 2, clientY: r.y + 2 }));
    expect(tip.textContent).toBe(`${data.slotmap_lut!.CS1}: Painter ROM`);
    const main = boxRect(POPUP, 0, 0, 0);      // no detail for this cell
    canvas.dispatchEvent(new MouseEvent('mousemove', { clientX: main.x + 2, clientY: main.y + 2 }));
    expect(tip.textContent).toBe(data.slotmap_lut!.MAIN);
  });

  it("a slot map cell's tooltip carries its detail too", () => {
    const data = makeData(models);
    data.models[0].slot_details = { [slotKey(1, 0, 0)]: 'Painter ROM' };
    const { element } = buildGrid(data);
    const col = (ms: number, ss: number, p: number) => data.columns.findIndex(c => c.key === slotKey(ms, ss, p));
    const td = (i: number) => element.querySelector<HTMLElement>(`tbody tr[data-model-id="1"] td[data-col-index="${i}"]`)!;
    expect(td(col(1, 0, 0)).dataset.tooltip).toBe(`${data.slotmap_lut!.CS1}: Painter ROM`);
    expect(td(col(0, 0, 0)).dataset.tooltip).toBe(data.slotmap_lut!.MAIN);
  });

  it('redraws thumbnails when the theme switches', async () => {
    const { element } = buildGrid(makeData(models));
    document.body.appendChild(element);
    const before = drawCalls;
    document.documentElement.setAttribute('data-theme', 'dark');
    await new Promise(r => setTimeout(r, 0));    // MutationObserver callbacks run as microtasks
    expect(drawCalls).toBeGreaterThan(before);
  });
});

// ── Empty-page outline (popup only) and dark theme ─────────────────────────

describe('empty pages and themes', () => {
  const inside = (f: [string, number, number, number, number], r: { x: number; y: number; w: number; h: number }) =>
    f[1] >= r.x && f[2] >= r.y && f[1] + f[3] <= r.x + r.w && f[2] + f[4] <= r.y + r.h;

  it.each([['light'], ['dark']] as const)('popup (%s): an empty page gets an inward outline', theme => {
    document.documentElement.setAttribute('data-theme', theme);
    const cells = cellsWith({ '0_0_0': 'MAIN' });          // 0-0 pages 1-3 are empty
    drawPopup(document.createElement('canvas'), cells);
    const outline = colorFor('empty_outline', theme);
    const r = boxRect(POPUP, 0, 0, 3);
    const edges = fills.filter(f => f[0] === outline && inside(f, r));
    expect(edges).toHaveLength(4);
    // A device box has no outline
    expect(fills.filter(f => f[0] === outline && inside(f, boxRect(POPUP, 0, 0, 0)))).toHaveLength(0);
  });

  it('thumbnail: no outline on empty pages', () => {
    const cells = cellsWith({ '0_0_0': 'MAIN' });
    drawThumbnail(document.createElement('canvas'), cells);
    const grid = colorFor('grid', 'light');
    const r = boxRect(THUMB, 0, 0, 3);
    expect(fills.filter(f => inside(f, r) && f[0] !== grid)).toHaveLength(0);
  });

  it('dark neutral boxes (black, dark gray) turn bright in dark mode, text inverted', () => {
    // A gray/black box that needs white text in light mode is a bright gray/white with
    // black text in dark mode, where dark boxes vanish against the page.
    const neutral = (hex: string) => hex.slice(1, 3) === hex.slice(3, 5) && hex.slice(3, 5) === hex.slice(5, 7);
    let checked = 0;
    for (const category of [...Object.keys(colorConfig.categories), 'other']) {
      const light = colorFor(category, 'light');
      if (!neutral(light) || textColorOn(light) !== '#ffffff') continue;
      const dark = colorFor(category, 'dark');
      expect(neutral(dark), category).toBe(true);
      expect(textColorOn(dark), category).toBe('#000000');
      checked++;
    }
    expect(checked).toBeGreaterThan(0);
  });

  it('thumbnail and popup draw a device in the same colour', () => {
    const cells = cellsWith({ '0_0_0': 'MAIN', '1_0_0': 'CS1' });
    drawThumbnail(document.createElement('canvas'), cells);
    const thumbStyles = fills.filter(f => f[1] === boxRect(THUMB, 1, 0, 0).x && f[2] === boxRect(THUMB, 1, 0, 0).y).map(f => f[0]);
    fills = [];
    drawPopup(document.createElement('canvas'), cells);
    const r = boxRect(POPUP, 1, 0, 0);
    const popupStyles = fills.filter(f => f[1] === r.x && f[2] === r.y && f[3] === r.w).map(f => f[0]);
    expect(thumbStyles).toContain(colorFor(categoryOf('CS1'), 'light'));
    expect(popupStyles).toContain(colorFor(categoryOf('CS1'), 'light'));
  });
});
