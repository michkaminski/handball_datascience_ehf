from __future__ import annotations

from collections import defaultdict

import numpy as np
from numpy.typing import NDArray

from maf.posterior import PosteriorAnalyzer
from maf.records import Measure

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]

COVERAGE_LEVELS = (0.5, 0.8, 0.95)
BACKTEST_DRAWS = 400


def holdout_mask(season_order: IntArray, holdout_seasons: int) -> NDArray[np.bool_]:
    seasons = sorted(set(int(order) for order in season_order))
    if len(seasons) <= holdout_seasons:
        return np.zeros(season_order.shape, dtype=bool)
    cutoff = seasons[-holdout_seasons]
    return np.asarray(season_order >= cutoff, dtype=bool)


def crps_from_samples(
    samples: FloatArray, observed: FloatArray, rng: np.random.Generator
) -> FloatArray:
    first = np.mean(np.abs(samples - observed[None, :]), axis=0)
    permuted = samples[rng.permutation(samples.shape[0])]
    second = 0.5 * np.mean(np.abs(samples - permuted), axis=0)
    return np.asarray(first - second, dtype=np.float64)


class ChronologicalBacktest:
    def __init__(
        self, analyzer: PosteriorAnalyzer, test_mask: NDArray[np.bool_], seed: int
    ) -> None:
        self._analyzer = analyzer
        self._mask = test_mask
        self._rng = np.random.default_rng(seed)

    def evaluate(self) -> dict[str, object]:
        analyzer = self._analyzer
        data = analyzer.context.data
        test_rows = np.flatnonzero(self._mask)
        train_rows = np.flatnonzero(~self._mask)
        if test_rows.size == 0 or train_rows.size == 0:
            return {"available": False, "reason": "za mało sezonów do walidacji chronologicznej"}
        draws = np.sort(
            self._rng.choice(
                analyzer.n_draws, size=min(BACKTEST_DRAWS, analyzer.n_draws), replace=False
            )
        )
        observed = data.spectators[test_rows].astype(np.float64)
        means = np.zeros(test_rows.size)
        samples = np.zeros((draws.size, test_rows.size))
        for chunk in np.array_split(np.arange(test_rows.size), max(1, test_rows.size // 2000)):
            mean, _, replicate = analyzer.predictive_moments(draws, test_rows[chunk])
            means[chunk] = mean.mean(axis=0)
            samples[:, chunk] = replicate
        medians = np.median(samples, axis=0)
        coverage = {}
        for level in COVERAGE_LEVELS:
            low = np.quantile(samples, (1.0 - level) / 2.0, axis=0)
            high = np.quantile(samples, 1.0 - (1.0 - level) / 2.0, axis=0)
            hits = (observed >= low) & (observed <= high)
            coverage[f"{int(level * 100)}"] = {
                "nominal": level,
                "observed": float(np.mean(hits)),
                "mean_width": float(np.mean(high - low)),
            }
        below = np.mean(samples < observed[None, :], axis=0)
        equal = np.mean(samples == observed[None, :], axis=0)
        pit = below + self._rng.uniform(size=observed.size) * equal
        pit_counts, _ = np.histogram(pit, bins=10, range=(0.0, 1.0))
        baseline = self._baseline(train_rows, test_rows)
        crps = crps_from_samples(samples, observed, self._rng)
        result: dict[str, object] = {
            "available": True,
            "train_matches": int(train_rows.size),
            "test_matches": int(test_rows.size),
            "train_seasons": sorted({self._season_key(int(row)) for row in train_rows}),
            "test_seasons": sorted({self._season_key(int(row)) for row in test_rows}),
            "mae": float(np.mean(np.abs(observed - medians))),
            "rmse": float(np.sqrt(np.mean((observed - means) ** 2))),
            "crps": float(np.mean(crps)),
            "baseline_mae": float(np.mean(np.abs(observed - baseline))),
            "baseline_rmse": float(np.sqrt(np.mean((observed - baseline) ** 2))),
            "baseline_label": "średnia frekwencja gospodarza w danych treningowych",
            "coverage": coverage,
            "pit_histogram": [int(item) for item in pit_counts],
        }
        if data.measure is Measure.FILL:
            capacity = data.capacity[test_rows].astype(np.float64)
            result["mae_fill_pp"] = float(100.0 * np.mean(np.abs(observed - medians) / capacity))
        return result

    def _season_key(self, row: int) -> str:
        data = self._analyzer.context.data
        season = data.indexes["season"].keys[int(data.groups["season"][row])]
        return str(season)

    def _baseline(self, train_rows: IntArray, test_rows: IntArray) -> FloatArray:
        data = self._analyzer.context.data
        totals: dict[int, list[float]] = defaultdict(list)
        hosts = data.groups["host"]
        for row in train_rows:
            totals[int(hosts[row])].append(float(data.spectators[row]))
        overall = float(np.mean(data.spectators[train_rows]))
        means = {host: float(np.mean(values)) for host, values in totals.items()}
        return np.array(
            [means.get(int(hosts[row]), overall) for row in test_rows], dtype=np.float64
        )
