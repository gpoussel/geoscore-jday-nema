"""Country reference for GeoGuessr Duels inputs.

Codes follow GeoGuessr convention: lowercase ISO 3166-1 alpha-2, plus 'uk'
for the United Kingdom (GeoGuessr uses 'uk' instead of the ISO 'gb') and 'xk'
for Kosovo (user-assigned code, absent from ISO 3166-1 / pycountry).
"""
from __future__ import annotations

import pycountry

COUNTRIES: frozenset[str] = frozenset(
    {c.alpha_2.lower() for c in pycountry.countries} | {"uk", "xk"}
)

# Codes hors ISO 3166-1 : pycountry ne les connaît pas, on nomme à la main.
EXTRA_NAMES: dict[str, str] = {
    "uk": "United Kingdom",
    "xk": "Kosovo",
}


def name_of(code: str) -> str | None:
    """Nom lisible d'un code pays, y compris les codes hors ISO."""
    code = code.strip().lower()
    if code in EXTRA_NAMES:
        return EXTRA_NAMES[code]
    obj = pycountry.countries.get(alpha_2=code.upper())
    return obj.name if obj else None


def is_valid(code: str) -> bool:
    code = code.strip().lower()
    return code in COUNTRIES
