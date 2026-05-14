"""Country reference for GeoGuessr Duels inputs.

Codes follow GeoGuessr convention: lowercase ISO 3166-1 alpha-2, plus 'uk'
for the United Kingdom (GeoGuessr uses 'uk' instead of the ISO 'gb').
"""
from __future__ import annotations

import pycountry

COUNTRIES: frozenset[str] = frozenset(
    {c.alpha_2.lower() for c in pycountry.countries} | {"uk"}
)


def is_valid(code: str) -> bool:
    code = code.strip().lower()
    return code in COUNTRIES
