from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from typing import Protocol

from ehf.domain.attendance_analytics import format_rounded
from ehf.domain.goal_distribution import format_int, format_share

MIN_FORECAST_ROWS = 40
TEST_FRACTION = 0.2
RIDGE = 1e-6
PIVOT_EPSILON = 1e-12
FEATURE_NAMES = (
    "Home club mean of earlier matches",
    "Weekend kickoff",
    "Month (sine)",
    "Month (cosine)",
    "Kickoff hour",
)
FORECAST_NOTE = (
    "Features are known before kickoff: weekday (weekend flag), month, hour and the home club's mean "
    "attendance in earlier matches. Scores and later matches are never used. The model is fitted on the "
    "earlier 80% of matches and tested on the latest 20%."
)


class ForecastMatch(Protocol):
    match_id: int
    kickoff: datetime | None
    spectators: int
    home_club_id: int | None


@dataclass(frozen=True)
class FeatureRow:
    match_id: int
    kickoff: datetime
    features: tuple[float, ...]
    target: float


@dataclass(frozen=True)
class ForecastCoefficient:
    name: str
    value: float

    @property
    def value_label(self) -> str:
        return f"{self.value:+,.2f}".replace(",", " ")


@dataclass(frozen=True)
class ForecastResult:
    train_size: int
    test_size: int
    mae: float
    rmse: float
    baseline_mae: float
    baseline_rmse: float
    coefficients: tuple[ForecastCoefficient, ...]
    train_end: datetime
    test_start: datetime

    @property
    def improvement(self) -> float | None:
        if self.baseline_mae == 0:
            return None
        return 1 - self.mae / self.baseline_mae

    @property
    def improvement_label(self) -> str:
        if self.improvement is None:
            return "—"
        return f"{self.improvement * 100:+.1f}%"

    @property
    def mae_label(self) -> str:
        return format_rounded(self.mae)

    @property
    def rmse_label(self) -> str:
        return format_rounded(self.rmse)

    @property
    def baseline_mae_label(self) -> str:
        return format_rounded(self.baseline_mae)

    @property
    def baseline_rmse_label(self) -> str:
        return format_rounded(self.baseline_rmse)

    @property
    def train_label(self) -> str:
        return format_int(self.train_size)

    @property
    def test_label(self) -> str:
        return format_int(self.test_size)

    @property
    def split_label(self) -> str:
        return (
            f"Trained up to {self.train_end:%Y-%m-%d}, tested from {self.test_start:%Y-%m-%d}"
        )

    @property
    def share_label(self) -> str:
        total = self.train_size + self.test_size
        return format_share(self.test_size / total) if total else "—"


@dataclass(frozen=True)
class ForecastOutcome:
    result: ForecastResult | None
    warning: str | None = None


@dataclass(frozen=True)
class LinearModel:
    intercept: float
    weights: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    def predict(self, features: Sequence[float]) -> float:
        return self.intercept + sum(
            weight * (value - mean) / scale
            for weight, value, mean, scale in zip(
                self.weights, features, self.means, self.scales
            )
        )

    @property
    def raw_weights(self) -> tuple[float, ...]:
        return tuple(weight / scale for weight, scale in zip(self.weights, self.scales))


class LinearSolver:
    @staticmethod
    def solve(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> tuple[float, ...]:
        size = len(vector)
        rows = [list(matrix[index]) + [vector[index]] for index in range(size)]
        for column in range(size):
            pivot = max(range(column, size), key=lambda index: abs(rows[index][column]))
            if abs(rows[pivot][column]) < PIVOT_EPSILON:
                raise ValueError("matrix is singular")
            rows[column], rows[pivot] = rows[pivot], rows[column]
            for index in range(column + 1, size):
                factor = rows[index][column] / rows[column][column]
                for offset in range(column, size + 1):
                    rows[index][offset] -= factor * rows[column][offset]
        solution = [0.0] * size
        for index in range(size - 1, -1, -1):
            known = sum(rows[index][offset] * solution[offset] for offset in range(index + 1, size))
            solution[index] = (rows[index][size] - known) / rows[index][index]
        return tuple(solution)


class OlsRegressor:
    @staticmethod
    def fit(features: Sequence[Sequence[float]], targets: Sequence[float]) -> LinearModel:
        if not features or len(features) != len(targets):
            raise ValueError("features and targets must be non-empty and of equal length")
        count = len(features)
        width = len(features[0])
        means = tuple(sum(row[column] for row in features) / count for column in range(width))
        scales = tuple(
            OlsRegressor._scale([row[column] for row in features], means[column])
            for column in range(width)
        )
        standardized = [
            [(row[column] - means[column]) / scales[column] for column in range(width)]
            for row in features
        ]
        target_mean = sum(targets) / count
        centered = [target - target_mean for target in targets]
        gram = [
            [
                sum(row[left] * row[right] for row in standardized)
                + (RIDGE if left == right else 0.0)
                for right in range(width)
            ]
            for left in range(width)
        ]
        moment = [
            sum(row[column] * value for row, value in zip(standardized, centered))
            for column in range(width)
        ]
        weights = LinearSolver.solve(gram, moment)
        return LinearModel(target_mean, weights, means, scales)

    @staticmethod
    def _scale(column: Sequence[float], mean: float) -> float:
        variance = sum((value - mean) ** 2 for value in column) / len(column)
        deviation = math.sqrt(variance)
        return deviation if deviation > 0 else 1.0


class ForecastFeatureBuilder:
    @staticmethod
    def build(sample: Sequence[ForecastMatch]) -> tuple[FeatureRow, ...]:
        dated = sorted(
            (match for match in sample if match.kickoff is not None),
            key=lambda match: (match.kickoff, match.match_id),
        )
        club_sums: dict[int, float] = {}
        club_counts: dict[int, int] = {}
        total_sum = 0.0
        total_count = 0
        rows: list[FeatureRow] = []
        for kickoff, group in groupby(dated, key=lambda match: match.kickoff):
            matches = list(group)
            if total_count:
                global_mean = total_sum / total_count
                for match in matches:
                    prior = ForecastFeatureBuilder._prior(
                        match.home_club_id, club_sums, club_counts, global_mean
                    )
                    rows.append(
                        FeatureRow(
                            match_id=match.match_id,
                            kickoff=kickoff,
                            features=ForecastFeatureBuilder._features(kickoff, prior),
                            target=float(match.spectators),
                        )
                    )
            for match in matches:
                total_sum += match.spectators
                total_count += 1
                if match.home_club_id is not None:
                    club_sums[match.home_club_id] = (
                        club_sums.get(match.home_club_id, 0.0) + match.spectators
                    )
                    club_counts[match.home_club_id] = club_counts.get(match.home_club_id, 0) + 1
        return tuple(rows)

    @staticmethod
    def _prior(
        club_id: int | None,
        sums: dict[int, float],
        counts: dict[int, int],
        fallback: float,
    ) -> float:
        if club_id is None or not counts.get(club_id):
            return fallback
        return sums[club_id] / counts[club_id]

    @staticmethod
    def _features(kickoff: datetime, prior: float) -> tuple[float, ...]:
        angle = 2 * math.pi * (kickoff.month - 1) / 12
        return (
            prior,
            1.0 if kickoff.weekday() >= 5 else 0.0,
            math.sin(angle),
            math.cos(angle),
            float(kickoff.hour),
        )


class AttendanceForecaster:
    @staticmethod
    def forecast(sample: Sequence[ForecastMatch]) -> ForecastOutcome:
        rows = ForecastFeatureBuilder.build(sample)
        if len(rows) < MIN_FORECAST_ROWS:
            return ForecastOutcome(
                None,
                f"Forecast skipped: {format_int(len(rows))} matches have a kickoff time and earlier "
                f"matches to learn from; at least {MIN_FORECAST_ROWS} are required.",
            )
        split = len(rows) - max(1, round(len(rows) * TEST_FRACTION))
        train, test = rows[:split], rows[split:]
        try:
            model = OlsRegressor.fit(
                [row.features for row in train], [row.target for row in train]
            )
        except ValueError:
            return ForecastOutcome(None, "Forecast skipped: the training data could not be fitted.")
        errors = [row.target - model.predict(row.features) for row in test]
        baseline = [row.target - row.features[0] for row in test]
        return ForecastOutcome(
            ForecastResult(
                train_size=len(train),
                test_size=len(test),
                mae=AttendanceForecaster._mae(errors),
                rmse=AttendanceForecaster._rmse(errors),
                baseline_mae=AttendanceForecaster._mae(baseline),
                baseline_rmse=AttendanceForecaster._rmse(baseline),
                coefficients=tuple(
                    ForecastCoefficient(name, value)
                    for name, value in zip(FEATURE_NAMES, model.raw_weights)
                ),
                train_end=train[-1].kickoff,
                test_start=test[0].kickoff,
            )
        )

    @staticmethod
    def _mae(errors: Sequence[float]) -> float:
        return sum(abs(error) for error in errors) / len(errors)

    @staticmethod
    def _rmse(errors: Sequence[float]) -> float:
        return math.sqrt(sum(error * error for error in errors) / len(errors))
