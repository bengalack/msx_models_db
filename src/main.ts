import './types.js';

if (!window.MSX_DATA) {
  // eslint-disable-next-line no-console
  console.error('[MSX Models DB] MSX_DATA not found. Is data.js loaded before bundle.js?');
} else {
  const { models } = window.MSX_DATA;

  document.title = 'MSX Models DB';
  const h1 = document.createElement('h1');
  h1.textContent = `MSX Models DB \u2014 ${models.length} models`;
  document.body.appendChild(h1);
}
