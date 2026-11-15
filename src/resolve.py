"""Pick one match per input with fail-safe rules R1 to R4 (docs/decisions.md D12 to D22).

Every input gets a decision, the rule that produced it, and the layer outcomes behind it.
"""
import subprocess

import pandas as pd

from src import config
from src.score import DIFFERENT, EXACT, SAME, STREET_ONLY, UNKNOWN

AUTO, PROBABLE, NO_CANDIDATE, REVIEW, UNMATCHED = "auto", "probable", "no_candidate", "review", "unmatched"
MANUAL, EXTERNAL = "manual", "external"
CONFIDENCE = {AUTO: "high", MANUAL: "high", PROBABLE: "medium", REVIEW: "none", UNMATCHED: "none", NO_CANDIDATE: "none"}
# Registry or research matches for inputs with no Veridion pick (D54); confidence comes from the file.
EXTERNAL_FIELDS = {"source": "external_source", "registry_id": "registry_id", "company_name": "external_company_name",
                   "registry_status": "registry_status", "match_basis": "external_match_basis",
                   "evidence_url": "external_evidence_url"}
MANUAL_MATCH, MANUAL_UNMATCHED = "match", "unmatched"
# Rules whose sample check found an error keep their decision but get a lower confidence (D51).
CONFIDENCE_BY_RULE = {"R5": "medium"}
# Pick fields that a manual decision replaces.
PICK_FIELDS = ["cand_idx", "veridion_id", "cand_name", "cand_matched_name", "cand_matched_source", "name_outcome",
               "name_sort", "legal", "country_word", "country", "city", "postcode", "street"]
# Reasons that only describe an address gap; a pick failing on these alone is "probable" (P1).
LOCATION_REASONS = ("street:", "city:", "postcode:")
NAME_EXACT, NAME_STRONG, NAME_WEAK, NAME_NONE = "exact", "strong", "weak", "none"
NAME_RANK = {NAME_EXACT: 3, NAME_STRONG: 2, NAME_WEAK: 1, NAME_NONE: 0}
EXACT_SCORE = 100
WEAK_MIN = 50
CONFLICT, NO_CONFLICT = "conflict", "no_conflict"
PRIMARY_NAME_SOURCE = "company_name"

# Address match ranking used for best pick and rival check (D19).
LOC_EXACT_STREET, LOC_STREET_POSTCODE, LOC_CITY, LOC_COUNTRY = 3, 2, 1, 0


def name_outcome(row) -> str:
    if row.name_sort == EXACT_SCORE:
        return NAME_EXACT
    if row.input_core.replace(" ", "") == row.cand_core.replace(" ", ""):
        return NAME_STRONG
    if row.name_set == EXACT_SCORE:
        return NAME_WEAK
    if row.name_sort >= WEAK_MIN:
        return NAME_WEAK
    return NAME_NONE


def _codes(value) -> set[str]:
    return set(value.split()) if isinstance(value, str) else set()


def legal_outcome(row) -> str:
    inp, cand = _codes(row.input_legal_countries), _codes(row.cand_legal_countries)
    if not inp or not cand:
        return UNKNOWN
    return NO_CONFLICT if inp & cand else CONFLICT


def _word_vs_country(words: set[str], country) -> str:
    if not words or not isinstance(country, str):
        return UNKNOWN
    return NO_CONFLICT if country in words else CONFLICT


def country_word_outcome(row) -> str:
    """Country words in either name must agree with the other side's country (D21, D35)."""
    outcomes = {_word_vs_country(_codes(row.input_country_words), row.cand_country_code),
                _word_vs_country(_codes(row.cand_country_words), row.input_country_code)}
    if CONFLICT in outcomes:
        return CONFLICT
    return NO_CONFLICT if NO_CONFLICT in outcomes else UNKNOWN


def location_rank(row) -> int:
    if row.street == EXACT:
        return LOC_EXACT_STREET
    if row.street == STREET_ONLY and row.postcode == SAME:
        return LOC_STREET_POSTCODE
    if row.city == SAME:
        return LOC_CITY
    return LOC_COUNTRY


def _has_value(value) -> bool:
    return isinstance(value, str) and value != ""


def _failing_layers(best) -> list[str]:
    reasons = []
    if best.name_outcome not in (NAME_EXACT, NAME_STRONG):
        reasons.append(f"name:{best.name_outcome}")
    if best.legal == CONFLICT:
        reasons.append("legal:conflict")
    if best.country_word == CONFLICT:
        reasons.append("country_word:conflict")
    if _has_value(best.input_street_norm):
        if not _has_value(best.cand_street_norm):
            reasons.append("street:candidate_missing")
        elif best.loc_rank < LOC_STREET_POSTCODE:
            reasons.append(f"street:{best.street}")
            if best.street == STREET_ONLY and best.postcode != DIFFERENT:
                reasons.append(f"postcode:{best.postcode}")
    if best.city == DIFFERENT or (not _has_value(best.input_street_norm) and best.city != SAME):
        reasons.append(f"city:{best.city}")
    if best.postcode == DIFFERENT:
        reasons.append("postcode:different")
    return reasons


def _is_duplicate(a, b) -> bool:
    """Same core name at the same street and city: likely one company stored twice."""
    return (a.cand_core == b.cand_core and _has_value(a.cand_street_norm)
            and a.cand_street_norm == b.cand_street_norm and a.cand_city_norm == b.cand_city_norm)


def _is_thin(row) -> bool:
    return not _has_value(row.cand_website) and pd.isna(row.cand_employees)


def _is_rich(row) -> bool:
    return _has_value(row.cand_website) and not pd.isna(row.cand_employees)


def _resolve_input(group: pd.DataFrame) -> dict:
    first = group.iloc[0]
    out = {
        "input_row_key": first.input_row_key,
        "input_name": first.input_name,
        "input_country_code": first.input_country_code,
        "n_candidates": len(group),
    }

    has_candidate = (group.name_outcome != NAME_NONE) & group.country.isin([SAME, UNKNOWN])
    if not has_candidate.any():
        return out | {"decision": NO_CANDIDATE, "rule": "R3", "reason": "no weak-or-better name in same or unknown country"}

    same_country = group[group.country == SAME]
    if same_country.empty:
        return out | {"decision": UNMATCHED, "rule": "U3", "reason": "no_same_country_candidate"}  # D48

    good = same_country.name_outcome.isin([NAME_EXACT, NAME_STRONG])
    primary = same_country.cand_matched_source == PRIMARY_NAME_SOURCE
    if (good & primary).any():  # D31: alias-only matches neither win nor rival a main-name match
        same_country = same_country[~(good & ~primary)]

    ranked = same_country.assign(neg_idx=-same_country.cand_idx).sort_values(
        ["name_rank", "loc_rank", "name_sort", "neg_idx"], ascending=False)
    best = ranked.iloc[0]
    others = ranked.iloc[1:]
    good_name = others.name_outcome.isin([NAME_EXACT, NAME_STRONG])
    if best.cand_matched_source == PRIMARY_NAME_SOURCE:
        rivals = others[good_name & (others.loc_rank >= best.loc_rank)]
    else:
        rivals = others[good_name]

    thin = pd.Series([_is_thin(rival) for rival in rivals.itertuples()], index=rivals.index, dtype=bool)
    ignored = rivals[thin] if _is_rich(best) else rivals.iloc[0:0]
    rivals = rivals.drop(ignored.index)  # D44

    duplicates = not rivals.empty and all(_is_duplicate(best, rival) for rival in rivals.itertuples())
    if duplicates:  # D33: keep the engine's first record of the duplicate set
        best = pd.concat([best.to_frame().T, rivals]).sort_values("cand_idx").iloc[0]

    out |= {
        "cand_idx": best.cand_idx,
        "veridion_id": best.veridion_id,
        "cand_name": best.cand_name,
        "cand_matched_name": best.cand_matched_name,
        "cand_matched_source": best.cand_matched_source,
        "name_outcome": best.name_outcome,
        "name_sort": best.name_sort,
        "legal": best.legal,
        "country_word": best.country_word,
        "country": best.country,
        "city": best.city,
        "postcode": best.postcode,
        "street": best.street,
        "rival_ids": "|".join(rivals.veridion_id.astype(str)),
        "ignored_thin_rival_ids": "|".join(ignored.veridion_id.astype(str)),
        "full_legal_match": best.full_legal_match,
        "city_in_other_locations": best.city_in_other_locations,
        "street_in_other_locations": best.street_in_other_locations,
    }

    supported = same_country.name_outcome.isin([NAME_EXACT, NAME_STRONG]) | (
        (same_country.name_outcome == NAME_WEAK) & (same_country.loc_rank >= LOC_CITY))
    if not supported.any():  # D32
        return out | {"decision": UNMATCHED, "rule": "U1", "reason": f"name:{best.name_outcome} no address support"}

    reasons = _failing_layers(best)
    if not rivals.empty:
        reasons.append(f"duplicate:{len(rivals)}" if duplicates else f"rival:{len(rivals)}")
    if _has_value(first.input_branch):
        reasons.append("branch")

    if not reasons:
        rule = "R1" if _has_value(best.input_street_norm) else "R2"
        return out | {"decision": AUTO, "rule": rule, "reason": ""}
    joined = " ".join(reasons)
    other = [r for r in reasons if r != "branch"]
    if "branch" in reasons and all(r.startswith("duplicate:") for r in other):  # D43
        return out | {"decision": PROBABLE, "rule": "P4", "reason": joined}
    if any(r.startswith("name:") for r in reasons) and all(r.startswith(("name:",) + LOCATION_REASONS) for r in reasons):
        return out | {"decision": UNMATCHED, "rule": "U2", "reason": joined}  # D47
    if not all(r.startswith(LOCATION_REASONS + ("duplicate:",)) for r in reasons):
        return out | {"decision": REVIEW, "rule": "R4", "reason": joined}
    if duplicates:
        return out | {"decision": PROBABLE, "rule": "P3", "reason": joined}
    if best.full_legal_match:  # D45
        return out | {"decision": AUTO, "rule": "R5", "reason": joined}
    if best.city != DIFFERENT:
        return out | {"decision": PROBABLE, "rule": "P1", "reason": joined}
    if best.cand_matched_source == PRIMARY_NAME_SOURCE:
        return out | {"decision": PROBABLE, "rule": "P2", "reason": joined}
    return out | {"decision": UNMATCHED, "rule": "U4", "reason": joined}  # D49


def code_version() -> str:
    def git(*args):
        return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True, check=True).stdout.strip()
    commit = git("rev-parse", "--short", "HEAD")
    return f"{commit}-dirty" if git("status", "--porcelain", "--", ".", f":!{config.OUTPUT.relative_to(config.ROOT)}") else commit


def resolve(features: pd.DataFrame, manual: pd.DataFrame | None = None,
            external: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per input: decision, rule, reason, chosen candidate and its layer outcomes."""
    f = features.copy()
    f["name_outcome"] = f.apply(name_outcome, axis=1)
    f["name_rank"] = f.name_outcome.map(NAME_RANK)
    f["legal"] = f.apply(legal_outcome, axis=1)
    f["country_word"] = f.apply(country_word_outcome, axis=1)
    f["loc_rank"] = f.apply(location_rank, axis=1)
    rows = [_resolve_input(g) for _, g in f.groupby("input_row_key", sort=True)]
    if manual is None:
        manual = pd.read_csv(config.MATCH_REVIEW, dtype=str, keep_default_na=False)
    if external is None:
        external = pd.read_csv(config.EXTERNAL_MATCHES, dtype=str, keep_default_na=False)
    decisions = apply_manual(pd.DataFrame(rows), f, manual)
    confidence = decisions.rule.map(CONFIDENCE_BY_RULE).fillna(decisions.decision.map(CONFIDENCE))
    decisions.insert(decisions.columns.get_loc("decision") + 1, "confidence", confidence)
    decisions = apply_external(decisions, external)
    decisions["code_version"] = code_version()
    return decisions


def apply_manual(decisions: pd.DataFrame, features: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """Manual decisions (data/manual/match_review.csv) override the rules (D50)."""
    decisions = decisions.copy()
    decisions["related_veridion_id"] = ""
    decisions["rule_decision"] = decisions.decision
    by_key = decisions.set_index("input_row_key")
    unknown = set(manual.input_row_key.astype(int)) - set(by_key.index)
    if unknown:
        raise ValueError(f"Manual decisions for unknown inputs: {sorted(unknown)}")
    for m in manual.itertuples():
        key = int(m.input_row_key)
        row = decisions.index[decisions.input_row_key == key][0]
        decisions.loc[row, PICK_FIELDS] = None
        if m.decision == MANUAL_MATCH:
            cand = features[(features.input_row_key == key) & (features.veridion_id == m.veridion_id)]
            if len(cand) != 1:
                raise ValueError(f"Manual pick {m.veridion_id} is not a candidate of input {key}")
            for field in PICK_FIELDS:
                if field in cand:
                    decisions.loc[row, field] = cand[field].iloc[0]
            decisions.loc[row, ["decision", "rule"]] = [MANUAL, "M1"]
        elif m.decision == MANUAL_UNMATCHED:
            decisions.loc[row, ["decision", "rule"]] = [UNMATCHED, "M2"]
        else:
            raise ValueError(f"Unknown manual decision {m.decision!r} for input {key}")
        decisions.loc[row, ["reason", "related_veridion_id"]] = [f"manual ({m.source})", m.related_veridion_id]
    return decisions


def apply_external(decisions: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
    """External matches (data/manual/external_matches.csv) resolve inputs that have no Veridion pick (D54)."""
    decisions = decisions.copy()
    for column in EXTERNAL_FIELDS.values():
        decisions[column] = ""
    for e in external.itertuples():
        key = int(e.input_row_key)
        rows = decisions.index[decisions.input_row_key == key]
        if len(rows) != 1:
            raise ValueError(f"External match for unknown input {key}")
        row = rows[0]
        if decisions.loc[row, "decision"] not in (UNMATCHED, NO_CANDIDATE):
            raise ValueError(f"External match for input {key}, which already has decision {decisions.loc[row, 'decision']}")
        decisions.loc[row, ["decision", "rule", "confidence"]] = [EXTERNAL, "E1", e.confidence]
        decisions.loc[row, "reason"] = f"external ({e.source})"
        decisions.loc[row, list(EXTERNAL_FIELDS.values())] = [getattr(e, field) for field in EXTERNAL_FIELDS]
    return decisions
