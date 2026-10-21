from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from ehf.domain.lineup_order import LineRole, line_role
from ehf.domain.match_sheet import (
    MatchSheetData,
    MatchSheetRequest,
    SheetTeamData,
    SquadPlayer,
    display_name,
    merge_squads,
    order_players,
)

LIVE_FORMAT = "protokol_live"
LIVE_VERSION = 1
SPARE_NUMBER_FROM = 100

# letters of the live protocol: B goalkeeper, R backcourt, S wing, O pivot
LIVE_POSITIONS = {
    LineRole.GOALKEEPER: "B",
    LineRole.BACKCOURT: "R",
    LineRole.WING: "S",
    LineRole.PIVOT: "O",
}

_FOLD = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss", "æ": "ae", "Æ": "AE"})


@dataclass(frozen=True)
class LiveProtocol:
    """The offline live protocol: a JSON document and the base name of its files."""

    base_name: str
    document: dict

    @property
    def html_name(self) -> str:
        return f"{self.base_name}.html"

    @property
    def json_name(self) -> str:
        return f"{self.base_name}.json"

    @property
    def zip_name(self) -> str:
        return f"{self.base_name}.zip"


def file_part(text: str) -> str:
    """ASCII, no spaces or separators: 'Orlen Wisła Płock' -> 'Orlen-Wisla-Plock'."""
    folded = unicodedata.normalize("NFKD", text.translate(_FOLD)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", folded).strip("-") or "team"


def live_base_name(match_date: date, home: str, away: str) -> str:
    return f"{match_date.isoformat()}_{file_part(home)}_{file_part(away)}"


def _shirt(number: str | None) -> int | None:
    text = (number or "").strip()
    return int(text) if text.isdigit() else None


def live_numbers(players: tuple[SquadPlayer, ...]) -> list[int]:
    """The live protocol keys players by number: missing or repeated numbers get free ones from 100."""
    taken: set[int] = set()
    numbers: list[int | None] = []
    for player in players:
        number = _shirt(player.number)
        if number is not None and number not in taken:
            taken.add(number)
            numbers.append(number)
        else:
            numbers.append(None)
    spare = SPARE_NUMBER_FROM
    result = []
    for number in numbers:
        if number is None:
            while spare in taken:
                spare += 1
            number = spare
            taken.add(spare)
        result.append(number)
    return result


def live_player(player: SquadPlayer, number: int) -> dict:
    role = line_role(player.position, player.is_goalkeeper)
    row: dict = {
        "nr": number,
        "name": display_name(player),
        "pos": LIVE_POSITIONS.get(role, ""),
        "ur": f"{player.birth_year % 100:02d}" if player.birth_year else "",
        "m": player.matches,
        "br": player.goals,
        "sr": round(player.goals / player.matches, 2) if player.matches and player.goals is not None else None,
    }
    if role is LineRole.GOALKEEPER and player.shots_faced:
        row["ob"] = player.saves or 0
        row["rz"] = player.shots_faced
        row["sk"] = round(100 * (player.saves or 0) / player.shots_faced)
    return row


def live_team(team: SheetTeamData, request: MatchSheetRequest) -> dict:
    players, _source = merge_squads(team, request.previous_season)
    ordered = order_players(players, request.order)
    return {
        "name": team.name,
        "short": team.name,
        "players": [live_player(p, n) for p, n in zip(ordered, live_numbers(ordered))],
    }


def build_live_protocol(data: MatchSheetData, request: MatchSheetRequest, today: date) -> LiveProtocol:
    match_date = request.match_date or today
    season = " ".join(part for part in (data.competition_name, data.season_code) if part)
    venue = ", ".join(part for part in (data.venue.name, data.venue.city, data.venue.country_code) if part) if data.venue else ""
    stats = f"Statystyki sezonu {data.season_code} (M, Br, Śr, %B)"
    if data.stats_until:
        stats += f" do {data.stats_until.strftime('%d.%m.%Y')}"
    base_name = live_base_name(match_date, data.home.name, data.away.name)
    match = {
        "id": None,
        "competition": season,
        "date": match_date.strftime("%d.%m.%Y"),
        "time": request.kickoff.strftime("%H:%M") if request.kickoff else "",
        "venue": venue,
        "statsNote": stats + ".",
        "A": live_team(data.home, request),
        "B": live_team(data.away, request),
    }
    return LiveProtocol(base_name=base_name, document={"format": LIVE_FORMAT, "version": LIVE_VERSION, "match": match})
