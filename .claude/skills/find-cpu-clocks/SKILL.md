---
name: find-cpu-clocks
description: Find documented CPU and Sub-CPU clock frequencies of MSX models in service manuals and schematics (archive.org, Hans Otten, msx.org links), cite the exact page, and record them in data/local-raw.json for the CPU Clock column. Use when new service manuals turn up or the CPU Clock column needs checking.
---

# Find CPU Clocks

## Role

You are a hardware-documentation researcher. You find what each MSX model's CPU clock is **according to a document**, prove it with a link to the exact page, and store it in `data/local-raw.json`. You never guess a value: a model without a document stays empty.

## Background

The MSX standard clock is 3.579545 MHz (NTSC colour subcarrier; 21.47727 MHz ÷ 6, 10.738635 MHz ÷ 3, 14.31818 MHz ÷ 4). Some European machines use another crystal:

| Model(s) | CPU clock | Cause |
|---|---|---|
| Philips VG-8230, VG-8235, NMS 8220, NMS 8245, NMS 8280 | 3.554685 MHz | V9938 crystal 21.328125 MHz ÷ 6 |
| Panasonic CF-2700 (European) | 3.559384 MHz | 10.6781522 MHz ÷ 3 |
| Sony HB-101P / HB-201P | 3.5625 MHz | (= 10.6875 MHz ÷ 3) |
| Sony HB-F500P/F | 3.578281 MHz | adjusted CPU clock |

The values live in `data/local-raw.json` (fields below); the CPU Clock column (`scraper/columns.py`, id 114) — and the Sub-CPU Clock column (id 115, fields `sub_cpu_clock_mhz` / `_source` / `_note`: the Z80 of a turbo R, the Z180 of a Victor HC-90/95) — keeps them rounded to 4 decimals (sorting), shows 2, links to the source page and shows every digit plus the note as tooltip. Design: technical-design.md, *Feature Design: CPU Clock*.

## Setup (once)

```sh
python -m venv %TEMP%\msx-manuals-venv                     # outside the repository
%TEMP%\msx-manuals-venv\Scripts\python -m pip install pypdf pillow lxml beautifulsoup4
```

Scripts are in `.claude/skills/find-cpu-clocks/scripts/`; downloads are cached in `~/.cache/msx-manuals` (`--cache` to change). OCR of image-only PDFs uses the Windows built-in engine (`scripts/ocr.ps1`, Windows 10/11, English text works best).

## Workflow

### 1. Collect candidate documents

```sh
python scripts/find_sources.py            # from the repo root; needs docs/data.js and the msx.org mirror
```

Writes `sources.json`: links on the models' msx.org pages that say service manual / schematic / circuit diagram / technical manual, Hans Otten's computer manuals (https://hansotten.file-hunter.com/manuals-and-guides/), and archive.org search results. Add any new source by hand (a PDF URL or an archive.org item). Prefer the archive.org copy of a document: it usually has OCR text and page links.

### 2. Read each document

```sh
python scripts/manual_text.py https://archive.org/details/<item>[/<doc>]
python scripts/manual_text.py https://example.org/manual.pdf
```

Prints the pages with clock-like numbers (21.x / 10.7x / 14.31x crystals, 3.55–3.58 MHz, 445/447 kHz) with a link to each page. Text comes from archive.org's OCR, else the PDF text layer, else Windows OCR of the scans in every orientation (some PDFs store scans flipped). Use `--find <digits>` to locate the page of a value you already know (e.g. `--find 21328125`).

Things to look for, best first:
1. An explicit **CPU clock** statement or adjustment ("CPU CLOCK FREQUENCY ADJUSTMENT … 3.578281 MHz", "Adjust … 3.562500 MHz on pin 6 of IC6 (CPU)").
2. A **VDP clock** adjustment on an MSX2 (V9938/V9958 supply the CPU clock: CPUCLK = crystal ÷ 6), e.g. Philips "Adjust TC3 for 3.554685 MHz".
3. The **crystal** in the parts list or schematic, when the manual says it drives the CPU.

### 3. Interpret carefully

- **The VDP crystal is not always the CPU clock.** MSX1 machines with a TMS99x8 may clock the CPU from the VDP (CPUCLK = crystal ÷ 3) or from a separate oscillator: Canon V-20 counts a 14.31818 MHz oscillator down to 3.579545 MHz, while its UK VDP is tuned to 445.32 kHz (GROMCLK = crystal ÷ 24, pin 37). Philips VG-8020 has a 10.6875 MHz VDP crystal *and* a 14.31818 MHz crystal — unconfirmed which feeds the CPU, so not recorded. Record a value only when the document ties it to the CPU (or, on MSX2, to the V9938/V9958 clock).
- **Philips parts lists** name crystals by 12NC: 4822 242 71347 = 21.328125 MHz, 4822 242 71685 = 21.47727 MHz, 71345 = 32.768 kHz, 71665 = 4 MHz.
- **Scope**: a manual covers the versions in its title ("NMS8245/00/16" — not /19). Record exactly those rows; a main model row counts as its /00 version. Other versions inherit from their main model in the build anyway.
- **Verify on the page image** before recording (open the page link, or fetch `https://archive.org/download/<item>/<doc>/page/n<N>_w1400.jpg`): OCR swaps digits and drops units.

### 4. Record

Add to the model's entry in `data/local-raw.json` (brand and model exactly as in `docs/data.js`; create the entry if missing, but only for a model the database has):

```json
{
  "brand": "Philips",
  "model": "NMS 8245",
  "cpu_clock_mhz": "3.554685",
  "cpu_clock_source": "https://archive.org/details/philipsnms8245sm/page/n1/mode/1up",
  "cpu_clock_note": "Service manual NMS8245/00/16, adjustments: VDP clock set to 3,554,685 ± 200 Hz (crystal 21.328125 MHz)"
}
```

- `cpu_clock_mhz`: a string with **every digit the source gives** ("3.562500", "3.58"); a crystal-derived value is the exact quotient ("3.5546875").
- `cpu_clock_source`: the page link (archive.org `…/page/nN/mode/1up`, or `<pdf>#page=N`).
- `cpu_clock_note`: which document, where in it, and what it says — the tooltip's "how it was found" hint. Say so when the value is calculated ("calculated: R800 clock = 28.636 MHz ÷ 4") or the source is not a service document (an msx.org page, as for the HC-90/95 Z180).
- A Sub-CPU clock uses the same three fields with the `sub_cpu_clock_` prefix. On a turbo R the CPU is the R800 (oscillator ÷ 4) and the Sub-CPU the Z80 in the MSX-Engine (VDP oscillator ÷ 6).
- Japanese manuals (turbo R technical guides, the MSX turboR Technical Hand Book) need the Windows Japanese OCR pack (`Add-WindowsCapability -Online -Name "Language.OCR~~~ja-JP~0.0.1.0"`, elevated); without it read their pages as images.

### 5. Rebuild and check

```sh
python -m scraper build
python -m pytest tests/scraper
```

Check that the model count did not change (a misspelt brand/model creates a stray row) and that the CPU Clock cells, links and tooltips look right. Keep the research trail (documents checked, values, unreadable ones) in `.claude/artifacts/planning/` if it is worth keeping, and commit the data separately from code.
