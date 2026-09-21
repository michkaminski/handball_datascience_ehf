from __future__ import annotations

from collections import Counter, defaultdict

from ehf.domain.counts import (
    MONTHS,
    WEEKDAYS,
    CountSeries,
    HeatCell,
    Heatmap,
    NamedCount,
    heat_level,
)
from ehf.domain.referees import RefereeMatchFact, RefereeStats


def _series(counter: Counter[str], order: tuple[str, ...] | None = None) -> CountSeries:
    if order is not None:
        return CountSeries(tuple(NamedCount(key, key, counter.get(key, 0)) for key in order))
    return CountSeries(tuple(NamedCount(key, key, value) for key, value in counter.most_common() if key))


def _heatmap(facts: tuple[RefereeMatchFact, ...]) -> Heatmap:
    counts: dict[tuple[str, int], int] = defaultdict(int)
    seasons: dict[str, int] = {}
    for fact in facts:
        if fact.kickoff_at is None:
            continue
        counts[(fact.season_code, fact.kickoff_at.month)] += 1
        seasons[fact.season_code] = fact.year_start
    ordered = tuple(sorted(seasons, key=lambda code: seasons[code], reverse=True))
    maximum = max(counts.values(), default=0)
    cells = tuple(
        HeatCell(season, month, counts.get((season, month), 0), heat_level(counts.get((season, month), 0), maximum))
        for season in ordered
        for month in range(1, 13)
    )
    return Heatmap(ordered, cells)


def build_referee_stats(facts: tuple[RefereeMatchFact, ...], expanded: frozenset[str]) -> RefereeStats:
    seasons = Counter(fact.season_code for fact in facts)
    competitions = Counter(fact.competition_name for fact in facts)
    season_competitions = Counter(f"{fact.season_code} · {fact.competition_name}" for fact in facts)
    teams: Counter[str] = Counter()
    home_teams: Counter[str] = Counter()
    away_teams: Counter[str] = Counter()
    partner_pairs: dict[tuple[str, str], int] = {}
    months: Counter[str] = Counter()
    weekdays: Counter[str] = Counter()
    season_order = tuple(
        code for code, _ in sorted({(fact.season_code, fact.year_start) for fact in facts}, key=lambda item: item[1])
    )
    for fact in facts:
        if fact.home_name:
            teams[fact.home_name] += 1
            home_teams[fact.home_name] += 1
        if fact.away_name:
            teams[fact.away_name] += 1
            away_teams[fact.away_name] += 1
        if fact.partner_name:
            pair = (str(fact.partner_id or ""), fact.partner_name)
            partner_pairs[pair] = partner_pairs.get(pair, 0) + 1
        if fact.kickoff_at is not None:
            months[MONTHS[fact.kickoff_at.month - 1]] += 1
            weekdays[WEEKDAYS[fact.kickoff_at.weekday()]] += 1
    return RefereeStats(
        seasons=_series(seasons, season_order or None),
        competitions=_series(competitions),
        season_competitions=_series(season_competitions),
        teams=_series(teams),
        home_teams=_series(home_teams),
        away_teams=_series(away_teams),
        partners=CountSeries(
            tuple(
                NamedCount(key, label, value)
                for (key, label), value in sorted(partner_pairs.items(), key=lambda item: (-item[1], item[0][1]))
            )
        ),
        months=_series(months, MONTHS),
        weekdays=_series(weekdays, WEEKDAYS),
        heatmap=_heatmap(facts),
        distinct_teams=len(teams),
        distinct_competitions=len(competitions),
        expanded=expanded,
    )
