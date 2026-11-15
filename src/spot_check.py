"""Draw spot-check samples: auto-matches (D9, D24) and the probable tier (D29)."""
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
PROBABLE_SAMPLE = {"different_city": 7, "same_city": 5, "input_no_city_or_street": 2, "candidate_address_missing": 1}
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


def probable_kind(row) -> str:
    if not isinstance(row.input_city_norm, str) and not isinstance(row.input_street_norm, str):
        return "input_no_city_or_street"
    if row.city == "same":
        return "same_city"
    if row.city == "different":
        return "different_city"
    return "candidate_address_missing"


def draw_probable(decisions: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    probable = decisions[decisions.decision == "probable"].merge(
        features[["input_row_key", "cand_idx", "input_city_norm", "input_street_norm"]],
        on=["input_row_key", "cand_idx"], how="left", validate="one_to_one")
    probable["kind"] = probable.apply(probable_kind, axis=1)
    return pd.concat(probable[probable.kind == kind].sample(n=n, random_state=SEED)
                     for kind, n in PROBABLE_SAMPLE.items())


def _with_details(sample: pd.DataFrame, keep: list[str]) -> pd.DataFrame:
    raw = load_raw()
    raw = raw.assign(cand_idx=raw.groupby("input_row_key").cumcount())
    detail = raw[INPUT_FIELDS + CAND_FIELDS + ["input_row_key", "cand_idx"]]
    out = sample[keep].merge(detail, on=["input_row_key", "cand_idx"], how="left", validate="one_to_one")
    for column in REVIEW_COLUMNS:
        out[column] = ""
    return out


def main_probable():
    decisions = pd.read_csv(config.DECISIONS_FILE)
    features = pd.read_csv(config.FEATURES_FILE)
    sample = draw_probable(decisions, features)
    keep = ["input_row_key", "kind", "rule", "reason", "cand_idx", "veridion_id",
            "city_in_other_locations", "street_in_other_locations", "code_version"]
    out = _with_details(sample, keep)
    out.to_csv(config.PROBABLE_CHECK, index=False)
    print(out.kind.value_counts().to_string())


def main():
    decisions = pd.read_csv(config.DECISIONS_FILE)
    sample = draw(decisions)
    out = _with_details(sample, ["input_row_key", "region", "rule", "cand_idx", "veridion_id", "code_version"])
    out.to_csv(config.SPOT_CHECK, index=False)
    print(out.groupby(["region", "rule"]).size().to_string())


if __name__ == "__main__":
    main()
