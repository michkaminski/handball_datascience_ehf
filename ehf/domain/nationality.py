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


SHORT_NATIONALITY = {
    "ALG": "DZ",
    "AND": "AD",
    "ANG": "AO",
    "ARG": "AR",
    "ARM": "AM",
    "AUS": "AU",
    "AUT": "AT",
    "AZE": "AZ",
    "BEL": "BE",
    "BIH": "BA",
    "BLR": "BY",
    "BRA": "BR",
    "BUL": "BG",
    "CAN": "CA",
    "CGO": "CG",
    "CHI": "CL",
    "CHN": "CN",
    "CIV": "CI",
    "CMR": "CM",
    "COD": "CD",
    "COL": "CO",
    "CPV": "CV",
    "CRO": "HR",
    "CUB": "CU",
    "CYP": "CY",
    "CZE": "CZ",
    "DEN": "DK",
    "DOM": "DO",
    "EGY": "EG",
    "ESP": "ES",
    "EST": "EE",
    "FAR": "FO",
    "FIN": "FI",
    "FRA": "FR",
    "FRO": "FO",
    "GBR": "GB",
    "GEO": "GE",
    "GER": "DE",
    "GRE": "GR",
    "GUI": "GN",
    "HUN": "HU",
    "IRL": "IE",
    "IRI": "IR",
    "ISL": "IS",
    "ISR": "IL",
    "ITA": "IT",
    "JPN": "JP",
    "KAZ": "KZ",
    "KOR": "KR",
    "KOS": "XK",
    "KSA": "SA",
    "KUW": "KW",
    "LAT": "LV",
    "LBN": "LB",
    "LTU": "LT",
    "LUX": "LU",
    "MAR": "MA",
    "MDA": "MD",
    "MKD": "MK",
    "MLT": "MT",
    "MNE": "ME",
    "NED": "NL",
    "NGR": "NG",
    "NOR": "NO",
    "PAR": "PY",
    "PLE": "PS",
    "POL": "PL",
    "POR": "PT",
    "PUR": "PR",
    "QAT": "QA",
    "ROU": "RO",
    "RSA": "ZA",
    "RUS": "RU",
    "SEN": "SN",
    "SLO": "SI",
    "SRB": "RS",
    "SUI": "CH",
    "SVK": "SK",
    "SWE": "SE",
    "SYR": "SY",
    "TOG": "TG",
    "TUN": "TN",
    "TUR": "TR",
    "UAE": "AE",
    "UKR": "UA",
    "URU": "UY",
    "USA": "US",
}


def short_nationality(code: str) -> str:
    clean = code.strip().upper()
    return SHORT_NATIONALITY.get(clean, clean)


def nationality_mark(codes: tuple[str, ...]) -> str:
    shown: list[str] = []
    for code in codes:
        short = short_nationality(code)
        if short and short not in shown:
            shown.append(short)
    if not shown:
        return ""
    if len(shown) == 1:
        return shown[0]
    return f"{shown[0]}+"
