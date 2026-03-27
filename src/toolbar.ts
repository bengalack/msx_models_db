export function buildToolbar(): HTMLElement {
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const colsBtn = document.createElement('button');
  colsBtn.className = 'toolbar__btn';
  colsBtn.disabled = true;
  colsBtn.title = 'Coming soon';
  colsBtn.textContent = '⊞ Columns';

  const filtersBtn = document.createElement('button');
  filtersBtn.className = 'toolbar__btn';
  filtersBtn.disabled = true;
  filtersBtn.title = 'Coming soon';
  filtersBtn.textContent = '⌃ Filters';

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);

  return toolbar;
}
