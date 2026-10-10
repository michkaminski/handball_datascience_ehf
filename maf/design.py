from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from maf.features import FeatureScaler, RawFeatures
from maf.quality import PreparedMatch
from maf.records import Measure

GROUPS: tuple[str, ...] = (
    "host",
    "opponent",
    "season",
    "competition",
    "host_season",
    "opponent_season",
)
GROUP_LABELS: dict[str, str] = {
    "host": "Gospodarz (H)",
    "opponent": "Rywal (R)",
    "season": "Sezon (S)",
    "competition": "Rozgrywki (L)",
    "host_season": "Gospodarz × sezon (HS)",
    "opponent_season": "Rywal × sezon (RS)",
}


class GroupIndex:
    def __init__(self) -> None:
        self._index: dict[Hashable, int] = {}
        self.keys: list[Hashable] = []

    def add(self, key: Hashable) -> int:
        position = self._index.get(key)
        if position is None:
            position = len(self.keys)
            self._index[key] = position
            self.keys.append(key)
        return position

    def get(self, key: Hashable) -> int | None:
        return self._index.get(key)

    def __len__(self) -> int:
        return len(self.keys)


@dataclass(frozen=True)
class ModelData:
    measure: Measure
    match_ids: NDArray[np.int64]
    spectators: NDArray[np.int64]
    capacity: NDArray[np.int64]
    features: NDArray[np.float64]
    groups: dict[str, NDArray[np.int64]]
    indexes: dict[str, GroupIndex]
    season_order: NDArray[np.int64]

    def blocks(self, name: str) -> NDArray[np.int64]:
        index = self.indexes[name]
        if name == "host_season":
            parent = self.indexes["host"]
        elif name == "opponent_season":
            parent = self.indexes["opponent"]
        else:
            return np.zeros(len(index), dtype=np.int64)
        return np.array(
            [_lookup(parent, key[0]) for key in index.keys if isinstance(key, tuple)],
            dtype=np.int64,
        )

    @property
    def size(self) -> int:
        return int(self.spectators.shape[0])

    def group_size(self, name: str) -> int:
        return len(self.indexes[name])

    def subset(self, mask: NDArray[np.bool_]) -> ModelData:
        return ModelData(
            measure=self.measure,
            match_ids=self.match_ids[mask],
            spectators=self.spectators[mask],
            capacity=self.capacity[mask],
            features=self.features[mask],
            groups={name: values[mask] for name, values in self.groups.items()},
            indexes=self.indexes,
            season_order=self.season_order[mask],
        )


class ModelDataBuilder:
    def build(
        self,
        matches: Sequence[PreparedMatch],
        raw_features: dict[int, RawFeatures],
        measure: Measure,
        scaler: FeatureScaler,
    ) -> ModelData:
        rows = [
            item
            for item in matches
            if (item.usable_fill if measure is Measure.FILL else item.usable_count)
        ]
        indexes = {name: GroupIndex() for name in GROUPS}
        groups: dict[str, list[int]] = {name: [] for name in GROUPS}
        for item in sorted(
            rows, key=lambda match: (match.record.season_order, match.record.match_id)
        ):
            record = item.record
            keys: dict[str, Hashable] = {
                "host": record.host_id,
                "opponent": record.opponent_id,
                "season": record.season_key,
                "competition": record.competition_key,
                "host_season": (record.host_id, record.season_key),
                "opponent_season": (record.opponent_id, record.season_key),
            }
            for name in GROUPS:
                indexes[name].add(keys[name])
        ordered = sorted(rows, key=lambda match: (match.record.season_order, match.record.match_id))
        for item in ordered:
            record = item.record
            groups["host"].append(_lookup(indexes["host"], record.host_id))
            groups["opponent"].append(_lookup(indexes["opponent"], record.opponent_id))
            groups["season"].append(_lookup(indexes["season"], record.season_key))
            groups["competition"].append(_lookup(indexes["competition"], record.competition_key))
            groups["host_season"].append(
                _lookup(indexes["host_season"], (record.host_id, record.season_key))
            )
            groups["opponent_season"].append(
                _lookup(indexes["opponent_season"], (record.opponent_id, record.season_key))
            )
        spectators = np.array([item.record.spectators for item in ordered], dtype=np.int64)
        capacity = np.array(
            [item.capacity if item.capacity is not None else 0 for item in ordered],
            dtype=np.int64,
        )
        return ModelData(
            measure=measure,
            match_ids=np.array([item.record.match_id for item in ordered], dtype=np.int64),
            spectators=spectators,
            capacity=capacity,
            features=scaler.transform([raw_features[item.record.match_id] for item in ordered]),
            groups={name: np.array(values, dtype=np.int64) for name, values in groups.items()},
            indexes=indexes,
            season_order=np.array([item.record.season_order for item in ordered], dtype=np.int64),
        )


def _lookup(index: GroupIndex, key: Hashable) -> int:
    position = index.get(key)
    assert position is not None
    return position
