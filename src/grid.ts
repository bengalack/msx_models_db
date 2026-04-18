import type { MSXData, GroupDef, ColumnDef, ModelRecord, ViewState } from './types.js';

/** Number of leading data columns (0-based) that are pinned during horizontal scroll. */
export const FROZEN_COL_COUNT = 2;

/** Width of the row-number gutter in pixels — must match .gutter { width } in grid.css. */
const GUTTER_WIDTH = 52;

// Normalize (sort) comma-separated string values (e.g., for Conn/Ports)
function normalizeCommaList(value: string): string {
  // Split by comma, trim, sort, and join
  return value
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .join(', ');
}

function cellText(value: string | number | boolean | null | undefined, col?: ColumnDef): string {
  if (value === null || value === undefined || value === '') return '\u2014'; // em dash
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  // Normalize Conn/Ports column for display
  if (col && col.key === 'connectivity' && typeof value === 'string') {
    return normalizeCommaList(value);
  }
  return String(value);
}

function isNullish(value: string | number | boolean | null | undefined): boolean {
  return value === null || value === undefined || value === '';
}

/**
 * Resolve a slot map cell value to its tooltip string, or null if no tooltip.
 *
 * Rules:
 *   - Exact key in lut (including "☒") → lut[value]
 *   - value ends with "*" → look up base (strip "*"); if found → "<base tooltip> (mirror)"
 *   - Not in lut and not a mirror → null (no tooltip)
 */
export function resolveSlotmapTooltip(
  value: string,
  lut: Record<string, string>,
): string | null {
  if (Object.prototype.hasOwnProperty.call(lut, value)) {
    return lut[value];
  }
  if (value.endsWith('*')) {
    const base = value.slice(0, -1);
    if (Object.prototype.hasOwnProperty.call(lut, base)) {
      return `${lut[base]} (mirror)`;
    }
  }
  return null;
}

function buildGroupHeaderRow(groups: GroupDef[], columns: ColumnDef[]): HTMLTableRowElement {
  const tr = document.createElement('tr');

  // Gutter corner cell
  const gutterCorner = document.createElement('th');
  gutterCorner.className = 'gutter';
  gutterCorner.rowSpan = 3; // spans group header, col header, and filter rows
  tr.appendChild(gutterCorner);

  // Build a map of groupId → first column index in the columns array
  const groupStartIdx = new Map<number, number>();
  columns.forEach((col, idx) => {
    if (!groupStartIdx.has(col.groupId)) groupStartIdx.set(col.groupId, idx);
  });

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

    // Freeze group header if ALL its columns fall within the frozen range
    const startIdx = groupStartIdx.get(group.id) ?? 0;
    if (startIdx + groupCols.length <= FROZEN_COL_COUNT) {
      th.classList.add('group-header--frozen');
    }

    const label = document.createTextNode(group.label);
    const filterIcon = document.createElement('i');
    filterIcon.className = 'fas fa-filter filter-indicator';
    filterIcon.setAttribute('aria-hidden', 'true');
    const chevron = document.createElement('i');
    chevron.className = 'chevron fas fa-chevron-down';
    chevron.setAttribute('aria-hidden', 'true');

    th.appendChild(label);
    th.appendChild(filterIcon);
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
    const span = document.createElement('span');
    span.className = 'col-header__text';
    span.textContent = col.shortLabel ?? col.label;
    th.appendChild(span);
    th.title = col.tooltip ?? col.label;
    th.dataset.colGroup = String(col.groupId);
    th.dataset.colIndex = String(colIndex);
    const order = groupOrder.get(col.groupId) ?? 0;
    th.dataset.colOrder = String(order);
    groupOrder.set(col.groupId, order + 1);
    if (colIndex < FROZEN_COL_COUNT) th.classList.add('col--frozen');
    tr.appendChild(th);
  });
  return tr;
}

function sortModels(
  models: ModelRecord[],
  colIndex: number,
  direction: 'asc' | 'desc',
  columns?: ColumnDef[]
): ModelRecord[] {
  return [...models].sort((a, b) => {
    const av = colIndex < a.values.length ? a.values[colIndex] : null;
    const bv = colIndex < b.values.length ? b.values[colIndex] : null;
    // null always last, regardless of direction
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    let cmp: number;
    // Special normalization for Conn/Ports column
    const col = columns?.[colIndex];
    if (col && col.key === 'connectivity' && typeof av === 'string' && typeof bv === 'string') {
      const nav = normalizeCommaList(av);
      const nbv = normalizeCommaList(bv);
      cmp = nav.localeCompare(nbv, undefined, { sensitivity: 'base' });
    } else if (typeof av === 'number' && typeof bv === 'number') {
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
    if (i < FROZEN_COL_COUNT) td.classList.add('col--frozen');

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

function buildDataRow(
  model: ModelRecord,
  columns: ColumnDef[],
  rowIndex: number,
  slotmapLut: Record<string, string>,
): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.dataset.modelId = String(model.id);

  // Gutter — × hide button (left) + 1-based row number (right)
  const gutter = document.createElement('td');
  gutter.className = 'gutter';
  gutter.dataset.modelId = String(model.id);

  const hideBtn = document.createElement('button');
  hideBtn.className = 'gutter__hide-btn';
  hideBtn.setAttribute('aria-label', 'Hide row');
  hideBtn.tabIndex = -1;
  hideBtn.textContent = '\u00d7'; // ×

  const numSpan = document.createElement('span');
  numSpan.className = 'gutter__num';
  numSpan.textContent = String(rowIndex);

  gutter.appendChild(hideBtn);
  gutter.appendChild(numSpan);
  tr.appendChild(gutter);

  const groupOrder = new Map<number, number>();
  for (let i = 0; i < columns.length; i++) {
    const rawValue = i < model.values.length ? model.values[i] : null;
    const col = columns[i];
    const td = document.createElement('td');
    const text = cellText(rawValue, col);

    // Apply truncation when the column has a positive truncateLimit
    const limit = col.truncateLimit ?? 0;
    let displayText: string;
    if (limit > 0 && text.length > limit) {
      td.dataset.fullValue = text;
      displayText = text.slice(0, limit - 1) + '\u2026';
    } else {
      displayText = text;
    }

    td.textContent = displayText;
    td.dataset.colGroup = String(col.groupId);
    td.dataset.colIndex = String(i);
    const order = groupOrder.get(col.groupId) ?? 0;
    td.dataset.colOrder = String(order);
    groupOrder.set(col.groupId, order + 1);
    if (i < FROZEN_COL_COUNT) td.classList.add('col--frozen');
    if (col.shaded) td.classList.add('col-shaded');

    if (isNullish(rawValue)) {
      td.classList.add('cell-null');
    } else {
      // Slot map tooltip + visual markers
      if (col.key.startsWith('slotmap_') && typeof rawValue === 'string') {
        const tooltip = resolveSlotmapTooltip(rawValue, slotmapLut);
        if (tooltip !== null) td.dataset.tooltip = tooltip;
        if (rawValue === '\u2327') {
          td.classList.add('cell-slotmap-empty');
        } else if (rawValue.endsWith('*')) {
          td.classList.add('cell-slotmap-mirror');
        }
      }

      const url = col.linkable ? (model.links?.[col.key] ?? null) : null;
      if (url !== null) {
        td.textContent = '';
        const a = document.createElement('a');
        a.className = 'cell-link';
        a.href = url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        // When truncated, combine full value + URL in the tooltip; otherwise URL only
        a.title = td.dataset.fullValue ? `${td.dataset.fullValue} \u2014 ${url}` : url;
        a.textContent = displayText;
        td.appendChild(a);
      }
    }

    tr.appendChild(td);
  }

  return tr;
}

function buildGapIndicator(
  hiddenIds: number[],
  onUnhide: (ids: number[]) => void,
  colCount: number,
): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.className = 'row-gap-indicator';

  // Sticky gutter cell — holds the unhide button, stays fixed on horizontal scroll
  const gutterTd = document.createElement('td');
  gutterTd.className = 'gutter gutter--gap-gutter';
  const btn = document.createElement('button');
  btn.className = 'gutter__unhide-btn';
  btn.setAttribute('aria-label', `Show ${hiddenIds.length} hidden row${hiddenIds.length > 1 ? 's' : ''}`);
  btn.textContent = '\u25b2'; // ▲
  btn.addEventListener('click', () => onUnhide(hiddenIds));
  gutterTd.appendChild(btn);
  tr.appendChild(gutterTd);

  // Frozen data cells — one per frozen column, each sticky with the dashed line
  for (let i = 0; i < FROZEN_COL_COUNT; i++) {
    const frozenTd = document.createElement('td');
    frozenTd.className = 'gutter--gap gutter--gap-frozen';
    frozenTd.setAttribute('data-col-index', String(i));
    tr.appendChild(frozenTd);
  }

  // Scrollable data cell — spans remaining columns, carries the dashed line
  const dataTd = document.createElement('td');
  dataTd.className = 'gutter--gap';
  dataTd.colSpan = colCount - FROZEN_COL_COUNT;
  tr.appendChild(dataTd);

  return tr;
}

export function buildGrid(data: MSXData, opts?: {
  initialState?: ViewState;
  onStateChange?: () => void;
}): {
  element: HTMLElement;
  toggleFilters: () => void;
  resetView: () => { filtersWereOn: boolean };
  setColumnVisible: (colIdx: number, visible: boolean) => void;
  getHiddenCols: () => ReadonlySet<number>;
  getHiddenRows: () => ReadonlySet<number>;
  hideRow: (modelId: number) => void;
  getSelectedCells: () => ReadonlySet<string>;
  clearAllSelection: () => void;
  copySelection: (includeHeaders?: boolean) => string;
  getViewState: () => ViewState;
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

  // ── Column ID ↔ index maps (for ViewState translation) ───────────────────
  const colIdToIdx = new Map(data.columns.map((col, i) => [col.id, i]));

  // ── Selection state ──────────────────────────────────────────────────────
  // Key format: "${modelId}:${colIdx}"
  const selectedCells = new Set<string>();
  let selAnchor: { modelId: number; colIdx: number } | null = null;
  let isDragging = false;
  let dragStart: { modelId: number; colIdx: number } | null = null;
  let isRowDragging = false;
  let rowDragAnchor: number | null = null;

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

    const activeColIdxs = new Set<number>();
    const activeModelIds = new Set<number>();
    for (const key of selectedCells) {
      const colon = key.indexOf(':');
      activeModelIds.add(Number(key.slice(0, colon)));
      activeColIdxs.add(Number(key.slice(colon + 1)));
    }

    thead.querySelectorAll<HTMLTableCellElement>('th.col-header[data-col-index]').forEach(th => {
      th.classList.toggle('col-header--active', activeColIdxs.has(Number(th.dataset.colIndex)));
    });

    tbody.querySelectorAll<HTMLTableCellElement>('td.gutter[data-model-id]').forEach(td => {
      td.classList.toggle('gutter--cell-active', activeModelIds.has(Number(td.dataset.modelId)));
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

  // ── Row selection state ──────────────────────────────────────────────────
  // Keyed by stable model ID; independent of selectedCells
  const selectedRows = new Set<number>();
  let rowSelAnchor: number | null = null;

  function applyRowSelectionToDOM(): void {
    tbody.querySelectorAll<HTMLTableCellElement>('td.gutter[data-model-id]').forEach(td => {
      td.classList.toggle('gutter--row-selected', selectedRows.has(Number(td.dataset.modelId)));
    });
  }

  // Rebuild selectedCells to contain exactly the cells of all selected rows.
  // Called every time row selection changes.
  function syncCellsFromRowSelection(): void {
    selectedCells.clear();
    selAnchor = null;
    if (selectedRows.size > 0) {
      const visibleColIdxs = data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i));
      selectedRows.forEach(modelId => {
        visibleColIdxs.forEach(colIdx => selectedCells.add(selKey(modelId, colIdx)));
      });
    }
    applySelectionToDOM();
  }

  function clearRowSelection(): void {
    selectedRows.clear();
    rowSelAnchor = null;
    applyRowSelectionToDOM();
    syncCellsFromRowSelection();
  }

  function selectRowRange(fromModelId: number, toModelId: number): void {
    const visibleModelIds = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]'))
      .map(tr => Number(tr.dataset.modelId));
    const fromIdx = visibleModelIds.indexOf(fromModelId);
    const toIdx = visibleModelIds.indexOf(toModelId);
    selectedRows.clear();
    if (fromIdx === -1 || toIdx === -1) {
      selectedRows.add(toModelId);
      rowSelAnchor = toModelId;
      return;
    }
    const min = Math.min(fromIdx, toIdx);
    const max = Math.max(fromIdx, toIdx);
    for (let i = min; i <= max; i++) {
      selectedRows.add(visibleModelIds[i]);
    }
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

    // Filter indicator: show if any column in this group has an active filter
    const hasFilter = groupCols.some(({ idx }) => filters.has(idx));
    th.classList.toggle('group-header--filtered', hasFilter);

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
    opts?.onStateChange?.();
  }

  function getHiddenCols(): ReadonlySet<number> {
    return hiddenCols;
  }

  function hideRow(modelId: number): void {
    hiddenRows.add(modelId);
    renderRows();
    opts?.onStateChange?.();
  }

  function unhideRowsInGap(modelIds: number[]): void {
    modelIds.forEach(id => hiddenRows.delete(id));
    renderRows();
    opts?.onStateChange?.();
  }

  function getHiddenRows(): ReadonlySet<number> {
    return hiddenRows;
  }

  // ── tbody ────────────────────────────────────────────────────────────────
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  function renderRows(): void {
    const sorted = sortColIndex !== null
      ? sortModels(originalModels, sortColIndex, sortDirection, data.columns)
      : originalModels;
    const filtered = filters.size === 0 ? sorted : sorted.filter(model =>
      [...filters.entries()].every(([colIdx, term]) => {
        const raw = colIdx < model.values.length ? model.values[colIdx] : null;
        const value = cellText(raw).toLowerCase();
        // Split on '|' for OR semantics; leading '!' negates a term
        const parts = term.split('|').map(p => p.trim()).filter(p => p.length > 0);
        if (parts.length === 0) return true;
        const positive = parts.filter(p => !p.startsWith('!'));
        const negative = parts.filter(p => p.startsWith('!')).map(p => p.slice(1).toLowerCase()).filter(p => p.length > 0);
        // Positive terms: row matches if value includes ANY of them (OR)
        const passPositive = positive.length === 0 || positive.some(p => value.includes(p.toLowerCase()));
        // Negative terms: row matches only if value includes NONE of them (AND)
        const passNegative = negative.every(n => !value.includes(n));
        return passPositive && passNegative;
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
          // Mark the previous data row so its border-bottom doesn't overlap the dashed line
          if (rows.length > 0) rows[rows.length - 1].classList.add('row-before-gap');
          rows.push(buildGapIndicator(buffer, unhideRowsInGap, data.columns.length));
          buffer = [];
        }
        rows.push(buildDataRow(model, data.columns, rowNum++, data.slotmap_lut ?? {}));
      }
    }
    if (buffer.length > 0) {
      rows.push(buildGapIndicator(buffer, unhideRowsInGap, data.columns.length));
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
    applyRowSelectionToDOM();
    // Defer layout-dependent updates — on initial load the element may not be in
    // the DOM yet, so getBoundingClientRect()/offsetWidth would return zeros.
    requestAnimationFrame(() => {
      updateGapVisibility();
      updateFrozenOffsets();
    });
  }

  // ── Gap indicator scroll-awareness ──────────────────────────────────────
  // Hide the dashed line + unhide button when a gap indicator scrolls under
  // the sticky header — show them again once the gap is fully below it.
  function updateGapVisibility(): void {

    const headerBottom = thead.getBoundingClientRect().bottom;
    for (const row of Array.from(tbody.querySelectorAll<HTMLTableRowElement>('.row-gap-indicator'))) {
      const btn = row.querySelector<HTMLElement>('.gutter__unhide-btn');
      if (!btn) continue;
      // Temporarily show so we can measure
      row.classList.remove('row-gap-indicator--under-header');
      const btnBottom = btn.getBoundingClientRect().bottom;
      const hidden = btnBottom <= headerBottom;
      row.classList.toggle('row-gap-indicator--under-header', hidden);
    }
  }

  // ── Frozen-column left-offset computation ────────────────────────────────
  // Writes CSS custom properties (--frozen-colN-left) onto the .grid-wrap so
  // each sticky column knows its exact `left` value regardless of which
  // preceding columns are hidden.  Called after every renderRows() and when
  // columns are shown/hidden.
  function updateFrozenOffsets(): void {
    let left = GUTTER_WIDTH; // starts just after the 52px row-number gutter
    for (let i = 0; i < FROZEN_COL_COUNT; i++) {
      wrap.style.setProperty(`--frozen-col${i}-left`, `${left}px`);
      if (!hiddenCols.has(i)) {
        // Measure the actual rendered width of any frozen header for column i
        const th = thead.querySelector<HTMLElement>(`th.col--frozen[data-col-index="${i}"]`);
        left += th ? th.offsetWidth : 0;
      }
    }
  }

  // ── Seed from initial state ──────────────────────────────────────────────
  if (opts?.initialState) {
    const init = opts.initialState;

    // Sort (columnId → colIdx)
    if (init.sortColumnId !== null) {
      const idx = colIdToIdx.get(init.sortColumnId);
      if (idx !== undefined) { sortColIndex = idx; sortDirection = init.sortDirection; }
    }

    // Filters (columnId → colIdx)
    for (const [colId, text] of init.filters) {
      const idx = colIdToIdx.get(colId);
      if (idx !== undefined) filters.set(idx, text);
    }

    // Hidden columns (columnId → colIdx)
    for (const colId of init.hiddenColumnIds) {
      const idx = colIdToIdx.get(colId);
      if (idx !== undefined) hiddenCols.add(idx);
    }

    // Hidden rows (already model IDs)
    for (const modelId of init.hiddenRowIds) hiddenRows.add(modelId);

    // Collapsed groups (already group IDs)
    for (const groupId of init.collapsedGroupIds) collapsedGroups.add(groupId);

    // Selected cells ("modelId:colId" → "modelId:colIdx")
    for (const cell of init.selectedCells) {
      const colon = cell.indexOf(':');
      const colIdx = colIdToIdx.get(Number(cell.slice(colon + 1)));
      if (colIdx !== undefined) selectedCells.add(`${cell.slice(0, colon)}:${colIdx}`);
    }

    // ── Apply visual state to thead ──────────────────────────────────────

    // Sort indicator
    if (sortColIndex !== null) {
      const th = thead.querySelector<HTMLElement>(`th.col-header[data-col-index="${sortColIndex}"]`);
      th?.classList.add(sortDirection === 'asc' ? 'col-header--sort-asc' : 'col-header--sort-desc');
    }

    // Filter inputs
    for (const [colId, text] of init.filters) {
      const idx = colIdToIdx.get(colId);
      if (idx === undefined) continue;
      const input = thead.querySelector<HTMLInputElement>(`input.filter-input[data-col-index="${idx}"]`);
      if (!input) continue;
      input.value = text;
      input.classList.add('filter-input--active');
      (input.nextElementSibling as HTMLElement | null)?.classList.remove('filter-clear--hidden');
    }
    if (init.filters.size > 0) {
      updateGutterIndicator();
      // Update group headers for groups that have filters
      const affectedGroups = new Set<number>();
      for (const [colIdx] of filters) {
        const gid = data.columns[colIdx]?.groupId;
        if (gid !== undefined) affectedGroups.add(gid);
      }
      for (const gid of affectedGroups) recalcGroupHeader(gid);
    }

    // Hidden columns in thead (tbody handled in renderRows)
    for (const colIdx of hiddenCols) {
      thead.querySelectorAll<HTMLElement>(`[data-col-index="${colIdx}"]`).forEach(cell => {
        cell.style.display = 'none';
      });
      const groupId = data.columns[colIdx]?.groupId;
      if (groupId !== undefined) recalcGroupHeader(groupId);
    }

    // Collapsed groups in thead (tbody handled in renderRows)
    for (const groupId of collapsedGroups) {
      const th = thead.querySelector<HTMLTableCellElement>(`th.group-header[data-group-id="${groupId}"]`);
      if (!th) continue;
      th.colSpan = 1;
      th.classList.add('collapsed');
      const chevron = th.querySelector<HTMLElement>('.chevron');
      if (chevron) { chevron.classList.remove('fa-chevron-down'); chevron.classList.add('fa-chevron-right'); }
      thead.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
        if (cell.dataset.colOrder === '0') {
          cell.classList.add('col-group-stub');
        } else {
          cell.style.display = 'none';
        }
      });
      recalcGroupHeader(groupId);
    }
  }

  // ── getViewState — snapshot of current state as stable ID-based ViewState ─
  function getViewState(): ViewState {
    const hiddenColumnIds = new Set(
      [...hiddenCols].map(idx => data.columns[idx]?.id).filter((id): id is number => id !== undefined)
    );
    const filtersById = new Map(
      [...filters.entries()]
        .map(([idx, text]): [number, string] | null => {
          const id = data.columns[idx]?.id;
          return id !== undefined ? [id, text] : null;
        })
        .filter((e): e is [number, string] => e !== null)
    );
    const selectedById = new Set(
      [...selectedCells]
        .map(key => {
          const colon = key.indexOf(':');
          const colId = data.columns[Number(key.slice(colon + 1))]?.id;
          return colId !== undefined ? `${key.slice(0, colon)}:${colId}` : null;
        })
        .filter((s): s is string => s !== null)
    );
    return {
      sortColumnId: sortColIndex !== null ? (data.columns[sortColIndex]?.id ?? null) : null,
      sortDirection,
      collapsedGroupIds: new Set(collapsedGroups),
      hiddenColumnIds,
      hiddenRowIds: new Set(hiddenRows),
      filters: filtersById,
      selectedCells: selectedById,
    };
  }

  renderRows();

  // ── Cell tooltip — only when text is actually truncated ──────────────────
  // Link cells manage their own title via the <a> element; skip them here.
  tbody.addEventListener('mouseenter', (e: MouseEvent) => {
    const td = (e.target as HTMLElement).closest<HTMLTableCellElement>('td[data-col-index]');
    if (!td) return;
    if (td.querySelector('a.cell-link')) return;
    if (td.dataset.fullValue) {
      td.title = td.dataset.fullValue;
    } else if (td.scrollWidth > td.offsetWidth) {
      td.title = td.textContent ?? '';
    } else {
      const staticTooltip = td.dataset.tooltip;
      if (staticTooltip) {
        td.title = staticTooltip;
      } else {
        td.removeAttribute('title');
      }
    }
  }, true);

  // ── Gutter mousedown — row hide (× button) and row selection (number) ─────────
  tbody.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    const gutterTd = target.closest<HTMLTableCellElement>('td.gutter[data-model-id]');
    if (!gutterTd) return;
    const modelId = Number(gutterTd.dataset.modelId);
    if (!modelId) return;

    // × hide button — handled on click to avoid accidental drag triggers
    if (target.closest('.gutter__hide-btn')) return;

    e.preventDefault(); // prevent text-selection cursor during drag

    // Row number area — row selection
    if (e.ctrlKey || e.metaKey) {
      if (selectedRows.has(modelId)) {
        selectedRows.delete(modelId);
      } else {
        selectedRows.add(modelId);
      }
      rowSelAnchor = modelId;
    } else if (e.shiftKey && rowSelAnchor !== null) {
      selectRowRange(rowSelAnchor, modelId);
    } else {
      const wasOnlySelection = selectedRows.has(modelId) && selectedRows.size === 1;
      selectedRows.clear();
      if (!wasOnlySelection) {
        selectedRows.add(modelId);
        isRowDragging = true;
        rowDragAnchor = modelId;
      }
      rowSelAnchor = modelId;
    }
    applyRowSelectionToDOM();
    syncCellsFromRowSelection();
    opts?.onStateChange?.();
  });

  // ── Gutter click — × hide button ─────────────────────────────────────────
  tbody.addEventListener('click', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (!target.closest('.gutter__hide-btn')) return;
    const gutterTd = target.closest<HTMLTableCellElement>('td.gutter[data-model-id]');
    if (!gutterTd) return;
    const modelId = Number(gutterTd.dataset.modelId);
    if (!modelId) return;
    if (selectedRows.size > 0) {
      selectedRows.forEach(id => hiddenRows.add(id));
      selectedRows.clear();
    } else {
      hiddenRows.add(modelId);
    }
    renderRows();
    opts?.onStateChange?.();
  });

  // ── Gutter drag — extend row selection ───────────────────────────────────
  tbody.addEventListener('mouseenter', (e: MouseEvent) => {
    if (!isRowDragging || e.buttons !== 1 || rowDragAnchor === null) return;
    const target = e.target as HTMLElement;
    const gutterTd = target.closest<HTMLTableCellElement>('td.gutter[data-model-id]');
    if (!gutterTd) return;
    const modelId = Number(gutterTd.dataset.modelId);
    if (!modelId) return;
    selectRowRange(rowDragAnchor, modelId);
    rowSelAnchor = modelId;
    applyRowSelectionToDOM();
    syncCellsFromRowSelection();
    opts?.onStateChange?.();
  }, true);

  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      clearSelection();
      clearRowSelection();
      opts?.onStateChange?.();
    }
  });

  // ── Cell selection (event delegation on tbody) ───────────────────────────
  tbody.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    // If the click is on link text, let the browser follow the href naturally
    if (target.closest('a.cell-link')) return;
    const td = target.closest<HTMLTableCellElement>('td[data-col-index]');
    if (!td) return;
    const tr = td.closest<HTMLTableRowElement>('tr[data-model-id]');
    if (!tr?.dataset.modelId) return; // gutter or gap indicator rows won't match

    e.preventDefault(); // prevent browser text-selection on drag

    // Direct cell interaction clears any gutter row selection
    if (selectedRows.size > 0) {
      selectedRows.clear();
      rowSelAnchor = null;
      applyRowSelectionToDOM();
    }

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
      opts?.onStateChange?.();
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
      opts?.onStateChange?.();
    } else {
      // Plain click — toggle off if already the only selection, else select single cell
      const key = selKey(modelId, colIdx);
      const wasOnlySelection = selectedCells.has(key) && selectedCells.size === 1;
      selectedCells.clear();
      if (!wasOnlySelection) {
        selectedCells.add(key);
        isDragging = true;
        dragStart = cell;
      }
      selAnchor = cell;
      applySelectionToDOM();
      opts?.onStateChange?.();
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
    opts?.onStateChange?.();
  }, true); // capture to catch all child mouseenter events

  document.addEventListener('mouseup', () => {
    isDragging = false;
    dragStart = null;
    isRowDragging = false;
    rowDragAnchor = null;
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
        chevron.classList.remove('fa-chevron-right'); chevron.classList.add('fa-chevron-down');
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          const cellColIdx = cell.dataset.colIndex !== undefined ? Number(cell.dataset.colIndex) : -1;
          if (hiddenCols.has(cellColIdx)) return; // leave individually-hidden cells hidden
          cell.style.display = '';
          cell.classList.remove('col-group-stub');
        });
        recalcGroupHeader(groupId);
        opts?.onStateChange?.();
      } else {
        // Collapse — keep first cell per row as a zero-width stub anchor;
        // hide all others so the group header colSpan=1 aligns correctly.
        collapsedGroups.add(groupId);
        th.colSpan = 1;
        th.classList.add('collapsed');
        chevron.classList.remove('fa-chevron-down'); chevron.classList.add('fa-chevron-right');
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          if (cell.dataset.colOrder === '0') {
            cell.classList.add('col-group-stub');
          } else {
            cell.style.display = 'none';
          }
        });
        recalcGroupHeader(groupId);
        opts?.onStateChange?.();
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
      opts?.onStateChange?.();
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
      const groupId = data.columns[colIdx]?.groupId;
      if (groupId !== undefined) recalcGroupHeader(groupId);
      updateGutterIndicator();
      renderRows();
      opts?.onStateChange?.();
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
      const groupId = data.columns[colIdx]?.groupId;
      if (groupId !== undefined) recalcGroupHeader(groupId);
      updateGutterIndicator();
      renderRows();
      opts?.onStateChange?.();
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
      // Update all group headers to remove filter indicators
      for (const g of data.groups) recalcGroupHeader(g.id);
      updateGutterIndicator();
      renderRows();
    } else {
      filterRow.style.display = 'table-row';
    }
  }

  // ── Reset view ────────────────────────────────────────────────────────
  function resetView(): { filtersWereOn: boolean } {
    // 1. Clear sort
    sortColIndex = null;
    colHeaders.forEach(h => h.classList.remove('col-header--sort-asc', 'col-header--sort-desc'));

    // 2. Clear hidden rows
    hiddenRows.clear();

    // 3. Expand all collapsed groups and show all hidden columns simultaneously.
    //    Clear both sets first so renderRows() won't re-hide anything.
    collapsedGroups.clear();
    hiddenCols.clear();
    // Restore all cell visibility in thead (tbody is handled by renderRows below)
    table.querySelectorAll<HTMLElement>('[data-col-index]').forEach(cell => {
      cell.style.display = '';
      cell.classList.remove('col-group-stub');
    });
    // Reset every group header: un-collapse, restore full colSpan and chevron direction
    thead.querySelectorAll<HTMLTableCellElement>('th.group-header').forEach(th => {
      const groupId = Number(th.dataset.groupId);
      const fullSpan = data.columns.filter(c => c.groupId === groupId).length;
      th.classList.remove('collapsed', 'group-header--partial', 'group-header--filtered');
      th.colSpan = fullSpan;
      th.style.display = '';
      const chevron = th.querySelector<HTMLElement>('.chevron');
      if (chevron) { chevron.classList.remove('fa-chevron-right'); chevron.classList.add('fa-chevron-down'); }
    });

    // 4. Clear filters
    const filtersWereOn = filterRow.style.display === 'table-row';
    filters.clear();
    thead.querySelectorAll<HTMLInputElement>('input.filter-input').forEach(inp => {
      inp.value = '';
      inp.classList.remove('filter-input--active');
      (inp.nextElementSibling as HTMLElement | null)?.classList.add('filter-clear--hidden');
    });
    if (filtersWereOn) filterRow.style.display = 'none';
    updateGutterIndicator();

    // 5. Clear all selections
    clearSelection();
    clearRowSelection();

    // 6. Re-render and notify
    renderRows();
    opts?.onStateChange?.();

    return { filtersWereOn };
  }

  // ── Clipboard copy ────────────────────────────────────────────────────
  function copySelection(includeHeaders?: boolean): string {
    const visibleModelIds = Array.from(tbody.querySelectorAll<HTMLTableRowElement>('tr[data-model-id]'))
      .map(tr => Number(tr.dataset.modelId));
    const visibleColIdxs = data.columns.map((_, i) => i).filter(i => !hiddenCols.has(i));

    // Group selectedCells by visible row, in visible order
    const rowMap = new Map<number, number[]>();
    for (const modelId of visibleModelIds) {
      const cols = visibleColIdxs.filter(c => selectedCells.has(selKey(modelId, c)));
      if (cols.length > 0) rowMap.set(modelId, cols);
    }
    if (rowMap.size === 0) return '';

    const lines: string[] = [];

    if (includeHeaders) {
      // Collect all selected column indices in visible order (deduplicated across rows)
      const selectedColSet = new Set<number>();
      for (const cols of rowMap.values()) cols.forEach(c => selectedColSet.add(c));
      const headerCols = visibleColIdxs.filter(c => selectedColSet.has(c));
      lines.push(headerCols.map(c => data.columns[c].shortLabel ?? data.columns[c].label).join('\t'));
    }

    for (const [modelId, cols] of rowMap) {
      const model = data.models.find(m => m.id === modelId);
      const fields = cols.map(c => {
        const raw = model && c < model.values.length ? model.values[c] : null;
        if (raw === null || raw === undefined || raw === '') return '';
        if (typeof raw === 'boolean') return raw ? 'Yes' : 'No';
        return String(raw);
      });
      lines.push(fields.join('\t'));
    }
    return lines.join('\n');
  }

  function clearAllSelection(): void {
    clearSelection();
    clearRowSelection();
    opts?.onStateChange?.();
  }

  wrap.appendChild(table);
  wrap.addEventListener('scroll', updateGapVisibility, { passive: true });

  // Deselect when clicking the empty area below the rows (target is wrap itself).
  // Guard against scrollbar clicks: offsetX/Y outside clientWidth/Height = scrollbar area.
  wrap.addEventListener('mousedown', (e: MouseEvent) => {
    if (e.target === wrap && e.offsetX <= wrap.clientWidth && e.offsetY <= wrap.clientHeight) {
      clearAllSelection();
    }
  });

  // Recalculate frozen-column left offsets when the table layout changes size
  // (e.g. window resize, font load, zoom change).
  const resizeObs = new ResizeObserver(() => updateFrozenOffsets());
  resizeObs.observe(table);

  return { element: wrap, toggleFilters, resetView, setColumnVisible, getHiddenCols, getHiddenRows, hideRow, getSelectedCells, clearAllSelection, copySelection, getViewState };
}
