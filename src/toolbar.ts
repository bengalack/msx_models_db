export function buildToolbar(
  onFiltersToggle: () => void,
  onColsToggle: () => void,
  onResetView: () => void,
  onHeadersCopyToggle: () => void,
  onShare: () => void,
  onHelpToggle: () => void,
): {
  element: HTMLElement;
  colsBtn: HTMLButtonElement;
  filtersBtn: HTMLButtonElement;
  resetBtn: HTMLButtonElement;
  headersCopyBtn: HTMLButtonElement;
  shareBtn: HTMLButtonElement;
  shareWrap: HTMLElement;
  helpBtn: HTMLButtonElement;
  helpWrap: HTMLElement;
} {
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

  const headersCopyBtn = document.createElement('button');
  headersCopyBtn.className = 'toolbar__btn';
  const headersCopyIcon = document.createElement('i');
  headersCopyIcon.className = 'fa fa-plus';
  headersCopyBtn.appendChild(headersCopyIcon);
  headersCopyBtn.appendChild(document.createTextNode(' Include headers on copy'));
  headersCopyBtn.addEventListener('click', onHeadersCopyToggle);

  // ── Share button ──────────────────────────────────────────────────────────
  const shareWrap = document.createElement('div');
  shareWrap.className = 'toolbar__btn-wrap';

  const shareBtn = document.createElement('button');
  shareBtn.className = 'toolbar__btn';
  shareBtn.setAttribute('title', 'Copy link to this view');
  const shareIcon = document.createElement('i');
  shareIcon.className = 'fas fa-arrow-up-from-bracket';
  shareBtn.appendChild(shareIcon);
  shareBtn.appendChild(document.createTextNode(' Share'));

  const shareToast = document.createElement('div');
  shareToast.className = 'share-toast';
  shareToast.textContent = 'URL copied to your clipboard';

  let shareToastTimer: ReturnType<typeof setTimeout> | null = null;
  shareBtn.addEventListener('click', () => {
    onShare();
    if (shareToastTimer !== null) clearTimeout(shareToastTimer);
    shareToast.classList.add('share-toast--visible');
    shareToastTimer = setTimeout(() => {
      shareToast.classList.remove('share-toast--visible');
      shareToastTimer = null;
    }, 3000);
  });

  shareWrap.appendChild(shareBtn);
  shareWrap.appendChild(shareToast);

  // ── Help button ───────────────────────────────────────────────────────────
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
  toolbar.appendChild(headersCopyBtn);
  toolbar.appendChild(shareWrap);
  toolbar.appendChild(helpWrap);

  return { element: toolbar, colsBtn, filtersBtn, resetBtn, headersCopyBtn, shareBtn, shareWrap, helpBtn, helpWrap };
}
