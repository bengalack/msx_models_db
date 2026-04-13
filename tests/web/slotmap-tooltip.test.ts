/**
 * Unit tests for resolveSlotmapTooltip — pure function, no DOM needed.
 */

import { describe, it, expect } from 'vitest';
import { resolveSlotmapTooltip } from '../../src/grid.js';
import { SLOTMAP_ABSENT, SLOTMAP_EMPTY_PAGE } from '../../src/symbols.js';

const STARTER_LUT: Record<string, string> = {
  MAIN: 'MSX BIOS with BASIC ROM',
  SUB: 'Sub ROM',
  KNJ: 'Kanji driver',
  JE: 'MSX-JE',
  FW: 'Firmware',
  DSK: 'Disk ROM',
  MUS: 'MSX Music',
  RS2: 'RS-232C Interface',
  MM: 'Memory Mapper',
  PM: 'Panasonic Mapper',
  RAM: 'RAM (no memory mapper)',
  EXP: 'Expansion Bus',
  CS1: 'Cartridge slot 1',
  CS2: 'Cartridge slot 2',
  CS3: 'Cartridge slot 3',
  CS4: 'Cartridge slot 4',
  [SLOTMAP_ABSENT]: 'Sub-slot absent (not expanded)',
  [SLOTMAP_EMPTY_PAGE]: 'Empty page — no device mapped',
};

describe('resolveSlotmapTooltip', () => {
  describe('known abbreviations', () => {
    it('returns tooltip for MAIN', () => {
      expect(resolveSlotmapTooltip('MAIN', STARTER_LUT)).toBe('MSX BIOS with BASIC ROM');
    });

    it('returns tooltip for SUB', () => {
      expect(resolveSlotmapTooltip('SUB', STARTER_LUT)).toBe('Sub ROM');
    });

    it('returns tooltip for DSK', () => {
      expect(resolveSlotmapTooltip('DSK', STARTER_LUT)).toBe('Disk ROM');
    });

    it('returns all starter LUT entries without null', () => {
      for (const [abbr, tooltip] of Object.entries(STARTER_LUT)) {
        expect(resolveSlotmapTooltip(abbr, STARTER_LUT)).toBe(tooltip);
      }
    });
  });

  describe(`${SLOTMAP_ABSENT} absent sentinel (U+2327)`, () => {
    it(`returns tooltip for ${SLOTMAP_ABSENT}`, () => {
      expect(resolveSlotmapTooltip(SLOTMAP_ABSENT, STARTER_LUT)).toBe('Sub-slot absent (not expanded)');
    });
  });

  describe(`${SLOTMAP_EMPTY_PAGE} empty sentinel (U+2334)`, () => {
    it(`returns tooltip for ${SLOTMAP_EMPTY_PAGE}`, () => {
      expect(resolveSlotmapTooltip(SLOTMAP_EMPTY_PAGE, STARTER_LUT)).toBe('Empty page \u2014 no device mapped');
    });
  });

  describe('mirror cells (abbr*)', () => {
    it('returns "Sub ROM (mirror)" for SUB*', () => {
      expect(resolveSlotmapTooltip('SUB*', STARTER_LUT)).toBe('Sub ROM (mirror)');
    });

    it('returns "MSX BIOS with BASIC ROM (mirror)" for MAIN*', () => {
      expect(resolveSlotmapTooltip('MAIN*', STARTER_LUT)).toBe('MSX BIOS with BASIC ROM (mirror)');
    });

    it('returns "Cartridge slot 1 (mirror)" for CS1*', () => {
      expect(resolveSlotmapTooltip('CS1*', STARTER_LUT)).toBe('Cartridge slot 1 (mirror)');
    });

    it('returns null for bare * (empty base)', () => {
      expect(resolveSlotmapTooltip('*', STARTER_LUT)).toBeNull();
    });
  });

  describe('unknown / unmatched values', () => {
    it('returns tooltip for CS1', () => {
      expect(resolveSlotmapTooltip('CS1', STARTER_LUT)).toBe('Cartridge slot 1');
    });

    it('returns tooltip for CS2', () => {
      expect(resolveSlotmapTooltip('CS2', STARTER_LUT)).toBe('Cartridge slot 2');
    });

    it('returns null for raw unknown device tag', () => {
      expect(resolveSlotmapTooltip('SomeChip', STARTER_LUT)).toBeNull();
    });
  });

  describe('empty LUT', () => {
    it('returns null for any value when LUT is empty', () => {
      expect(resolveSlotmapTooltip('MAIN', {})).toBeNull();
      expect(resolveSlotmapTooltip(SLOTMAP_ABSENT, {})).toBeNull();
      expect(resolveSlotmapTooltip(SLOTMAP_EMPTY_PAGE, {})).toBeNull();
      expect(resolveSlotmapTooltip('SUB*', {})).toBeNull();
    });
  });
});
