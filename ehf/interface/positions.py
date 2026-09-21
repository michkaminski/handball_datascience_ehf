from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.lineup_order import LineRole, line_role
from ehf.domain.match_detail import LineupPlayer

_ROLE_HUES: dict[LineRole, int] = {
    LineRole.GOALKEEPER: 200,
    LineRole.PIVOT: 285,
    LineRole.BACKCOURT: 42,
    LineRole.WING: 150,
    LineRole.OTHER: 180,
}


@dataclass(frozen=True)
class PositionStyle:
    code: str
    label: str
    hue: int
    rank: int


_CATALOG: dict[str, tuple[str, str]] = {
    "goalkeeper": ("GK", "Goalkeeper"),
    "left wing": ("LW", "Left Wing"),
    "right wing": ("RW", "Right Wing"),
    "wing": ("W", "Wing"),
    "left back": ("LB", "Left Back"),
    "right back": ("RB", "Right Back"),
    "centre back": ("CB", "Centre Back"),
    "center back": ("CB", "Centre Back"),
    "back": ("B", "Back"),
    "line player": ("LP", "Line Player"),
    "field player": ("FP", "Field Player"),
}


def _position_key(position: str | None, is_goalkeeper: bool) -> str | None:
    if is_goalkeeper:
        return "goalkeeper"
    key = (position or "").strip().casefold()
    return key or None


def style_for(position: str | None, is_goalkeeper: bool = False) -> PositionStyle | None:
    key = _position_key(position, is_goalkeeper)
    if key is None:
        return None
    role = line_role(position, is_goalkeeper)
    hue = _ROLE_HUES[role]
    mapped = _CATALOG.get(key)
    if mapped is not None:
        code, label = mapped
        return PositionStyle(code, label, hue, int(role))
    words = [word for word in key.split() if word]
    code = "".join(word[0] for word in words).upper() if words else key[:2].upper()
    label = (position or "").strip() or key.title()
    return PositionStyle(code, label, hue, int(role))


def hue_for_player(player: LineupPlayer) -> int | None:
    style = style_for(player.position, player.is_goalkeeper)
    return None if style is None else style.hue


def code_for_player(player: LineupPlayer) -> str | None:
    style = style_for(player.position, player.is_goalkeeper)
    return None if style is None else style.code


def legend_for_lineups(*groups: tuple[LineupPlayer, ...]) -> tuple[PositionStyle, ...]:
    seen: dict[str, PositionStyle] = {}
    for players in groups:
        for player in players:
            style = style_for(player.position, player.is_goalkeeper)
            if style is not None and style.code not in seen:
                seen[style.code] = style
    return tuple(sorted(seen.values(), key=lambda item: (item.rank, item.code)))
