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

## Findings
_TBD_
