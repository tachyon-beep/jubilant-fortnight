"""Multi-layer press artifact generation for The Great Work."""
from __future__ import annotations

import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .models import PressRelease, Scholar
from .press import (
    BulletinContext,
    ExpeditionContext,
    OutcomeContext,
    GossipContext,
    DefectionContext,
    academic_bulletin,
    research_manifesto,
    discovery_report,
    retraction_notice,
    academic_gossip,
    defection_notice
)


class PressDepth(Enum):
    """Depth of press coverage for an event."""
    MINIMAL = "minimal"      # Single press release
    STANDARD = "standard"     # Main release + 1-2 follow-ups
    EXTENSIVE = "extensive"   # Main release + 3-5 follow-ups
    BREAKING = "breaking"     # Main release + 5-8 follow-ups


@dataclass
class PressLayer:
    """Individual layer of press coverage."""
    delay_minutes: int  # Minutes after main event
    type: str          # Type of press release
    generator: callable  # Function to generate the release
    context: Any       # Context for generation


class MultiPressGenerator:
    """Generate multi-layer press artifacts for events."""

    def __init__(self):
        """Initialize the multi-press generator."""
        self.reaction_templates = [
            "{scholar} expresses {emotion} about {event}",
            "{scholar} questions the implications of {event}",
            "{scholar} calls for further investigation into {event}",
            "{scholar} praises the boldness of {event}",
            "{scholar} warns of consequences from {event}",
        ]

    def determine_depth(
        self,
        event_type: str,
        reputation_change: int = 0,
        confidence_level: Optional[str] = None,
        is_first_time: bool = False
    ) -> PressDepth:
        """Determine how much press coverage an event should get."""
        # Major events get extensive coverage
        if event_type in ["great_project_success", "defection", "major_discovery"]:
            return PressDepth.EXTENSIVE

        # High stakes get more coverage
        if confidence_level == "stake_my_career":
            return PressDepth.EXTENSIVE

        # Large reputation changes get attention
        if abs(reputation_change) >= 10:
            return PressDepth.BREAKING

        # First-time events get extra coverage
        if is_first_time:
            return PressDepth.EXTENSIVE

        # Medium reputation changes
        if abs(reputation_change) >= 5:
            return PressDepth.STANDARD

        # Default to minimal
        return PressDepth.MINIMAL

    def generate_expedition_layers(
        self,
        expedition_ctx: ExpeditionContext,
        outcome_ctx: OutcomeContext,
        scholars: List[Scholar],
        depth: PressDepth
    ) -> List[PressLayer]:
        """Generate multi-layer press for an expedition."""
        layers = []

        # Main manifesto (immediate)
        layers.append(PressLayer(
            delay_minutes=0,
            type="research_manifesto",
            generator=research_manifesto,
            context=expedition_ctx
        ))

        # Discovery/retraction report (immediate)
        if outcome_ctx.result.outcome.value in ["success", "sideways"]:
            layers.append(PressLayer(
                delay_minutes=0,
                type="discovery_report",
                generator=discovery_report,
                context=outcome_ctx
            ))
        else:
            layers.append(PressLayer(
                delay_minutes=0,
                type="retraction_notice",
                generator=retraction_notice,
                context=outcome_ctx
            ))

        # Add follow-up coverage based on depth
        if depth in [PressDepth.STANDARD, PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Scholar reactions (1 hour later)
            num_reactions = {
                PressDepth.STANDARD: 2,
                PressDepth.EXTENSIVE: 4,
                PressDepth.BREAKING: 6
            }.get(depth, 2)

            for i, scholar in enumerate(random.sample(scholars, min(num_reactions, len(scholars)))):
                emotion = random.choice(["enthusiasm", "skepticism", "concern", "admiration", "curiosity"])
                quote = self._generate_reaction_quote(
                    scholar.name,
                    expedition_ctx.objective,
                    outcome_ctx.result.outcome.value,
                    emotion
                )

                gossip_ctx = GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=f"Expedition {expedition_ctx.code}"
                )

                layers.append(PressLayer(
                    delay_minutes=60 + (i * 15),  # Stagger reactions
                    type="academic_gossip",
                    generator=academic_gossip,
                    context=gossip_ctx
                ))

        # Breaking news gets additional analysis
        if depth == PressDepth.BREAKING:
            # Editorial/analysis piece (2 hours later)
            layers.append(self._generate_analysis_layer(
                expedition_ctx,
                outcome_ctx,
                delay_minutes=120
            ))

            # Follow-up investigations (3 hours later)
            if outcome_ctx.result.sideways_discovery:
                layers.append(self._generate_investigation_layer(
                    outcome_ctx.result.sideways_discovery,
                    delay_minutes=180
                ))

        return layers

    def generate_symposium_layers(
        self,
        topic: str,
        description: str,
        phase: str,
        scholars: List[Scholar],
        votes: Optional[Dict[int, int]] = None,
    ) -> List[PressLayer]:
        """Generate layered coverage for symposium events."""

        layers: List[PressLayer] = []
        safe_scholars = scholars[:]
        random.shuffle(safe_scholars)

        if phase == "launch":
            # Curate teaser reactions (delayed)
            for i, scholar in enumerate(safe_scholars[:3]):
                quote = f"{scholar.name} hints at bold arguments for '{topic}'."
                ctx = GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=f"Symposium launch: {topic}"
                )
                layers.append(
                    PressLayer(
                        delay_minutes=45 + (i * 20),
                        type="academic_gossip",
                        generator=academic_gossip,
                        context=ctx,
                    )
                )
        elif phase == "resolution" and votes:
            total_votes = sum(votes.values()) or 1
            winner_option = max(votes.keys(), key=lambda key: votes.get(key, 0))
            winner_share = votes.get(winner_option, 0) / total_votes
            depth = (
                PressDepth.BREAKING
                if winner_share >= 0.66
                else PressDepth.STANDARD
            )

            analysts = safe_scholars[:4]
            for i, scholar in enumerate(analysts):
                quote = self._generate_symposium_reaction(
                    scholar.name,
                    topic,
                    winner_option,
                    winner_share,
                )
                ctx = GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=f"Symposium: {topic}",
                )
                delay = 60 + (i * 15)
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="academic_gossip",
                        generator=academic_gossip,
                        context=ctx,
                    )
                )

            if depth == PressDepth.BREAKING:
                layers.append(
                    PressLayer(
                        delay_minutes=150,
                        type="analysis",
                        generator=lambda ctx: PressRelease(
                            type="analysis",
                            headline=f"Symposium Analysis: {topic}",
                            body=(
                                f"Scholars dissect the decisive outcome on '{topic}'. "
                                f"Leading voices highlight lingering questions and follow-up debates."
                            ),
                            metadata={"topic": topic, "phase": "analysis"},
                        ),
                        context={},
                    )
                )

        return layers

    def generate_defection_layers(
        self,
        defection_ctx: DefectionContext,
        scholar: Scholar,
        old_faction: str,
        scholars: List[Scholar],
        depth: PressDepth
    ) -> List[PressLayer]:
        """Generate multi-layer press for a defection."""
        layers = []

        # Main defection notice
        layers.append(PressLayer(
            delay_minutes=0,
            type="defection_notice",
            generator=defection_notice,
            context=defection_ctx
        ))

        if depth in [PressDepth.STANDARD, PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Immediate reactions from close colleagues
            colleagues = self._find_colleagues(scholar, scholars)[:3]
            for i, colleague in enumerate(colleagues):
                quote = self._generate_defection_reaction(
                    colleague.name,
                    scholar.name,
                    old_faction,
                    defection_ctx.new_faction
                )

                gossip_ctx = GossipContext(
                    scholar=colleague.name,
                    quote=quote,
                    trigger=f"{scholar.name}'s defection"
                )

                layers.append(PressLayer(
                    delay_minutes=30 + (i * 10),
                    type="academic_gossip",
                    generator=academic_gossip,
                    context=gossip_ctx
                ))

        # Extensive coverage includes institutional responses
        if depth in [PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Statement from old faction (2 hours later)
            layers.append(self._generate_faction_statement(
                old_faction,
                scholar.name,
                "regret",
                delay_minutes=120
            ))

            # Statement from new faction (2.5 hours later)
            layers.append(self._generate_faction_statement(
                defection_ctx.new_faction,
                scholar.name,
                "welcome",
                delay_minutes=150
            ))

        return layers

    def generate_conference_layers(
        self,
        theory: str,
        confidence: str,
        outcome: str,
        participants: List[str],
        reputation_changes: Dict[str, int],
        depth: PressDepth
    ) -> List[PressLayer]:
        """Generate multi-layer press for a conference."""
        layers = []

        # Opening announcement
        bulletin_ctx = BulletinContext(
            bulletin_number=random.randint(1000, 9999),
            player=participants[0] if participants else "Unknown",
            theory=theory,
            confidence=confidence,
            supporters=participants[1:],
            deadline="Conference in session"
        )

        layers.append(PressLayer(
            delay_minutes=0,
            type="academic_bulletin",
            generator=academic_bulletin,
            context=bulletin_ctx
        ))

        # Conference proceedings (30 minutes later)
        if depth != PressDepth.MINIMAL:
            # Generate debate highlights
            for i in range(min(3, len(participants))):
                participant = participants[i] if i < len(participants) else f"Scholar {i+1}"
                quote = self._generate_conference_quote(participant, theory, confidence, i)

                gossip_ctx = GossipContext(
                    scholar=participant,
                    quote=quote,
                    trigger="Conference debate"
                )

                layers.append(PressLayer(
                    delay_minutes=30 + (i * 10),
                    type="academic_gossip",
                    generator=academic_gossip,
                    context=gossip_ctx
                ))

        # Outcome announcement (1 hour later)
        if depth in [PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Detailed outcome analysis
            layers.append(self._generate_conference_outcome(
                theory,
                outcome,
                reputation_changes,
                delay_minutes=60
            ))

        return layers

    def _generate_reaction_quote(
        self,
        scholar_name: str,
        objective: str,
        outcome: str,
        emotion: str
    ) -> str:
        """Generate a reaction quote from a scholar."""
        quotes = {
            "enthusiasm": [
                f"This changes everything we thought we knew about {objective}!",
                "Brilliant work! The implications are staggering.",
                f"I've been waiting years for someone to tackle {objective}."
            ],
            "skepticism": [
                "The methodology seems questionable at best.",
                "I'll believe it when I can reproduce the results.",
                f"Has anyone actually verified these claims about {objective}?"
            ],
            "concern": [
                "We may have opened a door better left closed.",
                f"The ethical implications of {objective} trouble me deeply.",
                "I fear we're not prepared for the consequences."
            ],
            "admiration": [
                "Bold and decisive - exactly what our field needs.",
                f"The courage to pursue {objective} is commendable.",
                "A masterclass in expedition planning and execution."
            ],
            "curiosity": [
                f"This raises more questions than it answers about {objective}.",
                "I wonder if similar methods could apply to my own research.",
                "The sideways implications are perhaps more interesting than the main findings."
            ]
        }

        return random.choice(quotes.get(emotion, ["No comment at this time."]))

    def _generate_symposium_reaction(
        self,
        scholar_name: str,
        topic: str,
        winning_option: int,
        winning_share: float,
    ) -> str:
        """Generate a symposium reaction quote."""

        option_text = {
            1: "support",
            2: "oppose",
            3: "call for further study",
        }.get(winning_option, "debate")

        sentiments = [
            f"{scholar_name} applauds the {option_text} verdict on '{topic}', citing its clarity.",
            f"{scholar_name} warns that the {option_text} outcome on '{topic}' leaves crucial questions unanswered.",
            f"{scholar_name} notes that with {winning_share:.0%} backing, the academy must act decisively on '{topic}'.",
            f"{scholar_name} believes the {option_text} majority on '{topic}' reflects a broader shift in priorities.",
        ]
        return random.choice(sentiments)

    def _generate_defection_reaction(
        self,
        colleague: str,
        defector: str,
        old_faction: str,
        new_faction: str
    ) -> str:
        """Generate a reaction to a defection."""
        reactions = [
            f"I'm shocked. {defector} seemed so committed to {old_faction}.",
            f"Perhaps {new_faction} offered what {old_faction} couldn't.",
            f"A loss for {old_faction}, but I understand the decision.",
            "Loyalty means nothing in today's academic climate, apparently.",
            f"I wish {defector} well in their new position with {new_faction}.",
        ]
        return random.choice(reactions)

    def _generate_conference_quote(
        self,
        participant: str,
        theory: str,
        confidence: str,
        position: int
    ) -> str:
        """Generate a quote from a conference participant."""
        if position == 0:  # Proposer
            return f"I stand by my {confidence} confidence in '{theory}' and welcome scrutiny."
        elif position == 1:  # First challenger
            return f"The evidence for '{theory}' is circumstantial at best."
        else:  # Other participants
            return "We must consider alternative interpretations of the data."

    def _find_colleagues(
        self,
        scholar: Scholar,
        all_scholars: List[Scholar],
        max_colleagues: int = 5
    ) -> List[Scholar]:
        """Find colleagues of a scholar (simplified - random selection)."""
        others = [s for s in all_scholars if s.name != scholar.name]
        return random.sample(others, min(max_colleagues, len(others)))

    def _generate_analysis_layer(
        self,
        expedition_ctx: ExpeditionContext,
        outcome_ctx: OutcomeContext,
        delay_minutes: int
    ) -> PressLayer:
        """Generate an analysis/editorial layer."""
        analysis_text = (
            f"EDITORIAL: The {expedition_ctx.expedition_type} expedition '{expedition_ctx.code}' "
            f"has profound implications for our understanding of {expedition_ctx.objective}. "
            f"With a {outcome_ctx.result.outcome.value} outcome and {outcome_ctx.reputation_change:+} "
            f"reputation change, this marks a turning point in the field."
        )

        return PressLayer(
            delay_minutes=delay_minutes,
            type="editorial",
            generator=lambda ctx: PressRelease(
                type="editorial",
                headline="Editorial: Analyzing Recent Developments",
                body=analysis_text
            ),
            context={}
        )

    def _generate_investigation_layer(
        self,
        sideways_discovery: str,
        delay_minutes: int
    ) -> PressLayer:
        """Generate follow-up investigation layer."""
        investigation_text = (
            f"INVESTIGATION: Following reports of '{sideways_discovery}', "
            f"our investigative team has uncovered additional details that suggest "
            f"this discovery may have far-reaching consequences beyond initial assessments."
        )

        return PressLayer(
            delay_minutes=delay_minutes,
            type="investigation",
            generator=lambda ctx: PressRelease(
                type="investigation",
                headline="Investigation: Uncovering the Truth",
                body=investigation_text
            ),
            context={}
        )

    def _generate_faction_statement(
        self,
        faction: str,
        scholar_name: str,
        tone: str,
        delay_minutes: int
    ) -> PressLayer:
        """Generate a faction statement."""
        if tone == "regret":
            statement = (
                f"STATEMENT FROM {faction.upper()}: We regret that {scholar_name} has chosen "
                f"to leave our institution. We wish them well in their future endeavors and "
                f"remain committed to our mission of advancing knowledge."
            )
        else:  # welcome
            statement = (
                f"STATEMENT FROM {faction.upper()}: We are delighted to welcome {scholar_name} "
                f"to our ranks. Their expertise and reputation will be invaluable assets "
                f"as we pursue groundbreaking research."
            )

        return PressLayer(
            delay_minutes=delay_minutes,
            type="faction_statement",
            generator=lambda ctx: PressRelease(
                type="faction_statement",
                headline=f"Official Statement from {faction}",
                body=statement
            ),
            context={}
        )

    def _generate_conference_outcome(
        self,
        theory: str,
        outcome: str,
        reputation_changes: Dict[str, int],
        delay_minutes: int
    ) -> PressLayer:
        """Generate conference outcome announcement."""
        winners = [p for p, r in reputation_changes.items() if r > 0]
        losers = [p for p, r in reputation_changes.items() if r < 0]

        outcome_text = (
            f"CONFERENCE CONCLUDED: After rigorous debate on '{theory}', "
            f"the conference has reached its conclusion. "
        )

        if winners:
            outcome_text += f"Vindicated: {', '.join(winners)}. "
        if losers:
            outcome_text += f"Refuted: {', '.join(losers)}. "

        outcome_text += "The academic community will be processing these results for years to come."

        return PressLayer(
            delay_minutes=delay_minutes,
            type="conference_outcome",
            generator=lambda ctx: PressRelease(
                type="conference_outcome",
                headline="Conference Conclusion",
                body=outcome_text
            ),
            context={}
        )

    def apply_layers(
        self,
        layers: List[PressLayer],
        immediate_only: bool = False
    ) -> List[PressRelease]:
        """Apply press layers and generate releases."""
        releases = []

        for layer in layers:
            # Skip delayed layers if immediate_only
            if immediate_only and layer.delay_minutes > 0:
                continue

            # Generate the press release
            release = layer.generator(layer.context)
            releases.append(release)

        return releases
