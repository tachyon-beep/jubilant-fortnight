"""Press release generation templates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import ExpeditionResult, PressRelease


@dataclass
class BulletinContext:
    bulletin_number: int
    player: str
    theory: str
    confidence: str
    supporters: List[str]
    deadline: str


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
    "research_manifesto",
    "discovery_report",
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
