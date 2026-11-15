"""Project paths and settings shared by all pipeline steps."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

RAW_FILE = DATA / "raw" / "presales_data_sample.xlsx"
MATCH_REVIEW = DATA / "manual" / "match_review.csv"
EXTERNAL_MATCHES = DATA / "manual" / "external_matches.csv"
OUTPUT = DATA / "output"
CACHE = DATA / "cache"

REFERENCE = DATA / "reference"
LEGAL_FORMS = REFERENCE / "legal_forms.csv"
COUNTRY_WORDS = REFERENCE / "country_words.csv"
POSTCODE_DIGITS = REFERENCE / "postcode_digits.csv"
CITY_ADMIN_WORDS = REFERENCE / "city_admin_words.csv"
BRANCH_MARKERS = REFERENCE / "branch_markers.csv"

FEATURES_FILE = OUTPUT / "phase_a_features.csv"
DECISIONS_FILE = OUTPUT / "phase_a_decisions.csv"
