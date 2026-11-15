"""Compute explainable per-candidate signals, one column per layer.

Location layers get categorical outcomes. The name layer gets raw scores only; its outcome
cut-offs are set in the decision log (D7, D8) after reviewing the score distribution.
"""
import pandas as pd
from rapidfuzz import fuzz

from src.normalize import norm_city, norm_postcode, norm_street, norm_street_number, split_name

SAME, DIFFERENT, UNKNOWN = "same", "different", "unknown"
EXACT, STREET_ONLY = "exact", "street_only"
NAME_LIST_SEPARATOR = "|"
LOCATION_SEPARATOR = " | "
LOCATION_FIELDS = 9  # country code, country, region, city, postcode, street, number, latitude, longitude


def _compare(a, b) -> str:
    if a is None or b is None:
        return UNKNOWN
    return SAME if a == b else DIFFERENT


def _street_outcome(street: str, number: str) -> str:
    if street != SAME:
        return street
    return EXACT if number == SAME else STREET_ONLY


def _candidate_names(row) -> list[tuple[str, str]]:
    names = [("company_name", row.company_name)]
    for source in ("company_legal_names", "company_commercial_names"):
        value = getattr(row, source)
        if isinstance(value, str):
            names += [(source, n.strip()) for n in value.split(NAME_LIST_SEPARATOR) if n.strip()]
    return names


def _locations(value) -> tuple[list[tuple[str, str | None, str | None]], int]:
    """Parse the locations field into (country, city, street) tuples; also count unparsed entries."""
    if not isinstance(value, str):
        return [], 0
    parsed, unparsed = [], 0
    for entry in value.split(LOCATION_SEPARATOR):
        fields = [f.strip() for f in entry.split(",")]
        if len(fields) != LOCATION_FIELDS:
            unparsed += 1
            continue
        parsed.append((fields[0], norm_city(fields[3] or None), norm_street(fields[5] or None)))
    return parsed, unparsed


def score_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (input, candidate) with normalized values and per-layer outcomes."""
    rows = []
    df = df.assign(cand_idx=df.groupby("input_row_key").cumcount())
    for r in df.itertuples(index=False):
        country = r.input_main_country_code
        inp = split_name(r.input_company_name)

        best = None
        for source, name in _candidate_names(r):
            parts = split_name(name)
            sort = fuzz.token_sort_ratio(inp.core, parts.core)
            subset = fuzz.token_set_ratio(inp.core, parts.core)
            if best is None or (sort, subset) > (best[0], best[1]):
                best = (sort, subset, source, name, parts)
        name_sort, name_set, name_source, matched_name, cand = best
        cand_splits = [split_name(n) for _, n in _candidate_names(r)]
        cand_legal = {f for p in cand_splits for f in p.legal_forms}
        cand_legal_countries = set().union(*(p.legal_countries for p in cand_splits))
        cand_country = None if pd.isna(r.main_country_code) else r.main_country_code

        in_city, c_city = norm_city(r.input_main_city), norm_city(r.main_city)
        in_pc = norm_postcode(r.input_main_postcode, country)
        c_pc = norm_postcode(r.main_postcode, r.main_country_code)
        in_st, c_st = norm_street(r.input_main_street), norm_street(r.main_street)
        in_no, c_no = norm_street_number(r.input_main_street_number), norm_street_number(r.main_street_number)
        street, number = _compare(in_st, c_st), _compare(in_no, c_no)

        locs, unparsed = _locations(r.locations)
        rows.append({
            "input_row_key": r.input_row_key,
            "cand_idx": r.cand_idx,
            "veridion_id": r.veridion_id,
            "input_name": r.input_company_name,
            "input_core": inp.core,
            "input_country_code": country,
            "input_legal_forms": " ".join(inp.legal_forms),
            "input_legal_countries": " ".join(sorted(inp.legal_countries)),
            "input_country_words": " ".join(inp.country_words),
            "input_branch": inp.branch,
            "cand_name": r.company_name,
            "cand_matched_name": matched_name,
            "cand_matched_source": name_source,
            "cand_core": cand.core,
            "cand_legal_forms": " ".join(sorted(cand_legal)),
            "cand_legal_countries": " ".join(sorted(cand_legal_countries)),
            "cand_country_code": cand_country,
            "name_sort": name_sort,
            "name_set": name_set,
            "country": _compare(country, cand_country),
            "city": _compare(in_city, c_city),
            "postcode": _compare(in_pc, c_pc),
            "street": _street_outcome(street, number),
            "street_number": number,
            "input_city_norm": in_city,
            "cand_city_norm": c_city,
            "input_postcode_norm": in_pc,
            "cand_postcode_norm": c_pc,
            "input_street_norm": in_st,
            "cand_street_norm": c_st,
            "city_in_other_locations": in_city is not None and any(
                cc == country and city == in_city for cc, city, _ in locs),
            "locations_unparsed": unparsed,
        })
    return pd.DataFrame(rows)
