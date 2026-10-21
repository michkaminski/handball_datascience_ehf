from datetime import date, time

from ehf.domain.live_protocol import build_live_protocol, file_part, live_numbers
from ehf.domain.match_sheet import MatchSheetData, MatchSheetRequest, SheetTeamData, SquadPlayer


def player(number: str | None, last: str, position: str = "Left back", saves: int | None = None, shots: int | None = None) -> SquadPlayer:
    return SquadPlayer(
        person_id=hash(last) % 1000,
        name=f"{last} Jan",
        first_name="Jan",
        last_name=last,
        number=number,
        position=position,
        is_goalkeeper=position == "Goalkeeper",
        birth_year=1999,
        matches=4,
        goals=10,
        saves=saves,
        shots_faced=shots,
    )


def team(name: str, players: tuple[SquadPlayer, ...]) -> SheetTeamData:
    return SheetTeamData(club_id=1, name=name, country_code=None, current=players, previous=(), roster=())


def test_nazwa_pliku_bez_znakow_spoza_ascii() -> None:
    assert file_part("Orlen Wisła Płock") == "Orlen-Wisla-Plock"
    assert file_part("Aalborg Håndbold") == "Aalborg-Handbold"


def test_brakujace_i_powtorzone_numery_dostaja_wolne_od_100() -> None:
    assert live_numbers((player("7", "A"), player(None, "B"), player("7", "C"), player("100", "D"))) == [7, 101, 102, 100]


def test_dokument_ma_mecz_sklady_i_skutecznosc_bramkarza() -> None:
    data = MatchSheetData(
        season_code="2025-26",
        competition_name="EHF Champions League Men",
        home=team("Aalborg Håndbold", (player("1", "KEEPER", "Goalkeeper", 30, 100), player("9", "BACK"))),
        away=team("Barça", ()),
        venue=None,
        stats_until=date(2026, 10, 1),
    )
    request = MatchSheetRequest(season_id=5, home_id=1, away_id=2, match_date=date(2026, 10, 24), kickoff=time(18, 45))
    protocol = build_live_protocol(data, request, date(2026, 1, 1))
    assert protocol.zip_name == "2026-10-24_Aalborg-Handbold_Barca.zip"
    match = protocol.document["match"]
    assert (match["date"], match["time"], match["competition"]) == ("24.10.2026", "18:45", "EHF Champions League Men 2025-26")
    keeper, back = match["A"]["players"]
    assert keeper == {"nr": 1, "name": "KEEPER Jan", "pos": "B", "ur": "99", "m": 4, "br": 10, "sr": 2.5, "ob": 30, "rz": 100, "sk": 30}
    assert "sk" not in back and back["pos"] == "R"
    assert match["B"]["players"] == []


def test_bez_daty_meczu_plik_ma_dzisiejsza_date() -> None:
    data = MatchSheetData("2025-26", None, team("A", ()), team("B", ()), None, None)
    assert build_live_protocol(data, MatchSheetRequest(season_id=5, home_id=1, away_id=2), date(2026, 10, 21)).base_name == "2026-10-21_A_B"
