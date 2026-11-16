"""Consistency checks on the matched Veridion records (flag, don't silently fix)."""
import re

import pandas as pd
import requests

from src import config, registry
from src.normalize import norm_postcode, split_name

MATCHED_DECISIONS = {"auto", "probable", "manual"}
ERROR, WARNING, INFO = "error", "warning", "info"
RULE, BRREG, MANUAL = "rule", "brreg", "manual review"
FLAG_COLUMNS = ["input_row_key", "veridion_id", "attribute", "check", "severity", "value", "evidence", "source"]

REQUIRED_FIELDS = ["website_domain", "employee_count", "revenue", "naics_2022_primary_code", "main_street",
                   "main_postcode"]
REVENUE_PER_EMPLOYEE_MIN, REVENUE_PER_EMPLOYEE_MAX = 10_000, 5_000_000
STALE_YEARS = 2
FOUNDED_MIN = 1800
EMPLOYEE_RATIO_MAX, EMPLOYEE_DIFF_MIN = 2, 5
NACE_DIVISION_DIGITS = 2
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}")
# Second-level labels before a country code, as in adecco.com.sg.
SECOND_LEVEL_LABELS = {"ac", "co", "com", "gov", "net", "org"}
BRREG_COUNTRY = "NO"


def matched_records(decisions: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """The picked Veridion record of every input matched to one (auto, probable, manual)."""
    picks = decisions[decisions.decision.isin(MATCHED_DECISIONS) & decisions.veridion_id.notna()]
    return picks[["input_row_key", "veridion_id"]].merge(raw, on=["input_row_key", "veridion_id"], how="left")


def _flag(r, attribute, check, severity, value, evidence="", source=RULE) -> dict:
    return {"input_row_key": r.input_row_key, "veridion_id": r.veridion_id, "attribute": attribute, "check": check,
            "severity": severity, "value": value, "evidence": evidence, "source": source}


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or (isinstance(value, str) and not value.strip())


def brand_label(domain) -> str | None:
    """Registrable name of a domain or email domain: adecco for adecco.com.sg."""
    if _missing(domain):
        return None
    parts = str(domain).lower().strip().split("@")[-1].split(".")
    if len(parts) >= 3 and parts[-2] in SECOND_LEVEL_LABELS:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]


def _postcode_text(value) -> str | None:
    if _missing(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s", "", str(value))


def rule_flags(records: pd.DataFrame, snapshot: pd.Timestamp) -> list[dict]:
    digits = pd.read_csv(config.POSTCODE_DIGITS).set_index("country_code").digits.to_dict()
    stale_before = snapshot - pd.DateOffset(years=STALE_YEARS)
    flags = []
    for r in records.itertuples():
        for field in REQUIRED_FIELDS:
            if _missing(getattr(r, field)):
                flags.append(_flag(r, field, "missing", INFO, ""))
        if not _missing(r.main_street_number) and DATE_PATTERN.match(str(r.main_street_number)):
            flags.append(_flag(r, "main_street_number", "date_in_street_number", ERROR, str(r.main_street_number)))
        if not _missing(r.year_founded):
            if r.year_founded < FOUNDED_MIN:
                flags.append(_flag(r, "year_founded", "founded_before_1800", WARNING, int(r.year_founded)))
            elif r.year_founded > snapshot.year:
                flags.append(_flag(r, "year_founded", "founded_after_snapshot", ERROR, int(r.year_founded)))
        postcode, expected = _postcode_text(r.main_postcode), digits.get(r.main_country_code)
        if postcode and postcode.isdigit() and expected and len(postcode) != expected:
            flags.append(_flag(r, "main_postcode", "postcode_length", WARNING, postcode,
                               f"{r.main_country_code} postcodes have {expected} digits"))
        if not _missing(r.revenue) and not _missing(r.employee_count) and r.employee_count > 0:
            per_employee = r.revenue / r.employee_count
            if not REVENUE_PER_EMPLOYEE_MIN <= per_employee <= REVENUE_PER_EMPLOYEE_MAX:
                flags.append(_flag(r, "revenue", "revenue_per_employee", WARNING, round(per_employee),
                                   f"revenue {r.revenue:.0f} / {r.employee_count:.0f} employees"))
        updated = pd.to_datetime(r.last_updated_at, utc=True, errors="coerce")
        if pd.notna(updated) and updated < stale_before:
            flags.append(_flag(r, "last_updated_at", "stale_record", WARNING, updated.date().isoformat(),
                               f"more than {STALE_YEARS} years before the newest record ({snapshot.date()})"))
        email, site = brand_label(r.primary_email), brand_label(r.website_domain)
        if email and site and email != site:
            flags.append(_flag(r, "primary_email", "email_domain_differs", INFO, r.primary_email,
                               f"website {r.website_domain}"))
    return flags


def nace_divisions(value) -> set[str]:
    if _missing(value):
        return set()
    codes = re.split(r"[|,;]", str(value))
    return {c.strip().split(".")[0].zfill(NACE_DIVISION_DIGITS) for c in codes if c.strip()}


def employees_agree(veridion, official) -> bool | None:
    if _missing(veridion) or _missing(official):
        return None
    low, high = sorted([float(veridion), float(official)])
    return high - low < EMPLOYEE_DIFF_MIN or high <= EMPLOYEE_RATIO_MAX * low


def _brreg_entity(input_name: str) -> tuple[dict | None, str]:
    """Brreg unit whose name and legal form equal the input's, or the reason there is none."""
    records, issue = registry._lookup(registry.query_brreg, split_name(input_name).core)
    if issue:
        return None, issue
    result = registry.accept(input_name, None, records, [])
    if result["outcome"] != registry.MATCHED:
        return None, result["outcome"]
    org = result["registry_id"].split(":", 1)[1]
    try:
        return registry._get("brreg", f"{registry.BRREG_URL}/{org}", {}), ""
    except requests.RequestException as exc:
        return None, f"{registry.ERROR_PREFIX} {exc}"


def brreg_sample(records: pd.DataFrame) -> pd.DataFrame:
    """Compare Norwegian records with Brreg: employees, NACE division, postcode, status."""
    rows = []
    for r in records[records.input_main_country_code == BRREG_COUNTRY].itertuples():
        entity, issue = _brreg_entity(r.input_company_name)
        row = {"input_row_key": r.input_row_key, "veridion_id": r.veridion_id, "input_name": r.input_company_name,
               "lookup": issue or "matched"}
        if entity:
            address = entity.get("forretningsadresse") or {}
            official_nace = (entity.get("naeringskode1") or {}).get("kode")
            official_postcode = address.get("postnummer")
            veridion_postcode = norm_postcode(_postcode_text(r.main_postcode), BRREG_COUNTRY)
            veridion_nace = nace_divisions(r.nace_rev2_codes)
            row |= {
                "orgnr": entity["organisasjonsnummer"], "brreg_name": entity["navn"],
                "brreg_status": registry._brreg_status(entity),
                "brreg_employees": entity.get("antallAnsatte"), "veridion_employees": r.employee_count,
                "employees_agree": employees_agree(r.employee_count, entity.get("antallAnsatte")),
                "brreg_nace": official_nace, "veridion_nace": " ".join(sorted(veridion_nace)),
                "nace_agree": (official_nace[:NACE_DIVISION_DIGITS] in veridion_nace)
                if official_nace and veridion_nace else None,
                "brreg_postcode": official_postcode, "veridion_postcode": veridion_postcode,
                "postcode_agree": official_postcode == veridion_postcode
                if official_postcode and veridion_postcode else None,
            }
        rows.append(row)
    return pd.DataFrame(rows)


def brreg_flags(sample: pd.DataFrame) -> list[dict]:
    flags = []
    if "orgnr" not in sample:
        return flags
    for r in sample[sample.orgnr.notna()].itertuples():
        evidence = f"Brreg {r.orgnr} {r.brreg_name}"
        if r.employees_agree is False:
            flags.append(_flag(r, "employee_count", "registry_employees_differ", ERROR, r.veridion_employees,
                               f"{evidence}: {r.brreg_employees} employees", BRREG))
        if r.nace_agree is False:
            flags.append(_flag(r, "nace_rev2_codes", "registry_nace_differs", ERROR, r.veridion_nace,
                               f"{evidence}: NACE {r.brreg_nace}", BRREG))
        if r.postcode_agree is False:
            flags.append(_flag(r, "main_postcode", "registry_postcode_differs", ERROR, r.veridion_postcode,
                               f"{evidence}: postcode {r.brreg_postcode}", BRREG))
        if r.brreg_status != "active":
            flags.append(_flag(r, "status", "registry_not_active", ERROR, "", f"{evidence}: {r.brreg_status}", BRREG))
    return flags


def manual_flags(records: pd.DataFrame) -> list[dict]:
    """Problems verified by hand (data/manual/qa_findings.csv); each must concern a matched record."""
    findings = pd.read_csv(config.QA_FINDINGS, dtype=str, keep_default_na=False)
    known = set(zip(records.input_row_key.astype(str), records.veridion_id))
    unknown = [(k, v) for k, v in zip(findings.input_row_key, findings.veridion_id) if (k, v) not in known]
    if unknown:
        raise ValueError(f"QA findings for records that are not matched picks: {unknown}")
    findings = findings.assign(input_row_key=findings.input_row_key.astype(int), source=MANUAL)
    return findings[FLAG_COLUMNS].to_dict("records")


def run(decisions: pd.DataFrame, raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = matched_records(decisions, raw)
    snapshot = pd.to_datetime(raw.last_updated_at, utc=True, errors="coerce").max()
    sample = brreg_sample(records)
    flags = rule_flags(records, snapshot) + brreg_flags(sample) + manual_flags(records)
    return pd.DataFrame(flags, columns=FLAG_COLUMNS), sample
