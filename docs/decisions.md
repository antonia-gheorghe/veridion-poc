# Decision log

One line per decision. Evidence for Phase A choices is in `notebooks/02_phase_a_design.ipynb`.

| # | Date | Decision | Reason | Status |
|---|---|---|---|---|
| D1 | 2026-11-15 | Exploration sample: 20 inputs stratified 8 nordics / 6 asia / 3 other / 3 no candidate in country, `random_state=42` | Cover each kind of case at least once | approved |
| D2 | 2026-11-15 | Stop manual exploration after 3 rows; drop the extra 6 | Phase C research covers the hard cases with sources | approved |
| D3 | 2026-11-15 | Matching layers: name, legal form, country, city, postcode, street + number | Each layer is independently explainable | approved |
| D4 | 2026-11-15 | Auto-match only when every layer is high and no other candidate matches comparably; everything else goes to manual review | A wrong auto-match merges two suppliers in the client's spend data | approved |
| D5 | 2026-11-15 | Inputs without a street may auto-match on name + city (rule R2), only if the fail-safe check passes | About a third of inputs have no street | approved |
| D6 | 2026-11-15 | Phase A spec A1 to A5, including the "subset" name outcome and the branch-marker field | Notebook 02, sections 1 to 8 | approved |
| D7 | 2026-11-15 | Name comparison: strict first (`token_sort_ratio` on core names). If no good match, fall back to a looser comparison that weighs less in the decision | Strict alone would send too many inputs to manual review | approved in principle, details after A1 |
| D8 | 2026-11-15 | Whether a "subset" name match can ever auto-match | 286 of 592 inputs have a subset match before stripping country and branch words | decide after A1 |
| D9 | 2026-11-15 | Spot-check 10% of auto-matches, spread across countries | 15% was too many rows to check by hand | approved, row count fixed after Phase A |
| D10 | 2026-11-15 | Non-auto rows: Claude researches first and records proposed pick, evidence and source links in `data/manual/research_report.csv`; the user makes the final call | Every match must be traceable to a source | approved |
| D11 | 2026-11-15 | Sources: official registries and company sites first; aggregators marked secondary; a row resting only on secondary sources stays "unverified" | Client-facing claims need an authoritative source | approved |
