from __future__ import annotations

import hashlib
import platform
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import scipy
from numpy.typing import NDArray
from scipy.special import expit

import maf
from maf.artifacts import ArtifactStore
from maf.design import GROUP_LABELS, GROUPS, ModelData, ModelDataBuilder
from maf.features import FEATURE_LABELS, FeatureBuilder, FeatureScaler, RawFeatures, TeamState
from maf.fit import PosteriorFit, PosteriorSampler
from maf.model import PriorSettings
from maf.nuts import SamplerSettings
from maf.posterior import PosteriorAnalyzer, PosteriorContext, histogram, summarize
from maf.quality import DataQualityChecker, PreparedMatch, QualityPolicy
from maf.records import CapacityOverride, ClubLineage, MatchRecord, Measure, ModelSpec
from maf.validation import ChronologicalBacktest, holdout_mask

JsonDict = dict[str, object]
Progress = Callable[[str], None]


@dataclass(frozen=True)
class TrainingResult:
    version: str
    directory: str
    status: str
    summary: JsonDict


def data_fingerprint(records: Sequence[MatchRecord]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item.match_id):
        digest.update(
            f"{record.match_id}|{record.spectators}|{record.capacity}|{record.host_id}|"
            f"{record.opponent_id}|{record.kickoff}".encode()
        )
    return digest.hexdigest()


class MafTrainer:
    def __init__(
        self,
        store: ArtifactStore,
        settings: SamplerSettings,
        priors: PriorSettings | None = None,
        quality_policy: QualityPolicy | None = None,
        overrides: Iterable[CapacityOverride] = (),
        lineage: Iterable[ClubLineage] = (),
        progress: Progress | None = None,
        parallel: bool = True,
    ) -> None:
        self._store = store
        self._settings = settings
        self._priors = priors or PriorSettings()
        self._lineage = tuple(lineage)
        self._checker = DataQualityChecker(quality_policy, overrides, self._lineage)
        self._progress = progress or (lambda message: None)
        self._parallel = parallel

    def train(
        self,
        records: Sequence[MatchRecord],
        spec: ModelSpec,
        club_names: Mapping[int, str],
        backtest: bool = True,
    ) -> TrainingResult:
        started = datetime.now(UTC)
        self._progress(f"[{spec.key}] kontrola jakości {len(records)} rekordów")
        prepared, quality = self._checker.prepare(records)
        raw, states = FeatureBuilder().build(prepared)
        usable = [
            item
            for item in prepared
            if (item.usable_fill if spec.measure is Measure.FILL else item.usable_count)
        ]
        if len(usable) < 50:
            raise ValueError(f"za mało meczów do estymacji modelu {spec.key}: {len(usable)}")
        scaler = FeatureScaler.fit([raw[item.record.match_id] for item in usable])
        data = ModelDataBuilder().build(prepared, raw, spec.measure, scaler)
        self._progress(f"[{spec.key}] NUTS: {data.size} meczów, {self._settings.chains} łańcuchy")
        sampler = PosteriorSampler(self._settings, self._priors, self._parallel)
        fit = sampler.fit(data)
        self._progress(f"[{spec.key}] diagnostyka: {fit.health.status}")
        matches = {item.record.match_id: item for item in prepared}
        names = self._names(records, club_names)
        context = PosteriorContext(spec, fit, data, matches, names)
        analyzer = PosteriorAnalyzer(context, self._settings.seed + 7)
        self._progress(f"[{spec.key}] indeksy IAF i reszty")
        opponents = analyzer.opponent_indices()
        host_index = analyzer.host_indices()
        seasons = analyzer.season_indices()
        baselines, host_meta = analyzer.host_baselines()
        residuals = analyzer.residuals()
        ppc = analyzer.posterior_predictive_checks()
        coefficients = analyzer.coefficients(scaler.names)
        backtest_summary: JsonDict = {"available": False, "reason": "pominięto na żądanie"}
        if backtest:
            self._progress(f"[{spec.key}] walidacja chronologiczna")
            backtest_summary = self._backtest(prepared, raw, spec, context)
        version = f"{maf.__version__}+{started:%Y%m%d%H%M%S}"
        summary = self._summary(
            spec=spec,
            version=version,
            started=started,
            records=records,
            data=data,
            fit=fit,
            analyzer=analyzer,
            quality=quality.as_dict(),
            scaler=scaler,
            opponents=opponents,
            host_index=host_index,
            seasons=seasons,
            host_meta=host_meta,
            residuals=residuals,
            ppc=ppc,
            coefficients=coefficients,
            backtest=backtest_summary,
            states=states,
            names=names,
            prepared=prepared,
        )
        draws = self._draws(analyzer, opponents, host_index, baselines)
        directory = self._store.save(spec.key, version, summary, residuals, draws)
        self._progress(f"[{spec.key}] zapisano {directory}")
        model_info = summary["model"]
        assert isinstance(model_info, dict)
        return TrainingResult(version, str(directory), str(model_info["status"]), summary)

    def _names(
        self, records: Sequence[MatchRecord], club_names: Mapping[int, str]
    ) -> dict[int, str]:
        names: dict[int, str] = {}
        canonical = {item.previous_id: item.current_id for item in self._lineage}
        for record in sorted(records, key=lambda item: (item.season_order, item.match_id)):
            names[canonical.get(record.host_id, record.host_id)] = record.host_name
            names[canonical.get(record.opponent_id, record.opponent_id)] = record.opponent_name
        names.update({key: value for key, value in club_names.items() if value})
        return names

    def _backtest(
        self,
        prepared: Sequence[PreparedMatch],
        raw: Mapping[int, RawFeatures],
        spec: ModelSpec,
        context: PosteriorContext,
    ) -> JsonDict:
        full = context.data
        mask = holdout_mask(full.season_order, spec.holdout_seasons)
        if not mask.any() or mask.all():
            return {"available": False, "reason": "za mało sezonów do walidacji chronologicznej"}
        train_ids = set(int(item) for item in full.match_ids[~mask])
        scaler = FeatureScaler.fit([raw[match_id] for match_id in sorted(train_ids)])
        data = ModelDataBuilder().build(prepared, dict(raw), spec.measure, scaler)
        test_mask = ~np.isin(data.match_ids, list(train_ids))
        training = data.subset(~test_mask)
        fit = PosteriorSampler(self._settings, self._priors, self._parallel).fit(training)
        analyzer = PosteriorAnalyzer(
            PosteriorContext(spec, fit, data, context.matches, context.club_names),
            self._settings.seed + 11,
        )
        result = ChronologicalBacktest(analyzer, test_mask, self._settings.seed + 13).evaluate()
        result["diagnostics_status"] = fit.health.status
        result["max_rhat"] = fit.health.max_rhat
        return result

    def _draws(
        self,
        analyzer: PosteriorAnalyzer,
        opponents: Mapping[str, NDArray[np.float64]],
        host_index: NDArray[np.float64],
        baselines: NDArray[np.float64],
    ) -> dict[str, NDArray[np.floating]]:
        params = analyzer.params
        draws: dict[str, NDArray[np.floating]] = {
            "alpha": params["alpha"],
            "beta": params["beta"],
            "sigma": params["sigma"],
            "dispersion": params["dispersion"],
            "dispersion_slope": params["dispersion_slope"],
            "iaf": opponents["iaf"],
            "delta_fill": opponents["delta_fill"],
            "extra": opponents["extra"],
            "reference_mean": opponents["reference_mean"],
            "host_index": host_index,
            "host_baseline": baselines,
        }
        for name in GROUPS:
            draws[f"effect_{name}"] = params[name]
        return draws

    def _summary(
        self,
        *,
        spec: ModelSpec,
        version: str,
        started: datetime,
        records: Sequence[MatchRecord],
        data: ModelData,
        fit: PosteriorFit,
        analyzer: PosteriorAnalyzer,
        quality: JsonDict,
        scaler: FeatureScaler,
        opponents: Mapping[str, NDArray[np.float64]],
        host_index: NDArray[np.float64],
        seasons: Mapping[Hashable, list[JsonDict]],
        host_meta: list[JsonDict],
        residuals: list[JsonDict],
        ppc: JsonDict,
        coefficients: list[JsonDict],
        backtest: JsonDict,
        states: Mapping[int, TeamState],
        names: Mapping[int, str],
        prepared: Sequence[PreparedMatch],
    ) -> JsonDict:
        model = fit.model
        health = fit.health.as_dict()
        status = str(health["status"])
        season_keys = [str(key) for key in data.indexes["season"].keys]
        rows_by_match = {int(row["match_id"]): row for row in residuals}  # type: ignore[call-overload]
        clubs = self._clubs(spec, data, analyzer, opponents, host_index, seasons, names, records)
        reference_capacity = analyzer.reference_capacity()
        reference = summarize(opponents["reference_mean"])
        index_keys = {
            name: [list(key) if isinstance(key, tuple) else key for key in data.indexes[name].keys]
            for name in GROUPS
        }
        competitions = self._competitions(records, data)
        venues = self._venues(prepared, data)
        group_info = []
        for group, name in enumerate(GROUPS):
            mode = model.modes[group]
            sigma = summarize(analyzer.params["sigma"][:, group]) if mode != "fixed" else None
            group_info.append(
                {
                    "name": name,
                    "label": GROUP_LABELS[name],
                    "levels": data.group_size(name),
                    "free": model.transforms[group].n_free,
                    "mode": mode,
                    "sigma": sigma,
                }
            )
        return {
            "model": {
                "key": spec.key,
                "label": spec.label,
                "scope": spec.scope,
                "measure": spec.measure.value,
                "version": version,
                "engine_version": maf.__version__,
                "trained_at": started.isoformat(),
                "finished_at": datetime.now(UTC).isoformat(),
                "status": status,
                "sampler": self._settings.as_dict(),
                "priors": self._priors.as_dict(),
                "intercept_prior_mean": model.intercept_mean,
                "dispersion_prior_mean": model.dispersion_mean,
                "capacity_log_mean": model.capacity_log_mean,
                "capacity_log_sd": model.capacity_log_sd,
                "data_fingerprint": data_fingerprint(records),
                "matches_used": data.size,
                "matches_total": len(records),
                "club_lineage": [
                    {
                        "previous_id": item.previous_id,
                        "current_id": item.current_id,
                        "note": item.note,
                    }
                    for item in self._lineage
                ],
                "seasons": season_keys,
                "period": self._period(prepared, data),
                "reference": {
                    "seasons": [
                        season_keys[index]
                        for index in range(len(season_keys))
                        if int(np.unique(data.season_order[data.groups["season"] == index])[0])
                        in analyzer.reference_seasons
                    ],
                    "matches_sampled": int(analyzer.reference_rows.size),
                    "matches_available": int(
                        np.isin(data.season_order, analyzer.reference_seasons).sum()
                    ),
                    "capacity_median": reference_capacity,
                    "expected": reference,
                },
                "features": {
                    **scaler.as_dict(),
                    "labels": [FEATURE_LABELS[name] for name in scaler.names],
                },
                "groups": group_info,
                "environment": {
                    "python": platform.python_version(),
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                },
                "min_matches_reliable": spec.min_matches_reliable,
                "max_ci_width_reliable": spec.max_ci_width_reliable,
            },
            "quality": quality,
            "diagnostics": {
                **health,
                "key_parameters": [item.as_dict() for item in fit.key_parameters],
            },
            "coefficients": coefficients,
            "kpi": self._kpi(data, clubs, residuals),
            "clubs": clubs,
            "index": index_keys,
            "hosts": host_meta,
            "teams": {
                str(team): {
                    "name": names.get(team, str(team)),
                    "form": state.form,
                    "position": state.position,
                    "last_kickoff": state.last_kickoff.isoformat() if state.last_kickoff else None,
                }
                for team, state in states.items()
            },
            "competitions": competitions,
            "venues": venues,
            "surprises": self._surprises(residuals),
            "records": self._records(residuals),
            "heatmap": self._heatmap(residuals, season_keys),
            "ppc": ppc,
            "backtest": backtest,
            "matches_index": len(rows_by_match),
        }

    def _period(self, prepared: Sequence[PreparedMatch], data: ModelData) -> JsonDict:
        used = set(int(item) for item in data.match_ids)
        dates = [
            item.record.kickoff
            for item in prepared
            if item.record.match_id in used and item.record.kickoff
        ]
        return {
            "from": min(dates).date().isoformat() if dates else None,
            "to": max(dates).date().isoformat() if dates else None,
        }

    def _clubs(
        self,
        spec: ModelSpec,
        data: ModelData,
        analyzer: PosteriorAnalyzer,
        opponents: Mapping[str, NDArray[np.float64]],
        host_index: NDArray[np.float64],
        seasons: Mapping[Hashable, list[JsonDict]],
        names: Mapping[int, str],
        records: Sequence[MatchRecord],
    ) -> list[JsonDict]:
        history: dict[int, Counter[str]] = defaultdict(Counter)
        canonical = {item.previous_id: item.current_id for item in self._lineage}
        for record in records:
            history[canonical.get(record.host_id, record.host_id)][record.host_name] += 1
            history[canonical.get(record.opponent_id, record.opponent_id)][
                record.opponent_name
            ] += 1
        opponent_keys = data.indexes["opponent"]
        host_keys = data.indexes["host"]
        clubs_ids = sorted(set(opponent_keys.keys) | set(host_keys.keys), key=lambda key: str(key))
        spectators = data.spectators.astype(np.float64)
        capacity = data.capacity.astype(np.float64)
        fill = np.where(capacity > 0, spectators / np.maximum(capacity, 1.0), np.nan)
        season_names = data.indexes["season"].keys
        base_rows = analyzer.reference_rows
        median_base = np.median(
            analyzer.eta(slice(None), base_rows, exclude=("opponent", "opponent_season")), axis=0
        )
        result: list[JsonDict] = []
        for club in clubs_ids:
            assert isinstance(club, int)
            entry: JsonDict = {
                "id": club,
                "name": names.get(club, str(club)),
                "names_history": [name for name, _ in history[club].most_common()],
            }
            opponent = opponent_keys.get(club)
            if opponent is not None:
                rows = np.flatnonzero(data.groups["opponent"] == opponent)
                iaf = opponents["iaf"][:, opponent]
                rhat, ess = analyzer.convergence(iaf)
                summary = summarize(iaf)
                width = summary["q975"] - summary["q025"]
                notes = []
                if rows.size < spec.min_matches_reliable:
                    notes.append(f"tylko {rows.size} mecze/meczów jako rywal")
                if width > spec.max_ci_width_reliable:
                    notes.append(f"szeroki przedział 95% ({width:.0f} pkt)")
                if not (rhat < 1.01 and ess >= 400):
                    notes.append("ostrzeżenie zbieżności MCMC")
                effect = analyzer.params["opponent"][:, opponent]
                central = self._central(median_base, float(np.median(effect)), data.measure)
                entry["away"] = {
                    "matches": int(rows.size),
                    "hosts": int(np.unique(data.groups["host"][rows]).size),
                    "mean": float(np.mean(spectators[rows])),
                    "median": float(np.median(spectators[rows])),
                    "fill_mean": float(np.nanmean(fill[rows]))
                    if data.measure is Measure.FILL
                    else None,
                    "seasons": sorted(
                        {str(season_names[int(item)]) for item in data.groups["season"][rows]}
                    ),
                    "iaf": summary,
                    "p_gt_100": float(np.mean(iaf > 100.0)),
                    "pp": summarize(opponents["pp"][:, opponent])
                    if data.measure is Measure.FILL
                    else None,
                    "delta_fill": (
                        summarize(opponents["delta_fill"][:, opponent])
                        if data.measure is Measure.FILL
                        else None
                    ),
                    "extra": summarize(opponents["extra"][:, opponent]),
                    "club_mean": summarize(opponents["club_mean"][:, opponent]),
                    "effect": summarize(effect),
                    "central": central,
                    "histogram": histogram(iaf),
                    "rhat": rhat,
                    "ess_bulk": ess,
                    "reliable": not notes,
                    "notes": notes,
                    "by_season": sorted(seasons.get(club, []), key=lambda item: int(item["order"])),  # type: ignore[call-overload]
                }
            host = host_keys.get(club)
            if host is not None:
                rows = np.flatnonzero(data.groups["host"] == host)
                values = host_index[:, host]
                entry["home"] = {
                    "matches": int(rows.size),
                    "mean": float(np.mean(spectators[rows])),
                    "median": float(np.median(spectators[rows])),
                    "fill_mean": float(np.nanmean(fill[rows]))
                    if data.measure is Measure.FILL
                    else None,
                    "index": summarize(values),
                    "p_gt_100": float(np.mean(values > 100.0)),
                }
            result.append(entry)
        return result

    def _central(
        self, median_base: NDArray[np.float64], effect: float, measure: Measure
    ) -> JsonDict:
        if measure is Measure.COUNT:
            reference = float(np.mean(np.exp(median_base)))
            club = float(np.mean(np.exp(median_base + effect)))
        else:
            reference = float(np.mean(expit(median_base)))
            club = float(np.mean(expit(median_base + effect)))
        return {
            "reference": reference,
            "club": club,
            "iaf": 100.0 * club / reference,
            "effect": effect,
        }

    def _kpi(self, data: ModelData, clubs: list[JsonDict], residuals: list[JsonDict]) -> JsonDict:
        spectators = data.spectators.astype(np.float64)
        top = max(residuals, key=lambda row: float(row["actual"]))  # type: ignore[arg-type]
        reliable = [club for club in clubs if _is_reliable(club)]

        def away(club: JsonDict, field: str) -> float:
            value = club["away"]
            assert isinstance(value, dict)
            inner = value[field]
            if isinstance(inner, dict):
                return float(inner["median"])
            return float(inner)

        best_iaf = max(reliable, key=lambda club: away(club, "iaf"), default=None)
        effect_field = "pp" if data.measure is Measure.FILL else "extra"
        best_effect = max(reliable, key=lambda club: away(club, effect_field), default=None)
        capacity = data.capacity.astype(np.float64)
        return {
            "total": float(spectators.sum()),
            "mean": float(spectators.mean()),
            "median": float(np.median(spectators)),
            "sd": float(spectators.std(ddof=1)),
            "fill_mean": float(np.mean(spectators / capacity))
            if data.measure is Measure.FILL
            else None,
            "matches": data.size,
            "top_match": top,
            "best_iaf": (
                {"id": best_iaf["id"], "name": best_iaf["name"], "value": away(best_iaf, "iaf")}
                if best_iaf
                else None
            ),
            "best_effect": (
                {
                    "id": best_effect["id"],
                    "name": best_effect["name"],
                    "value": away(best_effect, effect_field),
                    "unit": "p.p." if data.measure is Measure.FILL else "widzów",
                }
                if best_effect
                else None
            ),
            "reliable_clubs": len(reliable),
        }

    def _competitions(self, records: Sequence[MatchRecord], data: ModelData) -> list[JsonDict]:
        labels: dict[str, str] = {}
        for record in records:
            labels[record.competition_key] = record.competition_name
        counts = Counter(
            str(data.indexes["competition"].keys[int(item)]) for item in data.groups["competition"]
        )
        return [
            {"key": str(key), "name": labels.get(str(key), str(key)), "matches": counts[str(key)]}
            for key in data.indexes["competition"].keys
        ]

    def _venues(self, prepared: Sequence[PreparedMatch], data: ModelData) -> list[JsonDict]:
        used = set(int(item) for item in data.match_ids)
        venues: dict[int, JsonDict] = {}
        for item in prepared:
            record = item.record
            if record.venue_id is None or record.match_id not in used:
                continue
            entry = venues.setdefault(
                record.venue_id,
                {
                    "id": record.venue_id,
                    "name": record.venue_name,
                    "capacity": item.capacity,
                    "hosts": Counter(),
                    "matches": 0,
                },
            )
            entry["matches"] = int(entry["matches"]) + 1  # type: ignore[call-overload]
            hosts = entry["hosts"]
            assert isinstance(hosts, Counter)
            hosts[record.host_id] += 1
        result = []
        for entry in venues.values():
            hosts = entry.pop("hosts")
            assert isinstance(hosts, Counter)
            entry["main_host"] = hosts.most_common(1)[0][0]
            result.append(entry)
        return sorted(result, key=lambda item: -int(item["matches"]))  # type: ignore[call-overload]

    def _surprises(self, residuals: list[JsonDict], limit: int = 50) -> JsonDict:
        ordered = sorted(residuals, key=lambda row: float(row["z"]))  # type: ignore[arg-type]
        return {"positive": ordered[::-1][:limit], "negative": ordered[:limit]}

    def _records(self, residuals: list[JsonDict]) -> JsonDict:
        def best(key: str) -> list[JsonDict]:
            winners: dict[object, JsonDict] = {}
            for row in residuals:
                group = row.get(key)
                if group is None:
                    continue
                current = winners.get(group)
                if current is None or float(row["actual"]) > float(current["actual"]):  # type: ignore[arg-type]
                    winners[group] = row
            return sorted(winners.values(), key=lambda row: -float(row["actual"]))  # type: ignore[arg-type]

        return {
            "season": sorted(best("season"), key=lambda row: str(row["season"])),
            "club": best("host_id")[:40],
            "venue": best("venue_id")[:40],
        }

    def _heatmap(self, residuals: list[JsonDict], seasons: list[str], limit: int = 20) -> JsonDict:
        counts = Counter(int(row["host_id"]) for row in residuals)  # type: ignore[call-overload]
        hosts = [host for host, _ in counts.most_common(limit)]
        names = {int(row["host_id"]): str(row["host"]) for row in residuals}  # type: ignore[call-overload]
        cells: dict[tuple[int, str], list[float]] = defaultdict(list)
        for row in residuals:
            host = int(row["host_id"])  # type: ignore[call-overload]
            if host in hosts:
                cells[(host, str(row["season"]))].append(float(row["z"]))  # type: ignore[arg-type]
        values = [
            [seasons.index(season), hosts.index(host), float(np.mean(items)), len(items)]
            for (host, season), items in cells.items()
            if season in seasons
        ]
        return {
            "seasons": seasons,
            "hosts": [names[host] for host in hosts],
            "host_ids": hosts,
            "values": values,
        }


def _is_reliable(club: JsonDict) -> bool:
    away = club.get("away")
    return isinstance(away, dict) and bool(away["reliable"])
