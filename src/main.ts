import '@fortawesome/fontawesome-free/css/fontawesome.css';
import '@fortawesome/fontawesome-free/css/solid.css';
import './styles/theme.css';
import './styles/base.css';
import './styles/header.css';
import './styles/toolbar.css';
import './styles/grid.css';
import './styles/statusbar.css';
import './types.js';
import { initTheme, toggleTheme } from './theme.js';
import { buildToolbar } from './toolbar.js';
import { buildGrid } from './grid.js';
import { buildColPicker } from './col-picker.js';
import { encodeToHash, decodeFromHash } from './url/codec.js';

initTheme();

const header = document.createElement('header');
header.className = 'app-header';

const title = document.createElement('span');
title.className = 'app-header__title';
title.textContent = 'MSX Models DB';

const toggle = document.createElement('button');
toggle.className = 'theme-toggle';
toggle.textContent = '◐';
toggle.setAttribute('aria-label', 'Toggle dark/light theme');
toggle.addEventListener('click', toggleTheme);

header.appendChild(title);
header.appendChild(toggle);
document.body.appendChild(header);

if (!window.MSX_DATA) {
  // eslint-disable-next-line no-console
  console.error('[MSX Models DB] MSX_DATA not found. Is data.js loaded before bundle.js?');
  document.body.appendChild(buildToolbar(() => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }).element);
  const err = document.createElement('p');
  err.style.color = 'var(--color-danger)';
  err.style.padding = '16px';
  err.textContent = 'Failed to load data. Is data.js present and loaded before bundle.js?';
  document.body.appendChild(err);
} else {
  const { models, generated, columns, groups } = window.MSX_DATA;

  const pageTitle = `MSX Models DB by Bengalack\u2002·\u2002${models.length}\u00a0models\u2002·\u2002${generated}`;
  document.title = pageTitle;
  title.textContent = pageTitle;

  // ── URL state: decode hash on load ────────────────────────────────────────
  const knownColumnIds = new Set(columns.map(c => c.id));
  const knownGroupIds = new Set(groups.map(g => g.id));
  const knownModelIds = new Set(models.map(m => m.id));
  const initialState = decodeFromHash(window.location.hash, knownColumnIds, knownGroupIds, knownModelIds);

  // ── URL state: debounced write-back ───────────────────────────────────────
  let urlDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  function scheduleUrlUpdate(): void {
    if (urlDebounceTimer !== null) clearTimeout(urlDebounceTimer);
    urlDebounceTimer = setTimeout(() => {
      urlDebounceTimer = null;
      const hash = encodeToHash(grid.getViewState());
      if (!hash) return;
      try {
        history.replaceState(null, '', hash);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn('[url-codec] replaceState failed', { error: String(err) });
      }
    }, 1000);
  }

  const grid = buildGrid(window.MSX_DATA, {
    initialState,
    onStateChange: scheduleUrlUpdate,
  });
  const { element: gridEl, toggleFilters, resetView, setColumnVisible, getHiddenCols, clearAllSelection, copySelection } = grid;

  const identityGroupId = window.MSX_DATA.groups.find(g => g.key === 'identity')?.id;
  const pickerGroups = window.MSX_DATA.groups.filter(g => g.id !== identityGroupId);
  const pickerColumns = window.MSX_DATA.columns.filter(c => c.groupId !== identityGroupId);
  const { element: pickerEl, open: openPicker, close: closePicker } = buildColPicker(
    pickerGroups,
    pickerColumns,
    getHiddenCols,
    setColumnVisible,
  );

  let pickerOpen = false;
  function togglePicker(): void {
    if (pickerOpen) {
      closePicker();
    } else {
      if (helpOpen) { helpPanel.hidden = true; helpOpen = false; helpBtnEl.classList.remove('toolbar__btn--active'); }
      openPicker();
    }
    pickerOpen = !pickerOpen;
    colsBtnEl.classList.toggle('toolbar__btn--active', pickerOpen);
  }

  // ── Help panel ──────────────────────────────────────────────────────────
  const helpPanel = document.createElement('div');
  helpPanel.className = 'help-panel';
  helpPanel.hidden = true;
  helpPanel.innerHTML = `
<h3>Dataset</h3>
<p>
Main sources: <a href=\"https://openmsx.org/wiki\" >openmsx</a> and <a href=\"https://msx.org/wiki\" >msx.org</a>. The dataset is not complete. Maybe one day😊
</p><br/>
<h3>Symbols</h3>
<p>
— means empty cell (value is none or unknown).<br/>
· in a slot means absent slot (slot not expanded).<br/>
⏺ in a slot means that the page is empty (valid slot).<br/>
* (suffix) and italics in a slot means mirror.<br/>
! (suffix) in a slot is a cartridge or expansion slot placed in a sub slot.<br/>
</p><br/>
<h3>Sorting</h3>
<p>
Click column headers for sorting, click again to sort in opposite direction, and click yet again to remove sorting.
</p><br/>
<h3>Filters</h3>
<p>
When filters are enabled you can filter on a substring, and benefit from these special characters:<br/>
| means "or".<br/>
! means "not".<br/>
— means empty (em dash).<br/>
Example for "Engine": "Toshiba|!T9763" for Toshibas excluding the T9763.
<p>
</p><br/>
<h3>Selections</h3>
<ul>
<li>Drag, ctrl- and shift-clicks supported.</li>
<li>Click the line number to select the whole line.</li>
<li>Click anywhere to deselect.</li>
</ul>
</p><br/>
<h3>Hiding lines</h3>
<p>
Pressing the x next to a line number will hide the current line and/or all the selected lines.
</p><br/>
<h3>Reduce amount of columns</h3>
<p>
Use the 'Columns' button to choose visible columns, or toggle collapse/expand of groups in the header.
</p><br/>
<h3>Sharing</h3>
<p>
Share the current view customization via an URL. Use the button or just copy the URL in the address field.
</p><br/>
<h3>Export</h3>
<p>
Select and copy/paste.
Cells shown as "—" will paste as empty.
Toggle on 'Include headers on copy' for added context.
</p><br/>
<h3>Feedback</h3>
<p>
Let me hear your feedback about the <a href=\"https://github.com/bengalack/msx_models_db\">project</a> via the <a href=\"https://www.msx.org/forum/msx-talk/msx-resource-center/msx-models-overview-tool\">tool thread</a> on msx.org.
</p>
`;

  let helpOpen = false;
  function toggleHelp(): void {
    if (helpOpen) {
      helpPanel.hidden = true;
    } else {
      if (pickerOpen) { closePicker(); pickerOpen = false; colsBtnEl.classList.remove('toolbar__btn--active'); }
      helpPanel.hidden = false;
    }
    helpOpen = !helpOpen;
    helpBtnEl.classList.toggle('toolbar__btn--active', helpOpen);
  }

  // Show filter bar if initial state has active filters
  let filtersOn = initialState.filters.size > 0;
  if (filtersOn) toggleFilters();

  function handleFiltersToggle(): void {
    toggleFilters();
    filtersOn = !filtersOn;
    filtersBtnEl.classList.toggle('toolbar__btn--active', filtersOn);
  }

  function handleResetView(): void {
    // Close any open panels
    if (pickerOpen) { closePicker(); pickerOpen = false; colsBtnEl.classList.remove('toolbar__btn--active'); }
    if (helpOpen) { helpPanel.hidden = true; helpOpen = false; helpBtnEl.classList.remove('toolbar__btn--active'); }
    const { filtersWereOn } = resetView();
    if (filtersWereOn) {
      filtersOn = false;
      filtersBtnEl.classList.remove('toolbar__btn--active');
    }
  }

  // ── Include headers on copy toggle ────────────────────────────────────────
  let headersOnCopy = false;
  let headersCopyBtnEl!: HTMLButtonElement;

  function handleHeadersCopyToggle(): void {
    headersOnCopy = !headersOnCopy;
    headersCopyBtnEl.classList.toggle('toolbar__btn--active', headersOnCopy);
  }

  // ── Share button ──────────────────────────────────────────────────────────
  function handleShare(): void {
    const url = window.location.href;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(url).catch(() => execCommandFallback(url));
    } else {
      execCommandFallback(url);
    }
  }

  const toolbarResult = buildToolbar(handleFiltersToggle, togglePicker, handleResetView, handleHeadersCopyToggle, handleShare, toggleHelp);
  const toolbarEl = toolbarResult.element;
  const colsBtnEl = toolbarResult.colsBtn;
  const filtersBtnEl = toolbarResult.filtersBtn;
  headersCopyBtnEl = toolbarResult.headersCopyBtn;
  const helpBtnEl = toolbarResult.helpBtn;
  const helpWrap = toolbarResult.helpWrap;
  if (filtersOn) filtersBtnEl.classList.add('toolbar__btn--active');
  toolbarEl.appendChild(pickerEl);
  helpWrap.appendChild(helpPanel);
  document.body.appendChild(toolbarEl);
  document.body.appendChild(gridEl);

  // ── Status bar ────────────────────────────────────────────────────────────
  const statusBar = document.createElement('div');
  statusBar.className = 'status-bar';
  document.body.appendChild(statusBar);

  let statusTimer: ReturnType<typeof setTimeout> | null = null;
  function showStatus(msg: string, durationMs = 2000): void {
    if (statusTimer !== null) clearTimeout(statusTimer);
    statusBar.textContent = msg;
    statusBar.classList.add('status-bar--visible');
    statusTimer = setTimeout(() => {
      statusBar.classList.remove('status-bar--visible');
      statusTimer = null;
    }, durationMs);
  }

  // ── Clipboard copy (Ctrl+C / Cmd+C) ──────────────────────────────────────
  function execCommandFallback(text: string): void {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
      const tsv = copySelection(headersOnCopy);
      if (!tsv) return; // nothing selected — let browser handle default copy
      e.preventDefault();
      const cellCount = tsv.split('\n').reduce((n, row) => n + row.split('\t').length, 0);
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(tsv).catch(() => execCommandFallback(tsv));
      } else {
        execCommandFallback(tsv);
      }
      showStatus(`Copied ${cellCount} cell(s)`);
    }
  });

  // Deselect cells on outside click (click on dead space, not buttons/panels/grid)
  document.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as HTMLElement;
    if (
      !gridEl.contains(target) &&
      !pickerEl.contains(target) &&
      !helpPanel.contains(target) &&
      !target.closest('button') &&
      !target.closest('a')
    ) {
      clearAllSelection();
    }
  });

  // Close picker/help on outside click
  document.addEventListener('mousedown', (e: MouseEvent) => {
    const target = e.target as Node;
    if (pickerOpen && !pickerEl.contains(target) && !colsBtnEl.contains(target)) {
      closePicker();
      pickerOpen = false;
      colsBtnEl.classList.remove('toolbar__btn--active');
    }
    if (helpOpen && !helpPanel.contains(target) && !helpBtnEl.contains(target)) {
      helpPanel.hidden = true;
      helpOpen = false;
      helpBtnEl.classList.remove('toolbar__btn--active');
    }
  });

  // Close picker/help on Escape
  document.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      if (pickerOpen) {
        closePicker();
        pickerOpen = false;
        colsBtnEl.classList.remove('toolbar__btn--active');
      }
      if (helpOpen) {
        helpPanel.hidden = true;
        helpOpen = false;
        helpBtnEl.classList.remove('toolbar__btn--active');
      }
    }
  });
}
