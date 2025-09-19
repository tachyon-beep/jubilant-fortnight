# Changelog

All notable changes to The Great Work Discord game will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-01 (Upcoming)

### Added

#### Core Gameplay Features
- **Scholar System**: 20-30 memorable scholars with unique personalities, memories, and relationships
- **Expedition Mechanics**: Three expedition types (think tanks, field expeditions, great projects) with d100 resolution
- **Confidence Wagers**: Risk/reward system with reputation stakes (suspect +2/-1, certain +5/-7, stake_my_career +15/-25)
- **Five-Faction Influence Economy**: Academic, Government, Industry, Religious, and Foreign factions with reputation-based soft caps
- **Mentorship System**: Player-driven scholar career progression via `/mentor` and `/assign_lab` commands
- **Conference Mechanics**: Public theory debates with reputation wagering
- **Symposium Voting**: Weekly community topics with player participation

#### Advanced Features
- **Contract Negotiations**: Multi-stage poaching system with influence escrow via `/poach`, `/counter`, `/view_offers`
- **Sideways Discovery Effects**: Expeditions trigger mechanical consequences (faction shifts, theories, grudges)
- **Multi-layer Press System**: Depth-based narrative coverage for all events
- **Defection Arcs**: Complex loyalty mechanics with scars and emotional consequences

#### Discord Integration
- **20 Slash Commands**: Complete player interface for all game actions
- **Scheduled Digests**: Twice-daily automated game advancement
- **Admin Tools**: Moderation commands via `/gw_admin` command group
- **Channel Routing**: Separate channels for orders, gazette, and table talk

#### Narrative Enhancement
- **LLM Integration**: OpenAI-compatible API for dynamic persona voices
- **Content Moderation**: Multi-level safety checks with fallback templates
- **Press Archive**: All events generate permanent, citable press releases

#### Technical Infrastructure
- **Event Sourcing**: Complete audit trail of all game actions
- **Deterministic RNG**: Reproducible game mechanics for fair play
- **Web Archive**: Static HTML export with permalinks for historical records
- **Telemetry System**: Comprehensive metrics tracking with admin reporting
- **Qdrant Integration**: Vector database for semantic knowledge management

### Configuration
- Environment-based configuration via `.env` file
- Docker Compose support for containerized deployment
- Makefile automation for common development tasks
- Comprehensive test suite with 192 tests

### Documentation
- High-level design document (HLD.md)
- Requirements evaluation and gap analysis
- Implementation plan with sprint tracking
- CLAUDE.md for AI-assisted development
- Comprehensive inline code documentation

### Fixed
- All critical production bugs identified in Sprint 3
- Memory API issues in contract negotiation system
- Database schema compatibility issues
- Test suite reliability and coverage

### Security
- Content filtering for LLM-generated text
- Rate limiting on LLM API calls
- Admin permission checks on moderation commands
- Secure influence escrow system for contracts

## [0.9.0] - 2024-12-19 (Pre-release)

### Added
- Sprint 3 features: LLM integration, telemetry, multi-layer press
- Sprint 2 features: Contracts, sideways effects, web archive
- Sprint 1 features: Mentorship, conferences, symposiums, admin tools

### Known Issues
- Memory.get_feeling() method implementation
- Some edge cases in offer resolution
- Minor markdown formatting issues (resolved via Codacy patch)

## [0.1.0] - 2024-09-01 (Initial Development)

### Added
- Basic Discord bot framework
- Scholar generation system
- Expedition queueing and resolution
- Simple press release templates
- SQLite database persistence

---

## Versioning Policy

This project uses Semantic Versioning:
- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## Migration Notes

### Upgrading to 1.0.0
- No database migrations required from 0.9.0
- Environment variables remain compatible
- All Discord commands maintain backward compatibility