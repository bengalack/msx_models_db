import type { ColumnDef, GroupDef } from './types.js';

export interface ColPicker {
  element: HTMLElement;
  open: () => void;
  close: () => void;
}

export function buildColPicker(
  groups: GroupDef[],
  columns: ColumnDef[],
  getHiddenCols: () => ReadonlySet<number>,
  onToggle: (colIdx: number, visible: boolean) => void,
): ColPicker {
  const panel = document.createElement('div');
  panel.className = 'col-picker';
  panel.hidden = true;

  const sortedGroups = [...groups].sort((a, b) => a.order - b.order);

  // Build one section per group
  const checkboxes = new Map<number, HTMLInputElement>();

  for (const group of sortedGroups) {
    const groupCols = columns
      .map((col, idx) => ({ col, idx }))
      .filter(({ col }) => col.groupId === group.id);
    if (groupCols.length === 0) continue;

    const section = document.createElement('div');
    section.className = 'col-picker__group';

    const groupLabel = document.createElement('div');
    groupLabel.className = 'col-picker__group-label';
    groupLabel.textContent = group.label;
    section.appendChild(groupLabel);

    for (const { col, idx } of groupCols) {
      const label = document.createElement('label');
      label.className = 'col-picker__item';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.colIndex = String(idx);
      cb.addEventListener('change', () => {
        onToggle(idx, cb.checked);
      });

      checkboxes.set(idx, cb);
      label.appendChild(cb);
      label.appendChild(document.createTextNode(col.label));
      section.appendChild(label);
    }

    panel.appendChild(section);
  }

  // Close on Escape
  panel.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      close();
    }
  });

  function open(): void {
    // Sync checkbox states from current hidden set
    const hidden = getHiddenCols();
    checkboxes.forEach((cb, colIdx) => {
      cb.checked = !hidden.has(colIdx);
    });
    panel.hidden = false;
  }

  function close(): void {
    panel.hidden = true;
  }

  return { element: panel, open, close };
}
