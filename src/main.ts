import './styles/theme.css';
import './styles/base.css';
import './styles/header.css';
import './types.js';
import { initTheme, toggleTheme } from './theme.js';

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
} else {
  const { models } = window.MSX_DATA;

  document.title = `MSX Models DB — ${models.length} models`;
}
