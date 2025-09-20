"""Tests for multi-layer press generation."""
import os
import random
from unittest.mock import Mock

import pytest

from great_work.multi_press import (
    PressDepth,
    PressLayer,
    MultiPressGenerator
)
from great_work.models import (
    Scholar,
    ExpeditionResult,
    ExpeditionOutcome,
    PressRelease
)
from great_work.press import (
    ExpeditionContext,
    OutcomeContext,
    DefectionContext,
    BulletinContext
)


def test_press_depth_determination():
    """Test determining press coverage depth."""
    generator = MultiPressGenerator()

    # Great projects get extensive coverage
    depth = generator.determine_depth("great_project_success")
    assert depth == PressDepth.EXTENSIVE

    # High stakes get extensive coverage
    depth = generator.determine_depth("expedition", confidence_level="stake_my_career")
    assert depth == PressDepth.EXTENSIVE

    # Large reputation changes get breaking coverage
    depth = generator.determine_depth("discovery", reputation_change=15)
    assert depth == PressDepth.BREAKING

    # First-time events get extensive coverage
    depth = generator.determine_depth("theory", is_first_time=True)
    assert depth == PressDepth.EXTENSIVE

    # Medium reputation changes get standard coverage
    depth = generator.determine_depth("expedition", reputation_change=7)
    assert depth == PressDepth.STANDARD

    # Default is minimal
    depth = generator.determine_depth("routine", reputation_change=1)
    assert depth == PressDepth.MINIMAL


def test_generate_expedition_layers():
    """Test generating multi-layer press for expeditions."""
    generator = MultiPressGenerator()

    # Create test contexts
    exp_ctx = ExpeditionContext(
        code="EXP001",
        player="TestPlayer",
        expedition_type="field",
        objective="Test the limits",
        team=["Scholar1", "Scholar2"],
        funding=["Academic"]
    )

    result = ExpeditionResult(
        roll=85,
        modifier=10,
        final_score=95,
        outcome=ExpeditionOutcome.SUCCESS,
        sideways_discovery="Unexpected finding",
        failure_detail=None
    )

    outcome_ctx = OutcomeContext(
        code="EXP001",
        player="TestPlayer",
        expedition_type="field",
        result=result,
        reputation_change=5,
        reactions=["Amazing!", "Incredible!"]
    )

    # Create mock scholars
    scholars = []
    for i in range(1, 6):
        mock_scholar = Mock(spec=Scholar)
        mock_scholar.name = f"Scholar{i}"
        scholars.append(mock_scholar)

    # Generate layers for different depths
    layers_minimal = generator.generate_expedition_layers(
        exp_ctx, outcome_ctx, scholars, PressDepth.MINIMAL
    )
    assert len(layers_minimal) == 2  # Manifesto + report

    layers_standard = generator.generate_expedition_layers(
        exp_ctx, outcome_ctx, scholars, PressDepth.STANDARD
    )
    assert len(layers_standard) > 2  # Additional reactions

    layers_extensive = generator.generate_expedition_layers(
        exp_ctx, outcome_ctx, scholars, PressDepth.EXTENSIVE
    )
    assert len(layers_extensive) > len(layers_standard)

    # Check layer types
    assert layers_minimal[0].type == "research_manifesto"
    assert layers_minimal[1].type == "discovery_report"

    # Check delays are staggered
    delays = [layer.delay_minutes for layer in layers_extensive]
    assert delays[0] == 0  # First is immediate
    assert all(d >= 0 for d in delays)


def test_generate_defection_layers():
    """Test generating multi-layer press for defections."""
    generator = MultiPressGenerator()

    defection_ctx = DefectionContext(
        scholar="Dr. Smith",
        outcome="accepted",
        new_faction="Industry",
        probability=0.75
    )

    scholar = Mock(spec=Scholar)
    scholar.name = "Dr. Smith"

    other_scholars = []
    for i in range(1, 6):
        mock_scholar = Mock(spec=Scholar)
        mock_scholar.name = f"Colleague{i}"
        other_scholars.append(mock_scholar)

    # Generate layers
    layers = generator.generate_defection_layers(
        defection_ctx,
        scholar,
        "Academic",
        other_scholars,
        PressDepth.EXTENSIVE
    )

    # Should have main notice plus reactions and statements
    assert len(layers) > 1
    assert layers[0].type == "defection_notice"
    assert layers[0].delay_minutes == 0

    # Should include colleague reactions
    gossip_layers = [l for l in layers if l.type == "academic_gossip"]
    assert len(gossip_layers) > 0

    # Should include faction statements for extensive coverage
    statement_layers = [l for l in layers if l.type == "faction_statement"]
    assert len(statement_layers) > 0


def test_generate_conference_layers():
    """Test generating multi-layer press for conferences."""
    generator = MultiPressGenerator()

    layers = generator.generate_conference_layers(
        theory="Quantum consciousness",
        confidence="certain",
        outcome="validated",
        participants=["Alice", "Bob", "Charlie"],
        reputation_changes={"Alice": 5, "Bob": -3},
        depth=PressDepth.EXTENSIVE
    )

    # Should have opening bulletin
    assert layers[0].type == "academic_bulletin"
    assert layers[0].delay_minutes == 0

    # Should have debate quotes for non-minimal depth
    gossip_layers = [l for l in layers if l.type == "academic_gossip"]
    assert len(gossip_layers) > 0

    # Should have outcome for extensive depth
    outcome_layers = [l for l in layers if l.type == "conference_outcome"]
    assert len(outcome_layers) > 0


def test_reaction_quote_generation():
    """Test generating scholar reaction quotes."""
    generator = MultiPressGenerator()

    quote = generator._generate_reaction_quote(
        "Dr. Jones",
        "dark matter",
        "success",
        "enthusiasm"
    )
    assert isinstance(quote, str)
    assert len(quote) > 0

    # Test different emotions
    for emotion in ["skepticism", "concern", "admiration", "curiosity"]:
        quote = generator._generate_reaction_quote(
            "Dr. Smith",
            "test objective",
            "failure",
            emotion
        )
        assert isinstance(quote, str)


def test_apply_layers():
    """Test applying press layers to generate releases."""
    generator = MultiPressGenerator()

    # Create mock layers
    immediate_layer = PressLayer(
        delay_minutes=0,
        type="test",
        generator=lambda ctx: PressRelease(
            type="test",
            headline="Immediate",
            body="Immediate release"
        ),
        context={}
    )

    delayed_layer = PressLayer(
        delay_minutes=30,
        type="test",
        generator=lambda ctx: PressRelease(
            type="test",
            headline="Delayed",
            body="Delayed release"
        ),
        context={}
    )

    layers = [immediate_layer, delayed_layer]

    # Test immediate only
    immediate_releases = generator.apply_layers(layers, immediate_only=True)
    assert len(immediate_releases) == 1
    assert immediate_releases[0].headline == "Immediate"

    # Test all layers
    all_releases = generator.apply_layers(layers, immediate_only=False)
    assert len(all_releases) == 2
    assert all_releases[0].headline == "Immediate"
    assert all_releases[1].headline == "Delayed"


def test_find_colleagues():
    """Test finding colleagues of a scholar."""
    generator = MultiPressGenerator()

    main_scholar = Mock(spec=Scholar)
    main_scholar.name = "Main"

    all_scholars = [main_scholar]
    for i in range(1, 4):
        mock_scholar = Mock(spec=Scholar)
        mock_scholar.name = f"Scholar{i}"
        all_scholars.append(mock_scholar)

    colleagues = generator._find_colleagues(main_scholar, all_scholars, max_colleagues=2)

    # Should not include the main scholar
    assert main_scholar not in colleagues
    # Should return requested number or fewer
    assert len(colleagues) <= 2
    # All should be from the scholar list
    assert all(c in all_scholars for c in colleagues)


def test_generate_mentorship_layers_dual_schedule():
    """Mentorship cadence should produce fast gossip and long-form updates."""
    generator = MultiPressGenerator()
    generator.fast_layer_delays = [30, 60]
    generator.long_layer_delays = [720, 1440]

    scholar = Mock(spec=Scholar)
    scholar.name = "Dr. Vega"
    scholar.id = "s.mentor-001"
    scholar.career = {"track": "Academia"}

    layers = generator.generate_mentorship_layers(
        mentor="Professor Hale",
        scholar=scholar,
        phase="queued",
        track="Academia",
    )

    gossip_layers = [layer for layer in layers if layer.type == "academic_gossip"]
    update_layers = [layer for layer in layers if layer.type == "mentorship_update"]

    assert len(gossip_layers) == 2
    assert sorted(layer.delay_minutes for layer in gossip_layers) == [30, 60]
    assert len(update_layers) == 2
    assert sorted(layer.delay_minutes for layer in update_layers) == [720, 1440]


def test_generate_admin_layers_includes_reason():
    """Administrative layers should surface context and delay metadata."""
    generator = MultiPressGenerator()
    generator.fast_layer_delays = [15]
    generator.long_layer_delays = [120]

    layers = generator.generate_admin_layers(
        event="pause",
        actor="Ops Team",
        reason="LLM offline",
    )

    assert any(layer.type == "admin_update" for layer in layers)
    update_layer = next(layer for layer in layers if layer.type == "admin_update")
    release = update_layer.generator(update_layer.context)
    assert "LLM offline" in release.body


def test_generate_analysis_layer():
    """Test generating editorial/analysis layers."""
    generator = MultiPressGenerator()

    exp_ctx = ExpeditionContext(
        code="EXP001",
        player="TestPlayer",
        expedition_type="great_project",
        objective="unified theory",
        team=["Team"],
        funding=["Funding"]
    )

    result = ExpeditionResult(
        roll=90,
        modifier=10,
        final_score=100,
        outcome=ExpeditionOutcome.SUCCESS,
        sideways_discovery=None,
        failure_detail=None
    )

    outcome_ctx = OutcomeContext(
        code="EXP001",
        player="TestPlayer",
        expedition_type="great_project",
        result=result,
        reputation_change=15,
        reactions=[]
    )

    layer = generator._generate_analysis_layer(exp_ctx, outcome_ctx, 120)

    assert layer.type == "editorial"
    assert layer.delay_minutes == 120

    # Generate the actual release
    release = layer.generator(layer.context)
    assert release.type == "editorial"
    assert "profound implications" in release.body.lower()


def test_faction_statement_generation():
    """Test generating faction statements."""
    generator = MultiPressGenerator()

    # Test regret statement
    regret_layer = generator._generate_faction_statement(
        "Academic",
        "Dr. Smith",
        "regret",
        120
    )

    assert regret_layer.type == "faction_statement"
    assert regret_layer.delay_minutes == 120

    release = regret_layer.generator(regret_layer.context)
    assert "regret" in release.body.lower()

    # Test welcome statement
    welcome_layer = generator._generate_faction_statement(
        "Industry",
        "Dr. Smith",
        "welcome",
        150
    )

    release = welcome_layer.generator(welcome_layer.context)
    assert "welcome" in release.body.lower() or "delighted" in release.body.lower()


def test_multi_press_includes_tone_seed(monkeypatch):
    """Tone packs should attach seeds to mentorship follow-up layers."""
    monkeypatch.setenv("GREAT_WORK_PRESS_SETTING", "high_fantasy")
    generator = MultiPressGenerator()

    scholar = Mock(spec=Scholar)
    scholar.name = "Aria"
    scholar.id = "s.aria"
    scholar.career = {"track": "Academia"}

    layers = generator.generate_mentorship_layers(
        mentor="Professor Lorian",
        scholar=scholar,
        phase="completion",
    )

    tone_seeds = [layer.tone_seed for layer in layers if layer.type in {"mentorship_update", "academic_gossip"}]
    assert tone_seeds
    assert all(seed is not None for seed in tone_seeds)

def test_generate_recruitment_layers_uses_yaml_templates():
    """Recruitment coverage should pick headlines and callouts from YAML templates."""

    random.seed(42)
    generator = MultiPressGenerator()

    scholar = Mock(spec=Scholar)
    scholar.name = "Prof. Vale"
    scholar.id = "scholar-001"

    observers = []
    for idx in range(6):
        mock_obs = Mock(spec=Scholar)
        mock_obs.name = f"Observer{idx}"
        mock_obs.id = f"observer-{idx}"
        observers.append(mock_obs)

    layers = generator.generate_recruitment_layers(
        player="Player One",
        scholar=scholar,
        success=True,
        faction="Academic",
        chance=0.72,
        observers=observers,
    )

    digest_layer = next(layer for layer in layers if layer.type == "recruitment_followup")
    briefing_layer = next(layer for layer in layers if layer.type == "recruitment_brief")

    success_headlines = generator._recruitment_templates["recruitment"]["digest"]["success"]["headlines"]
    assert digest_layer.context["headline"] in success_headlines
    assert digest_layer.context["metadata"]["callouts"]
    assert all(isinstance(item, str) for item in digest_layer.context["metadata"]["callouts"])

    assert briefing_layer.context["metadata"]["callouts"]
    assert all(isinstance(item, str) for item in briefing_layer.context["metadata"]["callouts"])


def test_generate_table_talk_layers_produces_roundup_callouts():
    """Table-talk coverage should surface roundup callouts from YAML templates."""

    random.seed(24)
    generator = MultiPressGenerator()

    scholars = []
    for idx in range(5):
        mock_scholar = Mock(spec=Scholar)
        mock_scholar.name = f"Scholar{idx}"
        mock_scholar.id = f"scholar-{idx}"
        scholars.append(mock_scholar)

    message = "We should broaden the sideways catalogue and layer our table-talk press."
    layers = generator.generate_table_talk_layers(
        speaker="Dr. Echo",
        message=message,
        scholars=scholars,
    )

    digest_layer = next(layer for layer in layers if layer.type == "table_talk_digest")
    roundup_layer = next(layer for layer in layers if layer.type == "table_talk_roundup")

    digest_headlines = generator._table_talk_templates["table_talk"]["digest"]["headlines"]
    assert digest_layer.context["headline"] in digest_headlines

    roundup_metadata = roundup_layer.context["metadata"]
    assert roundup_metadata["callouts"]
    assert all(isinstance(item, str) for item in roundup_metadata["callouts"])


def test_generate_sidecast_layers_returns_plan():
    """Sidecast layers should draw from YAML arcs and schedule next phases."""

    random.seed(7)
    generator = MultiPressGenerator()
    arc_key = generator.pick_sidecast_arc()

    scholar = Mock(spec=Scholar)
    scholar.name = "Dr. Sidecast"
    plan = generator.generate_sidecast_layers(
        arc_key=arc_key,
        phase="debut",
        scholar=scholar,
        sponsor="Dr. Sponsor",
        expedition_type="field",
        expedition_code="EXP-001",
    )

    assert isinstance(plan.layers, list)
    assert plan.layers
    assert plan.next_phase in {"integration", "spotlight", None}


def test_generate_defection_epilogue_layers():
    """Defection epilogue layers should return configured press artifacts."""

    generator = MultiPressGenerator()
    layers = generator.generate_defection_epilogue_layers(
        scenario="reconciliation",
        scholar_name="Dr. Quill",
        former_faction="The Academy",
        new_faction="Industry",
        former_employer="Professor Hale",
    )

    assert layers
    primary = layers[0]
    assert primary.type == "defection_epilogue"
