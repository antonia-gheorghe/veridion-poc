import pandas as pd
import pytest

from src import resolve as r

BASE = {
    "input_row_key": 1, "input_name": "ACME AS", "input_country_code": "NO", "input_core": "ACME",
    "input_legal_countries": "NO", "input_country_words": None, "input_branch": None, "cand_country_words": None,
    "cand_name": "Acme", "cand_matched_name": "Acme", "cand_matched_source": "company_name", "cand_core": "ACME",
    "cand_legal_countries": None, "cand_country_code": "NO",
    "name_sort": 100, "name_set": 100, "country": "same", "city": "same", "postcode": "same",
    "street": "exact", "input_street_norm": "STORGATA", "cand_street_norm": "STORGATA", "cand_city_norm": "OSLO",
    "city_in_other_locations": False, "street_in_other_locations": False,
}


def run(*candidates):
    rows = [BASE | {"cand_idx": i, "veridion_id": f"v{i}"} | c for i, c in enumerate(candidates)]
    return r.resolve(pd.DataFrame(rows)).iloc[0]


@pytest.mark.parametrize("sort, set_, inp, cand, expected", [
    (100, 100, "ACME", "ACME", "exact"),
    (91, 91, "COMBA TECHNOLOGIES", "OM TECHNOLOGIES", "weak"),  # D36: no 90-99 band
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


def test_different_city_alias_match_goes_to_review():  # D30, D34
    out = run({"input_street_norm": None, "street": "unknown", "city": "different",
               "cand_matched_source": "company_commercial_names"})
    assert (out.decision, out.reason) == ("review", "city:different")


def test_different_city_main_name_is_p2():  # D34
    out = run({"input_street_norm": None, "street": "unknown", "city": "different"})
    assert (out.decision, out.rule, out.reason) == ("probable", "P2", "city:different")


def test_different_city_with_input_street_goes_to_review():  # D30
    out = run({"street": "different", "postcode": "different", "city": "different",
               "cand_matched_source": "company_legal_names"})
    assert out.decision == "review"
    assert set(out.reason.split()) == {"street:different", "postcode:different", "city:different"}


def test_same_city_street_gap_is_probable():  # D28
    out = run({"street": "different", "postcode": "different"})
    assert (out.decision, out.rule) == ("probable", "P1")


def test_weak_name_without_address_support_is_unmatched():  # D32
    out = run({"name_sort": 70, "name_set": 70, "cand_core": "ACMEX", "city": "different",
               "input_street_norm": None, "street": "unknown"})
    assert (out.decision, out.rule) == ("unmatched", "U1")


def test_weak_name_in_same_city_stays_review():  # D32
    out = run({"name_sort": 70, "name_set": 70, "cand_core": "ACMEX",
               "input_street_norm": None, "street": "unknown"})
    assert (out.decision, out.reason) == ("review", "name:weak")


def test_any_supported_candidate_blocks_unmatched():  # D32
    out = run({"name_sort": 70, "name_set": 70, "cand_core": "ACMEX", "city": "different", "street": "different"},
              {"name_sort": 60, "name_set": 60, "cand_core": "ACMY", "street": "different"})
    assert out.decision == "review"


def test_address_gap_with_rival_stays_review():
    out = run({"street": "different"}, {"street": "different", "cand_city_norm": "BAERUM"})
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
    out = run({}, {"cand_city_norm": "BAERUM"})
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
    out = run({"cand_matched_source": "company_legal_names"},
              {"cand_matched_source": "company_legal_names", "street": "different", "city": "different",
               "cand_street_norm": "NYGATA"})
    assert out.decision == "review" and out.reason == "rival:1"


def test_main_name_match_beats_alias_match():  # D31
    out = run({"cand_matched_source": "company_legal_names"}, {"street": "different", "postcode": "different"})
    assert (out.veridion_id, out.decision, out.rival_ids) == ("v1", "probable", "")


def test_duplicate_records_pick_engine_first():  # D33
    out = run({"street": "different", "postcode": "different", "cand_street_norm": "NYGATA"},
              {"street": "different", "postcode": "different", "cand_street_norm": "NYGATA"})
    assert (out.decision, out.rule, out.veridion_id) == ("probable", "P3", "v0")
    assert set(out.reason.split()) == {"street:different", "postcode:different", "duplicate:1"}


def test_duplicate_of_exact_match_is_probable_not_auto():  # D33
    out = run({}, {})
    assert (out.decision, out.rule, out.reason) == ("probable", "P3", "duplicate:1")


def test_alias_match_without_other_good_name_is_auto():
    out = run({"cand_matched_source": "company_commercial_names"},
              {"name_sort": 30, "name_set": 30, "cand_core": "ZETA"})
    assert out.decision == "auto"


def test_candidate_country_word_conflict():  # D35
    out = run({"cand_country_words": "SE"})
    assert out.decision == "review" and "country_word:conflict" in out.reason


def test_candidate_country_word_matching_input_country():
    assert run({"cand_country_words": "NO"}).decision == "auto"


@pytest.mark.parametrize("candidate, confidence", [
    ({}, "high"),
    ({"postcode": "different"}, "medium"),
    ({"name_sort": 70, "name_set": 70, "cand_core": "ACMEX"}, "none"),
])
def test_confidence_follows_decision(candidate, confidence):  # D40
    assert run(candidate).confidence == confidence
