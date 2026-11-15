"""Draw the Phase B spot-check sample of auto-matches (D9, D24)."""
import pandas as pd

from src import config
from src.load import load_raw

SEED = 42
MIN_R2 = 4
REGION_SAMPLE = {"DK": 5, "NO": 3, "ASIA": 3, "EUROPE": 2, "US": 1}
REGION_OF = {
    "DK": "DK", "NO": "NO", "US": "US",
    **dict.fromkeys(["MY", "CN", "SG", "PK", "IN", "TH", "HK", "JP", "KR"], "ASIA"),
    **dict.fromkeys(["SE", "GB", "FI", "FR", "CH", "NL", "HU", "IE", "RO"], "EUROPE"),
}
REVIEW_COLUMNS = ["verdict", "evidence", "source_links", "source_type", "verified", "user_decision"]
INPUT_FIELDS = ["input_company_name", "input_main_country_code", "input_main_city", "input_main_postcode",
                "input_main_street", "input_main_street_number"]
CAND_FIELDS = ["company_name", "company_legal_names", "main_country_code", "main_city", "main_postcode",
               "main_street", "main_street_number", "website_domain"]


def draw(decisions: pd.DataFrame) -> pd.DataFrame:
    auto = decisions[decisions.decision == "auto"].assign(region=lambda d: d.input_country_code.map(REGION_OF))
    unmapped = auto[auto.region.isna()].input_country_code.unique()
    if len(unmapped):
        raise ValueError(f"Countries without a region: {sorted(unmapped)}")

    picks = []
    for region, size in REGION_SAMPLE.items():
        pool = auto[auto.region == region]
        n_r2 = round(size * (pool.rule == "R2").mean())
        for rule, n in (("R2", n_r2), ("R1", size - n_r2)):
            picks.append(pool[pool.rule == rule].sample(n=n, random_state=SEED))
    sample = pd.concat(picks)
    if (sample.rule == "R2").sum() < MIN_R2:
        raise ValueError("Sample has fewer R2 rows than required")
    return sample


def main():
    decisions = pd.read_csv(config.DECISIONS_FILE)
    sample = draw(decisions)
    raw = load_raw()
    raw = raw.assign(cand_idx=raw.groupby("input_row_key").cumcount())
    detail = raw[INPUT_FIELDS + CAND_FIELDS + ["input_row_key", "cand_idx"]]
    out = sample[["input_row_key", "region", "rule", "cand_idx", "veridion_id", "code_version"]].merge(
        detail, on=["input_row_key", "cand_idx"], how="left", validate="one_to_one")
    for column in REVIEW_COLUMNS:
        out[column] = ""
    out.to_csv(config.SPOT_CHECK, index=False)
    print(out.groupby(["region", "rule"]).size().to_string())


if __name__ == "__main__":
    main()
