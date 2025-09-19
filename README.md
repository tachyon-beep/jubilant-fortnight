# The Great Work

[![Version](https://img.shields.io/badge/version-1.0.0--rc1-blue)](https://github.com/your-repo/the-great-work)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
![Tests](https://img.shields.io/badge/tests-192%20passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-70%25-yellow)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The Great Work is an asynchronous, fully public research drama played through Discord. Players direct scholars, make proclamations, and resolve expeditions that can succeed spectacularly or fail into sideways discoveries.

## Features

### Core Gameplay

* **Scholar System**: 20-30 memorable scholars with unique personalities, memories, and relationships
* **Expedition Mechanics**: Three expedition types (think tanks, field expeditions, great projects) with d100 resolution
* **Confidence Wagers**: Risk/reward system with reputation stakes (suspect +2/-1, certain +5/-7, stake_my_career +15/-25)
* **Five-Faction Influence**: Academic, Government, Industry, Religious, and Foreign factions with reputation-based soft caps
* **Mentorship System**: Player-driven scholar career progression via `/mentor` and `/assign_lab` commands
* **Conference Mechanics**: Public theory debates with reputation wagering
* **Symposium Voting**: Weekly community topics with player participation

### Advanced Features

* **Contract Negotiations**: Multi-stage poaching system with influence escrow
* **Sideways Discoveries**: Expeditions trigger mechanical consequences (faction shifts, theories, grudges)
* **Multi-layer Press System**: Depth-based narrative coverage for all events
* **Defection Arcs**: Complex loyalty mechanics with scars and emotional consequences
* **LLM Integration**: Dynamic persona voices via OpenAI-compatible API
* **Content Moderation**: Multi-level safety checks with fallback templates
* **Web Archive**: Static HTML export with permalinks for historical records
* **Telemetry System**: Comprehensive metrics tracking with admin reporting

### Technical Infrastructure

* **Event Sourcing**: Complete audit trail of all game actions
* **Deterministic RNG**: Reproducible game mechanics for fair play
* **Discord Integration**: 20 slash commands for complete player interaction
* **Automated Digests**: Twice-daily game advancement via APScheduler
* **SQLite Persistence**: Efficient local storage with JSON serialization
* **Vector Database**: Qdrant integration for semantic knowledge management

## Installation

### Prerequisites

* Python 3.12 or newer
* Discord bot token and application ID
* (Optional) OpenAI API key for LLM features
* (Optional) Docker and Docker Compose for containerized deployment

### Quick Start

1. **Clone the repository**:

```bash
git clone https://github.com/your-repo/the-great-work.git
cd the-great-work
```

1. **Set up Python environment**:

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .[dev]
```

1. **Configure environment**:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:

```env
# Discord Configuration
DISCORD_TOKEN=your_bot_token_here
DISCORD_APP_ID=your_app_id_here
GREAT_WORK_CHANNEL_ORDERS=channel_id_for_commands
GREAT_WORK_CHANNEL_GAZETTE=channel_id_for_digests
GREAT_WORK_CHANNEL_TABLE_TALK=channel_id_for_flavor

# Optional: LLM Configuration
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4-turbo-preview
```

1. **Initialize database**:

```bash
make seed  # Seeds canonical scholars
# Or manually:
python -m great_work.tools.seed_db great_work.db
```

1. **Run the bot**:

```bash
make run  # Loads .env automatically
# Or manually:
python -m great_work.discord_bot
```

## Discord Commands

### Player Commands

* `/submit_theory` - Publish an Academic Bulletin with confidence wager
* `/launch_expedition` - Queue an expedition (think tank, field work, or great project)
* `/mentor` - Guide a scholar's career development
* `/assign_lab` - Assign scholars to laboratory positions
* `/poach` - Attempt to recruit scholars from other players
* `/counter` - Counter a poaching attempt on your scholars
* `/view_offers` - View active contract negotiations
* `/conference` - Initiate or participate in academic conferences
* `/vote` - Participate in weekly symposium voting
* `/recruit` - Attempt to recruit new scholars

### Information Commands

* `/status` - View your reputation, influence, and cooldowns
* `/roster` - Display all scholars and their affiliations
* `/wager` - Review confidence stakes and thresholds
* `/gazette` - Browse recent press releases
* `/archive` - Access the web archive of historical events
* `/export_log` - Export game events for analysis

### Admin Commands

* `/gw_admin seed` - Initialize canonical scholars
* `/gw_admin digest` - Manually trigger gazette digest
* `/gw_admin followup` - Process scheduled events
* `/gw_admin telemetry` - View system metrics

## Deployment

### Docker Deployment (Recommended)

1. **Build and run with Docker Compose**:

```bash
docker-compose up -d
```

This starts:

* Discord bot container
* Qdrant vector database (if enabled)
* Automatic volume management for persistence

1. **Monitor logs**:

```bash
docker-compose logs -f bot
```

### Production Deployment

1. **System Requirements**:

* Linux server (Ubuntu 22.04+ recommended)
* 2GB RAM minimum, 4GB recommended
* 10GB disk space for database and archives
* Python 3.12+ runtime

1. **Systemd Service** (create `/etc/systemd/system/great-work.service`):

```ini
[Unit]
Description=The Great Work Discord Bot
After=network.target

[Service]
Type=simple
User=greatwork
WorkingDirectory=/opt/great-work
Environment="PATH=/opt/great-work/.venv/bin"
EnvironmentFile=/opt/great-work/.env
ExecStart=/opt/great-work/.venv/bin/python -m great_work.discord_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

1. **Enable and start service**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable great-work
sudo systemctl start great-work
```

### Database Backup

```bash
# Backup databases
cp great_work.db great_work.db.backup
cp telemetry.db telemetry.db.backup

# Export event log
python -m great_work.tools.export_events
```

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Bot authentication token |
| `DISCORD_APP_ID` | Yes | Application ID for slash commands |
| `GREAT_WORK_CHANNEL_ORDERS` | Yes | Channel for player commands |
| `GREAT_WORK_CHANNEL_GAZETTE` | Yes | Channel for automated digests |
| `GREAT_WORK_CHANNEL_TABLE_TALK` | Yes | Channel for flavor commentary |
| `LLM_API_BASE` | No | OpenAI-compatible API endpoint |
| `LLM_API_KEY` | No | API key for LLM service |
| `LLM_MODEL` | No | Model name (default: gpt-4-turbo-preview) |
| `LLM_ENABLED` | No | Enable LLM features (default: true if API key set) |
| `DIGEST_HOUR_1` | No | First daily digest hour (default: 12) |
| `DIGEST_HOUR_2` | No | Second daily digest hour (default: 20) |
| `SYMPOSIUM_DAY` | No | Weekly symposium day (default: Sunday) |

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=great_work --cov-report=html

# Run specific test file
pytest tests/test_scholar_generation.py

# Run tests in parallel
pytest -n auto
```

Test suite includes 192 tests covering:

* Scholar generation and deterministic RNG
* Expedition resolution and d100 mechanics
* Contract negotiations and defection arcs
* Multi-layer press system
* LLM integration and content moderation
* Web archive generation
* Telemetry and metrics

### Code Quality

```bash
# Lint with ruff
make lint

# Auto-fix issues
ruff --fix .

# Type checking
mypy great_work/
```

### Project Structure

```text
great_work/
├── models.py          # Core domain models
├── state.py           # GameState persistence layer
├── service.py         # High-level game orchestration
├── scholars.py        # Scholar generation system
├── expeditions.py     # Expedition resolution engine
├── contracts.py       # Contract negotiation system
├── sideways.py        # Sideways discovery effects
├── press.py           # Press release templates
├── multi_press.py     # Multi-layer press system
├── llm_client.py      # LLM integration
├── telemetry.py       # Metrics and analytics
├── web_archive.py     # HTML archive generation
├── scheduler.py       # Automated digest scheduling
├── discord_bot.py     # Discord interface
└── data/
    ├── scholars_base.yaml     # Canonical scholars
    ├── disciplines.yaml       # Academic fields
    ├── methods.yaml          # Research approaches
    ├── failure_tables.yaml   # d100 failure outcomes
    └── settings.yaml         # Game configuration
```

### API Usage

```python
from pathlib import Path
from great_work.models import ConfidenceLevel
from great_work.service import GameService

# Initialize service
service = GameService(Path("game.db"))
service.state.seed_base_scholars()

# Submit a theory
press = service.submit_theory(
    player_id="player_123",
    claim="Bronze Age flight existed",
    confidence=ConfidenceLevel.CERTAIN,
    supporters=["s.ironquill"],
    deadline="Friday 20:00"
)

# Launch an expedition
result = service.launch_expedition(
    player_id="player_123",
    expedition_type="field",
    scholars=["s.ironquill", "dr.sage"],
    confidence=ConfidenceLevel.SUSPECT,
    focus="Ancient aviation artifacts"
)

# Process game digest
digest_events = service.advance_digest()
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Workflow

```bash
# Set up development environment
make venv
make install

# Run tests before committing
make test
make lint

# Seed test database
make seed

# Run bot locally
make run
```

## Documentation

* [High-Level Design](docs/HLD.md) - Architecture and system design
* [Requirements Evaluation](docs/requirements_evaluation.md) - Feature implementation status
* [Gap Analysis](docs/gap_analysis.md) - Sprint completion tracking
* [CLAUDE.md](CLAUDE.md) - AI assistance documentation

## License

Code is released under the MIT License. Narrative assets and persona sheets default to CC BY-SA 4.0 as described in the design notes.

## Acknowledgments

* Built with [discord.py](https://github.com/Rapptz/discord.py)
* Vector search powered by [Qdrant](https://qdrant.tech/)
* Scheduling via [APScheduler](https://github.com/agronholm/apscheduler)
* LLM integration supports OpenAI-compatible APIs

## Support

For issues, questions, or suggestions:

* Open an issue on GitHub
* Join our Discord server (link coming soon)
* Check the [documentation](docs/)
