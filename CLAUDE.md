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

**The Great Work** is an asynchronous multiplayer Discord game where players direct scholars to make research
discoveries. The codebase follows a layered architecture:

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

1. **Event Sourcing**: All game actions produce Events stored in an append-only log, enabling full game replay
   and audit trails.

2. **Deterministic Generation**: Scholars use seeded RNG (DeterministicRNG) ensuring reproducible personalities across games.

3. **Public-First Design**: Every action generates PressReleases visible to all players - no private moves exist.

4. **Memory System**: Scholars maintain Facts (timestamped events) and Feelings (decaying emotions) with permanent
   Scars from betrayals.

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

## Qdrant Vector Database Integration

The project includes Qdrant for semantic search and knowledge management. When working with game knowledge,
scholar information, or press archives:

**IMPORTANT: Read these comprehensive guides:**

- **[Qdrant Usage Guide](docs/ai/qdrant_usage_guide.md)**: Complete MCP command reference, best practices, search strategies
- **[Qdrant Schemas](docs/ai/qdrant_schemas.md)**: Document schemas, examples for all content types, validation checklists

**Quick Reference:**

- Store information: `mcp__qdrant-great-work__qdrant-store(information="...")`
- Search knowledge: `mcp__qdrant-great-work__qdrant-find(query="...")`
- Collection name: `great-work-knowledge`

See the linked documentation for detailed usage patterns, schema examples, and best practices for maintaining
game continuity through the vector database.

## Available Subagents

**IMPORTANT**: Unless work needs to be done sequentially, agents should be launched in parallel using multiple Task tool calls in a single message for optimal performance.

The following specialized agents are available to assist with development:

### Core Development Agents

- **python-refactoring-expert**: Review, refactor, and improve Python code quality. Analyzes for complexity, applies design patterns, ensures SOLID principles.
- **test-engineer**: Write comprehensive tests, analyze coverage, implement TDD/BDD, create mocks, identify edge cases.
- **architecture-reviewer**: Review code architecture, system design, API patterns, modularity, scalability, and separation of concerns.

### System Design Agents

- **database-architect**: Design database schemas, event sourcing, CQRS, data consistency, migration strategies, transaction optimization.
- **api-integration-architect**: Design and implement REST/GraphQL APIs, webhooks, third-party integrations, authentication, rate limiting.
- **async-systems-architect**: Design asynchronous systems, event-driven architectures, message queues, pub/sub patterns.
- **data-architect**: Design data models, pipelines, ETL processes, data warehousing, analytics architectures.

### Infrastructure & Operations

- **devops-engineer**: Set up CI/CD pipelines, Docker containers, Kubernetes deployments, infrastructure as code, monitoring systems.
- **observability-engineer**: Implement logging, metrics, tracing, alerting, performance monitoring, debugging tools.
- **performance-optimizer**: Analyze and optimize performance bottlenecks, memory usage, query optimization, caching strategies.

### Specialized Domains

- **game-systems-designer**: Design game mechanics, balance systems, progression loops, player engagement strategies.
- **security-architect**: Design authentication, authorization, encryption, security audits, vulnerability assessments, OWASP compliance.
- **frontend-ui-specialist**: Design user interfaces, React components, state management, responsive layouts, accessibility.
- **platform-integration-specialist**: Integrate with external platforms, APIs, SDKs, handle platform-specific requirements.

### Quality & Compliance

- **compliance-standards-auditor**: Ensure regulatory compliance, audit standards, implement governance, risk management.
- **error-resilience-engineer**: Design error handling, fault tolerance, circuit breakers, retry logic, graceful degradation.
- **documentation-specialist**: Write technical documentation, API docs, user guides, maintain README files, create diagrams.

### Configuration & Planning

- **config-manager**: Manage application configuration, environment variables, secrets, feature flags, deployment configs.
- **domain-modeler**: Design domain models, bounded contexts, aggregates, value objects, domain events.
- **data-validator**: Implement data validation, sanitization, schema validation, input verification, data quality checks.
- **product-strategy-advisor**: Define product strategy, roadmaps, feature prioritization, user stories, market analysis.
- **ai-systems-optimizer**: Optimize AI/ML systems, model performance, prompt engineering, inference optimization.

### Usage Example

To launch multiple agents in parallel:

```python
# Single message with multiple Task tool calls for parallel execution
[
    Task(subagent_type="test-engineer", prompt="Write tests for the new feature"),
    Task(subagent_type="security-architect", prompt="Review authentication implementation"),
    Task(subagent_type="documentation-specialist", prompt="Update API documentation")
]
```
