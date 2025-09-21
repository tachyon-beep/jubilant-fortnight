from great_work.models import Scholar, ScholarStats
from great_work.scholars import defection_probability


def build_scholar(loyalty: int, integrity: int) -> Scholar:
    return Scholar(
        id="s.test",
        name="Dr Test",
        seed=1,
        archetype="Empiricist",
        disciplines=["Archaeology"],
        methods=["survey and trench"],
        drives=["Truth"],
        virtues=["integrity"],
        vices=["vanity"],
        stats=ScholarStats(
            talent=5,
            reliability=5,
            integrity=integrity,
            theatrics=5,
            loyalty=loyalty,
            risk=3,
        ),
        politics={},
        catchphrase="Show me {evidence} or I am not buying it.",
        taboos=[],
    )


def test_high_loyalty_lowers_probability() -> None:
    loyal = build_scholar(9, 8)
    disloyal = build_scholar(2, 3)
    offer = 0.8
    mistreatment = 0.2
    alignment = 0.1
    plateau = 0.2
    assert defection_probability(
        loyal, offer, mistreatment, alignment, plateau
    ) < defection_probability(disloyal, offer, mistreatment, alignment, plateau)


def test_probability_bounds() -> None:
    scholar = build_scholar(5, 5)
    prob = defection_probability(scholar, 1.0, 1.0, 0.3, 0.4)
    assert 0.0 <= prob <= 1.0
