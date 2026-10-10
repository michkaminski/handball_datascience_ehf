from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from maf.design import GROUPS, ModelData
from maf.diagnostics import (
    ParameterDiagnostic,
    SamplerHealth,
    diagnose_parameter,
    ebfmi,
)
from maf.model import HierarchicalAttendanceModel, PriorSettings
from maf.nuts import ChainResult, NutsSampler, SamplerSettings

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PosteriorFit:
    model: HierarchicalAttendanceModel
    settings: SamplerSettings
    chains: tuple[ChainResult, ...]
    health: SamplerHealth
    key_parameters: tuple[ParameterDiagnostic, ...]
    group_diagnostics: dict[str, tuple[ParameterDiagnostic, ...]]

    def stacked_draws(self) -> FloatArray:
        return np.concatenate([chain.draws for chain in self.chains], axis=0)

    def stored_draws(self) -> FloatArray:
        step = max(self.settings.thin_store, 1)
        return np.concatenate([chain.draws[::step] for chain in self.chains], axis=0)

    def chain_array(self, column: int) -> FloatArray:
        return np.stack([chain.draws[:, column] for chain in self.chains])


def _run_chain(
    data: ModelData, priors: PriorSettings, settings: SamplerSettings, chain: int
) -> ChainResult:
    model = HierarchicalAttendanceModel(data, priors)
    seed = settings.seed + 1009 * chain
    rng = np.random.default_rng(seed)
    sampler = NutsSampler(model.logp_and_grad, model.dimension, settings)
    return sampler.sample_chain(model.initial_point(rng), seed + 1)


class PosteriorSampler:
    def __init__(
        self,
        settings: SamplerSettings,
        priors: PriorSettings | None = None,
        parallel: bool = True,
    ) -> None:
        self._settings = settings
        self._priors = priors or PriorSettings()
        self._parallel = parallel

    def fit(self, data: ModelData) -> PosteriorFit:
        settings = self._settings
        model = HierarchicalAttendanceModel(data, self._priors)
        if self._parallel and settings.chains > 1:
            with ProcessPoolExecutor(max_workers=settings.chains) as pool:
                futures = [
                    pool.submit(_run_chain, data, self._priors, settings, chain)
                    for chain in range(settings.chains)
                ]
                chains = tuple(future.result() for future in futures)
        else:
            chains = tuple(
                _run_chain(data, self._priors, settings, chain) for chain in range(settings.chains)
            )
        return self._summarize(model, chains)

    def _summarize(
        self, model: HierarchicalAttendanceModel, chains: tuple[ChainResult, ...]
    ) -> PosteriorFit:
        names = model.parameter_names()
        layout = model.layout
        stacked = np.stack([chain.draws for chain in chains])
        diagnostics = [
            diagnose_parameter(names[column], stacked[:, :, column])
            for column in range(model.dimension)
        ]
        key_columns = (
            [layout.alpha]
            + list(range(layout.beta.start, layout.beta.stop))
            + list(range(layout.log_sigma.start, layout.log_sigma.stop))
            + [layout.log_dispersion]
            + ([layout.dispersion_slope] if model.measure.value == "fill" else [])
        )
        group_diagnostics = {
            name: tuple(diagnostics[layout.z(group)]) for group, name in enumerate(GROUPS)
        }
        finite = [item for item in diagnostics if not math.isnan(item.rhat)]
        worst = sorted(finite, key=lambda item: (-item.rhat, item.ess_bulk))[:12]
        health = SamplerHealth(
            chains=len(chains),
            draws_per_chain=self._settings.draws,
            divergences=int(sum(int(chain.divergent.sum()) for chain in chains)),
            max_tree_depth_hits=int(
                sum(
                    int((chain.tree_depth >= self._settings.max_tree_depth).sum())
                    for chain in chains
                )
            ),
            ebfmi=tuple(ebfmi(chain.energy) for chain in chains),
            step_sizes=tuple(chain.step_size for chain in chains),
            mean_accept=tuple(float(chain.accept_stat.mean()) for chain in chains),
            max_rhat=max(item.rhat for item in finite) if finite else math.nan,
            min_ess_bulk=min(item.ess_bulk for item in finite) if finite else math.nan,
            min_ess_tail=min(item.ess_tail for item in finite) if finite else math.nan,
            share_rhat_ok=(
                sum(1 for item in finite if item.rhat < 1.01) / len(finite) if finite else 0.0
            ),
            worst_parameters=tuple(worst),
        )
        return PosteriorFit(
            model=model,
            settings=self._settings,
            chains=chains,
            health=health,
            key_parameters=tuple(diagnostics[column] for column in key_columns),
            group_diagnostics=group_diagnostics,
        )
