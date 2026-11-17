import pandas as pd

from src import export, qc

DECISION = {"rule": "R1", "confidence": "high", "reason": "", "related_veridion_id": "", "registry_id": None,
            "registry_status": None, "external_company_name": None, "external_evidence_url": None}
RAW = {"input_company_name": "ACME AS", "input_main_country_code": "NO", "input_main_city": "Oslo",
       "input_main_street": "Storgata", "input_main_street_number": "3", "input_main_postcode": "0250",
       "company_name": "Acme", "website_domain": "acme.no", "main_country_code": "NO", "main_city": "Oslo",
       "employee_count": 10.0, "revenue": 2_000_000.0, "naics_2022_primary_code": 541611.0,
       "naics_2022_primary_label": "Consulting", "nace_rev2_codes": "70.22", "year_founded": 1990.0}


def build(decisions, flags=None):
    raw = pd.DataFrame([RAW | {"input_row_key": d["input_row_key"], "veridion_id": d["veridion_id"]} for d in decisions])
    flags = pd.DataFrame(flags or [], columns=qc.FLAG_COLUMNS)
    return export.build(pd.DataFrame([DECISION | d for d in decisions]), raw, flags).set_index("input_row_key")


def test_matched_row_shows_the_company():
    out = build([{"input_row_key": 1, "decision": "auto", "veridion_id": "v1"}])
    assert (out.loc[1, "status"], out.loc[1, "company_name"], out.loc[1, "employees"]) == ("matched", "Acme", 10)


def test_unmatched_row_shows_no_company():  # the rejected best candidate must not look like a match
    out = build([{"input_row_key": 1, "decision": "unmatched", "veridion_id": "v1"}])
    assert out.loc[1, "status"] == "unmatched" and pd.isna(out.loc[1, "company_name"])


def test_unmatched_row_with_aggregator_evidence_shows_no_company():  # D64
    out = build([{"input_row_key": 1, "decision": "unmatched", "veridion_id": None, "registry_id": "se:556262-9716",
                  "external_company_name": "Egencia Sweden AB", "external_evidence_url": "https://www.allabolag.se/x"}])
    assert pd.isna(out.loc[1, "company_name"]) and pd.isna(out.loc[1, "registry_id"])
    assert out.loc[1, "external_evidence_url"] == "https://www.allabolag.se/x"


def test_external_match_shows_the_registry_company_not_the_rejected_candidate():
    out = build([{"input_row_key": 1, "decision": "external", "veridion_id": "v1", "registry_id": "brreg:111",
                  "external_company_name": "ACME AS"},
                 {"input_row_key": 2, "decision": "auto", "veridion_id": "v1"}])
    assert (out.loc[1, "company_name"], out.loc[1, "registry_id"]) == ("ACME AS", "brreg:111")
    assert pd.isna(out.loc[1, "employees"]) and pd.isna(out.loc[1, "website"])
    assert out.loc[2, "same_veridion_record_as"] == ""


def test_external_matches_without_registry_id_are_not_grouped():
    out = build([{"input_row_key": 1, "decision": "external", "veridion_id": None, "registry_id": ""},
                 {"input_row_key": 2, "decision": "external", "veridion_id": None, "registry_id": ""}])
    assert out.same_veridion_record_as.tolist() == ["", ""]


def test_unknown_decision_fails():
    try:
        build([{"input_row_key": 1, "decision": "lead", "veridion_id": "v1"}])
    except ValueError:
        return
    raise AssertionError("a decision without a status must not be exported")


def test_inputs_on_one_record_point_to_each_other():
    out = build([{"input_row_key": 1, "decision": "auto", "veridion_id": "v1"},
                 {"input_row_key": 2, "decision": "manual", "veridion_id": "v1"},
                 {"input_row_key": 3, "decision": "unmatched", "veridion_id": "v1"}])
    assert out.same_veridion_record_as.tolist() == ["2", "1", ""]


def test_info_flags_are_not_counted():
    flags = [{"input_row_key": 1, "veridion_id": "v1", "check": "missing", "severity": qc.INFO},
             {"input_row_key": 1, "veridion_id": "v1", "check": "stale_record", "severity": qc.WARNING}]
    out = build([{"input_row_key": 1, "decision": "auto", "veridion_id": "v1"}], flags)
    assert (out.loc[1, "qc_errors"], out.loc[1, "qc_warnings"], out.loc[1, "qc_flags"]) == (0, 1, "stale_record")
