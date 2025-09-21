"""Tests for the narrative preview tooling."""

from __future__ import annotations

from great_work.tools import preview_narrative


def test_preview_generates_output() -> None:
    lines = preview_narrative.run_previewer("tone-packs")
    assert lines  # non-empty output
    assert any("Tone Packs" in line for line in lines)


def test_cli_accepts_specific_surface(capsys) -> None:
    exit_code = preview_narrative.main(["recruitment"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Recruitment Press" in captured.out


def test_landmark_preview_surface() -> None:
    lines = preview_narrative.run_previewer("landmark-prep")
    assert lines
    assert any("Landmark Preparations" in line for line in lines)
