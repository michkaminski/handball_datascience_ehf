from __future__ import annotations

from datetime import datetime

from ehf.domain.matches import MatchListItem, format_stage
from ehf.domain.news import (
    NewsMatchRecord,
    NewsPage,
    NewsPerformanceWithCompetition,
    NewsResultMatch,
    NewsSection,
    UpcomingSection,
)
from ehf.interface.view_models.news import (
    AktualnosciViewModel,
    BramkarzAktualnosciViewModel,
    CiekawostkaViewModel,
    MeczAktualnosciViewModel,
    NadchodzacaSekcjaViewModel,
    SekcjaAktualnosciViewModel,
    StrzelecAktualnosciViewModel,
)

MISSING = "—"


class NewsPresenter:
    def prepare(self, page: NewsPage) -> AktualnosciViewModel:
        return AktualnosciViewModel(
            sezon=page.season.code if page.season else None,
            id_sezon=page.season.id if page.season else None,
            stan_danych=self._date(page.last_kickoff),
            liczba_rozegranych=page.played_count,
            suma_bramek=page.total_goals,
            sekcje=[self._sekcja(section) for section in page.sections],
            ciekawostki=self._ciekawostki(page),
            nadchodzace_sekcje=[
                self._nadchodzaca_sekcja(section) for section in page.upcoming_sections
            ],
        )

    def _sekcja(self, section: NewsSection) -> SekcjaAktualnosciViewModel:
        return SekcjaAktualnosciViewModel(
            klucz=section.competition.key.replace("-", "_"),
            etykieta=section.competition.name,
            rozgrywki=section.competition.name,
            id_rozgrywek=section.competition.id,
            liczba_rozegranych=section.played_count,
            srednia_bramek=self._number(section.average_goals),
            mecze=[self._mecz(match) for match in section.recent_matches],
            strzelcy=[
                self._strzelec(position, scorer)
                for position, scorer in enumerate(section.scorers, 1)
            ],
            bramkarze=[
                self._bramkarz(position, keeper)
                for position, keeper in enumerate(section.goalkeepers, 1)
            ],
        )

    def _nadchodzaca_sekcja(self, section: UpcomingSection) -> NadchodzacaSekcjaViewModel:
        return NadchodzacaSekcjaViewModel(
            klucz=section.competition.key.replace("-", "_"),
            rozgrywki=section.competition.name,
            id_rozgrywek=section.competition.id,
            mecze=[self._nadchodzacy_mecz(match) for match in section.matches],
        )

    def _mecz(self, match: NewsResultMatch) -> MeczAktualnosciViewModel:
        winner = None
        if match.score_home is not None and match.score_away is not None:
            if match.score_home > match.score_away:
                winner = "home"
            elif match.score_away > match.score_home:
                winner = "away"
        return MeczAktualnosciViewModel(
            id=match.id,
            day=self._day(match.kickoff_at),
            time=self._time(match.kickoff_at),
            home=self._text(match.home_name),
            away=self._text(match.away_name),
            score=match.score_text,
            winner=winner,
        )

    def _nadchodzacy_mecz(self, match: MatchListItem) -> MeczAktualnosciViewModel:
        return MeczAktualnosciViewModel(
            id=match.id,
            day=self._day(match.kickoff_at),
            time=self._time(match.kickoff_at),
            home=self._text(match.home_name),
            away=self._text(match.away_name),
            score="vs",
            winner=None,
            stage=format_stage(match.phase, match.group_code),
        )

    def _strzelec(self, position: int, scorer) -> StrzelecAktualnosciViewModel:
        return StrzelecAktualnosciViewModel(
            pozycja=position,
            id_zawodnik=scorer.player_id,
            zawodnik=self._text(scorer.player_name),
            druzyna=self._text(scorer.team),
            mecze=scorer.matches,
            bramki=scorer.goals,
            srednia=self._number(scorer.goals / scorer.matches if scorer.matches else None),
        )

    def _bramkarz(self, position: int, keeper) -> BramkarzAktualnosciViewModel:
        return BramkarzAktualnosciViewModel(
            pozycja=position,
            id_zawodnik=keeper.player_id,
            zawodnik=self._text(keeper.player_name),
            druzyna=self._text(keeper.team),
            mecze=keeper.matches,
            rzuty=keeper.shots_faced,
            obrony=keeper.saves,
            skutecznosc=self._percent(keeper.average_save_percentage),
        )

    def _ciekawostki(self, page: NewsPage) -> list[CiekawostkaViewModel]:
        facts: list[CiekawostkaViewModel] = []
        if page.played_count:
            facts.append(
                CiekawostkaViewModel(
                    tytul="Sezon w liczbach",
                    wartosc=self._goals(page.total_goals),
                    opis=(
                        f"rozegrane mecze: {page.played_count}, średnio "
                        f"{self._number(page.total_goals / page.played_count)} na mecz"
                    ),
                )
            )
        if page.most_goals_match:
            facts.append(self._rekord("Najwięcej bramek w meczu", page.most_goals_match))
        if page.biggest_win:
            facts.append(
                self._rekord(
                    "Najwyższe zwycięstwo",
                    page.biggest_win,
                    wartosc=f"różnica {self._goals(page.biggest_win.value)}",
                )
            )
        if page.best_performances:
            facts.append(self._wystep(page.best_performances[0]))
        if page.highest_scoring_section:
            section = page.highest_scoring_section
            facts.append(
                CiekawostkaViewModel(
                    tytul="Najbardziej bramkostrzelne rozgrywki",
                    wartosc=f"{self._number(section.average_goals)} bramki na mecz",
                    opis=(
                        f"{section.competition.name} · rozegrane mecze: {section.played_count}"
                    ),
                )
            )
        return facts

    def _rekord(
        self,
        tytul: str,
        record: NewsMatchRecord,
        *,
        wartosc: str | None = None,
    ) -> CiekawostkaViewModel:
        match = self._mecz(record.match)
        return CiekawostkaViewModel(
            tytul=tytul,
            wartosc=wartosc or self._goals(record.value),
            opis=(
                f"{match.home} {match.score} {match.away} · {record.competition.name}, "
                f"{self._date(record.match.kickoff_at)}"
            ),
            id_mecz=record.match.id,
        )

    def _wystep(self, item: NewsPerformanceWithCompetition) -> CiekawostkaViewModel:
        performance = item.performance
        team = f" ({performance.team.strip()})" if performance.team and performance.team.strip() else ""
        return CiekawostkaViewModel(
            tytul="Najlepszy występ indywidualny",
            wartosc=f"{self._goals(performance.goals)} w meczu",
            opis=(
                f"{self._text(performance.player_name)}{team} · {item.competition.name}, "
                f"{self._date(performance.kickoff_at)}"
            ),
            id_mecz=performance.match_id,
            id_zawodnik=performance.player_id,
        )

    @staticmethod
    def _text(value: str | None) -> str:
        return " ".join(value.split()) if value and value.strip() else MISSING

    @staticmethod
    def _day(value: datetime | None) -> str:
        return value.strftime("%d.%m") if value else MISSING

    @staticmethod
    def _time(value: datetime | None) -> str:
        if not value or not (value.hour or value.minute):
            return ""
        return value.strftime("%H:%M")

    @staticmethod
    def _date(value: datetime | None) -> str:
        return value.strftime("%d.%m.%Y") if value else MISSING

    @staticmethod
    def _number(value: float | None) -> str:
        return f"{value:.1f}".replace(".", ",") if value is not None else MISSING

    @staticmethod
    def _percent(value: float | None) -> str:
        return f"{value:.1f} %".replace(".", ",") if value is not None else MISSING

    @staticmethod
    def _goals(count: int) -> str:
        if count == 1:
            return "1 bramka"
        if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
            return f"{count} bramki"
        return f"{count} bramek"
