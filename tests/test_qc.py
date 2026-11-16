import pandas as pd
import pytest

from src import qc

SNAPSHOT = pd.Timestamp("2025-04-21", tz="UTC")
RECORD = {
    "input_row_key": 1, "veridion_id": "v1", "main_country_code": "NO", "main_postcode": "0250",
    "main_street": "Storgata", "main_street_number": "3", "website_domain": "acme.no", "primary_email": "post@acme.no",
    "employee_count": 10.0, "revenue": 2_000_000.0, "naics_2022_primary_code": 541611.0, "year_founded": 1990.0,
    "last_updated_at": "2025-01-01T00:00:00Z",
}


def checks(**fields):
    flags = qc.rule_flags(pd.DataFrame([RECORD | fields]), SNAPSHOT)
    return {(f["check"], f["severity"]) for f in flags}


def test_clean_record_has_no_flags():
    assert checks() == set()


def test_missing_required_field_is_info():
    assert checks(website_domain=None, primary_email=None) == {("missing", "info")}


def test_date_in_street_number_is_error():  # CBRE Blytækkervej '2026-01-07 00:00:00'
    assert ("date_in_street_number", "error") in checks(main_street_number="2026-01-07 00:00:00")


@pytest.mark.parametrize("revenue, flagged", [
    (99_000, True),       # 9,900 per employee
    (100_000, False),     # 10,000 per employee
    (50_000_000, False),  # 5M per employee
    (60_000_000, True),
])
def test_revenue_per_employee_bounds(revenue, flagged):
    assert (("revenue_per_employee", "warning") in checks(revenue=revenue)) == flagged


def test_stale_record_is_measured_from_snapshot():
    assert ("stale_record", "warning") in checks(last_updated_at="2023-04-20T00:00:00Z")
    assert ("stale_record", "warning") not in checks(last_updated_at="2023-04-22T00:00:00Z")


def test_founding_year_before_1800_is_warning():
    assert ("founded_before_1800", "warning") in checks(year_founded=1647.0)


def test_founding_year_after_snapshot_is_error():
    assert ("founded_after_snapshot", "error") in checks(year_founded=2026.0)


def test_postcode_that_lost_its_leading_zero():  # Norwegian '668' for 0668
    assert ("postcode_length", "warning") in checks(main_postcode=668.0)


def test_postcode_with_space_is_not_flagged():  # Swedish '169 67'
    assert checks(main_country_code="SE", main_postcode="169 67") == set()


@pytest.mark.parametrize("email, site, flagged", [
    ("post@adecco.com", "adecco.com.sg", False),
    ("info@aia-premier.com.my", "aia.com.my", True),
    ("x@atea.com", "atea.no", False),
])
def test_email_domain_compares_brand_label(email, site, flagged):
    assert (("email_domain_differs", "info") in checks(primary_email=email, website_domain=site)) == flagged


@pytest.mark.parametrize("veridion, official, agree", [
    (1, 24, False),        # Extenda Retail
    (3, 7, True),          # within 5 people
    (100, 200, True),      # exactly 2x
    (100, 201, False),
    (135000, 88, False),   # group headcount on a national entity
    (None, 50, None),
])
def test_employees_agree(veridion, official, agree):
    assert qc.employees_agree(veridion, official) == agree


def test_nace_divisions():
    assert qc.nace_divisions("62.01 | 70.22") == {"62", "70"}
    assert qc.nace_divisions(1.1) == {"01"}
