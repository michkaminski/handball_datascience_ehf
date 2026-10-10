from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ehf.domain.attendance_analytics import (
    AttendanceStatsCalculator,
    format_rounded,
    format_signed_decimal,
)
from ehf.domain.attendance_calendar import WEEKDAY_LABELS
from ehf.domain.attendance_forecast import AttendanceForecaster, ForecastOutcome
from ehf.domain.goal_distribution import format_int, format_share

SAMPLE_LIMIT = 8000
SMALL_SAMPLE = 5
CORRELATION_SMALL_SAMPLE = 30
HISTOGRAM_BINS = 10
IQR_FENCE_FACTOR = 1.5
MIN_ANOMALY_SAMPLE = 4
MIN_CORRELATION_SAMPLE = 3
ANOMALY_LIMIT = 10
OPPONENT_EFFECT_LIMIT = 10
PERCENTILE_POINTS = (
    ("p10", 0.10),
    ("p25", 0.25),
    ("p50", 0.50),
    ("p75", 0.75),
    ("p90", 0.90),
    ("p95", 0.95),
)
CAUSATION_NOTE = (
    "Correlation describes association, not causation: a final score is only known after the match "
    "and cannot explain a crowd that was already in the hall."
)
OPPONENT_CLUB_REQUIRED_NOTE = "Opponent effect needs a home club filter; it was skipped."
NO_SAMPLE_NOTE = "No matches with known attendance for the selected filters."


@dataclass(frozen=True)
class MatchSample:
    match_id: int
    kickoff: datetime | None
    spectators: int
    home_club_id: int | None
    away_club_id: int | None
    home: str
    away: str
    home_goals: int | None
    away_goals: int | None

    def __post_init__(self) -> None:
        if self.spectators < 0:
            raise ValueError("spectators of a known match cannot be negative")

    @property
    def goal_difference(self) -> int | None:
        if self.home_goals is None or self.away_goals is None:
            return None
        return self.home_goals - self.away_goals

    @property
    def total_goals(self) -> int | None:
        if self.home_goals is None or self.away_goals is None:
            return None
        return self.home_goals + self.away_goals

    @property
    def kickoff_label(self) -> str:
        return "—" if self.kickoff is None else self.kickoff.strftime("%Y-%m-%d")


@dataclass(frozen=True)
class HistogramBin:
    lower: float
    upper: float
    count: int
    share: float
    relative: float

    @property
    def label(self) -> str:
        return f"{format_int(round(self.lower))} – {format_int(round(self.upper))}"

    @property
    def count_label(self) -> str:
        return format_int(self.count)

    @property
    def share_label(self) -> str:
        return format_share(self.share)

    @property
    def bar_percent(self) -> int:
        return round(self.relative * 100)


@dataclass(frozen=True)
class PercentilePoint:
    label: str
    value: float | None

    @property
    def value_label(self) -> str:
        return format_rounded(self.value)


@dataclass(frozen=True)
class DistributionStats:
    histogram: tuple[HistogramBin, ...]
    percentiles: tuple[PercentilePoint, ...]


@dataclass(frozen=True)
class StabilityStats:
    n: int
    mean: float | None
    stdev: float | None
    cv: float | None

    @property
    def small_sample(self) -> bool:
        return self.n < SMALL_SAMPLE

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)

    @property
    def stdev_label(self) -> str:
        return format_rounded(self.stdev)

    @property
    def cv_label(self) -> str:
        return "—" if self.cv is None else format_share(self.cv)

    @property
    def note(self) -> str | None:
        if self.small_sample:
            return f"Small sample (n = {self.n}, fewer than {SMALL_SAMPLE}): variability is unreliable."
        return None


@dataclass(frozen=True)
class AttendanceAnomaly:
    match_id: int
    kickoff_label: str
    home: str
    away: str
    spectators: int
    deviation: float

    @property
    def spectators_label(self) -> str:
        return format_int(self.spectators)

    @property
    def deviation_label(self) -> str:
        return format_signed_decimal(self.deviation)


@dataclass(frozen=True)
class AnomalyReport:
    q1: float
    q3: float
    lower_fence: float
    upper_fence: float
    high_count: int
    low_count: int
    high: tuple[AttendanceAnomaly, ...]
    low: tuple[AttendanceAnomaly, ...]

    @property
    def lower_fence_label(self) -> str:
        return format_rounded(self.lower_fence)

    @property
    def upper_fence_label(self) -> str:
        return format_rounded(self.upper_fence)

    @property
    def count_label(self) -> str:
        return format_int(self.high_count + self.low_count)


@dataclass(frozen=True)
class WeekdayEffect:
    weekday: int
    n: int
    mean: float | None

    @property
    def label(self) -> str:
        return WEEKDAY_LABELS[self.weekday]

    @property
    def small_sample(self) -> bool:
        return self.n < SMALL_SAMPLE

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)


@dataclass(frozen=True)
class OpponentEffectRow:
    opponent_id: int
    opponent_name: str
    n: int
    mean: float
    difference: float

    @property
    def small_sample(self) -> bool:
        return self.n < SMALL_SAMPLE

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)

    @property
    def difference_label(self) -> str:
        return format_signed_decimal(self.difference)


@dataclass(frozen=True)
class OpponentEffect:
    host_mean: float | None
    rows: tuple[OpponentEffectRow, ...]
    note: str | None = None

    @property
    def host_mean_label(self) -> str:
        return format_rounded(self.host_mean)


@dataclass(frozen=True)
class Correlation:
    label: str
    n: int
    coefficient: float | None

    @property
    def small_sample(self) -> bool:
        return self.n < CORRELATION_SMALL_SAMPLE

    @property
    def coefficient_label(self) -> str:
        return "—" if self.coefficient is None else f"{self.coefficient:+.2f}"

    @property
    def strength(self) -> str:
        if self.coefficient is None:
            return "not available"
        size = abs(self.coefficient)
        if size < 0.1:
            return "negligible"
        if size < 0.3:
            return "weak"
        if size < 0.5:
            return "moderate"
        return "strong"

    @property
    def warning(self) -> str | None:
        if self.small_sample:
            return f"Small sample (n = {self.n}, fewer than {CORRELATION_SMALL_SAMPLE}): unstable estimate."
        return None


@dataclass(frozen=True)
class ScienceReport:
    sample_size: int
    known_total: int
    distribution: DistributionStats | None
    stability: StabilityStats | None
    anomalies: AnomalyReport | None
    weekdays: tuple[WeekdayEffect, ...]
    opponent_effect: OpponentEffect
    correlations: tuple[Correlation, ...]
    forecast: ForecastOutcome
    notes: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return self.sample_size == 0

    @property
    def truncated(self) -> bool:
        return self.known_total > self.sample_size

    @property
    def sample_label(self) -> str:
        return format_int(self.sample_size)


class AttendanceScienceCalculator:
    @staticmethod
    def histogram(values: Sequence[float], bins: int = HISTOGRAM_BINS) -> tuple[HistogramBin, ...]:
        if bins < 1:
            raise ValueError("bins must be positive")
        if not values:
            return ()
        low, high = min(values), max(values)
        if low == high:
            return (HistogramBin(low, high, len(values), 1.0, 1.0),)
        width = (high - low) / bins
        counts = [0] * bins
        for value in values:
            counts[min(int((value - low) / width), bins - 1)] += 1
        peak = max(counts)
        return tuple(
            HistogramBin(
                lower=low + width * index,
                upper=low + width * (index + 1),
                count=count,
                share=count / len(values),
                relative=count / peak,
            )
            for index, count in enumerate(counts)
        )

    @staticmethod
    def percentiles(values: Sequence[float]) -> tuple[PercentilePoint, ...]:
        return tuple(
            PercentilePoint(label, AttendanceStatsCalculator.percentile(values, fraction))
            for label, fraction in PERCENTILE_POINTS
        )

    @staticmethod
    def distribution(values: Sequence[float]) -> DistributionStats | None:
        if not values:
            return None
        return DistributionStats(
            histogram=AttendanceScienceCalculator.histogram(values),
            percentiles=AttendanceScienceCalculator.percentiles(values),
        )

    @staticmethod
    def stdev(values: Sequence[float]) -> float | None:
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))

    @staticmethod
    def coefficient_of_variation(values: Sequence[float]) -> float | None:
        deviation = AttendanceScienceCalculator.stdev(values)
        mean = AttendanceStatsCalculator.mean(values)
        if deviation is None or mean is None or mean == 0:
            return None
        return deviation / mean

    @staticmethod
    def stability(values: Sequence[float]) -> StabilityStats | None:
        if not values:
            return None
        return StabilityStats(
            n=len(values),
            mean=AttendanceStatsCalculator.mean(values),
            stdev=AttendanceScienceCalculator.stdev(values),
            cv=AttendanceScienceCalculator.coefficient_of_variation(values),
        )

    @staticmethod
    def iqr_fences(values: Sequence[float]) -> tuple[float, float] | None:
        q1, q3 = AttendanceStatsCalculator.quartiles(values)
        if q1 is None or q3 is None:
            return None
        spread = (q3 - q1) * IQR_FENCE_FACTOR
        return q1 - spread, q3 + spread

    @staticmethod
    def anomalies(
        sample: Sequence[MatchSample], limit: int = ANOMALY_LIMIT
    ) -> AnomalyReport | None:
        values = [match.spectators for match in sample]
        if len(values) < MIN_ANOMALY_SAMPLE:
            return None
        fences = AttendanceScienceCalculator.iqr_fences(values)
        quartiles = AttendanceStatsCalculator.quartiles(values)
        if fences is None or quartiles[0] is None or quartiles[1] is None:
            return None
        lower, upper = fences
        highs = sorted(
            (match for match in sample if match.spectators > upper),
            key=lambda match: (-match.spectators, match.match_id),
        )
        lows = sorted(
            (match for match in sample if match.spectators < lower),
            key=lambda match: (match.spectators, match.match_id),
        )
        return AnomalyReport(
            q1=quartiles[0],
            q3=quartiles[1],
            lower_fence=lower,
            upper_fence=upper,
            high_count=len(highs),
            low_count=len(lows),
            high=tuple(AttendanceScienceCalculator._anomaly(m, upper) for m in highs[:limit]),
            low=tuple(AttendanceScienceCalculator._anomaly(m, lower) for m in lows[:limit]),
        )

    @staticmethod
    def _anomaly(match: MatchSample, fence: float) -> AttendanceAnomaly:
        return AttendanceAnomaly(
            match_id=match.match_id,
            kickoff_label=match.kickoff_label,
            home=match.home,
            away=match.away,
            spectators=match.spectators,
            deviation=match.spectators - fence,
        )

    @staticmethod
    def weekday_effect(sample: Sequence[MatchSample]) -> tuple[WeekdayEffect, ...]:
        grouped: dict[int, list[int]] = {}
        for match in sample:
            if match.kickoff is not None:
                grouped.setdefault(match.kickoff.weekday(), []).append(match.spectators)
        return tuple(
            WeekdayEffect(
                weekday=weekday,
                n=len(values),
                mean=AttendanceStatsCalculator.mean(values),
            )
            for weekday, values in sorted(grouped.items())
        )

    @staticmethod
    def opponent_effect(
        sample: Sequence[MatchSample],
        club_id: int | None,
        limit: int = OPPONENT_EFFECT_LIMIT,
    ) -> OpponentEffect:
        if club_id is None:
            return OpponentEffect(None, (), OPPONENT_CLUB_REQUIRED_NOTE)
        hosted = [match for match in sample if match.home_club_id == club_id]
        host_mean = AttendanceStatsCalculator.mean([match.spectators for match in hosted])
        if host_mean is None:
            return OpponentEffect(None, (), NO_SAMPLE_NOTE)
        grouped: dict[int, list[MatchSample]] = {}
        for match in hosted:
            if match.away_club_id is not None:
                grouped.setdefault(match.away_club_id, []).append(match)
        rows = sorted(
            (
                AttendanceScienceCalculator._opponent_row(opponent_id, matches, host_mean)
                for opponent_id, matches in grouped.items()
            ),
            key=lambda row: (-row.difference, row.opponent_name.casefold(), row.opponent_id),
        )
        if len(rows) > 2 * limit:
            rows = rows[:limit] + rows[-limit:]
        return OpponentEffect(host_mean, tuple(rows))

    @staticmethod
    def _opponent_row(
        opponent_id: int, matches: Sequence[MatchSample], host_mean: float
    ) -> OpponentEffectRow:
        mean = sum(match.spectators for match in matches) / len(matches)
        return OpponentEffectRow(
            opponent_id=opponent_id,
            opponent_name=matches[-1].away,
            n=len(matches),
            mean=mean,
            difference=mean - host_mean,
        )

    @staticmethod
    def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
        if len(xs) != len(ys):
            raise ValueError("series must have the same length")
        if len(xs) < MIN_CORRELATION_SAMPLE:
            return None
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        variance_x = sum((x - mean_x) ** 2 for x in xs)
        variance_y = sum((y - mean_y) ** 2 for y in ys)
        if variance_x == 0 or variance_y == 0:
            return None
        covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        return max(-1.0, min(1.0, covariance / math.sqrt(variance_x * variance_y)))

    @staticmethod
    def correlations(sample: Sequence[MatchSample]) -> tuple[Correlation, ...]:
        scored = [match for match in sample if match.goal_difference is not None]
        spectators = [float(match.spectators) for match in scored]
        return (
            Correlation(
                "Spectators vs goal difference (home − away)",
                len(scored),
                AttendanceScienceCalculator.pearson(
                    spectators, [float(match.goal_difference) for match in scored]
                ),
            ),
            Correlation(
                "Spectators vs total goals",
                len(scored),
                AttendanceScienceCalculator.pearson(
                    spectators, [float(match.total_goals) for match in scored]
                ),
            ),
        )

    @staticmethod
    def build(
        sample: Sequence[MatchSample], known_total: int, club_id: int | None
    ) -> ScienceReport:
        ordered = tuple(
            sorted(
                sample,
                key=lambda match: (match.kickoff is None, match.kickoff or datetime.min, match.match_id),
            )
        )
        values = [float(match.spectators) for match in ordered]
        return ScienceReport(
            sample_size=len(ordered),
            known_total=known_total,
            distribution=AttendanceScienceCalculator.distribution(values),
            stability=AttendanceScienceCalculator.stability(values),
            anomalies=AttendanceScienceCalculator.anomalies(ordered),
            weekdays=AttendanceScienceCalculator.weekday_effect(ordered),
            opponent_effect=AttendanceScienceCalculator.opponent_effect(ordered, club_id),
            correlations=AttendanceScienceCalculator.correlations(ordered),
            forecast=AttendanceForecaster.forecast(ordered),
            notes=AttendanceScienceCalculator._notes(len(ordered), known_total),
        )

    @staticmethod
    def _notes(size: int, known_total: int) -> tuple[str, ...]:
        if size == 0:
            return (NO_SAMPLE_NOTE,)
        notes = [
            f"Based on {format_int(size)} matches with known attendance (0 counts as known; "
            "missing attendance is excluded).",
        ]
        if known_total > size:
            notes.append(
                f"The sample is capped at the {format_int(size)} most recent of "
                f"{format_int(known_total)} matches; older matches are not analysed."
            )
        if size < SMALL_SAMPLE:
            notes.append(f"Small sample (n = {size}): treat every figure below as indicative only.")
        notes.append(CAUSATION_NOTE)
        return tuple(notes)
