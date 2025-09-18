# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup and Installation:**
```bash
make venv        # Create Python 3.12 virtualenv
make install     # Install project + dev dependencies
make env         # Create .env from .env.example
```

**Core Commands:**
```bash
make test        # Run pytest suite
make lint        # Run ruff linter
make seed        # Seed database with canonical scholars
make run         # Run Discord bot (loads .env if present)
```

**Testing:**
```bash
pytest                              # Run all tests
pytest tests/test_scholar_generation.py  # Run specific test file
pytest -k "test_name"               # Run specific test by name
```

**Linting:**
```bash
ruff .           # Check all files
ruff --fix .     # Auto-fix issues where possible
```

## Architecture Overview

**The Great Work** is an asynchronous multiplayer Discord game where players direct scholars to make research discoveries. The codebase follows a layered architecture:

### Core Game Logic (`great_work/`)
- **models.py**: Core domain models (Scholar, Player, Theory, Expedition, etc.) with Pydantic dataclasses
- **state.py**: GameState class managing persistent SQLite storage and event log
- **service.py**: GameService orchestrating high-level game operations and player commands
- **scholars.py**: ScholarRepository and generation logic for deterministic character creation
- **expeditions.py**: ExpeditionResolver handling d100-based resolution with failure tables
- **press.py**: Template system for generating narrative press releases from game events
- **scheduler.py**: APScheduler integration for automated Gazette posts and symposia
- **discord_bot.py**: Discord slash command interface mapping to game service

### Data Files (`great_work/data/`)
YAML configuration files defining game content:
- **scholars_base.yaml**: Hand-authored legendary scholar profiles
- **disciplines.yaml**, **methods.yaml**: Academic specializations and research approaches
- **failure_tables.yaml**: d100 tables for expedition failure outcomes
- **settings.yaml**: Game configuration (reputation thresholds, cooldowns, influence caps)

### Key Design Patterns

1. **Event Sourcing**: All game actions produce Events stored in an append-only log, enabling full game replay and audit trails.

2. **Deterministic Generation**: Scholars use seeded RNG (DeterministicRNG) ensuring reproducible personalities across games.

3. **Public-First Design**: Every action generates PressReleases visible to all players - no private moves exist.

4. **Memory System**: Scholars maintain Facts (timestamped events) and Feelings (decaying emotions) with permanent Scars from betrayals.

5. **Influence Vectors**: Five-faction system (Academic, Government, Industry, Religious, Foreign) replaces single currency.

## Discord Bot Environment

Required environment variables:
- `DISCORD_TOKEN`: Bot authentication token
- `DISCORD_APP_ID`: Application ID for slash commands
- `GREAT_WORK_CHANNEL_ORDERS`: Channel ID for player commands
- `GREAT_WORK_CHANNEL_GAZETTE`: Channel ID for automated digests
- `GREAT_WORK_CHANNEL_TABLE_TALK`: Channel ID for flavor commentary

## Database Schema

SQLite with JSON serialization for complex types:
- **players**: Player profiles with reputation and influence vectors
- **scholars**: Generated personalities with memories and relationships
- **theories**: Published research claims with confidence wagers
- **expeditions**: Queued field work with preparation details
- **events**: Append-only log of all game actions
- **press**: Generated narrative content for public consumption

## Testing Approach

Tests focus on deterministic behavior and game mechanics:
- **test_scholar_generation.py**: Reproducible character generation
- **test_expedition_resolver.py**: d100 threshold calculations
- **test_defection_probability.py**: Scholar loyalty curves
- **test_game_service.py**: Integration tests for command flow

Use `conftest.py` fixtures for temporary databases and test data.