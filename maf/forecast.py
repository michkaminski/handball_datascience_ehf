from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property

import numpy as np
from numpy.typing import NDArray
from scipy.special import expit

from maf.artifacts import ModelArtifact
from maf.design import GROUPS
from maf.features import FeatureScaler, RawFeatures
from maf.posterior import summarize

FloatArray = NDArray[np.float64]
JsonDict = dict[str, object]

REPLICATES_PER_DRAW = 5
FILL_THRESHOLDS = (0.75, 0.9, 0.95, 1.0)
PREDICTIVE_LEVELS = (0.5, 0.8, 0.95)
PHASES = ("regular", "playoff", "final")


@dataclass(frozen=True)
class ForecastScenario:
    host_id: int
    opponent_id: int
    competition_key: str | None
    season_key: str | None
    capacity: int | None
    weekday: int
    hour: float | None
    phase: str
    threshold: int | None = None


class ArtifactView:
    def __init__(self, artifact: ModelArtifact) -> None:
        self.artifact = artifact
        self.summary = artifact.summary
        model = self.summary["model"]
        assert isinstance(model, dict)
        self.model = model
        self.measure = str(model["measure"])

    @cached_property
    def positions(self) -> dict[str, dict[object, int]]:
        index = self.summary["index"]
        assert isinstance(index, dict)
        result: dict[str, dict[object, int]] = {}
        for name in GROUPS:
            keys = index[name]
            assert isinstance(keys, list)
            result[name] = {
                (tuple(key) if isinstance(key, list) else key): position
                for position, key in enumerate(keys)
            }
        return result

    @cached_property
    def modes(self) -> dict[str, str]:
        groups = self.model["groups"]
        assert isinstance(groups, list)
        return {str(item["name"]): str(item["mode"]) for item in groups}

    def effect(self, name: str) -> FloatArray:
        return np.asarray(self.artifact.draws[f"effect_{name}"], dtype=np.float64)

    def group_column(self, name: str) -> int:
        return GROUPS.index(name)

    def new_level(self, name: str, rng: np.random.Generator) -> FloatArray:
        if self.modes.get(name) == "fixed":
            spread = self.effect(name).std(axis=1)
        else:
            spread = np.asarray(self.artifact.draws["sigma"], dtype=np.float64)[
                :, self.group_column(name)
            ]
        return rng.normal(0.0, 1.0, size=spread.shape) * spread

    def level(self, name: str, key: object, rng: np.random.Generator) -> tuple[FloatArray, bool]:
        position = self.positions[name].get(key)
        if position is None:
            return self.new_level(name, rng), False
        return self.effect(name)[:, position], True


class AttendanceSimulator:
    def __init__(self, artifact: ModelArtifact, seed: int = 20261010) -> None:
        self._view = ArtifactView(artifact)
        self._seed = seed

    def _features(self, scenario: ForecastScenario) -> FloatArray:
        teams = self._view.summary["teams"]
        assert isinstance(teams, dict)
        host = teams.get(str(scenario.host_id), {})
        opponent = teams.get(str(scenario.opponent_id), {})
        raw = RawFeatures(
            weekend=1.0 if scenario.weekday >= 5 else 0.0,
            hour=scenario.hour,
            host_form=host.get("form"),
            opponent_form=opponent.get("form"),
            host_position=host.get("position"),
            opponent_position=opponent.get("position"),
            phase_class=scenario.phase if scenario.phase in PHASES else "regular",
        )
        features = self._view.model["features"]
        assert isinstance(features, dict)
        return FeatureScaler.from_dict(features).transform_one(raw)

    def simulate(self, scenario: ForecastScenario) -> JsonDict:
        view = self._view
        if scenario.host_id == scenario.opponent_id:
            raise ValueError("gospodarz i rywal muszą być różnymi klubami")
        if view.measure == "fill" and (scenario.capacity is None or scenario.capacity <= 0):
            raise ValueError("model wypełnienia wymaga pojemności hali")
        rng = np.random.default_rng(self._seed)
        draws = view.artifact.draws
        alpha = np.asarray(draws["alpha"], dtype=np.float64)
        beta = np.asarray(draws["beta"], dtype=np.float64)
        x = self._features(scenario)
        eta = alpha + beta @ x
        notes: list[str] = []
        season_key = scenario.season_key
        components = {
            "host": scenario.host_id,
            "opponent": scenario.opponent_id,
            "season": season_key,
            "competition": scenario.competition_key,
            "host_season": (scenario.host_id, season_key),
            "opponent_season": (scenario.opponent_id, season_key),
        }
        contributions: JsonDict = {}
        for name, key in components.items():
            values, known = view.level(name, key, rng)
            eta = eta + values
            contributions[name] = {"median": float(np.median(values)), "known": known}
            if not known:
                notes.append(f"{name}: poziom spoza danych — losowany z rozkładu populacji")
        dispersion = np.asarray(draws["dispersion"], dtype=np.float64)
        if view.measure == "fill" and capacity_value(scenario) > 0:
            covariate = (
                math.log(capacity_value(scenario)) - float(view.model["capacity_log_mean"])
            ) / float(view.model["capacity_log_sd"])
            dispersion = dispersion * np.exp(
                np.asarray(draws["dispersion_slope"], dtype=np.float64) * covariate
            )
        size = eta.size * REPLICATES_PER_DRAW
        eta_rep = np.repeat(eta, REPLICATES_PER_DRAW)
        dispersion_rep = np.repeat(dispersion, REPLICATES_PER_DRAW)
        capacity = scenario.capacity
        if view.measure == "fill":
            assert capacity is not None
            mu = expit(eta)
            mean_parameter = capacity * mu
            probability = rng.beta(
                np.clip(expit(eta_rep) * dispersion_rep, 1e-9, None),
                np.clip((1.0 - expit(eta_rep)) * dispersion_rep, 1e-9, None),
            )
            samples = rng.binomial(capacity, probability, size=size).astype(np.float64)
        else:
            mean_parameter = np.exp(np.clip(eta, -30.0, 30.0))
            rate = rng.gamma(dispersion_rep, np.exp(np.clip(eta_rep, -30.0, 30.0)) / dispersion_rep)
            samples = rng.poisson(rate).astype(np.float64)
            notes.append(
                "model liczby widzów nie zna limitu miejsc — "
                "prawdopodobieństwa kompletu są przybliżeniem"
            )
        intervals = {
            f"{int(level * 100)}": [
                float(np.quantile(samples, (1.0 - level) / 2.0)),
                float(np.quantile(samples, 1.0 - (1.0 - level) / 2.0)),
            ]
            for level in PREDICTIVE_LEVELS
        }
        result: JsonDict = {
            "measure": view.measure,
            "draws": int(eta.size),
            "samples": int(size),
            "expected": float(np.mean(samples)),
            "median": float(np.median(samples)),
            "mean_parameter": summarize(mean_parameter),
            "intervals": intervals,
            "contributions": contributions,
            "features": [float(value) for value in x],
            "notes": notes,
            "histogram": self._histogram(samples, capacity),
        }
        if capacity:
            fill = samples / capacity
            result["capacity"] = capacity
            result["fill_expected"] = float(np.mean(np.minimum(fill, 1.0)))
            result["fill_probabilities"] = {
                f"{int(level * 100)}": float(np.mean(fill >= level - 1e-12))
                for level in FILL_THRESHOLDS
            }
        if scenario.threshold is not None:
            result["threshold"] = scenario.threshold
            result["p_threshold"] = float(np.mean(samples >= scenario.threshold))
        return result

    def _histogram(self, samples: FloatArray, capacity: int | None) -> JsonDict:
        high = float(np.quantile(samples, 0.999))
        if capacity:
            high = min(max(high, 1.0), float(capacity))
        bins = 40
        counts, edges = np.histogram(
            np.clip(samples, 0.0, high), bins=bins, range=(0.0, max(high, 1.0))
        )
        total = float(samples.size)
        return {
            "edges": [float(item) for item in edges],
            "probabilities": [float(item) / total for item in counts],
        }


class HostOpponentAnalysis:
    def __init__(self, artifact: ModelArtifact) -> None:
        self._view = ArtifactView(artifact)

    def analyze(self, host_id: int, limit: int = 15) -> JsonDict:
        view = self._view
        host_position = view.positions["host"].get(host_id)
        if host_position is None:
            raise KeyError(f"klub {host_id} nie występuje w modelu jako gospodarz")
        draws = view.artifact.draws
        baseline = np.asarray(draws["host_baseline"], dtype=np.float64)[:, host_position]
        effects = view.effect("opponent")
        hosts = view.summary["hosts"]
        assert isinstance(hosts, list)
        meta = hosts[host_position]
        assert isinstance(meta, dict)
        capacity = meta.get("capacity")
        if view.measure == "fill":
            reference = expit(baseline)
            expected = expit(baseline[:, None] + effects)
            ratio = expected / reference[:, None]
            scale = float(capacity) if capacity else 0.0
            extra = (expected - reference[:, None]) * scale
        else:
            reference = np.exp(baseline)
            ratio = np.exp(effects)
            extra = reference[:, None] * (ratio - 1.0)
        visited: dict[int, int] = {}
        for row in view.artifact.matches:
            if int(str(row["host_id"])) == host_id:
                opponent = int(str(row["opponent_id"]))
                visited[opponent] = visited.get(opponent, 0) + 1
        clubs = view.summary["clubs"]
        assert isinstance(clubs, list)
        names = {int(club["id"]): str(club["name"]) for club in clubs}
        keys = list(view.positions["opponent"].keys())
        rows = []
        for position, club in enumerate(keys):
            if club == host_id or club not in visited:
                continue
            values = 100.0 * ratio[:, position]
            rows.append(
                {
                    "id": club,
                    "name": names.get(int(str(club)), str(club)),
                    "visits": visited[int(str(club))],
                    "index": summarize(values),
                    "p_gt_100": float(np.mean(values > 100.0)),
                    "extra": summarize(extra[:, position]),
                }
            )
        rows.sort(key=lambda item: -float(item["index"]["median"]))  # type: ignore[index]
        return {
            "host_id": host_id,
            "host": names.get(host_id, str(host_id)),
            "capacity": capacity,
            "reference_expected": summarize(
                reference * (float(capacity) if view.measure == "fill" and capacity else 1.0)
            ),
            "home_mean": meta.get("mean_attendance"),
            "opponents_total": len(rows),
            "top": rows[:limit],
            "bottom": rows[::-1][:limit],
            "uniform_ratio": view.measure == "count",
        }


def compare_clubs(artifact: ModelArtifact, first: int, second: int) -> JsonDict:
    view = ArtifactView(artifact)
    positions = view.positions["opponent"]
    if first not in positions or second not in positions:
        raise KeyError("oba kluby muszą występować w modelu jako rywale")
    iaf = np.asarray(artifact.draws["iaf"], dtype=np.float64)
    a = iaf[:, positions[first]]
    b = iaf[:, positions[second]]
    difference = a - b
    probability = float(np.mean(difference > 0))
    return {
        "first": first,
        "second": second,
        "p_first_greater": probability,
        "mcse": math.sqrt(max(probability * (1.0 - probability), 1e-12) / difference.size),
        "difference": summarize(difference),
        "first_iaf": summarize(a),
        "second_iaf": summarize(b),
    }


def capacity_value(scenario: ForecastScenario) -> float:
    return float(scenario.capacity) if scenario.capacity else 0.0


def parse_hour(value: str | None) -> float | None:
    if not value:
        return None
    moment = datetime.strptime(value, "%H:%M")
    return moment.hour + moment.minute / 60.0
