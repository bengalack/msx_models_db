# Decision Log

| Date | Decision | Why | Tradeoff |
| --- | --- | --- | --- |
| 2026-03-27 | Visual theme: CRT phosphor green (dark default) + warm cream (light) | MSX enthusiast audience; retro aesthetic fits the subject matter | More distinctive than generic enterprise; theme must remain swappable via CSS custom properties |
| 2026-03-27 | All colors via CSS custom properties on `[data-theme]`; zero hardcoded hex in components | Maintainer wants to be able to change the theme later without touching component code | Slightly more CSS boilerplate upfront |
| 2026-03-27 | Monospace font throughout (Share Tech Mono / Consolas fallback) | Reinforces terminal aesthetic; ensures column alignment in dense data grid | Less typographic flexibility than mixed font stack |
| 2026-03-27 | Compact row density (24px rows) | Grid has many columns and rows; desktop-first users expect dense data tools | Smaller touch targets — acceptable since mobile-first is out of scope |
| 2026-03-27 | Single-page layout; no modals or navigation | Grid is the only view; all controls are in-page toolbar or context menus | No room for detail panels or per-model views in this iteration |
| 2026-03-27 | Scraper language: Python 3.11+ (beautifulsoup4 + lxml) | Best-in-class HTML/XML scraping libraries; maintainer preference | Two runtimes in the project (Node.js for web, Python for scraper) |
| 2026-03-27 | Web page: Vanilla TypeScript + Vite (no framework) | Custom cell-selection model doesn't fit standard table library abstractions; Vite output is plain static files | More grid implementation work; Node.js required for development |
| 2026-03-27 | Build output committed to docs/ on main branch | GitHub Pages serves from docs/; no separate deploy pipeline needed | Git history includes build artifacts; diffs noisy after scraper runs |
| 2026-03-27 | URL state: versioned binary codec, base64 in hash fragment | Compact enough for large selections; hash has no hard length limit; no server involved | Not human-readable; requires careful version migration if format changes |
| 2026-03-27 | docs/data.js loaded via script tag (not fetch) | Works on file://, HTTP, and Blogger embed equally | Data is bundled as a JS assignment (window.MSX_DATA); slightly less clean than JSON |
