/**
 * Unit tests for the URL state codec.
 * Pure logic — no DOM interactions needed (jsdom environment is fine but unused).
 */

import { describe, it, expect } from 'vitest';
import {
  encodeViewState,
  decodeViewState,
  encodeToHash,
  decodeFromHash,
  emptyViewState,
} from '../../src/url/codec.js';
import type { ViewState } from '../../src/types.js';

// ── helpers ────────────────────────────────────────────────────────────────

const ALL_COL_IDS = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]);
const ALL_GROUP_IDS = new Set([0, 1, 2, 3, 4, 5, 6, 7]);
const ALL_MODEL_IDS = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

function roundTrip(state: ViewState): ViewState {
  const encoded = encodeViewState(state);
  return decodeViewState(encoded, ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
}

function statesEqual(a: ViewState, b: ViewState): boolean {
  if (a.sortColumnId !== b.sortColumnId) return false;
  if (a.sortDirection !== b.sortDirection) return false;
  if (a.collapsedGroupIds.size !== b.collapsedGroupIds.size) return false;
  for (const id of a.collapsedGroupIds) if (!b.collapsedGroupIds.has(id)) return false;
  if (a.hiddenColumnIds.size !== b.hiddenColumnIds.size) return false;
  for (const id of a.hiddenColumnIds) if (!b.hiddenColumnIds.has(id)) return false;
  if (a.hiddenRowIds.size !== b.hiddenRowIds.size) return false;
  for (const id of a.hiddenRowIds) if (!b.hiddenRowIds.has(id)) return false;
  if (a.filters.size !== b.filters.size) return false;
  for (const [k, v] of a.filters) if (b.filters.get(k) !== v) return false;
  if (a.selectedCells.size !== b.selectedCells.size) return false;
  for (const cell of a.selectedCells) if (!b.selectedCells.has(cell)) return false;
  return true;
}

// ── Round-trip tests ───────────────────────────────────────────────────────

describe('round-trip: empty state', () => {
  it('encodes and decodes empty state without data loss', () => {
    const state = emptyViewState();
    const result = roundTrip(state);
    expect(statesEqual(result, state)).toBe(true);
  });
});

describe('round-trip: sort ascending', () => {
  it('preserves sort column and direction', () => {
    const state: ViewState = {
      ...emptyViewState(),
      sortColumnId: 3,
      sortDirection: 'asc',
    };
    const result = roundTrip(state);
    expect(result.sortColumnId).toBe(3);
    expect(result.sortDirection).toBe('asc');
  });
});

describe('round-trip: sort descending', () => {
  it('preserves descending direction', () => {
    const state: ViewState = {
      ...emptyViewState(),
      sortColumnId: 5,
      sortDirection: 'desc',
    };
    const result = roundTrip(state);
    expect(result.sortColumnId).toBe(5);
    expect(result.sortDirection).toBe('desc');
  });
});

describe('round-trip: no-sort sentinel', () => {
  it('null sort column encodes as 0 and decodes back to null', () => {
    const state: ViewState = { ...emptyViewState(), sortColumnId: null };
    const result = roundTrip(state);
    expect(result.sortColumnId).toBeNull();
  });
});

describe('round-trip: collapsed groups', () => {
  it('preserves collapsed group IDs bitmask', () => {
    const state: ViewState = {
      ...emptyViewState(),
      collapsedGroupIds: new Set([0, 2, 7]),
    };
    const result = roundTrip(state);
    expect(result.collapsedGroupIds).toEqual(new Set([0, 2, 7]));
  });
});

describe('round-trip: hidden columns (sparse)', () => {
  it('preserves a sparse set of hidden column IDs', () => {
    const state: ViewState = {
      ...emptyViewState(),
      hiddenColumnIds: new Set([1, 15, 29]),
    };
    const result = roundTrip(state);
    expect(result.hiddenColumnIds).toEqual(new Set([1, 15, 29]));
  });
});

describe('round-trip: hidden columns (dense)', () => {
  it('preserves a dense set of hidden column IDs', () => {
    const ids = new Set([1, 2, 3, 4, 5, 6, 7, 8]);
    const state: ViewState = { ...emptyViewState(), hiddenColumnIds: ids };
    const result = roundTrip(state);
    expect(result.hiddenColumnIds).toEqual(ids);
  });
});

describe('round-trip: hidden rows', () => {
  it('preserves hidden model IDs', () => {
    const state: ViewState = {
      ...emptyViewState(),
      hiddenRowIds: new Set([2, 5, 9]),
    };
    const result = roundTrip(state);
    expect(result.hiddenRowIds).toEqual(new Set([2, 5, 9]));
  });
});

describe('round-trip: single filter', () => {
  it('preserves a single ASCII filter', () => {
    const state: ViewState = {
      ...emptyViewState(),
      filters: new Map([[5, 'turboR']]),
    };
    const result = roundTrip(state);
    expect(result.filters.get(5)).toBe('turboR');
    expect(result.filters.size).toBe(1);
  });
});

describe('round-trip: multiple filters', () => {
  it('preserves multiple filter entries', () => {
    const state: ViewState = {
      ...emptyViewState(),
      filters: new Map([[3, '1985'], [5, 'MSX2']]),
    };
    const result = roundTrip(state);
    expect(result.filters.get(3)).toBe('1985');
    expect(result.filters.get(5)).toBe('MSX2');
    expect(result.filters.size).toBe(2);
  });
});

describe('round-trip: UTF-8 multibyte filter', () => {
  it('preserves multibyte Unicode characters in filter text', () => {
    const state: ViewState = {
      ...emptyViewState(),
      filters: new Map([[1, '日本語テスト']]),
    };
    const result = roundTrip(state);
    expect(result.filters.get(1)).toBe('日本語テスト');
  });
});

describe('round-trip: selected cells', () => {
  it('preserves selected cell coordinates', () => {
    const state: ViewState = {
      ...emptyViewState(),
      selectedCells: new Set(['1:3', '2:5', '10:29']),
    };
    const result = roundTrip(state);
    expect(result.selectedCells).toEqual(new Set(['1:3', '2:5', '10:29']));
  });
});

describe('round-trip: all fields populated (kitchen sink)', () => {
  it('preserves all state dimensions simultaneously', () => {
    const state: ViewState = {
      sortColumnId: 3,
      sortDirection: 'desc',
      collapsedGroupIds: new Set([1, 3]),
      hiddenColumnIds: new Set([7, 8, 9]),
      hiddenRowIds: new Set([4, 6]),
      filters: new Map([[5, 'turboR'], [1, 'Panasonic']]),
      selectedCells: new Set(['1:2', '3:5']),
    };
    const result = roundTrip(state);
    expect(statesEqual(result, state)).toBe(true);
  });
});

// ── Boundary tests ─────────────────────────────────────────────────────────

describe('boundary: bit 0 (ID 0) in bitset', () => {
  it('handles group ID 0 correctly', () => {
    const state: ViewState = {
      ...emptyViewState(),
      collapsedGroupIds: new Set([0]),
    };
    const result = roundTrip(state);
    expect(result.collapsedGroupIds.has(0)).toBe(true);
  });
});

describe('boundary: empty selection section', () => {
  it('decodes empty selection without error', () => {
    const state: ViewState = {
      ...emptyViewState(),
      selectedCells: new Set(),
    };
    const result = roundTrip(state);
    expect(result.selectedCells.size).toBe(0);
  });
});

describe('boundary: empty filter string', () => {
  it('round-trips a filter with empty string value', () => {
    const state: ViewState = {
      ...emptyViewState(),
      filters: new Map([[3, '']]),
    };
    const result = roundTrip(state);
    expect(result.filters.get(3)).toBe('');
  });
});

// ── Version / compat tests ─────────────────────────────────────────────────

describe('version: encoded payload starts with version byte 0x01', () => {
  it('first byte of decoded base64 is 0x01', () => {
    const encoded = encodeViewState(emptyViewState());
    // Decode raw base64 to check version byte
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '=='.slice(0, (4 - (base64.length % 4)) % 4);
    const binary = atob(padded);
    expect(binary.charCodeAt(0)).toBe(0x01);
  });
});

describe('version: unknown version byte returns empty state with console.warn', () => {
  it('returns emptyViewState when version byte is 0xFF', () => {
    // Build a valid payload then corrupt version byte
    const valid = encodeViewState(emptyViewState());
    const base64 = valid.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '=='.slice(0, (4 - (base64.length % 4)) % 4);
    const binary = atob(padded);
    // Swap version byte to 0xFF
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    bytes[0] = 0xFF;
    let corrupted = btoa(String.fromCharCode(...bytes));
    corrupted = corrupted.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

    const result = decodeViewState(corrupted, ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

// ── Resilience tests ───────────────────────────────────────────────────────

describe('resilience: empty buffer', () => {
  it('returns emptyViewState for empty base64 string', () => {
    const result = decodeViewState('', ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

describe('resilience: truncated buffer', () => {
  it('returns emptyViewState without throwing for truncated input', () => {
    const result = decodeViewState('AQ', ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

describe('resilience: corrupted base64', () => {
  it('returns emptyViewState without throwing for invalid base64', () => {
    const result = decodeViewState('!!!not_valid_base64!!!', ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

describe('resilience: unknown column IDs are silently dropped', () => {
  it('ignores column ID 999 not in known set, preserves other state', () => {
    // Encode with known columns
    const state: ViewState = {
      ...emptyViewState(),
      hiddenColumnIds: new Set([7]),
      filters: new Map([[5, 'test']]),
    };
    const encoded = encodeViewState(state);
    // Decode with a restricted known set that excludes col 7 but includes col 5
    const limitedCols = new Set([1, 2, 3, 4, 5, 6]);
    const result = decodeViewState(encoded, limitedCols, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(result.hiddenColumnIds.has(7)).toBe(false);
    expect(result.filters.get(5)).toBe('test');
  });
});

describe('resilience: unknown model IDs are silently dropped', () => {
  it('ignores model IDs not in known set', () => {
    const state: ViewState = {
      ...emptyViewState(),
      hiddenRowIds: new Set([5]),
    };
    const encoded = encodeViewState(state);
    const limitedModels = new Set([1, 2, 3, 4]); // excludes model 5
    const result = decodeViewState(encoded, ALL_COL_IDS, ALL_GROUP_IDS, limitedModels);
    expect(result.hiddenRowIds.has(5)).toBe(false);
  });
});

describe('resilience: unknown filter column IDs are silently dropped', () => {
  it('drops filter for unknown column ID', () => {
    const state: ViewState = {
      ...emptyViewState(),
      filters: new Map([[5, 'turboR']]),
    };
    const encoded = encodeViewState(state);
    const limitedCols = new Set([1, 2, 3]); // excludes col 5
    const result = decodeViewState(encoded, limitedCols, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(result.filters.size).toBe(0);
  });
});

describe('resilience: unknown selection IDs are silently dropped', () => {
  it('drops selected cell with unknown model or column ID', () => {
    const state: ViewState = {
      ...emptyViewState(),
      selectedCells: new Set(['1:3', '2:5']),
    };
    const encoded = encodeViewState(state);
    const limitedModels = new Set([1]); // excludes model 2
    const result = decodeViewState(encoded, ALL_COL_IDS, ALL_GROUP_IDS, limitedModels);
    expect(result.selectedCells.has('1:3')).toBe(true);
    expect(result.selectedCells.has('2:5')).toBe(false);
  });
});

// ── URL layer tests ────────────────────────────────────────────────────────

describe('URL layer: encodeToHash returns string starting with #', () => {
  it('result starts with #', () => {
    const hash = encodeToHash(emptyViewState());
    expect(hash.startsWith('#')).toBe(true);
  });
});

describe('URL layer: decodeFromHash with empty string returns empty state', () => {
  it('empty string → emptyViewState', () => {
    const result = decodeFromHash('', ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

describe('URL layer: decodeFromHash with bare # returns empty state', () => {
  it('"#" → emptyViewState', () => {
    const result = decodeFromHash('#', ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, emptyViewState())).toBe(true);
  });
});

describe('URL layer: encodeToHash + decodeFromHash round-trips', () => {
  it('hash wrapping does not corrupt the payload', () => {
    const state: ViewState = {
      ...emptyViewState(),
      sortColumnId: 3,
      sortDirection: 'desc',
      collapsedGroupIds: new Set([2]),
      filters: new Map([[5, 'turboR']]),
    };
    const hash = encodeToHash(state);
    const result = decodeFromHash(hash, ALL_COL_IDS, ALL_GROUP_IDS, ALL_MODEL_IDS);
    expect(statesEqual(result, state)).toBe(true);
  });
});
