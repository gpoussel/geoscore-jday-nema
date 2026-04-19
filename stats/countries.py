"""Country and US-state reference for GeoGuessr Duels inputs.

Codes follow GeoGuessr convention: lowercase ISO 3166-1 alpha-2, plus 'uk'
for the United Kingdom (GeoGuessr uses 'uk' instead of the ISO 'gb').
US state sub-codes are written as 'us:<state>', e.g. 'us:fl'.
"""
from __future__ import annotations

import pycountry

COUNTRIES: frozenset[str] = frozenset(
    {c.alpha_2.lower() for c in pycountry.countries} | {"uk"}
)

US_STATES: frozenset[str] = frozenset(
    sd.code.split("-", 1)[1].lower()
    for sd in pycountry.subdivisions
    if sd.country_code == "US" and sd.type in ("State", "District")
)


def is_valid(code: str) -> bool:
    code = code.strip().lower()
    if ":" in code:
        country, sub = code.split(":", 1)
        return country == "us" and sub in US_STATES
    return code in COUNTRIES
