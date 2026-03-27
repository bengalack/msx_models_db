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
    const order = groupOrder.get(columns[i].groupId) ?? 0;
    td.dataset.colOrder = String(order);
    groupOrder.set(columns[i].groupId, order + 1);
    tr.appendChild(td);
  }
  return tr;
}

function buildDataRow(model: ModelRecord, columns: ColumnDef[], rowIndex: number): HTMLTableRowElement {
  const tr = document.createElement('tr');

  // Gutter — 1-based row number
  const gutter = document.createElement('td');
  gutter.className = 'gutter';
  gutter.textContent = String(rowIndex);
  tr.appendChild(gutter);

  const groupOrder = new Map<number, number>();
  for (let i = 0; i < columns.length; i++) {
    const rawValue = i < model.values.length ? model.values[i] : null;
    const td = document.createElement('td');
    const text = cellText(rawValue);
    td.textContent = text;
    td.dataset.colGroup = String(columns[i].groupId);
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

export function buildGrid(data: MSXData): HTMLElement {
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

  // ── thead ────────────────────────────────────────────────────────────────
  const thead = document.createElement('thead');
  thead.appendChild(buildGroupHeaderRow(data.groups, data.columns));
  thead.appendChild(buildColHeaderRow(data.columns));
  thead.appendChild(buildFilterRow(data.columns));
  table.appendChild(thead);

  // ── tbody ────────────────────────────────────────────────────────────────
  const tbody = document.createElement('tbody');
  table.appendChild(tbody);

  function renderRows(): void {
    const models = sortColIndex !== null
      ? sortModels(originalModels, sortColIndex, sortDirection)
      : originalModels;
    tbody.replaceChildren(
      ...models.map((model, i) => buildDataRow(model, data.columns, i + 1))
    );
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
  }

  renderRows();

  // ── Group collapse / expand ──────────────────────────────────────────────
  const groupHeaders = thead.querySelectorAll<HTMLTableCellElement>('th.group-header');
  groupHeaders.forEach(th => {
    th.addEventListener('click', () => {
      const groupId = Number(th.dataset.groupId);
      const colCount = Number(th.dataset.colCount);
      const chevron = th.querySelector<HTMLElement>('.chevron')!;

      if (collapsedGroups.has(groupId)) {
        // Expand
        collapsedGroups.delete(groupId);
        th.colSpan = colCount;
        th.classList.remove('collapsed');
        chevron.textContent = '\u25bc'; // ▼
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          cell.style.display = '';
          cell.classList.remove('col-group-stub');
        });
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

  wrap.appendChild(table);
  return wrap;
}
