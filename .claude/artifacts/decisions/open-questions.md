# Open Questions

## Open

- [x] [Affects: problem-description-slotmap.md] What is the exact structure of `<primary>` / `<secondary>` elements in openMSX machine XMLs for MSX2/2+/turboR? (Answer: Expansion is structural — devices are direct children of `<primary>` when non-expanded; `<secondary slot="0..3">` children appear when expanded. Cartridge slots are `<primary external="true" slot="N"/>`. Page mapping derived from `<mem base size>`. Classification by XML element type + `id` attribute.) (Date: 2026-03-29)
- [x] [Affects: problem-description-slotmap.md] What is the full set of device strings encountered across all target openMSX XML files? (Answer: ROM, RAM, MemoryMapper, PanasonicRAM, WD2793, TC8566AF, MSX-MUSIC, FMPAC, MSX-RS232, MSX-JE (as ROM id). MegaRam/SCCplus/SunriseIDE only in excluded Boosted configs. Starter LUT is sufficient.) (Date: 2026-03-29)
- [x] [Affects: problem-description-slotmap.md] Should numbered cartridge slots (CS1, CS2, …) be auto-generated from a single parameterised pattern or listed individually? (Answer: Parameterised — slot number read from `slot="N"` attribute on `<primary external="true">`. One rule, N derived from data.) (Date: 2026-03-29)
- [ ] [Affects: problem-description-slotmap.md] Is the msx.org "Slot Map" HTML structure consistent across model pages? Manually check 5–10 pages. (Answer: TBD)
- [x] [Affects: problem-description.md] Which FPGA-based unofficial MSX models should be included (MiSTer, Omega, 1chipMSX, others)? (Answer: 1chipMSX and Omega MSX are included — both have dedicated msx.org wiki pages and must be scraped as models. MiSTer MSX core is excluded — it does not represent a distinct MSX model.) (Date: 2026-04-08)
- [ ] [Affects: problem-description.md] Do the proposed column groups and columns match your expectations, or do any need to be added/removed/renamed? (Answer: TBD)
- [x] [Affects: product-requirements.md] Does msx.org allow programmatic scraping? Check msx.org/robots.txt and ToS before implementing the scraper. (Answer: Yes — wiki article pages are allowed for general crawlers. Scraper must use a descriptive custom user-agent, avoid Special: pages, and respect Disallow paths.) (Date: 2026-03-27)
- [x] [Affects: product-requirements.md] What runtime should the scraper use — Node.js or Python? (Answer: Python 3.11+ with beautifulsoup4 + lxml) (Date: 2026-03-27)

## Resolved
