from __future__ import annotations

from collections.abc import Mapping

from ehf.domain.match_detail import LineupPlayer

POSITION_HUES: Mapping[str, int] = {
    "goalkeeper": 200,
    "left wing": 150,
    "right wing": 28,
    "wing": 90,
    "left back": 260,
    "right back": 320,
    "centre back": 42,
    "center back": 42,
    "back": 50,
    "line player": 285,
    "field player": 180,
}


def position_hue(position: str | None, is_goalkeeper: bool = False) -> int | None:
    key = (position or "").strip().casefold()
    if not key and is_goalkeeper:
        key = "goalkeeper"
    if not key:
        return None
    mapped = POSITION_HUES.get(key)
    if mapped is not None:
        return mapped
    return sum(ord(character) for character in key) * 17 % 360


def hue_for_player(player: LineupPlayer) -> int | None:
    return position_hue(player.position, player.is_goalkeeper)
