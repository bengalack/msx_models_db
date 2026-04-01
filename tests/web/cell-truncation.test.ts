/**
 * Tests for cell value truncation in buildGrid() / buildDataRow().
 *
 * When a ColumnDef has truncateLimit > 0:
 *  - values longer than the limit are clipped to (limit-1) chars + '…'
 *  - the full value is stored in td.dataset.fullValue
 *  - plain cell: mouseenter sets td.title = fullValue
 *  - link cell: a.title = "<fullValue> — <url>"
 *  - values at or below the limit are unchanged with no dataset.fullValue
 *  - truncateLimit=0 / absent = no truncation
 * Sorting and clipboard copy are unaffected (they read model.values directly).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

// ── Helpers ───────────────────────────────────────────────────────────────

function makeData(overrides?: {
  mfrLimit?: number;
  modelLimit?: number;
  mfr?: string;
  modelName?: string;
  modelUrl?: string;
}): MSXData {
  const {
    mfrLimit = 10,
    modelLimit = 10,
    mfr = 'Spectravideo',
    modelName = 'SVI-728',
    modelUrl,
  } = overrides ?? {};

  return {
    version: 1,
    generated: '2026-04-01',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
    ],
    columns: [
      {
        id: 1, key: 'manufacturer', label: 'Manufacturer',
        groupId: 0, type: 'string',
        ...(mfrLimit > 0 ? { truncateLimit: mfrLimit } : {}),
      },
      {
        id: 2, key: 'model', label: 'Model',
        groupId: 0, type: 'string', linkable: true,
        ...(modelLimit > 0 ? { truncateLimit: modelLimit } : {}),
      },
    ],
    models: [
      {
        id: 1,
        values: [mfr, modelName],
        ...(modelUrl ? { links: { model: modelUrl } } : {}),
      },
    ],
    slotmap_lut: {},
  };
}

function getGrid(data: MSXData): HTMLElement {
  const { element } = buildGrid(data);
  document.body.appendChild(element);
  return element;
}

function getCell(wrap: HTMLElement, colIndex: number): HTMLTableCellElement | null {
  return wrap.querySelector<HTMLTableCellElement>(`tbody td[data-col-index="${colIndex}"]`);
}

function fireMouseEnter(el: HTMLElement): void {
  el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
}

beforeEach(() => {
  // Synchronous RAF stub
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  // ResizeObserver stub
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
  document.body.innerHTML = '';
});

// ── Plain cell truncation ─────────────────────────────────────────────────

describe('plain cell truncation', () => {
  it('clips a value longer than the limit to (limit-1) chars + ellipsis', () => {
    // "Spectravideo" = 12 chars > limit=10 → display first 9 + '…' = 'Spectravi…'
    const wrap = getGrid(makeData({ mfr: 'Spectravideo' }));
    const td = getCell(wrap, 0)!;
    expect(td.textContent).toBe('Spectravi\u2026');
  });

  it('stores the full value in dataset.fullValue when truncated', () => {
    const wrap = getGrid(makeData({ mfr: 'Spectravideo' }));
    const td = getCell(wrap, 0)!;
    expect(td.dataset.fullValue).toBe('Spectravideo');
  });

  it('sets td.title to full value on mouseenter', () => {
    const wrap = getGrid(makeData({ mfr: 'Spectravideo' }));
    const td = getCell(wrap, 0)!;
    fireMouseEnter(td);
    expect(td.title).toBe('Spectravideo');
  });

  it('does not truncate a value exactly at the limit (10 chars)', () => {
    // "Sharp Corp" = 10 chars = limit, must not truncate
    const wrap = getGrid(makeData({ mfr: 'Sharp Corp' }));
    const td = getCell(wrap, 0)!;
    expect(td.textContent).toBe('Sharp Corp');
    expect(td.dataset.fullValue).toBeUndefined();
  });

  it('does not truncate a value shorter than the limit', () => {
    const wrap = getGrid(makeData({ mfr: 'Canon' }));
    const td = getCell(wrap, 0)!;
    expect(td.textContent).toBe('Canon');
    expect(td.dataset.fullValue).toBeUndefined();
  });

  it('does not truncate when truncateLimit is absent (0/undefined)', () => {
    const longValue = 'A'.repeat(50);
    const wrap = getGrid(makeData({ mfrLimit: 0, mfr: longValue }));
    const td = getCell(wrap, 0)!;
    expect(td.textContent).toBe(longValue);
    expect(td.dataset.fullValue).toBeUndefined();
  });
});

// ── Link cell truncation ──────────────────────────────────────────────────

describe('link cell truncation', () => {
  const URL = 'https://www.msx.org/wiki/Spectravideo_SVI-728';

  it('truncates the link text when value exceeds limit', () => {
    // "SVI-728 Color" = 13 chars > 10 → 9 chars + '…' = 'SVI-728 C…'
    const wrap = getGrid(makeData({ modelName: 'SVI-728 Color', modelUrl: URL }));
    const td = getCell(wrap, 1)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.textContent).toBe('SVI-728 C\u2026');
  });

  it('sets a.title to "fullValue \u2014 url" when truncated', () => {
    const wrap = getGrid(makeData({ modelName: 'SVI-728 Color', modelUrl: URL }));
    const td = getCell(wrap, 1)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(`SVI-728 Color \u2014 ${URL}`);
  });

  it('sets a.title to URL only when value is at or below limit', () => {
    // "Sony HB-10" = 10 chars = limit, no truncation
    const wrap = getGrid(makeData({ modelName: 'Sony HB-10', modelUrl: URL }));
    const td = getCell(wrap, 1)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(URL);
  });

  it('link cell without truncation keeps URL-only title', () => {
    // Short name, no truncation
    const wrap = getGrid(makeData({ modelName: 'HB-10', modelUrl: URL }));
    const td = getCell(wrap, 1)!;
    const a = td.querySelector<HTMLAnchorElement>('a.cell-link')!;
    expect(a.title).toBe(URL);
    expect(td.dataset.fullValue).toBeUndefined();
  });
});

// ── Mouseenter handler priority ───────────────────────────────────────────

describe('mouseenter handler', () => {
  it('link cells are skipped by the mouseenter handler (title managed by <a>)', () => {
    const URL = 'https://www.msx.org/wiki/SVI-728';
    const wrap = getGrid(makeData({ modelName: 'SVI-728 Color', modelUrl: URL }));
    const td = getCell(wrap, 1)!;
    // Remove any title set at render time to test the handler independently
    td.removeAttribute('title');
    fireMouseEnter(td);
    // Handler must skip link cells, so td.title stays empty
    expect(td.title).toBe('');
  });

  it('non-truncated cell without overflow and no data-tooltip gets no title', () => {
    const wrap = getGrid(makeData({ mfr: 'Canon' }));
    const td = getCell(wrap, 0)!;
    td.removeAttribute('title');
    fireMouseEnter(td);
    expect(td.title).toBe('');
  });
});
