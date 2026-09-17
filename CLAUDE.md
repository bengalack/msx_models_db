# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

**MSX Models DB** — a single static web page presenting a spreadsheet-like grid of MSX1 / MSX2 / MSX2+ / turbo R computer model specs, hosted on GitHub Pages at https://bengalack.github.io/msx_models_db/.

Two independent sub-systems that only communicate through one file, `docs/data.js`:

1. **Scraper** (`scraper/`, Python 3.11+) — offline CLI the maintainer runs on demand. Pulls openMSX machine XMLs + ROM files, msx.org wiki pages, and local curated JSON; merges them; writes `docs/data.js` (`window.MSX_DATA = {...}`) and updates `data/id-registry.json`.
2. **Web page** (`src/`, vanilla TypeScript + Vite, no framework) — reads `window.MSX_DATA`, renders the grid, keeps all view state client-side and encodes it in the URL hash.

No server anywhere. Output must work on `file://`, GitHub Pages, and as a Blogger embed.

## Project documentation — use it, keep it current

The project was built with a doc-driven agentic workflow. These docs are the source of truth and **must be kept in sync with the implementation** when behaviour changes:

| Doc | Purpose |
|---|---|
| [.claude/artifacts/planning/technical-design.md](.claude/artifacts/planning/technical-design.md) | Architecture, components, key flows, URL codec binary format, feature designs |
| [.claude/artifacts/planning/product-requirements.md](.claude/artifacts/planning/product-requirements.md) | PRD / functional requirements |
| [.claude/artifacts/planning/product-backlog.md](.claude/artifacts/planning/product-backlog.md) | Now/Next/Later/Inbox + shipped features |
| [.claude/artifacts/planning/ux-design-guide.md](.claude/artifacts/planning/ux-design-guide.md) | UX guardrails, theme, interaction patterns |
| [.claude/artifacts/decisions/decision-log.md](.claude/artifacts/decisions/decision-log.md) | Architectural decisions (append new rows with date/why/tradeoff) |
| [.claude/artifacts/decisions/open-questions.md](.claude/artifacts/decisions/open-questions.md) | Open/answered questions |
| [.claude/artifacts/ops/](.claude/artifacts/ops/) | Bug, security, and UX/UI issue lists (tables consumed by `find-issues` / `fix-issues` skills) |
| [.claude/artifacts/planning/tasks/](.claude/artifacts/planning/tasks/) | Per-feature implementation plans |
| [data/schema.md](data/schema.md) | `MSXData` schema shipped in `data.js` |

Conventions:
- New planning/design docs go in `.claude/artifacts/planning/` (dated `YYYY-MM-DD-<topic>-design.md` / `-plan.md`), never `docs/` — `docs/` is the build output served by GitHub Pages.
- The project skills in `.claude/skills/` (describe-problem → define-requirements → design-technical → create-backlog → plan-feature → execute-plan, plus quality-gate, find-issues/fix-issues) are the intended workflow for non-trivial work.

## Commands

```sh
# Web
npm install
npm run dev                 # Vite dev server, http://localhost:5173 (root: src/; hot reload;
                            #   serves docs/data.js fresh per request via the devDataJs plugin)
npm run build               # Build to docs/ (index.html, bundle.js); preserves docs/data.js
npm run typecheck           # tsc --noEmit
npm run lint                # ESLint on src/
npm test -- --run           # Vitest (tests/web/) once

# Scraper (from repo root; paths in scraper/build.py are relative to cwd)
pip install -r requirements.txt
python -m pytest tests/scraper            # pyproject sets pythonpath=.
python -m scraper build                   # Build docs/data.js from cached data/*-raw.json
python -m scraper build --fetch           # Fetch fresh sources first
python -m scraper build --fetch -l        # Fetch using local mirrors only (typical, msx.org blocks scraping)
python -m scraper fetch-openmsx -o data/openmsx-raw.json [--limit N]
python -m scraper fetch-msxorg  -o data/msxorg-raw.json  [--limit N]
python -m scraper merge --openmsx ... --msxorg ... -o ...
```

User prefers `rtk`-prefixed shell commands (see global CLAUDE.md).

## Architecture notes

### Scraper (`scraper/`)
- `__main__.py` — argparse CLI (`build`, `fetch-openmsx`, `fetch-msxorg`, `merge`).
- `build.py` — pipeline orchestration: load config/excludes → load/fetch raw → merge → local overrides → link-shares → derive columns → assign IDs → atomic write of `docs/data.js` + registry. Default file paths are constants at the top.
- `columns.py` — **single source of truth** for groups and columns (IDs, labels, `hidden`, `retired`, `derive`, `truncate_limit`, `shaded`, `linkable`, `max_width`). Validated on load.
- `openmsx.py` / `openmsx_source.py` — XML parsing (lxml `recover=True`) and Live/Mirror/Fallback XML sources.
- `msxorg.py` / `mirror.py` / `msxorg_slotmap.py` — msx.org HTML parsing and Live/Mirror/Fallback page sources.
- `slotmap.py` / `slotmap_lut.py` — 64 slot-map columns (`slotmap_{ms}_{ss}_{page}`), LUT classification (first match wins), mirror detection.
- `merge.py` — natural key `manufacturer|model` (lowercase), openMSX wins over msx.org, substitutions, conflict handling.
- `aliases.py`, `link_shares.py`, `exclude.py`, `registry.py`, `local_source.py`, `http.py`, `symbols.py`.

Merge precedence: **local-raw.json > openMSX > msx.org**.

### Maintainer-curated data (`data/`)
`aliases.json`, `substitutions.json`, `exclude.json`, `link-shares.json`, `slotmap-lut.json`, `local-raw.json`, `scraper-config.json` (local mirror paths + slot-map symbols). `id-registry.json` is generated but committed and **append-only** — IDs are never deleted or reused.

### Web (`src/`)
- `main.ts` — entry; wires header, toolbar, grid, column picker, URL hash sync.
- `grid.ts` — the hand-rolled grid (~1400 lines): rendering, sort, filter (`|` = OR, `!` = NOT), selection, row hide/unhide gaps, sticky headers/gutter, frozen Identity columns, tooltips, clipboard.
- `url/codec.ts` — versioned binary view-state codec → URL-safe base64 in the hash. Format is documented in technical-design.md. Decoder must never throw; unknown IDs are silently dropped.
- `col-picker.ts`, `toolbar.ts`, `theme.ts`, `symbols.ts`, `types.ts` (MSXData types — keep in sync with `data/schema.md` and `scraper/build.py` serialisation).
- `styles/` — all colours via CSS custom properties on `[data-theme]`; no hardcoded hex in components.
- `vite.config.ts` builds an **IIFE** bundle and rewrites `index.html` to plain `<script>` tags (data.js then bundle.js) so it works on `file://`. Don't reintroduce `type="module"`.

## Invariants — do not break

- **Stable IDs**: column IDs (in `columns.py`), group IDs, and model IDs (in `id-registry.json`) are permanent. Never renumber or reuse. Column ID 0 is reserved (sort "none" in codec). Remove columns via `retired=True`, not deletion.
- **Shared URLs are forever**: any change to the URL codec needs a version bump and backward-compatible decoding.
- `docs/` is committed build output. After changing `src/`, run `npm run build`; after scraper changes affecting output, rerun the scraper. Commit rebuilt output separately (existing convention: `chore: rebuild bundle and data`).
- ROM files in `systemroms/` are copyrighted and never committed; only `systemroms/machines/all_sha1s.txt` is tracked. Code that needs ROMs must degrade gracefully when they are absent.
- Scraper never aborts on per-model slot-map/BIOS extraction issues — warn and continue.

## Testing

- Scraper: pytest, `tests/scraper/`. Web: Vitest + jsdom, `tests/web/`.
- Before committing, all of these must pass: `npm run lint`, `npm run typecheck`, `npm test -- --run`, `python -m pytest tests/scraper`, and `npm run build` when `src/` changed.
- **Never hardcode flexible content in tests.** Don't assert `len(columns) == 94`, a fixed set of LUT abbreviations, a label, or a symbol glyph. Load the source of truth (`active_columns()` / `COLUMNS` / `GROUPS` from `scraper/columns.py`, `data/slotmap-lut.json`, `scraper.symbols` constants, `data/scraper-config.json`, `window.MSX_DATA` shape from types) and assert against it. Editing config or data must never break tests when the code is correct. Hardcoded values are fine only in fixtures the test creates itself (tmp files, inline fake data).
- Test overlapping filter inputs and side effects across boundaries (e.g. hide/unhide interplay with filters/selection), not just each feature in isolation.
- Commit style: Conventional Commits (`feat:`, `fix:`, `perf:`, `chore:`, `docs:`, `tests:`).

## Gotchas

- **Slot-map symbols live in two places**: `slotmap_symbols` in `data/scraper-config.json` (used by `scraper/symbols.py` and imported by `src/symbols.ts`) and the `__sentinel__` rules in `data/slotmap-lut.json`. Change both together. Tests must use the `scraper.symbols` constants, never literal glyphs — the configured values differ from the code defaults.
- `data/scraper-config.json` is committed on purpose (the web build needs it); it also holds the maintainer's local mirror paths.
- `data/local-raw.json` is committed (exception to the `data/*-raw.json` ignore rule); the other `*-raw.json` files are local fetch caches.
- Test fakes for `PageSource` / `XMLSource` must match the protocol signatures (e.g. `fetch_category(standard, url, page=1)`).
- Avoid hardcoded counts of columns/LUT rules in tests where a derived value (e.g. `len(active_columns())`) works.
- No CI — all checks are run locally.
- `dill.txt` at repo root is a local scraper log (gitignored).
- Python in this environment is 3.14; Node 24. Windows console is cp1252 — printing slot-map glyphs from ad-hoc Python scripts needs `PYTHONIOENCODING=utf-8`.
