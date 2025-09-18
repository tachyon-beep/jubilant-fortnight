from pathlib import Path

from great_work.rng import DeterministicRNG
from great_work.scholars import ScholarRepository


def test_deterministic_generation(tmp_path: Path) -> None:
    repo = ScholarRepository()
    rng = DeterministicRNG(1234)
    scholar_a = repo.generate(rng, "s.dynamic-1")
    rng = DeterministicRNG(1234)
    scholar_b = repo.generate(rng, "s.dynamic-1")
    assert scholar_a.name == scholar_b.name
    assert scholar_a.stats == scholar_b.stats
    assert scholar_a.politics == scholar_b.politics
