# Design: model revisions (1st / 2nd generation of the same model)

## Metadata
- Date: 2026-09-26
- Status: Implemented (`scraper/revisions.py`, `scraper/msxorg_series.py`, `scraper/msxorg.py`, `scraper/merge.py`)
- Related: 2026-09-26-msxorg-series-pages-design.md, technical-design.md (Alias LUT, merge)

## Problem

Some models exist in more than one revision with different hardware. openMSX models each revision as its own machine, named with a `(vN)` suffix: `Sony HB-F500` and `Sony HB-F500 (v2)`, `Frael BRUC 100 (v1)` and `(v2)`. msx.org describes the revisions on one page (or series page) and marks revision-specific facts in free text:

| Page | Revision-specific info |
|---|---|
| Sony HB-F500 (series) | slot maps "1st Gen HB-F500" / "2nd Gen HB-F500"; RAM "64kB in slot 3-2 (HB-F500 second version)" |
| Frael Bruc 100 | slot maps "version 1 …" / "version 2 …"; Year "1987 (first model), 1988 (second model)"; RAM "(version 1) … (version 2)"; Media "(version 2 only)" |
| Sakhr AX-330 | Video "1st version: TMS-9929A …, 2nd version: Yamaha V9938" |
| Dynadata DPC-200, Talent DPC-200 | Keyboard "(1st version) … (2nd version) …" |

Today the `(v2)` machine gets no msx.org data or link, and the base row can pick up the *second* revision's values (HB-F500's RAM text names "HB-F500 second version"; AX-330's VDP picks the 2nd version's V9938).

## Approach

1. **Naming.** Revision *N* of model *M* is `M (vN)` — openMSX's convention. Revision 1 is the plain name; an openMSX `(v1)` machine is aliased onto the plain name.
2. **Vocabulary.** A revision reference is an ordinal or number with a revision word: `1st/2nd/3rd…`, `first/second/third…` followed by `gen`, `generation`, `version`, `revision` or `model`; `version N`, `revision N`, `generation N`; a standalone `vN`. Version numbers of firmware (`firmware 1.1`) are not revisions.
3. **Resolution.** The per-variant resolver (series design) treats revision references like variant names in qualifiers and labels. A segment qualified for revision *N* (and this variant, or no variant) applies to revision *N* only.
   - The **base record** (revision 1) takes segments for revision 1 or with no revision; segments marked for a later revision are excluded. If only later-revision and other-variant segments remain, the field is unset.
   - A **revision record** (*N* ≥ 2) starts as a copy of the base record and is **overridden** by every value specific to revision *N*. Anything not specific to *N* is inherited — "basic info, overridden by N-th generation info".
4. **Slot map.** A slot map heading with a revision reference applies to that revision (and the variant it names, if any). The base takes a revision-1 heading when there is one.
5. **Emission.** For every revision *N* ≥ 2 that has at least one revision-specific parsed value or slot map, the msx.org parser emits `M (vN)` alongside `M`, with the **same `msxorg_title`** (same msx.org link) and an internal `_revision: N` marker. This applies to model pages and series pages alike.
6. **openMSX gate.** In the merge, an msx.org revision record whose natural key has no openMSX counterpart is dropped (logged `[merge:revision]`). msx.org alone never creates a revision row; its base record still gets the 1st-revision values.

## Data changes
- `data/aliases.json`: `"BRUC 100": ["BRUC 100 (v1)"]` — v2 is no longer collapsed; Bruc 100 becomes two rows (v1 keeps its id).

## Expected effect (2026-09-26 data)

| Row | Change |
|---|---|
| Sony HB-F500 (v2) | msx.org link and data; 2nd Gen slot map; RAM "in slot 3-2" |
| Sony HB-F500 | no longer takes the 2nd version's RAM text |
| Frael BRUC 100 / BRUC 100 (v2) | two rows; year, RAM, media and slot map per revision |
| Sakhr AX-330, Dynadata/Talent DPC-200 | base row gets 1st-version VDP / keyboard; no (v2) row (no openMSX machine) |

## Implementation notes
- The resolver splits a qualified value into segments tagged with variant names and revision numbers (label-colon, leading label, "in" qualifier, trailing qualifier) and one selector picks the segment for (variant, revision). Text before the first label is kept on every segment (`PSG clone (1st version: X, 2nd version: Y)` → `PSG clone X`).
- A lowercase `v` with one or two digits is a revision (`v2`); `V9938` is a VDP.
- A model page with its own specs table only switches to per-revision resolution for the fields and slot map headings that mention revisions; other pages are parsed exactly as before.
- A revision record is emitted only if at least one parsed value differs from the base record.

## Result (2026-09-26 data)
- Revisions detected: Sony HB-F500, Frael Bruc 100, Sakhr AX-330, Dynadata DPC-200, Talent DPC-200.
- Kept (openMSX has the machine): `HB-F500 (v2)` (msx.org link, engine, keyboard), `BRUC 100 (v2)` (id 332 — already registered for that machine before the alias collapsed it).
- Dropped (no openMSX machine): AX-330 (v2), both DPC-200 (v2); their base rows now show the 1st-version VDP / keyboard.

## Testing
- Revision vocabulary: references found and ignored (`firmware 1.1`).
- Resolver: base vs revision values for each form (leading label, label-colon, trailing qualifier, qualifier naming variant + revision).
- Slot map choice per revision.
- Emission: revision record copies the base, overrides only revision-specific fields, keeps `msxorg_title`.
- Merge gate: revision record kept with an openMSX counterpart, dropped without.
