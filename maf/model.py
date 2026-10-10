from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import digamma, expit, gammaln

from maf.design import GROUPS, ModelData
from maf.records import Measure
from maf.zerosum import ZeroSumTransform

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class PriorSettings:
    intercept_sd: float = 2.0
    coefficient_sd: float = 1.0
    sigma_scale: float = 1.0
    fill_log_precision_mean: float = math.log(15.0)
    count_log_shape_mean: float = math.log(5.0)
    dispersion_sd: float = 1.5
    centered_min_per_level: float = 25.0
    centered_min_levels: int = 10
    fixed_effect_sd: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {
            "intercept_sd": self.intercept_sd,
            "coefficient_sd": self.coefficient_sd,
            "sigma_scale": self.sigma_scale,
            "fill_log_precision_mean": self.fill_log_precision_mean,
            "count_log_shape_mean": self.count_log_shape_mean,
            "dispersion_sd": self.dispersion_sd,
            "centered_min_per_level": self.centered_min_per_level,
            "centered_min_levels": self.centered_min_levels,
            "fixed_effect_sd": self.fixed_effect_sd,
        }


@dataclass(frozen=True)
class ParameterLayout:
    n_features: int
    group_sizes: tuple[int, ...]

    @property
    def n_groups(self) -> int:
        return len(self.group_sizes)

    @property
    def alpha(self) -> int:
        return 0

    @property
    def beta(self) -> slice:
        return slice(1, 1 + self.n_features)

    @property
    def log_sigma(self) -> slice:
        start = 1 + self.n_features
        return slice(start, start + self.n_groups)

    @property
    def log_dispersion(self) -> int:
        return 1 + self.n_features + self.n_groups

    @property
    def dispersion_slope(self) -> int:
        return 2 + self.n_features + self.n_groups

    def z(self, group: int) -> slice:
        start = 3 + self.n_features + self.n_groups + sum(self.group_sizes[:group])
        return slice(start, start + self.group_sizes[group])

    @property
    def dimension(self) -> int:
        return 3 + self.n_features + self.n_groups + sum(self.group_sizes)


class HierarchicalAttendanceModel:
    def __init__(self, data: ModelData, priors: PriorSettings | None = None) -> None:
        self.data = data
        self.priors = priors or PriorSettings()
        self.measure = data.measure
        self.transforms = tuple(ZeroSumTransform(data.blocks(name)) for name in GROUPS)
        self.layout = ParameterLayout(
            n_features=data.features.shape[1],
            group_sizes=tuple(transform.n_free for transform in self.transforms),
        )
        self._y = data.spectators.astype(np.float64)
        self._capacity = data.capacity.astype(np.float64)
        self._x = data.features
        self._index = [data.groups[name] for name in GROUPS]
        self.modes = tuple(self._mode(transform) for transform in self.transforms)
        self.centered = tuple(mode != "noncentered" for mode in self.modes)
        self.intercept_mean = self._empirical_intercept()
        self.dispersion_mean = (
            self.priors.fill_log_precision_mean
            if self.measure is Measure.FILL
            else self.priors.count_log_shape_mean
        )
        self._constant = self._likelihood_constant()
        if self.measure is Measure.FILL:
            log_capacity = np.log(np.maximum(self._capacity, 1.0))
            self.capacity_log_mean = float(np.mean(log_capacity))
            self.capacity_log_sd = float(np.std(log_capacity)) or 1.0
            self._dispersion_covariate = (
                log_capacity - self.capacity_log_mean
            ) / self.capacity_log_sd
        else:
            self.capacity_log_mean = 0.0
            self.capacity_log_sd = 1.0
            self._dispersion_covariate = np.zeros_like(self._y)

    @property
    def dimension(self) -> int:
        return self.layout.dimension

    def _mode(self, transform: ZeroSumTransform) -> str:
        if transform.n_free < self.priors.centered_min_levels:
            return "fixed"
        if self.data.size / max(transform.n_levels, 1) >= self.priors.centered_min_per_level:
            return "centered"
        return "noncentered"

    def _empirical_intercept(self) -> float:
        if self.measure is Measure.FILL:
            share = float(np.clip(np.mean(self._y / self._capacity), 0.02, 0.98))
            return math.log(share / (1.0 - share))
        return math.log(max(float(np.mean(self._y)), 1.0))

    def _likelihood_constant(self) -> float:
        if self.measure is Measure.FILL:
            return float(
                np.sum(
                    gammaln(self._capacity + 1.0)
                    - gammaln(self._y + 1.0)
                    - gammaln(self._capacity - self._y + 1.0)
                )
            )
        return float(-np.sum(gammaln(self._y + 1.0)))

    def initial_point(self, rng: np.random.Generator) -> FloatArray:
        theta = np.zeros(self.dimension, dtype=np.float64)
        layout = self.layout
        theta[layout.alpha] = self.intercept_mean + rng.uniform(-0.5, 0.5)
        theta[layout.beta] = rng.uniform(-0.2, 0.2, size=layout.n_features)
        theta[layout.log_sigma] = math.log(0.3) + rng.uniform(-0.5, 0.5, size=layout.n_groups)
        theta[layout.log_dispersion] = self.dispersion_mean + rng.uniform(-0.5, 0.5)
        theta[layout.dispersion_slope] = rng.uniform(-0.2, 0.2)
        for group in range(layout.n_groups):
            scale = 0.15 if self.centered[group] else 0.5
            theta[layout.z(group)] = rng.uniform(-scale, scale, size=layout.group_sizes[group])
        return theta

    def row_dispersion(
        self, log_dispersion: FloatArray, slope: FloatArray, capacity: FloatArray
    ) -> FloatArray:
        if self.measure is not Measure.FILL:
            return np.asarray(np.exp(log_dispersion)[:, None] * np.ones_like(capacity)[None, :])
        covariate = (
            np.log(np.maximum(capacity, 1.0)) - self.capacity_log_mean
        ) / self.capacity_log_sd
        return np.asarray(np.exp(log_dispersion[:, None] + slope[:, None] * covariate[None, :]))

    def linear_predictor(self, theta: FloatArray) -> FloatArray:
        layout = self.layout
        eta = theta[layout.alpha] + self._x @ theta[layout.beta]
        sigmas = np.exp(theta[layout.log_sigma])
        for group in range(layout.n_groups):
            factor = 1.0 if self.centered[group] else sigmas[group]
            effects = self.transforms[group].forward(factor * theta[layout.z(group)])
            eta = eta + effects[self._index[group]]
        return np.asarray(eta, dtype=np.float64)

    def log_likelihood_terms(
        self, eta: FloatArray, log_dispersion: FloatArray
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        y = self._y
        if self.measure is Measure.FILL:
            phi = np.exp(log_dispersion)
            mu = np.clip(expit(eta), 1e-12, 1.0 - 1e-12)
            a = mu * phi
            b = (1.0 - mu) * phi
            n = self._capacity
            log_lik = (
                gammaln(y + a)
                + gammaln(n - y + b)
                - gammaln(n + phi)
                - gammaln(a)
                - gammaln(b)
                + gammaln(phi)
            )
            psi_a = digamma(y + a) - digamma(a)
            psi_b = digamma(n - y + b) - digamma(b)
            d_eta = phi * mu * (1.0 - mu) * (psi_a - psi_b)
            d_log_dispersion = phi * (
                mu * psi_a + (1.0 - mu) * psi_b - digamma(n + phi) + digamma(phi)
            )
            return log_lik, d_eta, d_log_dispersion
        kappa = np.exp(log_dispersion)
        mu = np.exp(np.clip(eta, -30.0, 30.0))
        log_ratio = np.log(kappa) - np.log(kappa + mu)
        log_lik = (
            gammaln(y + kappa)
            - gammaln(kappa)
            + kappa * log_ratio
            + y * (np.log(mu) - np.log(kappa + mu))
        )
        d_eta = kappa * (y - mu) / (kappa + mu)
        d_log_dispersion = kappa * (
            digamma(y + kappa) - digamma(kappa) + log_ratio + 1.0 - (y + kappa) / (kappa + mu)
        )
        return log_lik, d_eta, d_log_dispersion

    def logp_and_grad(self, theta: FloatArray) -> tuple[float, FloatArray]:
        layout = self.layout
        priors = self.priors
        grad = np.zeros_like(theta)
        eta = self.linear_predictor(theta)
        log_dispersion = float(theta[layout.log_dispersion])
        slope = float(theta[layout.dispersion_slope])
        log_lik, d_eta, d_disp = self.log_likelihood_terms(
            eta, log_dispersion + slope * self._dispersion_covariate
        )
        total = float(np.sum(log_lik)) + self._constant
        if not math.isfinite(total):
            return -math.inf, grad
        alpha = float(theta[layout.alpha])
        total -= 0.5 * ((alpha - self.intercept_mean) / priors.intercept_sd) ** 2
        grad[layout.alpha] = float(np.sum(d_eta)) - (alpha - self.intercept_mean) / (
            priors.intercept_sd**2
        )
        beta = theta[layout.beta]
        total -= 0.5 * float(np.sum((beta / priors.coefficient_sd) ** 2))
        grad[layout.beta] = self._x.T @ d_eta - beta / priors.coefficient_sd**2
        log_sigma = theta[layout.log_sigma]
        sigmas = np.exp(log_sigma)
        grad_log_sigma = np.zeros(layout.n_groups, dtype=np.float64)
        for group in range(layout.n_groups):
            z = theta[layout.z(group)]
            index = self._index[group]
            transform = self.transforms[group]
            summed = transform.backward(
                np.bincount(index, weights=d_eta, minlength=transform.n_levels)
            )
            if self.modes[group] == "fixed":
                variance = priors.fixed_effect_sd**2
                grad[layout.z(group)] = summed - z / variance
                total -= 0.5 * float(np.dot(z, z)) / variance
            elif self.centered[group]:
                variance = sigmas[group] ** 2
                squares = float(np.dot(z, z))
                grad[layout.z(group)] = summed - z / variance
                grad_log_sigma[group] = squares / variance - z.size
                total -= 0.5 * squares / variance + z.size * float(log_sigma[group])
            else:
                grad[layout.z(group)] = sigmas[group] * summed - z
                grad_log_sigma[group] = sigmas[group] * float(np.dot(summed, z))
                total -= 0.5 * float(np.dot(z, z))
        total += float(np.sum(-0.5 * (sigmas / priors.sigma_scale) ** 2 + log_sigma))
        grad[layout.log_sigma] = grad_log_sigma - sigmas**2 / priors.sigma_scale**2 + 1.0
        total -= 0.5 * ((log_dispersion - self.dispersion_mean) / priors.dispersion_sd) ** 2
        grad[layout.log_dispersion] = float(np.sum(d_disp)) - (
            log_dispersion - self.dispersion_mean
        ) / (priors.dispersion_sd**2)
        total -= 0.5 * slope**2
        grad[layout.dispersion_slope] = float(np.dot(d_disp, self._dispersion_covariate)) - slope
        if not np.all(np.isfinite(grad)):
            return -math.inf, np.zeros_like(theta)
        return total, grad

    def unpack(self, draws: FloatArray) -> dict[str, FloatArray]:
        layout = self.layout
        sigmas = np.exp(draws[:, layout.log_sigma])
        result: dict[str, FloatArray] = {
            "alpha": draws[:, layout.alpha].copy(),
            "beta": draws[:, layout.beta].copy(),
            "sigma": sigmas,
            "dispersion": np.exp(draws[:, layout.log_dispersion]),
            "dispersion_slope": draws[:, layout.dispersion_slope].copy(),
        }
        for group, name in enumerate(GROUPS):
            values = draws[:, layout.z(group)]
            if not self.centered[group]:
                values = values * sigmas[:, group : group + 1]
            result[name] = self.transforms[group].forward(values)
        return result

    def parameter_names(self) -> list[str]:
        layout = self.layout
        names = ["alpha"]
        names += [f"beta[{index}]" for index in range(layout.n_features)]
        names += [f"log_sigma[{name}]" for name in GROUPS]
        names.append("log_dispersion")
        names.append("dispersion_slope")
        for group, name in enumerate(GROUPS):
            prefix = {"fixed": "f", "centered": "u", "noncentered": "z"}[self.modes[group]]
            names += [f"{prefix}_{name}[{index}]" for index in range(layout.group_sizes[group])]
        return names
