# Data findings

Issues noticed along the way, to revisit in the QC phase and in feedback to Veridion.
Counts are from the raw sample unless stated otherwise.

## Client input data

| Finding | Example | Count | Source |
|---|---|---|---|
| Norwegian postcodes lost their leading zero (stored as numbers) | "668" for 0668 | 47 of 90 NO inputs | notebook 02, s.3 |
| Outdated company names after rebrands or mergers | ENERGI HOBRO TELE A/S, now a former name of Sinal A/S (key 168); LeasePlan Sverige AB, LeasePlan now Ayvens (key 305) | 2 seen so far | manual review |
| Address updated but name not | key 168 has the Norlys HQ address with the pre-2022 name | 1 seen so far | manual review |
| Branch-of-foreign-company names | "KLM-ROYAL DUTCH AIRLINES Filial av utenlandsk foretak" | 11 inputs | notebook 02, s.6b |
| Country words inside names | "DANMARK A/S", "NORWAY AS" | 153 inputs | notebook 02, s.2 |
| Near-duplicate inputs | 592 inputs, 591 unique names | 1 | profiling |

## Veridion data

| Finding | Example | Count | Source |
|---|---|---|---|
| Norwegian candidate postcodes also lost their leading zero | TINEX Group "668" (key 537) | 129 of 296 NO candidate rows | notebook 02, s.3 |
| Candidates with no country | | 145 candidate rows; 13 of the 26 "no candidate in country" inputs include one | notebook 02, s.8 |
| Implausible employee count | Leaseplan Sweden: 1 employee (key 305) | 1 seen | manual review |
| Revenue inconsistent with size | Norlys: 2,500 employees, revenue 4M (key 168) | 1 seen | manual review |
| Identical values on sibling entities, possibly copied | TINEX Group and TINEX AS both founded 1991 with 6 employees (key 537); Norlys and Eniig both 2,500 employees (key 168) | 2 seen | manual review |
| One record mixes two legal entities | "Eniig Energi Naturgas" lists Eniig Fiber A/S and Stofa Fiber A/S as legal names (key 168) | 1 seen | manual review |
| Outdated names and domains | eniig.com, a retired brand (key 168) | 1 seen | manual review |
| Scraped text used as description | Norlys description is a sentence about trees shading solar panels (key 168) | 1 seen | manual review |
| Website belongs to another company | 3Step IT Oy with domain karei.dev (key 2) | 1 seen | profiling |
| Industry missing on the correct candidate | Leaseplan Sweden (key 305) | 1 seen | manual review |

## Matching engine

| Finding | Example | Count | Source |
|---|---|---|---|
| Alias lists pull in unrelated companies | Wheels Donlen surfaced for LeasePlan via the alias "Wheels Donlen Lease Plan" (key 305) | 1 seen | manual review |
| Parent, sibling and foreign entities returned alongside the right one | TINEX (key 537), LeasePlan (key 305) | 2 seen | manual review |
| Several candidates at the input's exact street | Norlys HQ, three candidates (key 168) | 111 inputs | notebook 02, s.7 |
| Right entity present only under a former name | Sinal A/S appears as "Eniig Energi Naturgas" (key 168) | 1 seen | manual review |
| No candidate in the input's country | | 26 inputs, about half due to missing country | notebook 02, s.8 |
