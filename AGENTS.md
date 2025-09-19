# Repository Guidelines

## Project Structure & Module Organization
Gameplay logic lives in `great_work/`, with `service.py`, `scheduler.py`, and `discord_bot.py` coordinating Discord flows, scheduling, and persistence. Domain contracts sit in `models.py` and `state.py`, while telemetry, RNG, and seeding helpers share the same package. Reference material and design notes are under `docs/`; automated coverage targets `tests/`. Use `great_work/tools/` for utilities such as database seeding, and reach for `docker-compose.yml` when local Qdrant is needed.

## Build, Test, and Development Commands
Create an isolated environment with `make venv`, then install dependencies via `make install` to pull in the `dev` extras. Run `make test` or `pytest -q` for the suite, and narrow with `pytest -k <pattern>`. Guard style by running `make lint`, which invokes Ruff across the tree. Launch the Discord bot with `make run` (loads `.env` automatically) and seed a fresh SQLite database using `make seed DB=great_work.db` before manual playtests.

## Coding Style & Naming Conventions
Target Python 3.12, indent with four spaces, and keep lines ≤100 characters. Module and file names stay in `snake_case`; classes use `PascalCase`; functions and variables use `snake_case`. Lean on type hints and Pydantic models for cross-module boundaries, mirroring existing patterns in `models.py`. When defining Discord commands, reuse established naming seen in `scholars.py` and `expeditions.py` to keep UX consistent.

## Testing Guidelines
Pytest with pytest-asyncio backs the suite. Place new tests under `tests/`, naming files `test_<feature>.py` and test functions `test_<behavior>`. Cover edge cases for scheduling, RNG determinism, and state transitions—`test_service_edge_cases.py` and `test_rng_determinism.py` are good templates. When introducing integrations, patch `llm_client`, telemetry, or scheduler hooks so tests remain deterministic and offline-friendly.

## Commit & Pull Request Guidelines
Commits use short, imperative sentences without trailing punctuation (e.g., "Tighten mentorship cooldown"). Group related work and include relevant docs or data updates together. Before opening a PR, ensure lint and tests pass, summarize behavioral impact, link issues or planning docs, and attach screenshots or transcripts for Discord-visible changes. Call out configuration or migration steps so reviewers can verify them quickly.

## Environment & Configuration Tips
Copy `.env.example` to `.env` for local runs and keep secrets out of version control. Use `telemetry.db` only for development; reset with `make clean-db` when needed. Start Qdrant locally with `docker-compose up qdrant` and align connection details in `config.py` when working on embedding features.
