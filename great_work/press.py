"""Press release generation templates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from .models import ExpeditionResult, PressRelease
from .llm_client import enhance_press_release


@dataclass
class BulletinContext:
    bulletin_number: int
    player: str
    theory: str
    confidence: str
    supporters: List[str]
    deadline: str


async def academic_bulletin_async(
    ctx: BulletinContext,
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None
) -> PressRelease:
    """Generate academic bulletin with optional LLM enhancement."""
    headline = f"Academic Bulletin No. {ctx.bulletin_number}"
    support = ", ".join(ctx.supporters) if ctx.supporters else "None"
    base_body = (
        f"{ctx.player} submits \"{ctx.theory}\" with {ctx.confidence} confidence. "
        f"Supporting scholars: {support}. Counter-claims invited before {ctx.deadline}."
    )

    # Try to enhance with LLM
    context = {
        "type": "academic_bulletin",
        "player": ctx.player,
        "theory": ctx.theory,
        "confidence": ctx.confidence
    }

    try:
        body = await enhance_press_release(
            "academic_bulletin", base_body, context, scholar_name, scholar_traits
        )
    except Exception:
        body = base_body  # Fallback to template

    return PressRelease(type="academic_bulletin", headline=headline, body=body)


def academic_bulletin(ctx: BulletinContext) -> PressRelease:
    headline = f"Academic Bulletin No. {ctx.bulletin_number}"
    support = ", ".join(ctx.supporters) if ctx.supporters else "None"
    body = (
        f"{ctx.player} submits \"{ctx.theory}\" with {ctx.confidence} confidence. "
        f"Supporting scholars: {support}. Counter-claims invited before {ctx.deadline}."
    )
    return PressRelease(type="academic_bulletin", headline=headline, body=body)


@dataclass
class ExpeditionContext:
    code: str
    player: str
    expedition_type: str
    objective: str
    team: List[str]
    funding: List[str]


async def research_manifesto_async(
    ctx: ExpeditionContext,
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None
) -> PressRelease:
    """Generate research manifesto with optional LLM enhancement."""
    team = ", ".join(ctx.team)
    funding = ", ".join(ctx.funding) if ctx.funding else "self-funded"
    headline = f"Expedition {ctx.code} Manifesto"
    base_body = (
        f"{ctx.player} announces Expedition {ctx.code}. Objective: {ctx.objective}. "
        f"Team: {team}. Funding: {funding}."
    )

    # Try to enhance with LLM
    context = {
        "type": "research_manifesto",
        "player": ctx.player,
        "code": ctx.code,
        "objective": ctx.objective,
        "team": team
    }

    try:
        body = await enhance_press_release(
            "research_manifesto", base_body, context, scholar_name, scholar_traits
        )
    except Exception:
        body = base_body  # Fallback to template

    return PressRelease(type="research_manifesto", headline=headline, body=body)


def research_manifesto(ctx: ExpeditionContext) -> PressRelease:
    team = ", ".join(ctx.team)
    funding = ", ".join(ctx.funding) if ctx.funding else "self-funded"
    headline = f"Expedition {ctx.code} Manifesto"
    body = (
        f"{ctx.player} announces Expedition {ctx.code}. Objective: {ctx.objective}. "
        f"Team: {team}. Funding: {funding}."
    )
    return PressRelease(type="research_manifesto", headline=headline, body=body)


@dataclass
class OutcomeContext:
    code: str
    player: str
    expedition_type: str
    result: ExpeditionResult
    reputation_change: int
    reactions: List[str]


async def discovery_report_async(
    ctx: OutcomeContext,
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None
) -> PressRelease:
    """Generate discovery report with optional LLM enhancement."""
    headline = f"Discovery Report: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    reaction_text = " | ".join(ctx.reactions)
    base_body = (
        f"Outcome: {ctx.result.outcome.value}. "
        f"Roll {ctx.result.roll} + {ctx.result.modifier} = {ctx.result.final_score}. "
        f"Reputation change: {ctx.reputation_change:+}."
    )
    if ctx.result.sideways_discovery:
        base_body += f" Side discovery: {ctx.result.sideways_discovery}."
    if ctx.result.failure_detail:
        base_body += f" Failure detail: {ctx.result.failure_detail}."
    if reaction_text:
        base_body += f" Scholar reactions: {reaction_text}."

    # Try to enhance with LLM
    context = {
        "type": "discovery_report",
        "player": ctx.player,
        "code": ctx.code,
        "outcome": ctx.result.outcome.value,
        "reputation_change": ctx.reputation_change
    }

    try:
        body = await enhance_press_release(
            "discovery_report", base_body, context, scholar_name, scholar_traits
        )
    except Exception:
        body = base_body  # Fallback to template

    return PressRelease(
        type="discovery_report",
        headline=headline,
        body=body,
        metadata={"outcome": ctx.result.outcome.value},
    )


def discovery_report(ctx: OutcomeContext) -> PressRelease:
    headline = f"Discovery Report: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    reaction_text = " | ".join(ctx.reactions)
    body = (
        f"Outcome: {ctx.result.outcome.value}. "
        f"Roll {ctx.result.roll} + {ctx.result.modifier} = {ctx.result.final_score}. "
        f"Reputation change: {ctx.reputation_change:+}."
    )
    if ctx.result.sideways_discovery:
        body += f" Side discovery: {ctx.result.sideways_discovery}."
    if ctx.result.failure_detail:
        body += f" Failure detail: {ctx.result.failure_detail}."
    if reaction_text:
        body += f" Scholar reactions: {reaction_text}."
    return PressRelease(
        type="discovery_report",
        headline=headline,
        body=body,
        metadata={"outcome": ctx.result.outcome.value},
    )


def retraction_notice(ctx: OutcomeContext) -> PressRelease:
    headline = f"Retraction Notice: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    reaction_text = " | ".join(ctx.reactions)
    body = (
        f"Outcome: {ctx.result.outcome.value}. Roll {ctx.result.roll} + {ctx.result.modifier} = {ctx.result.final_score}. "
        f"Reputation change: {ctx.reputation_change:+}. Failure detail: {ctx.result.failure_detail}."
    )
    if reaction_text:
        body += f" Scholar reactions: {reaction_text}."
    return PressRelease(
        type="retraction_notice",
        headline=headline,
        body=body,
        metadata={"outcome": ctx.result.outcome.value},
    )


@dataclass
class GossipContext:
    scholar: str
    quote: str
    trigger: str


def academic_gossip(ctx: GossipContext) -> PressRelease:
    headline = f"Academic Gossip — {ctx.scholar}"
    body = f"{ctx.scholar}: \"{ctx.quote}\" (Context: {ctx.trigger})."
    return PressRelease(type="academic_gossip", headline=headline, body=body)


@dataclass
class RecruitmentContext:
    player: str
    scholar: str
    outcome: str
    chance: float
    faction: str


def recruitment_report(ctx: RecruitmentContext) -> PressRelease:
    headline = f"Recruitment Update: {ctx.scholar}"
    body = (
        f"{ctx.player} pursued {ctx.scholar} through {ctx.faction}. "
        f"Outcome: {ctx.outcome}. Chance: {ctx.chance:.0%}."
    )
    return PressRelease(type="recruitment_report", headline=headline, body=body)


@dataclass
class DefectionContext:
    scholar: str
    outcome: str
    new_faction: str
    probability: float


def defection_notice(ctx: DefectionContext) -> PressRelease:
    headline = f"Defection Wire — {ctx.scholar}"
    body = (
        f"{ctx.scholar} {ctx.outcome} an offer from {ctx.new_faction}. "
        f"Probability: {ctx.probability:.0%}."
    )
    return PressRelease(type="defection_notice", headline=headline, body=body)


__all__ = [
    "academic_bulletin",
    "academic_bulletin_async",
    "research_manifesto",
    "research_manifesto_async",
    "discovery_report",
    "discovery_report_async",
    "retraction_notice",
    "academic_gossip",
    "recruitment_report",
    "defection_notice",
    "BulletinContext",
    "ExpeditionContext",
    "OutcomeContext",
    "GossipContext",
    "RecruitmentContext",
    "DefectionContext",
]
