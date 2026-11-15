import pandas as pd
import pytest

from src import resolve as r

BASE = {
    "input_row_key": 1, "input_name": "ACME AS", "input_country_code": "NO", "input_core": "ACME",
    "input_legal_countries": "NO", "input_country_words": None, "input_branch": None,
    "cand_name": "Acme", "cand_matched_name": "Acme", "cand_core": "ACME",
    "cand_legal_countries": None, "cand_country_code": "NO",
    "name_sort": 100, "name_set": 100, "country": "same", "city": "same", "postcode": "same",
    "street": "exact", "input_street_norm": "STORGATA", "cand_street_norm": "STORGATA",
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


def test_r1_postcode_different_goes_to_review():  # D23
    out = run({"postcode": "different"})
    assert out.decision == "review" and "postcode:different" in out.reason


def test_r2_auto_without_input_street():
    out = run({"input_street_norm": None, "street": "unknown", "postcode": "unknown"})
    assert (out.decision, out.rule) == ("auto", "R2")


def test_candidate_without_street_goes_to_review():  # D18
    out = run({"cand_street_norm": None, "street": "unknown"})
    assert out.reason == "street:candidate_missing"


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
