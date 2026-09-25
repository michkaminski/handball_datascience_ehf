from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sort:
    column: str
    descending: bool = False

    @property
    def direction(self) -> str:
        return "desc" if self.descending else "asc"

    def aria(self, column: str) -> str | None:
        if column != self.column:
            return None
        return "descending" if self.descending else "ascending"


DEFAULT_MATCH_SORT = Sort("date", True)
DEFAULT_PLAYER_SORT = Sort("last_name", False)
DEFAULT_PLAYER_MATCH_SORT = Sort("date", True)

MATCH_SORT_COLUMNS = frozenset(
    {
        "id",
        "date",
        "time",
        "season",
        "competition",
        "phase",
        "home",
        "score",
        "away",
        "venue",
        "spectators",
    }
)
PLAYER_SORT_COLUMNS = frozenset(
    {
        "id",
        "first_name",
        "last_name",
        "position",
        "teams",
        "year",
        "height",
        "weight",
    }
)
PLAYER_MATCH_SORT_COLUMNS = frozenset(
    {
        "date",
        "season",
        "competition",
        "team",
        "opponent",
        "score",
        "goals",
        "shots",
        "shot_pct",
        "two_min",
        "saves",
        "faced",
        "save_pct",
    }
)


DEFAULT_VENUE_SORT = Sort("name", False)
DEFAULT_VENUE_MATCH_SORT = Sort("date", True)
DEFAULT_VENUE_PLAYER_SORT = Sort("matches", True)
DEFAULT_REFEREE_SORT = Sort("name", False)
DEFAULT_REFEREE_MATCH_SORT = Sort("date", True)

VENUE_SORT_COLUMNS = frozenset({"id", "name", "city", "country", "matches"})
VENUE_MATCH_SORT_COLUMNS = frozenset(
    {"date", "season", "competition", "home", "score", "away"}
)
VENUE_PLAYER_SORT_COLUMNS = frozenset(
    {"name", "matches", "first", "last", "goals", "avg", "teams"}
)
REFEREE_SORT_COLUMNS = frozenset({"id", "name", "country", "matches"})
REFEREE_MATCH_SORT_COLUMNS = frozenset(
    {"date", "season", "competition", "home", "score", "away", "partner"}
)

SEASON_SORT_COLUMNS = frozenset(
    {"id", "season", "year", "competitions", "matches", "state"}
)
COMPETITION_SORT_COLUMNS = frozenset(
    {"id", "season", "name", "gender", "teams", "matches"}
)
TEAM_SORT_COLUMNS = frozenset(
    {"id", "season", "name", "gender", "city", "matches", "status"}
)
SCORER_SORT_COLUMNS = frozenset({"player", "team", "goals", "matches"})


def resolve_sort(column: str | None, direction: str | None, allowed: frozenset[str], default: Sort) -> Sort:
    if column not in allowed:
        return default
    if direction in {"asc", "desc"}:
        return Sort(column, direction == "desc")
    if column == default.column:
        return default
    return Sort(column, False)
