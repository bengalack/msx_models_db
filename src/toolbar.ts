export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onResetView: () => void,
  onHelpToggle: () => void,
): { element: HTMLElement; colsBtn: HTMLButtonElement; filtersBtn: HTMLButtonElement; resetBtn: HTMLButtonElement; helpBtn: HTMLButtonElement; helpWrap: HTMLElement } {
  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';

  const colsBtn = document.createElement('button');
  colsBtn.className = 'toolbar__btn';
  const colsIcon = document.createElement('i');
  colsIcon.className = 'fa fa-table';
  colsBtn.appendChild(colsIcon);
  colsBtn.appendChild(document.createTextNode(' Columns'));
  colsBtn.addEventListener('click', onColsToggle);

  const filtersBtn = document.createElement('button');
  filtersBtn.className = 'toolbar__btn';
  const filtersIcon = document.createElement('i');
  filtersIcon.className = 'fas fa-filter';
  filtersBtn.appendChild(filtersIcon);
  filtersBtn.appendChild(document.createTextNode(' Filters'));
  filtersBtn.addEventListener('click', onFiltersToggle);

  const resetBtn = document.createElement('button');
  resetBtn.className = 'toolbar__btn';
  resetBtn.textContent = '\u21bb Reset view';
  resetBtn.addEventListener('click', onResetView);

  const helpWrap = document.createElement('div');
  helpWrap.className = 'toolbar__btn-wrap';
  const helpBtn = document.createElement('button');
  helpBtn.className = 'toolbar__btn';
  helpBtn.textContent = '? Help';
  helpBtn.addEventListener('click', onHelpToggle);
  helpWrap.appendChild(helpBtn);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);
  toolbar.appendChild(resetBtn);
  toolbar.appendChild(helpWrap);

  return { element: toolbar, colsBtn, filtersBtn, resetBtn, helpBtn, helpWrap };
}
