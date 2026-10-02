/**
 * Slotmap Overview — the slot map of a model drawn on a canvas.
 *
 * The cell shows a 90×21 thumbnail; hovering it opens a floating popup with a
 * larger, labelled drawing whose boxes show the slot map tooltips. Both are
 * drawn from the model's 64 slot map cells (columns slotmap_{ms}_{ss}_{p}); the
 * column's own value is only its sort key. Nothing is stored as an image.
 *
 * Colours come from data/slotmap-colors.json, compiled into the bundle at build
 * time (never fetched at runtime). Design: technical-design.md,
 * *Feature Design: Slotmap Overview*.
 */

import colorConfig from '../data/slotmap-colors.json';
import { SLOTMAP_ABSENT, SLOTMAP_EMPTY_PAGE, SLOTMAP_MIRROR_SUFFIX } from './symbols.js';

/** 64 slot map cells, index = ms*16 + ss*4 + page. */
export type SlotCells = (string | null)[];

type Theme = 'light' | 'dark';
type ColorValue = string | { light: string; dark: string };

export const SLOT_COUNT = 4;

export function cellIndex(ms: number, ss: number, page: number): number {
  return ms * 16 + ss * 4 + page;
}

/** Column key of one slot map cell. */
export function slotKey(ms: number, ss: number, page: number): string {
  return `slotmap_${ms}_${ss}_${page}`;
}

// ── Classification ─────────────────────────────────────────────────────────

export type CellKind = 'absent' | 'empty' | 'device';

export function cellKind(value: string | null | undefined): CellKind {
  if (value === null || value === undefined || value === '' || value === SLOTMAP_ABSENT) return 'absent';
  if (value === SLOTMAP_EMPTY_PAGE) return 'empty';
  return 'device';
}

const CATEGORIES: [string, RegExp[]][] = Object.entries(
  colorConfig.categories as Record<string, string[]>,
).map(([name, patterns]) => [name, patterns.map(p => new RegExp(p))]);

/** Colour category of a device label ("CS1", "RAM*", "ES2!"); "other" when none matches. */
export function categoryOf(label: string): string {
  const base = label.endsWith(SLOTMAP_MIRROR_SUFFIX) ? label.slice(0, -SLOTMAP_MIRROR_SUFFIX.length) : label;
  for (const [name, patterns] of CATEGORIES) {
    if (patterns.some(re => re.test(base))) return name;
  }
  return 'other';
}

/** Colour of a category in a theme (one set for thumbnail and popup); unknown categories use "other". */
export function colorFor(category: string, theme: Theme): string {
  const colors = colorConfig.colors as Record<string, ColorValue>;
  const value = colors[category] ?? colors.other;
  return typeof value === 'string' ? value : value[theme];
}

/** Black or white, whichever contrasts best with a "#rrggbb" background (WCAG luminance). */
export function textColorOn(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  const channel = (c: number): number => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  const lum = 0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255);
  // Contrast against black (lum + 0.05) / 0.05 vs white 1.05 / (lum + 0.05)
  return (lum + 0.05) / 0.05 >= 1.05 / (lum + 0.05) ? '#000000' : '#ffffff';
}

/** A primary slot is expanded when any page of sub-slots 1–3 is present. */
export function isExpanded(cells: SlotCells, ms: number): boolean {
  for (let ss = 1; ss < 4; ss++) {
    for (let p = 0; p < 4; p++) {
      if (cellKind(cells[cellIndex(ms, ss, p)]) !== 'absent') return true;
    }
  }
  return false;
}

// ── Geometry ───────────────────────────────────────────────────────────────

interface Geometry {
  boxW: number;
  boxH: number;
  /** Grid line thickness — the same horizontally and vertically. */
  grid: number;
  /** Space between primary slot blocks. */
  gap: number;
  pad: number;
  /** Height above the blocks for the "SLOT n" titles (0 = none). */
  titleH: number;
  /** Height below the blocks for sub-slot numbers + "subslots" (0 = none). */
  footerH: number;
}

/** 4 × (4×4 px boxes + 1 px grid) = 21 px per block; 4 blocks + 3 × 2 px = 90 × 21. */
export const THUMB: Geometry = { boxW: 4, boxH: 4, grid: 1, gap: 2, pad: 0, titleH: 0, footerH: 0 };
export const POPUP: Geometry = { boxW: 34, boxH: 18, grid: 3, gap: 12, pad: 8, titleH: 22, footerH: 34 };

function blockSize(g: Geometry): { w: number; h: number } {
  return { w: 4 * g.boxW + 5 * g.grid, h: 4 * g.boxH + 5 * g.grid };
}

export function canvasSize(g: Geometry): { w: number; h: number } {
  const b = blockSize(g);
  return { w: 2 * g.pad + SLOT_COUNT * b.w + (SLOT_COUNT - 1) * g.gap, h: 2 * g.pad + g.titleH + b.h + g.footerH };
}

export interface BoxRect { ms: number; ss: number; page: number; x: number; y: number; w: number; h: number }

/** Box of (slot, sub-slot, page): slot 0 left, sub-slot 0 left in its block, page 0 at the bottom. */
export function boxRect(g: Geometry, ms: number, ss: number, page: number): BoxRect {
  const b = blockSize(g);
  const bx = g.pad + ms * (b.w + g.gap);
  const by = g.pad + g.titleH;
  const x = bx + g.grid + ss * (g.boxW + g.grid);
  const y = by + g.grid + (3 - page) * (g.boxH + g.grid);
  return { ms, ss, page, x, y, w: g.boxW, h: g.boxH };
}

/** The box under (x, y) in canvas CSS pixels, or null (grid lines, gaps, labels). */
export function hitTest(g: Geometry, x: number, y: number): BoxRect | null {
  for (let ms = 0; ms < 4; ms++) {
    for (let ss = 0; ss < 4; ss++) {
      for (let p = 0; p < 4; p++) {
        const r = boxRect(g, ms, ss, p);
        if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) return r;
      }
    }
  }
  return null;
}

// ── Drawing ────────────────────────────────────────────────────────────────

function currentTheme(): Theme {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

function context2d(canvas: HTMLCanvasElement): CanvasRenderingContext2D | null {
  try {
    return canvas.getContext('2d');
  } catch {
    return null;   // no canvas support (e.g. jsdom)
  }
}

/** Size *canvas* for *g* at the screen's pixel density; returns its context scaled to CSS pixels. */
function prepare(canvas: HTMLCanvasElement, g: Geometry): CanvasRenderingContext2D | null {
  const { w, h } = canvasSize(g);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  const ctx = context2d(canvas);
  if (!ctx) return null;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return ctx;
}

const FONT = 'Consolas, Monaco, "Courier New", monospace';

/** Draw the thumbnail: colours only, no text. */
export function drawThumbnail(canvas: HTMLCanvasElement, cells: SlotCells): void {
  const ctx = prepare(canvas, THUMB);
  if (!ctx) return;
  paintBlocks(ctx, THUMB, cells, false);
}

/** Draw the popup version: labelled boxes, "SLOT n" titles, sub-slot numbers under expanded slots. */
export function drawPopup(canvas: HTMLCanvasElement, cells: SlotCells): void {
  const ctx = prepare(canvas, POPUP);
  if (!ctx) return;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  drawOnto(ctx, cells);
}

/**
 * Grid, then every box: transparent when absent, grid colour when empty, category colour for
 * a device. *detailed* (the popup): device labels, and a 1 px inward outline on empty pages
 * (the thumbnail's 4 px boxes get neither).
 */
function paintBlocks(ctx: CanvasRenderingContext2D, g: Geometry, cells: SlotCells, detailed: boolean): void {
  const theme = currentTheme();
  const b = blockSize(g);
  const grid = colorFor('grid', theme);
  const outline = detailed ? colorFor('empty_outline', theme) : null;
  ctx.font = `10px ${FONT}`;
  for (let ms = 0; ms < 4; ms++) {
    ctx.fillStyle = grid;
    ctx.fillRect(g.pad + ms * (b.w + g.gap), g.pad + g.titleH, b.w, b.h);
    for (let ss = 0; ss < 4; ss++) {
      for (let p = 0; p < 4; p++) {
        const value = cells[cellIndex(ms, ss, p)];
        const r = boxRect(g, ms, ss, p);
        const kind = cellKind(value);
        if (kind === 'absent') {
          ctx.clearRect(r.x, r.y, r.w, r.h);          // transparent: not present
        } else if (kind === 'device') {
          const fill = colorFor(categoryOf(value as string), theme);
          ctx.fillStyle = fill;
          ctx.fillRect(r.x, r.y, r.w, r.h);
          if (detailed) {
            ctx.fillStyle = textColorOn(fill);
            ctx.fillText(value as string, r.x + r.w / 2, r.y + r.h / 2 + 1);
          }
        } else if (outline) {
          // empty page (slot confirmed, nothing mapped): grid colour with a 1 px inward outline
          ctx.fillStyle = outline;
          ctx.fillRect(r.x, r.y, r.w, 1);
          ctx.fillRect(r.x, r.y + r.h - 1, r.w, 1);
          ctx.fillRect(r.x, r.y + 1, 1, r.h - 2);
          ctx.fillRect(r.x + r.w - 1, r.y + 1, 1, r.h - 2);
        }
      }
    }
  }
}

function drawOnto(ctx: CanvasRenderingContext2D, cells: SlotCells): void {
  const g = POPUP;
  const b = blockSize(g);
  const text = getComputedStyle(document.documentElement).getPropertyValue('--color-text').trim() || '#888888';
  paintBlocks(ctx, g, cells, true);
  ctx.fillStyle = text;
  for (let ms = 0; ms < 4; ms++) {
    const bx = g.pad + ms * (b.w + g.gap);
    const by = g.pad + g.titleH;
    ctx.font = `bold 12px ${FONT}`;
    ctx.fillText(`SLOT ${ms}`, bx + b.w / 2, g.pad + g.titleH / 2 - 2);
    if (isExpanded(cells, ms)) {
      ctx.font = `11px ${FONT}`;
      for (let ss = 0; ss < 4; ss++) {
        const r = boxRect(g, ms, ss, 0);
        ctx.fillText(String(ss), r.x + r.w / 2, by + b.h + 9);
      }
      ctx.fillText('subslots', bx + b.w / 2, by + b.h + 25);
    }
  }
}

// ── Thumbnail cache ────────────────────────────────────────────────────────
//
// Rows are rebuilt on every sort / filter; each model's thumbnail is drawn once
// per theme and pixel density and then only copied. Cleared on theme switch.

const thumbCache = new Map<string, HTMLCanvasElement>();

export function clearThumbnailCache(): void {
  thumbCache.clear();
}

/** A canvas showing *cells* as a thumbnail (drawn once per model, theme and density). */
export function thumbnailFor(modelId: number, cells: SlotCells): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.className = 'slotmap-thumb';
  canvas.dataset.modelId = String(modelId);
  paintThumbnail(canvas, modelId, cells);
  return canvas;
}

function paintThumbnail(canvas: HTMLCanvasElement, modelId: number, cells: SlotCells): void {
  const key = `${currentTheme()}|${window.devicePixelRatio || 1}|${modelId}`;
  let source = thumbCache.get(key);
  if (!source) {
    source = document.createElement('canvas');
    drawThumbnail(source, cells);
    thumbCache.set(key, source);
  }
  const ctx = prepare(canvas, THUMB);
  if (ctx) ctx.drawImage(source, 0, 0, canvasSize(THUMB).w, canvasSize(THUMB).h);
}

// ── Popup ──────────────────────────────────────────────────────────────────

export interface SlotmapPopupOptions {
  /** Slot map cells of a model, or null when it has none. */
  cellsOf: (modelId: number) => SlotCells | null;
  /** Heading of the popup ("Sony HB-F1XD"). */
  titleOf: (modelId: number) => string;
  /**
   * Tooltip of one slot map cell of a model ("CS2" → "Cartridge slot 2",
   * "FW" → "Firmware: Painter ROM" with a per-cell detail), or null.
   */
  tooltipOf: (label: string, modelId: number, cellKey: string) => string | null;
}

/** Pixels the popup overlaps the edge of its cell, so no gap opens between them. */
export const POPUP_CELL_OVERLAP = 1;
/** Delay before the popup closes once the pointer has left both the cell and the popup. */
export const POPUP_CLOSE_DELAY_MS = 120;

/**
 * Show the popup while the pointer is over an Overview cell of *root* or over
 * the popup itself; redraw thumbnails and the popup when the theme changes.
 * Returns the popup element.
 */
export function installSlotmapPopup(root: HTMLElement, options: SlotmapPopupOptions): HTMLElement {
  const popup = document.createElement('div');
  popup.className = 'slotmap-popup';
  popup.hidden = true;
  const heading = document.createElement('div');
  heading.className = 'slotmap-popup__title';
  const canvas = document.createElement('canvas');
  canvas.className = 'slotmap-popup__canvas';
  const tip = document.createElement('div');
  tip.className = 'slotmap-popup__tip';
  tip.hidden = true;
  popup.append(heading, canvas, tip);
  document.body.appendChild(popup);

  let modelId: number | null = null;
  let cells: SlotCells | null = null;
  let closeTimer: number | undefined;

  function open(td: HTMLElement): void {
    const id = Number((td.closest('tr') as HTMLElement | null)?.dataset.modelId);
    const found = Number.isFinite(id) ? options.cellsOf(id) : null;
    if (!found) return;
    window.clearTimeout(closeTimer);
    modelId = id;
    cells = found;
    heading.textContent = options.titleOf(id);
    drawPopup(canvas, found);
    tip.hidden = true;
    popup.hidden = false;
    place(td);
  }

  function place(td: HTMLElement): void {
    const cell = td.getBoundingClientRect();
    const w = popup.offsetWidth;
    const h = popup.offsetHeight;
    let left = cell.left;
    // Touch the cell (1px overlap, no gap): the pointer moving into the popup
    // must never cross the next row's Overview cell, which would switch popups.
    let top = cell.bottom - POPUP_CELL_OVERLAP;
    if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - 8 - w);
    if (top + h > window.innerHeight - 8) top = Math.max(8, cell.top + POPUP_CELL_OVERLAP - h);
    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;
  }

  function scheduleClose(): void {
    window.clearTimeout(closeTimer);
    closeTimer = window.setTimeout(close, POPUP_CLOSE_DELAY_MS);
  }

  function close(): void {
    popup.hidden = true;
    tip.hidden = true;
    modelId = null;
    cells = null;
  }

  root.addEventListener('mouseover', (e: MouseEvent) => {
    const td = (e.target as HTMLElement).closest<HTMLElement>('td.cell-slotmap-overview');
    if (td && root.contains(td)) {
      const id = Number((td.closest('tr') as HTMLElement | null)?.dataset.modelId);
      if (popup.hidden || id !== modelId) open(td);
      else window.clearTimeout(closeTimer);
    }
  });
  root.addEventListener('mouseout', (e: MouseEvent) => {
    const td = (e.target as HTMLElement).closest<HTMLElement>('td.cell-slotmap-overview');
    const to = e.relatedTarget as Node | null;
    if (td && !(to && (td.contains(to) || popup.contains(to)))) scheduleClose();
  });
  popup.addEventListener('mouseenter', () => window.clearTimeout(closeTimer));
  popup.addEventListener('mouseleave', (e: MouseEvent) => {
    const to = e.relatedTarget as HTMLElement | null;
    if (!to?.closest?.('td.cell-slotmap-overview')) scheduleClose();
  });

  canvas.addEventListener('mousemove', (e: MouseEvent) => {
    if (!cells) return;
    const rect = canvas.getBoundingClientRect();
    const box = hitTest(POPUP, e.clientX - rect.left, e.clientY - rect.top);
    const value = box ? cells[cellIndex(box.ms, box.ss, box.page)] : null;
    const text = value && box && modelId !== null && cellKind(value) !== 'absent'
      ? options.tooltipOf(value, modelId, slotKey(box.ms, box.ss, box.page)) : null;
    if (!text) {
      tip.hidden = true;
      return;
    }
    tip.textContent = text;
    tip.hidden = false;
    const pr = popup.getBoundingClientRect();
    tip.style.left = `${e.clientX - pr.left + 12}px`;
    tip.style.top = `${e.clientY - pr.top + 14}px`;
  });
  canvas.addEventListener('mouseleave', () => { tip.hidden = true; });

  // Theme switch: drawings depend on the theme's grid colour and page background.
  new MutationObserver(() => {
    clearThumbnailCache();
    root.querySelectorAll<HTMLCanvasElement>('canvas.slotmap-thumb').forEach(c => {
      const id = Number(c.dataset.modelId);
      const found = options.cellsOf(id);
      if (found) paintThumbnail(c, id, found);
    });
    if (!popup.hidden && cells) drawPopup(canvas, cells);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  return popup;
}
