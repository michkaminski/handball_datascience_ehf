from __future__ import annotations

from typing import Mapping

from flask import request, url_for


def expanded_keys(args: Mapping[str, str]) -> frozenset[str]:
    raw = args.get("full") or ""
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def expand_href(key: str) -> str:
    args = request.args.to_dict(flat=True)
    keys = set(expanded_keys(request.args))
    if key in keys:
        keys.discard(key)
    else:
        keys.add(key)
    if keys:
        args["full"] = ",".join(sorted(keys))
    else:
        args.pop("full", None)
    args["tab"] = "statistics"
    return url_for(request.endpoint, **{**(request.view_args or {}), **args})
