from __future__ import annotations

import math
import re
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import groupby

import numpy as np
from numpy.typing import NDArray

from maf.quality import PreparedMatch
from maf.records import MatchRecord

FEATURE_NAMES: tuple[str, ...] = (
    "weekend",
    "hour",
    "host_form",
    "opponent_form",
    "host_position",
    "opponent_position",
    "playoff",
    "final",
)
FEATURE_LABELS: dict[str, str] = {
    "weekend": "Mecz w weekend (sobota–niedziela)",
    "hour": "Godzina rozpoczęcia (standaryzowana)",
    "host_form": "Forma gospodarza — średnia punktów z 5 ostatnich meczów",
    "opponent_form": "Forma rywala — średnia punktów z 5 ostatnich meczów",
    "host_position": "Pozycja gospodarza w tabeli przed meczem (0 = lider, 1 = ostatni)",
    "opponent_position": "Pozycja rywala w tabeli przed meczem (0 = lider, 1 = ostatni)",
    "playoff": "Faza pucharowa / play-off",
    "final": "Finał lub mecz o medal",
}
STANDARDIZED: frozenset[str] = frozenset(
    {"hour", "host_form", "opponent_form", "host_position", "opponent_position"}
)
FORM_WINDOW = 5

_SEMI = re.compile(r"semi|p[oó][lł]fina|1/2", re.IGNORECASE)
_FINAL = re.compile(r"fina[lł]|medal|o\s*3\.?\s*miejsce|bronze|super\s*cup", re.IGNORECASE)
_PLAYOFF = re.compile(
    r"play|quarter|[cć]wier[cć]|last\s*16|1/8|1/4|bara[zż]|knock|pucharow|round of|"
    r"eliminac|qualification|kwalifik",
    re.IGNORECASE,
)


class PhaseClassifier:
    def classify(self, phase: str | None) -> str:
        if not phase:
            return "regular"
        if _SEMI.search(phase) or _PLAYOFF.search(phase):
            return "playoff"
        if _FINAL.search(phase):
            return "final"
        return "regular"


@dataclass(frozen=True)
class RawFeatures:
    weekend: float | None
    hour: float | None
    host_form: float | None
    opponent_form: float | None
    host_position: float | None
    opponent_position: float | None
    phase_class: str


@dataclass(frozen=True)
class FeatureScaler:
    names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def transform(self, raw: Sequence[RawFeatures]) -> NDArray[np.float64]:
        matrix = np.zeros((len(raw), len(self.names)), dtype=np.float64)
        for row, item in enumerate(raw):
            matrix[row] = self.transform_one(item)
        return matrix

    def transform_one(self, item: RawFeatures) -> NDArray[np.float64]:
        values = _raw_vector(item)
        result = np.zeros(len(self.names), dtype=np.float64)
        for column, name in enumerate(self.names):
            value = values[name]
            mean = self.means[column]
            if value is None or math.isnan(value):
                value = mean
            result[column] = (value - mean) / self.scales[column] if name in STANDARDIZED else value
        return result

    def as_dict(self) -> dict[str, object]:
        return {"names": list(self.names), "means": list(self.means), "scales": list(self.scales)}

    @classmethod
    def fit(cls, raw: Sequence[RawFeatures]) -> FeatureScaler:
        means: list[float] = []
        scales: list[float] = []
        for name in FEATURE_NAMES:
            values = [v for v in (_raw_vector(item)[name] for item in raw) if v is not None]
            mean = float(np.mean(values)) if values else 0.0
            scale = float(np.std(values)) if len(values) > 1 else 1.0
            means.append(mean)
            scales.append(scale if scale > 1e-9 else 1.0)
        return cls(FEATURE_NAMES, tuple(means), tuple(scales))

    @classmethod
    def from_dict(cls, data: dict[str, list[float] | list[str]]) -> FeatureScaler:
        return cls(
            tuple(str(name) for name in data["names"]),
            tuple(float(value) for value in data["means"]),
            tuple(float(value) for value in data["scales"]),
        )


def _raw_vector(item: RawFeatures) -> dict[str, float | None]:
    return {
        "weekend": item.weekend,
        "hour": item.hour,
        "host_form": item.host_form,
        "opponent_form": item.opponent_form,
        "host_position": item.host_position,
        "opponent_position": item.opponent_position,
        "playoff": 1.0 if item.phase_class == "playoff" else 0.0,
        "final": 1.0 if item.phase_class == "final" else 0.0,
    }


@dataclass
class _Standing:
    points: float = 0.0
    played: int = 0
    goal_difference: int = 0


@dataclass
class TeamState:
    form: float | None
    position: float | None
    last_kickoff: datetime | None


@dataclass
class FeatureBuilder:
    phases: PhaseClassifier = field(default_factory=PhaseClassifier)

    def build(
        self, matches: Sequence[PreparedMatch]
    ) -> tuple[dict[int, RawFeatures], dict[int, TeamState]]:
        ordered = sorted(matches, key=_chronological_key)
        recent: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=FORM_WINDOW))
        tables: dict[tuple[str, str], dict[int, _Standing]] = defaultdict(dict)
        features: dict[int, RawFeatures] = {}
        last_seen: dict[int, datetime | None] = {}
        last_table: dict[int, tuple[str, str]] = {}
        for _, group in groupby(ordered, key=_time_bucket):
            batch = [item.record for item in group]
            for record in batch:
                table = tables[(record.competition_key, record.season_key)]
                features[record.match_id] = RawFeatures(
                    weekend=_weekend(record.kickoff),
                    hour=_hour(record.kickoff),
                    host_form=_form(recent.get(record.host_id)),
                    opponent_form=_form(recent.get(record.opponent_id)),
                    host_position=_position(table, record.host_id),
                    opponent_position=_position(table, record.opponent_id),
                    phase_class=self.phases.classify(record.phase),
                )
            for record in batch:
                outcome = _outcome(record)
                last_seen[record.host_id] = record.kickoff
                last_seen[record.opponent_id] = record.kickoff
                last_table[record.host_id] = (record.competition_key, record.season_key)
                last_table[record.opponent_id] = (record.competition_key, record.season_key)
                if outcome is None:
                    continue
                recent[record.host_id].append(outcome)
                recent[record.opponent_id].append(1.0 - outcome)
                table = tables[(record.competition_key, record.season_key)]
                _update_table(table, record, outcome)
        states = {
            team: TeamState(
                form=_form(recent.get(team)),
                position=_position(tables[last_table[team]], team) if team in last_table else None,
                last_kickoff=kickoff,
            )
            for team, kickoff in last_seen.items()
        }
        return features, states


EPOCH = datetime(1900, 1, 1)


def seconds(moment: datetime) -> float:
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return (moment - EPOCH).total_seconds()


def _chronological_key(item: PreparedMatch) -> tuple[int, float, int]:
    record = item.record
    timestamp = seconds(record.kickoff) if record.kickoff is not None else math.inf
    return (record.season_order, timestamp, record.match_id)


def _time_bucket(item: PreparedMatch) -> tuple[int, float]:
    record = item.record
    if record.kickoff is None:
        return (record.season_order, float(record.match_id))
    return (record.season_order, seconds(record.kickoff))


def _weekend(kickoff: datetime | None) -> float | None:
    if kickoff is None:
        return None
    return 1.0 if kickoff.weekday() >= 5 else 0.0


def _hour(kickoff: datetime | None) -> float | None:
    if kickoff is None or (kickoff.hour == 0 and kickoff.minute == 0):
        return None
    return kickoff.hour + kickoff.minute / 60.0


def _form(results: deque[float] | None) -> float | None:
    if not results:
        return None
    return float(sum(results) / len(results))


def _outcome(record: MatchRecord) -> float | None:
    if record.host_goals is None or record.opponent_goals is None:
        return None
    if record.host_goals > record.opponent_goals:
        return 1.0
    if record.host_goals < record.opponent_goals:
        return 0.0
    return 0.5


def _position(table: dict[int, _Standing], team: int) -> float | None:
    if team not in table or len(table) < 2:
        return None
    ranking = sorted(
        table.items(),
        key=lambda item: (-item[1].points, -item[1].goal_difference, item[0]),
    )
    rank = next(index for index, (club, _) in enumerate(ranking) if club == team)
    return rank / (len(ranking) - 1)


def _update_table(table: dict[int, _Standing], record: MatchRecord, outcome: float) -> None:
    assert record.host_goals is not None and record.opponent_goals is not None
    host = table.setdefault(record.host_id, _Standing())
    opponent = table.setdefault(record.opponent_id, _Standing())
    host.points += 2.0 * outcome
    opponent.points += 2.0 * (1.0 - outcome)
    host.played += 1
    opponent.played += 1
    difference = record.host_goals - record.opponent_goals
    host.goal_difference += difference
    opponent.goal_difference -= difference
