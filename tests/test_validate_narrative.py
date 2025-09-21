"""Tests for the narrative validation CLI."""
from __future__ import annotations

from pathlib import Path

from great_work.tools import validate_narrative


def test_current_assets_pass_validation() -> None:
    errors, related = validate_narrative.validate_files(validate_narrative.DEFAULT_FILES)
    assert errors == []
    assert related == []


def test_tone_pack_missing_required_field() -> None:
    data = {
        "settings": {
            "test_pack": {
                "digest_highlight": {
                    "headline": ["Example"],
                    "callout": ["Reminder"],
                }
            }
        }
    }

    errors = validate_narrative.validate_press_tone_packs(Path("dummy.yaml"), data)
    assert any("blurb_template" in message for message in errors)
