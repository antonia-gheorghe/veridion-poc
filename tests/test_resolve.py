import pandas as pd
import pytest

from src import resolve as r

BASE = {
    "input_row_key": 1, "input_name": "ACME AS", "input_country_code": "NO", "input_core": "ACME",
    "input_legal_countries": "NO", "input_country_words": None, "input_branch": None,
    "cand_name": "Acme", "cand_matched_name": "Acme", "cand_matched_source": "company_name", "cand_core": "ACME",
    "cand_legal_countries": None, "cand_country_code": "NO",
    "name_sort": 100, "name_set": 100, "country": "same", "city": "same", "postcode": "same",
    "street": "exact", "input_street_norm": "STORGATA", "cand_street_norm": "STORGATA",
    "city_in_other_locations": False, "street_in_other_locations": False,
}


def run(*candidates):
    rows = [BASE | {"cand_idx": i, "veridion_id": f"v{i}"} | c for i, c in enumerate(candidates)]
    return r.resolve(pd.DataFrame(rows)).iloc[0]


@pytest.mark.parametrize("sort, set_, inp, cand, expected", [
    (100, 100, "ACME", "ACME", "exact"),
    (91, 91, "ACME CORP", "ACME COPR", "strong"),
    (95, 100, "ACME", "ACME GLOBAL", "weak"),        # D15 subset
    (89, 89, "ACME", "ACMEE", "weak"),
    (60, 70, "A T KEARNEY", "ATKEARNEY", "strong"),   # D16
    (49, 49, "ACME", "ZETA", "none"),
])
def test_name_outcome(sort, set_, inp, cand, expected):
    row = pd.Series({"name_sort": sort, "name_set": set_, "input_core": inp, "cand_core": cand})
    assert r.name_outcome(row) == expected


def test_r1_auto():
    out = run({})
    assert (out.decision, out.rule, out.veridion_id) == ("auto", "R1", "v0")


def test_r1_street_and_postcode_without_number():
    assert run({"street": "street_only"}).rule == "R1"


def test_r1_postcode_different_is_probable():  # D23, D28
    out = run({"postcode": "different"})
    assert (out.decision, out.rule, out.reason) == ("probable", "P1", "postcode:different")


def test_r2_auto_without_input_street():
    out = run({"input_street_norm": None, "street": "unknown", "postcode": "unknown"})
    assert (out.decision, out.rule) == ("auto", "R2")


def test_candidate_without_street_is_probable():  # D18, D28
    out = run({"cand_street_norm": None, "street": "unknown"})
    assert (out.decision, out.reason) == ("probable", "street:candidate_missing")


def test_different_city_goes_to_review():  # D30
    out = run({"input_street_norm": None, "street": "unknown", "city": "different"})
    assert (out.decision, out.reason) == ("review", "city:different")


def test_different_city_with_input_street_goes_to_review():  # D30
    out = run({"street": "different", "postcode": "different", "city": "different"})
    assert out.decision == "review"
    assert set(out.reason.split()) == {"street:different", "postcode:different", "city:different"}


def test_same_city_street_gap_is_probable():  # D28
    out = run({"street": "different", "postcode": "different"})
    assert (out.decision, out.rule) == ("probable", "P1")


def test_address_gap_with_weak_name_stays_review():
    out = run({"name_sort": 70, "name_set": 70, "cand_core": "ACMEX", "city": "different",
               "input_street_norm": None, "street": "unknown"})
    assert out.decision == "review"


def test_address_gap_with_rival_stays_review():
    out = run({"street": "different"}, {"street": "different"})
    assert out.decision == "review" and "rival:1" in out.reason


def test_legal_conflict():  # D17
    out = run({"cand_legal_countries": "SE"})
    assert out.decision == "review" and "legal:conflict" in out.reason


def test_generic_legal_form_never_conflicts():
    assert run({"input_legal_countries": None, "cand_legal_countries": "SE"}).decision == "auto"


def test_country_word_conflict():  # D21
    out = run({"input_country_words": "SE"})
    assert out.decision == "review" and "country_word:conflict" in out.reason


def test_branch_goes_to_review():  # D20
    assert run({"input_branch": "FILIAL"}).reason == "branch"


def test_rival_with_equal_location():  # D19
    out = run({}, {})
    assert out.decision == "review" and out.reason == "rival:1" and out.veridion_id == "v0"


def test_weaker_location_is_not_rival():
    out = run({}, {"street": "different", "city": "same"})
    assert (out.decision, out.veridion_id, out.rival_ids) == ("auto", "v0", "")


def test_better_location_wins_pick():
    out = run({"street": "different"}, {})
    assert out.veridion_id == "v1" and out.decision == "auto"


def test_r3_no_candidate():
    out = run({"name_sort": 30, "name_set": 30, "cand_core": "ZETA"})
    assert (out.decision, out.rule) == ("no_candidate", "R3")


def test_only_foreign_candidates_with_good_name():
    assert run({"country": "different"}).decision == "no_candidate"


def test_unknown_country_candidate_goes_to_review():
    out = run({"country": "unknown", "cand_country_code": None})
    assert out.reason == "no_same_country_candidate"


def test_alias_match_with_other_good_name_is_rival():  # D25
    out = run({"cand_matched_source": "company_legal_names"}, {"street": "different", "city": "different"})
    assert out.decision == "review" and out.reason == "rival:1"


def test_alias_match_without_other_good_name_is_auto():
    out = run({"cand_matched_source": "company_commercial_names"},
              {"name_sort": 30, "name_set": 30, "cand_core": "ZETA"})
    assert out.decision == "auto"
