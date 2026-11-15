from src.registry import CURRENT, FORMER, Record, accept


def record(name, source="brreg", registry_id="111", cities=("OSLO",), status="active", former=(), national_id=None):
    return Record(source=source, registry_id=registry_id, name=name, status=status, url=f"https://x/{registry_id}",
                  names=[(name, CURRENT)] + [(f, FORMER) for f in former], cities=set(cities),
                  national_id=national_id or registry_id)


def test_same_core_and_legal_form_in_same_city_is_high():  # D54
    out = accept("Acme Consulting AS", "OSLO", [record("ACME CONSULTING AS")], [])
    assert (out["outcome"], out["registry_id"], out["match_basis"], out["confidence"]) == (
        "matched", "brreg:111", CURRENT, "high")


def test_other_city_is_medium():  # D54
    assert accept("Acme Consulting AS", "BERGEN", [record("ACME CONSULTING AS")], [])["confidence"] == "medium"


def test_input_without_city_is_medium():  # D54
    assert accept("Acme Consulting AS", None, [record("ACME CONSULTING AS")], [])["confidence"] == "medium"


def test_different_legal_form_is_no_hit():  # D54
    assert accept("Acme Consulting AS", "OSLO", [record("ACME CONSULTING ASA")], [])["outcome"] == "no_hit"


def test_longer_name_is_no_hit():  # D54
    assert accept("Acme AS", "OSLO", [record("ACME CONSULTING AS")], [])["outcome"] == "no_hit"


def test_two_passing_records_are_ambiguous():  # D54
    out = accept("Acme AS", "OSLO", [record("ACME AS"), record("ACME AS", registry_id="222")], [])
    assert out["outcome"] == "ambiguous"


def test_former_name_match_is_labelled():  # D54
    out = accept("Oldname AS", "OSLO", [record("NEWNAME AS", former=["OLDNAME AS"])], [])
    assert (out["outcome"], out["company_name"], out["match_basis"]) == ("matched", "NEWNAME AS", FORMER)


def test_dissolved_company_is_accepted_with_status():  # D54
    out = accept("Acme AS", "OSLO", [record("ACME AS", status="deleted")], [])
    assert (out["outcome"], out["registry_status"]) == ("matched", "deleted")


def test_national_and_gleif_agree_keeps_both_ids():  # D54
    lei = record("ACME AS", source="gleif", registry_id="LEI1", national_id="111")
    out = accept("Acme AS", "OSLO", [record("ACME AS")], [lei])
    assert (out["outcome"], out["registry_id"], out["source"]) == ("matched", "brreg:111; gleif:LEI1", "brreg+gleif")


def test_national_and_gleif_disagree_is_ambiguous():  # D54
    lei = record("ACME AS", source="gleif", registry_id="LEI1", national_id="999")
    assert accept("Acme AS", "OSLO", [record("ACME AS")], [lei])["outcome"] == "ambiguous"


def test_gleif_alone_matches():  # D54
    lei = record("ACME PTE. LTD.", source="gleif", registry_id="LEI1", cities=("SINGAPORE",))
    out = accept("Acme Pte Ltd", "SINGAPORE", [], [lei])
    assert (out["outcome"], out["registry_id"], out["confidence"]) == ("matched", "gleif:LEI1", "high")
