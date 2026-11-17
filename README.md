# Veridion POC: supplier entity resolution and data QC

A large manufacturer's procurement team sent 592 supplier records, each with up to 5 candidate companies from
Veridion. This repo resolves each supplier to a real company, checks the quality of Veridion's data on the matches,
and writes one clean dataset for spend analysis.

## Results

| Status | Suppliers | Meaning |
|---|---|---|
| Matched | 470 (79%) | Resolved to one company: 232 high confidence, 238 medium |
| Unmatched | 122 (21%) | No candidate fits and no official source identifies the company |

Main takeaways for the client:

- 79% of the supplier list now resolves to a verified company with a confidence label, so spend analysis can start
  on those rows today.
- The list is out of date as well as duplicated. It holds renamed companies, old addresses, and two suppliers
  dissolved in 2002 and 2013. Five suppliers appear twice under slightly different spellings.
- Most of the unmatched 21% are local subsidiaries of multinationals (Talend Singapore, AsiaInfo Denmark). The
  candidates contain the group, not the local entity, so these need a targeted search rather than more rules.

## Deliverables

| File | Contents |
|---|---|
| `data/output/suppliers_resolved.xlsx` (and `.csv`) | One row per supplier: status, confidence, matched company, key attributes, registry id, QC counts, suppliers sharing a Veridion record |
| `data/output/qc_flags.csv` | Every QC flag: record, attribute, check, severity, value, evidence |
| `data/output/qc_brreg_sample.csv` | Veridion vs the Norwegian register for 58 records |
| `docs/decisions.md`, `docs/data_findings.md` | Why each rule exists; data problems found, with examples |
| `data/manual/` | Manual decisions, registry and research matches, and sample checks, each with sources |

## How suppliers are matched

Every supplier goes through the same five steps. The logic is plain Python rules in `src/`; no LLM or trained model
is involved, and every manual decision is in `data/manual/` with its source.

**1. Normalize.** Names are uppercased and stripped of accents and punctuation, then split using reference lists in
`data/reference/`: "TELENOR DANMARK A/S" becomes core name `TELENOR`, legal form `A/S` (Danish) and country word
`DK`. Cities drop words like "Kommune", and postcodes get back the leading zeros lost in the spreadsheet.

**2. Score each candidate.** The input is compared with each of its candidates, one layer at a time:

| Layer | Outcome |
|---|---|
| Name | Core names are compared with [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz) against every name the candidate has (main, legal, commercial). **Exact**: same words in any order. **Strong**: same letters ignoring spaces (NOR SAT, NORSAT). **Weak**: one name contains the other, or at least 50% similar. **None**: below that |
| Legal form | Conflict when the forms belong to different countries (A/S is Danish, AB is Swedish) |
| Country words | Conflict when a name says DANMARK and the record is in Norway |
| Country, city, postcode | Same, different, or unknown when missing on either side |
| Street | Street and number same, street only, different, or unknown |

**3. Pick the best candidate.** Only candidates in the input's country take part, and a match on a candidate's main
name beats a match on an alias. They are ranked by name level, then by how much of the address matches (street and
number, street and postcode, city, country only), then by similarity score. The top one is the best candidate. Any
other candidate with an exact or strong name and an address match at least as good is a **rival**, unless it is an
empty record (no website, no employees) next to a full one.

**4. Accept or reject.** The best candidate is checked on every layer, and the problems found decide the rule.
Rules were checked on samples of 8 to 14 rows before use.

| Rule | When | Confidence | Suppliers | Sample check |
|---|---|---|---|---|
| R1 | No problem on any layer: exact or strong name, same country, street and city, no rival | high | 93 | R1 and R2: 12 of 14 correct, 1 unverified, 1 wrong (rule corrected) |
| R2 | As R1, for inputs without a street; the city must agree | high | 40 | see R1 |
| R5 | Only address gaps, and the full legal name (core and legal form) is identical | medium | 117 | 7 of 10 correct, 2 unverified, 1 wrong (corrected by hand) |
| P1 | Only address gaps, good name, city agrees or is unknown | medium | 34 | 8 of 8 correct |
| P2 | Only address gaps, good main name, different city | medium | 25 | 8 of 10 correct, 2 unverified |
| P3 | The rivals are the same company stored twice (same core name, street and city); Veridion's first record kept | medium | 16 | not sampled |
| M1 | Rival, legal or country conflict, or branch name: researched by hand and matched | high | 44 | every row sourced |
| M2 | As M1, researched by hand and rejected | none | 10 | every row sourced |
| U0 | No candidate with even a weak name in the input's country (or with no country) | none | 22 | |
| U1 | No candidate with a good name, or a weak name with at least the city matching | none | 55 | 7 of 10 rightly rejected, 1 missed |
| U2 | Weak name and address gaps | none | 33 | 0 of 10 were the company |
| U3 | No candidate in the input's country | none | 2 | |

**5. Search outside Veridion.** For the unmatched, the core name is looked up in the Norwegian (Brreg) and Finnish
(PRH) registers and GLEIF. A register record is accepted only if its core name and legal form are identical to the
input's and it is the only such record; high confidence if the city also agrees, medium otherwise. A sample of the
rest was researched by hand in official registers and on company sites.

| Rule | When | Confidence | Suppliers | Sample check |
|---|---|---|---|---|
| E1 | Found in an official register (77) or by sourced research (24) | high or medium | 101 | registry: 8 of 10 correct, 2 unverified |

## Data quality

Checks run on the 369 matched Veridion records:

- **Rules on every record:** missing key fields, street number stored as a date, founding year, postcode format,
  revenue per employee below 10k or above 5M, records more than 2 years older than the newest one, and email domain
  vs website.
- **Accuracy against an official register:** the Norwegian register (Brreg) is free and lists employees, industry
  code and address. 34 Norwegian records matched exactly one registered company:

  | Field | Agrees with Brreg |
  |---|---|
  | Employees (within 2x or 5 people) | 14 of 23 (61%) |
  | Industry (NACE division) | 14 of 26 (54%) |
  | Postcode | 23 of 34 (68%) |

- **Hand-verified problems** from the matching work, in `data/manual/qa_findings.csv`.

Severity is **error** for provably wrong values, **warning** for implausible ones and **info** for gaps. 31 suppliers
have at least one error and 51 more have warnings.

What stands out:

- Employee counts are often the group's, not the local entity's: CBRE AS has 135,000 in Veridion and 88 in Brreg.
- Some records carry another company's legal name or website. The Telenor Linx record has the legal name of Telenor
  Pakistan. Amazon Web Services EMEA points to logitech-events.com. A Nordea candidate uses nordeea.co.uk.
- Revenue and employees are missing on about 40% of records, and the website on 25%.
- Mavenir Systems Limited and Mavenir Systems UK Limited, two legal entities, share one Veridion record.

Overall, Veridion is good at finding the company and weaker on attributes. The grouping is usable for spend
analysis now. Employee counts and industry codes need a check before supplier-risk or sustainability decisions rely
on them.

## Limitations and next steps

This is a best-effort result within the time and access available. Each limitation has a known fix:

| Limitation | With more time or access |
|---|---|
| Only Veridion's 5 candidates per supplier; local subsidiaries are often missing | Query Veridion's Match/Search API for the 122 unmatched with the full normalized legal name (e.g. "TALEND SINGAPORE PTE LTD", not the stripped core "TALEND"), plus country, city, street and postcode, and apply the same fail-safe rules to the results |
| Free registers cover only Norway, Finland and LEI holders; attribute accuracy is measured on Norway only | API access to CVR (Denmark, 39 unmatched, 121 matched) and Companies House (UK), and a check of Bolagsverket (Sweden) and ACRA (Singapore), to find the unmatched there and extend the accuracy check to about 200 more records |
| Addresses are compared exactly after cleaning, so "Kongens Lyngby" vs "Lyngby" or "Gl. Kongevej" vs "Gammel Kongevej" count as different; region words in names (Fuzhou, SEA) are not removed | Fuzzy street and city comparison with abbreviation lists, or geocoding both addresses and comparing coordinates |
| Rules checked on 10-row samples, so error rates are rough | A labelled test set of 100+ suppliers to measure each rule's precision |
| The client data has no VAT or registry ids | Ask for them from the ERP; most matching then becomes an exact lookup |
| One reviewer for manual decisions | A second reviewer, and a periodic rerun to catch renames and dissolutions |

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.registry   # optional: registry lookup for unmatched rows (network, cached)
.venv/bin/python run.py            # regenerates everything in data/output/
.venv/bin/python -m pytest
```

Registry responses are cached in `data/external/cache/`, so a rerun gives the same result offline.

## Repo layout

| Path | Purpose |
|---|---|
| `data/raw/` | Client sample as received; never modified |
| `data/reference/` | Legal forms, country words, postcode lengths |
| `data/manual/` | Manual decisions, external matches, QA findings, sample checks |
| `data/external/` | Registry lookup log and cached registry responses |
| `data/output/` | Generated outputs |
| `src/` | Pipeline: normalize, score, resolve, registry, qc, export |
| `notebooks/` | Exploration behind the design |
| `tests/` | Tests for each step |
