import './styles/theme.css';
import './styles/base.css';
import './styles/header.css';
import './styles/toolbar.css';
import './styles/grid.css';
import './types.js';
import { initTheme, toggleTheme } from './theme.js';
import { buildToolbar } from './toolbar.js';
import { buildGrid } from './grid.js';

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
document.body.appendChild(buildToolbar());

if (!window.MSX_DATA) {
  // eslint-disable-next-line no-console
  console.error('[MSX Models DB] MSX_DATA not found. Is data.js loaded before bundle.js?');
  const err = document.createElement('p');
  err.style.color = 'var(--color-danger)';
  err.style.padding = '16px';
  err.textContent = 'Failed to load data. Is data.js present and loaded before bundle.js?';
  document.body.appendChild(err);
} else {
  const { models, generated } = window.MSX_DATA;

  document.title = `MSX Models DB — ${models.length} models`;
  title.textContent = `MSX Models DB\u2002·\u2002${generated}`;
  document.body.appendChild(buildGrid(window.MSX_DATA));
}
