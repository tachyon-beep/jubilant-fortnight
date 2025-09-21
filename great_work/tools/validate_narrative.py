"""Validate narrative YAML assets for structure and required fields."""
from __future__ import annotations

import argparse
import sys
from numbers import Real
from pathlib import Path
from typing import Any, List, Sequence

import yaml

DEFAULT_FILES = [
    Path("great_work/data/press_tone_packs.yaml"),
    Path("great_work/data/recruitment_press.yaml"),
    Path("great_work/data/table_talk_press.yaml"),
    Path("great_work/data/mentorship_press.yaml"),
    Path("great_work/data/sidecast_arcs.yaml"),
    Path("great_work/data/defection_epilogues.yaml"),
    Path("great_work/data/sideways_vignettes.yaml"),
    Path("great_work/data/landmark_preparations.yaml"),
]


def _load_yaml(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except Exception as exc:  # pragma: no cover - failure path
        raise ValueError(f"Failed to load {path}: {exc}") from exc


def _ensure_non_empty_list(value: Any, path: Path, context: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(value, list) or not value:
        errors.append(f"{path}: {context} must be a non-empty list")
        return errors
    for idx, element in enumerate(value):
        if not isinstance(element, str) or not element.strip():
            errors.append(f"{path}: {context}[{idx}] must be a non-empty string")
    return errors


def _ensure_mapping(value: Any, path: Path, context: str) -> List[str]:
    if not isinstance(value, dict):
        return [f"{path}: {context} must be a mapping"]
    return []


def validate_press_tone_packs(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict) or "settings" not in data:
        return [f"{path}: top-level 'settings' mapping is required"]

    settings = data["settings"]
    if not isinstance(settings, dict) or not settings:
        return [f"{path}: 'settings' must be a non-empty mapping"]

    sections = {
        "digest_highlight": {"headline": True, "blurb_template": True, "callout": True},
        "expedition_followup": {"headline": True, "blurb": True, "callout": True},
        "mentorship_longform": {"headline": True, "blurb": True, "callout": True},
        "defection_followup": {"headline": True, "blurb": True, "callout": True},
        "defection_epilogue": {"headline": True, "blurb": True, "callout": True},
        "symposium_resolution": {"headline": True, "blurb": True, "callout": True},
        "admin_recovery": {"headline": True, "blurb": True, "callout": True},
        "sidecast_followup": {"headline": True, "blurb": True, "callout": True},
        "sideways_vignette": {"headline": True, "blurb": True, "callout": True},
    }

    for pack_name, pack_data in settings.items():
        context = f"settings.{pack_name}"
        if not isinstance(pack_data, dict):
            errors.append(f"{path}: {context} must be a mapping")
            continue
        for section, required in sections.items():
            if section not in pack_data:
                continue
            section_data = pack_data[section]
            if not isinstance(section_data, dict):
                errors.append(f"{path}: {context}.{section} must be a mapping")
                continue
            for key, mandatory in required.items():
                if key in section_data:
                    errors.extend(
                        _ensure_non_empty_list(
                            section_data[key], path, f"{context}.{section}.{key}"
                        )
                    )
                elif mandatory:
                    errors.append(
                        f"{path}: {context}.{section} missing required '{key}' list"
                    )
        # Warn on empty optional sections
        for section, section_data in pack_data.items():
            if isinstance(section_data, dict):
                for list_key, value in section_data.items():
                    if isinstance(value, list) and not value:
                        errors.append(
                            f"{path}: {context}.{section}.{list_key} should not be empty"
                        )
    return errors


def validate_recruitment_press(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("recruitment") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return [f"{path}: expected top-level 'recruitment' mapping"]

    reactions = root.get("reactions")
    if not isinstance(reactions, dict):
        errors.append(f"{path}: recruitment.reactions must be a mapping")
    else:
        for outcome in ("success", "failure"):
            errors.extend(
                _ensure_non_empty_list(
                    reactions.get(outcome), path, f"recruitment.reactions.{outcome}"
                )
            )

    digest = root.get("digest")
    if not isinstance(digest, dict):
        errors.append(f"{path}: recruitment.digest must be a mapping")
    else:
        for outcome in ("success", "failure"):
            section = digest.get(outcome)
            if not isinstance(section, dict):
                errors.append(f"{path}: recruitment.digest.{outcome} must be a mapping")
                continue
            errors.extend(
                _ensure_non_empty_list(
                    section.get("headlines"),
                    path,
                    f"recruitment.digest.{outcome}.headlines",
                )
            )
            errors.extend(
                _ensure_non_empty_list(
                    section.get("body_templates"),
                    path,
                    f"recruitment.digest.{outcome}.body_templates",
                )
            )

    briefing = root.get("briefing")
    if not isinstance(briefing, dict):
        errors.append(f"{path}: recruitment.briefing must be a mapping")
    else:
        for outcome in ("success", "failure"):
            section = briefing.get(outcome)
            if not isinstance(section, dict):
                errors.append(f"{path}: recruitment.briefing.{outcome} must be a mapping")
                continue
            errors.extend(
                _ensure_non_empty_list(
                    section.get("headlines"),
                    path,
                    f"recruitment.briefing.{outcome}.headlines",
                )
            )
            errors.extend(
                _ensure_non_empty_list(
                    section.get("body_templates"),
                    path,
                    f"recruitment.briefing.{outcome}.body_templates",
                )
            )
            errors.extend(
                _ensure_non_empty_list(
                    section.get("callouts"),
                    path,
                    f"recruitment.briefing.{outcome}.callouts",
                )
            )
    return errors


def validate_table_talk_press(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("table_talk") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return [f"{path}: expected top-level 'table_talk' mapping"]

    errors.extend(
        _ensure_non_empty_list(root.get("reactions"), path, "table_talk.reactions")
    )

    for section_name in ("digest", "roundup"):
        section = root.get(section_name)
        if not isinstance(section, dict):
            errors.append(f"{path}: table_talk.{section_name} must be a mapping")
            continue
        errors.extend(
            _ensure_non_empty_list(
                section.get("headlines"), path, f"table_talk.{section_name}.headlines"
            )
        )
        errors.extend(
            _ensure_non_empty_list(
                section.get("body_templates"),
                path,
                f"table_talk.{section_name}.body_templates",
            )
        )
        if section_name == "roundup":
            errors.extend(
                _ensure_non_empty_list(
                    section.get("callouts"),
                    path,
                    "table_talk.roundup.callouts",
                )
            )
    return errors


def validate_landmark_preparations(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("landmark_preparations") if isinstance(data, dict) else None
    if not isinstance(root, dict) or not root:
        return [f"{path}: expected non-empty 'landmark_preparations' mapping"]

    for expedition_type, depth_map in root.items():
        context = f"landmark_preparations.{expedition_type}"
        if not isinstance(depth_map, dict) or not depth_map:
            errors.append(f"{path}: {context} must be a non-empty mapping")
            continue
        for depth, entry in depth_map.items():
            entry_ctx = f"{context}.{depth}"
            if not isinstance(entry, dict):
                errors.append(f"{path}: {entry_ctx} must be a mapping")
                continue

            discoveries = entry.get("discoveries")
            if discoveries is not None:
                errors.extend(_ensure_non_empty_list(discoveries, path, f"{entry_ctx}.discoveries"))

            briefs = entry.get("briefs")
            if briefs is not None:
                if not isinstance(briefs, list) or not briefs:
                    errors.append(f"{path}: {entry_ctx}.briefs must be a non-empty list")
                else:
                    for index, brief in enumerate(briefs):
                        brief_ctx = f"{entry_ctx}.briefs[{index}]"
                        if not isinstance(brief, dict):
                            errors.append(f"{path}: {brief_ctx} must be a mapping")
                            continue
                        headline = brief.get("headline")
                        body = brief.get("body")
                        if not isinstance(headline, str) or not headline.strip():
                            errors.append(f"{path}: {brief_ctx}.headline must be a non-empty string")
                        if not isinstance(body, str) or not body.strip():
                            errors.append(f"{path}: {brief_ctx}.body must be a non-empty string")

            if discoveries is None and briefs is None:
                errors.append(f"{path}: {entry_ctx} must define 'discoveries' or 'briefs'")

    return errors


def validate_mentorship_press(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    phases = data.get("phases") if isinstance(data, dict) else None
    if not isinstance(phases, dict) or not phases:
        errors.append(f"{path}: top-level 'phases' mapping is required")
    else:
        for phase_name, phase_data in phases.items():
            if not isinstance(phase_data, dict):
                errors.append(f"{path}: phases.{phase_name} must be a mapping")
                continue
            for key in ("fast", "long"):
                errors.extend(
                    _ensure_non_empty_list(
                        phase_data.get(key), path, f"phases.{phase_name}.{key}"
                    )
                )

    tracks = data.get("tracks") if isinstance(data, dict) else None
    if not isinstance(tracks, dict) or not tracks:
        errors.append(f"{path}: top-level 'tracks' mapping is required")
    else:
        for track_name, track_data in tracks.items():
            if not isinstance(track_data, dict) or "descriptor" not in track_data:
                errors.append(
                    f"{path}: tracks.{track_name} must provide a 'descriptor' string"
                )
            else:
                descriptor = track_data["descriptor"]
                if not isinstance(descriptor, str) or not descriptor.strip():
                    errors.append(
                        f"{path}: tracks.{track_name}.descriptor must be a non-empty string"
                    )
    return errors


def validate_sidecast_arcs(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("sidecasts") if isinstance(data, dict) else None
    if not isinstance(root, dict) or not root:
        return [f"{path}: top-level 'sidecasts' mapping is required"]

    for arc_name, arc_data in root.items():
        context = f"sidecasts.{arc_name}"
        if not isinstance(arc_data, dict):
            errors.append(f"{path}: {context} must be a mapping")
            continue
        if "label" not in arc_data or not isinstance(arc_data["label"], str):
            errors.append(f"{path}: {context}.label must be a string")
        phases = arc_data.get("phases")
        if not isinstance(phases, dict) or not phases:
            errors.append(f"{path}: {context}.phases must be a non-empty mapping")
            continue
        for phase_name, phase_data in phases.items():
            phase_ctx = f"{context}.phases.{phase_name}"
            if not isinstance(phase_data, dict):
                errors.append(f"{path}: {phase_ctx} must be a mapping")
                continue
            delay = phase_data.get("delay_hours")
            if not isinstance(delay, Real):
                errors.append(f"{path}: {phase_ctx}.delay_hours must be numeric")
            errors.extend(
                _ensure_non_empty_list(
                    phase_data.get("gossip"), path, f"{phase_ctx}.gossip"
                )
            )
            briefs = phase_data.get("briefs")
            if not isinstance(briefs, list) or not briefs:
                errors.append(f"{path}: {phase_ctx}.briefs must be a non-empty list")
            else:
                for idx, brief in enumerate(briefs):
                    brief_ctx = f"{phase_ctx}.briefs[{idx}]"
                    if not isinstance(brief, dict):
                        errors.append(f"{path}: {brief_ctx} must be a mapping")
                        continue
                    for key in ("headline", "body"):
                        value = brief.get(key)
                        if not isinstance(value, str) or not value.strip():
                            errors.append(f"{path}: {brief_ctx}.{key} must be a string")
            if "next" in phase_data:
                next_data = phase_data["next"]
                if not isinstance(next_data, dict):
                    errors.append(f"{path}: {phase_ctx}.next must be a mapping")
                else:
                    if not isinstance(next_data.get("phase"), str):
                        errors.append(f"{path}: {phase_ctx}.next.phase must be a string")
                    if not isinstance(next_data.get("delay_hours"), Real):
                        errors.append(
                            f"{path}: {phase_ctx}.next.delay_hours must be numeric"
                        )
    return errors


def validate_defection_epilogues(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("epilogues") if isinstance(data, dict) else None
    if not isinstance(root, dict) or not root:
        return [f"{path}: top-level 'epilogues' mapping is required"]

    for name, payload in root.items():
        ctx = f"epilogues.{name}"
        if not isinstance(payload, dict):
            errors.append(f"{path}: {ctx} must be a mapping")
            continue
        primary = payload.get("primary")
        if not isinstance(primary, dict):
            errors.append(f"{path}: {ctx}.primary must be a mapping")
        else:
            for key in ("headline", "body"):
                if not isinstance(primary.get(key), str) or not primary[key].strip():
                    errors.append(f"{path}: {ctx}.primary.{key} must be a string")
        errors.extend(
            _ensure_non_empty_list(payload.get("gossip"), path, f"{ctx}.gossip")
        )
        brief = payload.get("faction_brief")
        if not isinstance(brief, dict):
            errors.append(f"{path}: {ctx}.faction_brief must be a mapping")
        else:
            for key in ("headline", "body"):
                if not isinstance(brief.get(key), str) or not brief[key].strip():
                    errors.append(f"{path}: {ctx}.faction_brief.{key} must be a string")
    return errors


def validate_sideways_vignettes(path: Path, data: Any) -> List[str]:
    errors: List[str] = []
    root = data.get("vignettes") if isinstance(data, dict) else None
    if not isinstance(root, dict) or not root:
        return [f"{path}: top-level 'vignettes' mapping is required"]

    for category, depths in root.items():
        if not isinstance(depths, dict) or not depths:
            errors.append(f"{path}: vignettes.{category} must be a mapping of depths")
            continue
        for depth, entries in depths.items():
            ctx = f"vignettes.{category}.{depth}"
            if not isinstance(entries, list) or not entries:
                errors.append(f"{path}: {ctx} must be a non-empty list")
                continue
            seen_ids: set[str] = set()
            for idx, entry in enumerate(entries):
                entry_ctx = f"{ctx}[{idx}]"
                if not isinstance(entry, dict):
                    errors.append(f"{path}: {entry_ctx} must be a mapping")
                    continue
                entry_id = entry.get("id")
                if not isinstance(entry_id, str) or not entry_id.strip():
                    errors.append(f"{path}: {entry_ctx}.id must be a string")
                elif entry_id in seen_ids:
                    errors.append(f"{path}: duplicate vignette id '{entry_id}' in {ctx}")
                else:
                    seen_ids.add(entry_id)
                for key in ("headline", "body"):
                    if not isinstance(entry.get(key), str) or not entry[key].strip():
                        errors.append(f"{path}: {entry_ctx}.{key} must be a string")
                tags = entry.get("tags")
                errors.extend(
                    _ensure_non_empty_list(tags, path, f"{entry_ctx}.tags")
                )
                gossip = entry.get("gossip")
                if gossip is not None:
                    errors.extend(
                        _ensure_non_empty_list(
                            gossip, path, f"{entry_ctx}.gossip"
                        )
                    )
    return errors


CANONICAL_PATHS = {
    Path("great_work/data/press_tone_packs.yaml"): validate_press_tone_packs,
    Path("great_work/data/recruitment_press.yaml"): validate_recruitment_press,
    Path("great_work/data/table_talk_press.yaml"): validate_table_talk_press,
    Path("great_work/data/mentorship_press.yaml"): validate_mentorship_press,
    Path("great_work/data/sidecast_arcs.yaml"): validate_sidecast_arcs,
    Path("great_work/data/defection_epilogues.yaml"): validate_defection_epilogues,
    Path("great_work/data/sideways_vignettes.yaml"): validate_sideways_vignettes,
    Path("great_work/data/landmark_preparations.yaml"): validate_landmark_preparations,
}


def _match_canonical(path: Path) -> Path | None:
    resolved = path.resolve()
    for candidate in CANONICAL_PATHS:
        candidate_resolved = (Path.cwd() / candidate).resolve()
        if resolved == candidate_resolved:
            return candidate
    return None


def validate_file(path: Path) -> List[str]:
    canonical = _match_canonical(path)
    if canonical is None:
        return [f"No validator registered for {path}"]
    resolver = CANONICAL_PATHS[canonical]
    data = _load_yaml(Path.cwd() / canonical)
    return resolver(canonical, data)


def validate_files(paths: Sequence[Path]) -> List[str]:
    errors: List[str] = []
    for path in paths:
        resolved = path if path.is_absolute() else Path.cwd() / path
        if not resolved.exists():
            errors.append(f"{path}: file not found")
            continue
        errors.extend(validate_file(resolved))
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate narrative YAML assets for structure and required fields."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Specific YAML files to validate (defaults to core narrative assets)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate the canonical set of narrative YAML assets",
    )

    args = parser.parse_args(argv)
    targets: List[Path]
    if args.paths:
        targets = [path for path in args.paths]
    elif args.all or not args.paths:
        targets = list(DEFAULT_FILES)
    else:  # pragma: no cover - defensive fallback
        targets = []

    errors = validate_files(targets)
    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1

    print("Narrative validation passed for", len(targets), "file(s).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
