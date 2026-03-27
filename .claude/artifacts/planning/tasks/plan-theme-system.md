# Plan: Theme System

## Metadata
- Date: 2026-03-27
- Backlog item: Theme system
- Feature slug: theme-system

## Context
- Intended outcome: The page has a complete dark/light theme controlled by CSS custom properties on `[data-theme]`. The default is dark (CRT phosphor). A `◐` toggle button in a minimal page header switches themes instantly and persists the choice to `localStorage`. All component CSS from this point forward uses only `var(--...)` tokens — zero hardcoded hex.

## Functional Snapshot
- Problem: The page has no visual styling. Every subsequent feature (grid, toolbar, filters) must inherit the theme from the start; retrofitting theme tokens later would require touching every file.
- Target user: Any visitor to the page; bengalack as the developer seeing a styled skeleton
- Success criteria (observable):
  - Page loads with dark phosphor green theme by default (black background, green text)
  - A `◐` button is visible in the top-right of the page header
  - Clicking `◐` switches to the warm cream light theme instantly, without page reload
  - Clicking again switches back to dark
  - Refreshing the page after switching to light → light theme is restored (localStorage)
  - No hardcoded hex values in any CSS file other than `theme.css`
  - `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
- Primary user flow:
  1. User opens page → dark theme renders
  2. User clicks `◐` → light theme applies
  3. User refreshes → light theme persists
- Must never happen:
  - Theme preference lost on page reload
  - `localStorage` unavailability causing an uncaught error (private mode, storage blocked)
  - Any component CSS file containing a hardcoded hex color (e.g. `color: #39ff14`)
  - Theme transition causing visible layout shift or flash
- Key edge cases:
  - `localStorage` unavailable → silently default to dark, no error thrown
  - Unknown `data-theme` value in localStorage → default to dark
  - Multiple rapid toggle clicks → each click applies correctly, no stuck state
- Business rules:
  - `data-theme="dark"` or `data-theme="light"` is set on the `<html>` element (not `<body>`)
  - `localStorage` key: `msx-models-theme`; value: `"dark"` or `"light"`
  - All component styles reference only `var(--...)` custom properties
  - No CSS transitions/animations on theme change (avoid flash artifacts with dense grids)
  - The `◐` button is the only interactive element in the header at this stage; other toolbar buttons (⊞ Columns, ⌃ Filters) are deferred to Grid rendering
- Integrations: none (theme is fully local)
- Non-functional requirements:
  - WCAG 2.1 AA — all text ≥ 4.5:1 contrast in both themes
  - Performance: theme applies synchronously before first render (no flash of wrong theme)
- Minimal viable increment (MVI): CSS tokens for both themes + `theme.ts` module + page header shell with `◐` button
- Deferred:
  - Full toolbar (⊞ Columns, ⌃ Filters buttons — deferred to Grid rendering)
  - Toolbar timestamp display
  - Any grid-specific CSS (grid rows, cells, headers — deferred to Grid rendering)

## Executable Specification (Gherkin)

```gherkin
Feature: Theme system
  The page supports dark and light themes via CSS custom properties on the
  html element. Theme choice persists across page loads via localStorage.

  Scenario: Dark theme is the default on first visit
    Given no theme preference is stored in localStorage
    When the user opens the page
    Then the html element has data-theme="dark"
    And the page background is near-black and text is phosphor green

  Scenario: Toggle switches from dark to light
    Given the page is loaded in dark theme
    When the user clicks the ◐ toggle button
    Then the html element has data-theme="light"
    And the page background changes to warm off-white
    And the ◐ button is still visible and clickable

  Scenario: Theme preference persists across page reloads
    Given the user has switched to light theme
    When the user reloads the page
    Then the html element has data-theme="light"
    And the light theme renders without flicker

  Scenario: Toggle back from light to dark
    Given the page is loaded in light theme
    When the user clicks the ◐ toggle button
    Then the html element has data-theme="dark"

  Scenario: localStorage unavailable does not cause an error
    Given localStorage throws an error on access (private browsing or storage blocked)
    When the page loads
    Then the page renders in dark theme
    And no uncaught JavaScript error is thrown

  Scenario: Unknown stored theme value falls back to dark
    Given localStorage contains msx-models-theme = "retro"
    When the page loads
    Then the html element has data-theme="dark"

  Scenario: No hardcoded hex in component CSS
    Given any CSS file other than theme.css
    When the file is inspected
    Then no hex color literal (e.g. #39ff14, #0a0a0a) appears in the file
```

## Baseline Gate
- Start from clean, green trunk.
- All npm commands exit 0 before branching.

## Architecture Fit
- Touch points:
  - `src/styles/theme.css` — new; all CSS custom property definitions for both themes
  - `src/styles/base.css` — new; body/html resets, font stack, `*` box-sizing; uses only `var(--...)` tokens
  - `src/styles/header.css` — new; page header bar styles
  - `src/theme.ts` — new; `initTheme()`, `toggleTheme()`, `getTheme()`
  - `src/main.ts` — updated; import CSS files, call `initTheme()`, build header DOM
  - `index.html` — updated; add `<link rel="stylesheet">` or rely on Vite CSS imports; font import
  - `docs/` — updated after build
- Compatibility notes:
  - `initTheme()` must run synchronously before any DOM render to avoid flash of wrong theme
  - The font (Share Tech Mono from Google Fonts) must load gracefully — fallback to Consolas/Monaco if unavailable. Since the page must work on `file://` (no network), we should embed a `@font-face` local fallback or accept the system monospace fallback without a network request.
  - Decision: do NOT load Share Tech Mono from Google Fonts CDN (blocked on `file://` and requires network). Use system monospace stack (`"Consolas", "Monaco", "Courier New", monospace`) only. Accent the terminal feel with CSS, not the specific font.

## Observability (Minimum Viable)
- Applicability: Minimal
- Failure modes:
  - localStorage read fails → catch silently, use default `"dark"`
  - localStorage write fails → catch silently, theme still applies in-memory

## Testing Strategy (Tier 0/1/2)
- Tier 0: `npm run typecheck` validates `theme.ts` types; `npm run lint` validates no-console and other rules
- Tier 1: N/A (no logic complex enough to unit test — `initTheme` is a single localStorage read + setAttribute; `toggleTheme` is a ternary)
- Tier 2: N/A
- Note: Visual correctness is validated manually by opening `docs/index.html` and verifying both themes

## Data and Migrations
- Applicability: N/A — localStorage key `msx-models-theme` is created on first toggle; no migration needed

## Rollout and Verify
- Applicability: N/A — local development; no deployment step in this feature
- Note: `docs/` committed after build for GitHub Pages

## Cleanup Before Merge
- No hardcoded hex in any CSS other than `theme.css`
- No debug console statements
- All commits follow Conventional Commits (`feat:` or `style:` prefix)

## Definition of Done
- `npm run typecheck`, `npm run lint`, `npm run build` all exit 0
- Opening `docs/index.html` via `file://` shows dark theme by default
- `◐` button toggles theme; preference persists on reload
- `localStorage` failure is silent (no uncaught errors)
- Zero hardcoded hex in CSS files other than `theme.css`

## Chunks

- Chunk 1: CSS theme tokens + base styles
  - User value: The terminal aesthetic is visible for the first time; devs can start using `var(--...)` tokens immediately
  - Scope: `src/styles/theme.css` (both theme blocks), `src/styles/base.css` (resets + font stack), import both in `main.ts`
  - Ship criteria: `npm run build` exits 0; opening `docs/index.html` shows dark background + phosphor green text
  - Rollout notes: none

- Chunk 2: Theme module (init + toggle + localStorage)
  - User value: `◐` button works; theme persists across reloads
  - Scope: `src/theme.ts` (`initTheme`, `toggleTheme`, `getTheme`), update `main.ts` to call `initTheme()` before DOM render
  - Ship criteria: `npm run typecheck` exits 0; `initTheme()` applies correct theme on load; localStorage failure is silent
  - Rollout notes: none

- Chunk 3: Page header shell + toggle button wired up
  - User value: Page looks like a real app — header bar with title and `◐` button; clicking toggles theme
  - Scope: `src/styles/header.css`, update `main.ts` to render `<header>` with title + `◐` button calling `toggleTheme()`; rebuild and commit `docs/`
  - Ship criteria: Header renders in both themes; toggle works visually; `npm run build` exits 0; `docs/index.html` passes all validation steps
  - Rollout notes: none

## Relevant Files (Expected)
- `src/styles/theme.css` — CSS custom property definitions for `[data-theme="dark"]` and `[data-theme="light"]`
- `src/styles/base.css` — `html`, `body`, `*` resets; font stack; background/text using `var(--...)`
- `src/styles/header.css` — header bar layout and button styles; all colors via `var(--...)`
- `src/theme.ts` — `initTheme()`, `toggleTheme()`, `getTheme()` exported functions
- `src/main.ts` — imports CSS, calls `initTheme()`, builds header DOM with toggle button
- `index.html` — unchanged (CSS injected by Vite via imports in main.ts)
- `docs/` — rebuilt after Chunk 3

## Assumptions
- Google Fonts CDN is not used (breaks on `file://`); system monospace stack is the fallback
- `initTheme()` is called synchronously at module load time — before any DOM append — to avoid flash of wrong theme
- The `◐` button is the only toolbar element at this stage; ⊞ Columns and ⌃ Filters are added in Grid rendering

## Validation Script (Draft)
1. Run `npm run build` — exits 0
2. Open `docs/index.html` via `file://` in Chrome
3. Verify: background is near-black, text is phosphor green, `◐` button is visible in top-right
4. Click `◐` → verify: background switches to warm off-white, text to dark forest green
5. Click `◐` again → verify: returns to dark theme
6. Switch to light, refresh the page → verify: light theme loads immediately (no flash of dark)
7. DevTools → Application → Local Storage → confirm `msx-models-theme` key is present
8. Run `npm run typecheck` — exits 0
9. Run `npm run lint` — exits 0
10. Grep `src/styles/base.css` and `src/styles/header.css` for `#` → expect no matches

## Tasks
- [x] T-001 Create and checkout a local branch `feature/theme-system`

- [ ] Chunk 1: CSS theme tokens + base styles
  - [x] T-010 Create `src/styles/theme.css`: exact dark and light theme custom property blocks from UX design guide; no other CSS in this file
  - [x] T-011 Create `src/styles/base.css`: `*`/`html`/`body` resets; font stack (`"Consolas", "Monaco", "Courier New", monospace`); set `background: var(--color-bg)` and `color: var(--color-text)` on body; `box-sizing: border-box`; `margin: 0`
  - [x] T-012 Import both CSS files at top of `src/main.ts` (Vite injects them into the bundle)
  - [x] T-013 Verify `npm run build` exits 0; open `docs/index.html` — dark background and green text visible
  - [x] T-014 Commit: `style: add CSS theme tokens and base styles`

- [ ] Chunk 2: Theme module
  - [x] T-020 Create `src/theme.ts`: export `initTheme()` (reads localStorage, validates value, sets `data-theme` on `<html>`, defaults to `"dark"`); export `toggleTheme()` (switches `data-theme` and writes to localStorage, swallowing any storage errors); export `getTheme()` (returns current `data-theme` value)
  - [x] T-021 Update `src/main.ts`: call `initTheme()` as the first line of the `else` branch (after MSX_DATA guard), before any DOM manipulation
  - [x] T-022 Verify `npm run typecheck` exits 0 and `npm run lint` exits 0
  - [x] T-023 Commit: `feat: add theme module with localStorage persistence`

- [ ] Chunk 3: Page header shell + toggle button
  - [x] T-030 Create `src/styles/header.css`: `.app-header` layout (flexbox, space-between, sticky, 36px height); `.theme-toggle` button reset + size + cursor; all colors via `var(--...)`
  - [x] T-031 Update `src/main.ts`: replace the current `h1` stub with a proper `<header class="app-header">` containing a `<span>` for the title and a `<button class="theme-toggle">◐</button>` wired to `toggleTheme()`; import `header.css`
  - [x] T-032 Verify `npm run build` exits 0; open `docs/index.html` — header visible in both themes; toggle works; localStorage key set
  - [x] T-033 Commit: `feat: add page header bar with dark/light theme toggle`

- [ ] Chunk 4: Update docs/ and commit
  - [x] T-040 Run `npm run build` to ensure final `docs/` is current
  - [x] T-041 Commit: `chore: update docs/ build output with theme system`

- [ ] Quality gate
  - [x] T-900 Run `npm run lint` — confirm 0 errors
  - [x] T-901 Run `npm run typecheck` — confirm 0 errors
  - [x] T-902 Run `npm test -- --run` — confirm exits 0
  - [x] T-903 Run `npm run build` — confirm exits 0
  - [x] T-904 Grep `src/styles/base.css src/styles/header.css` for hex — confirm 0 matches

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Confirm all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge fast-forward only

## Open Questions
- None
