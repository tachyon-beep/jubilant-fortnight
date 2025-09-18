"""Tests for deterministic random number generation."""
from __future__ import annotations

import pytest

from great_work.rng import DeterministicRNG, SeedSequence


def test_deterministic_rng_reproducibility():
    """DeterministicRNG should produce the same sequence for the same seed."""
    seed = 42

    rng1 = DeterministicRNG(seed)
    rng2 = DeterministicRNG(seed)

    # Generate sequences from both
    sequence1 = [rng1.randint(0, 100) for _ in range(10)]
    sequence2 = [rng2.randint(0, 100) for _ in range(10)]

    assert sequence1 == sequence2


def test_deterministic_rng_different_seeds():
    """Different seeds should produce different sequences."""
    rng1 = DeterministicRNG(42)
    rng2 = DeterministicRNG(43)

    sequence1 = [rng1.randint(0, 100) for _ in range(10)]
    sequence2 = [rng2.randint(0, 100) for _ in range(10)]

    assert sequence1 != sequence2


def test_deterministic_rng_seed_property():
    """Seed property should return the masked seed value."""
    seed = 0x12345678ABCDEF
    rng = DeterministicRNG(seed)

    # Should be masked to 32 bits
    assert rng.seed == (seed & 0xFFFFFFFF)


def test_deterministic_rng_choice():
    """Choice method should work deterministically."""
    rng = DeterministicRNG(100)
    options = ["A", "B", "C", "D", "E"]

    # Should produce same sequence
    choices1 = [rng.choice(options) for _ in range(5)]

    rng2 = DeterministicRNG(100)
    choices2 = [rng2.choice(options) for _ in range(5)]

    assert choices1 == choices2
    assert all(c in options for c in choices1)


def test_deterministic_rng_uniform():
    """Uniform method should generate values in range deterministically."""
    rng = DeterministicRNG(200)

    values = [rng.uniform(0.0, 1.0) for _ in range(10)]

    # All values should be in range
    assert all(0.0 <= v <= 1.0 for v in values)

    # Should be reproducible
    rng2 = DeterministicRNG(200)
    values2 = [rng2.uniform(0.0, 1.0) for _ in range(10)]
    assert values == values2


def test_deterministic_rng_shuffle():
    """Shuffle should reorder list deterministically."""
    rng1 = DeterministicRNG(300)
    rng2 = DeterministicRNG(300)

    list1 = list(range(10))
    list2 = list(range(10))

    rng1.shuffle(list1)
    rng2.shuffle(list2)

    # Should produce same shuffle
    assert list1 == list2

    # Should actually shuffle (not remain in original order)
    assert list1 != list(range(10))


def test_deterministic_rng_sample():
    """Sample should select items deterministically without replacement."""
    rng = DeterministicRNG(400)
    population = list(range(20))

    sample1 = rng.sample(population, 5)

    # Should have correct size
    assert len(sample1) == 5

    # Should have no duplicates
    assert len(set(sample1)) == 5

    # Should be reproducible
    rng2 = DeterministicRNG(400)
    sample2 = rng2.sample(population, 5)
    assert sample1 == sample2


def test_deterministic_rng_roll_d100():
    """roll_d100 should generate values between 1 and 100."""
    rng = DeterministicRNG(500)

    rolls = [rng.roll_d100() for _ in range(100)]

    # All values should be in valid d100 range
    assert all(1 <= roll <= 100 for roll in rolls)

    # Should have reasonable distribution (not all same value)
    assert len(set(rolls)) > 10


def test_deterministic_rng_stream():
    """Stream should generate infinite sequence of floats."""
    rng = DeterministicRNG(600)
    stream = rng.stream()

    # Get first 10 values
    values = [next(stream) for _ in range(10)]

    # All should be in [0, 1) range
    assert all(0.0 <= v < 1.0 for v in values)

    # Should be reproducible
    rng2 = DeterministicRNG(600)
    stream2 = rng2.stream()
    values2 = [next(stream2) for _ in range(10)]
    assert values == values2

    # Stream should continue generating values
    more_values = [next(stream) for _ in range(10)]
    assert len(more_values) == 10
    assert more_values != values  # Should be different from first batch


def test_deterministic_rng_randrange():
    """randrange should work like Python's random.randrange."""
    rng = DeterministicRNG(700)

    # Test with stop only
    values = [rng.randrange(10) for _ in range(10)]
    assert all(0 <= v < 10 for v in values)

    # Test with start and stop
    values = [rng.randrange(5, 15) for _ in range(10)]
    assert all(5 <= v < 15 for v in values)

    # Test with step
    values = [rng.randrange(0, 20, 5) for _ in range(10)]
    assert all(v in [0, 5, 10, 15] for v in values)


def test_seed_sequence_spawn_default():
    """SeedSequence.spawn() without index should increment counter."""
    seq = SeedSequence(campaign_seed=1000)

    child1 = seq.spawn()
    child2 = seq.spawn()
    child3 = seq.spawn()

    # Each spawn should have different seed
    assert child1.campaign_seed != child2.campaign_seed
    assert child2.campaign_seed != child3.campaign_seed

    # Counter should increment
    assert seq.counter == 3


def test_seed_sequence_spawn_with_index():
    """SeedSequence.spawn(index) should use specific index."""
    seq = SeedSequence(campaign_seed=2000)

    child_5 = seq.spawn(5)
    child_10 = seq.spawn(10)
    child_5_again = seq.spawn(5)

    # Same index should produce same seed
    assert child_5.campaign_seed == child_5_again.campaign_seed

    # Different indices should produce different seeds
    assert child_5.campaign_seed != child_10.campaign_seed

    # Counter should not change when index provided
    assert seq.counter == 0


def test_seed_sequence_random():
    """SeedSequence.random() should create Random instance with derived seed."""
    seq = SeedSequence(campaign_seed=3000)

    rng1 = seq.random()

    # Counter doesn't increment for random() method
    assert seq.counter == 0

    # Should produce deterministic values
    values1 = [rng1.randint(0, 100) for _ in range(5)]

    # Create another sequence with same campaign seed
    seq2 = SeedSequence(campaign_seed=3000)
    rng2 = seq2.random()
    values2 = [rng2.randint(0, 100) for _ in range(5)]

    # Should produce same sequence
    assert values1 == values2


def test_seed_sequence_campaign_seed_masking():
    """Campaign seed should be properly masked to 32 bits."""
    large_seed = 0xFFFFFFFFFFFFFFFF
    seq = SeedSequence(campaign_seed=large_seed)

    # Check that the campaign seed was stored (may not be masked in storage)
    # But operations should produce valid 32-bit results
    child = seq.spawn(0)

    # The XOR operation should work and produce valid result
    # Verify it doesn't overflow or cause issues
    assert isinstance(child.campaign_seed, int)
    assert 0 <= child.campaign_seed <= 0xFFFFFFFF


def test_seed_sequence_xor_mixing():
    """Seed mixing should use XOR with golden ratio constant."""
    seq = SeedSequence(campaign_seed=4000)

    # The constant 0x9E3779B9 is derived from golden ratio
    # Used for good bit mixing properties
    child1 = seq.spawn(1)
    expected_seed = (4000 ^ (1 * 0x9E3779B9)) & 0xFFFFFFFF

    assert child1.campaign_seed == expected_seed


def test_deterministic_rng_large_seed():
    """DeterministicRNG should handle large seeds correctly."""
    large_seed = 2**40 + 12345
    rng = DeterministicRNG(large_seed)

    # Should mask to 32 bits
    assert rng.seed == (large_seed & 0xFFFFFFFF)

    # Should still work correctly
    values = [rng.randint(0, 10) for _ in range(5)]
    assert all(0 <= v <= 10 for v in values)