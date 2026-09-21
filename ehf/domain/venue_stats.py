from __future__ import annotations

from collections import Counter, defaultdict

from ehf.domain.counts import (
    MONTHS,
    WEEKDAYS,
    CountSeries,
    HeatCell,
    Heatmap,
    MatchRecord,
    NamedCount,
    completeness,
    heat_level,
    mean,
    median,
)
from ehf.domain.venues import VenueMatchFact, VenuePlayerItem, VenueStats


def _series(counter: Counter[str], order: tuple[str, ...] | None = None) -> CountSeries:
    if order is not None:
        items = tuple(NamedCount(key, key, counter.get(key, 0)) for key in order)
        return CountSeries(items)
    ranked = counter.most_common()
    return CountSeries(tuple(NamedCount(key, key, value) for key, value in ranked if key))


def _histogram(totals: tuple[int, ...]) -> CountSeries:
    edges = (40, 50, 60, 70, 80, 90)
    labels = ("≤40", "41–50", "51–60", "61–70", "71–80", "81–90", "91+")
    buckets = [0] * len(labels)
    for total in totals:
        index = len(edges)
        for edge_index, edge in enumerate(edges):
            if total <= edge:
                index = edge_index
                break
        buckets[index] += 1
    return CountSeries(tuple(NamedCount(label, label, count) for label, count in zip(labels, buckets)))


def _heatmap(facts: tuple[VenueMatchFact, ...]) -> Heatmap:
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


def _records(facts: tuple[VenueMatchFact, ...]) -> tuple[MatchRecord, ...]:
    scored = [fact for fact in facts if fact.score_home is not None and fact.score_away is not None]
    attended = [fact for fact in facts if fact.spectators is not None]
    records: list[MatchRecord] = []
    if scored:
        highest = max(scored, key=lambda fact: fact.score_home + fact.score_away)
        records.append(
            MatchRecord(
                "Highest scoring match",
                highest.match_id,
                f"{highest.home_name} {highest.score_home}:{highest.score_away} {highest.away_name}",
            )
        )
        widest = max(scored, key=lambda fact: abs(fact.score_home - fact.score_away))
        records.append(
            MatchRecord(
                "Biggest winning margin",
                widest.match_id,
                f"{widest.home_name} {widest.score_home}:{widest.score_away} {widest.away_name}",
            )
        )
    if attended:
        crowd = max(attended, key=lambda fact: fact.spectators or 0)
        records.append(
            MatchRecord(
                "Highest attendance",
                crowd.match_id,
                f"{crowd.spectators} — {crowd.home_name} vs {crowd.away_name}",
            )
        )
    return tuple(records)


def build_venue_stats(
    facts: tuple[VenueMatchFact, ...],
    players: tuple[VenuePlayerItem, ...],
    expanded: frozenset[str],
) -> VenueStats:
    seasons = Counter(fact.season_code for fact in facts)
    competitions = Counter(fact.competition_name for fact in facts)
    months = Counter()
    weekdays = Counter()
    teams: Counter[str] = Counter()
    profile = Counter()
    totals: list[int] = []
    crowds: list[int] = []
    season_order = tuple(
        code for code, _ in sorted({(fact.season_code, fact.year_start) for fact in facts}, key=lambda item: item[1])
    )
    for fact in facts:
        if fact.home_name:
            teams[fact.home_name] += 1
        if fact.away_name:
            teams[fact.away_name] += 1
        if fact.kickoff_at is not None:
            months[MONTHS[fact.kickoff_at.month - 1]] += 1
            weekdays[WEEKDAYS[fact.kickoff_at.weekday()]] += 1
        if fact.score_home is not None and fact.score_away is not None:
            totals.append(fact.score_home + fact.score_away)
            if fact.score_home > fact.score_away:
                profile["Home wins"] += 1
            elif fact.score_away > fact.score_home:
                profile["Away wins"] += 1
            else:
                profile["Draws"] += 1
        if fact.result_type == "extra_time":
            profile["Extra time"] += 1
        elif fact.result_type == "penalties":
            profile["Penalties"] += 1
        if fact.spectators is not None:
            crowds.append(fact.spectators)
    goal_totals = tuple(totals)
    player_matches = CountSeries(
        tuple(NamedCount(str(item.player_id), item.display_name, item.matches) for item in sorted(players, key=lambda row: (-row.matches, row.display_name)))
    )
    scorers = CountSeries(
        tuple(
            NamedCount(str(item.player_id), item.display_name, int(item.goals or 0))
            for item in sorted(players, key=lambda row: (-(row.goals or 0), row.display_name))
            if item.goals
        )
    )
    return VenueStats(
        seasons=_series(seasons, season_order or None),
        competitions=_series(competitions),
        result_profile=CountSeries(
            tuple(
                NamedCount(label, label, profile.get(label, 0))
                for label in ("Home wins", "Away wins", "Draws", "Extra time", "Penalties")
            )
        ),
        goal_totals=goal_totals,
        mean_goals=mean(goal_totals),
        median_goals=median(goal_totals),
        histogram=_histogram(goal_totals),
        months=_series(months, MONTHS),
        weekdays=_series(weekdays, WEEKDAYS),
        heatmap=_heatmap(facts),
        attendance_known=len(crowds),
        attendance_total=len(facts),
        attendance_completeness=completeness(len(crowds), len(facts)),
        mean_attendance=mean(tuple(crowds)),
        records=_records(facts),
        teams=_series(teams),
        players=player_matches,
        scorers=scorers,
        expanded=expanded,
    )
