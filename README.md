# Veridion POC – Supplier Entity Resolution & Data QC

Procurement POC for a large manufacturer: resolve 592 supplier records to real-world
companies, QC the Veridion attributes, and show how the cleaned data supports spend
analysis, cost savings and (later) sustainability.

## Repo layout
| Path | Purpose |
|---|---|
| `data/raw/` | Client sample as received. Never modified. |
| `data/manual/match_review.csv` | Human match decisions (override rules), with reasons. |
| `data/manual/external_matches.csv` | Companies found outside the 5 candidates (Veridion Search API / web). |
| `data/output/` | Generated: final dataset, QC flags, summary. |
| `notebooks/` | Exploration. Findings that hold up move into `src/`. |
| `src/` | Pipeline steps: normalize → score → resolve → qc → export. |
| `run.py` | Regenerates all outputs from raw + manual decisions. |

## Running
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # add Veridion API key (optional, only for external lookups)
.venv/bin/python run.py
```

## Approach
_TBD_

## Match confidence
Each input in `data/output/phase_a_decisions.csv` has a `decision`, the `rule` that produced it, a `reason`
and a `confidence`. Rules are in `docs/decisions.md`; sample checks with sources are in `data/manual/`.

| Rule | Decision | Confidence | Sample check |
|---|---|---|---|
| R1, R2 | auto | high | 12 of 14 confirmed, 1 unverified, 1 wrong (fixed by D25); 2 more wrong found later (fixed by D35) |
| R5 | auto | medium | 7 of 10 correct, 2 unverified, 1 wrong (fixed manually) |
| M1 | manual | high | user review or sourced research per row |
| P1 | probable | medium | 8 of 8 correct |
| P2 | probable | medium | first sample 2 wrong (fixed by D35, D36); second sample 8 correct, 2 unverified |
| P3 | probable | medium | not sampled |
| U1 | unmatched | none | 7 of 10 correctly rejected, 1 missed match, 2 unverified |
| U2 | unmatched | none | 0 of 10 were the company (5 related, 1 wrong, 4 unverified) |
| U3 | unmatched | none | 0 of 5 were the company (5 group or parent records) |
| U4 | unmatched | none | alias picks right 2 of 5; the right company was another candidate or missing |
| M2 | unmatched | none | user review or sourced research per row |
| R3 | no candidate | none | not sampled |

## Findings
_TBD_
