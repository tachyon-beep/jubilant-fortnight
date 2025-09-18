# Repository Guidelines

This guide explains how to contribute to The Great Work codebase in this repository.

## Project Structure & Module Organization
- `great_work/`: Main package (Discord bot `discord_bot.py`, game logic `service.py`, data assets under `data/`, utilities under `tools/`).
- `tests/`: Pytest suite for core mechanics and services.
- `docs/`: Design notes and implementation plans.
- Root files: `README.md`, `pyproject.toml`, `LICENSE`.

## Build, Test, and Development Commands
Environment setup and install (Python 3.12+):
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```
Run tests and lints:
```bash
pytest
ruff .  # if installed/configured
```
Seed and run locally:
```bash
python -m great_work.tools.seed_db great_work.db
export DISCORD_TOKEN=...; export GREAT_WORK_CHANNEL_ORDERS=...; export GREAT_WORK_CHANNEL_GAZETTE=...; export GREAT_WORK_CHANNEL_TABLE_TALK=...
python -m great_work.discord_bot
```

## Coding Style & Naming Conventions
- Python: PEP 8; prefer type hints and concise docstrings.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Formatting/linting: use `ruff` where available; keep imports and files tidy.

## Testing Guidelines
- Framework: `pytest`; tests live in `tests/` and follow `test_*.py` naming.
- Add tests for new behavior and edge cases; keep randomness deterministic where applicable.
- Run `pytest` before pushing any changes touching `great_work/` or `tests/`.

## Commit & Pull Request Guidelines
- Commits: one logical change per commit, imperative subject (e.g., "Add expedition resolver thresholds").
- PRs: clear description, linked issues, mention impacted paths (e.g., `great_work/`, `tests/`, `docs/`), and any relevant logs or screenshots.
- Ensure CI prerequisites pass locally (`pytest`, lint) and `git status` is clean.

## Security & Configuration Tips
- Keep secrets out of the repo; use environment variables (`DISCORD_TOKEN`, `GREAT_WORK_CHANNEL_*`).
- Do not commit local databases or env files (`*.db`, `.env` are ignored in `.gitignore`).
