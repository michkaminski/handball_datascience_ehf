from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from maf.records import MatchRecord

TRUE_VISITOR_EFFECTS = (0.6, 0.3, 0.0, 0.0, -0.2, -0.4)


def synthetic_matches(
    *,
    seasons: int = 4,
    clubs: int = 6,
    seed: int = 7,
    with_capacity: bool = True,
) -> list[MatchRecord]:
    rng = np.random.default_rng(seed)
    home_effects = np.linspace(0.5, -0.5, clubs)
    visitor_effects = np.array(TRUE_VISITOR_EFFECTS[:clubs])
    capacities = [800 + 200 * indeks for indeks in range(clubs)]
    records: list[MatchRecord] = []
    match_id = 1
    for season in range(seasons):
        start = datetime(2020 + season, 9, 5, 18, 0)
        round_no = 0
        for home in range(clubs):
            for visitor in range(clubs):
                if home == visitor:
                    continue
                kickoff = start + timedelta(days=7 * round_no + (home % 2))
                round_no += 1
                eta = -0.4 + home_effects[home] + visitor_effects[visitor]
                mu = 1.0 / (1.0 + np.exp(-eta))
                p = rng.beta(mu * 20.0, (1.0 - mu) * 20.0)
                spectators = int(rng.binomial(capacities[home], p))
                records.append(
                    MatchRecord(
                        match_id=match_id,
                        kickoff=kickoff,
                        season_key=f"{2020 + season}/{2021 + season}",
                        season_order=2020 + season,
                        competition_key="Test League",
                        competition_name="Test League",
                        host_id=100 + home,
                        host_name=f"Club {home}",
                        opponent_id=100 + visitor,
                        opponent_name=f"Club {visitor}",
                        venue_id=500 + home,
                        venue_name=f"Venue {home}",
                        spectators=spectators,
                        capacity=capacities[home] if with_capacity else None,
                        phase="Group Phase",
                        host_goals=int(rng.integers(20, 35)),
                        opponent_goals=int(rng.integers(20, 35)),
                    )
                )
                match_id += 1
    return records
