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
 *   …           selection_count (uint16)
 *     Per selected cell:
 *       model_id  (uint16)
 *       column_id (uint16)
 *
 * Base64 encoding: URL-safe variant — replace `+`→`-`, `/`→`_`, strip `=` padding.
 */

import type { ViewState } from '../types.js';

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

  // Pre-encode selection
  const selectionEntries = [...state.selectedCells].map(cell => {
    const [modelIdStr, colIdStr] = cell.split(':');
    return [parseInt(modelIdStr, 10), parseInt(colIdStr, 10)] as [number, number];
  });

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
  size += 2; // selection_count
  size += selectionEntries.length * 4; // model_id(2) + col_id(2) per entry

  const buf = new ArrayBuffer(size);
  const view = new DataView(buf);
  let offset = 0;

  view.setUint8(offset++, CODEC_VERSION);            // version
  view.setUint8(offset++, 0x00);                      // flags (reserved)
  view.setUint16(offset, state.sortColumnId ?? 0, false); offset += 2; // sort_col
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

  // selection
  view.setUint16(offset, selectionEntries.length, false); offset += 2;
  for (const [modelId, colId] of selectionEntries) {
    view.setUint16(offset, modelId, false); offset += 2;
    view.setUint16(offset, colId, false); offset += 2;
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

// ── decoder ────────────────────────────────────────────────────────────────

/**
 * Decode a URL-safe base64 string back to a ViewState.
 * Never throws — returns emptyViewState() on any error.
 * Unknown IDs are silently dropped.
 */
export function decodeViewState(
  base64: string,
  knownColumnIds: Set<number>,
  knownGroupIds: Set<number>,
  knownModelIds: Set<number>,
): ViewState {
  if (!base64) return emptyViewState();
  try {
    const bytes = fromUrlSafeBase64(base64);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    let offset = 0;

    if (bytes.length < 9) {
      // eslint-disable-next-line no-console
      console.warn('[url-codec] decode failed', { error: 'buffer too short', hashLength: base64.length });
      return emptyViewState();
    }

    const version = view.getUint8(offset++);
    if (version !== CODEC_VERSION) {
      // eslint-disable-next-line no-console
      console.warn('[url-codec] unknown version', { received: version, expected: CODEC_VERSION });
      return emptyViewState();
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
    if (offset + 2 > bytes.length) return emptyViewState();
    const l1 = view.getUint16(offset, false); offset += 2;
    if (offset + l1 > bytes.length) return emptyViewState();
    const hiddenColsBuf = bytes.slice(offset, offset + l1); offset += l1;
    const hiddenColumnIds = decodeBitset(hiddenColsBuf, knownColumnIds);

    // hidden_rows bitset
    if (offset + 2 > bytes.length) return emptyViewState();
    const l2 = view.getUint16(offset, false); offset += 2;
    if (offset + l2 > bytes.length) return emptyViewState();
    const hiddenRowsBuf = bytes.slice(offset, offset + l2); offset += l2;
    const hiddenRowIds = decodeBitset(hiddenRowsBuf, knownModelIds);

    // filters
    if (offset + 2 > bytes.length) return emptyViewState();
    const filterCount = view.getUint16(offset, false); offset += 2;
    const decoder = new TextDecoder();
    const filters = new Map<number, string>();
    for (let i = 0; i < filterCount; i++) {
      if (offset + 4 > bytes.length) return emptyViewState();
      const colId = view.getUint16(offset, false); offset += 2;
      const strLen = view.getUint16(offset, false); offset += 2;
      if (offset + strLen > bytes.length) return emptyViewState();
      const text = decoder.decode(bytes.slice(offset, offset + strLen)); offset += strLen;
      if (knownColumnIds.has(colId)) filters.set(colId, text);
    }

    // selection
    if (offset + 2 > bytes.length) return emptyViewState();
    const selCount = view.getUint16(offset, false); offset += 2;
    const selectedCells = new Set<string>();
    for (let i = 0; i < selCount; i++) {
      if (offset + 4 > bytes.length) return emptyViewState();
      const modelId = view.getUint16(offset, false); offset += 2;
      const colId = view.getUint16(offset, false); offset += 2;
      if (knownModelIds.has(modelId) && knownColumnIds.has(colId)) {
        selectedCells.add(`${modelId}:${colId}`);
      }
    }

    return { sortColumnId, sortDirection, collapsedGroupIds, hiddenColumnIds, hiddenRowIds, filters, selectedCells };
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn('[url-codec] decode failed', { error: String(err), hashLength: base64.length });
    return emptyViewState();
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
 * Returns emptyViewState() for empty/absent/corrupt hashes — never throws.
 */
export function decodeFromHash(
  hash: string,
  knownColumnIds: Set<number>,
  knownGroupIds: Set<number>,
  knownModelIds: Set<number>,
): ViewState {
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw) return emptyViewState();
  return decodeViewState(raw, knownColumnIds, knownGroupIds, knownModelIds);
}
