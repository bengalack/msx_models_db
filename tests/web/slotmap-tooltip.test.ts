/**
 * Unit tests for resolveSlotmapTooltip — pure function, no DOM needed.
 */

import { describe, it, expect } from 'vitest';
import { resolveSlotmapTooltip } from '../../src/grid.js';

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
  '\u2327': 'Sub-slot absent (not expanded)',
  '\u2022': 'Empty page — no device mapped',
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

  describe('⌧ absent sentinel (U+2327)', () => {
    it('returns tooltip for ⌧', () => {
      expect(resolveSlotmapTooltip('\u2327', STARTER_LUT)).toBe('Sub-slot absent (not expanded)');
    });
  });

  describe('• empty sentinel (U+2022)', () => {
    it('returns tooltip for •', () => {
      expect(resolveSlotmapTooltip('\u2022', STARTER_LUT)).toBe('Empty page — no device mapped');
    });
  });

  describe('mirror cells (abbr*)', () => {
    it('returns "Sub ROM (mirror)" for SUB*', () => {
      expect(resolveSlotmapTooltip('SUB*', STARTER_LUT)).toBe('Sub ROM (mirror)');
    });

    it('returns "MSX BIOS with BASIC ROM (mirror)" for MAIN*', () => {
      expect(resolveSlotmapTooltip('MAIN*', STARTER_LUT)).toBe('MSX BIOS with BASIC ROM (mirror)');
    });

    it('returns null for mirror with unknown base', () => {
      expect(resolveSlotmapTooltip('CS1*', STARTER_LUT)).toBeNull();
    });

    it('returns null for bare * (empty base)', () => {
      expect(resolveSlotmapTooltip('*', STARTER_LUT)).toBeNull();
    });
  });

  describe('unknown / unmatched values', () => {
    it('returns null for CS1 (not in starter LUT)', () => {
      expect(resolveSlotmapTooltip('CS1', STARTER_LUT)).toBeNull();
    });

    it('returns null for CS2', () => {
      expect(resolveSlotmapTooltip('CS2', STARTER_LUT)).toBeNull();
    });

    it('returns null for raw unknown device tag', () => {
      expect(resolveSlotmapTooltip('SomeChip', STARTER_LUT)).toBeNull();
    });
  });

  describe('empty LUT', () => {
    it('returns null for any value when LUT is empty', () => {
      expect(resolveSlotmapTooltip('MAIN', {})).toBeNull();
      expect(resolveSlotmapTooltip('\u2327', {})).toBeNull();
      expect(resolveSlotmapTooltip('\u2022', {})).toBeNull();
      expect(resolveSlotmapTooltip('SUB*', {})).toBeNull();
    });
  });
});
