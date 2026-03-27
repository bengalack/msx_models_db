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
  for (const col of columns) {
    const th = document.createElement('th');
    th.className = 'col-header';
    th.scope = 'col';
    th.textContent = col.label;
    th.dataset.colGroup = String(col.groupId);
    tr.appendChild(th);
  }
  return tr;
}

function buildFilterRow(columns: ColumnDef[]): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.className = 'filter-row';
  for (let i = 0; i < columns.length; i++) {
    const td = document.createElement('td');
    td.dataset.colGroup = String(columns[i].groupId);
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

  for (let i = 0; i < columns.length; i++) {
    const rawValue = i < model.values.length ? model.values[i] : null;
    const td = document.createElement('td');
    const text = cellText(rawValue);
    td.textContent = text;
    td.dataset.colGroup = String(columns[i].groupId);

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

  // ── thead ────────────────────────────────────────────────────────────────
  const thead = document.createElement('thead');
  thead.appendChild(buildGroupHeaderRow(data.groups, data.columns));
  thead.appendChild(buildColHeaderRow(data.columns));
  thead.appendChild(buildFilterRow(data.columns));
  table.appendChild(thead);

  // ── tbody ────────────────────────────────────────────────────────────────
  const tbody = document.createElement('tbody');
  data.models.forEach((model, i) => {
    tbody.appendChild(buildDataRow(model, data.columns, i + 1));
  });
  table.appendChild(tbody);

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
        });
      } else {
        // Collapse
        collapsedGroups.add(groupId);
        th.colSpan = 1;
        th.classList.add('collapsed');
        chevron.textContent = '\u25b6'; // ▶
        table.querySelectorAll<HTMLElement>(`[data-col-group="${groupId}"]`).forEach(cell => {
          cell.style.display = 'none';
        });
      }
    });
  });

  wrap.appendChild(table);
  return wrap;
}
