from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import expit

from maf.design import GROUPS, ModelData
from maf.diagnostics import ess_bulk, rank_normalized_rhat
from maf.features import FEATURE_LABELS
from maf.fit import PosteriorFit
from maf.quality import PreparedMatch
from maf.records import Measure, ModelSpec

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
JsonDict = dict[str, object]

REFERENCE_SAMPLE = 500
SEASON_REFERENCE_SAMPLE = 160
SEASON_DRAWS = 200
RESIDUAL_DRAWS = 400
PPC_DRAWS = 200
HISTOGRAM_BINS = 40
FILL_THRESHOLDS = (0.75, 0.9, 0.95, 1.0)


def summarize(values: FloatArray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "q025": float(np.quantile(values, 0.025)),
        "q975": float(np.quantile(values, 0.975)),
        "q10": float(np.quantile(values, 0.10)),
        "q90": float(np.quantile(values, 0.90)),
        "sd": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
    }


def histogram(values: FloatArray, bins: int = HISTOGRAM_BINS) -> JsonDict:
    low, high = np.quantile(values, [0.002, 0.998])
    if not high > low:
        high = low + 1.0
    counts, edges = np.histogram(np.clip(values, low, high), bins=bins, range=(low, high))
    return {"edges": [float(item) for item in edges], "counts": [int(item) for item in counts]}


@dataclass(frozen=True)
class PosteriorContext:
    spec: ModelSpec
    fit: PosteriorFit
    data: ModelData
    matches: Mapping[int, PreparedMatch]
    club_names: Mapping[int, str]

    @property
    def measure(self) -> Measure:
        return self.data.measure


class PosteriorAnalyzer:
    def __init__(self, context: PosteriorContext, seed: int) -> None:
        self.context = context
        self.rng = np.random.default_rng(seed)
        fit = context.fit
        chain_draws = [chain.draws[:: max(fit.settings.thin_store, 1)] for chain in fit.chains]
        self.n_chains = len(chain_draws)
        self.per_chain = chain_draws[0].shape[0]
        self.raw = np.concatenate(chain_draws, axis=0)
        self.params = fit.model.unpack(self.raw)
        self.n_draws = self.raw.shape[0]
        data = context.data
        self.index = {name: data.groups[name] for name in GROUPS}
        seasons = sorted(set(int(order) for order in data.season_order))
        reference_orders = set(seasons[-context.spec.reference_seasons :])
        self.reference_seasons = sorted(reference_orders)
        reference_rows = np.flatnonzero(np.isin(data.season_order, list(reference_orders)))
        self.reference_rows = self._sample_rows(reference_rows, REFERENCE_SAMPLE)

    def _sample_rows(self, rows: IntArray, limit: int) -> IntArray:
        if rows.size <= limit:
            return rows
        return np.sort(self.rng.choice(rows, size=limit, replace=False))

    def eta(
        self, draws: slice | IntArray, rows: IntArray, exclude: Sequence[str] = ()
    ) -> FloatArray:
        params = self.params
        data = self.context.data
        alpha = params["alpha"][draws]
        result = alpha[:, None] + params["beta"][draws] @ data.features[rows].T
        for name in GROUPS:
            if name in exclude:
                continue
            result = result + params[name][draws][:, self.index[name][rows]]
        return np.asarray(result, dtype=np.float64)

    def mean_response(self, eta: FloatArray) -> FloatArray:
        if self.context.measure is Measure.FILL:
            return np.asarray(expit(eta), dtype=np.float64)
        return np.exp(np.clip(eta, -30.0, 30.0))

    def chain_split(self, values: FloatArray) -> FloatArray:
        return values.reshape(self.n_chains, self.per_chain)

    def convergence(self, values: FloatArray) -> tuple[float, float]:
        chains = self.chain_split(values)
        return rank_normalized_rhat(chains), ess_bulk(chains)

    def opponent_indices(self) -> dict[str, FloatArray]:
        rows = self.reference_rows
        base = self.eta(slice(None), rows, exclude=("opponent", "opponent_season"))
        effects = self.params["opponent"]
        if self.context.measure is Measure.COUNT:
            reference_mean = self.mean_response(base).mean(axis=1)
            ratio = np.exp(effects)
            return {
                "iaf": 100.0 * ratio,
                "pp": np.full_like(ratio, math.nan),
                "delta_fill": np.full_like(ratio, math.nan),
                "extra": reference_mean[:, None] * (ratio - 1.0),
                "reference_mean": reference_mean,
                "club_mean": reference_mean[:, None] * ratio,
            }
        reference = expit(base).mean(axis=1)
        club_means = np.zeros_like(effects)
        for draw in range(self.n_draws):
            club_means[draw] = expit(base[draw][:, None] + effects[draw][None, :]).mean(axis=0)
        delta = club_means - reference[:, None]
        capacity = self.reference_capacity()
        return {
            "iaf": 100.0 * club_means / reference[:, None],
            "pp": 100.0 * delta,
            "delta_fill": delta,
            "extra": delta * capacity,
            "reference_mean": reference,
            "club_mean": club_means,
        }

    def host_indices(self) -> FloatArray:
        rows = self.reference_rows
        base = self.eta(slice(None), rows, exclude=("host", "host_season"))
        effects = self.params["host"]
        if self.context.measure is Measure.COUNT:
            return np.asarray(100.0 * np.exp(effects), dtype=np.float64)
        reference = expit(base).mean(axis=1)
        values = np.zeros_like(effects)
        for draw in range(self.n_draws):
            values[draw] = expit(base[draw][:, None] + effects[draw][None, :]).mean(axis=0)
        return np.asarray(100.0 * values / reference[:, None], dtype=np.float64)

    def reference_capacity(self) -> float:
        capacity = self.context.data.capacity[self.reference_rows]
        positive = capacity[capacity > 0]
        return float(np.median(positive)) if positive.size else 0.0

    def season_indices(self) -> dict[Hashable, list[JsonDict]]:
        data = self.context.data
        draws = np.sort(
            self.rng.choice(self.n_draws, size=min(SEASON_DRAWS, self.n_draws), replace=False)
        )
        season_index = data.indexes["season"]
        opponent_index = data.indexes["opponent"]
        counts: dict[tuple[int, int], int] = defaultdict(int)
        for opponent, season in zip(self.index["opponent"], self.index["season"], strict=True):
            counts[(int(opponent), int(season))] += 1
        rows_by_season: dict[int, IntArray] = {}
        for season in range(len(season_index)):
            rows = np.flatnonzero(self.index["season"] == season)
            rows_by_season[season] = self._sample_rows(rows, SEASON_REFERENCE_SAMPLE)
        bases = {
            season: self.eta(draws, rows, exclude=("opponent", "opponent_season"))
            for season, rows in rows_by_season.items()
        }
        result: dict[Hashable, list[JsonDict]] = defaultdict(list)
        pair_index = data.indexes["opponent_season"]
        for position, key in enumerate(pair_index.keys):
            assert isinstance(key, tuple)
            club, season_key = key
            opponent = opponent_index.get(club)
            season = season_index.get(season_key)
            if opponent is None or season is None:
                continue
            effect = (
                self.params["opponent"][draws, opponent]
                + self.params["opponent_season"][draws, position]
            )
            if self.context.measure is Measure.COUNT:
                values = 100.0 * np.exp(effect)
            else:
                base = bases[season]
                reference = expit(base).mean(axis=1)
                values = 100.0 * expit(base + effect[:, None]).mean(axis=1) / reference
            summary = summarize(values)
            result[club].append(
                {
                    "season": str(season_key),
                    "order": int(season_index.keys.index(season_key)),
                    "median": summary["median"],
                    "q025": summary["q025"],
                    "q975": summary["q975"],
                    "q10": summary["q10"],
                    "q90": summary["q90"],
                    "matches": counts[(opponent, season)],
                }
            )
        return result

    def host_baselines(self) -> tuple[FloatArray, list[JsonDict]]:
        data = self.context.data
        host_index = data.indexes["host"]
        n_hosts = len(host_index)
        baselines = np.zeros((self.n_draws, n_hosts))
        meta: list[JsonDict] = []
        for host in range(n_hosts):
            rows = np.flatnonzero(self.index["host"] == host)
            last_order = int(data.season_order[rows].max())
            recent = rows[data.season_order[rows] == last_order]
            eta = self.eta(slice(None), recent, exclude=("opponent", "opponent_season"))
            baselines[:, host] = eta.mean(axis=1)
            capacity = data.capacity[recent]
            positive = capacity[capacity > 0]
            meta.append(
                {
                    "club_id": host_index.keys[host],
                    "capacity": float(np.median(positive)) if positive.size else None,
                    "mean_attendance": float(np.mean(data.spectators[recent])),
                    "matches_recent": int(recent.size),
                    "season_order": last_order,
                }
            )
        return baselines, meta

    def predictive_moments(
        self, draws: IntArray, rows: IntArray
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        data = self.context.data
        eta = self.eta(draws, rows)
        model = self.context.fit.model
        dispersion = model.row_dispersion(
            np.log(self.params["dispersion"][draws]),
            self.params["dispersion_slope"][draws],
            data.capacity[rows].astype(np.float64),
        )
        if self.context.measure is Measure.FILL:
            mu = expit(eta)
            capacity = data.capacity[rows].astype(np.float64)[None, :]
            mean = capacity * mu
            variance = capacity * mu * (1.0 - mu) * (dispersion + capacity) / (dispersion + 1.0)
            probability = self.rng.beta(
                np.clip(mu * dispersion, 1e-9, None), np.clip((1.0 - mu) * dispersion, 1e-9, None)
            )
            replicate = self.rng.binomial(
                np.broadcast_to(data.capacity[rows], mu.shape), probability
            )
        else:
            mean = np.exp(np.clip(eta, -30.0, 30.0))
            variance = mean + mean**2 / dispersion
            rate = self.rng.gamma(dispersion, mean / dispersion)
            replicate = self.rng.poisson(rate)
        return mean, variance, replicate.astype(np.float64)

    def residuals(self) -> list[JsonDict]:
        data = self.context.data
        draws = np.sort(
            self.rng.choice(self.n_draws, size=min(RESIDUAL_DRAWS, self.n_draws), replace=False)
        )
        rows_all = np.arange(data.size)
        expected = np.zeros(data.size)
        total_variance = np.zeros(data.size)
        below = np.zeros(data.size)
        equal = np.zeros(data.size)
        q05 = np.zeros(data.size)
        q95 = np.zeros(data.size)
        for chunk in np.array_split(rows_all, max(1, data.size // 2000)):
            mean, variance, replicate = self.predictive_moments(draws, chunk)
            expected[chunk] = mean.mean(axis=0)
            total_variance[chunk] = variance.mean(axis=0) + mean.var(axis=0)
            observed = data.spectators[chunk].astype(np.float64)[None, :]
            below[chunk] = (replicate < observed).mean(axis=0)
            equal[chunk] = (replicate == observed).mean(axis=0)
            q05[chunk] = np.quantile(replicate, 0.05, axis=0)
            q95[chunk] = np.quantile(replicate, 0.95, axis=0)
        lower_tail = below + 0.5 * equal
        p_value = np.clip(2.0 * np.minimum(lower_tail, 1.0 - lower_tail), 0.0, 1.0)
        sd = np.sqrt(np.maximum(total_variance, 1e-9))
        results: list[JsonDict] = []
        for row in range(data.size):
            match = self.context.matches[int(data.match_ids[row])]
            record = match.record
            actual = float(data.spectators[row])
            capacity = float(data.capacity[row]) if data.capacity[row] > 0 else None
            fill_actual = actual / capacity if capacity else None
            fill_expected = expected[row] / capacity if capacity else None
            results.append(
                {
                    "match_id": record.match_id,
                    "kickoff": record.kickoff.isoformat() if record.kickoff else None,
                    "season": record.season_key,
                    "competition": record.competition_name,
                    "host_id": record.host_id,
                    "host": self.context.club_names.get(record.host_id, record.host_name),
                    "opponent_id": record.opponent_id,
                    "opponent": self.context.club_names.get(
                        record.opponent_id, record.opponent_name
                    ),
                    "venue_id": record.venue_id,
                    "venue": record.venue_name,
                    "score": (
                        f"{record.host_goals}:{record.opponent_goals}"
                        if record.host_goals is not None and record.opponent_goals is not None
                        else None
                    ),
                    "actual": actual,
                    "expected": float(expected[row]),
                    "interval90": [float(q05[row]), float(q95[row])],
                    "difference": float(actual - expected[row]),
                    "difference_pct": (
                        float(100.0 * (actual - expected[row]) / expected[row])
                        if expected[row] > 0
                        else None
                    ),
                    "capacity": capacity,
                    "fill_actual": fill_actual,
                    "fill_expected": fill_expected,
                    "difference_pp": (
                        float(100.0 * (fill_actual - fill_expected))
                        if fill_actual is not None and fill_expected is not None
                        else None
                    ),
                    "z": float((actual - expected[row]) / sd[row]),
                    "pit": float(lower_tail[row]),
                    "p_value": float(p_value[row]),
                    "flags": list(match.flags),
                }
            )
        return results

    def posterior_predictive_checks(self) -> JsonDict:
        data = self.context.data
        draws = np.sort(
            self.rng.choice(self.n_draws, size=min(PPC_DRAWS, self.n_draws), replace=False)
        )
        rows = np.arange(data.size)
        replicates = np.zeros((draws.size, data.size))
        for chunk in np.array_split(rows, max(1, data.size // 2000)):
            replicates[:, chunk] = self.predictive_moments(draws, chunk)[2]
        observed = data.spectators.astype(np.float64)
        if self.context.measure is Measure.FILL:
            capacity = data.capacity.astype(np.float64)
            observed_scale = observed / capacity
            replicated_scale = replicates / capacity[None, :]
            edges = np.linspace(0.0, 1.0, 21)
            statistics = {
                "Średnie wypełnienie": lambda values: np.mean(values, axis=-1),
                "Odchylenie standardowe wypełnienia": lambda values: np.std(values, axis=-1),
                "Odsetek meczów z wypełnieniem ≥ 95%": lambda values: np.mean(
                    values >= 0.95, axis=-1
                ),
                "Odsetek meczów z wypełnieniem ≤ 10%": lambda values: np.mean(
                    values <= 0.10, axis=-1
                ),
                "Mediana wypełnienia": lambda values: np.median(values, axis=-1),
            }
            scale_label = "wypełnienie hali"
        else:
            observed_scale = np.log10(np.maximum(observed, 1.0))
            replicated_scale = np.log10(np.maximum(replicates, 1.0))
            low = float(min(observed_scale.min(), np.quantile(replicated_scale, 0.001)))
            high = float(max(observed_scale.max(), np.quantile(replicated_scale, 0.999)))
            edges = np.linspace(low, high, 21)
            statistics = {
                "Średnia liczba widzów": lambda values: np.mean(10**values, axis=-1),
                "Odchylenie standardowe": lambda values: np.std(10**values, axis=-1),
                "Mediana": lambda values: np.median(10**values, axis=-1),
                "Percentyl 90": lambda values: np.quantile(10**values, 0.9, axis=-1),
                "Odsetek meczów < 100 widzów": lambda values: np.mean(10**values < 100, axis=-1),
            }
            scale_label = "log10(liczba widzów)"
        observed_counts, _ = np.histogram(np.clip(observed_scale, edges[0], edges[-1]), bins=edges)
        replicated_counts = np.stack(
            [
                np.histogram(np.clip(item, edges[0], edges[-1]), bins=edges)[0]
                for item in replicated_scale
            ]
        )
        checks = []
        statistic_functions: Mapping[str, Callable[[FloatArray], object]] = statistics
        for label, function in statistic_functions.items():
            observed_value = float(np.asarray(function(observed_scale)))
            replicated_values = np.asarray(function(replicated_scale), dtype=np.float64)
            checks.append(
                {
                    "statistic": label,
                    "observed": observed_value,
                    "replicated_median": float(np.median(replicated_values)),
                    "replicated_q05": float(np.quantile(replicated_values, 0.05)),
                    "replicated_q95": float(np.quantile(replicated_values, 0.95)),
                    "p_value": float(np.mean(replicated_values >= observed_value)),
                }
            )
        return {
            "scale": scale_label,
            "draws": int(draws.size),
            "edges": [float(item) for item in edges],
            "observed": [int(item) for item in observed_counts],
            "replicated_median": [float(item) for item in np.median(replicated_counts, axis=0)],
            "replicated_q05": [
                float(item) for item in np.quantile(replicated_counts, 0.05, axis=0)
            ],
            "replicated_q95": [
                float(item) for item in np.quantile(replicated_counts, 0.95, axis=0)
            ],
            "checks": checks,
        }

    def coefficients(self, feature_names: Sequence[str]) -> list[JsonDict]:
        rows = self.reference_rows
        base = self.eta(slice(None), rows)
        reference = self.mean_response(base).mean(axis=1)
        items: list[JsonDict] = []
        for column, name in enumerate(feature_names):
            values = self.params["beta"][:, column]
            shifted = self.mean_response(base + values[:, None]).mean(axis=1)
            if self.context.measure is Measure.FILL:
                effect = 100.0 * (shifted - reference)
                unit = "p.p. wypełnienia"
            else:
                effect = 100.0 * (shifted / reference - 1.0)
                unit = "% widzów"
            rhat, ess = self.convergence(values)
            items.append(
                {
                    "name": name,
                    "label": FEATURE_LABELS.get(name, name),
                    "coefficient": summarize(values),
                    "p_positive": float(np.mean(values > 0)),
                    "effect": summarize(effect),
                    "effect_unit": unit,
                    "rhat": rhat,
                    "ess_bulk": ess,
                }
            )
        return items
