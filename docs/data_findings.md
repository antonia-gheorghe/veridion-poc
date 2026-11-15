# Data findings

Issues noticed along the way, to revisit in the QC phase and in feedback to Veridion.
Counts are from the raw sample unless stated otherwise.

## Client input data

| Finding | Example | Count | Source |
|---|---|---|---|
| Postcodes lost their leading zero; the xlsx stores most postcodes as numbers | "668" for 0668 (NO), "68804" for 068804 (SG), "2610" for 02610 (FI) | NO 47 of 90, SG 21 of 41, FI 6 of 10, MY 1, US 1 inputs | notebook 02, s.3; postcode check per country |
| Placeholder postcode | "0" for a Hong Kong input; Hong Kong has no postcodes | 1 | postcode check per country |
| Outdated company names after rebrands or mergers | ENERGI HOBRO TELE A/S, now a former name of Sinal A/S (key 168); LeasePlan Sverige AB, LeasePlan now Ayvens (key 305) | 2 seen so far | manual review |
| Address updated but name not | key 168 has the Norlys HQ address with the pre-2022 name | 1 seen so far | manual review |
| Branch-of-foreign-company names | "KLM-ROYAL DUTCH AIRLINES Filial av utenlandsk foretak" | 11 inputs | notebook 02, s.6b |
| Country words inside names | "DANMARK A/S", "NORWAY AS" | 153 inputs | notebook 02, s.2 |
| Input names of legal entities that were renamed and demerged | KANTAR TNS AS = org 924319623, now FIFTY5BLUE NORGE AS; business moved to KANTAR NORGE AS in 2023 (287) | 1 seen | Phase B |
| Outdated input address after an HQ move | EUTELSAT S.A. at Rue Balard; registered office is 32 bd Gallieni, Issy-les-Moulineaux per its statuts (179) | 1 seen | Phase C, review table |
| Near-duplicate inputs | 592 inputs, 591 unique names | 1 | profiling |

## Veridion data

| Finding | Example | Count | Source |
|---|---|---|---|
| Norwegian candidate postcodes also lost their leading zero | TINEX Group "668" (key 537) | 129 of 296 NO candidate rows | notebook 02, s.3 |
| Candidates with no country | | 145 candidate rows; 13 of the 26 "no candidate in country" inputs include one | notebook 02, s.8 |
| `locations` entries that do not split into the 9 documented fields | probably commas inside street or city names | 86 entries in 76 candidate rows | `src/score.py`, column `locations_unparsed` |
| Company names with broken spacing | "DAILY JURR AT", "E WORKGROUP" | 2 seen | notebook 03 |
| Implausible employee count | Leaseplan Sweden: 1 employee (key 305) | 1 seen | manual review |
| Revenue inconsistent with size | Norlys: 2,500 employees, revenue 4M (key 168) | 1 seen | manual review |
| Identical values on sibling entities, possibly copied | TINEX Group and TINEX AS both founded 1991 with 6 employees (key 537); Norlys and Eniig both 2,500 employees (key 168) | 2 seen | manual review |
| One record mixes two legal entities | "Eniig Energi Naturgas" lists Eniig Fiber A/S and Stofa Fiber A/S as legal names (key 168) | 1 seen | manual review |
| Outdated names and domains | eniig.com, a retired brand (key 168) | 1 seen | manual review |
| Scraped text used as description | Norlys description is a sentence about trees shading solar panels (key 168) | 1 seen | manual review |
| Website belongs to another company | 3Step IT Oy with domain karei.dev (key 2) | 1 seen | profiling |
| Possible duplicate records: two candidates with the same name at the same address | ANNALECT and Annalect (key 38); two "Citero" records (key 97) | up to 33 inputs have 2+ exact/strong candidates in the same city; duplicates not yet separated from sibling entities | rival check, D19 |
| Legal names that belong to other entities | TM Global: 'Telekom Malaysia UK Ltd.' (507); ACOME: 'ACOME GmbH' (12); China Telecom Global: 'Innovic Technology Corporation Limited' (90); Telenor Linx: 'Telenor Pakistan Private Limited' (519) | 4 of 14 spot-check rows | Phase B |
| Street number stored as a date | CBRE Teknisk servicepartner: '2026-01-07 00:00:00' for Blytækkervej 3-7 (86) | 1 seen | Phase B |
| Dissolved company still listed | eCapacity A/S, CVR 30814037, dissolved after merger June 2024 per aggregator (154) | 1 seen | Phase B |
| Outdated main address | A&O Shearman at Bishops Square; registered office now 2 Broadgate (27) | 1 seen | Phase B |
| Division record next to the company record | TM Global (division, 250 employees) and Telekom Malaysia (group, 24,000) both returned (507) | 1 seen | Phase B |
| Singapore postcode 178957 used as a filler on unrelated addresses | Delta Electronics (Saint George's Road), Eastcompeace (Ang Mo Kio Ave 5), Gartner (Straits View) all 178957 | 50 candidate rows | Phase C, probable sample |
| Commercial names that belong to another company | Telefiber AS (org 990331367) lists 'Telenor Fiber AS' (org 929340272) as a commercial name (515) | 1 seen | Phase C, probable sample |
| Main country set from a foreign branch | SystemTeknik A/S (Nørresundby HQ) filed under Poland via its Szczecin office (489) | 1 seen | Phase C, U1 sample |
| Address belongs to another organisation | Neras Direkte AS record carries the address of NERAS B.I.L, a sports club (346) | 1 seen | Phase C, P2 sample |
| Website is a look-alike domain | Nordea record at Essendrops gate 7, Oslo has website nordeea.co.uk (359) | 1 seen | Phase C, review table |
| Correct record with no country, no address and a wrong website | Amazon Web Services EMEA: website logitech-events.com (31) | 1 seen | Phase C, review table |
| Industry missing on the correct candidate | Leaseplan Sweden (key 305) | 1 seen | manual review |

## Matching engine

| Finding | Example | Count | Source |
|---|---|---|---|
| Alias lists pull in unrelated companies | Wheels Donlen surfaced for LeasePlan via the alias "Wheels Donlen Lease Plan" (key 305) | 1 seen | manual review |
| Parent, sibling and foreign entities returned alongside the right one | TINEX (key 537), LeasePlan (key 305) | 2 seen | manual review |
| Several candidates at the input's exact street | Norlys HQ, three candidates (key 168) | 111 inputs | notebook 02, s.7 |
| Right entity present only under a former name | Sinal A/S appears as "Eniig Energi Naturgas" (key 168) | 1 seen | manual review |
| Auto-match picks an alias-named record over the main record | Nokia Solutions and Networks Oy -> HEXA-X Consortium; Johnson Controls Denmark ApS -> Sabroe; Telekom Malaysia Berhad -> TM Global | 10 of 141 auto-matches matched via a legal or commercial name while another exact/strong same-country candidate exists | Phase B |
| No candidate in the input's country | | 26 inputs, about half due to missing country | notebook 02, s.8 |
| Record carries the old legal name of a renamed company | GegeStore (Debrecen reseller) holds "Telenor Magyarország Zrt.", renamed Yettel Magyarország Zrt. in 2022 (key 520) | 1 seen | legal form update (D56) |
| Registries know renames that the candidates miss | DK Hostmaster -> Punktum dk (142), itelligence -> NTT DATA Business Solutions (368), IBM Danmark A/S -> ApS (253) | 4 of 76 registry matches via a former name | registry lookup (D54) |
