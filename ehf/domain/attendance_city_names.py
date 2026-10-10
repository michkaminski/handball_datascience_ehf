from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def collapse_whitespace(name: str) -> str:
    return _WHITESPACE.sub(" ", name).strip()


def normalize_city_key(name: str) -> str:
    return collapse_whitespace(name).casefold()
