from great_work.expeditions import ExpeditionResolver, FailureTables
from great_work.models import ExpeditionOutcome, ExpeditionPreparation
from great_work.rng import DeterministicRNG


def make_prep(modifier: int) -> ExpeditionPreparation:
    return ExpeditionPreparation(
        think_tank_bonus=modifier,
        expertise_bonus=0,
        site_friction=0,
        political_friction=0,
    )


def test_failure_when_score_below_threshold() -> None:
    resolver = ExpeditionResolver(FailureTables())
    rng = DeterministicRNG(1)
    prep = make_prep(-30)
    result = resolver.resolve(rng, prep, "shallow")
    assert result.outcome == ExpeditionOutcome.FAILURE


def test_success_when_score_high() -> None:
    resolver = ExpeditionResolver(FailureTables())
    rng = DeterministicRNG(99)
    prep = make_prep(20)
    result = resolver.resolve(rng, prep, "deep")
    assert result.outcome in {ExpeditionOutcome.SUCCESS, ExpeditionOutcome.LANDMARK}
