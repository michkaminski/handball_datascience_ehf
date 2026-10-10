from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask

from ehf.domain.attendance_analytics import (
    COMPLETENESS_NOTE,
    AttendanceFilterChoices,
    AttendanceFilters,
    AttendanceRecord,
    AttendanceReport,
    AttendanceStatsCalculator,
    AttendanceSummary,
    ClubAttendance,
    ClubSeasonMean,
    MatchAttendanceRecord,
    SeasonAttendance,
)
from ehf.domain.attendance_calendar import (
    DIMENSION_DAY_TYPE,
    DIMENSION_HEATMAP,
    DIMENSION_HOUR,
    DIMENSION_MONTH,
    DIMENSION_PHASE,
    DIMENSION_WEEKDAY,
    CalendarCalculator,
    CalendarCell,
)
from ehf.domain.attendance_cities import (
    CITY_NAMES_NOTE,
    CITY_SOURCE_NOTE,
    CityAttendance,
    CityBundle,
    CityCalculator,
    CityContribution,
    CityReport,
)
from ehf.domain.attendance_city_breakdown import CityCompetition, CitySeason, CityVenue
from ehf.domain.attendance_city_names import normalize_city_key
from ehf.domain.attendance_extended_records import ExtendedRecords
from ehf.domain.attendance_forecast import (
    MIN_FORECAST_ROWS,
    AttendanceForecaster,
    ForecastFeatureBuilder,
    OlsRegressor,
)
from ehf.domain.attendance_opponents import (
    OPPONENTS_CLUB_REQUIRED_NOTE,
    OpponentAttendance,
    OpponentCalculator,
    OpponentSection,
)
from ehf.domain.attendance_science import (
    CAUSATION_NOTE,
    SAMPLE_LIMIT,
    AttendanceScienceCalculator,
    MatchSample,
)
from ehf.domain.matches import Choice
from ehf.infrastructure.attendance_analytics_reader import (
    build_where,
    clubs_sql,
    known_predicate,
    top_matches_sql,
)
from ehf.infrastructure.attendance_cities_queries import (
    CITY_KEY_SQL,
    cities_sql,
    city_contributions_sql,
    contribution_from_row,
    city_from_row,
    matches_without_city_sql,
)
from ehf.infrastructure.attendance_city_breakdown_queries import (
    city_competitions_sql,
    city_seasons_sql,
    city_venues_sql,
    competition_from_row,
    season_from_row,
    venue_from_row,
)
from ehf.infrastructure.attendance_extended_queries import (
    RECORD_SPECS,
    calendar_sql,
    opponents_sql,
    record_sql,
)
from ehf.infrastructure.attendance_sample_query import sample_sql
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import PLAYED_SQL
from ehf.interface.attendance_analytics_chart import attendance_charts_payload
from ehf.interface.attendance_analytics_filters import attendance_filters_from_args
from ehf.interface.attendance_analytics_views import AttendanceAnalyticsView
from ehf.interface.navigation import GORNY_PASEK, SIDEBAR, zarejestruj_kontekst_nawigacji
from ehf.services.attendance_analytics import ATTENDANCE_GENDERS, AttendanceAnalyticsService

INTERFACE = Path(__file__).resolve().parents[1] / "ehf" / "interface"
TAB_KEYS = ("overview", "trends", "clubs", "cities", "records", "opponents", "calendar", "extended", "science")
calc = AttendanceStatsCalculator


def _season(season_id: int, code: str, year: int, values: list[int | None]) -> SeasonAttendance:
    return SeasonAttendance(season_id, code, year, calc.summarize(values))


def test_null_is_missing_and_zero_is_known() -> None:
    assert calc.known_values([None, 0, 500, -5]) == (0, 500)
    assert calc.known_values([None, 0, 500], exclude_zeros=True) == (500,)

    summary = calc.summarize([None, 0, 1000, 2000, 3000])

    assert summary.played == 5
    assert summary.known == 4
    assert summary.excluded == 1
    assert summary.total == 6000
    assert summary.mean == 1500
    assert summary.median == 1500
    assert (summary.q1, summary.q3) == (750, 2250)
    assert (summary.minimum, summary.maximum) == (0, 3000)
    assert summary.zero_matches == 1
    assert summary.coverage == 0.8
    assert summary.coverage_label == "80.0%"


def test_missing_values_never_lower_the_mean() -> None:
    assert calc.summarize([None, None, 1000]).mean == 1000
    assert calc.summarize([0, 1000]).mean == 500


def test_exclude_zeros_drops_closed_doors_from_the_sample() -> None:
    summary = calc.summarize([0, 0, 1000], exclude_zeros=True)

    assert summary.known == 1
    assert summary.mean == 1000
    assert summary.zero_matches == 2
    assert summary.coverage == pytest.approx(1 / 3)


def test_empty_and_unknown_samples_have_no_statistics() -> None:
    empty = calc.summarize([])
    unknown = calc.summarize([None, None])

    assert empty.coverage is None
    assert empty.coverage_label == "—"
    assert empty.mean is None
    assert empty.median_label == "—"
    assert empty.maximum_label == "—"
    assert unknown.played == 2
    assert unknown.known == 0
    assert unknown.mean is None
    assert unknown.total == 0
    assert calc.quartiles([]) == (None, None)


def test_percentiles_interpolate_like_percentile_cont() -> None:
    assert calc.percentile([10], 0.25) == 10
    assert calc.median([1, 2, 3, 4]) == 2.5
    assert calc.quartiles([1, 2, 3, 4, 5]) == (2, 4)
    with pytest.raises(ValueError):
        calc.percentile([1], 1.5)


def test_summary_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError):
        AttendanceSummary(1, 2, 0, None, None, None, None, None, None)


def test_year_over_year_change() -> None:
    assert calc.yoy_change(110, 100) == pytest.approx(0.1)
    assert calc.yoy_change(90, 100) == pytest.approx(-0.1)
    assert calc.yoy_change(None, 100) is None
    assert calc.yoy_change(100, None) is None
    assert calc.yoy_change(100, 0) is None


def test_moving_average_and_slope() -> None:
    assert calc.moving_average([100, 200, None, 400], window=2) == (100, 150, None, 400)
    assert calc.linear_slope([(2020, 100), (2021, 200), (2022, 300)]) == pytest.approx(100)
    assert calc.linear_slope([(2020, 100), (2021, None)]) is None
    assert calc.linear_slope([(2020, 100), (2020, 200)]) is None
    with pytest.raises(ValueError):
        calc.moving_average([1], window=0)


def test_trend_orders_seasons_and_computes_yoy_and_slope() -> None:
    trend = calc.build_trend(
        [
            _season(3, "2022/2023", 2022, [3000]),
            _season(1, "2020/2021", 2020, [1000]),
            _season(2, "2021/2022", 2021, [None]),
        ]
    )

    assert [point.season.season_code for point in trend.points] == [
        "2020/2021",
        "2021/2022",
        "2022/2023",
    ]
    assert [point.yoy for point in trend.points] == [None, None, None]
    assert trend.slope == pytest.approx(1000)
    assert trend.slope_label == "+1 000 per season"

    steady = calc.build_trend(
        [_season(1, "a", 2020, [1000]), _season(2, "b", 2021, [1500])]
    )
    assert steady.points[1].yoy == pytest.approx(0.5)
    assert steady.points[1].yoy_label == "+50.0%"
    assert steady.points[1].moving_average == 1250


def test_comparison_pair_uses_selected_or_latest_known_season() -> None:
    trend = calc.build_trend(
        [
            _season(1, "2021/2022", 2021, [1000]),
            _season(2, "2022/2023", 2022, [1500]),
            _season(3, "2023/2024", 2023, [None]),
        ]
    )

    latest = calc.comparison_pair(trend, None)
    selected = calc.comparison_pair(trend, 1)
    unknown_target = calc.comparison_pair(trend, 3)

    assert latest is not None
    assert latest.caption == "2022/2023 vs 2021/2022"
    assert latest.change == pytest.approx(0.5)
    assert selected is None
    assert unknown_target is None
    assert calc.comparison_pair(calc.build_trend([]), None) is None


def _fixture_matches() -> list[MatchAttendanceRecord]:
    return [
        MatchAttendanceRecord(1, "Kielce", 2, "Barcelona", 4000),
        MatchAttendanceRecord(1, "Kielce", 3, "Veszprem", None),
        MatchAttendanceRecord(2, "Barcelona", 1, "Kielce", 9000),
        MatchAttendanceRecord(2, "Barcelona", 3, "Veszprem", 0),
        MatchAttendanceRecord(None, "Unknown", 1, "Kielce", 7000),
    ]


def test_home_ranking_never_credits_the_away_club() -> None:
    clubs = {club.club_id: club for club in calc.aggregate_home_clubs(_fixture_matches())}

    assert set(clubs) == {1, 2}
    assert clubs[1].summary.played == 2
    assert clubs[1].summary.known == 1
    assert clubs[1].summary.total == 4000
    assert clubs[2].summary.played == 2
    assert clubs[2].summary.total == 9000
    assert clubs[2].summary.mean == 4500
    assert clubs[2].summary.minimum == 0


def test_home_ranking_can_exclude_zeros() -> None:
    clubs = {
        club.club_id: club
        for club in calc.aggregate_home_clubs(_fixture_matches(), exclude_zeros=True)
    }

    assert clubs[2].summary.mean == 9000
    assert clubs[2].summary.known == 1


def test_ranking_sorts_by_mean_with_positions_and_yoy() -> None:
    clubs = calc.aggregate_home_clubs(_fixture_matches())
    clubs += (ClubAttendance(5, "Nowhere", calc.summarize([None])),)
    trend = calc.build_trend(
        [_season(1, "2022/2023", 2022, [1000]), _season(2, "2023/2024", 2023, [2000])]
    )
    pair = calc.comparison_pair(trend, None)
    means = [
        ClubSeasonMean(1, 1, 2000.0),
        ClubSeasonMean(1, 2, 3000.0),
        ClubSeasonMean(2, 2, 4500.0),
    ]

    ranking = calc.rank_clubs(clubs, means, pair)

    assert [row.club.club_name for row in ranking] == ["Barcelona", "Kielce"]
    assert [row.position for row in ranking] == [1, 2]
    assert ranking[0].yoy is None
    assert ranking[0].yoy_label == "—"
    assert ranking[1].yoy == pytest.approx(0.5)
    assert calc.rank_clubs(clubs, means, None)[1].yoy is None
    assert len(calc.rank_clubs(clubs, means, pair, limit=1)) == 1


def test_filters_validate_gender_and_date_range() -> None:
    with pytest.raises(ValueError):
        AttendanceFilters(gender="mixed")
    with pytest.raises(ValueError):
        AttendanceFilters(date_from=date(2024, 5, 1), date_to=date(2024, 1, 1))
    filters = AttendanceFilters(season_id=3, date_from=date(2024, 1, 1))
    assert filters.has_date_range
    assert filters.without_season().season_id is None
    assert not AttendanceFilters().has_date_range


def test_filters_are_parsed_from_query_args() -> None:
    filters = attendance_filters_from_args(
        {
            "season": "9",
            "competition": "",
            "gender": "women",
            "phase": " Final ",
            "club": "4",
            "exclude_zeros": "1",
            "date_from": "2024-01-02",
            "date_to": "2024-03-04",
        }
    )

    assert filters == AttendanceFilters(
        season_id=9,
        gender="women",
        phase="Final",
        club_id=4,
        exclude_zeros=True,
        date_from=date(2024, 1, 2),
        date_to=date(2024, 3, 4),
    )
    assert attendance_filters_from_args({}) == AttendanceFilters()
    with pytest.raises(ValueError):
        attendance_filters_from_args({"gender": "mixed"})
    with pytest.raises(ValueError):
        attendance_filters_from_args({"season": "abc"})
    with pytest.raises(ValueError):
        attendance_filters_from_args({"date_from": "yesterday"})


def test_sql_uses_played_matches_home_club_and_known_predicate() -> None:
    filters = AttendanceFilters(season_id=2, club_id=7, exclude_zeros=True)

    where, params = build_where(filters)
    sql, club_params = clubs_sql(filters)
    top_sql, top_params = top_matches_sql(filters, 50)
    no_season_where, no_season_params = build_where(filters, with_season=False)

    assert where.startswith(PLAYED_SQL)
    assert "m.home_club_id = %s" in where
    assert params == [2, 7]
    assert no_season_params == [7]
    assert "s.id" not in no_season_where
    assert "GROUP BY m.home_club_id" in sql
    assert "m.home_club_id IS NOT NULL" in sql
    assert "GROUP BY m.away_club_id" not in sql
    assert "m.spectators > 0" in sql
    assert club_params == [2, 7]
    assert "m.spectators > 0" in top_sql
    assert top_params == [2, 7, 50]
    assert "m.spectators >= 0" in clubs_sql(AttendanceFilters())[0]


def _sample(
    match_id: int,
    day: int,
    spectators: int,
    *,
    home_id: int | None = 1,
    away_id: int | None = 2,
    home_goals: int | None = None,
    away_goals: int | None = None,
    hour: int = 18,
    month: int = 1,
    dated: bool = True,
) -> MatchSample:
    return MatchSample(
        match_id=match_id,
        kickoff=datetime(2023, month, day, hour) if dated else None,
        spectators=spectators,
        home_club_id=home_id,
        away_club_id=away_id,
        home=f"Home {home_id}",
        away=f"Away {away_id}",
        home_goals=home_goals,
        away_goals=away_goals,
    )


def _timeline(count: int) -> list[MatchSample]:
    start = datetime(2022, 9, 1, 18)
    matches = []
    for index in range(count):
        kickoff = start + timedelta(days=index, hours=index % 3)
        home = index % 3 + 1
        weekend = 1 if kickoff.weekday() >= 5 else 0
        spectators = 2000 + 300 * home + 500 * weekend + (index * 37) % 90
        matches.append(
            MatchSample(
                match_id=index + 1,
                kickoff=kickoff,
                spectators=spectators,
                home_club_id=home,
                away_club_id=(home % 3) + 1,
                home=f"Home {home}",
                away=f"Away {(home % 3) + 1}",
                home_goals=28 + index % 5,
                away_goals=25 + index % 4,
            )
        )
    return matches


def _record(match_id: int, spectators: int, home: str = "Kielce") -> AttendanceRecord:
    return AttendanceRecord(
        match_id,
        datetime(2024, 3, 1, 18, 30),
        "2023/2024",
        "Champions League",
        home,
        "Barcelona",
        30,
        28,
        "Hala Legionow, Kielce",
        spectators,
    )


def _cities() -> tuple[CityAttendance, ...]:
    return (
        CityAttendance("Kielce", 4, 3, 12000, 4000.0, 4000.0, 3000, 6000, 1, 2),
        CityAttendance("Barcelona", 2, 2, 18000, 9000.0, 9000.0, 6000, 12000, 2, 1),
        CityAttendance("Nowhere", 1, 0, 0, None, None, None, None, 1, 1),
    )


def _seasons() -> tuple[CitySeason, ...]:
    return (
        CitySeason("KIELCE", "2023/2024", 2023, 2, 2, 7000, 3500.0, 3500.0, 4000),
        CitySeason("Kielce", "2022/2023", 2022, 2, 1, 5000, 5000.0, 5000.0, 5000),
        CitySeason("Barcelona", "2023/2024", 2023, 2, 2, 18000, 9000.0, 9000.0, 12000),
        CitySeason("Elsewhere", "2023/2024", 2023, 1, 1, 100, 100.0, 100.0, 100),
    )


def _competitions() -> tuple[CityCompetition, ...]:
    return (
        CityCompetition("Kielce", "EHF Cup", 1, 1, 4000, 4000.0, 4000.0, 4000),
        CityCompetition("kielce ", "Champions League", 3, 2, 8000, 4000.0, 4000.0, 6000),
        CityCompetition("Barcelona", "Champions League", 2, 2, 18000, 9000.0, 9000.0, 12000),
        CityCompetition("Elsewhere", "EHF Cup", 1, 1, 100, 100.0, 100.0, 100),
    )


def _venues() -> tuple[CityVenue, ...]:
    return (
        CityVenue("Kielce", 11, "Hala Legionow", 4, 3, 12000, 4000.0, 6000, 4000.0),
        CityVenue("Barcelona", 21, "Palau Blaugrana", 2, 2, 18000, 9000.0, 12000, 9000.0),
        CityVenue("Barcelona", 22, "Closed hall", 1, 0, 0, None, None, None),
    )


def _bundle(missing: int = 4) -> CityBundle:
    return CityBundle(
        cities=_cities(),
        contributions=_contributions(),
        seasons=_seasons(),
        competitions=_competitions(),
        venues=_venues(),
        matches_without_city=missing,
    )


def _contributions() -> tuple[CityContribution, ...]:
    return (
        CityContribution("Kielce", 1, "Kielce", "Champions League", 3, 2, 8000, 4000.0, 6000),
        CityContribution("Kielce", 1, "Kielce", "EHF Cup", 1, 1, 4000, 4000.0, 4000),
        CityContribution("Barcelona", 2, "Barcelona", "Champions League", 2, 2, 18000, 9000.0, 12000),
        CityContribution("Kielce", None, "—", "EHF Cup", 1, 0, 0, None, None),
        CityContribution("Elsewhere", 5, "Other", "EHF Cup", 1, 1, 100, 100.0, 100),
    )


class MemoryReader:
    def __init__(self) -> None:
        self.filters: list[AttendanceFilters] = []
        self.season_means_calls = 0
        self.opponent_calls: list[AttendanceFilters] = []
        self.calendar_calls: list[AttendanceFilters] = []
        self.extended_calls: list[AttendanceFilters] = []
        self.sample_calls: list[tuple[AttendanceFilters, int]] = []
        self.city_calls: list[AttendanceFilters] = []
        self.city_limits: list[int] = []
        self.contribution_limits: list[int] = []
        self.sample = _timeline(45)

    def fetch_city_bundle(
        self, filters: AttendanceFilters, city_limit: int, contribution_limit: int
    ) -> CityBundle:
        self.city_calls.append(filters)
        self.city_limits.append(city_limit)
        self.contribution_limits.append(contribution_limit)
        return _bundle()

    def fetch_opponents(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[OpponentAttendance, ...]:
        self.opponent_calls.append(filters)
        return (
            OpponentAttendance(9, "Barcelona", 4, 3, 9000.0, 12000),
            OpponentAttendance(8, "Veszprem", 2, 2, 3000.0, 3500),
            OpponentAttendance(7, "Unknown", 1, 0, None, None),
        )

    def fetch_calendar(self, filters: AttendanceFilters) -> tuple[CalendarCell, ...]:
        self.calendar_calls.append(filters)
        return (
            CalendarCell(DIMENSION_MONTH, "3", None, 4, 3, 5000.0),
            CalendarCell(DIMENSION_WEEKDAY, "5", None, 4, 3, 6500.0),
            CalendarCell(DIMENSION_HOUR, "18", None, 4, 3, 5200.0),
            CalendarCell(DIMENSION_DAY_TYPE, "weekend", None, 2, 2, 6500.0),
            CalendarCell(DIMENSION_PHASE, "Final", None, 1, 1, 9000.0),
            CalendarCell(DIMENSION_HEATMAP, "5", "18", 4, 3, 6500.0),
        )

    def fetch_extended_records(self, filters: AttendanceFilters) -> ExtendedRecords:
        self.extended_calls.append(filters)
        return ExtendedRecords(
            seasons=(_record(11, 6100),),
            clubs=(_record(12, 6200, "Barcelona"),),
            venues=(_record(13, 6300),),
            finals=(_record(14, 6400),),
            rivalries=(_record(15, 6500),),
        )

    def fetch_match_sample(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[MatchSample, ...]:
        self.sample_calls.append((filters, limit))
        return tuple(self.sample)

    def fetch_choices(self) -> AttendanceFilterChoices:
        return AttendanceFilterChoices(
            seasons=(Choice("2", "2023/2024"),),
            competitions=(Choice("3", "Champions League"),),
            phases=(Choice("Final", "Final"),),
            clubs=(Choice("1", "Kielce"),),
        )

    def fetch_summary(self, filters: AttendanceFilters) -> AttendanceSummary:
        self.filters.append(filters)
        return calc.summarize([None, 0, 4000, 6000])

    def fetch_season_summaries(
        self, filters: AttendanceFilters
    ) -> tuple[SeasonAttendance, ...]:
        return (
            _season(1, "2022/2023", 2022, [4000, 4000]),
            _season(2, "2023/2024", 2023, [5000, 7000, None]),
        )

    def fetch_club_attendance(self, filters: AttendanceFilters) -> tuple[ClubAttendance, ...]:
        return calc.aggregate_home_clubs(_fixture_matches())

    def fetch_club_season_means(
        self, filters: AttendanceFilters
    ) -> tuple[ClubSeasonMean, ...]:
        self.season_means_calls += 1
        return (ClubSeasonMean(1, 1, 2000.0), ClubSeasonMean(1, 2, 3000.0))

    def fetch_top_matches(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[AttendanceRecord, ...]:
        return (
            AttendanceRecord(
                7,
                datetime(2024, 3, 1, 18, 30),
                "2023/2024",
                "Champions League",
                "Kielce",
                "Barcelona",
                30,
                28,
                "Hala Legionow, Kielce",
                6000,
            ),
        )


def test_service_builds_the_report() -> None:
    reader = MemoryReader()
    filters = AttendanceFilters(gender="men")

    report = AttendanceAnalyticsService(reader).report(filters)

    assert isinstance(report, AttendanceReport)
    assert reader.filters == [filters]
    assert report.summary.known == 3
    assert report.season_pair is not None
    assert report.season_pair.change == pytest.approx(0.5)
    assert report.yoy_label == "+50.0%"
    assert report.ranking[0].club.club_name == "Barcelona"
    assert report.ranking[1].yoy == pytest.approx(0.5)
    assert report.record is not None
    assert report.record.score_label == "30:28"
    assert report.record.spectators_label == "6 000"
    assert COMPLETENESS_NOTE in report.completeness_notes
    assert any("closed-doors" in note for note in report.completeness_notes)
    assert any("fill rate" in note for note in report.completeness_notes)
    assert AttendanceAnalyticsService(reader).genders() == ATTENDANCE_GENDERS


def test_service_skips_year_over_year_for_a_date_range() -> None:
    reader = MemoryReader()

    report = AttendanceAnalyticsService(reader).report(
        AttendanceFilters(date_from=date(2024, 1, 1), exclude_zeros=True)
    )

    assert report.season_pair is None
    assert report.yoy_label == "—"
    assert report.yoy_caption == "No comparable previous season"
    assert reader.season_means_calls == 0
    assert all(row.yoy is None for row in report.ranking)
    assert any("excluded by the filter" in note for note in report.completeness_notes)


def _app(service: AttendanceAnalyticsService) -> Flask:
    app = Flask(
        "ehf_test",
        template_folder=str(INTERFACE / "templates"),
        static_folder=str(INTERFACE / "static"),
    )
    app.config["SECRET_KEY"] = "test"
    zarejestruj_kontekst_nawigacji(app)
    endpoints = {item.punkt_koncowy for item in GORNY_PASEK}
    for _group, items in SIDEBAR:
        endpoints.update(item.punkt_koncowy for item in items)
    endpoints.discard("panel.attendance_analytics")
    endpoints.update({"panel.match_detail", "panel.team_detail", "panel.venue_detail"})

    def stub(name: str):
        def view(**_kwargs) -> str:
            return name

        view.__name__ = name.replace(".", "_")
        return view

    for endpoint in sorted(endpoints):
        rule = f"/__nav/{endpoint.replace('.', '/')}"
        if endpoint == "panel.match_detail":
            rule = "/mecze/<int:match_id>"
        if endpoint == "panel.team_detail":
            rule = "/druzyny/<int:club_id>"
        if endpoint == "panel.venue_detail":
            rule = "/hale/<int:venue_id>"
        app.add_url_rule(rule, endpoint=endpoint, view_func=stub(endpoint))
    app.add_url_rule(
        "/raporty/frekwencja",
        endpoint="panel.attendance_analytics",
        view_func=AttendanceAnalyticsView.as_view("attendance_analytics", service=service),
    )
    return app


def test_dashboard_renders_filters_kpis_trends_ranking_and_records() -> None:
    reader = MemoryReader()
    client = _app(AttendanceAnalyticsService(reader)).test_client()

    response = client.get(
        "/raporty/frekwencja?season=2&gender=men&exclude_zeros=1&date_from=2024-01-01"
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert reader.filters == [
        AttendanceFilters(
            season_id=2, gender="men", exclude_zeros=True, date_from=date(2024, 1, 1)
        )
    ]
    assert "Matches without known attendance are excluded from averages." in page
    assert "Total spectators" in page
    assert "Matches with attendance" in page
    assert "Played matches" in page
    assert "Coverage" in page
    assert "Record attendance" in page
    assert 'href="/mecze/7"' in page
    assert "Seasonal trends" in page
    assert 'role="tablist"' in page and "data-attendance-tabs" in page
    assert 'data-chart="trend"' in page and 'data-chart="coverage"' in page
    assert 'data-chart="clubs"' in page
    assert "att-nav" not in page
    assert "2023/2024" in page
    assert "Home attendance by club" in page
    assert 'href="/druzyny/2"' in page
    assert "data-attendance-search" in page
    assert "Attendance records" in page
    assert "Hala Legionow, Kielce" in page
    assert "30:28" in page
    assert ">Men<" in page
    assert ">Women<" in page
    assert "name=\"exclude_zeros\"" in page and "checked" in page
    assert 'value="2024-01-01"' in page
    assert "Attendance</a>" in page or "<span>Attendance</span>" in page


def test_dashboard_renders_stage_two_and_three_sections() -> None:
    reader = MemoryReader()
    client = _app(AttendanceAnalyticsService(reader)).test_client()

    page = client.get("/raporty/frekwencja?club=1&season=2").get_data(as_text=True)

    for heading in (
        "Opponents",
        "Calendar",
        "Extended records",
        "Season records",
        "Club home records",
        "Venue records",
        "Finals-like matches",
        "Rivalry pairs",
        "Data science",
        "Distribution",
        "Anomalies",
        "Weekday effect",
        "Opponent effect",
        "Result correlation",
        "Forecast",
    ):
        assert f">{heading}<" in page, heading
    for tab in TAB_KEYS:
        assert f'data-tab="{tab}"' in page, tab
        assert f'id="att-panel-{tab}"' in page, tab
    assert 'href="/druzyny/9"' in page
    assert "Diff vs club mean" in page
    for chart in (
        "trend",
        "coverage",
        "clubs",
        "cities",
        "heatmap",
        "months",
        "weekdays",
        "hours",
        "opponents",
        "histogram",
        "weekdayEffect",
    ):
        assert f'data-chart="{chart}"' in page, chart
    assert page.count('id="attendance-charts-data"') == 1
    assert "attendance-chart-data" not in page and "attendance-heatmap-data" not in page
    assert "Association, not causation" in page
    assert CAUSATION_NOTE in page.replace("&#39;", "'")
    assert 'href="/mecze/12"' in page and 'href="/mecze/15"' in page
    assert "Linear regression (OLS)" in page
    assert reader.opponent_calls == [AttendanceFilters(season_id=2, club_id=1)]
    assert reader.calendar_calls == [AttendanceFilters(season_id=2, club_id=1)]
    assert reader.extended_calls == [AttendanceFilters(season_id=2, club_id=1)]
    assert reader.sample_calls == [(AttendanceFilters(season_id=2, club_id=1), SAMPLE_LIMIT)]


def test_dashboard_requires_a_home_club_for_opponents() -> None:
    reader = MemoryReader()
    client = _app(AttendanceAnalyticsService(reader)).test_client()

    page = client.get("/raporty/frekwencja").get_data(as_text=True)

    assert "Select a home club in the filters" in page
    assert reader.opponent_calls == []
    assert "Opponent effect needs a home club filter" in page


def test_dashboard_warns_when_forecast_has_too_few_matches() -> None:
    reader = MemoryReader()
    reader.sample = reader.sample[:10]
    client = _app(AttendanceAnalyticsService(reader)).test_client()

    page = client.get("/raporty/frekwencja").get_data(as_text=True)

    assert "Forecast skipped" in page
    assert "Linear regression (OLS)" not in page


def test_dashboard_without_sample_shows_empty_science() -> None:
    reader = MemoryReader()
    reader.sample = []
    client = _app(AttendanceAnalyticsService(reader)).test_client()

    response = client.get("/raporty/frekwencja")

    assert response.status_code == 200
    assert "No matches with known attendance for the selected filters." in response.get_data(as_text=True)


def test_histogram_bins_cover_all_values_and_the_maximum() -> None:
    values = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    bins = AttendanceScienceCalculator.histogram(values, bins=5)

    assert len(bins) == 5
    assert sum(item.count for item in bins) == len(values)
    assert bins[0].lower == 0
    assert bins[-1].upper == 100
    assert bins[-1].count >= 1
    assert [item.count for item in bins] == [2, 2, 2, 2, 3]
    assert bins[-1].relative == 1
    assert sum(item.share for item in bins) == pytest.approx(1)
    assert bins[0].label == "0 – 20"


def test_histogram_handles_empty_constant_and_invalid_input() -> None:
    constant = AttendanceScienceCalculator.histogram([500, 500, 500])

    assert AttendanceScienceCalculator.histogram([]) == ()
    assert len(constant) == 1 and constant[0].count == 3
    with pytest.raises(ValueError):
        AttendanceScienceCalculator.histogram([1], bins=0)


def test_percentile_points_follow_the_requested_levels() -> None:
    points = AttendanceScienceCalculator.percentiles(list(range(0, 101)))

    assert [point.label for point in points] == ["p10", "p25", "p50", "p75", "p90", "p95"]
    assert [point.value for point in points] == pytest.approx([10, 25, 50, 75, 90, 95])
    assert all(point.value is None for point in AttendanceScienceCalculator.percentiles([]))
    assert AttendanceScienceCalculator.distribution([]) is None


def test_stdev_and_coefficient_of_variation() -> None:
    values = [2, 4, 4, 4, 5, 5, 7, 9]

    deviation = AttendanceScienceCalculator.stdev(values)

    assert deviation == pytest.approx(2.13809, abs=1e-4)
    assert AttendanceScienceCalculator.coefficient_of_variation(values) == pytest.approx(
        deviation / 5
    )
    assert AttendanceScienceCalculator.stdev([5]) is None
    assert AttendanceScienceCalculator.coefficient_of_variation([0, 0, 0]) is None
    assert AttendanceScienceCalculator.coefficient_of_variation([5]) is None


def test_stability_flags_small_samples() -> None:
    small = AttendanceScienceCalculator.stability([1000, 2000, 3000])
    large = AttendanceScienceCalculator.stability([1000, 2000, 3000, 4000, 5000, 6000])

    assert small is not None and small.small_sample
    assert small.note is not None and "Small sample" in small.note
    assert small.cv_label == "50.0%"
    assert large is not None and not large.small_sample and large.note is None
    assert AttendanceScienceCalculator.stability([]) is None


def test_iqr_fences_and_anomalies_list_match_ids() -> None:
    sample = [_sample(index, 1 + index % 28, 100 + index) for index in range(1, 11)]
    sample.append(_sample(100, 2, 1000))
    sample.append(_sample(101, 3, 0))

    fences = AttendanceScienceCalculator.iqr_fences([m.spectators for m in sample])
    report = AttendanceScienceCalculator.anomalies(sample)

    assert fences is not None and report is not None
    assert (report.lower_fence, report.upper_fence) == fences
    assert report.lower_fence == pytest.approx(report.q1 - 1.5 * (report.q3 - report.q1))
    assert report.upper_fence == pytest.approx(report.q3 + 1.5 * (report.q3 - report.q1))
    assert [item.match_id for item in report.high] == [100]
    assert [item.match_id for item in report.low] == [101]
    assert report.high[0].deviation > 0 > report.low[0].deviation
    assert report.count_label == "2"
    assert AttendanceScienceCalculator.anomalies(sample[:3]) is None
    assert AttendanceScienceCalculator.iqr_fences([]) is None


def test_anomalies_are_limited_and_ordered_by_severity() -> None:
    sample = [_sample(index, 1 + index % 28, 100) for index in range(1, 41)]
    sample += [_sample(200 + index, 5, 1000 + index) for index in range(5)]

    report = AttendanceScienceCalculator.anomalies(sample, limit=3)

    assert report is not None
    assert report.high_count == 5
    assert [item.match_id for item in report.high] == [204, 203, 202]


def test_weekday_effect_uses_kickoff_weekday_and_flags_small_samples() -> None:
    saturdays = [_sample(index, 7 + 7 * (index % 3), 4000 + index) for index in range(6)]
    monday = [_sample(50, 2, 1000)]
    undated = [_sample(60, 1, 9999, dated=False)]

    effect = AttendanceScienceCalculator.weekday_effect(saturdays + monday + undated)

    by_weekday = {item.weekday: item for item in effect}
    assert set(by_weekday) == {0, 5}
    assert by_weekday[5].n == 6 and not by_weekday[5].small_sample
    assert by_weekday[0].n == 1 and by_weekday[0].small_sample
    assert by_weekday[0].label == "Mon" and by_weekday[5].label == "Sat"
    assert by_weekday[0].mean == 1000


def test_opponent_effect_compares_with_the_host_mean() -> None:
    sample = [
        _sample(1, 1, 1000, away_id=2),
        _sample(2, 2, 3000, away_id=2),
        _sample(3, 3, 5000, away_id=3),
        _sample(4, 4, 9999, home_id=7, away_id=2),
    ]

    effect = AttendanceScienceCalculator.opponent_effect(sample, club_id=1)
    skipped = AttendanceScienceCalculator.opponent_effect(sample, club_id=None)
    missing = AttendanceScienceCalculator.opponent_effect(sample, club_id=99)

    assert effect.host_mean == 3000
    assert [row.opponent_id for row in effect.rows] == [3, 2]
    assert effect.rows[0].difference == 2000
    assert effect.rows[1].difference == -1000
    assert all(row.small_sample for row in effect.rows)
    assert skipped.rows == () and skipped.note is not None and "home club" in skipped.note
    assert missing.rows == () and missing.note is not None


def test_opponent_effect_keeps_the_strongest_and_weakest_draws() -> None:
    sample = [
        _sample(index, 1 + index % 28, 1000 + index * 10, away_id=index + 10)
        for index in range(1, 31)
    ]

    effect = AttendanceScienceCalculator.opponent_effect(sample, club_id=1, limit=3)

    assert len(effect.rows) == 6
    assert effect.rows[0].difference > 0 > effect.rows[-1].difference


def test_pearson_correlation_matches_known_values() -> None:
    pearson = AttendanceScienceCalculator.pearson

    assert pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1)
    assert pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1)
    assert pearson([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) == pytest.approx(0.8)
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([1, 2], [1, 2]) is None
    with pytest.raises(ValueError):
        pearson([1, 2, 3], [1, 2])


def test_result_correlations_ignore_matches_without_scores_and_warn_on_small_n() -> None:
    sample = [
        _sample(1, 1, 1000, home_goals=30, away_goals=20),
        _sample(2, 2, 2000, home_goals=28, away_goals=26),
        _sample(3, 3, 3000, home_goals=25, away_goals=25),
        _sample(4, 4, 4000, home_goals=22, away_goals=30),
        _sample(5, 5, 9000),
    ]

    difference, total = AttendanceScienceCalculator.correlations(sample)

    assert difference.n == 4 and total.n == 4
    assert difference.coefficient is not None and difference.coefficient < -0.9
    assert difference.strength == "strong"
    assert difference.small_sample and difference.warning is not None
    assert "goal difference" in difference.label
    assert total.coefficient is not None
    assert difference.coefficient_label.startswith("-")


def test_correlation_without_scores_is_not_available() -> None:
    difference, total = AttendanceScienceCalculator.correlations([_sample(1, 1, 1000)])

    assert difference.coefficient is None and total.coefficient is None
    assert difference.coefficient_label == "—"
    assert difference.strength == "not available"


def test_ols_recovers_a_linear_relationship() -> None:
    features = [[x, (x * 7) % 5] for x in range(1, 21)]
    targets = [5 + 2 * row[0] - 3 * row[1] for row in features]

    model = OlsRegressor.fit(features, targets)

    assert model.predict([30, 2]) == pytest.approx(5 + 60 - 6, abs=1e-3)
    assert model.raw_weights == pytest.approx((2, -3), abs=1e-3)
    with pytest.raises(ValueError):
        OlsRegressor.fit([], [])


def test_ols_ignores_constant_features() -> None:
    features = [[x, 1.0] for x in range(1, 11)]
    targets = [10 + 4 * x for x in range(1, 11)]

    model = OlsRegressor.fit(features, targets)

    assert model.predict([20, 1.0]) == pytest.approx(90, abs=1e-3)
    assert model.raw_weights[1] == pytest.approx(0, abs=1e-6)


def test_forecast_features_only_use_earlier_matches() -> None:
    sample = [
        _sample(1, 1, 100),
        _sample(2, 2, 300),
        _sample(3, 3, 999),
        _sample(4, 3, 5000, home_id=2),
    ]

    rows = {row.match_id: row for row in ForecastFeatureBuilder.build(sample)}

    assert 1 not in rows
    assert rows[2].features[0] == 100
    assert rows[3].features[0] == 200
    assert rows[4].features[0] == pytest.approx((100 + 300) / 2)
    assert rows[2].target == 300
    assert rows[3].features[1] == 0 and rows[3].features[4] == 18


def test_forecast_features_ignore_matches_without_kickoff_and_scores() -> None:
    plain = [_sample(index, index, 1000 + index) for index in range(1, 6)]
    noisy = [
        *(
            MatchSample(
                m.match_id, m.kickoff, m.spectators, m.home_club_id, m.away_club_id,
                m.home, m.away, 99, 0,
            )
            for m in plain
        ),
        _sample(77, 1, 123456, dated=False),
    ]

    assert ForecastFeatureBuilder.build(plain) == ForecastFeatureBuilder.build(noisy)


def test_forecast_requires_enough_matches() -> None:
    enough = AttendanceForecaster.forecast(_timeline(MIN_FORECAST_ROWS + 1))
    short = AttendanceForecaster.forecast(_timeline(MIN_FORECAST_ROWS))

    assert enough.result is not None and enough.warning is None
    assert short.result is None
    assert short.warning is not None and "Forecast skipped" in short.warning
    assert AttendanceForecaster.forecast([]).result is None


def test_forecast_trains_on_earlier_matches_and_tests_on_the_latest_fifth() -> None:
    outcome = AttendanceForecaster.forecast(_timeline(61))

    assert outcome.result is not None
    result = outcome.result
    assert result.train_size + result.test_size == 60
    assert result.test_size == 12
    assert result.train_end < result.test_start
    assert result.mae >= 0 and result.rmse >= result.mae
    assert result.baseline_mae > 0
    assert len(result.coefficients) == 5
    assert result.improvement is not None
    assert result.split_label.startswith("Trained up to")


def test_forecast_never_peeks_at_the_test_period_or_scores() -> None:
    base = _timeline(61)
    reference = AttendanceForecaster.forecast(base).result
    assert reference is not None

    altered = [
        MatchSample(
            m.match_id,
            m.kickoff,
            m.spectators * 10 if m.kickoff >= reference.test_start else m.spectators,
            m.home_club_id,
            m.away_club_id,
            m.home,
            m.away,
            0,
            50,
        )
        for m in base
    ]
    changed = AttendanceForecaster.forecast(altered).result

    assert changed is not None
    assert changed.train_size == reference.train_size
    assert changed.train_end == reference.train_end
    assert changed.coefficients[1:] == reference.coefficients[1:]
    assert changed.coefficients[0] == reference.coefficients[0]
    assert changed.mae != reference.mae

    before = {r.match_id: r for r in ForecastFeatureBuilder.build(base)}
    after = {r.match_id: r for r in ForecastFeatureBuilder.build(altered)}
    first_test = min(
        match_id for match_id, row in before.items() if row.kickoff >= reference.test_start
    )
    assert all(before[i].features == after[i].features for i in before if i <= first_test)


def test_forecast_is_independent_of_input_order() -> None:
    base = _timeline(61)

    forward = AttendanceForecaster.forecast(base)
    shuffled = AttendanceForecaster.forecast(list(reversed(base)))

    assert forward == shuffled


def test_science_report_notes_cap_and_small_samples() -> None:
    capped = AttendanceScienceCalculator.build(_timeline(10), known_total=9000, club_id=None)
    tiny = AttendanceScienceCalculator.build([_sample(1, 1, 0)], known_total=1, club_id=None)
    empty = AttendanceScienceCalculator.build([], known_total=0, club_id=None)

    assert capped.truncated and any("capped" in note for note in capped.notes)
    assert CAUSATION_NOTE in capped.notes
    assert tiny.stability is not None and tiny.stability.mean == 0
    assert any("Small sample" in note for note in tiny.notes)
    assert empty.is_empty and empty.distribution is None and empty.stability is None
    assert empty.forecast.result is None


def test_match_sample_rejects_negative_spectators() -> None:
    with pytest.raises(ValueError):
        _sample(1, 1, -1)


def test_opponent_ranking_orders_by_mean_and_compares_to_the_club_mean() -> None:
    opponents = [
        OpponentAttendance(1, "Low", 3, 3, 1000.0, 1500),
        OpponentAttendance(2, "High", 2, 2, 5000.0, 6000),
        OpponentAttendance(3, "Unknown", 2, 0, None, None),
    ]

    section = OpponentCalculator.build_section(7, opponents, 3000.0)

    assert [row.opponent.opponent_name for row in section.rows] == ["High", "Low"]
    assert [row.position for row in section.rows] == [1, 2]
    assert section.rows[0].difference == 2000
    assert section.rows[0].difference_label == "+2 000"
    assert section.rows[1].difference_label == "-2 000"
    assert section.rows[0].coverage_label == "100.0%"
    assert section.rows[0].maximum_label == "6 000"
    assert section.club_mean_label == "3 000"
    assert not section.requires_club and section.note is None
    assert len(OpponentCalculator.build_section(7, opponents, 3000.0, limit=1).rows) == 1


def test_opponent_section_without_data_or_club_explains_itself() -> None:
    empty = OpponentCalculator.build_section(7, [], None)
    required = OpponentSection.club_required()

    assert empty.rows == () and empty.note is not None
    assert required.requires_club and required.note == OPPONENTS_CLUB_REQUIRED_NOTE
    with pytest.raises(ValueError):
        OpponentAttendance(1, "x", 1, 2, None, None)


def test_calendar_builds_ordered_buckets_and_heatmap() -> None:
    cells = [
        CalendarCell(DIMENSION_MONTH, "10", None, 4, 4, 2000.0),
        CalendarCell(DIMENSION_MONTH, "2", None, 2, 1, 4000.0),
        CalendarCell(DIMENSION_MONTH, "13", None, 1, 1, 1.0),
        CalendarCell(DIMENSION_WEEKDAY, "6", None, 3, 3, 3000.0),
        CalendarCell(DIMENSION_WEEKDAY, "0", None, 3, 0, None),
        CalendarCell(DIMENSION_HOUR, "20", None, 3, 3, 3000.0),
        CalendarCell(DIMENSION_HOUR, "9", None, 1, 1, 500.0),
        CalendarCell(DIMENSION_DAY_TYPE, "weekend", None, 3, 3, 3000.0),
        CalendarCell(DIMENSION_DAY_TYPE, "weekday", None, 5, 4, 1500.0),
        CalendarCell(DIMENSION_PHASE, "Group", None, 5, 5, 1000.0),
        CalendarCell(DIMENSION_PHASE, "Final", None, 1, 1, 8000.0),
        CalendarCell(DIMENSION_PHASE, "", None, 2, 0, None),
        CalendarCell(DIMENSION_HEATMAP, "6", "20", 3, 3, 3000.0),
        CalendarCell(DIMENSION_HEATMAP, "0", "9", 1, 0, None),
    ]

    report = CalendarCalculator.build(cells)

    assert [b.label for b in report.months] == ["Feb", "Oct"]
    assert [b.label for b in report.weekdays] == ["Mon", "Sun"]
    assert [b.label for b in report.hours] == ["09:00", "20:00"]
    assert [b.label for b in report.day_types] == ["Weekday (Mon–Fri)", "Weekend (Sat–Sun)"]
    assert [b.label for b in report.phases] == ["Final", "Group", "Unknown phase"]
    assert report.months[0].bar_percent == 100 and report.months[1].bar_percent == 50
    assert report.weekdays[0].mean_label == "—" and report.weekdays[0].bar_percent == 0
    assert report.months[0].played_label == "2" and report.months[0].known_label == "1"
    assert [(c.weekday, c.hour) for c in report.heatmap] == [(0, 9), (6, 20)]
    assert report.has_heatmap and not report.is_empty
    assert CalendarCalculator.build([]).is_empty
    assert not CalendarCalculator.build([]).has_heatmap


def test_calendar_cell_validates_counts() -> None:
    with pytest.raises(ValueError):
        CalendarCell(DIMENSION_MONTH, "1", None, 1, 2, None)


def test_opponent_sql_uses_away_club_for_the_filtered_home_club() -> None:
    filters = AttendanceFilters(club_id=7, season_id=2, exclude_zeros=True)
    where, params = build_where(filters)

    sql, sql_params = opponents_sql(where, params, known_predicate(filters), 100)

    assert where.startswith(PLAYED_SQL)
    assert "m.home_club_id = %s" in sql
    assert "GROUP BY m.away_club_id" in sql
    assert "m.away_club_id IS NOT NULL" in sql
    assert "m.spectators > 0" in sql
    assert "AVG(m.spectators) FILTER" in sql
    assert sql_params == [2, 7, 100]


def test_calendar_sql_uses_kickoff_expression_and_known_filter() -> None:
    filters = AttendanceFilters(gender="men", date_from=date(2024, 1, 1))
    where, params = build_where(filters)

    sql, sql_params = calendar_sql(where, params, known_predicate(filters))

    assert KICKOFF_AT_SQL in sql
    assert PLAYED_SQL in sql
    assert "EXTRACT(ISODOW FROM kickoff_at)" in sql
    assert "EXTRACT(HOUR FROM kickoff_at)" in sql
    assert "EXTRACT(MONTH FROM kickoff_at)" in sql
    assert sql.count("UNION ALL") == 5
    assert "m.spectators >= 0" in sql
    assert sql_params == ["men", date(2024, 1, 1)]
    for dimension in ("month", "weekday", "hour", "day_type", "phase", "heatmap"):
        assert f"'{dimension}' AS dimension" in sql


def test_record_sql_covers_every_extended_record_kind() -> None:
    filters = AttendanceFilters(season_id=2, club_id=7)
    queries = {}
    for spec in RECORD_SPECS:
        where, params = build_where(filters, with_season=spec.with_season)
        queries[spec.name] = record_sql(spec, where, params, known_predicate(filters))

    assert list(queries) == ["seasons", "clubs", "venues", "finals", "rivalries"]
    seasons_sql_text, seasons_params = queries["seasons"]
    assert "DISTINCT ON (s.id)" in seasons_sql_text
    assert seasons_params == [7]
    assert "LIMIT" not in seasons_sql_text
    assert "DISTINCT ON (m.home_club_id)" in queries["clubs"][0]
    assert queries["clubs"][1] == [2, 7, 30]
    assert "DISTINCT ON (m.venue_id)" in queries["venues"][0]
    assert "m.venue_id IS NOT NULL" in queries["venues"][0]
    finals_text, finals_params = queries["finals"]
    assert "DISTINCT ON" not in finals_text
    assert "m.phase ILIKE %s" in finals_text
    assert finals_params == [2, 7, "%final%", 30]
    assert "DISTINCT ON (m.home_club_id, m.away_club_id)" in queries["rivalries"][0]
    assert all(PLAYED_SQL in text and "m.spectators >= 0" in text for text, _ in queries.values())


def test_sample_sql_is_capped_and_orders_by_kickoff() -> None:
    filters = AttendanceFilters(club_id=3, exclude_zeros=True)
    where, params = build_where(filters)

    sql, sql_params = sample_sql(where, params, known_predicate(filters), 8000)

    assert f"ORDER BY {KICKOFF_AT_SQL} DESC NULLS LAST" in sql
    assert "m.spectators > 0" in sql
    assert "LIMIT %s" in sql
    assert sql_params == [3, 8000]


def test_service_builds_stage_two_and_three_sections() -> None:
    reader = MemoryReader()
    filters = AttendanceFilters(club_id=1)

    report = AttendanceAnalyticsService(reader).report(filters)

    assert report.opponents is not None and not report.opponents.requires_club
    assert [row.opponent.opponent_name for row in report.opponents.rows] == ["Barcelona", "Veszprem"]
    assert report.opponents.club_mean == report.summary.mean
    assert report.opponents.rows[0].difference == pytest.approx(9000 - report.summary.mean)
    assert report.calendar is not None and report.calendar.months[0].label == "Mar"
    assert report.extended_records is not None and not report.extended_records.is_empty
    assert report.science is not None and report.science.sample_size == 45
    assert report.science.forecast.result is not None
    assert reader.sample_calls == [(filters, SAMPLE_LIMIT)]


def test_service_skips_opponent_query_without_a_club() -> None:
    reader = MemoryReader()

    report = AttendanceAnalyticsService(reader).report(AttendanceFilters())

    assert reader.opponent_calls == []
    assert report.opponents is not None and report.opponents.requires_club
    assert report.science is not None
    assert report.science.opponent_effect.rows == ()


def test_charts_payload_covers_every_chart_series() -> None:
    report = AttendanceAnalyticsService(MemoryReader()).report(AttendanceFilters(club_id=1))

    payload = attendance_charts_payload(report)

    assert set(payload) == {
        "trend",
        "heatmap",
        "histogram",
        "clubs",
        "cities",
        "cityDetails",
        "months",
        "weekdays",
        "hours",
        "opponents",
        "coverage",
        "weekdayEffect",
    }
    assert [p["season"] for p in payload["trend"]["points"]] == ["2022/2023", "2023/2024"]
    assert payload["coverage"][1] == {
        "season": "2023/2024",
        "known": 2,
        "played": 3,
        "coverage": pytest.approx(66.7, abs=0.05),
    }
    assert len(payload["histogram"]) == 10
    assert set(payload["histogram"][0]) == {"label", "count", "share"}
    assert [c["name"] for c in payload["clubs"]] == ["Barcelona", "Kielce"]
    assert set(payload["clubs"][0]) == {"name", "mean", "known"}
    assert payload["months"][0]["label"] == "Mar"
    assert payload["weekdays"][0] == {"label": "Sat", "mean": 6500.0, "known": 3, "played": 4}
    assert payload["hours"][0]["label"] == "18:00"
    assert [o["name"] for o in payload["opponents"]] == ["Barcelona", "Veszprem"]
    assert set(payload["opponents"][0]) == {"name", "mean", "difference"}
    assert payload["weekdayEffect"] and set(payload["weekdayEffect"][0]) == {"label", "mean", "n"}
    assert len(payload["heatmap"]["weekdays"]) == 7 and payload["heatmap"]["cells"]


def test_city_ranking_sorts_by_total_and_drops_unknown_cities() -> None:
    ranked = CityCalculator.rank_cities(_cities())

    assert [item.city for item in ranked] == ["Barcelona", "Kielce"]
    assert len(CityCalculator.rank_cities(_cities(), limit=1)) == 1
    assert ranked[0].total_label == "18 000"
    assert ranked[0].mean_label == "9 000"
    assert ranked[0].maximum_label == "12 000"
    assert ranked[0].median_label == "9 000" and ranked[0].mode_label == "6 000"
    assert ranked[1].club_count_label == "1" and ranked[1].competition_count_label == "2"


def test_city_key_ignores_case_and_extra_whitespace() -> None:
    assert normalize_city_key("Kielce") == normalize_city_key("KIELCE")
    assert normalize_city_key("  Kielce ") == "kielce"
    assert normalize_city_key("Bad   Salzuflen\t") == normalize_city_key("bad salzuflen")
    assert normalize_city_key("Straße") == normalize_city_key("STRASSE")
    assert normalize_city_key("   ") == ""
    assert CityAttendance("KIELCE ", 1, 1, 5, 5.0, 5.0, 5, 5, 1, 1).key == "kielce"


def test_city_breakdowns_are_merged_under_the_ranked_display_name() -> None:
    report = CityCalculator.build(_bundle())

    assert [(item.city, item.season_code) for item in report.seasons] == [
        ("Barcelona", "2023/2024"),
        ("Kielce", "2022/2023"),
        ("Kielce", "2023/2024"),
    ]
    assert [(item.city, item.competition) for item in report.competitions] == [
        ("Barcelona", "Champions League"),
        ("Kielce", "Champions League"),
        ("Kielce", "EHF Cup"),
    ]
    assert [(item.city, item.venue_name) for item in report.venues] == [
        ("Barcelona", "Palau Blaugrana"),
        ("Kielce", "Hala Legionow"),
    ]
    assert [item.season_code for item in report.seasons_of("Kielce")] == ["2022/2023", "2023/2024"]
    assert report.venues_of("Kielce")[0].venue_id == 11
    assert report.competitions_of("Nowhere") == ()
    assert report.seasons[2].total_label == "7 000" and report.seasons[2].median_label == "3 500"
    assert report.venues[0].mean_label == "9 000" and report.venues[0].maximum_label == "12 000"


def test_city_breakdowns_respect_the_row_limit_and_report_notes() -> None:
    report = CityCalculator.build(_bundle(), breakdown_limit=1)

    assert len(report.seasons) == len(report.competitions) == len(report.venues) == 1
    assert "1 rows" in report.seasons_note
    assert "ranked cities" in report.competitions_note and "Venues located" in report.venues_note
    assert [item.city for item in report.chart_cities] == ["Barcelona", "Kielce"]
    assert "most common spelling" in report.names_note


def test_city_contributions_follow_the_city_ranking_and_skip_unranked_cities() -> None:
    report = CityCalculator.build(_bundle())

    assert [(item.city, item.competition) for item in report.contributions] == [
        ("Barcelona", "Champions League"),
        ("Kielce", "Champions League"),
        ("Kielce", "EHF Cup"),
    ]
    assert report.matches_without_city == 4
    assert report.source_note == CITY_SOURCE_NOTE
    assert not report.is_empty
    limited = CityCalculator.build(_bundle(0), contribution_limit=2)
    assert [item.total for item in limited.contributions] == [18000, 8000]


def test_city_spelling_variants_share_one_ranked_city() -> None:
    bundle = CityBundle(
        cities=(CityAttendance("KIELCE", 1, 1, 100, 100.0, 100.0, 100, 100, 1, 1),),
        contributions=(
            CityContribution("kielce", 1, "Kielce", "Cup", 1, 1, 100, 100.0, 100),
        ),
        seasons=(CitySeason(" kielce", "2023/2024", 2023, 1, 1, 100, 100.0, 100.0, 100),),
    )

    report = CityCalculator.build(bundle)

    assert [item.city for item in report.contributions] == ["KIELCE"]
    assert [item.city for item in report.seasons] == ["KIELCE"]


def test_city_report_explains_missing_cities_and_empty_state() -> None:
    report = CityCalculator.build(_bundle(1234))
    complete = CityReport.empty()

    assert "1 234 played matches have no venue city" in report.missing_city_note
    assert "Every played match" in complete.missing_city_note
    assert complete.is_empty
    assert "clubs have no city" in CITY_SOURCE_NOTE and "where spectators attended" in CITY_SOURCE_NOTE


def test_city_models_validate_counts() -> None:
    with pytest.raises(ValueError):
        CityAttendance("X", 1, 2, 0, None, None, None, None, 0, 0)
    with pytest.raises(ValueError):
        CityContribution("X", None, "—", "Cup", 1, 2, 0, None, None)
    with pytest.raises(ValueError):
        CitySeason("X", "2023/2024", 2023, 1, 2, 0, None, None, None)
    with pytest.raises(ValueError):
        CityCompetition("X", "Cup", 1, 2, 0, None, None, None)
    with pytest.raises(ValueError):
        CityVenue("X", 1, "Hall", 1, 2, 0, None, None)
    with pytest.raises(ValueError):
        CityReport((), (), -1)


def test_city_sql_uses_venue_city_played_filter_and_known_predicate() -> None:
    filters = AttendanceFilters(season_id=2, club_id=7, exclude_zeros=True)
    where, params = build_where(filters)
    known = known_predicate(filters)

    sql, sql_params = cities_sql(where, params, known, 100)
    contributions_sql, contributions_params = city_contributions_sql(where, params, known, 300)
    missing_sql, missing_params = matches_without_city_sql(where, params)

    for text in (sql, contributions_sql, missing_sql):
        assert PLAYED_SQL in text
        assert "m.home_club_id = %s" in text
        assert "LEFT JOIN ehf.venue v ON v.id = m.venue_id" in text
        assert CITY_KEY_SQL in text
    assert "club_edition" not in sql
    assert f"GROUP BY {CITY_KEY_SQL}\n" in sql
    assert "lower(regexp_replace(btrim(v.city)" in CITY_KEY_SQL
    assert "MODE() WITHIN GROUP (ORDER BY regexp_replace(btrim(v.city)" in sql
    assert "COUNT(DISTINCT m.home_club_id)" in sql
    assert "COUNT(DISTINCT COALESCE(NULLIF(btrim(c.name), ''), '—'))" in sql
    assert f"{CITY_KEY_SQL} IS NOT NULL" in sql
    assert "m.spectators > 0" in sql and "LIMIT %s" in sql
    assert "percentile_cont(0.5) WITHIN GROUP (ORDER BY m.spectators)" in sql
    assert "MODE() WITHIN GROUP (ORDER BY m.spectators)" in sql
    assert sql_params == [2, 7, 100]
    assert f"GROUP BY {CITY_KEY_SQL}, m.home_club_id" in contributions_sql
    assert "COALESCE(NULLIF(btrim(c.name), ''), '—')" in contributions_sql
    assert contributions_params == [2, 7, 300]
    assert f"{CITY_KEY_SQL} IS NULL" in missing_sql
    assert "LIMIT" not in missing_sql
    assert missing_params == [2, 7]
    assert "m.spectators >= 0" in cities_sql(*build_where(AttendanceFilters()), known_predicate(AttendanceFilters()), 1)[0]


def test_city_breakdown_sql_is_limited_to_the_ranked_cities() -> None:
    filters = AttendanceFilters(season_id=2, club_id=7)
    where, params = build_where(filters)
    known = known_predicate(filters)

    seasons = city_seasons_sql(where, params, known, 100)
    competitions = city_competitions_sql(where, params, known, 100)
    venues = city_venues_sql(where, params, known, 100)

    for sql, sql_params in (seasons, competitions, venues):
        assert PLAYED_SQL in sql
        assert sql.count("m.home_club_id = %s") == 2
        assert sql.lstrip().startswith("WITH") and "ranked AS (" in sql
        assert f"{CITY_KEY_SQL} IN (SELECT city_key FROM ranked)" in sql
        assert "LEFT JOIN ehf.venue v ON v.id = m.venue_id" in sql
        assert "HAVING COUNT(*) FILTER (WHERE m.spectators >= 0) > 0" in sql
        assert sql_params == [2, 7, 100, 2, 7]
        assert "INSERT" not in sql and "UPDATE" not in sql
    assert f"GROUP BY {CITY_KEY_SQL}, s.id, s.code, s.year_start" in seasons[0]
    assert "ORDER BY city_key, s.year_start" in seasons[0]
    assert f"GROUP BY {CITY_KEY_SQL}, COALESCE(NULLIF(btrim(c.name), ''), '—')" in competitions[0]
    assert f"GROUP BY {CITY_KEY_SQL}, v.id, v.name" in venues[0]
    assert "v.id AS venue_id" in venues[0] and "AS venue_name" in venues[0]


def test_city_row_mappers_build_domain_objects() -> None:
    figures = {
        "played": 4, "known": 3, "total": 12000, "mean": 4000.0, "median": 4000.0,
        "spectator_mode": 3000, "maximum": 6000,
    }
    city = city_from_row({"city": "Kielce", **figures, "club_count": 1, "competition_count": 2})
    contribution = contribution_from_row(
        {
            "city": "Kielce", "club_id": None, "club_name": "—", "competition": "EHF Cup",
            "played": 1, "known": 1, "total": 500, "mean": 500.0, "median": 500.0,
            "spectator_mode": 500, "maximum": 500,
        }
    )
    season = season_from_row({"city": "Kielce", "season_code": "2023/2024", "year_start": 2023, **figures})
    competition = competition_from_row({"city": "Kielce", "competition": "EHF Cup", **figures})
    venue = venue_from_row({"city": "Kielce", "venue_id": 11, "venue_name": "Hala Legionow", **figures})

    assert city == _cities()[0]
    assert contribution.club_id is None and contribution.total == 500 and contribution.mode == 500
    assert season.season_code == "2023/2024" and season.year_start == 2023 and season.median == 4000.0
    assert competition.competition == "EHF Cup" and competition.mode == 3000
    assert venue.venue_id == 11 and venue.venue_name == "Hala Legionow" and venue.mode == 3000


def test_service_builds_city_report_with_limits() -> None:
    reader = MemoryReader()
    filters = AttendanceFilters(gender="women")

    report = AttendanceAnalyticsService(reader).report(filters)

    assert report.cities is not None
    assert [item.city for item in report.cities.cities] == ["Barcelona", "Kielce"]
    assert report.cities.matches_without_city == 4
    assert reader.city_calls == [filters]
    assert reader.city_limits == [100] and reader.contribution_limits == [300]


def test_charts_payload_lists_top_cities_by_total() -> None:
    report = AttendanceAnalyticsService(MemoryReader()).report(AttendanceFilters())

    cities = attendance_charts_payload(report)["cities"]

    assert [item["name"] for item in cities] == ["Barcelona", "Kielce"]
    assert set(cities[0]) == {"name", "total", "mean", "median", "mode", "known"}
    assert cities[0]["total"] == 18000 and cities[0]["median"] == 9000.0 and cities[0]["mode"] == 6000


def test_charts_payload_lists_city_details_for_the_selector() -> None:
    report = AttendanceAnalyticsService(MemoryReader()).report(AttendanceFilters())

    details = attendance_charts_payload(report)["cityDetails"]

    assert [item["name"] for item in details] == ["Barcelona", "Kielce"]
    assert set(details[1]) == {"name", "seasons", "competitions", "venues"}
    assert [row["season"] for row in details[1]["seasons"]] == ["2022/2023", "2023/2024"]
    assert set(details[1]["seasons"][0]) == {"season", "total", "mean", "median", "known", "played"}
    assert [row["name"] for row in details[1]["competitions"]] == ["Champions League", "EHF Cup"]
    assert [row["name"] for row in details[0]["venues"]] == ["Palau Blaugrana"]
    assert set(details[0]["venues"][0]) == {"name", "total", "mean", "known"}


def test_dashboard_renders_cities_tab_panel_and_chart() -> None:
    client = _app(AttendanceAnalyticsService(MemoryReader())).test_client()

    page = client.get("/raporty/frekwencja").get_data(as_text=True)

    assert 'data-tab="cities"' in page and ">Cities<" in page
    assert page.index('data-tab="clubs"') < page.index('data-tab="cities"') < page.index('data-tab="records"')
    assert 'id="att-panel-cities"' in page
    assert 'data-chart="cities"' in page
    assert CITY_SOURCE_NOTE in page
    assert "4 played matches have no venue city" in page
    assert 'data-attendance-search="cities"' in page
    assert ">Barcelona<" in page and "18 000" in page
    assert 'href="/druzyny/2"' in page
    assert "Clubs and competitions behind the city totals" in page
    assert "Elsewhere" not in page
    assert "<th scope=\"col\" class=\"num\">Median</th>" in page and ">Mode<" in page
    assert CITY_NAMES_NOTE in page
    for chart in ("cityTrend", "cityCompetitions", "cityVenues"):
        assert f'data-chart="{chart}" data-city-chart' in page
    assert 'data-city-select' in page and '<option value="1">Kielce</option>' in page
    assert "Seasons in each city" in page and "Competitions in each city" in page
    assert "Venues in each city" in page
    assert 'href="/hale/21"' in page and ">Palau Blaugrana<" in page
    assert "2022/2023" in page and "Closed hall" not in page


def test_dashboard_renders_without_city_chart_when_no_city_has_attendance() -> None:
    class NoCityReader(MemoryReader):
        def fetch_city_bundle(self, filters, city_limit, contribution_limit):
            return CityBundle(matches_without_city=4)

    client = _app(AttendanceAnalyticsService(NoCityReader())).test_client()

    page = client.get("/raporty/frekwencja?tab=cities").get_data(as_text=True)

    assert 'data-chart="cities"' not in page
    assert 'data-chart="cityTrend"' not in page and "data-city-select" not in page
    assert "No matches with a venue city and known attendance" in page
    assert CITY_SOURCE_NOTE in page


def test_charts_payload_skips_opponents_without_a_home_club() -> None:
    report = AttendanceAnalyticsService(MemoryReader()).report(AttendanceFilters())

    assert attendance_charts_payload(report)["opponents"] == []


def test_dashboard_renders_without_opponent_chart_and_keeps_hidden_headings() -> None:
    client = _app(AttendanceAnalyticsService(MemoryReader())).test_client()

    page = client.get("/raporty/frekwencja?tab=science").get_data(as_text=True)

    assert 'data-chart="opponents"' not in page
    assert 'data-chart="histogram"' in page and 'data-chart="weekdayEffect"' in page
    assert ">Data science<" in page and ">Opponents<" in page


def test_dashboard_rejects_bad_filters() -> None:
    client = _app(AttendanceAnalyticsService(MemoryReader())).test_client()

    assert client.get("/raporty/frekwencja?gender=mixed").status_code == 400
    assert client.get("/raporty/frekwencja?season=abc").status_code == 400
    assert (
        client.get("/raporty/frekwencja?date_from=2024-05-01&date_to=2024-01-01").status_code
        == 400
    )
