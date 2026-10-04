# CPU Clock Research — 2026-10-03

Findings behind the CPU Clock column (`cpu_clock_*` in `data/local-raw.json`). Process: the `find-cpu-clocks` skill. Standard clock: 3.579545 MHz.

## Documented, non-standard (21 rows)

| Rows | CPU clock | Evidence |
|---|---|---|
| Philips VG 8230 | 3.554685 MHz | [VG8230/00 adjustments](https://archive.org/details/philipsvg8230sm/page/n1/mode/1up); crystal 21.32812 MHz ([parts](https://archive.org/details/philipsvg8230sm/page/n16/mode/1up)) |
| Philips VG-8235, VG 8235/00, /02, /19 | 3.554685 MHz | [VG8235/00/02/19 adjustments](https://archive.org/details/vg8235sm/vg8235sm00/page/n1/mode/1up) |
| Philips VG 8235/20, /39, VG-8235/22, /29, /36 | 3.5546875 MHz | [VG8235/20/22/29/36/39 parts: crystal 21.328125 MHz](https://archive.org/details/vg8235sm/vg8235sm20/page/n13/mode/1up) |
| Philips NMS 8220, NMS 8220/16 | 3.554685 MHz | [adjustments](https://archive.org/details/philipsnms8220sm/page/n1/mode/1up); crystal 21.328125 MHz ([parts](https://archive.org/details/philipsnms8220sm/page/n22/mode/1up)) |
| Philips NMS 8245, NMS 8245/16 | 3.554685 MHz | [adjustments](https://archive.org/details/philipsnms8245sm/page/n1/mode/1up); crystal 21.328125 MHz ([parts](https://archive.org/details/philipsnms8245sm/page/n24/mode/1up)) |
| Philips NMS 8280, NMS 8280/16 | 3.554688 MHz | [adjustments](https://archive.org/details/philipsnms8280sm/page/n1/mode/1up); "3.55 MHz crystal" ([parts](https://archive.org/details/philipsnms8280sm/page/n45/mode/1up)) |
| Panasonic CF-2700 (GB) | 3.559384 MHz | [10.6781522 MHz ÷ 3](https://archive.org/details/panasoniccf2700sm/page/n6/mode/1up) |
| Sony HB-101P, HB-201P | 3.5625 MHz | [CPU clock adjustment](https://archive.org/details/sonyhb101sm/page/n59/mode/1up) |
| Sony HB-F500P, HB-F500F | 3.578281 MHz | [CPU clock adjustment](https://archive.org/details/SonyHBF500ServiceManual/Sony%20HB-F500%20Service%20Manual%20-%20Part%202/page/n56/mode/1up) |

## Documented, standard (39 rows)

Philips VG-8000, VG 8000/00, VG-8010, VG 8010/00; NMS 8250, 8250/16, 8250/19, 8255, 8255/16, 8255/19 (parts list: X104 21.47727 MHz); Sony HB-10P, HB-10B, HB-501P, HB-501F, HB-F1XD, HB-F9P, HB-F9S, HB-F700P/S/F/D, HB-G900P, HB-G900F, HB-G900AP; Panasonic FS-A1WX; Pioneer PX-7, PX-7(HB), PX-V60, UC-V102; Yamaha CX5M, CX5MU, CX5MII, YIS-503F; Sakhr AX-500; Goldstar FC-200; Sanyo PHC-77; Spectravideo SVI-728; Canon V-20 (EU), V-20 (FR). Links in `data/local-raw.json`.

## Sub-CPU clocks (Sub-CPU Clock column)

| Rows | CPU / Sub-CPU | Evidence |
|---|---|---|
| Panasonic FS-A1GT | R800 7.159 MHz / Z80 3.57953 MHz | [technical guide, Z80-mode self-test](https://archive.org/details/panasonicturborgtsm/panasonicturborgtcolorsm/page/n29/mode/1up): oscillators 28.636 MHz (R800) and 21.4772 MHz (VDP); calculated ÷ 4 and ÷ 6 |
| Victor HC-90, HC-90A, HC-95, HC-95A (+ (B)/(V)/(T) by inheritance) | Sub-CPU Z180 6.144 MHz | msx.org [HC-90](https://www.msx.org/wiki/Victor_HC-90) / [HC-95](https://www.msx.org/wiki/Victor_HC-95): "a Z180 (HD64180) at 6.144 MHz"; the HC-90/95 schematic gave no value |

Not found: Panasonic FS-A1ST (technical guide JP: MSX-Engine "Z80A equivalent", no frequency on the pages read), Aucnet NIA-2001, and the MSX turboR Technical Hand Book (Hans Otten; chapter 1 hardware has no frequencies). Searching the Japanese documents properly needs the Windows Japanese OCR pack — postponed.

## Corrections made during the research

- **Canon V-20 UK** first looked non-standard (VDP tuned to 445.12–445.52 kHz → crystal ≈ 10.688 MHz), but its CPU runs from a separate 14.31818 MHz oscillator ÷ 4 = 3.579545 MHz ([n20](https://archive.org/details/canonv20sm/page/n20/mode/1up)). Standard.
- **Philips VG-8020** has a 10.6875 MHz VDP crystal (VDP adjusted to 445.32 kHz) and a 14.31818 MHz crystal X2; the manual does not say which drives the CPU. Not recorded.
- **Philips NMS 8250/8255** — unlike the 8220/8245/8280 — use 21.47727 MHz ([parts list](https://archive.org/details/PhilipsNMS825xSM/philipsnms825055sm/page/n35/mode/1up)); their scans are stored flipped in the PDF.

## Read, no clock found

Victor HC-90/95 schematic, Panasonic FS-A1ST technical guide (JP), Talent TPC-310 circuit diagram, Pioneer PX-JY7 (JP), Yamaha YIS-503IIIR circuit diagram, Panasonic FS-A1WSX (only the FS-A1WX schematic was found).

## Candidates for a next round

Models likely to share a documented clock but outside a manual's stated scope (inherited in the build where they are versions): NMS 8245/19, NMS 8280/02 / 09 / 19, VG-8235/16, VG 8010/19, Phonola rebrands, CF-2700 (DE), HB-G900D, PX-V7, HB-F700B. About 360 rows have no service manual found.

## Re-check 2026-10-04: documents that were never really read

The Sony HB-55P/75P/75B service manual was listed above as "read, no clock found", yet its specifications page says "Clock frequency 3.579545 MHz" ([n2](https://archive.org/details/sonyhb5575sm/sonyhp5575sm/page/n2/mode/1up)). Causes, all fixed in the skill's `manual_text.py`:

1. The scans are stored flipped; the first OCR pass read them as stored only and got mirrored garbage ("CIOCX gedneuch"). Orientation handling came later and the document was not read again.
2. OCR errors were silently taken as empty pages (Windows OCR needs absolute image paths).
3. A document with almost no text still counted as read, and a short archive.org text (CPC-300 schematic: 215 characters over 9 pages) passed as "real text", so its PDF was never OCR'd.
4. Tiny downloads were kept (msxblog.es answers plain http with a 239-byte "403 Forbidden" page).
5. `find_sources.py` read only the models' own pages, not the series pages they defer to (`Category:Sony_HB-75` holds the HB-55P/75P/75B manual).

Every image-only document was read again (14 documents whose archive.org text was empty or tiny, plus the two service manuals in the CX-5M technical documents ZIP):

| Document | Result |
|---|---|
| Sony HB-55P/75P/75B service manual | **new**: 3.579545 MHz ([n2](https://archive.org/details/sonyhb5575sm/sonyhp5575sm/page/n2/mode/1up)) → HB-55P, HB-75P, HB-75B |
| Daewoo CPC-300 schematic (domestic) | OCR cannot read the faint scan; read by eye: V9938 crystal 21.47727 MHz, CPUCLK → Z-80A ([n5](https://archive.org/details/cpc300sch/page/n5/mode/1up)) → **new** 3.579545 MHz (calculated; AVT CPC-300 inherits) |
| Talent TPC-310 schematic | read by eye: Y3 21.4772 MHz → V9938 XTAL1 ([n5](https://archive.org/details/tpc310msx2pcserviceguide/page/n5/mode/1up), [n1](https://archive.org/details/tpc310msx2pcserviceguide/page/n1/mode/1up)) → **new** 3.5795333 MHz (calculated) |
| Yamaha CX5M (GB) / CX-5MU, CX5M and CX5M-II manuals in the CX-5M ZIP | readable now; confirm the CX5MU / CX5MII values already recorded |
| Canon V-20, Philips VG8235 (4 documents), Sony HB-501 diagrams | readable now; confirm the values already recorded |
| Philips VG8230 hi-res circuit | not readable (1 huge page); VG 8230 already recorded from its service manual |
| Yamaha YIS-503IIIR circuit diagram | readable now; no clock value printed |
| Pioneer PX-JY7 (JP) | not read (Japanese) |
| Sony HB-F700D manual (msxblog.es, series page link) | same file as the HB-F700P/F/S/D manual already read (10,089,229 bytes) |

