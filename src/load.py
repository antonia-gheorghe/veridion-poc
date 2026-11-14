"""Load the raw client sample. The raw file is never modified."""
import pandas as pd

from src.config import RAW_FILE


def load_raw() -> pd.DataFrame:
    """One row per (input company, candidate) pair."""
    return pd.read_excel(RAW_FILE, dtype={"input_row_key": int})
