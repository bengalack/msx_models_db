# Open Questions

## Open

- [ ] [Affects: problem-description.md] Which FPGA-based unofficial MSX models should be included (MiSTer, Omega, 1chipMSX, others)? (Answer: TBD)
- [ ] [Affects: problem-description.md] Do the proposed column groups and columns match your expectations, or do any need to be added/removed/renamed? (Answer: TBD)
- [x] [Affects: product-requirements.md] Does msx.org allow programmatic scraping? Check msx.org/robots.txt and ToS before implementing the scraper. (Answer: Yes — wiki article pages are allowed for general crawlers. Scraper must use a descriptive custom user-agent, avoid Special: pages, and respect Disallow paths.) (Date: 2026-03-27)
- [x] [Affects: product-requirements.md] What runtime should the scraper use — Node.js or Python? (Answer: Python 3.11+ with beautifulsoup4 + lxml) (Date: 2026-03-27)

## Resolved
