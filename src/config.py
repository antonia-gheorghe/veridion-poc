"""Project paths and settings shared by all pipeline steps."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

RAW_FILE = DATA / "raw" / "presales_data_sample.xlsx"
MATCH_REVIEW = DATA / "manual" / "match_review.csv"
EXTERNAL_MATCHES = DATA / "manual" / "external_matches.csv"
OUTPUT = DATA / "output"
CACHE = DATA / "cache"
