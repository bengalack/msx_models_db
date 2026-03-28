export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onHelpToggle: () => void,
): { element: HTMLElement; colsBtn: HTMLButtonElement; filtersBtn: HTMLButtonElement; helpBtn: HTMLButtonElement; helpWrap: HTMLElement } {
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

  const helpWrap = document.createElement('div');
  helpWrap.className = 'toolbar__btn-wrap';
  const helpBtn = document.createElement('button');
  helpBtn.className = 'toolbar__btn';
  helpBtn.textContent = '? Help';
  helpBtn.addEventListener('click', onHelpToggle);
  helpWrap.appendChild(helpBtn);

  toolbar.appendChild(colsBtn);
  toolbar.appendChild(filtersBtn);
  toolbar.appendChild(helpWrap);

  return { element: toolbar, colsBtn, filtersBtn, helpBtn, helpWrap };
}
