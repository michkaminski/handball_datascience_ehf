from __future__ import annotations

from enum import IntEnum

from dataclasses import replace

from ehf.domain.match_detail import LineupPlayer, MatchDetail


class LineRole(IntEnum):
    GOALKEEPER = 0
    PIVOT = 1
    BACKCOURT = 2
    WING = 3
    OTHER = 4


_ROLE_BY_POSITION: dict[str, LineRole] = {
    "goalkeeper": LineRole.GOALKEEPER,
    "line player": LineRole.PIVOT,
    "pivot": LineRole.PIVOT,
    "left back": LineRole.BACKCOURT,
    "right back": LineRole.BACKCOURT,
    "centre back": LineRole.BACKCOURT,
    "center back": LineRole.BACKCOURT,
    "back": LineRole.BACKCOURT,
    "left wing": LineRole.WING,
    "right wing": LineRole.WING,
    "wing": LineRole.WING,
}


def line_role(position: str | None, is_goalkeeper: bool = False) -> LineRole:
    if is_goalkeeper:
        return LineRole.GOALKEEPER
    key = (position or "").strip().casefold()
    if not key:
        return LineRole.OTHER
    return _ROLE_BY_POSITION.get(key, LineRole.OTHER)


def _shirt_sort(number: str | None) -> tuple[int, int, str]:
    text = (number or "").strip()
    if not text:
        return (1, 0, "")
    if text.isdigit():
        return (0, int(text), text)
    return (0, 0, text)


def sort_lineup(players: tuple[LineupPlayer, ...]) -> tuple[LineupPlayer, ...]:
    return tuple(
        sorted(
            players,
            key=lambda player: (
                line_role(player.position, player.is_goalkeeper),
                _shirt_sort(player.shirt_number),
                player.name,
            ),
        )
    )


def with_sorted_lineups(match: MatchDetail) -> MatchDetail:
    return replace(
        match,
        home_lineup=sort_lineup(match.home_lineup),
        away_lineup=sort_lineup(match.away_lineup),
    )
