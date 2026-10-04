/**
 * Tests for the column filter syntax (parseFilter / matchesFilter in src/grid.ts):
 * "|" = OR, leading "!" = NOT, "…" = exact match, backslash = literal next character.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid, matchesFilter, parseFilter } from '../../src/grid.js';
import type { MSXData } from '../../src/types.js';

describe('parseFilter', () => {
  it.each([
    ['FS-A1', [{ text: 'fs-a1', exact: false, negate: false }]],
    ['"FS-A1"', [{ text: 'fs-a1', exact: true, negate: false }]],
    ['"FS-A1"|"FS-A1FM"', [{ text: 'fs-a1', exact: true, negate: false }, { text: 'fs-a1fm', exact: true, negate: false }]],
    ['!"FS-A1"', [{ text: 'fs-a1', exact: true, negate: true }]],
    [' Toshiba | !T9763 ', [{ text: 'toshiba', exact: false, negate: false }, { text: 't9763', exact: false, negate: true }]],
    ['A\\|B', [{ text: 'a|b', exact: false, negate: false }]],                   // escaped bar: not an OR
    ['\\!x', [{ text: '!x', exact: false, negate: false }]],                     // escaped !: not a NOT
    ['\\"x\\"', [{ text: '"x"', exact: false, negate: false }]],                 // escaped quotes: not exact
    ['"say \\"hi\\""', [{ text: 'say "hi"', exact: true, negate: false }]],      // quotes inside an exact term
    ['a\\\\b', [{ text: 'a\\b', exact: false, negate: false }]],                 // escaped backslash
    ['|  |', []],
    ['"', [{ text: '"', exact: false, negate: false }]],                          // a lone quote is text
  ])('%s', (input, expected) => {
    expect(parseFilter(input)).toEqual(expected);
  });
});

describe('matchesFilter', () => {
  const fs = (text: string): string => text.toLowerCase();
  it('a quoted term must equal the whole cell; a plain one may be part of it', () => {
    expect(matchesFilter(fs('FS-A1'), parseFilter('"FS-A1"'))).toBe(true);
    expect(matchesFilter(fs('FS-A1FM'), parseFilter('"FS-A1"'))).toBe(false);
    expect(matchesFilter(fs('FS-A1FM'), parseFilter('FS-A1'))).toBe(true);
  });

  it('an exact term matches any line of the haystack (value or what the cell shows)', () => {
    expect(matchesFilter('japan\n 🇯🇵 ', parseFilter('"🇯🇵"'))).toBe(true);
    expect(matchesFilter('japan\n 🇯🇵 ', parseFilter('"Japan"'))).toBe(true);
    expect(matchesFilter('belgium, sweden\n 🇧🇪  🇸🇪 ', parseFilter('"🇸🇪"'))).toBe(false);   // the whole cell, not one flag
  });

  it('OR of positives, AND of negations, exact or not', () => {
    const terms = parseFilter('FS-A1|!"FS-A1FM"');
    expect(matchesFilter(fs('FS-A1WX'), terms)).toBe(true);
    expect(matchesFilter(fs('FS-A1FM'), terms)).toBe(false);
    expect(matchesFilter(fs('HB-F1'), terms)).toBe(false);
  });

  it('no terms: everything passes', () => {
    expect(matchesFilter('x', parseFilter('  '))).toBe(true);
  });
});

describe('grid filter with exact terms', () => {
  beforeEach(() => {
    globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
    if (!globalThis.ResizeObserver) {
      globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
    }
  });

  function data(): MSXData {
    return {
      version: 1,
      generated: '2026-10-04',
      groups: [{ id: 0, key: 'identity', label: 'Identity', order: 0 }],
      columns: [
        { id: 1, key: 'brand', label: 'Brand', groupId: 0, type: 'string' },
        { id: 2, key: 'model', label: 'Model', groupId: 0, type: 'string' },
      ],
      models: ['FS-A1', 'FS-A1FM', 'FS-A1WX', 'FS-A1F'].map((model, i) => ({ id: i + 1, values: ['Panasonic', model] })),
      slotmap_lut: {},
    };
  }

  function shown(element: HTMLElement): string[] {
    return Array.from(element.querySelectorAll<HTMLElement>('tbody tr[data-model-id]'))
      .filter(tr => tr.style.display !== 'none')
      .map(tr => tr.querySelector<HTMLElement>('td[data-col-index="1"]')!.textContent!);
  }

  it.each([
    ['"FS-A1"|"FS-A1FM"', ['FS-A1', 'FS-A1FM']],
    ['FS-A1|!"FS-A1"', ['FS-A1FM', 'FS-A1WX', 'FS-A1F']],
    ['"fs-a1f"', ['FS-A1F']],
  ])('%s', (term, expected) => {
    const { element, toggleFilters } = buildGrid(data());
    toggleFilters();
    const input = element.querySelector<HTMLInputElement>('input.filter-input[data-col-index="1"]')!;
    input.value = term;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(shown(element)).toEqual(expected);
  });
});
