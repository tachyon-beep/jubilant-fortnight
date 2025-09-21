"""Press release generation templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm_client import enhance_press_release
from .models import ExpeditionResult, PressRelease


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
    scholar_traits: Optional[Dict[str, Any]] = None,
) -> PressRelease:
    """Generate academic bulletin with optional LLM enhancement."""
    headline = f"Academic Bulletin No. {ctx.bulletin_number}"
    support = ", ".join(ctx.supporters) if ctx.supporters else "None"
    base_body = (
        f'{ctx.player} submits "{ctx.theory}" with {ctx.confidence} confidence. '
        f"Supporting scholars: {support}. Counter-claims invited before {ctx.deadline}."
    )

    # Try to enhance with LLM
    context = {
        "type": "academic_bulletin",
        "player": ctx.player,
        "theory": ctx.theory,
        "confidence": ctx.confidence,
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
        f'{ctx.player} submits "{ctx.theory}" with {ctx.confidence} confidence. '
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
    prep_depth: Optional[str] = None
    preparation_strengths: List[str] = field(default_factory=list)
    preparation_frictions: List[str] = field(default_factory=list)


async def research_manifesto_async(
    ctx: ExpeditionContext,
    scholar_name: Optional[str] = None,
    scholar_traits: Optional[Dict[str, Any]] = None,
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
        "team": team,
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
    if ctx.prep_depth:
        depth_text = ctx.prep_depth.replace("_", " ").title()
        body += f" Preparation depth: {depth_text}."
    if ctx.preparation_strengths:
        body += " Prep highlights: " + "; ".join(ctx.preparation_strengths) + "."
    if ctx.preparation_frictions:
        body += " Known risks: " + "; ".join(ctx.preparation_frictions) + "."
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
    scholar_traits: Optional[Dict[str, Any]] = None,
) -> PressRelease:
    """Generate discovery report with optional LLM enhancement."""
    headline = (
        f"Discovery Report: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    )
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
        "reputation_change": ctx.reputation_change,
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
    headline = (
        f"Discovery Report: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    )
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
    headline = (
        f"Retraction Notice: Expedition {ctx.code} ({ctx.expedition_type.title()})"
    )
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
    body = f'{ctx.scholar}: "{ctx.quote}" (Context: {ctx.trigger}).'
    return PressRelease(type="academic_gossip", headline=headline, body=body)


@dataclass
class RecruitmentContext:
    player: str
    scholar: str
    outcome: str
    chance: float
    faction: str
    relationship_modifier: float = 0.0


def recruitment_report(ctx: RecruitmentContext) -> PressRelease:
    headline = f"Recruitment Update: {ctx.scholar}"
    body = (
        f"{ctx.player} pursued {ctx.scholar} through {ctx.faction}. "
        f"Outcome: {ctx.outcome}. Chance: {ctx.chance:.0%}."
    )
    if ctx.relationship_modifier:
        body += f" Relationship modifier {ctx.relationship_modifier:+.0%}."
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


@dataclass
class SeasonalCommitmentContext:
    player: str
    faction: str
    tier: Optional[str]
    cost: int
    relationship_modifier: float
    debt: int
    status: str
    paid: int


def seasonal_commitment_update(ctx: SeasonalCommitmentContext) -> PressRelease:
    tier_suffix = f" (Tier {ctx.tier})" if ctx.tier else ""
    headline = f"Seasonal Commitment Update — {ctx.player}{tier_suffix}"
    body = (
        f"{ctx.player} maintains a seasonal pledge with {ctx.faction}. "
        f"Cost: {ctx.cost}. Relationship modifier {ctx.relationship_modifier:+.0%}."
    )
    if ctx.debt:
        body += f" Outstanding debt: {ctx.debt}."
    if ctx.paid and ctx.debt == 0:
        body += " Commitments remain in good standing."
    return PressRelease(type="seasonal_commitment_update", headline=headline, body=body)


def seasonal_commitment_complete(ctx: SeasonalCommitmentContext) -> PressRelease:
    tier_suffix = f" (Tier {ctx.tier})" if ctx.tier else ""
    headline = f"Seasonal Commitment Completed — {ctx.player}{tier_suffix}"
    body = (
        f"{ctx.player} concludes their seasonal pledge with {ctx.faction}. "
        f"Final cost {ctx.cost} with relationship modifier {ctx.relationship_modifier:+.0%}."
    )
    if ctx.debt:
        body += f" Remaining debt {ctx.debt} will carry forward."
    return PressRelease(
        type="seasonal_commitment_complete", headline=headline, body=body
    )


@dataclass
class FactionProjectUpdateContext:
    name: str
    faction: str
    progress: float
    target: float
    contributions: List[Dict[str, object]]


def faction_project_update(ctx: FactionProjectUpdateContext) -> PressRelease:
    headline = f"Faction Project Update — {ctx.name}"
    progress_pct = (ctx.progress / ctx.target * 100) if ctx.target else 0
    body_lines = [
        f"{ctx.name} advances under {ctx.faction} stewardship.",
        f"Progress: {ctx.progress:.2f}/{ctx.target:.2f} ({progress_pct:.1f}%).",
    ]
    if ctx.contributions:
        top = sorted(
            ctx.contributions, key=lambda entry: entry["contribution"], reverse=True
        )[:3]
        contrib_lines = [
            f"{entry['player']}: {entry['contribution']:.2f} ({entry['relationship_modifier']:+.0%})"
            for entry in top
        ]
        body_lines.append("Top contributors: " + "; ".join(contrib_lines))
    body = " ".join(body_lines)
    return PressRelease(type="faction_project_update", headline=headline, body=body)


def faction_project_complete(ctx: FactionProjectUpdateContext) -> PressRelease:
    headline = f"Faction Project Completed — {ctx.name}"
    body = (
        f"{ctx.name} is complete under the auspices of {ctx.faction}. "
        f"Final progress {ctx.progress:.2f}/{ctx.target:.2f}."
    )
    return PressRelease(type="faction_project_complete", headline=headline, body=body)


@dataclass
class FactionInvestmentContext:
    player: str
    faction: str
    amount: int
    total: int
    program: Optional[str]
    relationship_bonus: float


def faction_investment(ctx: FactionInvestmentContext) -> PressRelease:
    headline = f"Faction Investment — {ctx.player}"
    body_parts = [
        f"{ctx.player} invests {ctx.amount} influence with {ctx.faction}.",
        f"Lifetime contributions now total {ctx.total} influence.",
    ]
    if ctx.program:
        body_parts.append(f"Program focus: {ctx.program}.")
    if ctx.relationship_bonus:
        body_parts.append(
            f"Scholarly goodwill improves by {ctx.relationship_bonus:+.1f}."
        )
    body = " ".join(body_parts)
    return PressRelease(type="faction_investment", headline=headline, body=body)


@dataclass
class ArchiveEndowmentContext:
    player: str
    faction: str
    amount: int
    program: Optional[str]
    paid_debt: int
    reputation_delta: int


def archive_endowment(ctx: ArchiveEndowmentContext) -> PressRelease:
    headline = f"Archive Endowment — {ctx.player}"
    body_parts = [
        f"{ctx.player} donates {ctx.amount} influence from {ctx.faction} reserves to the Archive.",
    ]
    if ctx.program:
        body_parts.append(f"Attributed to the {ctx.program} initiative.")
    if ctx.paid_debt:
        body_parts.append(f"Symposium debts reduced by {ctx.paid_debt} influence.")
    if ctx.reputation_delta:
        body_parts.append(
            f"Reputation shifts by {ctx.reputation_delta:+d} in recognition."
        )
    body = " ".join(body_parts)
    return PressRelease(type="archive_endowment", headline=headline, body=body)


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
    "SeasonalCommitmentContext",
    "FactionProjectUpdateContext",
    "FactionInvestmentContext",
    "ArchiveEndowmentContext",
    "seasonal_commitment_update",
    "seasonal_commitment_complete",
    "faction_project_update",
    "faction_project_complete",
    "faction_investment",
    "archive_endowment",
]
