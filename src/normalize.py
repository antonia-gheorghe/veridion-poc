"""Normalize names, locations and addresses so inputs and candidates are comparable.

All word lists live in data/reference/ so every rule can be reviewed without reading code.
"""
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from src import config

# Letters NFKD does not decompose into an ASCII base letter.
_TRANSLIT = str.maketrans({"Ø": "O", "ø": "o", "Æ": "AE", "æ": "ae", "ß": "ss", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d"})
# Single-letter country markers used before a local legal form, e.g. "X (M) Sdn Bhd", "X (S) Pte Ltd".
COUNTRY_MARKERS = {"M": ("MY", {"SDN BHD", "BHD"}), "S": ("SG", {"PTE LTD"})}
WEB_DOMAIN_SUFFIX = re.compile(r"\.(COM|NET|ORG|IO|DK|NO|SE|FI|DE|NL|UK|SG|MY)\b", re.IGNORECASE)


@dataclass(frozen=True)
class NameParts:
    core: str
    legal_forms: tuple[str, ...]
    legal_countries: frozenset[str]
    country_words: tuple[str, ...]
    branch: str


def fold(text: str) -> str:
    """Uppercase ASCII form, for comparison only."""
    text = str(text).translate(_TRANSLIT)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.upper()


def _tokens(text: str) -> list[str]:
    text = WEB_DOMAIN_SUFFIX.sub("", fold(text).strip())
    text = text.replace("&", " AND ").replace(".", "")
    return re.sub(r"[^\w/ ]", " ", text).split()


def _is_missing(value) -> bool:
    return value is None or (not isinstance(value, str) and pd.isna(value))


@lru_cache(maxsize=None)
def _legal_forms() -> list[tuple[list[str], str, frozenset[str]]]:
    table = pd.read_csv(config.LEGAL_FORMS, keep_default_na=False)
    rows = [(v.split(), c, frozenset(cs.split())) for v, c, cs in table.itertuples(index=False)]
    return sorted(rows, key=lambda r: len(r[0]), reverse=True)


@lru_cache(maxsize=None)
def _country_words() -> list[tuple[list[str], str]]:
    table = pd.read_csv(config.COUNTRY_WORDS, keep_default_na=False)
    rows = [(w.split(), cc) for w, cc in table.itertuples(index=False)]
    return sorted(rows, key=lambda r: len(r[0]), reverse=True)


@lru_cache(maxsize=None)
def _branch_markers() -> list[list[str]]:
    markers = pd.read_csv(config.BRANCH_MARKERS, keep_default_na=False).marker
    return sorted((m.split() for m in markers), key=len, reverse=True)


@lru_cache(maxsize=None)
def _postcode_digits() -> dict[str, int]:
    table = pd.read_csv(config.POSTCODE_DIGITS, keep_default_na=False)
    return dict(zip(table.country_code, table.digits))


@lru_cache(maxsize=None)
def _city_admin_words() -> frozenset[str]:
    return frozenset(pd.read_csv(config.CITY_ADMIN_WORDS, keep_default_na=False).word)


def _ends_with(tokens: list[str], suffix: list[str]) -> bool:
    return len(tokens) > len(suffix) and tokens[-len(suffix):] == suffix


def _find(tokens: list[str], phrase: list[str]) -> int:
    for i in range(1, len(tokens) - len(phrase) + 1):
        if tokens[i:i + len(phrase)] == phrase:
            return i
    return -1


def split_name(name: str) -> NameParts:
    """Split a company name into core name, legal forms, country words and branch marker.

    Legal forms and country words are only stripped from the end, and never down to an empty core.
    """
    tokens = _tokens(name)

    branch = ""
    cuts = [(i, m) for m in _branch_markers() if (i := _find(tokens, m)) > 0]
    if cuts:
        cut = min(i for i, _ in cuts)
        branch = " ".join(tokens[cut:])
        tokens = tokens[:cut]

    legal, legal_countries, country_words = [], set(), []
    changed = True
    while changed:
        changed = False
        for variant, canonical, countries in _legal_forms():
            if _ends_with(tokens, variant):
                tokens = tokens[:-len(variant)]
                legal.append(canonical)
                legal_countries |= countries
                changed = True
                break
        if changed:
            continue
        for word, country in _country_words():
            if _ends_with(tokens, word):
                tokens = tokens[:-len(word)]
                country_words.append(country)
                changed = True
                break
        if changed:
            continue
        for marker, (country, forms) in COUNTRY_MARKERS.items():
            if forms & set(legal) and _ends_with(tokens, [marker]):
                tokens = tokens[:-1]
                country_words.append(country)
                changed = True
                break

    return NameParts(
        core=" ".join(tokens),
        legal_forms=tuple(legal),
        legal_countries=frozenset(legal_countries),
        country_words=tuple(country_words),
        branch=branch,
    )


def norm_city(city) -> str | None:
    if _is_missing(city):
        return None
    tokens = [t for t in _tokens(city) if t not in _city_admin_words()]
    return " ".join(tokens) or None


def norm_postcode(postcode, country_code) -> str | None:
    """Remove spaces and dashes; restore leading zeros for all-digit postcode countries."""
    if _is_missing(postcode):
        return None
    code = re.sub(r"[\s-]", "", fold(postcode))
    if not code or set(code) == {"0"}:
        return None
    digits = _postcode_digits().get(country_code)
    if digits and code.isdigit() and len(code) < digits:
        code = code.zfill(digits)
    return code


def norm_street(street) -> str | None:
    if _is_missing(street):
        return None
    return " ".join(_tokens(street)) or None


def norm_street_number(number) -> str | None:
    if _is_missing(number):
        return None
    return re.sub(r"\s", "", fold(number)) or None
