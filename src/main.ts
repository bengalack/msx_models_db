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
  document.body.appendChild(buildToolbar(() => { /* no-op */ }, () => { /* no-op */ }, () => { /* no-op */ }).element);
  const err = document.createElement('p');
  err.style.color = 'var(--color-danger)';
  err.style.padding = '16px';
  err.textContent = 'Failed to load data. Is data.js present and loaded before bundle.js?';
  document.body.appendChild(err);
} else {
  const { models, generated } = window.MSX_DATA;

  document.title = `MSX Models DB — ${models.length} models`;
  title.textContent = `MSX Models DB\u2002·\u2002${generated}`;
  const { element: gridEl, toggleFilters, setColumnVisible, getHiddenCols, copySelection } = buildGrid(window.MSX_DATA);

  const { element: pickerEl, open: openPicker, close: closePicker } = buildColPicker(
    window.MSX_DATA.groups,
    window.MSX_DATA.columns,
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
  helpPanel.textContent = 'Help content coming soon.';

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

  let filtersOn = false;
  function handleFiltersToggle(): void {
    toggleFilters();
    filtersOn = !filtersOn;
    filtersBtnEl.classList.toggle('toolbar__btn--active', filtersOn);
  }

  const { element: toolbarEl, colsBtn: colsBtnEl, filtersBtn: filtersBtnEl, helpBtn: helpBtnEl, helpWrap } = buildToolbar(handleFiltersToggle, togglePicker, toggleHelp);
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
      const tsv = copySelection();
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

  // Close picker/help on outside click
  document.addEventListener('mousedown', (e: MouseEvent) => {
    if (pickerOpen && !toolbarEl.contains(e.target as Node)) {
      closePicker();
      pickerOpen = false;
      colsBtnEl.classList.remove('toolbar__btn--active');
    }
    if (helpOpen && !toolbarEl.contains(e.target as Node)) {
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
