# The Great Work

The Great Work is an asynchronous, fully public research drama played through Discord. Players direct scholars, make proclamations, and resolve expeditions that can succeed spectacularly or fail into sideways discoveries.

This repository contains a playable MVP aligned with the provided design:

* Discord-first interface powered by `discord.py`
* Deterministic scholar generator with hand-authored legends
* Reputation-aware confidence wagers and five-faction influence scaffolding
* Expedition resolver with d100 recipe and failure tables
* Automatic press release templates suitable for Gazette digests
* Append-only event log backed by SQLite and exportable for audits
* APScheduler integration for twice-daily Gazette posts and weekly symposia hooks

## Getting started

Ensure you are running Python 3.12 or newer, then create a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Seed the database with the canonical scholars and run the Discord bot:

```bash
python -m great_work.tools.seed_db great_work.db
export DISCORD_TOKEN=your_token_here
python -m great_work.discord_bot
```

The bot exposes three slash commands in Discord:

* `/submit_theory` – publish an Academic Bulletin.
* `/launch_expedition` – queue a field expedition with preparation details.
* `/resolve_expeditions` – resolve all queued expeditions and post Discovery Reports.

For offline experiments you can drive the service directly:

```python
from pathlib import Path
from great_work.models import ConfidenceLevel, ExpeditionPreparation
from great_work.service import GameService

service = GameService(Path("demo.db"))
service.state.seed_base_scholars()
press = service.submit_theory("sarah", "Bronze Age flight", ConfidenceLevel.CERTAIN, ["s.ironquill"], "Friday 20:00")
print(press.headline)
print(press.body)
```

## Tests

Run the unit test suite with `pytest`:

```bash
pytest
```

The tests cover scholar generation reproducibility, expedition resolution thresholds, and the defection probability curve.

## License

Code is released under the MIT License. Narrative assets and persona sheets default to CC BY-SA 4.0 as described in the design notes.
