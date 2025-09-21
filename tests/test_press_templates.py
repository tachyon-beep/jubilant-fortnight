"""Tests for press release template generation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from great_work.expeditions import ExpeditionOutcome, ExpeditionResult
from great_work.models import PressRelease
from great_work.press import (
    BulletinContext,
    DefectionContext,
    ExpeditionContext,
    GossipContext,
    OutcomeContext,
    RecruitmentContext,
    academic_bulletin,
    academic_gossip,
    defection_notice,
    discovery_report,
    recruitment_report,
    research_manifesto,
    retraction_notice,
)


def test_academic_bulletin_template():
    """Academic bulletin should format theory submissions correctly."""
    ctx = BulletinContext(
        bulletin_number=42,
        player="Dr. Smith",
        theory="Quantum entanglement affects tea brewing",
        confidence="certain",
        supporters=["Dr. Jones", "Prof. Williams"],
        deadline="2024-12-31",
    )

    press = academic_bulletin(ctx)

    assert press.type == "academic_bulletin"
    assert press.headline == "Academic Bulletin No. 42"
    assert "Dr. Smith" in press.body
    assert "Quantum entanglement affects tea brewing" in press.body
    assert "certain confidence" in press.body
    assert "Dr. Jones, Prof. Williams" in press.body
    assert "2024-12-31" in press.body


def test_academic_bulletin_no_supporters():
    """Academic bulletin should handle empty supporter list."""
    ctx = BulletinContext(
        bulletin_number=1,
        player="Solo Researcher",
        theory="Independent discovery",
        confidence="suspect",
        supporters=[],
        deadline="2025-01-01",
    )

    press = academic_bulletin(ctx)

    assert "Supporting scholars: None" in press.body


def test_research_manifesto_template():
    """Research manifesto should format expedition announcements correctly."""
    ctx = ExpeditionContext(
        code="AR-2024-001",
        player="Explorer",
        expedition_type="field",
        objective="Map the ancient ruins",
        team=["Scholar A", "Scholar B", "Scholar C"],
        funding=["academia", "government"],
    )

    press = research_manifesto(ctx)

    assert press.type == "research_manifesto"
    assert "Expedition AR-2024-001" in press.headline
    assert "Map the ancient ruins" in press.body
    assert "Scholar A, Scholar B, Scholar C" in press.body
    assert "academia, government" in press.body
    assert "Explorer" in press.body


def test_research_manifesto_self_funded():
    """Research manifesto should handle empty funding list as self-funded."""
    ctx = ExpeditionContext(
        code="EX-001",
        player="Independent",
        expedition_type="theoretical",
        objective="Prove hypothesis",
        team=["Solo Scholar"],
        funding=[],
    )

    press = research_manifesto(ctx)

    assert "self-funded" in press.body
    assert "Solo Scholar" in press.body


def test_discovery_report_success():
    """Discovery report should format successful expeditions correctly."""
    result = ExpeditionResult(
        outcome=ExpeditionOutcome.SUCCESS,
        roll=85,
        modifier=10,
        final_score=95,
        failure_detail=None,
    )

    ctx = OutcomeContext(
        code="AR-001",
        player="Explorer",
        expedition_type="field",
        result=result,
        reputation_change=5,
        reactions=["Dr. Smith: 'Excellent work!'", "Prof. Jones: 'Groundbreaking!'"],
    )

    press = discovery_report(ctx)

    assert press.type == "discovery_report"
    assert "Discovery Report: Expedition AR-001" in press.headline
    assert "Outcome: success" in press.body
    assert "Roll 85 + 10 = 95" in press.body
    assert "Reputation change: +5" in press.body
    assert "Dr. Smith: 'Excellent work!'" in press.body
    assert press.metadata["outcome"] == "success"


def test_retraction_notice_failure():
    """Retraction notice should format failed expeditions correctly."""
    result = ExpeditionResult(
        outcome=ExpeditionOutcome.FAILURE,
        roll=25,
        modifier=-5,
        final_score=20,
        failure_detail="Equipment malfunction caused data loss",
    )

    ctx = OutcomeContext(
        code="EX-FAIL-001",
        player="Researcher",
        expedition_type="theoretical",
        result=result,
        reputation_change=-7,
        reactions=["Scholar A: 'Disappointing'", "Scholar B: 'Poor preparation'"],
    )

    press = retraction_notice(ctx)

    assert press.type == "retraction_notice"
    assert "Retraction Notice: Expedition EX-FAIL-001" in press.headline
    assert "Theoretical" in press.headline
    assert "Outcome: failure" in press.body
    assert "Roll 25 + -5 = 20" in press.body
    assert "Reputation change: -7" in press.body
    assert "Equipment malfunction caused data loss" in press.body
    assert "Scholar A: 'Disappointing'" in press.body
    assert press.metadata["outcome"] == "failure"


def test_retraction_notice_no_reactions():
    """Retraction notice should handle empty reactions list."""
    result = ExpeditionResult(
        outcome=ExpeditionOutcome.PARTIAL,
        roll=50,
        modifier=0,
        final_score=50,
        failure_detail="Partial data recovery",
    )

    ctx = OutcomeContext(
        code="PART-001",
        player="Investigator",
        expedition_type="field",
        result=result,
        reputation_change=1,
        reactions=[],
    )

    press = retraction_notice(ctx)

    # Should not have scholar reactions section
    assert "Scholar reactions:" not in press.body


def test_recruitment_report_success():
    """Recruitment report should format successful recruitment correctly."""
    ctx = RecruitmentContext(
        player="Recruiter",
        scholar="Dr. Elena Vasquez",
        outcome="SUCCESS",
        chance=0.85,
        faction="academia",
    )

    press = recruitment_report(ctx)

    assert press.type == "recruitment_report"
    assert "Dr. Elena Vasquez" in press.headline
    assert "Recruiter" in press.body
    assert "academia" in press.body
    assert "SUCCESS" in press.body
    assert "85%" in press.body


def test_recruitment_report_failure():
    """Recruitment report should format failed recruitment correctly."""
    ctx = RecruitmentContext(
        player="Failed Recruiter",
        scholar="Prof. Stubborn",
        outcome="FAILED",
        chance=0.25,
        faction="government",
    )

    press = recruitment_report(ctx)

    assert "Prof. Stubborn" in press.headline
    assert "FAILED" in press.body
    assert "25%" in press.body


def test_defection_notice_template():
    """Defection notice should format scholar defections correctly."""
    ctx = DefectionContext(
        scholar="Dr. Turncoat",
        outcome="accepted",
        new_faction="industry",
        probability=0.75,
    )

    press = defection_notice(ctx)

    assert press.type == "defection_notice"
    assert "Dr. Turncoat" in press.headline
    assert "accepted" in press.body
    assert "industry" in press.body
    assert "75%" in press.body


def test_defection_notice_rejected():
    """Defection notice should handle rejected offers."""
    ctx = DefectionContext(
        scholar="Prof. Loyal",
        outcome="rejected",
        new_faction="Foreign Academy",
        probability=0.10,
    )

    press = defection_notice(ctx)

    assert "rejected" in press.body
    assert "10%" in press.body


def test_academic_gossip_template():
    """Academic gossip should format gossip correctly."""
    ctx = GossipContext(
        scholar="Prof. Smith",
        quote="The Dean's priorities are misaligned with true scholarship",
        trigger="funding dispute",
    )

    press = academic_gossip(ctx)

    assert press.type == "academic_gossip"
    assert "Academic Gossip" in press.headline
    assert "Prof. Smith" in press.headline
    assert "The Dean's priorities" in press.body
    assert "funding dispute" in press.body


def test_academic_gossip_short_quote():
    """Academic gossip should handle short quotes."""
    ctx = GossipContext(
        scholar="Dr. Brief", quote="Nonsense!", trigger="theory presentation"
    )

    press = academic_gossip(ctx)

    assert "Nonsense!" in press.body
    assert "theory presentation" in press.body
