from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import ndtri
from scipy.stats import rankdata

FloatArray = NDArray[np.float64]

RHAT_THRESHOLD = 1.01
ESS_THRESHOLD = 400.0
EBFMI_THRESHOLD = 0.3


def split_chains(draws: FloatArray) -> FloatArray:
    chains, size = draws.shape
    half = size // 2
    return np.concatenate([draws[:, :half], draws[:, size - half :]], axis=0)


def z_scale(draws: FloatArray) -> FloatArray:
    flat = draws.reshape(-1)
    ranks = rankdata(flat, method="average")
    scaled = ndtri((ranks - 0.375) / (flat.size + 0.25))
    return np.asarray(scaled.reshape(draws.shape), dtype=np.float64)


def basic_rhat(draws: FloatArray) -> float:
    chains, size = draws.shape
    if size < 2 or chains < 2:
        return math.nan
    chain_means = draws.mean(axis=1)
    chain_vars = draws.var(axis=1, ddof=1)
    within = float(chain_vars.mean())
    between = size * float(chain_means.var(ddof=1))
    if within <= 0.0:
        return 1.0 if between <= 0.0 else math.inf
    var_plus = (size - 1) / size * within + between / size
    return math.sqrt(var_plus / within)


def rank_normalized_rhat(draws: FloatArray) -> float:
    split = split_chains(draws)
    if np.ptp(split) == 0.0:
        return 1.0
    bulk = basic_rhat(z_scale(split))
    folded = np.abs(split - np.median(split))
    tail = basic_rhat(z_scale(folded))
    return float(max(bulk, tail))


def _autocovariance(series: FloatArray) -> FloatArray:
    size = series.shape[-1]
    centered = series - series.mean(axis=-1, keepdims=True)
    length = 1 << (2 * size - 1).bit_length()
    transformed = np.fft.rfft(centered, n=length, axis=-1)
    result = np.fft.irfft(transformed * np.conjugate(transformed), n=length, axis=-1)[..., :size]
    return np.asarray(result / size, dtype=np.float64)


def basic_ess(draws: FloatArray) -> float:
    chains, size = draws.shape
    if size < 4:
        return math.nan
    if np.ptp(draws) == 0.0:
        return float(chains * size)
    acov = _autocovariance(draws)
    chain_means = draws.mean(axis=1)
    mean_var = float(np.mean(acov[:, 0])) * size / (size - 1.0)
    var_plus = mean_var * (size - 1.0) / size
    if chains > 1:
        var_plus += float(np.var(chain_means, ddof=1))
    rho_hat = np.zeros(size)
    rho_hat_even = 1.0
    rho_hat[0] = rho_hat_even
    rho_hat_odd = 1.0 - (mean_var - float(np.mean(acov[:, 1]))) / var_plus
    rho_hat[1] = rho_hat_odd
    t = 1
    while t < size - 3 and (rho_hat_even + rho_hat_odd) > 0.0:
        rho_hat_even = 1.0 - (mean_var - float(np.mean(acov[:, t + 1]))) / var_plus
        rho_hat_odd = 1.0 - (mean_var - float(np.mean(acov[:, t + 2]))) / var_plus
        if rho_hat_even + rho_hat_odd >= 0.0:
            rho_hat[t + 1] = rho_hat_even
            rho_hat[t + 2] = rho_hat_odd
        t += 2
    max_t = t - 2
    if rho_hat_even > 0.0:
        rho_hat[max_t + 1] = rho_hat_even
    t = 1
    while t <= max_t - 2:
        if rho_hat[t + 1] + rho_hat[t + 2] > rho_hat[t - 1] + rho_hat[t]:
            rho_hat[t + 1] = (rho_hat[t - 1] + rho_hat[t]) / 2.0
            rho_hat[t + 2] = rho_hat[t + 1]
        t += 2
    total = chains * size
    tau = (
        -1.0
        + 2.0 * float(np.sum(rho_hat[: max_t + 1]))
        + float(np.sum(rho_hat[max_t + 1 : max_t + 2]))
    )
    tau = max(tau, 1.0 / math.log10(total))
    return float(total / tau)


def ess_bulk(draws: FloatArray) -> float:
    return basic_ess(z_scale(split_chains(draws)))


def ess_tail(draws: FloatArray) -> float:
    split = split_chains(draws)
    lower = np.quantile(split, 0.05)
    upper = np.quantile(split, 0.95)
    return float(
        min(
            basic_ess((split <= lower).astype(np.float64)),
            basic_ess((split <= upper).astype(np.float64)),
        )
    )


def ebfmi(energy: FloatArray) -> float:
    differences = np.diff(energy)
    denominator = float(np.var(energy))
    if denominator <= 0.0:
        return math.nan
    return float(np.mean(differences**2) / denominator)


@dataclass(frozen=True)
class ParameterDiagnostic:
    name: str
    mean: float
    sd: float
    q025: float
    q50: float
    q975: float
    rhat: float
    ess_bulk: float
    ess_tail: float
    mcse_mean: float

    def as_dict(self) -> dict[str, float | str]:
        return {
            "name": self.name,
            "mean": self.mean,
            "sd": self.sd,
            "q025": self.q025,
            "q50": self.q50,
            "q975": self.q975,
            "rhat": self.rhat,
            "ess_bulk": self.ess_bulk,
            "ess_tail": self.ess_tail,
            "mcse_mean": self.mcse_mean,
        }


def diagnose_parameter(name: str, draws: FloatArray) -> ParameterDiagnostic:
    flat = draws.reshape(-1)
    bulk = ess_bulk(draws)
    sd = float(np.std(flat, ddof=1))
    return ParameterDiagnostic(
        name=name,
        mean=float(np.mean(flat)),
        sd=sd,
        q025=float(np.quantile(flat, 0.025)),
        q50=float(np.quantile(flat, 0.5)),
        q975=float(np.quantile(flat, 0.975)),
        rhat=rank_normalized_rhat(draws),
        ess_bulk=bulk,
        ess_tail=ess_tail(draws),
        mcse_mean=sd / math.sqrt(bulk) if bulk and bulk > 0 else math.nan,
    )


@dataclass(frozen=True)
class SamplerHealth:
    chains: int
    draws_per_chain: int
    divergences: int
    max_tree_depth_hits: int
    ebfmi: tuple[float, ...]
    step_sizes: tuple[float, ...]
    mean_accept: tuple[float, ...]
    max_rhat: float
    min_ess_bulk: float
    min_ess_tail: float
    share_rhat_ok: float
    worst_parameters: tuple[ParameterDiagnostic, ...]

    @property
    def status(self) -> str:
        converged = self.max_rhat < RHAT_THRESHOLD and self.min_ess_bulk >= ESS_THRESHOLD
        clean = self.divergences == 0 and all(
            value >= EBFMI_THRESHOLD for value in self.ebfmi if not math.isnan(value)
        )
        if converged and clean and self.min_ess_tail >= ESS_THRESHOLD:
            return "ok"
        if (
            self.max_rhat < 1.05
            and self.min_ess_bulk >= 100
            and self.divergences <= max(1, int(0.002 * self.chains * self.draws_per_chain))
        ):
            return "ostrzezenie"
        return "niewiarygodny"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "chains": self.chains,
            "draws_per_chain": self.draws_per_chain,
            "divergences": self.divergences,
            "max_tree_depth_hits": self.max_tree_depth_hits,
            "ebfmi": list(self.ebfmi),
            "step_sizes": list(self.step_sizes),
            "mean_accept": list(self.mean_accept),
            "max_rhat": self.max_rhat,
            "min_ess_bulk": self.min_ess_bulk,
            "min_ess_tail": self.min_ess_tail,
            "share_rhat_ok": self.share_rhat_ok,
            "thresholds": {
                "rhat": RHAT_THRESHOLD,
                "ess": ESS_THRESHOLD,
                "ebfmi": EBFMI_THRESHOLD,
            },
            "worst_parameters": [item.as_dict() for item in self.worst_parameters],
        }
