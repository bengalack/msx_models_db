export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
): { element: HTMLElement; filtersBtn: HTMLButtonElement } {
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const colsBtn = document.createElement('button');
  colsBtn.className = 'toolbar__btn';
  colsBtn.textContent = '\u229e Columns';
  colsBtn.addEventListener('click', onColsToggle);

  const filtersBtn = document.createElement('button');
  filtersBtn.className = 'toolbar__btn';
  filtersBtn.textContent = '\u2261 Filters';
  filtersBtn.addEventListener('click', onFiltersToggle);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);

  return { element: toolbar, filtersBtn };
}
