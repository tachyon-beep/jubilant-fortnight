"""Generate sample previews for narrative YAML assets."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

from .validate_narrative import (
    CANONICAL_PATHS,
    _load_yaml,
)


class SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


SAMPLE_CONTEXT: Dict[str, str] = {
    "player": "Archivist Cael",
    "scholar": "Dr Lyra Anselm",
    "sponsor": "Mentor Hal",
    "mentor": "Mentor Hal",
    "track_descriptor": "astral navigation labs",
    "treatise": "Treatise on Skyward Leylines",
    "hall": "Grand Loggia",
    "artifact": "stellar compass",
    "city": "Florence",
    "expedition_code": "EX-42",
    "expedition_type": "field",
    "persona": "Operator Sol",
    "deadline": "dawn bell",
    "hours": "12",
    "minutes": "45",
    "relative_time": "2 hours",
    "count": "3",
    "option": "Further Study",
    "vote_share": "64",
    "analyst": "Scholar Brynn",
    "voices": "Commentator A; Commentator B",
    "call_to_action": "Scribes prepare the mezzanine",
    "chance_pct": "42%",
    "outcome_verb": "accepts",
    "outcome": "accepted",
    "faction": "Academia",
    "new_faction": "Industry",
    "former_faction": "Academia",
    "former_employer": "Dean Rowan",
    "commentator": "Analyst Mirelle",
    "speaker": "Scholar Idris",
    "topic_hint": "relic interference",
    "snippet": "Hidden archive seals cracked at dusk",
    "bullet_lines": "- Courtiers whisper about the findings\n- Archivists petition for public release",
    "callout_lines": "- Prepare reception in the Grand Hall\n- Assign liaison to new recruit",
    "summary": "New layers of the dig yield intact archives",
    "prep_depth_title": "Deep",
    "prep_depth_title_lower": "deep",
    "strengths_text": "think tank modelling +8; field oversight +4",
    "frictions_text": "site friction -3",
    "team_summary": "Dr Lyra Anselm, Scholar Idris",
}


def _fmt(text: str, context: Dict[str, str]) -> str:
    return text.format_map(SafeDict(context))


def preview_press_tone_packs(data: Any) -> List[str]:
    lines: List[str] = ["== Tone Packs =="]
    settings = data.get("settings", {})
    for pack_name, pack in settings.items():
        lines.append(f"-- {pack_name} --")
        for section, values in pack.items():
            if not isinstance(values, dict):
                continue
            headline = values.get("headline") or values.get("headlines")
            body = values.get("blurb") or values.get("blurb_template")
            callout = values.get("callout")
            if headline:
                lines.append("headline: " + _fmt(str(headline[0]), SAMPLE_CONTEXT))
            if body:
                lines.append("body: " + _fmt(str(body[0]), SAMPLE_CONTEXT))
            if callout:
                lines.append("callout: " + _fmt(str(callout[0]), SAMPLE_CONTEXT))
        lines.append("")
    return lines


def preview_recruitment(data: Any) -> List[str]:
    lines = ["== Recruitment Press =="]
    root = data.get("recruitment", {})
    digest = root.get("digest", {})
    for outcome in ("success", "failure"):
        section = digest.get(outcome)
        if not section:
            continue
        lines.append(f"[{outcome.title()} Digest]")
        headline = section.get("headlines", [None])[0]
        body = section.get("body_templates", [None])[0]
        if headline:
            lines.append(_fmt(headline, SAMPLE_CONTEXT))
        if body:
            lines.append(_fmt(body, SAMPLE_CONTEXT))
        lines.append("")
    return lines


def preview_table_talk(data: Any) -> List[str]:
    lines = ["== Table Talk =="]
    root = data.get("table_talk", {})
    digest = root.get("digest", {})
    headlines = digest.get("headlines", [None])[0]
    bodies = digest.get("body_templates", [None])[0]
    if headlines:
        lines.append(_fmt(headlines, SAMPLE_CONTEXT))
    if bodies:
        lines.append(_fmt(bodies, SAMPLE_CONTEXT))
    lines.append("")
    return lines


def preview_mentorship(data: Any) -> List[str]:
    lines = ["== Mentorship Beats =="]
    phases = data.get("phases", {})
    for phase, content in phases.items():
        fast = content.get("fast", [None])[0]
        long = content.get("long", [None])[0]
        lines.append(f"[{phase}]")
        if fast:
            lines.append("fast: " + _fmt(fast, SAMPLE_CONTEXT))
        if long:
            lines.append("long: " + _fmt(long, SAMPLE_CONTEXT))
        lines.append("")
    return lines


def preview_sidecast(data: Any) -> List[str]:
    lines = ["== Sidecast Arcs =="]
    arcs = data.get("sidecasts", {})
    for arc_name, arc in arcs.items():
        lines.append(f"-- {arc_name} ({arc.get('label', 'Arc')}) --")
        phases = arc.get("phases", {})
        for phase_name, phase_data in phases.items():
            gossip = phase_data.get("gossip", [None])[0]
            brief = None
            briefs = phase_data.get("briefs", [])
            if briefs:
                brief = briefs[0]
            lines.append(f"[{phase_name}]")
            if gossip:
                lines.append("gossip: " + _fmt(gossip, SAMPLE_CONTEXT))
            if isinstance(brief, dict):
                headline = brief.get("headline")
                body = brief.get("body")
                if headline:
                    lines.append("headline: " + _fmt(headline, SAMPLE_CONTEXT))
                if body:
                    lines.append(_fmt(body, SAMPLE_CONTEXT))
            lines.append("")
        break
    return lines


def preview_epilogues(data: Any) -> List[str]:
    lines = ["== Defection Epilogues =="]
    epilogues = data.get("epilogues", {})
    for name, entry in epilogues.items():
        lines.append(f"-- {name} --")
        primary = entry.get("primary", {})
        if primary:
            lines.append(_fmt(primary.get("headline", ""), SAMPLE_CONTEXT))
            lines.append(_fmt(primary.get("body", ""), SAMPLE_CONTEXT))
        gossip = entry.get("gossip", [None])[0]
        if gossip:
            lines.append("gossip: " + _fmt(gossip, SAMPLE_CONTEXT))
        brief = entry.get("faction_brief", {})
        if brief:
            lines.append(_fmt(brief.get("headline", ""), SAMPLE_CONTEXT))
            lines.append(_fmt(brief.get("body", ""), SAMPLE_CONTEXT))
        lines.append("")
        break
    return lines


def preview_vignettes(data: Any) -> List[str]:
    lines = ["== Sideways Vignettes =="]
    categories = data.get("vignettes", {})
    for category, depths in categories.items():
        for depth, entries in depths.items():
            if not entries:
                continue
            sample = entries[0]
            lines.append(f"-- {category} / {depth} --")
            lines.append(_fmt(sample.get("headline", ""), SAMPLE_CONTEXT))
            lines.append(_fmt(sample.get("body", ""), SAMPLE_CONTEXT))
            gossip = sample.get("gossip")
            if gossip:
                lines.append("gossip: " + _fmt(gossip[0], SAMPLE_CONTEXT))
            lines.append("tags: " + ", ".join(sample.get("tags", [])))
            lines.append("")
            break
        break
    return lines


def preview_landmark_preparations(data: Any) -> List[str]:
    lines = ["== Landmark Preparations =="]
    root = data.get("landmark_preparations", {}) if isinstance(data, dict) else {}
    for expedition_type, depths in root.items():
        if not isinstance(depths, dict):
            continue
        for depth, entry in depths.items():
            if not isinstance(entry, dict):
                continue
            lines.append(f"-- {expedition_type} / {depth} --")
            discoveries = entry.get("discoveries")
            if isinstance(discoveries, list) and discoveries:
                lines.append("discovery: " + _fmt(str(discoveries[0]), SAMPLE_CONTEXT))
            briefs = entry.get("briefs")
            if isinstance(briefs, list) and briefs:
                brief = briefs[0]
                headline = brief.get("headline")
                body = brief.get("body")
                if headline:
                    lines.append("headline: " + _fmt(str(headline), SAMPLE_CONTEXT))
                if body:
                    lines.append(_fmt(str(body), SAMPLE_CONTEXT))
            lines.append("")
            break
        break
    return lines


PREVIEWERS = {
    "tone-packs": (Path("great_work/data/press_tone_packs.yaml"), preview_press_tone_packs),
    "recruitment": (Path("great_work/data/recruitment_press.yaml"), preview_recruitment),
    "table-talk": (Path("great_work/data/table_talk_press.yaml"), preview_table_talk),
    "mentorship": (Path("great_work/data/mentorship_press.yaml"), preview_mentorship),
    "sidecasts": (Path("great_work/data/sidecast_arcs.yaml"), preview_sidecast),
    "epilogues": (Path("great_work/data/defection_epilogues.yaml"), preview_epilogues),
    "vignettes": (Path("great_work/data/sideways_vignettes.yaml"), preview_vignettes),
    "landmark-prep": (Path("great_work/data/landmark_preparations.yaml"), preview_landmark_preparations),
}


def run_previewer(name: str) -> List[str]:
    if name not in PREVIEWERS:
        raise KeyError(name)
    path, renderer = PREVIEWERS[name]
    data = _load_yaml(path)
    return renderer(data)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render sample previews for narrative YAML")
    parser.add_argument(
        "surface",
        nargs="*",
        help="Surface keys to preview (e.g., tone-packs, recruitment). Defaults to all.",
    )

    args = parser.parse_args(argv)
    targets = args.surface or list(PREVIEWERS.keys())
    for name in targets:
        if name not in PREVIEWERS:
            print(f"Unknown surface '{name}'. Available: {', '.join(PREVIEWERS)}")
            return 1

    for name in targets:
        for line in run_previewer(name):
            print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
