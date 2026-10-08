from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

from ehf.domain.goal_distribution import (
    GoalDistributionFilters,
    GoalDistributionReport,
    GoalFilterChoices,
    GoalMatch,
    GoalScoreline,
    SeriesKind,
    build_series,
    series_from_scorelines,
    series_kind,
)
from ehf.domain.matches import Choice
from ehf.interface.goal_distribution_views import (
    DistributionListView,
    GoalDistributionMatchesView,
    GoalDistributionView,
)
from ehf.interface.navigation import GORNY_PASEK, SIDEBAR, zarejestruj_kontekst_nawigacji
from ehf.services.goal_distribution import REPORT_GENDERS, GoalDistributionService

INTERFACE = Path(__file__).resolve().parents[1] / "ehf" / "interface"


def test_seria_wypelnia_luki_i_liczy_udzial() -> None:
    series = build_series({10: 1, 12: 3})

    assert [item.goals for item in series.bins] == [10, 11, 12]
    assert series.match_count == 4
    assert series.bins[2].share == 0.75
    assert series.bins[2].cumulative == 1
    assert series.modes == (12,)
    assert series.mean == 11.5
    assert series.median == 12


def test_mediana_parzysta_i_pusta_seria() -> None:
    assert build_series({1: 1, 3: 1}).median == 2
    assert build_series({1: 1, 3: 1}).modes == ()
    empty = build_series({})
    assert empty.match_count == 0
    assert empty.bins == ()
    assert empty.mean is None


def test_wyniki_rozkladaja_sie_na_trzy_serie() -> None:
    total, home, away = series_from_scorelines(
        (GoalScoreline(30, 28, 4), GoalScoreline(25, 25, 2))
    )

    assert total.match_count == 6
    assert {item.goals: item.matches for item in total.bins if item.matches} == {58: 4, 50: 2}
    assert home.modes == (30,)
    assert away.modes == (28,)


def test_ujemne_bramki_sa_odrzucone() -> None:
    with pytest.raises(ValueError):
        GoalScoreline(-1, 10, 1)
    with pytest.raises(ValueError):
        GoalDistributionFilters(gender="mixed")
    with pytest.raises(ValueError):
        series_kind("overtime")


class CzytnikPamieciowy:
    def __init__(self) -> None:
        self.filters: GoalDistributionFilters | None = None

    def fetch_choices(self) -> GoalFilterChoices:
        return GoalFilterChoices(
            seasons=(Choice("9", "2025/2026"),),
            competitions=(Choice("3", "Champions League"),),
        )

    def fetch_scorelines(self, filters: GoalDistributionFilters) -> tuple[GoalScoreline, ...]:
        self.filters = filters
        return (GoalScoreline(30, 28, 4), GoalScoreline(25, 25, 2))

    def fetch_matches(
        self, filters: GoalDistributionFilters, kind: SeriesKind, goals: int
    ) -> tuple[GoalMatch, ...]:
        self.selection = (filters, kind, goals)
        return (
            GoalMatch(
                7,
                datetime(2026, 3, 1, 18, 30),
                "2025/2026",
                "Champions League",
                "Kielce",
                "Barcelona",
                30,
                28,
            ),
        )


def test_serwis_sklada_raport() -> None:
    reader = CzytnikPamieciowy()
    filters = GoalDistributionFilters(season_id=9, competition_id=3, gender="women")

    report = GoalDistributionService(reader).report(filters)

    assert reader.filters == filters
    assert isinstance(report, GoalDistributionReport)
    assert report.total.match_count == 6
    assert GoalDistributionService(reader).genders() == REPORT_GENDERS
    matches = GoalDistributionService(reader).matches(filters, SeriesKind.TOTAL, 58)
    assert reader.selection == (filters, SeriesKind.TOTAL, 58)
    assert matches[0].score_label == "30:28"
    with pytest.raises(ValueError):
        GoalDistributionService(reader).matches(filters, SeriesKind.HOME, -1)


def _aplikacja(service: GoalDistributionService) -> Flask:
    aplikacja = Flask(
        "ehf_test",
        template_folder=str(INTERFACE / "templates"),
        static_folder=str(INTERFACE / "static"),
    )
    aplikacja.config["SECRET_KEY"] = "test"
    zarejestruj_kontekst_nawigacji(aplikacja)
    punkty = {pozycja.punkt_koncowy for pozycja in GORNY_PASEK}
    for _grupa, pozycje in SIDEBAR:
        punkty.update(pozycja.punkt_koncowy for pozycja in pozycje)
    punkty.discard("panel.lista_rozkladow")
    punkty.discard("panel.rozklad_bramek")
    punkty.discard("panel.goal_distribution_matches")

    def pusta(nazwa: str):
        def widok() -> str:
            return nazwa

        widok.__name__ = nazwa.replace(".", "_")
        return widok

    for punkt in sorted(punkty):
        aplikacja.add_url_rule(
            f"/__nav/{punkt.replace('.', '/')}",
            endpoint=punkt,
            view_func=pusta(punkt),
        )
    aplikacja.add_url_rule(
        "/rozklady",
        endpoint="panel.lista_rozkladow",
        view_func=DistributionListView.as_view("lista_rozkladow"),
    )
    aplikacja.add_url_rule(
        "/rozklady/bramki",
        endpoint="panel.rozklad_bramek",
        view_func=GoalDistributionView.as_view("rozklad_bramek", service=service),
    )
    aplikacja.add_url_rule(
        "/rozklady/bramki/matches",
        endpoint="panel.goal_distribution_matches",
        view_func=GoalDistributionMatchesView.as_view(
            "goal_distribution_matches", service=service
        ),
    )
    aplikacja.add_url_rule(
        "/mecze/<int:match_id>",
        endpoint="panel.match_detail",
        view_func=pusta("panel.match_detail"),
    )
    return aplikacja


def test_strony_rozkladu_renderuja_katalog_wykres_i_tabele() -> None:
    reader = CzytnikPamieciowy()
    klient = _aplikacja(GoalDistributionService(reader)).test_client()
    katalog = klient.get("/rozklady")
    assert katalog.status_code == 200
    tresc_katalogu = katalog.get_data(as_text=True)
    assert "Distribution catalog" in tresc_katalogu
    assert "Goals per match" in tresc_katalogu
    assert 'href="/rozklady/bramki"' in tresc_katalogu
    assert ">Distributions</span>" in tresc_katalogu

    odpowiedz = klient.get("/rozklady/bramki?season=9&competition=3&gender=women")
    tresc = odpowiedz.get_data(as_text=True)
    assert odpowiedz.status_code == 200
    assert reader.filters == GoalDistributionFilters(9, 3, "women")
    assert "Total goals" in tresc
    assert "Home goals" in tresc
    assert "Away goals" in tresc
    assert ">Men<" in tresc
    assert ">Women<" in tresc
    assert "goal-dist-chart" in tresc
    assert "data-goal-bar" in tresc
    assert "Cumulative" in tresc
    assert ">58<" in tresc
    assert "66.7%" in tresc
    assert "Champions League" in tresc
    assert klient.get("/rozklady/bramki?gender=mixed").status_code == 400

    mecze = klient.get("/rozklady/bramki/matches?series=total&goals=58&season=9")
    tresc_meczow = mecze.get_data(as_text=True)
    assert mecze.status_code == 200
    assert reader.selection == (GoalDistributionFilters(9, None, None), SeriesKind.TOTAL, 58)
    assert "Kielce" in tresc_meczow
    assert "30:28" in tresc_meczow
    assert 'href="/mecze/7"' in tresc_meczow
    assert klient.get("/rozklady/bramki/matches?series=overtime&goals=1").status_code == 400
