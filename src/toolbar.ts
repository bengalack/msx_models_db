export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onHelpToggle: () => void,
): { element: HTMLElement; filtersBtn: HTMLButtonElement; helpBtn: HTMLButtonElement } {
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

  const helpBtn = document.createElement('button');
  helpBtn.className = 'toolbar__btn';
  helpBtn.textContent = '? Help';
  helpBtn.addEventListener('click', onHelpToggle);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);
  toolbar.appendChild(helpBtn);

  return { element: toolbar, filtersBtn, helpBtn };
}
