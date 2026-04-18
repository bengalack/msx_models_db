/**
 * Tests for the column picker panel (col-picker).
 *
 * Key behaviour under test:
 *   - The Identity group (Manufacturer, Model) is excluded from the picker
 *     panel. main.ts filters it out before calling buildColPicker, so the
 *     panel must not render a section for it.
 *   - All other groups and their columns are listed with checkboxes.
 */

import { describe, it, expect } from 'vitest';
import { buildColPicker } from '../../src/col-picker.js';
import type { ColumnDef, GroupDef } from '../../src/types.js';

// ── Minimal test fixture ───────────────────────────────────────────────────

const allGroups: GroupDef[] = [
  { id: 0, key: 'identity', label: 'Identity', order: 0 },
  { id: 1, key: 'specs',    label: 'Specs',    order: 1 },
  { id: 2, key: 'media',    label: 'Media',    order: 2 },
];

const allColumns: ColumnDef[] = [
  { id: 1, key: 'manufacturer', label: 'Manufacturer', groupId: 0, type: 'string' },
  { id: 2, key: 'model',        label: 'Model',        groupId: 0, type: 'string' },
  { id: 3, key: 'year',         label: 'Year',         groupId: 1, type: 'number' },
  { id: 4, key: 'ram',          label: 'RAM',          groupId: 1, type: 'number' },
  { id: 5, key: 'floppy',       label: 'Floppy',       groupId: 2, type: 'string' },
];

/** Simulate what main.ts does: strip the identity group before building the picker. */
function buildPickerWithoutIdentity() {
  const identityId = allGroups.find(g => g.key === 'identity')?.id;
  const groups  = allGroups.filter(g  => g.id      !== identityId);
  const columns = allColumns.filter(c => c.groupId !== identityId);
  return buildColPicker(groups, columns, () => new Set<number>(), () => {});
}

// ── Helpers ────────────────────────────────────────────────────────────────

function groupSections(panel: HTMLElement): HTMLElement[] {
  return Array.from(panel.querySelectorAll<HTMLElement>('.col-picker__group'));
}

function groupLabels(panel: HTMLElement): string[] {
  return Array.from(panel.querySelectorAll<HTMLElement>('.col-picker__group-label'))
    .map(el => el.textContent ?? '');
}

function checkboxLabels(panel: HTMLElement): string[] {
  return Array.from(panel.querySelectorAll<HTMLElement>('.col-picker__item'))
    .map(el => el.textContent?.trim() ?? '');
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('col-picker — Identity group exclusion', () => {
  it('does not render a section for the Identity group', () => {
    const { element } = buildPickerWithoutIdentity();
    expect(groupLabels(element)).not.toContain('Identity');
  });

  it('does not list Manufacturer in the picker', () => {
    const { element } = buildPickerWithoutIdentity();
    expect(checkboxLabels(element)).not.toContain('Manufacturer');
  });

  it('does not list Model in the picker', () => {
    const { element } = buildPickerWithoutIdentity();
    expect(checkboxLabels(element)).not.toContain('Model');
  });

  it('renders sections for all non-identity groups', () => {
    const { element } = buildPickerWithoutIdentity();
    const labels = groupLabels(element);
    expect(labels).toContain('Specs');
    expect(labels).toContain('Media');
    expect(groupSections(element).length).toBe(2);
  });

  it('lists all non-identity columns with checkboxes', () => {
    const { element } = buildPickerWithoutIdentity();
    const labels = checkboxLabels(element);
    expect(labels).toContain('Year');
    expect(labels).toContain('RAM');
    expect(labels).toContain('Floppy');
    expect(labels.length).toBe(3);
  });

  it('renders no sections at all when only identity columns are passed', () => {
    const identityId = allGroups.find(g => g.key === 'identity')!.id;
    // Pass only the identity group — after exclusion, nothing should render
    const groups  = allGroups.filter(g  => g.id      !== identityId);
    const columns = allColumns.filter(c => c.groupId !== identityId && c.groupId !== 1 && c.groupId !== 2);
    const { element } = buildColPicker(groups, columns, () => new Set<number>(), () => {});
    expect(groupSections(element).length).toBe(0);
  });
});
