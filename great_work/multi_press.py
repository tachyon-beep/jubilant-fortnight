"""Multi-layer press artifact generation for The Great Work."""
from __future__ import annotations

import os
import random
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

import yaml

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
    defection_notice,
)
from .press_tone import get_tone_seed


_MENTORSHIP_TEMPLATES: Optional[Dict[str, Any]] = None
_RECRUITMENT_TEMPLATES: Optional[Dict[str, Any]] = None
_TABLE_TALK_TEMPLATES: Optional[Dict[str, Any]] = None
_SIDECAST_ARCS: Optional[Dict[str, Any]] = None
_DEFECTION_EPILOGUES: Optional[Dict[str, Any]] = None


def _load_yaml_resource(filename: str) -> Dict[str, Any]:
    path = Path(__file__).resolve().parent / "data" / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def _load_mentorship_templates() -> Dict[str, Any]:
    global _MENTORSHIP_TEMPLATES
    if _MENTORSHIP_TEMPLATES is None:
        _MENTORSHIP_TEMPLATES = _load_yaml_resource("mentorship_press.yaml")
    return _MENTORSHIP_TEMPLATES


def _load_recruitment_templates() -> Dict[str, Any]:
    global _RECRUITMENT_TEMPLATES
    if _RECRUITMENT_TEMPLATES is None:
        _RECRUITMENT_TEMPLATES = _load_yaml_resource("recruitment_press.yaml")
    return _RECRUITMENT_TEMPLATES


def _load_table_talk_templates() -> Dict[str, Any]:
    global _TABLE_TALK_TEMPLATES
    if _TABLE_TALK_TEMPLATES is None:
        _TABLE_TALK_TEMPLATES = _load_yaml_resource("table_talk_press.yaml")
    return _TABLE_TALK_TEMPLATES


def _load_sidecast_arcs() -> Dict[str, Any]:
    global _SIDECAST_ARCS
    if _SIDECAST_ARCS is None:
        data = _load_yaml_resource("sidecast_arcs.yaml")
        _SIDECAST_ARCS = data.get("sidecasts", {}) if isinstance(data, dict) else {}
    return _SIDECAST_ARCS


def _load_defection_epilogues() -> Dict[str, Any]:
    global _DEFECTION_EPILOGUES
    if _DEFECTION_EPILOGUES is None:
        data = _load_yaml_resource("defection_epilogues.yaml")
        _DEFECTION_EPILOGUES = data.get("epilogues", {}) if isinstance(data, dict) else {}
    return _DEFECTION_EPILOGUES


def mentorship_update(context: Dict[str, Any]) -> PressRelease:
    """Generate a mentorship-themed press release from context."""

    return PressRelease(
        type=context.get("type", "mentorship_update"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def admin_update(context: Dict[str, Any]) -> PressRelease:
    """Generate an administrative status press release."""

    return PressRelease(
        type=context.get("type", "admin_update"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def recruitment_followup(context: Dict[str, Any]) -> PressRelease:
    """Generate a recruitment follow-up artefact."""

    return PressRelease(
        type=context.get("type", "recruitment_followup"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def recruitment_brief(context: Dict[str, Any]) -> PressRelease:
    """Generate a faction briefing about recruitment outcomes."""

    return PressRelease(
        type=context.get("type", "recruitment_brief"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def sidecast_brief(context: Dict[str, Any]) -> PressRelease:
    """Generate a sidecast-focused brief."""

    return PressRelease(
        type=context.get("type", "sidecast_brief"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def defection_epilogue_release(context: Dict[str, Any]) -> PressRelease:
    """Generate the primary defection epilogue artefact."""

    return PressRelease(
        type=context.get("type", "defection_epilogue"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def defection_epilogue_brief(context: Dict[str, Any]) -> PressRelease:
    """Generate a faction briefing for defection fallout."""

    return PressRelease(
        type=context.get("type", "defection_epilogue_brief"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def table_talk_digest(context: Dict[str, Any]) -> PressRelease:
    """Generate a digest summarising table-talk reactions."""

    return PressRelease(
        type=context.get("type", "table_talk_digest"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
    )


def table_talk_roundup(context: Dict[str, Any]) -> PressRelease:
    """Generate a roundup of table-talk whispers."""

    return PressRelease(
        type=context.get("type", "table_talk_roundup"),
        headline=context["headline"],
        body=context["body"],
        metadata=context.get("metadata", {}),
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
    tone_seed: Optional[Dict[str, str]] = None


@dataclass
class SidecastPhasePlan:
    """Plan for a sidecast phase including upcoming scheduling."""

    layers: List[PressLayer]
    next_phase: Optional[str]
    next_delay_hours: Optional[float]


class MultiPressGenerator:
    """Generate multi-layer press artifacts for events."""

    def __init__(self, setting: str | None = None):
        """Initialize the multi-press generator."""
        self.reaction_templates = [
            "{scholar} expresses {emotion} about {event}",
            "{scholar} questions the implications of {event}",
            "{scholar} calls for further investigation into {event}",
            "{scholar} praises the boldness of {event}",
            "{scholar} warns of consequences from {event}",
        ]
        self.fast_layer_delays = self._load_delays(
            os.getenv("GREAT_WORK_FAST_LAYER_DELAYS"),
            default=[0, 45, 120],
        )
        self.long_layer_delays = self._load_delays(
            os.getenv("GREAT_WORK_LONG_LAYER_DELAYS"),
            default=[720, 1440, 2880],
        )
        self._setting = setting
        self._mentorship_templates = _load_mentorship_templates()
        self._recruitment_templates = _load_recruitment_templates()
        self._table_talk_templates = _load_table_talk_templates()
        self._sidecast_arcs = _load_sidecast_arcs()
        self._defection_epilogues = _load_defection_epilogues()

    @staticmethod
    def _load_delays(raw: Optional[str], default: List[int]) -> List[int]:
        """Parse comma-separated delay minutes with graceful fallback."""

        if not raw:
            return list(default)
        try:
            values = [int(value.strip()) for value in raw.split(",") if value.strip()]
            return values or list(default)
        except ValueError:
            return list(default)

    def _resolve_track_descriptor(self, track_name: str) -> str:
        templates = self._mentorship_templates or {}
        track_cfg = templates.get("tracks", {})
        entry = (
            track_cfg.get(track_name)
            or track_cfg.get(track_name.title())
            or track_cfg.get(track_name.lower())
            or track_cfg.get("Default", {})
        )
        return entry.get("descriptor", track_name.lower())

    @staticmethod
    def _format_delay(delay_minutes: int) -> str:
        if delay_minutes >= 1440:
            days = delay_minutes // 1440
            return f"{days} day{'s' if days != 1 else ''}"
        if delay_minutes >= 60:
            hours = delay_minutes // 60
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{delay_minutes} minute{'s' if delay_minutes != 1 else ''}"

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

    def _tone_seed(self, event_key: str) -> Optional[Dict[str, str]]:
        seed = get_tone_seed(event_key, self._setting)
        if seed:
            return dict(seed)
        return None

    def pick_sidecast_arc(self) -> str:
        """Select a sidecast arc identifier, defaulting to the first entry."""

        if not self._sidecast_arcs:
            return "local_junior"
        return random.choice(list(self._sidecast_arcs.keys()))

    def _sidecast_phase_config(self, arc_key: str, phase: str) -> Dict[str, Any]:
        arc = self._sidecast_arcs.get(arc_key) or {}
        phases = arc.get("phases", {})
        return phases.get(phase, {})

    def sidecast_phase_delay(self, arc_key: str, phase: str, default_hours: float = 24.0) -> float:
        cfg = self._sidecast_phase_config(arc_key, phase)
        delay = cfg.get("delay_hours")
        try:
            return float(delay)
        except (TypeError, ValueError):
            return float(default_hours)

    def generate_sidecast_layers(
        self,
        *,
        arc_key: str,
        phase: str,
        scholar: Scholar,
        sponsor: str,
        expedition_type: Optional[str] = None,
        expedition_code: Optional[str] = None,
    ) -> SidecastPhasePlan:
        """Generate multi-layer press for a sidecast phase."""

        cfg = self._sidecast_phase_config(arc_key, phase)
        tone_seed = self._tone_seed("sidecast_followup")
        context_values = {
            "scholar": scholar.name,
            "sponsor": sponsor,
            "expedition_type": (expedition_type or "the expedition").replace("_", " "),
            "expedition_code": expedition_code or "the effort",
        }
        layers: List[PressLayer] = []

        gossip_entries = cfg.get("gossip") or []
        if gossip_entries:
            fast_pool = list(gossip_entries)
            random.shuffle(fast_pool)
            for idx, delay in enumerate([d for d in self.fast_layer_delays if d > 0][: len(fast_pool)]):
                template = fast_pool[idx]
                try:
                    quote = template.format(**context_values)
                except (KeyError, ValueError):
                    quote = template
                ctx = GossipContext(
                    scholar=scholar.name,
                    quote=quote,
                    trigger=f"Sidecast {phase.title()}",
                )
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="academic_gossip",
                        generator=academic_gossip,
                        context=ctx,
                        tone_seed=tone_seed,
                    )
                )

        briefs = cfg.get("briefs") or []
        if briefs:
            brief_entry = briefs[0]
            headline_tpl = brief_entry.get("headline")
            body_templates = brief_entry.get("body") or brief_entry.get("body_templates")

            def _default_headline() -> str:
                return f"Sidecast Spotlight — {scholar.name}"

            headline = self._render_template(headline_tpl, context_values, fallback=_default_headline)

            def _default_body() -> str:
                return brief_entry if isinstance(brief_entry, str) else ""

            body = self._render_template(body_templates, context_values, fallback=_default_body)
            metadata = {
                "arc": arc_key,
                "phase": phase,
                "sponsor": sponsor,
                "expedition_code": expedition_code,
                "expedition_type": expedition_type,
            }
            for delay in [d for d in self.long_layer_delays if d > 0] or [720]:
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="sidecast_brief",
                        generator=sidecast_brief,
                        context={
                            "headline": headline,
                            "body": body,
                            "metadata": metadata,
                            "persona": sponsor,
                            "type": "sidecast_brief",
                        },
                        tone_seed=tone_seed,
                    )
                )

        next_cfg = cfg.get("next") or {}
        next_phase = next_cfg.get("phase")
        next_delay = next_cfg.get("delay_hours")
        try:
            next_delay = float(next_delay) if next_delay is not None else None
        except (TypeError, ValueError):
            next_delay = None

        return SidecastPhasePlan(
            layers=layers,
            next_phase=next_phase,
            next_delay_hours=next_delay,
        )

    def generate_defection_epilogue_layers(
        self,
        *,
        scenario: str,
        scholar_name: str,
        former_faction: str,
        new_faction: str,
        former_employer: str,
    ) -> List[PressLayer]:
        """Generate narrative layers for defection epilogues."""

        template = self._defection_epilogues.get(scenario) or self._defection_epilogues.get("reconciliation", {})
        tone_seed = self._tone_seed("defection_epilogue")
        context_values = {
            "scholar": scholar_name,
            "former_faction": former_faction,
            "new_faction": new_faction,
            "former_employer": former_employer,
        }
        layers: List[PressLayer] = []

        primary = template.get("primary") or {}
        if primary:
            headline = primary.get("headline", "Defection Epilogue").format(**context_values)
            body_template = primary.get("body", "")
            try:
                body = body_template.format(**context_values)
            except (KeyError, ValueError):
                body = body_template
            metadata = {
                "scenario": scenario,
                "former_faction": former_faction,
                "new_faction": new_faction,
            }
            layers.append(
                PressLayer(
                    delay_minutes=0,
                    type="defection_epilogue",
                    generator=defection_epilogue_release,
                    context={
                        "headline": headline,
                        "body": body,
                        "metadata": metadata,
                        "type": "defection_epilogue",
                    },
                    tone_seed=tone_seed,
                )
            )

        gossip_entries = template.get("gossip") or []
        if gossip_entries:
            pool = list(gossip_entries)
            random.shuffle(pool)
            fast_delays = [d for d in self.fast_layer_delays if d > 0]
            for idx, template_text in enumerate(pool):
                delay = 0 if idx == 0 else fast_delays[min(idx - 1, len(fast_delays) - 1)] if fast_delays else 0
                template_text = pool[idx]
                try:
                    quote = template_text.format(**context_values)
                except (KeyError, ValueError):
                    quote = template_text
                ctx = GossipContext(
                    scholar=scholar_name,
                    quote=quote,
                    trigger=f"Defection {scenario}",
                )
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="academic_gossip",
                        generator=academic_gossip,
                        context=ctx,
                        tone_seed=tone_seed,
                    )
                )

        faction_brief = template.get("faction_brief") or {}
        if faction_brief:
            headline_tpl = faction_brief.get("headline")
            body_tpl = faction_brief.get("body")
            headline = headline_tpl.format(**context_values) if isinstance(headline_tpl, str) else "Faction Briefing"
            if isinstance(body_tpl, str):
                try:
                    body = body_tpl.format(**context_values)
                except (KeyError, ValueError):
                    body = body_tpl
            else:
                body = ""
            metadata = {
                "scenario": scenario,
                "former_faction": former_faction,
                "new_faction": new_faction,
            }
            layers.append(
                PressLayer(
                    delay_minutes=self.long_layer_delays[0] if self.long_layer_delays else 720,
                    type="defection_epilogue_brief",
                    generator=defection_epilogue_brief,
                    context={
                        "headline": headline,
                        "body": body,
                        "metadata": metadata,
                        "persona": former_employer,
                        "type": "defection_epilogue_brief",
                    },
                    tone_seed=tone_seed,
                )
            )

        return layers

    @staticmethod
    def _choose_option(
        options: Optional[Any],
        *,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Pick a random option from a string or list of strings."""

        if not options:
            return default
        if isinstance(options, str):
            return options
        if isinstance(options, list):
            candidates = [opt for opt in options if opt]
            if not candidates:
                return default
            return random.choice(candidates)
        return default

    def _render_template(
        self,
        templates: Optional[Any],
        context: Dict[str, Any],
        fallback: Optional[callable] = None,
    ) -> Optional[str]:
        """Render a template list/string with context, falling back if needed."""

        template = self._choose_option(templates)
        if template:
            try:
                return template.format(**context)
            except (KeyError, ValueError):
                pass
        if callable(fallback):
            return fallback()
        return fallback

    def _render_callouts(
        self,
        templates: Optional[Any],
        context: Dict[str, Any],
        limit: int = 2,
    ) -> List[str]:
        """Render a subset of callout templates."""

        if not templates:
            return []
        if isinstance(templates, str):
            templates = [templates]
        unique_templates = [tpl for tpl in templates if tpl]
        if not unique_templates:
            return []
        random.shuffle(unique_templates)
        rendered: List[str] = []
        for template in unique_templates[:limit]:
            try:
                rendered.append(template.format(**context))
            except (KeyError, ValueError):
                continue
        return rendered

    @property
    def setting(self) -> Optional[str]:
        return self._setting

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
            tone_seed = self._tone_seed("expedition_followup")
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
                    context=gossip_ctx,
                    tone_seed=tone_seed,
                ))

        # Breaking news gets additional analysis
        if depth == PressDepth.BREAKING:
            # Editorial/analysis piece (2 hours later)
            layers.append(self._generate_analysis_layer(
                expedition_ctx,
                outcome_ctx,
                delay_minutes=120,
                tone_seed=self._tone_seed("expedition_followup"),
            ))

            # Follow-up investigations (3 hours later)
            if outcome_ctx.result.sideways_discovery:
                layers.append(self._generate_investigation_layer(
                    outcome_ctx.result.sideways_discovery,
                    delay_minutes=180,
                    tone_seed=self._tone_seed("expedition_followup"),
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
            tone_seed = self._tone_seed("symposium_resolution")
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
                        tone_seed=tone_seed,
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
            tone_seed = self._tone_seed("symposium_resolution")
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
                        tone_seed=tone_seed,
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
                        tone_seed=tone_seed,
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
            tone_seed = self._tone_seed("defection_followup")
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
                    context=gossip_ctx,
                    tone_seed=tone_seed,
                ))

        # Extensive coverage includes institutional responses
        if depth in [PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Statement from old faction (2 hours later)
            layers.append(self._generate_faction_statement(
                old_faction,
                scholar.name,
                "regret",
                delay_minutes=120,
                tone_seed=self._tone_seed("defection_followup"),
            ))

            # Statement from new faction (2.5 hours later)
            layers.append(self._generate_faction_statement(
                defection_ctx.new_faction,
                scholar.name,
                "welcome",
                delay_minutes=150,
                tone_seed=self._tone_seed("defection_followup"),
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
            tone_seed = self._tone_seed("symposium_resolution")
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
                    context=gossip_ctx,
                    tone_seed=tone_seed,
                ))

        # Outcome announcement (1 hour later)
        if depth in [PressDepth.EXTENSIVE, PressDepth.BREAKING]:
            # Detailed outcome analysis
            layers.append(self._generate_conference_outcome(
                theory,
                outcome,
                reputation_changes,
                delay_minutes=60,
                tone_seed=self._tone_seed("symposium_resolution"),
            ))

        return layers

    def generate_mentorship_layers(
        self,
        *,
        mentor: str,
        scholar: Scholar,
        phase: str,
        track: Optional[str] = None,
    ) -> List[PressLayer]:
        """Generate layered coverage for mentorship lifecycle events."""

        layers: List[PressLayer] = []
        safe_fast = [delay for delay in self.fast_layer_delays if delay > 0]
        safe_long = [delay for delay in self.long_layer_delays if delay > 0]
        track_name = track or scholar.career.get("track", "Academia")
        templates = self._mentorship_templates or {}
        phases_cfg = templates.get("phases", {})
        phase_cfg = phases_cfg.get(phase, {})
        track_descriptor = self._resolve_track_descriptor(track_name)
        context_values = {
            "mentor": mentor,
            "scholar": scholar.name,
            "scholar_id": scholar.id,
            "track": track_name,
            "track_descriptor": track_descriptor,
        }

        fast_quotes = {
            "queued": [
                f"{mentor} promises to open hidden archives for {scholar.name}.",
                f"Assistants scramble to prepare {scholar.name}'s orientation dossier.",
            ],
            "activation": [
                f"{scholar.name} reports for their first session with {mentor}.",
                f"The {track_name} faculty clear space for the new protégé.",
            ],
            "progression": [
                f"{scholar.name}'s experiments draw praise from {mentor}.",
                f"Lab chatter says {scholar.name} cracked a vexing {track_name} puzzle.",
            ],
            "completion": [
                f"{mentor} applauds {scholar.name}'s graduation from the mentorship.",
                f"Peers toast {scholar.name}'s final colloquy with {mentor}.",
            ],
        }

        long_summaries = {
            "queued": (
                f"{mentor} outlines a rigorous on-boarding for {scholar.name},"
                f" blending fresh fieldwork with {track_name} theory."),
            "activation": (
                f"{scholar.name} begins daily workshops under {mentor},"
                f" mapping milestones for the {track_name} track."),
            "progression": (
                f"Progress reports note {scholar.name}'s breakthroughs and setbacks,"
                f" with {mentor} adjusting the syllabus in real time."),
            "completion": (
                f"The mentorship capstone highlights {scholar.name}'s signature contribution"
                f" to {track_name}, while {mentor} prepares the next cohort."),
        }

        tone_seed = self._tone_seed("mentorship_longform")
        fast_templates = phase_cfg.get("fast") or fast_quotes.get(phase, []) or []
        if fast_templates and safe_fast:
            fast_pool = list(fast_templates)
            random.shuffle(fast_pool)
            for idx, delay in enumerate(safe_fast):
                template = fast_pool[idx % len(fast_pool)]
                quote = template.format(**context_values)
                ctx = GossipContext(
                    scholar=mentor,
                    quote=quote,
                    trigger=f"Mentorship {phase}",
                )
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="academic_gossip",
                        generator=academic_gossip,
                        context=ctx,
                        tone_seed=tone_seed,
                    )
                )

        long_templates = phase_cfg.get("long") or ([] if long_summaries.get(phase) is None else [long_summaries.get(phase)])
        if long_templates and safe_long:
            headline_template = phase_cfg.get("headline", "Mentorship Briefing: {scholar}")
            headline = headline_template.format(**context_values)
            long_pool = list(long_templates)
            random.shuffle(long_pool)
            use_custom_templates = bool(phase_cfg.get("long"))
            for idx, delay in enumerate(safe_long):
                template = long_pool[idx % len(long_pool)]
                duration_text = self._format_delay(delay)
                if use_custom_templates:
                    body = template.format(**{**context_values, "duration": duration_text})
                else:
                    body = f"After {duration_text}, {template}"
                ctx = {
                    "headline": headline,
                    "body": body,
                    "metadata": {
                        "phase": phase,
                        "mentor": mentor,
                        "scholar": scholar.id,
                        "track": track_name,
                        "delay_minutes": delay,
                    },
                    "persona": mentor,
                }
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="mentorship_update",
                        generator=mentorship_update,
                        context=ctx,
                        tone_seed=tone_seed,
                    )
                )

        return layers

    def generate_recruitment_layers(
        self,
        *,
        player: str,
        scholar: Scholar,
        success: bool,
        faction: str,
        chance: float,
        observers: List[Scholar],
    ) -> List[PressLayer]:
        """Generate layered coverage for recruitment attempts."""

        layers: List[PressLayer] = []
        tone_seed = self._tone_seed("recruitment_followup")
        templates = (self._recruitment_templates or {}).get("recruitment", {})
        variant_key = "success" if success else "failure"

        safe_fast = [delay for delay in self.fast_layer_delays if delay > 0]
        audience = [obs for obs in observers if obs.id != scholar.id]
        random.shuffle(audience)
        reactions: List[Dict[str, str]] = []
        chance_pct = f"{chance:.0%}"
        outcome_text = "accepts" if success else "declines"
        outcome_label = "success" if success else "failure"

        reaction_templates = templates.get("reactions", {}).get(variant_key)

        for delay, observer in zip(safe_fast, audience[:4]):
            context = {
                "commentator": observer.name,
                "scholar": scholar.name,
                "player": player,
                "faction": faction,
                "chance_pct": chance_pct,
                "outcome": outcome_label,
                "outcome_verb": outcome_text,
            }
            quote = self._render_template(
                reaction_templates,
                context,
                fallback=lambda: self._generate_recruitment_quote(
                    commentator=observer.name,
                    scholar_name=scholar.name,
                    player_name=player,
                    faction=faction,
                    success=success,
                ),
            )
            if not quote:
                continue
            reactions.append({"scholar": observer.name, "quote": quote})
            ctx = GossipContext(
                scholar=observer.name,
                quote=quote,
                trigger=f"Recruitment of {scholar.name}",
            )
            layers.append(
                PressLayer(
                    delay_minutes=delay,
                    type="academic_gossip",
                    generator=academic_gossip,
                    context=ctx,
                    tone_seed=tone_seed,
                )
            )

        safe_long = [delay for delay in self.long_layer_delays if delay > 0]
        if safe_long:
            digest_cfg = templates.get("digest", {}).get(variant_key, {})
            reaction_lines = " | ".join(
                f"{item['scholar']}: {item['quote']}" for item in reactions
            )
            voices_text = reaction_lines or "No public reactions recorded."
            metadata = {
                "scholar": scholar.id,
                "player": player,
                "success": success,
                "chance": chance,
                "faction": faction,
                "reactions": reactions,
            }
            summary_context = {
                "scholar": scholar.name,
                "scholar_id": scholar.id,
                "player": player,
                "faction": faction,
                "faction_cap": faction.capitalize(),
                "chance_pct": chance_pct,
                "outcome": outcome_label,
                "outcome_verb": outcome_text,
                "voices": voices_text,
                "first_voice": reactions[0]["quote"] if reactions else "No immediate commentary",
                "callout_lines": "",
            }
            digest_headline = self._choose_option(
                digest_cfg.get("headlines"),
                default=f"Recruitment Round-Up: {scholar.name}",
            )
            digest_body_template = self._choose_option(
                digest_cfg.get("body_templates"),
                default=(
                    "Observers weigh in after {scholar} {outcome_verb} {player}'s "
                    "{faction} overtures (chance {chance_pct}).\nVoices: {voices}"
                ),
            )
            try:
                summary_body = digest_body_template.format(**summary_context)
            except (KeyError, ValueError):
                summary_body = (
                    f"Observers weigh in after {scholar.name} {outcome_text} {player}'s "
                    f"{faction} overtures (chance {chance_pct}).\nVoices: {voices_text}"
                )
            ctx = {
                "headline": digest_headline,
                "body": summary_body,
                "metadata": metadata,
                "persona": player,
                "type": "recruitment_followup",
            }
            layers.append(
                PressLayer(
                    delay_minutes=safe_long[0],
                    type="recruitment_followup",
                    generator=recruitment_followup,
                    context=ctx,
                    tone_seed=tone_seed,
                )
            )

            briefing_cfg = templates.get("briefing", {}).get(variant_key, {})
            callouts = self._render_callouts(
                briefing_cfg.get("callouts"),
                summary_context,
                limit=3,
            )
            if not callouts and reactions:
                callouts = [reactions[0]["quote"]]
            if not callouts:
                callouts = ["Await guidance from faction leads"]
            callout_lines = "\n".join(f"- {line}" for line in callouts)
            summary_context["callout_lines"] = callout_lines
            metadata["callouts"] = callouts
            faction_headline = self._choose_option(
                briefing_cfg.get("headlines"),
                default=f"Faction Briefing: {faction.capitalize()} eyes {scholar.name}",
            )
            briefing_body_template = self._choose_option(
                briefing_cfg.get("body_templates"),
                default=(
                    "Internal memos recap the approach to {scholar}.\n"
                    "Chance: {chance_pct}. Outcome: {outcome}.\nHighlights:\n{callout_lines}"
                ),
            )
            try:
                briefing_body = briefing_body_template.format(**summary_context)
            except (KeyError, ValueError):
                briefing_body = (
                    f"Internal memos recap the approach to {scholar.name}.\n"
                    f"Chance: {chance_pct}. Outcome: {outcome_label}.\n{callout_lines}"
                )
            briefing_metadata = {
                "scholar": scholar.id,
                "player": player,
                "success": success,
                "chance": chance,
                "faction": faction,
                "reactions": reactions,
                "briefing": True,
                "callouts": callouts,
            }
            briefing_ctx = {
                "headline": faction_headline,
                "body": briefing_body,
                "metadata": briefing_metadata,
                "persona": faction.capitalize(),
                "type": "recruitment_brief",
            }
            if len(safe_long) > 1:
                delay_minutes = safe_long[1]
            else:
                delay_minutes = safe_long[0] + 120
            layers.append(
                PressLayer(
                    delay_minutes=delay_minutes,
                    type="recruitment_brief",
                    generator=recruitment_brief,
                    context=briefing_ctx,
                    tone_seed=tone_seed,
                )
            )

        return layers

    def generate_table_talk_layers(
        self,
        *,
        speaker: str,
        message: str,
        scholars: List[Scholar],
    ) -> List[PressLayer]:
        """Generate layered reactions to a table-talk post."""

        layers: List[PressLayer] = []
        tone_seed = self._tone_seed("table_talk_followup")
        safe_fast = [delay for delay in self.fast_layer_delays if delay > 0]
        safe_long = [delay for delay in self.long_layer_delays if delay > 0]
        templates = (self._table_talk_templates or {}).get("table_talk", {})

        audience = scholars[:]
        random.shuffle(audience)
        reactions: List[Dict[str, str]] = []
        snippet = message if len(message) <= 120 else message[:117] + "..."
        topic_hint = message.splitlines()[0][:60] if message else "table talk"
        reaction_templates = templates.get("reactions")
        for delay, observer in zip(safe_fast, audience[:4]):
            context = {
                "commentator": observer.name,
                "speaker": speaker,
                "message": message,
                "snippet": snippet,
                "topic_hint": topic_hint,
            }
            quote = self._render_template(
                reaction_templates,
                context,
                fallback=lambda: self._generate_table_talk_reaction(
                    commentator=observer.name,
                    speaker=speaker,
                    message=message,
                ),
            )
            if not quote:
                continue
            reactions.append({"scholar": observer.name, "quote": quote})
            ctx = GossipContext(
                scholar=observer.name,
                quote=quote,
                trigger=f"Table talk from {speaker}",
            )
            layers.append(
                PressLayer(
                    delay_minutes=delay,
                    type="academic_gossip",
                    generator=academic_gossip,
                    context=ctx,
                    tone_seed=tone_seed,
                )
            )

        if safe_long:
            digest_cfg = templates.get("digest", {})
            digest_lines = [
                f"- {item['scholar']}: {item['quote']}" for item in reactions
            ]
            bullet_lines = "\n".join(digest_lines) if digest_lines else "- No immediate replies"
            digest_context = {
                "speaker": speaker,
                "message": message,
                "snippet": snippet,
                "bullet_lines": bullet_lines,
                "reactions": reactions,
                "topic_hint": topic_hint,
            }
            digest_headline = self._choose_option(
                digest_cfg.get("headlines"),
                default=f"Table Talk Digest — {speaker}",
            )
            digest_body_template = self._choose_option(
                digest_cfg.get("body_templates"),
                default=(
                    "{speaker}'s note '{snippet}' keeps the lounges buzzing.\n{bullet_lines}"
                ),
            )
            try:
                digest_body = digest_body_template.format(**digest_context)
            except (KeyError, ValueError):
                digest_body = (
                    f"{speaker}'s note '{snippet}' keeps the lounges buzzing.\n{bullet_lines}"
                )
            metadata = {
                "speaker": speaker,
                "message": snippet,
                "reactions": reactions,
            }
            ctx = {
                "headline": digest_headline,
                "body": digest_body,
                "metadata": metadata,
                "persona": speaker,
                "type": "table_talk_digest",
            }
            layers.append(
                PressLayer(
                    delay_minutes=safe_long[0],
                    type="table_talk_digest",
                    generator=table_talk_digest,
                    context=ctx,
                    tone_seed=tone_seed,
                )
            )

            roundup_cfg = templates.get("roundup", {})
            roundup_lines = "\n".join(
                f"• {item['scholar']}: {item['quote']}" for item in reactions[:4]
            ) or "• Commons quiet for now"
            roundup_context = {
                "speaker": speaker,
                "message": message,
                "snippet": snippet,
                "bullet_lines": roundup_lines,
                "topic_hint": topic_hint,
            }
            roundup_headline = self._choose_option(
                roundup_cfg.get("headlines"),
                default=f"Commons Roundup — Re: {speaker}",
            )
            roundup_body_template = self._choose_option(
                roundup_cfg.get("body_templates"),
                default="Whispers across the faculty warren:\n{bullet_lines}",
            )
            try:
                roundup_body = roundup_body_template.format(**roundup_context)
            except (KeyError, ValueError):
                roundup_body = f"Whispers across the faculty warren:\n{roundup_lines}"
            callouts = self._render_callouts(roundup_cfg.get("callouts"), roundup_context, limit=2)
            roundup_ctx = {
                "headline": roundup_headline,
                "body": roundup_body,
                "metadata": {
                    "speaker": speaker,
                    "message": snippet,
                    "reactions": reactions,
                    "type": "roundup",
                    "callouts": callouts,
                },
                "persona": "Commons Bulletin",
                "type": "table_talk_roundup",
            }
            delay_minutes = safe_long[1] if len(safe_long) > 1 else safe_long[0] + 60
            layers.append(
                PressLayer(
                    delay_minutes=delay_minutes,
                    type="table_talk_roundup",
                    generator=table_talk_roundup,
                    context=roundup_ctx,
                    tone_seed=tone_seed,
                )
            )

        return layers

    def generate_admin_layers(
        self,
        *,
        event: str,
        actor: Optional[str],
        reason: Optional[str] = None,
    ) -> List[PressLayer]:
        """Generate layered coverage for administrative events."""

        layers: List[PressLayer] = []
        persona = actor or "Operations Council"
        event_title = event.replace("_", " ").title()

        fast_messages = {
            "pause": [
                "Systems team initiates failover drills.",
                "Moderators catalogue which queues are safe to resume.",
            ],
            "resume": [
                "Bots signal that queued stories are warming back up.",
                "Archivists verify no records were lost during the pause.",
            ],
        }

        long_messages = {
            "pause": (
                "Operations publish a stabilization plan, outlining diagnostics,"
                " recovery checkpoints, and expectations for players awaiting narratives."
            ),
            "resume": (
                "A retrospective summarises the outage, remediation steps,"
                " and new safeguards for the narrative pipeline."
            ),
        }

        tone_seed = self._tone_seed("admin_recovery")
        quick_updates = fast_messages.get(event, [
            "Administrators coordinate the next steps.",
            "Players are reminded to monitor status channels.",
        ])

        safe_fast = [delay for delay in self.fast_layer_delays if delay > 0]
        for delay, message in zip(safe_fast, quick_updates):
            ctx = GossipContext(
                scholar=persona,
                quote=message,
                trigger=f"Admin {event_title}",
            )
            layers.append(
                PressLayer(
                    delay_minutes=delay,
                    type="admin_gossip",
                    generator=academic_gossip,
                    context=ctx,
                    tone_seed=tone_seed,
                )
            )

        long_message = long_messages.get(event)
        if long_message:
            safe_long = [delay for delay in self.long_layer_delays if delay > 0]
            for delay in safe_long:
                ctx = {
                    "headline": f"Administrative Update: {event_title}",
                    "body": long_message if not reason else f"{long_message}\nReason: {reason}",
                    "metadata": {
                        "event": event,
                        "actor": persona,
                        "reason": reason,
                        "delay_minutes": delay,
                    },
                    "persona": persona,
                    "type": "admin_update",
                }
                layers.append(
                    PressLayer(
                        delay_minutes=delay,
                        type="admin_update",
                        generator=admin_update,
                        context=ctx,
                        tone_seed=tone_seed,
                    )
                )

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

    def _generate_recruitment_quote(
        self,
        *,
        commentator: str,
        scholar_name: str,
        player_name: str,
        faction: str,
        success: bool,
    ) -> str:
        """Generate a follow-up quote reacting to recruitment news."""

        if success:
            options = [
                f"{scholar_name} joining {player_name} will tilt {faction} politics for months.",
                f"Rumour has it {player_name} promised prime {faction} resources to {scholar_name}.",
                f"{commentator} notes the halls are already rearranging to welcome {scholar_name}.",
                f"Everyone wonders if {player_name} can keep {scholar_name} inspired under {faction}'s banner.",
            ]
        else:
            options = [
                f"{scholar_name} spurning {player_name} leaves {faction} strategists rattled.",
                f"Some say {player_name} overplayed their hand trying to woo {scholar_name}.",
                f"{commentator} hears {scholar_name} demanded more than {faction} could promise.",
                f"The lab gossip is that {scholar_name} never intended to leave their current patron.",
            ]
        return random.choice(options)

    def _generate_table_talk_reaction(
        self,
        *,
        commentator: str,
        speaker: str,
        message: str,
    ) -> str:
        """Generate a fast reaction to a table-talk post."""

        sentiments = [
            f"{commentator} riffs on {speaker}'s note, calling it 'exactly the spark we needed'.",
            f"{commentator} wonders if {speaker}'s message hints at deeper symposium intrigue.",
            f"{commentator} challenges {speaker} to bring that table-talk energy to the next digest.",
            f"{commentator} shares the post with their lab, saying it captures the mood perfectly.",
            f"{commentator} jokes that {speaker}'s aside belongs in the Gazette proper.",
        ]
        if "?" in message:
            sentiments.append(
                f"{commentator} opens a thread to unpack the question {speaker} raised."
            )
        if len(message) > 120:
            sentiments.append(
                f"{commentator} summarises the lengthy missive from {speaker} for the busy scholars."
            )
        return random.choice(sentiments)

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
        delay_minutes: int,
        tone_seed: Optional[Dict[str, str]] = None,
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
            context={},
            tone_seed=tone_seed,
        )

    def _generate_investigation_layer(
        self,
        sideways_discovery: str,
        delay_minutes: int,
        tone_seed: Optional[Dict[str, str]] = None,
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
            context={},
            tone_seed=tone_seed,
        )

    def _generate_faction_statement(
        self,
        faction: str,
        scholar_name: str,
        tone: str,
        delay_minutes: int,
        tone_seed: Optional[Dict[str, str]] = None,
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
            context={},
            tone_seed=tone_seed,
        )

    def _generate_conference_outcome(
        self,
        theory: str,
        outcome: str,
        reputation_changes: Dict[str, int],
        delay_minutes: int,
        tone_seed: Optional[Dict[str, str]] = None,
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
            context={},
            tone_seed=tone_seed,
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
