from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DistributionEntry:
    key: str
    title: str
    description: str
    category: str
    endpoint: str


DISTRIBUTION_CATALOG: tuple[DistributionEntry, ...] = (
    DistributionEntry(
        "goal_distribution",
        "Goals per match",
        "How often each match goal total occurs, and how often the home and away teams "
        "score each number of goals.",
        "Results",
        "panel.rozklad_bramek",
    ),
)
