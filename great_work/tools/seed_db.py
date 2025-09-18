"""Seed the database with base scholars."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..scholars import ScholarRepository
from ..state import GameState


def seed_database(path: Path) -> None:
    repo = ScholarRepository()
    state = GameState(path, repository=repo)
    state.seed_base_scholars()
    print(f"Seeded {len(list(state.all_scholars()))} scholars into {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed The Great Work database")
    parser.add_argument("db", type=Path, help="Path to SQLite database")
    args = parser.parse_args()
    seed_database(args.db)


if __name__ == "__main__":  # pragma: no cover - CLI tool
    main()
