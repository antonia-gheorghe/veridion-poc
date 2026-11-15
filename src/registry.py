"""Look up unmatched inputs in official registries: Brreg (NO), PRH (FI) and GLEIF (all countries).

A registry record is accepted only when its core name and legal forms equal the input's (D54).
Raw responses are cached under data/external/cache so a rerun needs no network.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import pandas as pd
import requests

from src import config
from src.normalize import norm_city, split_name

BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
BRREG_PHRASE_SEARCH = "FORTLOEPENDE"
PRH_URL = "https://avoindata.prh.fi/opendata-ytj-api/v3/companies"
GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
USER_AGENT = "registry-lookup/1.0"
REQUEST_INTERVAL_S = 1.0
TIMEOUT_S = 30
PAGE_SIZE = 100
MAX_RESULTS = 500  # more hits than this means the name is too generic to prove a unique match
NATIONAL = {"NO": "brreg", "FI": "prh"}
GLEIF_LEGAL_NAME_TYPES = {"ALTERNATIVE_LANGUAGE_LEGAL_NAME", "AUTO_ASCII_TRANSLITERATED_LEGAL_NAME"}
GLEIF_FORMER_NAME_TYPE = "PREVIOUS_LEGAL_NAME"
QUEUE_DECISIONS = {"unmatched", "no_candidate"}
REGISTRY_SOURCES = {"brreg", "prh", "gleif"}

MATCHED, AMBIGUOUS, NO_HIT, TRUNCATED, ERROR = "matched", "ambiguous", "no_hit", "truncated", "error"
NO_LEGAL_FORM = "input_has_no_legal_form"
ERROR_PREFIX = "ERROR"
CURRENT, FORMER = "current name", "former name"


@dataclass
class Record:
    source: str
    registry_id: str
    name: str
    status: str
    url: str
    names: list[tuple[str, str]]  # (name, CURRENT or FORMER)
    cities: set[str] = field(default_factory=set)
    national_id: str = ""


class Truncated(Exception):
    pass


# --- HTTP with cache -------------------------------------------------------

_last_request = 0.0


def _get(source: str, url: str, params: dict) -> dict:
    full = f"{url}?{urlencode(params)}"
    path = config.EXTERNAL_CACHE / source / f"{hashlib.sha256(full.encode()).hexdigest()[:16]}.json"
    if path.exists():
        return json.loads(path.read_text())["response"]
    global _last_request
    time.sleep(max(0.0, _last_request + REQUEST_INTERVAL_S - time.monotonic()))
    _last_request = time.monotonic()
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    response.raise_for_status()
    body = response.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": full, "response": body}, ensure_ascii=False, indent=1))
    return body


# --- Parsers ---------------------------------------------------------------

def _brreg_status(e: dict) -> str:
    if e.get("slettedato"):
        return "deleted"
    if e.get("konkurs"):
        return "bankrupt"
    if e.get("underAvvikling") or e.get("underTvangsavviklingEllerTvangsopplosning"):
        return "being dissolved"
    return "active"


def parse_brreg(e: dict) -> Record:
    names = [(e["navn"], CURRENT)] + [(h["navn"], FORMER) for h in e.get("historiskeNavn") or []]
    cities = {(e.get(a) or {}).get("poststed") for a in ("forretningsadresse", "postadresse")}
    return Record(source="brreg", registry_id=e["organisasjonsnummer"], name=e["navn"], status=_brreg_status(e),
                  url=e["_links"]["self"]["href"], names=names, cities={norm_city(c) for c in cities if c} - {None},
                  national_id=e["organisasjonsnummer"])


def parse_prh(c: dict, query_url: str) -> Record:
    names = [(n["name"], FORMER if n.get("endDate") else CURRENT) for n in c["names"]]
    current = next((n for n, kind in names if kind == CURRENT), names[0][0])
    cities = {o["city"] for a in c.get("addresses") or [] for o in a.get("postOffices") or []}
    business_id = c["businessId"]["value"]
    return Record(source="prh", registry_id=business_id, name=current,
                  status=f"prh status={c.get('status')} tradeRegisterStatus={c.get('tradeRegisterStatus')}",
                  url=query_url, names=names, cities={norm_city(x) for x in cities} - {None}, national_id=business_id)


def parse_gleif(item: dict) -> Record:
    entity = item["attributes"]["entity"]
    names = [(entity["legalName"]["name"], CURRENT)]
    for other in (entity.get("otherNames") or []) + (entity.get("transliteratedOtherNames") or []):
        if other["type"] in GLEIF_LEGAL_NAME_TYPES:
            names.append((other["name"], CURRENT))
        elif other["type"] == GLEIF_FORMER_NAME_TYPE:
            names.append((other["name"], FORMER))
    cities = {(entity.get(a) or {}).get("city") for a in ("legalAddress", "headquartersAddress")}
    return Record(source="gleif", registry_id=item["attributes"]["lei"], name=entity["legalName"]["name"],
                  status=f"{entity['status'].lower()}", url=item["links"]["self"], names=names,
                  cities={norm_city(c) for c in cities if c} - {None}, national_id=entity.get("registeredAs") or "")


# --- Queries ---------------------------------------------------------------

def query_brreg(core: str) -> list[Record]:
    records, page = [], 0
    while True:
        body = _get("brreg", BRREG_URL, {"navn": core, "navnMetodeForSoek": BRREG_PHRASE_SEARCH, "size": PAGE_SIZE, "page": page})
        total = body["page"]["totalElements"]
        if total > MAX_RESULTS:
            raise Truncated(f"brreg: {total} hits")
        records += [parse_brreg(e) for e in body.get("_embedded", {}).get("enheter", [])]
        page += 1
        if page >= body["page"]["totalPages"]:
            return records


def query_prh(core: str) -> list[Record]:
    records, page = {}, 1
    while True:
        params = {"name": core, "page": page}
        body = _get("prh", PRH_URL, params)
        if body["totalResults"] > MAX_RESULTS:
            raise Truncated(f"prh: {body['totalResults']} hits")
        new = {c["businessId"]["value"]: c for c in body["companies"]}
        if not new.keys() - records.keys():
            break
        query_url = f"{PRH_URL}?{urlencode({'name': core})}"
        records |= {k: parse_prh(c, query_url) for k, c in new.items() if k not in records}
        if len(records) >= body["totalResults"]:
            break
        page += 1
    return list(records.values())


def query_gleif(core: str, country: str) -> list[Record]:
    records, page = [], 1
    while True:
        body = _get("gleif", GLEIF_URL, {"filter[fulltext]": core, "filter[entity.legalAddress.country]": country,
                                         "page[size]": PAGE_SIZE, "page[number]": page})
        pagination = body["meta"]["pagination"]
        if pagination["total"] > MAX_RESULTS:
            raise Truncated(f"gleif: {pagination['total']} hits")
        records += [parse_gleif(item) for item in body["data"]]
        if page >= pagination["lastPage"]:
            return records
        page += 1


# --- Acceptance ------------------------------------------------------------

def name_basis(input_name: str, record: Record) -> str | None:
    """CURRENT or FORMER when one of the record's names has the input's core and legal forms, else None."""
    inp = split_name(input_name)
    kinds = {kind for name, kind in record.names
             if (p := split_name(name)).core == inp.core and set(p.legal_forms) == set(inp.legal_forms)}
    return CURRENT if CURRENT in kinds else FORMER if FORMER in kinds else None


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum())


def accept(input_name: str, input_city: str | None, national: list[Record], gleif: list[Record]) -> dict:
    """Decide one input from the records each source returned."""
    hits = {}
    for source_records in (national, gleif):
        passing = {r.registry_id: r for r in source_records if name_basis(input_name, r)}
        if len(passing) > 1:
            return {"outcome": AMBIGUOUS, "note": f"{len(passing)} {source_records[0].source} records: "
                    + "; ".join(sorted(passing))}
        hits |= {r.source: r for r in passing.values()}
    if not hits:
        return {"outcome": NO_HIT}
    nat = next((r for r in hits.values() if r.source != "gleif"), None)
    lei = hits.get("gleif")
    if nat and lei and _digits(lei.national_id) != _digits(nat.national_id):
        return {"outcome": AMBIGUOUS, "note": f"{nat.source} {nat.registry_id} vs gleif {lei.registry_id} ({lei.national_id})"}
    main = nat or lei
    cities = set().union(*(r.cities for r in hits.values()))
    return {
        "outcome": MATCHED,
        "source": "+".join(r.source for r in hits.values()),
        "registry_id": "; ".join(f"{r.source}:{r.registry_id}" for r in hits.values()),
        "company_name": main.name,
        "registry_status": main.status,
        "match_basis": name_basis(input_name, main),
        "confidence": "high" if input_city and input_city in cities else "medium",
        "evidence_url": " ".join(r.url for r in hits.values()),
    }


# --- Main ------------------------------------------------------------------

def _lookup(query, *args) -> tuple[list[Record], str]:
    try:
        return query(*args), ""
    except Truncated as exc:
        return [], str(exc)
    except requests.RequestException as exc:
        return [], f"{ERROR_PREFIX} {exc}"


def in_queue(decisions: pd.DataFrame) -> pd.Series:
    """Inputs without a Veridion pick, including those resolved by an earlier registry lookup."""
    registry = decisions.external_source.fillna("").str.split("+").map(lambda parts: set(parts) <= REGISTRY_SOURCES)
    return decisions.decision.isin(QUEUE_DECISIONS) | ((decisions.decision == "external") & registry)


def lookup_queue(decisions: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    cities = features.drop_duplicates("input_row_key").set_index("input_row_key").input_city_norm
    rows = []
    for d in decisions[in_queue(decisions)].itertuples():
        core, country = split_name(d.input_name).core, d.input_country_code
        base = {"input_row_key": d.input_row_key, "input_name": d.input_name, "country_code": country, "query": core}
        if not split_name(d.input_name).legal_forms:
            rows.append(base | {"issues": "", "outcome": NO_LEGAL_FORM})
            continue
        national, nat_issue = [], ""
        if country in NATIONAL:
            national, nat_issue = _lookup(query_brreg if country == "NO" else query_prh, core)
        gleif, gleif_issue = _lookup(query_gleif, core, country)
        city = cities.get(d.input_row_key)
        result = accept(d.input_name, city if isinstance(city, str) else None, national, gleif)
        issues = "; ".join(i for i in (nat_issue, gleif_issue) if i)
        if issues and result["outcome"] != AMBIGUOUS:  # an incomplete search cannot prove a unique match
            result = {"outcome": ERROR if ERROR_PREFIX in issues else TRUNCATED}
        rows.append(base | {"issues": issues} | result)
    return pd.DataFrame(rows)


def main():
    decisions = pd.read_csv(config.DECISIONS_FILE)
    features = pd.read_csv(config.FEATURES_FILE)
    log = lookup_queue(decisions, features)
    log.to_csv(config.REGISTRY_LOG, index=False)
    print(log.outcome.value_counts().to_string())
    errors = log[log.outcome == ERROR]
    if len(errors):
        print(f"\n{len(errors)} LOOKUPS FAILED; rerun to retry (failed requests are not cached):")
        print(errors[["input_row_key", "input_name", "issues"]].to_string(index=False))

    existing = pd.read_csv(config.EXTERNAL_MATCHES, dtype=str, keep_default_na=False)
    kept = existing[~existing.source.str.split("+").map(lambda parts: set(parts) <= REGISTRY_SOURCES)]
    matched = log[log.outcome == MATCHED].assign(veridion_id="", website="", note="")
    out = pd.concat([kept, matched[EXTERNAL_COLUMNS].astype(str)], ignore_index=True)
    out[EXTERNAL_COLUMNS].to_csv(config.EXTERNAL_MATCHES, index=False)
    print(f"\nWrote {len(matched)} registry matches to {config.EXTERNAL_MATCHES.relative_to(config.ROOT)}")


EXTERNAL_COLUMNS = ["input_row_key", "source", "veridion_id", "company_name", "website", "country_code", "evidence_url",
                    "note", "registry_id", "registry_status", "match_basis", "confidence"]

if __name__ == "__main__":
    main()
