/**
 * Slot-map display symbols, loaded from data/scraper-config.json.
 *
 * Mirrors the Python scraper/symbols.py module so that TypeScript code
 * and tests never hard-code Unicode codepoints directly.
 */

import config from '../data/scraper-config.json';

const syms = config.slotmap_symbols;

export const SLOTMAP_ABSENT:         string = syms.absent;
export const SLOTMAP_EMPTY_PAGE:     string = syms.empty_page;
export const SLOTMAP_MIRROR_SUFFIX:  string = syms.mirror_suffix;
export const SLOTMAP_SUBSLOT_SUFFIX: string = syms.subslot_suffix;
