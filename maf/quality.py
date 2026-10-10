from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from statistics import median

from maf.records import CapacityOverride, ClubLineage, MatchRecord

ISSUE_LABELS = {
    "duplikat": "Zdublowany mecz (ten sam identyfikator albo ta sama data i para drużyn)",
    "brak_frekwencji": "Brak informacji o widzach (NULL) — mecz pominięty, nie liczony jako 0",
    "zero_widzow": "Zero widzów (mecz bez publiczności) — pominięty w modelu atrakcyjności",
    "teren_neutralny": "Mecz na terenie neutralnym (turniej) — pominięty",
    "brak_pojemnosci": "Nieznana pojemność hali — tylko analiza liczby widzów",
    "przekroczona_pojemnosc": (
        "Widzów więcej niż miejsc — pojemność niespójna, pominięty w modelu wypełnienia"
    ),
    "podejrzana_wartosc": "Widzów co najmniej 1,5 raza więcej niż miejsc — wartość podejrzana",
    "odstajaca": "Wartość odstająca względem typowej frekwencji gospodarza (odporny z-score)",
}


@dataclass(frozen=True)
class QualityPolicy:
    exclude_zero_attendance: bool = True
    min_capacity: int = 50
    max_overflow_ratio: float = 1.0
    suspicious_overflow_ratio: float = 1.5
    outlier_robust_z: float = 4.0
    outlier_min_matches: int = 8
    neutral_window_days: int = 2
    neutral_max_home_share: float = 0.34


@dataclass(frozen=True)
class QualityIssue:
    match_id: int
    code: str
    detail: str


@dataclass(frozen=True)
class PreparedMatch:
    record: MatchRecord
    capacity: int | None
    nominal_capacity: int | None
    capacity_source: str
    neutral: bool
    flags: tuple[str, ...]
    usable_count: bool
    usable_fill: bool


@dataclass(frozen=True)
class QualityReport:
    total_records: int
    duplicates_removed: int
    attendance_unknown: int
    attendance_zero: int
    neutral_matches: int
    capacity_unknown: int
    capacity_exceeded: int
    suspicious_values: int
    outliers_flagged: int
    lineage_remapped: int
    usable_count: int
    usable_fill: int
    issues: tuple[QualityIssue, ...] = field(default_factory=tuple)

    def as_dict(self, issue_limit: int = 300) -> dict[str, object]:
        return {
            "total_records": self.total_records,
            "duplicates_removed": self.duplicates_removed,
            "attendance_unknown": self.attendance_unknown,
            "attendance_zero": self.attendance_zero,
            "neutral_matches": self.neutral_matches,
            "capacity_unknown": self.capacity_unknown,
            "capacity_exceeded": self.capacity_exceeded,
            "suspicious_values": self.suspicious_values,
            "outliers_flagged": self.outliers_flagged,
            "lineage_remapped": self.lineage_remapped,
            "usable_count": self.usable_count,
            "usable_fill": self.usable_fill,
            "issue_labels": ISSUE_LABELS,
            "issues": [
                {"match_id": issue.match_id, "code": issue.code, "detail": issue.detail}
                for issue in self.issues
                if issue.code not in {"brak_frekwencji", "brak_pojemnosci"}
            ][:issue_limit],
        }


class CapacityResolver:
    def __init__(self, overrides: Iterable[CapacityOverride] = (), min_capacity: int = 50) -> None:
        self._by_match: dict[int, CapacityOverride] = {}
        self._by_venue_season: dict[tuple[int, str], CapacityOverride] = {}
        self._by_venue: dict[int, CapacityOverride] = {}
        self._min_capacity = min_capacity
        for override in overrides:
            if override.match_id is not None:
                self._by_match[override.match_id] = override
            elif override.venue_id is not None and override.season_key is not None:
                self._by_venue_season[(override.venue_id, override.season_key)] = override
            elif override.venue_id is not None:
                self._by_venue[override.venue_id] = override

    def resolve(self, record: MatchRecord) -> tuple[int | None, str]:
        override = self._by_match.get(record.match_id)
        if override is None and record.venue_id is not None:
            override = self._by_venue_season.get((record.venue_id, record.season_key))
            if override is None:
                override = self._by_venue.get(record.venue_id)
        if override is not None:
            return override.capacity, "korekta"
        if record.capacity is None or record.capacity < self._min_capacity:
            return None, "brak"
        return record.capacity, "nominalna"


class NeutralVenueDetector:
    def __init__(self, window_days: int, max_home_share: float) -> None:
        self._window_days = window_days
        self._max_home_share = max_home_share

    def detect(self, records: Sequence[MatchRecord]) -> set[int]:
        home_venues: dict[tuple[int, str], Counter[int]] = defaultdict(Counter)
        by_venue: dict[int, list[MatchRecord]] = defaultdict(list)
        for record in records:
            if record.venue_id is None:
                continue
            home_venues[(record.host_id, record.season_key)][record.venue_id] += 1
            if record.kickoff is not None:
                by_venue[record.venue_id].append(record)
        neutral: set[int] = set()
        for venue_records in by_venue.values():
            venue_records.sort(key=lambda item: item.kickoff or 0)
            for record in venue_records:
                assert record.kickoff is not None
                hosts = {
                    other.host_id
                    for other in venue_records
                    if other.kickoff is not None
                    and abs((other.kickoff - record.kickoff).days) <= self._window_days
                }
                if len(hosts) < 2:
                    continue
                counts = home_venues[(record.host_id, record.season_key)]
                total = sum(counts.values())
                venue = record.venue_id
                share = counts[venue] / total if total and venue is not None else 0.0
                if total >= 2 and share <= self._max_home_share:
                    neutral.add(record.match_id)
        return neutral


class DataQualityChecker:
    def __init__(
        self,
        policy: QualityPolicy | None = None,
        overrides: Iterable[CapacityOverride] = (),
        lineage: Iterable[ClubLineage] = (),
    ) -> None:
        self._policy = policy or QualityPolicy()
        self._lineage = {item.previous_id: item.current_id for item in lineage}
        self._capacity = CapacityResolver(overrides, self._policy.min_capacity)
        self._neutral = NeutralVenueDetector(
            self._policy.neutral_window_days, self._policy.neutral_max_home_share
        )

    def prepare(self, records: Sequence[MatchRecord]) -> tuple[list[PreparedMatch], QualityReport]:
        policy = self._policy
        issues: list[QualityIssue] = []
        records, remapped = self._apply_lineage(records)
        unique, duplicates = self._deduplicate(records, issues)
        neutral_ids = self._neutral.detect(unique)
        outlier_ids = self._outliers(unique, neutral_ids)
        prepared: list[PreparedMatch] = []
        counters: Counter[str] = Counter()
        for record in unique:
            flags: list[str] = []
            capacity, source = self._capacity.resolve(record)
            spectators = record.spectators
            neutral = record.match_id in neutral_ids
            if spectators is None:
                flags.append("brak_frekwencji")
            elif spectators == 0:
                flags.append("zero_widzow")
            if neutral:
                flags.append("teren_neutralny")
            if capacity is None:
                flags.append("brak_pojemnosci")
            elif spectators is not None and spectators > capacity * policy.max_overflow_ratio:
                flags.append("przekroczona_pojemnosc")
                if spectators >= capacity * policy.suspicious_overflow_ratio:
                    flags.append("podejrzana_wartosc")
            if record.match_id in outlier_ids:
                flags.append("odstajaca")
            known = spectators is not None and spectators >= 0
            zero_blocked = spectators == 0 and policy.exclude_zero_attendance
            usable_count = known and not zero_blocked and not neutral
            usable_fill = (
                usable_count and capacity is not None and "przekroczona_pojemnosc" not in flags
            )
            for flag in flags:
                counters[flag] += 1
                issues.append(QualityIssue(record.match_id, flag, ISSUE_LABELS[flag]))
            prepared.append(
                PreparedMatch(
                    record=record,
                    capacity=capacity,
                    nominal_capacity=record.capacity,
                    capacity_source=source,
                    neutral=neutral,
                    flags=tuple(flags),
                    usable_count=usable_count,
                    usable_fill=usable_fill,
                )
            )
        report = QualityReport(
            total_records=len(records),
            duplicates_removed=duplicates,
            attendance_unknown=counters["brak_frekwencji"],
            attendance_zero=counters["zero_widzow"],
            neutral_matches=counters["teren_neutralny"],
            capacity_unknown=counters["brak_pojemnosci"],
            capacity_exceeded=counters["przekroczona_pojemnosc"],
            suspicious_values=counters["podejrzana_wartosc"],
            outliers_flagged=counters["odstajaca"],
            lineage_remapped=remapped,
            usable_count=sum(1 for item in prepared if item.usable_count),
            usable_fill=sum(1 for item in prepared if item.usable_fill),
            issues=tuple(issues),
        )
        return prepared, report

    def _canonical(self, club: int) -> int:
        seen = {club}
        while club in self._lineage and self._lineage[club] not in seen:
            club = self._lineage[club]
            seen.add(club)
        return club

    def _apply_lineage(self, records: Sequence[MatchRecord]) -> tuple[list[MatchRecord], int]:
        if not self._lineage:
            return list(records), 0
        result: list[MatchRecord] = []
        remapped = 0
        for record in records:
            host = self._canonical(record.host_id)
            opponent = self._canonical(record.opponent_id)
            if host != record.host_id or opponent != record.opponent_id:
                remapped += 1
                record = replace(record, host_id=host, opponent_id=opponent)
            result.append(record)
        return result, remapped

    def _deduplicate(
        self, records: Sequence[MatchRecord], issues: list[QualityIssue]
    ) -> tuple[list[MatchRecord], int]:
        seen_ids: set[int] = set()
        seen_keys: set[tuple[object, ...]] = set()
        unique: list[MatchRecord] = []
        duplicates = 0
        for record in records:
            day = record.kickoff.date() if record.kickoff is not None else None
            key = (day, record.host_id, record.opponent_id, record.competition_key)
            if record.match_id in seen_ids or (day is not None and key in seen_keys):
                duplicates += 1
                issues.append(QualityIssue(record.match_id, "duplikat", ISSUE_LABELS["duplikat"]))
                continue
            seen_ids.add(record.match_id)
            if day is not None:
                seen_keys.add(key)
            unique.append(record)
        return unique, duplicates

    def _outliers(self, records: Sequence[MatchRecord], neutral_ids: set[int]) -> set[int]:
        by_host: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for record in records:
            if record.spectators is None or record.spectators <= 0:
                continue
            if record.match_id in neutral_ids:
                continue
            by_host[record.host_id].append((record.match_id, math.log(record.spectators)))
        flagged: set[int] = set()
        for values in by_host.values():
            if len(values) < self._policy.outlier_min_matches:
                continue
            logs = [value for _, value in values]
            center = median(logs)
            mad = median(abs(value - center) for value in logs) * 1.4826
            if mad <= 1e-9:
                continue
            for match_id, value in values:
                if abs(value - center) / mad > self._policy.outlier_robust_z:
                    flagged.add(match_id)
        return flagged
