from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


class ZeroSumTransform:
    def __init__(self, blocks: NDArray[np.int64]) -> None:
        blocks = np.asarray(blocks, dtype=np.int64)
        self.n_levels = int(blocks.size)
        self.order = np.argsort(blocks, kind="stable")
        self.inverse = np.empty_like(self.order)
        self.inverse[self.order] = np.arange(self.n_levels)
        sorted_blocks = blocks[self.order]
        starts = (
            np.r_[0, np.flatnonzero(np.diff(sorted_blocks)) + 1]
            if self.n_levels
            else np.array([], dtype=np.int64)
        )
        ends = np.r_[starts[1:], self.n_levels] if self.n_levels else np.array([], dtype=np.int64)
        self.n_blocks = int(starts.size)
        position = np.zeros(self.n_levels, dtype=np.int64)
        block_start = np.zeros(self.n_levels, dtype=np.int64)
        block_end = np.zeros(self.n_levels, dtype=np.int64)
        for start, end in zip(starts, ends, strict=True):
            position[start:end] = np.arange(1, end - start + 1)
            block_start[start:end] = start
            block_end[start:end] = end
        self.position = position
        self.block_start = block_start
        self.block_end = block_end
        self.is_free = position < (block_end - block_start)
        self.n_free = int(self.is_free.sum())
        safe = np.maximum(position, 1).astype(np.float64)
        self.coefficient = np.where(self.is_free, 1.0 / np.sqrt(safe * (safe + 1.0)), 0.0)

    def forward(self, free: FloatArray) -> FloatArray:
        free = np.asarray(free, dtype=np.float64)
        shape = free.shape[:-1] + (self.n_levels,)
        terms = np.zeros(shape)
        terms[..., self.is_free] = free
        terms = terms * self.coefficient
        reverse = np.cumsum(terms[..., ::-1], axis=-1)[..., ::-1]
        segment_tail = np.take(
            np.concatenate([reverse, np.zeros(shape[:-1] + (1,))], axis=-1), self.block_end, axis=-1
        )
        suffix = reverse - segment_tail
        previous = np.concatenate([np.zeros(shape[:-1] + (1,)), terms[..., :-1]], axis=-1)
        weights = (self.position - 1).astype(np.float64)
        first = self.position == 1
        previous[..., first] = 0.0
        sorted_values = suffix - weights * previous
        return np.asarray(np.take(sorted_values, self.inverse, axis=-1), dtype=np.float64)

    def backward(self, gradient: FloatArray) -> FloatArray:
        gradient = np.asarray(gradient, dtype=np.float64)
        ordered = np.take(gradient, self.order, axis=-1)
        cumulative = np.cumsum(ordered, axis=-1)
        before = np.concatenate([np.zeros(ordered.shape[:-1] + (1,)), cumulative], axis=-1)
        prefix = cumulative - np.take(before, self.block_start, axis=-1)
        following = np.concatenate([ordered[..., 1:], np.zeros(ordered.shape[:-1] + (1,))], axis=-1)
        values = self.coefficient * (prefix - self.position * following)
        return np.asarray(values[..., self.is_free], dtype=np.float64)
