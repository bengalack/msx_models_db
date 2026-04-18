/**
 * Tests for the "Include headers on copy" feature.
 *
 * copySelection(true) must prepend a tab-joined header row
 * (shortLabel ?? label for each selected visible column).
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { buildGrid } from '../../src/grid.js';
import type { MSXData, ViewState } from '../../src/types.js';

function makeData(): MSXData {
  return {
    version: 1,
    generated: '2026-04-18',
    groups: [
      { id: 0, key: 'identity', label: 'Identity', order: 0 },
      { id: 1, key: 'specs',    label: 'Specs',    order: 1 },
    ],
    columns: [
      { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
      { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string', shortLabel: 'Model' },
      { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number', shortLabel: 'Yr' },
      { id: 4, key: 'ram',          label: 'RAM (KB)',     groupId: 1, type: 'number' },
    ],
    models: [
      { id: 1, values: ['Sony',    'HB-F1XD',   1987,  64] },
      { id: 2, values: ['Philips', 'NMS-8250',  1986, 128] },
    ],
    slotmap_lut: {},
  };
}

const defaultInit = (): ViewState => ({
  sortColumnId: null,
  sortDirection: 'asc',
  filters: new Map(),
  hiddenColumnIds: new Set(),
  hiddenRowIds: new Set(),
  collapsedGroupIds: new Set(),
  selectedCells: new Set(),
});

beforeEach(() => {
  globalThis.requestAnimationFrame = (cb: FrameRequestCallback): number => { cb(0); return 0; };
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class {
      observe() {} unobserve() {} disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

describe('copySelection — includeHeaders', () => {
  it('returns empty string when nothing is selected (includeHeaders=true)', () => {
    const { copySelection } = buildGrid(makeData(), { initialState: defaultInit() });
    expect(copySelection(true)).toBe('');
  });

  it('omits header row when includeHeaders is false (existing behaviour)', () => {
    const init = defaultInit();
    // year has stable column id=3 in makeData()
    init.selectedCells = new Set(['1:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const result = copySelection(false);
    expect(result).toBe('1987');
  });

  it('omits header row when includeHeaders is absent (existing behaviour)', () => {
    const init = defaultInit();
    init.selectedCells = new Set(['1:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    expect(copySelection()).toBe('1987');
  });

  it('prepends header row using shortLabel when available', () => {
    const init = defaultInit();
    // year (id=3, shortLabel "Yr") for model 1 (modelId=1)
    init.selectedCells = new Set(['1:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const result = copySelection(true);
    const lines = result.split('\n');
    expect(lines[0]).toBe('Yr');   // shortLabel
    expect(lines[1]).toBe('1987'); // data
    expect(lines.length).toBe(2);
  });

  it('falls back to label when shortLabel is absent', () => {
    const init = defaultInit();
    // ram has stable column id=4, label "RAM (KB)", no shortLabel
    init.selectedCells = new Set(['1:4']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('RAM (KB)');
    expect(lines[1]).toBe('64');
  });

  it('header columns match data row columns for multi-column selection', () => {
    const init = defaultInit();
    // model (id=2, shortLabel "Model") and year (id=3, shortLabel "Yr") for model 1
    init.selectedCells = new Set(['1:2', '1:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('Model\tYr');
    expect(lines[1]).toBe('HB-F1XD\t1987');
  });

  it('header columns match across multiple rows with same columns', () => {
    const init = defaultInit();
    // year (id=3) for both models (modelId=1 and 2)
    init.selectedCells = new Set(['1:3', '2:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    expect(lines[0]).toBe('Yr');
    expect(lines[1]).toBe('1987');
    expect(lines[2]).toBe('1986');
    expect(lines.length).toBe(3);
  });

  it('header row is union of all selected columns when rows have different columns selected', () => {
    const init = defaultInit();
    // Row 1 (modelId=1): model (id=2) + year (id=3) selected
    // Row 2 (modelId=2): year (id=3) only selected
    init.selectedCells = new Set(['1:2', '1:3', '2:3']);
    const { copySelection } = buildGrid(makeData(), { initialState: init });
    const lines = copySelection(true).split('\n');
    // Header = union in visible order: Model, Yr
    expect(lines[0]).toBe('Model\tYr');
    // Row 1 has both columns
    expect(lines[1]).toBe('HB-F1XD\t1987');
    // Row 2 has only year (col idx 2), model (col idx 1) is not selected for row 2
    // so row 2's data line contains only year value
    expect(lines[2]).toBe('1986');
    expect(lines.length).toBe(3);
  });
});
