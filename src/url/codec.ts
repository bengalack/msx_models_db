/**
 * URL state codec — binary encode/decode of ViewState into a URL-safe base64 hash.
 *
 * Binary format (big-endian throughout):
 *
 *   Byte 0:     version (0x01)
 *   Byte 1:     flags   (reserved, 0x00)
 *   Bytes 2–3:  sort_column_id (uint16; 0x0000 = no sort)
 *   Byte 4:     sort_direction (0x00 = asc, 0x01 = desc)
 *   Bytes 5–8:  collapsed_groups bitmask (uint32; bit N = group ID N is collapsed)
 *   Bytes 9–10: hidden_columns bitset byte length L1 (uint16)
 *   …           hidden_columns bitset (L1 bytes; bit N = column ID N is hidden)
 *   …           hidden_rows bitset byte length L2 (uint16)
 *   …           hidden_rows bitset (L2 bytes; bit N = model ID N is hidden)
 *   …           filter_count (uint16)
 *     Per filter:
 *       column_id          (uint16)
 *       string_byte_length (uint16)
 *       UTF-8 bytes
 *   …           selection_row_count (uint16)
 *     Per selected row:
 *       model_id             (uint16)
 *       col_bitset_byte_len  (uint16)
 *       col_bitset bytes     (variable; bit N = column ID N is selected)
 *
 * Base64 encoding: URL-safe variant — replace `+`→`-`, `/`→`_`, strip `=` padding.
 */

import type { ColumnDef, ViewState } from '../types.js';

const CODEC_VERSION = 0x01;

// ── base64 helpers ─────────────────────────────────────────────────────────

function toUrlSafeBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromUrlSafeBase64(s: string): Uint8Array {
  const base64 = s.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '=='.slice(0, (4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

// ── bitset helpers ─────────────────────────────────────────────────────────

/** Encode a Set<number> as a packed bitset. Returns empty Uint8Array for empty set. */
function encodeBitset(ids: Set<number>): Uint8Array {
  if (ids.size === 0) return new Uint8Array(0);
  const maxId = Math.max(...ids);
  const byteLength = Math.ceil((maxId + 1) / 8);
  const buf = new Uint8Array(byteLength);
  for (const id of ids) {
    buf[id >> 3] |= 1 << (id & 7);
  }
  return buf;
}

/** Decode a bitset back to a Set<number> of IDs, filtering to only known IDs. */
function decodeBitset(buf: Uint8Array, knownIds: Set<number>): Set<number> {
  const result = new Set<number>();
  for (let byteIdx = 0; byteIdx < buf.length; byteIdx++) {
    const byte = buf[byteIdx];
    if (byte === 0) continue;
    for (let bit = 0; bit < 8; bit++) {
      if (byte & (1 << bit)) {
        const id = byteIdx * 8 + bit;
        if (knownIds.has(id)) result.add(id);
      }
    }
  }
  return result;
}

// ── encoder ────────────────────────────────────────────────────────────────

/** Encode a ViewState to a URL-safe base64 string. Throws on internal errors. */
export function encodeViewState(state: ViewState): string {
  const encoder = new TextEncoder();

  // Pre-encode filters to UTF-8
  const filterEntries = [...state.filters.entries()];
  const filterBuffers = filterEntries.map(([, text]) => encoder.encode(text));

  // Pre-encode selection — group cells by model ID, encode each row's columns as a bitset
  const selectionByRow = new Map<number, Set<number>>();
  for (const cell of state.selectedCells) {
    const colonIdx = cell.indexOf(':');
    const modelId = parseInt(cell.slice(0, colonIdx), 10);
    const colId = parseInt(cell.slice(colonIdx + 1), 10);
    let cols = selectionByRow.get(modelId);
    if (!cols) { cols = new Set(); selectionByRow.set(modelId, cols); }
    cols.add(colId);
  }
  const selectionRows = [...selectionByRow.entries()];
  const selectionBitsets = selectionRows.map(([, cols]) => encodeBitset(cols));

  // Build bitsets
  const hiddenColsBitset = encodeBitset(state.hiddenColumnIds);
  const hiddenRowsBitset = encodeBitset(state.hiddenRowIds);

  // Collapsed groups bitmask (uint32 — group IDs are 0–31)
  let collapsedMask = 0;
  for (const gid of state.collapsedGroupIds) {
    if (gid >= 0 && gid <= 31) collapsedMask |= (1 << gid);
  }

  // Calculate total buffer size
  // Fixed header: version(1) + flags(1) + sort_col(2) + sort_dir(1) + collapsed(4) = 9
  let size = 9;
  size += 2 + hiddenColsBitset.length;  // L1 + bitset
  size += 2 + hiddenRowsBitset.length;  // L2 + bitset
  size += 2; // filter_count
  for (let i = 0; i < filterEntries.length; i++) {
    size += 2 + 2 + filterBuffers[i].length; // col_id + str_len + utf8
  }
  size += 2; // selection_row_count
  for (let i = 0; i < selectionRows.length; i++) {
    size += 2 + 2 + selectionBitsets[i].length; // model_id(2) + bitset_len(2) + bitset
  }

  const buf = new ArrayBuffer(size);
  const view = new DataView(buf);
  let offset = 0;

  // Sort column ID 0 is reserved as the "no sort" sentinel in the binary format.
  // Treat it as unsortable — encode as no-sort.
  const sortColId = (state.sortColumnId !== null && state.sortColumnId !== 0)
    ? state.sortColumnId : 0;

  view.setUint8(offset++, CODEC_VERSION);            // version
  view.setUint8(offset++, 0x00);                      // flags (reserved)
  view.setUint16(offset, sortColId, false); offset += 2; // sort_col
  view.setUint8(offset++, state.sortDirection === 'desc' ? 0x01 : 0x00); // sort_dir
  view.setUint32(offset, collapsedMask >>> 0, false); offset += 4; // collapsed_groups

  // hidden_columns bitset
  view.setUint16(offset, hiddenColsBitset.length, false); offset += 2;
  new Uint8Array(buf, offset, hiddenColsBitset.length).set(hiddenColsBitset);
  offset += hiddenColsBitset.length;

  // hidden_rows bitset
  view.setUint16(offset, hiddenRowsBitset.length, false); offset += 2;
  new Uint8Array(buf, offset, hiddenRowsBitset.length).set(hiddenRowsBitset);
  offset += hiddenRowsBitset.length;

  // filters
  view.setUint16(offset, filterEntries.length, false); offset += 2;
  for (let i = 0; i < filterEntries.length; i++) {
    const [colId] = filterEntries[i];
    const fb = filterBuffers[i];
    view.setUint16(offset, colId, false); offset += 2;
    view.setUint16(offset, fb.length, false); offset += 2;
    new Uint8Array(buf, offset, fb.length).set(fb);
    offset += fb.length;
  }

  // selection — per-row bitset: row_count, then per row: model_id + col_bitset_len + col_bitset
  view.setUint16(offset, selectionRows.length, false); offset += 2;
  for (let i = 0; i < selectionRows.length; i++) {
    const [modelId] = selectionRows[i];
    const bitset = selectionBitsets[i];
    view.setUint16(offset, modelId, false); offset += 2;
    view.setUint16(offset, bitset.length, false); offset += 2;
    new Uint8Array(buf, offset, bitset.length).set(bitset);
    offset += bitset.length;
  }

  return toUrlSafeBase64(new Uint8Array(buf));
}

// ── empty state factory ────────────────────────────────────────────────────

export function emptyViewState(): ViewState {
  return {
    sortColumnId: null,
    sortDirection: 'asc',
    collapsedGroupIds: new Set(),
    hiddenColumnIds: new Set(),
    hiddenRowIds: new Set(),
    filters: new Map(),
    selectedCells: new Set(),
  };
}

/**
 * The view a first-time visitor gets: empty, except that every column flagged
 * `defaultOff` in the column config starts hidden.
 *
 * Defaults seed the *initial* view only — they are never folded into the hash.
 * The encoded `hidden_columns` bitset stays absolute (see the format note above),
 * so a URL shared before a column became `defaultOff` still decodes to exactly
 * what its author saw, with no codec version bump.
 */
export function defaultViewState(columns: readonly ColumnDef[]): ViewState {
  const state = emptyViewState();
  for (const col of columns) {
    if (col.defaultOff) state.hiddenColumnIds.add(col.id);
  }
  return state;
}

/** Copy a ViewState so two callers can never share the same mutable sets. */
function cloneViewState(state: ViewState): ViewState {
  return {
    sortColumnId: state.sortColumnId,
    sortDirection: state.sortDirection,
    collapsedGroupIds: new Set(state.collapsedGroupIds),
    hiddenColumnIds: new Set(state.hiddenColumnIds),
    hiddenRowIds: new Set(state.hiddenRowIds),
    filters: new Map(state.filters),
    selectedCells: new Set(state.selectedCells),
  };
}

// ── decoder ────────────────────────────────────────────────────────────────

/**
 * Decode a URL-safe base64 string back to a ViewState.
 * Never throws — returns `fallback` (default: emptyViewState()) on any error.
 * Unknown IDs are silently dropped.
 *
 * `fallback` covers only the *absence* of a decodable hash. A hash that decodes
 * cleanly wins outright, even when it hides nothing.
 */
export function decodeViewState(
  base64: string,
  knownColumnIds: Set<number>,
  knownGroupIds: Set<number>,
  knownModelIds: Set<number>,
  fallback?: ViewState,
): ViewState {
  const onFailure = (): ViewState => (fallback ? cloneViewState(fallback) : emptyViewState());
  if (!base64) return onFailure();
  try {
    const bytes = fromUrlSafeBase64(base64);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let offset = 0;

    if (bytes.length < 9) {
      // eslint-disable-next-line no-console
      console.warn('[url-codec] decode failed', { error: 'buffer too short', hashLength: base64.length });
      return onFailure();
    }

    const version = view.getUint8(offset++);
    if (version !== CODEC_VERSION) {
      // eslint-disable-next-line no-console
      console.warn('[url-codec] unknown version', { received: version, expected: CODEC_VERSION });
      return onFailure();
    }

    offset++; // skip flags byte

    const rawSortColId = view.getUint16(offset, false); offset += 2;
    const sortColumnId = rawSortColId === 0 ? null : (knownColumnIds.has(rawSortColId) ? rawSortColId : null);
    const sortDir = view.getUint8(offset++);
    const sortDirection: 'asc' | 'desc' = sortDir === 0x01 ? 'desc' : 'asc';

    const collapsedMask = view.getUint32(offset, false); offset += 4;
    const collapsedGroupIds = new Set<number>();
    for (let bit = 0; bit < 32; bit++) {
      if (collapsedMask & (1 << bit)) {
        if (knownGroupIds.has(bit)) collapsedGroupIds.add(bit);
      }
    }

    // hidden_columns bitset
    if (offset + 2 > bytes.length) return onFailure();
    const l1 = view.getUint16(offset, false); offset += 2;
    if (offset + l1 > bytes.length) return onFailure();
    const hiddenColsBuf = bytes.slice(offset, offset + l1); offset += l1;
    const hiddenColumnIds = decodeBitset(hiddenColsBuf, knownColumnIds);

    // hidden_rows bitset
    if (offset + 2 > bytes.length) return onFailure();
    const l2 = view.getUint16(offset, false); offset += 2;
    if (offset + l2 > bytes.length) return onFailure();
    const hiddenRowsBuf = bytes.slice(offset, offset + l2); offset += l2;
    const hiddenRowIds = decodeBitset(hiddenRowsBuf, knownModelIds);

    // filters
    if (offset + 2 > bytes.length) return onFailure();
    const filterCount = view.getUint16(offset, false); offset += 2;
    const decoder = new TextDecoder();
    const filters = new Map<number, string>();
    for (let i = 0; i < filterCount; i++) {
      if (offset + 4 > bytes.length) return onFailure();
      const colId = view.getUint16(offset, false); offset += 2;
      const strLen = view.getUint16(offset, false); offset += 2;
      if (offset + strLen > bytes.length) return onFailure();
      const text = decoder.decode(bytes.slice(offset, offset + strLen)); offset += strLen;
      if (knownColumnIds.has(colId)) filters.set(colId, text);
    }

    // selection — per-row bitset
    if (offset + 2 > bytes.length) return onFailure();
    const selRowCount = view.getUint16(offset, false); offset += 2;
    const selectedCells = new Set<string>();
    for (let i = 0; i < selRowCount; i++) {
      if (offset + 4 > bytes.length) return onFailure();
      const modelId = view.getUint16(offset, false); offset += 2;
      const bitsetLen = view.getUint16(offset, false); offset += 2;
      if (offset + bitsetLen > bytes.length) return onFailure();
      const colBitset = bytes.slice(offset, offset + bitsetLen); offset += bitsetLen;
      if (!knownModelIds.has(modelId)) continue; // skip unknown model, already advanced offset
      for (let byteIdx = 0; byteIdx < colBitset.length; byteIdx++) {
        const byte = colBitset[byteIdx];
        if (byte === 0) continue;
        for (let bit = 0; bit < 8; bit++) {
          if (byte & (1 << bit)) {
            const colId = byteIdx * 8 + bit;
            if (knownColumnIds.has(colId)) selectedCells.add(`${modelId}:${colId}`);
          }
        }
      }
    }

    return { sortColumnId, sortDirection, collapsedGroupIds, hiddenColumnIds, hiddenRowIds, filters, selectedCells };
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn('[url-codec] decode failed', { error: String(err), hashLength: base64.length });
    return onFailure();
  }
}

// ── hash wrappers ──────────────────────────────────────────────────────────

/** Encode ViewState to a `#…` URL hash string. Returns '' on error. */
export function encodeToHash(state: ViewState): string {
  try {
    return '#' + encodeViewState(state);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn('[url-codec] encode failed', { error: String(err) });
    return '';
  }
}

/**
 * Decode a URL hash string (e.g. `window.location.hash`) to a ViewState.
 * Returns `fallback` (default: emptyViewState()) for empty/absent/corrupt
 * hashes — never throws. Pass defaultViewState(columns) as the fallback so a
 * first-time visitor lands on the configured defaults.
 */
export function decodeFromHash(
  hash: string,
  knownColumnIds: Set<number>,
  knownGroupIds: Set<number>,
  knownModelIds: Set<number>,
  fallback?: ViewState,
): ViewState {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw) return fallback ? cloneViewState(fallback) : emptyViewState();
  return decodeViewState(raw, knownColumnIds, knownGroupIds, knownModelIds, fallback);
}
