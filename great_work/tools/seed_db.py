"""Seed the database with base scholars."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import get_settings
from ..scholars import ScholarRepository
from ..state import GameState


def seed_database(path: Path) -> None:
    repo = ScholarRepository()
    settings = get_settings()
    state = GameState(path, repository=repo, start_year=settings.timeline_start_year)
    state.seed_base_scholars()
    print(f"Seeded {len(list(state.all_scholars()))} scholars into {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed The Great Work database")
    parser.add_argument("db", type=Path, help="Path to SQLite database")
    args = parser.parse_args()
    seed_database(args.db)


if __name__ == "__main__":  # pragma: no cover - CLI tool
    main()
