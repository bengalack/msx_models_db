export function buildToolbar(onFiltersToggle: () => void, onColsToggle: () => void): HTMLElement {
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const colsBtn = document.createElement('button');
  colsBtn.className = 'toolbar__btn';
  colsBtn.textContent = '⊞ Columns';
  colsBtn.addEventListener('click', onColsToggle);

  const filtersBtn = document.createElement('button');
  filtersBtn.className = 'toolbar__btn';
  filtersBtn.textContent = '⌃ Filters';
  filtersBtn.addEventListener('click', onFiltersToggle);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);

  return toolbar;
}
