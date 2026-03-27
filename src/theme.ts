const STORAGE_KEY = 'msx-models-theme';
type Theme = 'dark' | 'light';

function isValidTheme(value: string): value is Theme {
  return value === 'dark' || value === 'light';
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null && isValidTheme(stored)) {
      return stored;
    }
  } catch {
    // localStorage unavailable (private browsing, storage blocked) — use default
  }
  return 'dark';
}

function writeStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // localStorage unavailable — theme still applies in-memory
  }
}

export function initTheme(): void {
  const theme = readStoredTheme();
  document.documentElement.setAttribute('data-theme', theme);
}

export function toggleTheme(): void {
  const current = getTheme();
  const next: Theme = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  writeStoredTheme(next);
}

export function getTheme(): Theme {
  const value = document.documentElement.getAttribute('data-theme');
  return isValidTheme(value ?? '') ? (value as Theme) : 'dark';
}
