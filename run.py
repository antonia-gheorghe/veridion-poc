"""Run the full pipeline: raw -> resolved matches -> QC -> client output."""
from src import config
from src.load import load_raw
from src.resolve import resolve
from src.score import score_candidates


def main():
    raw = load_raw()
    print(f"Loaded {len(raw)} candidate rows for {raw.input_row_key.nunique()} input companies")
    features = score_candidates(raw)
    config.OUTPUT.mkdir(parents=True, exist_ok=True)
    features.to_csv(config.FEATURES_FILE, index=False)
    print(f"Wrote {len(features)} scored candidates to {config.FEATURES_FILE.relative_to(config.ROOT)}")
    decisions = resolve(features)
    decisions.to_csv(config.DECISIONS_FILE, index=False)
    print(f"Wrote {len(decisions)} decisions to {config.DECISIONS_FILE.relative_to(config.ROOT)}")
    print(decisions.groupby(["decision", "rule"]).size().to_string())
    # TODO: qc -> export


if __name__ == "__main__":
    main()
