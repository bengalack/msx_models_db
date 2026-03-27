import type { MSXData, GroupDef, ColumnDef, ModelRecord } from './types.js';

function cellText(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined || value === '') return '\u2014'; // em dash
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

function isNullish(value: string | number | boolean | null | undefined): boolean {
  return value === null || value === undefined || value === '';
}

function buildGroupHeaderRow(groups: GroupDef[], columns: ColumnDef[]): HTMLTableRowElement {
  const tr = document.createElement('tr');

  // Gutter corner cell
  const gutterCorner = document.createElement('th');
  gutterCorner.className = 'gutter';
  gutterCorner.rowSpan = 3; // spans group header, col header, and filter rows
  tr.appendChild(gutterCorner);

  // One th per group, spanning its columns
  for (const group of [...groups].sort((a, b) => a.order - b.order)) {
    const groupCols = columns.filter(c => c.groupId === group.id);
    if (groupCols.length === 0) continue;

    const th = document.createElement('th');
    th.className = 'group-header';
    th.colSpan = groupCols.length;
    th.scope = 'colgroup';
    th.dataset.groupId = String(group.id);
    th.dataset.colCount = String(groupCols.length);

    const label = document.createTextNode(group.label);
    const chevron = document.createElement('i');
    chevron.className = 'chevron';
    chevron.setAttribute('aria-hidden', 'true');
    chevron.textContent = '\u25bc'; // ▼

    th.appendChild(label);
    th.appendChild(chevron);
    tr.appendChild(th);
  }

  return tr;
}

function buildColHeaderRow(columns: ColumnDef[]): HTMLTableRowElement {
  const tr = document.createElement('tr');
  const groupOrder = new Map<number, number>();
  columns.forEach((col, colIndex) => {
    const th = document.createElement('th');
    th.className = 'col-header';
    th.scope = 'col';
    th.textContent = col.label;
    th.dataset.colGroup = String(col.groupId);
    th.dataset.colIndex = String(colIndex);
    const order = groupOrder.get(col.groupId) ?? 0;
    th.dataset.colOrder = String(order);
    groupOrder.set(col.groupId, order + 1);
    tr.appendChild(th);
  });
  return tr;
}

function sortModels(
  models: ModelRecord[],
  colIndex: number,
  direction: 'asc' | 'desc'
): ModelRecord[] {
  return [...models].sort((a, b) => {
    const av = colIndex < a.values.length ? a.values[colIndex] : null;
    const bv = colIndex < b.values.length ? b.values[colIndex] : null;
    // null always last, regardless of direction
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    let cmp: number;
    if (typeof av === 'number' && typeof bv === 'number') {
      cmp = av - bv;
    } else if (typeof av === 'boolean' && typeof bv === 'boolean') {
      cmp = av === bv ? 0 : av ? 1 : -1;
    } else {
      cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: 'base' });
    }
    return direction === 'asc' ? cmp : -cmp;
  });
}

function buildFilterRow(columns: ColumnDef[]): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.className = 'filter-row';
  const groupOrder = new Map<number, number>();
  for (let i = 0; i < columns.length; i++) {
    const td = document.createElement('td');
    td.dataset.colGroup = String(columns[i].groupId);
    td.dataset.colIndex = String(i);
    const order = groupOrder.get(columns[i].groupId) ?? 0;
    td.dataset.colOrder = String(order);
    groupOrder.set(columns[i].groupId, order + 1);

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'filter-input';
    input.placeholder = '…';
    input.dataset.colIndex = String(i);
    input.setAttribute('aria-label', `Filter ${columns[i].label}`);

    const clearBtn = document.createElement('button');
    clearBtn.className = 'filter-clear filter-clear--hidden';
    clearBtn.setAttribute('aria-label', 'Clear filter');
    clearBtn.tabIndex = -1;
    clearBtn.textContent = '×';

    td.appendChild(input);
    td.appendChild(clearBtn);
    tr.appendChild(td);
  }
  return tr;
}

function buildDataRow(model: ModelRecord, columns: ColumnDef[], rowIndex: number): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.dataset.modelId = String(model.id);

  // Gutter — 1-based row number
  const gutter = document.createElement('td');
  gutter.className = 'gutter';
  gutter.textContent = String(rowIndex);
  gutter.dataset.modelId = String(model.id);
  tr.appendChild(gutter);

  const groupOrder = new Map<number, number>();
  for (let i = 0; i < columns.length; i++) {
    const rawValue = i < model.values.length ? model.values[i] : null;
    const td = document.createElement('td');
    const text = cellText(rawValue);
    td.textContent = text;
    td.dataset.colGroup = String(columns[i].groupId);
    td.dataset.colIndex = String(i);
    const order = groupOrder.get(columns[i].groupId) ?? 0;
    td.dataset.colOrder = String(order);
    groupOrder.set(columns[i].groupId, order + 1);

    if (isNullish(rawValue)) {
      td.classList.add('cell-null');
    } else {
      // Only set title when value is present — avoids "—" tooltip
      td.title = text;
    }

    tr.appendChild(td);
  }

  return tr;
}

function buildGapIndicator(
  hiddenIds: number[],
  colCount: number,
  onUnhide: (ids: number[]) => void,
): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.className = 'row-gap-indicator';
  const td = document.createElement('td');
  td.colSpan = colCount + 1; // gutter + all columns
  const btn = document.createElement('button');
  btn.className = 'row-gap-indicator__btn';
  btn.setAttribute('aria-label', `Show ${hiddenIds.length} hidden row${hiddenIds.length > 1 ? 's' : ''}`);
  btn.textContent = '\u25bc\u25b2'; // ▼▲
  btn.addEventListener('click', () => onUnhide(hiddenIds));
  td.appendChild(btn);
  tr.appendChild(td);
  return tr;
}

export function buildGrid(data: MSXData): {
  element: HTMLElement;
  toggleFilters: () => void;
  setColumnVisible: (colIdx: number, visible: boolean) => void;
  getHiddenCols: () => ReadonlySet<number>;
  getHiddenRows: () => ReadonlySet<number>;
  hideRow: (modelId: number) => void;
  getSelectedCells: () => ReadonlySet<string>;
} {
  const wrap = document.createElement('div');
  wrap.className = 'grid-wrap';

  const table = document.createElement('table');
  table.className = 'grid';

  // Tracks which group IDs are currently collapsed
  const collapsedGroups = new Set<number>();

  // Sort state
  const originalModels = [...data.models];
  let sortColIndex: number | null = null;
  let sortDirection: 'asc' | 'desc' = 'asc';

  // Filter state — keyed by 0-based column index
  const filters = new Map<number, string>();

  // Hidden columns — keyed by 0-based column index
  const hiddenCols = new Set<number>();

  // Hidden rows — keyed by stable model ID
  const hiddenRows = new Set<number>();

  // ── Selection state ──────────────────────────────────────────────────────
  // Key format: "${modelId}:${colIdx}"
  const selectedCells = new Set<string>();
  let selAnchor: { modelId: number; colIdx: number } | null = null;
  let isDragging = false;
  let dragStart: { modelId: number; colIdx: number } | null = null;

  function selKey(modelId: number, colIdx: number): string {
    return `${modelId}:${colIdx}`;
  }

  function applySelectionToDOM(): void {
    tbody.querySelectorAll<HTMLTableCellElement>('td[data-col-index]').forEach(td => {
      const tr = td.closest<HTMLTableRowElement>('tr[data-model-id]');
      if (!tr?.dataset.modelId) return;
      td.classList.toggle(
        'cell--selected',
        selectedCells.has(selKey(Number(tr.dataset.modelId), Number(td.dataset.colIndex)))
      );
    });
  }

  function clearSelection(): void {
    selectedCells.clear();
    selAnchor = null;
    applySelectionToDOM();
  }

  function selectRectangle(
    a: { modelId: number; colIdx: number },
    b: { modelId: number; colIdx: number }
  ): void {
    const visibleModelIds = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]'))
      .map(tr => Number(tr.dataset.modelId));
    const visibleColIdxs = data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i));

    const ar = visibleModelIds.indexOf(a.modelId);
    const br = visibleModelIds.indexOf(b.modelId);
    const ac = visibleColIdxs.indexOf(a.colIdx);
    const bc = visibleColIdxs.indexOf(b.colIdx);

    selectedCells.clear();
    if (ar === -1 || br === -1 || ac === -1 || bc === -1) {
      // Anchor or target not in visible set — fall back to single cell
      selectedCells.add(selKey(b.modelId, b.colIdx));
      selAnchor = b;
      return;
    }
    const minR = Math.min(ar, br); const maxR = Math.max(ar, br);
    const minC = Math.min(ac, bc); const maxC = Math.max(ac, bc);
    for (let r = minR; r <= maxR; r++) {
      for (let c = minC; c <= maxC; c++) {
        selectedCells.add(selKey(visibleModelIds[r], visibleColIdxs[c]));
      }
    }
  }

  function getSelectedCells(): ReadonlySet<string> {
    return selectedCells;
  }

  // ── thead ────────────────────────────────────────────────────────────────
  const thead = document.createElement('thead');
  thead.appendChild(buildGroupHeaderRow(data.groups, data.columns));
  thead.appendChild(buildColHeaderRow(data.columns));
  thead.appendChild(buildFilterRow(data.columns));
  table.appendChild(thead);

  // Gutter corner (rowSpan=3) used for the filtered indicator
  const gutterCorner = thead.rows[0].cells[0] as HTMLTableCellElement;

  function updateGutterIndicator(): void {
    if (filters.size > 0) {
      gutterCorner.classList.add('gutter--filtered');
      gutterCorner.title = 'Some rows are filtered out';
    } else {
      gutterCorner.classList.remove('gutter--filtered');
      gutterCorner.title = '';
    }
  }

  function recalcGroupHeader(groupId: number): void {
    const th = thead.querySelector<HTMLTableCellElement>(`th.group-header[data-group-id="${groupId}"]`);
    if (!th) return;
    const groupCols = data.columns.map((c, i) => ({ col: c, idx: i })).filter(({ col }) => col.groupId === groupId);
    const hiddenInGroup = groupCols.filter(({ idx }) => hiddenCols.has(idx)).length;
    const totalCols = groupCols.length;
    const visibleCount = totalCols - hiddenInGroup;

    if (collapsedGroups.has(groupId)) {
      // Collapsed: colSpan is always 1 while collapsed; indicator still applies
      th.classList.toggle('group-header--partial', hiddenInGroup > 0);
    } else if (visibleCount === 0) {
      th.style.display = 'none';
      th.classList.remove('group-header--partial');
    } else {
      th.style.display = '';
      th.colSpan = visibleCount;
      th.classList.toggle('group-header--partial', hiddenInGroup > 0);
    }
  }

  function setColumnVisible(colIdx: number, visible: boolean): void {
    if (visible) {
      hiddenCols.delete(colIdx);
    } else {
      hiddenCols.add(colIdx);
    }
    // Apply to all already-rendered cells for this column (thead + current tbody rows)
    table.querySelectorAll<HTMLElement>(`[data-col-index="${colIdx}"]`).forEach(cell => {
      cell.style.display = visible ? '' : 'none';
    });
    const groupId = data.columns[colIdx]?.groupId;
    if (groupId !== undefined) recalcGroupHeader(groupId);
    renderRows();
  }

  function getHiddenCols(): ReadonlySet<number> {
    return hiddenCols;
  }

  function hideRow(modelId: number): void {
    hiddenRows.add(modelId);
    renderRows();
  }

  function unhideRowsInGap(modelIds: number[]): void {
    modelIds.forEach(id => hiddenRows.delete(id));
    renderRows();
  }

  function getHiddenRows(): ReadonlySet<number> {
    return hiddenRows;
  }

  // ── tbody ────────────────────────────────────────────────────────────────
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  function renderRows(): void {
    const sorted = sortColIndex !== null
      ? sortModels(originalModels, sortColIndex, sortDirection)
      : originalModels;
    const filtered = filters.size === 0 ? sorted : sorted.filter(model =>
      [...filters.entries()].every(([colIdx, term]) => {
        const raw = colIdx < model.values.length ? model.values[colIdx] : null;
        return cellText(raw).toLowerCase().includes(term.toLowerCase());
      })
    );
    // Gap-walk: emit data rows and gap indicator rows
    const rows: HTMLTableRowElement[] = [];
    let buffer: number[] = [];
    let rowNum = 1;
    for (const model of filtered) {
      if (hiddenRows.has(model.id)) {
        buffer.push(model.id);
      } else {
        if (buffer.length > 0) {
          rows.push(buildGapIndicator(buffer, data.columns.length, unhideRowsInGap));
          buffer = [];
        }
        rows.push(buildDataRow(model, data.columns, rowNum++));
      }
    }
    if (buffer.length > 0) {
      rows.push(buildGapIndicator(buffer, data.columns.length, unhideRowsInGap));
    }
    tbody.replaceChildren(...rows);
    // Re-apply collapsed group visibility to newly rendered rows
    collapsedGroups.forEach(groupId => {
      tbody.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
        if (cell.dataset.colOrder === '0') {
          cell.classList.add('col-group-stub');
        } else {
          cell.style.display = 'none';
        }
      });
    });
    // Re-apply individually hidden columns to newly rendered rows
    hiddenCols.forEach(colIdx => {
      tbody.querySelectorAll<HTMLElement>(`[data-col-index="${colIdx}"]`).forEach(cell => {
        cell.style.display = 'none';
      });
    });
    // Re-apply selection highlights
    applySelectionToDOM();
  }

  renderRows();

  // ── Gutter context menu (event delegation on tbody) ──────────────────────
  let activeMenu: HTMLElement | null = null;

  function closeContextMenu(): void {
    if (activeMenu) {
      activeMenu.remove();
      activeMenu = null;
    }
  }

  tbody.addEventListener('contextmenu', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    const gutterCell = target.closest<HTMLElement>('td.gutter');
    if (!gutterCell) return;
    const modelId = Number(gutterCell.dataset.modelId);
    if (!modelId) return;
    e.preventDefault();
    closeContextMenu();

    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.setAttribute('role', 'menu');
    const btn = document.createElement('button');
    btn.className = 'ctx-menu__item';
    btn.setAttribute('role', 'menuitem');
    btn.textContent = 'Hide row';
    btn.addEventListener('click', () => {
      closeContextMenu();
      hideRow(modelId);
    });
    menu.appendChild(btn);

    // Position at cursor
    menu.style.left = `${e.clientX}px`;
    menu.style.top = `${e.clientY}px`;
    document.body.appendChild(menu);
    activeMenu = menu;
    btn.focus();
  });

  document.addEventListener('mousedown', (e: MouseEvent) => {
    if (activeMenu && !activeMenu.contains(e.target as Node)) {
      closeContextMenu();
    }
  });

  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (activeMenu) {
        closeContextMenu();
      } else {
        clearSelection();
      }
    }
  });

  // ── Cell selection (event delegation on tbody) ───────────────────────────
  tbody.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    const td = target.closest<HTMLTableCellElement>('td[data-col-index]');
    if (!td) return;
    const tr = td.closest<HTMLTableRowElement>('tr[data-model-id]');
    if (!tr?.dataset.modelId) return; // gutter or gap indicator rows won't match

    e.preventDefault(); // prevent browser text-selection on drag

    const modelId = Number(tr.dataset.modelId);
    const colIdx = Number(td.dataset.colIndex);
    const cell = { modelId, colIdx };

    if (e.ctrlKey || e.metaKey) {
      // Toggle cell in/out of selection
      const key = selKey(modelId, colIdx);
      if (selectedCells.has(key)) {
        selectedCells.delete(key);
      } else {
        selectedCells.add(key);
      }
      selAnchor = cell;
      applySelectionToDOM();
    } else if (e.shiftKey) {
      // Extend rectangle from anchor to clicked cell
      if (selAnchor) {
        selectRectangle(selAnchor, cell);
      } else {
        // No anchor yet — treat like plain click
        selectedCells.clear();
        selectedCells.add(selKey(modelId, colIdx));
        selAnchor = cell;
      }
      applySelectionToDOM();
    } else {
      // Plain click — select single cell, start potential drag
      selectedCells.clear();
      selectedCells.add(selKey(modelId, colIdx));
      selAnchor = cell;
      isDragging = true;
      dragStart = cell;
      applySelectionToDOM();
    }
  });

  // ── Drag selection (mouseenter + mouseup) ───────────────────────────────
  tbody.addEventListener('mouseenter', (e: MouseEvent) => {
    if (!isDragging || e.buttons !== 1 || !dragStart) return;
    const target = e.target as HTMLElement;
    const td = target.closest<HTMLTableCellElement>('td[data-col-index]');
    if (!td) return;
    const tr = td.closest<HTMLTableRowElement>('tr[data-model-id]');
    if (!tr?.dataset.modelId) return;

    const modelId = Number(tr.dataset.modelId);
    const colIdx = Number(td.dataset.colIndex);
    selectRectangle(dragStart, { modelId, colIdx });
    applySelectionToDOM();
  }, true); // capture to catch all child mouseenter events

  document.addEventListener('mouseup', () => {
    isDragging = false;
    dragStart = null;
  });

  // ── Group collapse / expand ──────────────────────────────────────────────
  const groupHeaders = thead.querySelectorAll<HTMLTableCellElement>('th.group-header');
  groupHeaders.forEach(th => {
    th.addEventListener('click', () => {
      const groupId = Number(th.dataset.groupId);
      const chevron = th.querySelector<HTMLElement>('.chevron')!;

      if (collapsedGroups.has(groupId)) {
        // Expand — restore all cells except those individually hidden
        collapsedGroups.delete(groupId);
        th.classList.remove('collapsed');
        chevron.textContent = '\u25bc'; // ▼
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          const cellColIdx = cell.dataset.colIndex !== undefined ? Number(cell.dataset.colIndex) : -1;
          if (hiddenCols.has(cellColIdx)) return; // leave individually-hidden cells hidden
          cell.style.display = '';
          cell.classList.remove('col-group-stub');
        });
        recalcGroupHeader(groupId);
      } else {
        // Collapse — keep first cell per row as a zero-width stub anchor;
        // hide all others so the group header colSpan=1 aligns correctly.
        collapsedGroups.add(groupId);
        th.colSpan = 1;
        th.classList.add('collapsed');
        chevron.textContent = '\u25b6'; // ▶
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          if (cell.dataset.colOrder === '0') {
            cell.classList.add('col-group-stub');
          } else {
            cell.style.display = 'none';
          }
        });
        recalcGroupHeader(groupId);
      }
    });
  });

  // ── Column sort ──────────────────────────────────────────────────────────
  const colHeaders = thead.querySelectorAll<HTMLTableCellElement>('th.col-header');
  colHeaders.forEach(th => {
    th.addEventListener('click', () => {
      const clickedIndex = Number(th.dataset.colIndex);
      // Determine next sort state
      if (sortColIndex !== clickedIndex) {
        sortColIndex = clickedIndex;
        sortDirection = 'asc';
      } else if (sortDirection === 'asc') {
        sortDirection = 'desc';
      } else {
        sortColIndex = null;
      }
      // Update indicator classes on all col-headers
      colHeaders.forEach(h => {
        h.classList.remove('col-header--sort-asc', 'col-header--sort-desc');
      });
      if (sortColIndex !== null) {
        th.classList.add(sortDirection === 'asc' ? 'col-header--sort-asc' : 'col-header--sort-desc');
      }
      renderRows();
    });
  });

  // ── Column filter inputs ──────────────────────────────────────────────
  thead.querySelectorAll<HTMLInputElement>('input.filter-input').forEach(input => {
    input.addEventListener('input', () => {
      const colIdx = Number(input.dataset.colIndex);
      const val = input.value.trim();
      if (val) {
        filters.set(colIdx, val);
        input.classList.add('filter-input--active');
        const clearBtn = input.nextElementSibling as HTMLElement | null;
        clearBtn?.classList.remove('filter-clear--hidden');
      } else {
        filters.delete(colIdx);
        input.classList.remove('filter-input--active');
        const clearBtn = input.nextElementSibling as HTMLElement | null;
        clearBtn?.classList.add('filter-clear--hidden');
      }
      updateGutterIndicator();
      renderRows();
    });
  });

  thead.querySelectorAll<HTMLButtonElement>('button.filter-clear').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.previousElementSibling as HTMLInputElement | null;
      if (!input) return;
      input.value = '';
      const colIdx = Number(input.dataset.colIndex);
      filters.delete(colIdx);
      input.classList.remove('filter-input--active');
      btn.classList.add('filter-clear--hidden');
      updateGutterIndicator();
      renderRows();
    });
  });

  // ── Toggle filter row ───────────────────────────────────────────────
  const filterRow = thead.querySelector<HTMLTableRowElement>('.filter-row')!;

  function toggleFilters(): void {
    const isVisible = filterRow.style.display === 'table-row';
    if (isVisible) {
      // Hide and clear all filters
      filterRow.style.display = 'none';
      filters.clear();
      thead.querySelectorAll<HTMLInputElement>('input.filter-input').forEach(inp => {
        inp.value = '';
        inp.classList.remove('filter-input--active');
        (inp.nextElementSibling as HTMLElement | null)?.classList.add('filter-clear--hidden');
      });
      updateGutterIndicator();
      renderRows();
    } else {
      filterRow.style.display = 'table-row';
    }
  }

  wrap.appendChild(table);
  return { element: wrap, toggleFilters, setColumnVisible, getHiddenCols, getHiddenRows, hideRow, getSelectedCells };
}
