"""Write the client-ready dataset and summary stats to data/output/."""
import pandas as pd

from src import config, qc

MATCHED, UNMATCHED = "matched", "unmatched"
EXTERNAL_DECISION = "external"
STATUS = {"auto": MATCHED, "probable": MATCHED, "manual": MATCHED, "external": MATCHED,
          "unmatched": UNMATCHED, "no_candidate": UNMATCHED}
INPUT_COLUMNS = {"input_company_name": "input_name", "input_main_country_code": "input_country",
                 "input_main_city": "input_city", "input_main_street": "input_street",
                 "input_main_street_number": "input_street_number", "input_main_postcode": "input_postcode"}
RECORD_COLUMNS = {"company_name": "company_name", "website_domain": "website", "main_country_code": "country",
                  "main_city": "city", "employee_count": "employees", "revenue": "revenue",
                  "naics_2022_primary_code": "naics_code", "naics_2022_primary_label": "naics_label",
                  "nace_rev2_codes": "nace_codes", "year_founded": "year_founded"}
INTEGER_COLUMNS = ["employees", "revenue", "naics_code", "year_founded"]
FLAGGED_SEVERITIES = [qc.ERROR, qc.WARNING]


def build(decisions: pd.DataFrame, raw: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """One row per supplier: input, status, matched company, key attributes and QC flags."""
    inputs = raw.drop_duplicates("input_row_key").set_index("input_row_key")[list(INPUT_COLUMNS)].rename(
        columns=INPUT_COLUMNS)
    records = raw.set_index(["input_row_key", "veridion_id"])[list(RECORD_COLUMNS)].rename(columns=RECORD_COLUMNS)
    out = decisions[["input_row_key", "decision", "rule", "confidence", "reason", "veridion_id", "related_veridion_id",
                     "registry_id", "registry_status", "external_company_name", "external_evidence_url"]].copy()
    unknown = set(out.decision) - set(STATUS)
    if unknown:
        raise ValueError(f"Decisions without a status: {sorted(unknown)}")
    out.insert(1, "status", out.decision.map(STATUS))
    # Unmatched rows keep only the rejection reason and evidence link, not a company or id.
    out.loc[out.status != MATCHED, ["veridion_id", "registry_id", "registry_status", "external_company_name"]] = None
    # External matches have no Veridion pick; their veridion_id is the rejected best candidate.
    out.loc[out.decision == EXTERNAL_DECISION, "veridion_id"] = None
    out = out.join(inputs, on="input_row_key")
    out = out.join(records, on=["input_row_key", "veridion_id"])
    out["company_name"] = out.company_name.fillna(out.external_company_name)
    for column in INTEGER_COLUMNS:
        out[column] = out[column].round().astype("Int64")
    out = out.drop(columns="external_company_name")

    shown = flags[flags.severity.isin(FLAGGED_SEVERITIES)]
    per_input = shown.groupby("input_row_key").agg(
        qc_errors=("severity", lambda s: int((s == qc.ERROR).sum())),
        qc_warnings=("severity", lambda s: int((s == qc.WARNING).sum())),
        qc_flags=("check", lambda s: "; ".join(sorted(set(s)))))
    out = out.join(per_input, on="input_row_key")
    out[["qc_errors", "qc_warnings"]] = out[["qc_errors", "qc_warnings"]].fillna(0).astype(int)

    registry_id = out.registry_id.replace("", None)
    entity = out.veridion_id.where(out.veridion_id.notna(), registry_id).where(out.status == MATCHED)
    groups = out.groupby(entity).input_row_key.agg(lambda keys: sorted(keys))
    out["same_veridion_record_as"] = [
        "; ".join(str(k) for k in groups[e] if k != key) if isinstance(e, str) else ""
        for key, e in zip(out.input_row_key, entity)]
    front = ["input_row_key", "status", "confidence", "input_name", "input_country", "input_city", "company_name",
             "country", "city", "website", "employees", "revenue", "naics_code", "naics_label", "nace_codes",
             "year_founded", "registry_id", "registry_status", "same_veridion_record_as", "qc_errors", "qc_warnings",
             "qc_flags"]
    return out[front + [c for c in out.columns if c not in front]]


def summary(dataset: pd.DataFrame) -> pd.DataFrame:
    return dataset.groupby(["status", "decision", "rule", "confidence"], dropna=False).size().rename(
        "suppliers").reset_index()


def write(dataset: pd.DataFrame) -> None:
    dataset.to_csv(config.SUPPLIERS_CSV, index=False)
    with pd.ExcelWriter(config.SUPPLIERS_XLSX) as writer:
        dataset.to_excel(writer, sheet_name="suppliers", index=False)
        summary(dataset).to_excel(writer, sheet_name="summary", index=False)
