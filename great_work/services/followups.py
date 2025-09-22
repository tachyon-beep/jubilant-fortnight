"""Follow-up and reminder helpers."""

from __future__ import annotations


def build_symposium_reminder_body(
    *,
    player_display: str,
    topic: str,
    reminder_level: str,
    pledged_amount: int,
    grace_remaining: int,
) -> str:
    """Compose the reminder body text for symposium voting.

    reminder_level: "first" or "escalation".
    """

    if reminder_level == "escalation":
        return (
            f"{player_display}, the Academy notes you have not yet cast a vote on "
            f"'{topic}'. Missing this symposium will forfeit {pledged_amount} influence. "
            "Use /symposium_vote before resolution to keep your pledge intact."
        )

    if grace_remaining > 0:
        plural = "s" if grace_remaining != 1 else ""
        grace_text = f"You have {grace_remaining} grace miss{plural} remaining; voting preserves it."
    else:
        grace_text = f"You are out of grace—silence will cost {pledged_amount} influence."
    return (
        f"{player_display} is requested to cast a vote on '{topic}'. "
        f"{grace_text} Use /symposium_vote to weigh in."
    )


__all__ = ["build_symposium_reminder_body"]

from typing import Dict, Any, List, Optional
from ..models import PressRelease, Event
from ..press import GossipContext, academic_gossip
from ..services.narrative import (
    generate_defection_epilogue_layers as _mp_defection_epilogue_layers,
    generate_sidecast_layers as _mp_sidecast_layers,
)


def build_symposium_reprimand_press(
    *,
    display_name: str,
    faction: str,
    penalty_influence: int,
    penalty_reputation: int,
    reprisal_level: int,
    remaining: int,
    player_id: str,
) -> PressRelease:
    headline = f"Symposium Reprimand: {display_name}".rstrip()
    impacts = []
    if penalty_influence:
        impacts.append(f"{penalty_influence} influence seized by {faction}")
    if penalty_reputation:
        impacts.append(f"{penalty_reputation} reputation deducted")
    impact_text = "; ".join(impacts) if impacts else "Public reprimand issued"
    body = (
        f"{display_name} faces a symposium reprisal from {faction}. {impact_text}. "
        f"Outstanding debt: {remaining}. Reprisal level now {reprisal_level}."
    )
    return PressRelease(
        type="symposium_reprimand",
        headline=headline,
        body=body,
        metadata={
            "player_id": player_id,
            "faction": faction,
            "reprisal_level": reprisal_level,
            "remaining": remaining,
            "penalty_influence": penalty_influence,
            "penalty_reputation": penalty_reputation,
        },
    )


# Simple follow-up message registry ------------------------------------------

_FOLLOWUP_QUOTES = {
    "evaluate_offer": "The negotiation deadline has arrived.",
    "evaluate_counter": "The counter-offer awaits final resolution.",
}


def followup_quote(kind: str, payload: Dict[str, Any]) -> str:
    """Return a default quote/message for a follow-up kind.

    Payload is available for future handlers that want to format richer messages.
    """

    return _FOLLOWUP_QUOTES.get(kind, "An unresolved thread lingers in the archives.")


# Registry-based dispatch ------------------------------------------------------

def _handle_symposium_reprimand(service, now, followup_id: int, scholar_id: str, payload: Dict[str, Any]) -> list[PressRelease]:
    player_record = service.state.get_player(scholar_id)
    display_name = payload.get("display_name") or (
        player_record.display_name if player_record else scholar_id
    )
    faction = payload.get("faction", "the Academy")
    penalty_influence = int(payload.get("penalty_influence", 0))
    penalty_reputation = int(payload.get("penalty_reputation", 0))
    reprisal_level = int(payload.get("reprisal_level", 1))
    remaining = int(payload.get("remaining", 0))
    press = build_symposium_reprimand_press(
        display_name=display_name,
        faction=faction,
        penalty_influence=penalty_influence,
        penalty_reputation=penalty_reputation,
        reprisal_level=reprisal_level,
        remaining=remaining,
        player_id=str(payload.get("player_id") or scholar_id),
    )
    service._archive_press(press, now)
    service.state.append_event(
        Event(
            timestamp=now,
            action="symposium_reprimand",
            payload={
                "player": payload.get("player_id") or scholar_id,
                "faction": faction,
                "reprisal_level": reprisal_level,
                "remaining": remaining,
            },
        )
    )
    service.state.clear_followup(
        followup_id,
        result={"resolution": "symposium_reprimand"},
    )
    return [press]


def _handle_offer_resolution(service, now, followup_id: int, scholar_id: str, payload: Dict[str, Any], key: str) -> list[PressRelease] | None:
    offer_id = payload.get(key)
    if not offer_id:
        return None
    releases = service.resolve_offer_negotiation(offer_id)
    service.state.clear_followup(
        followup_id,
        result={"resolution": "offer_negotiation" if key == "offer_id" else "counter_negotiation"},
    )
    return releases


def dispatch_followup(service, now, followup_id: int, scholar_id: str, kind: str, payload: Dict[str, Any]) -> list[PressRelease] | None:
    """Dispatch follow-up handling to registered handlers. Returns None if unhandled."""

    if kind == "symposium_reprimand":
        return _handle_symposium_reprimand(service, now, followup_id, scholar_id, payload)
    if kind == "evaluate_offer":
        return _handle_offer_resolution(service, now, followup_id, scholar_id, payload, key="offer_id")
    if kind == "evaluate_counter":
        return _handle_offer_resolution(service, now, followup_id, scholar_id, payload, key="counter_offer_id")
    if kind in {"defection_grudge", "defection_return"}:
        return _handle_defection_epilogue(service, now, followup_id, scholar_id, kind, payload)
    if kind.startswith("sidecast_"):
        return _handle_sidecast_phase(service, now, followup_id, scholar_id, kind, payload)
    if kind == "sideways_vignette":
        return _handle_sideways_vignette(service, now, followup_id, scholar_id, payload)
    if kind == "recruitment_grudge":
        return _handle_recruitment_grudge(service, now, followup_id, scholar_id, payload)
    return None


def _handle_defection_epilogue(service, now, followup_id: int, scholar_id: str, kind: str, payload: Dict[str, Any]) -> Optional[List[PressRelease]]:
    scholar = service.state.get_scholar(scholar_id)
    if not scholar:
        service.state.clear_followup(followup_id, status="cancelled", result={"reason": "scholar_missing"})
        return []
    scenario = payload.get("scenario")
    if kind == "defection_grudge":
        scenario = scenario or "rivalry"
    else:
        scenario = scenario or "reconciliation"

    former_employer_id = (
        payload.get("former_employer")
        or scholar.contract.get("sidecast_sponsor")
        or scholar.contract.get("employer")
    )
    former_employer = service.state.get_player(former_employer_id)
    former_name = former_employer.display_name if former_employer else (former_employer_id or "their patron")

    if scenario == "reconciliation":
        scholar.memory.adjust_feeling(former_employer_id or "patron", 1.5)
        if former_employer_id:
            scholar.contract["employer"] = former_employer_id
    else:
        new_faction = (
            payload.get("new_faction")
            or payload.get("faction")
            or scholar.contract.get("employer", "Unknown")
        )
        scholar.memory.adjust_feeling(new_faction, -1.5)

    new_faction_name = (
        payload.get("new_faction")
        or payload.get("faction")
        or scholar.contract.get("employer", "Unknown")
    )

    layers = _mp_defection_epilogue_layers(
        service._multi_press,
        scenario=scenario,
        scholar_name=scholar.name,
        former_faction=former_name,
        new_faction=new_faction_name,
        former_employer=former_name,
    )
    immediate_layers = service._apply_multi_press_layers(
        layers,
        skip_types=set(),
        timestamp=now,
        event_type="defection_epilogue",
    )
    releases = list(immediate_layers)
    service.state.append_event(
        Event(
            timestamp=now,
            action="defection_epilogue",
            payload={
                "scholar": scholar.id,
                "scenario": scenario,
                "former_faction": former_name,
                "new_faction": new_faction_name,
            },
        )
    )
    service.state.save_scholar(scholar)
    service.state.clear_followup(
        followup_id,
        result={"resolution": f"defection_{scenario}"},
    )
    return releases


def _handle_sidecast_phase(service, now, followup_id: int, scholar_id: str, kind: str, payload: Dict[str, Any]) -> Optional[List[PressRelease]]:
    scholar = service.state.get_scholar(scholar_id)
    if not scholar:
        service.state.clear_followup(
            followup_id,
            status="cancelled",
            result={"reason": "scholar_missing"},
        )
        return []
    arc_key = payload.get("arc") or scholar.contract.get("sidecast_arc") or service._multi_press.pick_sidecast_arc()
    phase = payload.get("phase") or kind.split("_", 1)[1]
    sponsor_id = payload.get("sponsor") or scholar.contract.get("sidecast_sponsor")
    sponsor_player = service.state.get_player(sponsor_id) if sponsor_id else None
    sponsor_display = sponsor_player.display_name if sponsor_player else (sponsor_id or "Patron")
    expedition_type = payload.get("expedition_type")
    expedition_code = payload.get("expedition_code")

    plan = _mp_sidecast_layers(
        service._multi_press,
        arc_key=arc_key,
        phase=phase,
        scholar=scholar,
        sponsor=sponsor_display,
        expedition_type=expedition_type,
        expedition_code=expedition_code,
    )

    service._record_sidecast_memory(
        scholar,
        sponsor_id,
        arc=arc_key,
        phase=phase,
        timestamp=now,
        extra={
            "expedition_code": expedition_code,
            "expedition_type": expedition_type,
        },
    )
    service.state.save_scholar(scholar)

    immediate_layers = service._apply_multi_press_layers(
        plan.layers, skip_types=set(), timestamp=now, event_type="sidecast"
    )
    releases = list(immediate_layers)

    service.state.append_event(
        Event(
            timestamp=now,
            action="sidecast_followup",
            payload={
                "scholar": scholar.id,
                "arc": arc_key,
                "phase": phase,
                "sponsor": sponsor_id,
            },
        )
    )
    service.state.clear_followup(
        followup_id,
        result={"resolution": f"sidecast_{phase}"},
    )

    if getattr(plan, "next_phase", None):
        next_delay = getattr(plan, "next_delay_hours", None)
        if next_delay is None:
            next_delay = service._multi_press.sidecast_phase_delay(
                arc_key, plan.next_phase, default_hours=36.0
            )
        from datetime import timedelta as _td
        scheduled_at = now + _td(hours=next_delay)
        service.state.enqueue_order(
            f"followup:sidecast_{plan.next_phase}",
            actor_id=scholar.id,
            subject_id=sponsor_id,
            payload={
                "arc": arc_key,
                "phase": plan.next_phase,
                "sponsor": sponsor_id,
                "expedition_code": expedition_code,
                "expedition_type": expedition_type,
            },
            scheduled_at=scheduled_at,
        )
    return releases


def _handle_sideways_vignette(service, now, followup_id: int, scholar_id: str, payload: Dict[str, Any]) -> Optional[List[PressRelease]]:
    scholar = service.state.get_scholar(scholar_id)
    if not scholar:
        service.state.clear_followup(
            followup_id,
            status="cancelled",
            result={"reason": "scholar_missing"},
        )
        return []
    headline = payload.get("headline", f"Sideways Vignette — {scholar.name}")
    body = payload.get("body", "")
    tags = payload.get("tags", [])
    base_press = PressRelease(
        type="sideways_vignette",
        headline=headline,
        body=body,
        metadata={
            "scholar": scholar.id,
            "tags": tags,
            "discovery": payload.get("discovery"),
        },
    )
    service._archive_press(base_press, now)
    releases: List[PressRelease] = [base_press]
    for quote in payload.get("gossip") or []:
        ctx = GossipContext(scholar=scholar.name, quote=quote, trigger="Sideways Discovery")
        gossip_press = academic_gossip(ctx)
        service._archive_press(gossip_press, now)
        releases.append(gossip_press)
    service.state.append_event(
        Event(
            timestamp=now,
            action="sideways_vignette",
            payload={"scholar": scholar.id, "headline": headline, "tags": tags},
        )
    )
    service.state.clear_followup(
        followup_id,
        result={"resolution": "sideways_vignette"},
    )
    return releases


def _handle_recruitment_grudge(service, now, followup_id: int, scholar_id: str, payload: Dict[str, Any]) -> Optional[List[PressRelease]]:
    scholar = service.state.get_scholar(scholar_id)
    if not scholar:
        service.state.clear_followup(
            followup_id,
            status="cancelled",
            result={"reason": "scholar_missing"},
        )
        return []
    player_id = payload.get("player", "Unknown")
    scholar.memory.adjust_feeling(player_id, -1.0)
    quote = _FOLLOWUP_QUOTES.get("recruitment_grudge", "The slighted scholar sharpens their public retort.")
    ctx = GossipContext(scholar=scholar.name, quote=quote, trigger="Recruitment Grudge")
    press = academic_gossip(ctx)
    service._archive_press(press, now)
    service.state.append_event(
        Event(
            timestamp=now,
            action="followup_resolved",
            payload={"scholar": scholar.id, "kind": "recruitment_grudge", "order_id": followup_id},
        )
    )
    service.state.save_scholar(scholar)
    service.state.clear_followup(followup_id, result={"resolution": "recruitment_grudge"})
    return [press]
