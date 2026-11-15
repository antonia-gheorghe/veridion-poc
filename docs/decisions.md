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
| D7 | 2026-11-15 | Name comparison: strict first (`token_sort_ratio` on core names). If no good match, fall back to a looser comparison that weighs less in the decision | Strict alone would send too many inputs to manual review | approved; details in D16 |
| D8 | 2026-11-15 | Whether a "subset" name match can ever auto-match | 286 of 592 inputs have a subset match before stripping country and branch words | decided in D15 |
| D9 | 2026-11-15 | Spot-check 10% of auto-matches, spread across countries | 15% was too many rows to check by hand | approved, row count fixed after Phase A |
| D10 | 2026-11-15 | Non-auto rows: Claude researches first and records proposed pick, evidence and source links in `data/manual/research_report.csv`; the user makes the final call | Every match must be traceable to a source | approved |
| D11 | 2026-11-15 | Sources: official registries and company sites first; aggregators marked secondary; a row resting only on secondary sources stays "unverified" | Client-facing claims need an authoritative source | approved |
| D12 | 2026-11-15 | Name outcome "exact": `name_sort` = 100 after normalization | 393 inputs; clean break below 100 (notebook 03) | approved |
| D13 | 2026-11-15 | Name outcome "strong": `name_sort` >= 90 | Lower bands add wrong pairs such as BAE Systems International vs BAE Systems Spain; a strong name still needs every location layer | approved |
| D14 | 2026-11-15 | Name outcome "weak": `name_sort` >= 50; below 50 is "none" and feeds rule R3 | 33 inputs below 50 | approved |
| D15 | 2026-11-15 | A subset match (`name_set` = 100, `name_sort` < 100) counts as "weak" at most and never auto-matches | 58 inputs have a subset match as best candidate, e.g. GOOGLE vs GOOGLE COMMERCE | approved |
| D16 | 2026-11-15 | Fallback: if core names are identical with spaces removed, the name outcome is "strong", not "exact" | Catches A T KEARNEY vs ATKEARNEY, FASTBRIDGE vs FAST BRIDGE (6 inputs) | approved |
| D17 | 2026-11-15 | Legal form "conflict": the input's legal form has specific countries and none of the candidate's legal forms (across all its names) shares one. Generic forms (LTD, INC, SA, CO LTD) never conflict; a missing form on either side is "unknown" | 7 exact/strong same-country candidates conflict, e.g. Nets Denmark A/S vs Nets Sweden AB | approved |
| D18 | 2026-11-15 | Input has a street, candidate has none: no auto-match, goes to review | Strict and fail-safe; 13 inputs | approved |
| D19 | 2026-11-15 | Rival: another same-country candidate with exact/strong name and an equal or better address match (exact street > street + postcode > city > country only) sends the input to review | About 33 inputs; some look like duplicate Veridion records (logged as a finding) | approved |
| D20 | 2026-11-15 | Inputs with a branch marker always go to review | Branch or foreign parent is a judgement call | approved |
| D21 | 2026-11-15 | Country word in the input name that disagrees with the candidate's country counts as a conflict | Same signal as a legal-form conflict (D17) | approved |
| D22 | 2026-11-15 | Phase A rules: R1 auto (name exact/strong, same country, no conflict, exact street + number or same street + postcode, no rival); R2 auto (same, but same city, postcode not different, input has no street); R3 no candidate (no weak-or-better name in same or unknown country); R4 review with failing layers as reason. Output `data/output/phase_a_decisions.csv`, one row per input, with layer outcomes, rival and git commit | Restated parameter set | approved |
| D23 | 2026-11-15 | R1 also requires postcode not different, even with exact street + number | 6 auto-matches had the same street and number but a different postcode, e.g. Eastcompeace SG 560501 vs 178957 | approved |
