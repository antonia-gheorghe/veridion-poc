"""Run the full pipeline: raw -> resolved matches -> QC -> client output."""
from src.load import load_raw


def main():
    raw = load_raw()
    print(f"Loaded {len(raw)} candidate rows for {raw.input_row_key.nunique()} input companies")
    # TODO: normalize -> score -> resolve -> qc -> export


if __name__ == "__main__":
    main()
