from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
LogDensity = Callable[[FloatArray], tuple[float, FloatArray]]


@dataclass(frozen=True)
class SamplerSettings:
    chains: int = 4
    warmup: int = 1000
    draws: int = 1000
    target_accept: float = 0.9
    max_tree_depth: int = 10
    max_delta_h: float = 1000.0
    seed: int = 20261010
    thin_store: int = 4

    def as_dict(self) -> dict[str, float | int]:
        return {
            "chains": self.chains,
            "warmup": self.warmup,
            "draws": self.draws,
            "target_accept": self.target_accept,
            "max_tree_depth": self.max_tree_depth,
            "max_delta_h": self.max_delta_h,
            "seed": self.seed,
            "thin_store": self.thin_store,
        }


@dataclass
class _State:
    theta: FloatArray
    momentum: FloatArray
    grad: FloatArray
    logp: float


@dataclass
class _Subtree:
    sample: _State
    log_sum_weight: float
    rho: FloatArray
    p_sharp_begin: FloatArray
    p_sharp_end: FloatArray
    p_begin: FloatArray
    p_end: FloatArray
    edge: _State
    valid: bool


@dataclass
class ChainResult:
    draws: FloatArray
    step_size: float
    inverse_metric: FloatArray
    accept_stat: FloatArray
    tree_depth: NDArray[np.int64]
    n_leapfrog: NDArray[np.int64]
    divergent: NDArray[np.bool_]
    energy: FloatArray
    logp: FloatArray


@dataclass
class _DualAveraging:
    target: float
    mu: float
    gamma: float = 0.05
    t0: float = 10.0
    kappa: float = 0.75
    counter: int = 0
    s_bar: float = 0.0
    x_bar: float = 0.0

    def restart(self, step_size: float) -> None:
        self.mu = math.log(10.0 * step_size)
        self.counter = 0
        self.s_bar = 0.0
        self.x_bar = 0.0

    def update(self, accept_stat: float) -> float:
        self.counter += 1
        accept_stat = min(1.0, accept_stat)
        eta = 1.0 / (self.counter + self.t0)
        self.s_bar = (1.0 - eta) * self.s_bar + eta * (self.target - accept_stat)
        x = self.mu - self.s_bar * math.sqrt(self.counter) / self.gamma
        x_eta = self.counter ** (-self.kappa)
        self.x_bar = (1.0 - x_eta) * self.x_bar + x_eta * x
        return math.exp(x)

    def final(self) -> float:
        return math.exp(self.x_bar)


@dataclass
class _Welford:
    size: int
    count: int = 0
    mean: FloatArray = field(init=False)
    m2: FloatArray = field(init=False)

    def __post_init__(self) -> None:
        self.mean = np.zeros(self.size)
        self.m2 = np.zeros(self.size)

    def add(self, value: FloatArray) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean = self.mean + delta / self.count
        self.m2 = self.m2 + delta * (value - self.mean)

    def regularized_variance(self) -> FloatArray:
        n = self.count
        variance = self.m2 / max(n - 1, 1)
        return np.asarray((n / (n + 5.0)) * variance + 1e-3 * (5.0 / (n + 5.0)), dtype=np.float64)


def adaptation_windows(warmup: int) -> list[int]:
    init_buffer, term_buffer, base_window = 75, 50, 25
    if warmup < 20:
        return []
    if init_buffer + base_window + term_buffer > warmup:
        init_buffer = int(0.15 * warmup)
        term_buffer = int(0.1 * warmup)
        base_window = warmup - init_buffer - term_buffer
    ends: list[int] = []
    start = init_buffer
    size = base_window
    limit = warmup - term_buffer
    while start < limit:
        end = start + size
        next_end = end + 2 * size
        if next_end > limit:
            end = limit
        ends.append(end)
        start = end
        size *= 2
    return ends


class NutsSampler:
    def __init__(self, log_density: LogDensity, dimension: int, settings: SamplerSettings) -> None:
        self._log_density = log_density
        self._dimension = dimension
        self._settings = settings

    def sample_chain(self, initial: FloatArray, seed: int) -> ChainResult:
        settings = self._settings
        rng = np.random.default_rng(seed)
        inverse_metric = np.ones(self._dimension)
        logp, grad = self._log_density(initial)
        if not math.isfinite(logp):
            raise ValueError("punkt startowy ma zerową gęstość posterior")
        state = _State(initial.copy(), np.zeros(self._dimension), grad, logp)
        step_size = self._initial_step_size(state, inverse_metric, rng, 0.1)
        averaging = _DualAveraging(settings.target_accept, math.log(10.0 * step_size))
        window_ends = set(adaptation_windows(settings.warmup))
        windows = sorted(window_ends)
        window_start = 75 if settings.warmup >= 150 else int(0.15 * settings.warmup)
        welford = _Welford(self._dimension)
        total = settings.warmup + settings.draws
        draws = np.zeros((settings.draws, self._dimension))
        accept = np.zeros(settings.draws)
        depths = np.zeros(settings.draws, dtype=np.int64)
        leapfrogs = np.zeros(settings.draws, dtype=np.int64)
        divergent = np.zeros(settings.draws, dtype=bool)
        energy = np.zeros(settings.draws)
        logps = np.zeros(settings.draws)
        for iteration in range(total):
            state, stats = self._transition(state, step_size, inverse_metric, rng)
            if iteration < settings.warmup:
                step_size = averaging.update(stats["accept_stat"])
                if windows and window_start <= iteration < windows[-1]:
                    welford.add(state.theta)
                if iteration + 1 in window_ends:
                    inverse_metric = welford.regularized_variance()
                    welford = _Welford(self._dimension)
                    step_size = self._initial_step_size(state, inverse_metric, rng, step_size)
                    averaging.restart(step_size)
                if iteration + 1 == settings.warmup:
                    step_size = averaging.final()
                continue
            index = iteration - settings.warmup
            draws[index] = state.theta
            accept[index] = stats["accept_stat"]
            depths[index] = int(stats["depth"])
            leapfrogs[index] = int(stats["n_leapfrog"])
            divergent[index] = bool(stats["divergent"])
            energy[index] = stats["energy"]
            logps[index] = state.logp
        return ChainResult(
            draws=draws,
            step_size=step_size,
            inverse_metric=inverse_metric,
            accept_stat=accept,
            tree_depth=depths,
            n_leapfrog=leapfrogs,
            divergent=divergent,
            energy=energy,
            logp=logps,
        )

    def _leapfrog(self, state: _State, step: float, inverse_metric: FloatArray) -> _State:
        momentum = state.momentum + 0.5 * step * state.grad
        theta = state.theta + step * inverse_metric * momentum
        logp, grad = self._log_density(theta)
        momentum = momentum + 0.5 * step * grad
        return _State(theta, momentum, grad, logp)

    @staticmethod
    def _hamiltonian(state: _State, inverse_metric: FloatArray) -> float:
        if not math.isfinite(state.logp):
            return math.inf
        return -state.logp + 0.5 * float(np.dot(state.momentum * inverse_metric, state.momentum))

    def _initial_step_size(
        self,
        state: _State,
        inverse_metric: FloatArray,
        rng: np.random.Generator,
        step_size: float,
    ) -> float:
        momentum = rng.normal(size=self._dimension) / np.sqrt(inverse_metric)
        start = _State(state.theta, momentum, state.grad, state.logp)
        h0 = self._hamiltonian(start, inverse_metric)
        proposal = self._leapfrog(start, step_size, inverse_metric)
        delta = h0 - self._hamiltonian(proposal, inverse_metric)
        direction = 1 if delta > math.log(0.8) else -1
        for _ in range(100):
            momentum = rng.normal(size=self._dimension) / np.sqrt(inverse_metric)
            start = _State(state.theta, momentum, state.grad, state.logp)
            h0 = self._hamiltonian(start, inverse_metric)
            proposal = self._leapfrog(start, step_size, inverse_metric)
            delta = h0 - self._hamiltonian(proposal, inverse_metric)
            if not math.isfinite(delta):
                delta = -math.inf
            if direction == 1 and not delta > math.log(0.8):
                break
            if direction == -1 and not delta < math.log(0.8):
                break
            step_size = step_size * 2.0 if direction == 1 else step_size * 0.5
            if step_size > 1e7 or step_size < 1e-10:
                break
        return step_size

    def _transition(
        self,
        state: _State,
        step_size: float,
        inverse_metric: FloatArray,
        rng: np.random.Generator,
    ) -> tuple[_State, dict[str, float]]:
        momentum = rng.normal(size=self._dimension) / np.sqrt(inverse_metric)
        start = _State(state.theta, momentum, state.grad, state.logp)
        h0 = self._hamiltonian(start, inverse_metric)
        stats = {"sum_accept": 0.0, "n_leapfrog": 0.0, "divergent": 0.0}
        backward = start
        forward = start
        sample = start
        log_sum_weight = 0.0
        p_sharp = inverse_metric * momentum
        left_p, left_p_sharp = momentum, p_sharp
        right_p, right_p_sharp = momentum, p_sharp
        rho = momentum.copy()
        depth = 0
        while depth < self._settings.max_tree_depth:
            go_forward = rng.uniform() > 0.5
            edge = forward if go_forward else backward
            subtree = self._build_tree(
                edge,
                depth,
                step_size if go_forward else -step_size,
                inverse_metric,
                h0,
                rng,
                stats,
            )
            if not subtree.valid:
                break
            depth += 1
            if math.log(rng.uniform()) < subtree.log_sum_weight - log_sum_weight:
                sample = subtree.sample
            log_sum_weight = float(np.logaddexp(log_sum_weight, subtree.log_sum_weight))
            if go_forward:
                persist = _merge_criterion(
                    outer_a=left_p_sharp,
                    inner_a=right_p_sharp,
                    inner_a_p=right_p,
                    rho_a=rho,
                    outer_b=subtree.p_sharp_end,
                    inner_b=subtree.p_sharp_begin,
                    inner_b_p=subtree.p_begin,
                    rho_b=subtree.rho,
                )
                forward = subtree.edge
                right_p, right_p_sharp = subtree.p_end, subtree.p_sharp_end
            else:
                persist = _merge_criterion(
                    outer_a=subtree.p_sharp_end,
                    inner_a=subtree.p_sharp_begin,
                    inner_a_p=subtree.p_begin,
                    rho_a=subtree.rho,
                    outer_b=right_p_sharp,
                    inner_b=left_p_sharp,
                    inner_b_p=left_p,
                    rho_b=rho,
                )
                backward = subtree.edge
                left_p, left_p_sharp = subtree.p_end, subtree.p_sharp_end
            rho = rho + subtree.rho
            if not persist:
                break
        n_leapfrog = max(stats["n_leapfrog"], 1.0)
        result = {
            "accept_stat": stats["sum_accept"] / n_leapfrog,
            "n_leapfrog": n_leapfrog,
            "depth": float(depth),
            "divergent": stats["divergent"],
            "energy": self._hamiltonian(
                _State(sample.theta, sample.momentum, sample.grad, sample.logp), inverse_metric
            ),
        }
        return _State(sample.theta, np.zeros_like(momentum), sample.grad, sample.logp), result

    def _build_tree(
        self,
        state: _State,
        depth: int,
        step: float,
        inverse_metric: FloatArray,
        h0: float,
        rng: np.random.Generator,
        stats: dict[str, float],
    ) -> _Subtree:
        if depth == 0:
            proposal = self._leapfrog(state, step, inverse_metric)
            stats["n_leapfrog"] += 1.0
            h = self._hamiltonian(proposal, inverse_metric)
            if not math.isfinite(h):
                h = math.inf
            if h - h0 > self._settings.max_delta_h:
                stats["divergent"] = 1.0
                empty = np.zeros_like(state.momentum)
                return _Subtree(
                    proposal, -math.inf, empty, empty, empty, empty, empty, proposal, False
                )
            log_weight = h0 - h
            stats["sum_accept"] += 1.0 if log_weight > 0 else math.exp(log_weight)
            p_sharp = inverse_metric * proposal.momentum
            return _Subtree(
                sample=proposal,
                log_sum_weight=log_weight,
                rho=proposal.momentum.copy(),
                p_sharp_begin=p_sharp,
                p_sharp_end=p_sharp,
                p_begin=proposal.momentum,
                p_end=proposal.momentum,
                edge=proposal,
                valid=True,
            )
        initial = self._build_tree(state, depth - 1, step, inverse_metric, h0, rng, stats)
        if not initial.valid:
            return initial
        final = self._build_tree(initial.edge, depth - 1, step, inverse_metric, h0, rng, stats)
        if not final.valid:
            return final
        log_sum_weight = float(np.logaddexp(initial.log_sum_weight, final.log_sum_weight))
        sample = initial.sample
        if math.log(rng.uniform()) < final.log_sum_weight - log_sum_weight:
            sample = final.sample
        rho = initial.rho + final.rho
        persist = _criterion(initial.p_sharp_begin, final.p_sharp_end, rho)
        persist = persist and _criterion(
            initial.p_sharp_begin, final.p_sharp_begin, initial.rho + final.p_begin
        )
        persist = persist and _criterion(
            initial.p_sharp_end, final.p_sharp_end, final.rho + initial.p_end
        )
        return _Subtree(
            sample=sample,
            log_sum_weight=log_sum_weight,
            rho=rho,
            p_sharp_begin=initial.p_sharp_begin,
            p_sharp_end=final.p_sharp_end,
            p_begin=initial.p_begin,
            p_end=final.p_end,
            edge=final.edge,
            valid=persist,
        )


def _criterion(p_sharp_minus: FloatArray, p_sharp_plus: FloatArray, rho: FloatArray) -> bool:
    return float(np.dot(p_sharp_plus, rho)) > 0.0 and float(np.dot(p_sharp_minus, rho)) > 0.0


def _merge_criterion(
    *,
    outer_a: FloatArray,
    inner_a: FloatArray,
    inner_a_p: FloatArray,
    rho_a: FloatArray,
    outer_b: FloatArray,
    inner_b: FloatArray,
    inner_b_p: FloatArray,
    rho_b: FloatArray,
) -> bool:
    return (
        _criterion(outer_a, outer_b, rho_a + rho_b)
        and _criterion(outer_a, inner_b, rho_a + inner_b_p)
        and _criterion(inner_a, outer_b, rho_b + inner_a_p)
    )
