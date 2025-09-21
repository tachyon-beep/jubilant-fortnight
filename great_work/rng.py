"""Deterministic random utilities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterator


@dataclass
class SeedSequence:
    """Deterministic seed sequence built from campaign and counter."""

    campaign_seed: int
    counter: int = 0

    def spawn(self, index: int | None = None) -> "SeedSequence":
        if index is None:
            index = self.counter
            self.counter += 1
        return SeedSequence((self.campaign_seed ^ (index * 0x9E3779B9)) & 0xFFFFFFFF, 0)

    def random(self) -> random.Random:
        return random.Random(
            (self.campaign_seed ^ (self.counter * 0x9E3779B9)) & 0xFFFFFFFF
        )


class DeterministicRNG:
    """Wraps :mod:`random` with deterministic replay support."""

    def __init__(self, seed: int) -> None:
        self._seed = seed & 0xFFFFFFFF
        # nosec B311 - deterministic pseudo-RNG acceptable for game mechanics
        self._random = random.Random(self._seed)

    @property
    def seed(self) -> int:
        return self._seed

    def choice(self, seq):
        return self._random.choice(seq)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        return self._random.randrange(start, stop, step)

    def uniform(self, a: float, b: float) -> float:
        return self._random.uniform(a, b)

    def shuffle(self, seq) -> None:
        self._random.shuffle(seq)

    def sample(self, population, k: int):
        return self._random.sample(population, k)

    def roll_d100(self) -> int:
        return self._random.randint(1, 100)

    def stream(self) -> Iterator[float]:
        while True:
            yield self._random.random()


__all__ = ["DeterministicRNG", "SeedSequence"]
