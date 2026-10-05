from __future__ import annotations

from html import unescape

# IOC codes for nationalities that ehf.country does not list (names as EHF spells them).
EXTRA_CODES = {
    "türkiye": "TUR",
    "turkey": "TUR",
    "brazil": "BRA",
    "argentina": "ARG",
    "egypt": "EGY",
    "tunisia": "TUN",
    "cuba": "CUB",
    "angola": "ANG",
    "georgia": "GEO",
    "algeria": "ALG",
    "japan": "JPN",
    "congo": "CGO",
    "nigeria": "NGR",
    "iran": "IRI",
    "cap verde": "CPV",
    "moldova": "MDA",
    "senegal": "SEN",
    "united states of america": "USA",
    "qatar": "QAT",
    "canada": "CAN",
    "paraguay": "PAR",
    "kazakhstan": "KAZ",
    "uruguay": "URU",
    "cameroons": "CMR",
    "chile": "CHI",
    "marocco": "MAR",
    "lebanon": "LBN",
    "kuwait": "KUW",
    "palestina": "PLE",
    "ivory coast": "CIV",
    "puerto rico": "PUR",
    "ireland": "IRL",
    "guinea": "GUI",
    "syria": "SYR",
    "dominican republic": "DOM",
    "togo": "TOG",
    "democratic republic of the congo": "COD",
    "columbia": "COL",
    "australia": "AUS",
}


def nationality_code(name: str, country_code: str | None) -> str:
    """Three-letter code for a nationality: ehf.country first, then the IOC list, then the first letters."""
    if country_code:
        return country_code.strip()
    clean = unescape(name).strip()
    return EXTRA_CODES.get(clean.casefold(), clean[:3].upper())
