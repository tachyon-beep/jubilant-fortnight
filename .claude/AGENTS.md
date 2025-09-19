# Repository Guidelines

This guide keeps contributors aligned on how The Great Work codebase is organized, built, and reviewed.

## Project Structure & Module Organization
- `great_work/`: Core package; Discord entrypoint in `discord_bot.py`, shared services in `service.py`, data assets under `data/`, utilities in `tools/`.
- `tests/`: Pytest suite mirroring production modules; add new files as `test_<feature>.py`.
- `docs/`: Design notes, RFCs, and implementation plans worth reviewing before major changes.
- Root artifacts such as `README.md`, `pyproject.toml`, and `LICENSE` describe setup, packaging, and licensing expectations.

## Build, Test, and Development Commands
- Environment: `python3.12 -m venv .venv && source .venv/bin/activate` followed by `pip install -e .[dev]` gives an editable install with tooling.
- Quality gates: run `pytest` for unit coverage and `ruff .` (when available) for linting before pushing.
- Local run: seed the SQLite database via `python -m great_work.tools.seed_db great_work.db`, export `DISCORD_TOKEN` plus the `GREAT_WORK_CHANNEL_*` vars, then start the bot with `python -m great_work.discord_bot`.

## Coding Style & Naming Conventions
- Python code follows PEP 8 with 4-space indentation, explicit type hints, and succinct docstrings when behavior is non-obvious.
- Prefer `snake_case` for modules and functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.
- Use `ruff` or a compatible formatter to maintain import order and strip dead code.

## Testing Guidelines
- Tests live beside relevant modules in `tests/`; keep names deterministic and fixtures isolated.
- Structure tests as `test_<behavior>` with arrange/act/assert clarity, and extend coverage whenever logic branches are introduced.
- Always run `pytest` locally after changes touching `great_work/` or shared utilities.

## Commit & Pull Request Guidelines
- Write commits in the imperative mood (e.g., `Add expedition resolver thresholds`) and limit each commit to a focused concern.
- PRs should summarize intent, reference related issues, list touched paths (e.g., `great_work/`, `tests/`, `docs/`), and include relevant logs or screenshots.
- Confirm the working tree is clean and quality gates have passed before requesting review.

## Security & Configuration Tips
- Never commit secrets; rely on environment variables such as `DISCORD_TOKEN` and `GREAT_WORK_CHANNEL_*`.
- Exclude local artifacts like `.env` and `*.db`, which are already ignored in version control but should stay local.
