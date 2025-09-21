# The Great Work — User Guide (Start a Game)

The Great Work is a fully public, asynchronous game of research and reputation that lives entirely in a Discord server. Every move is a press release, every success or failure is recorded in a public archive, and the community steers weekly debates at a symposium. This guide explains how to bring a world online and, once it’s up, how players actually play.

## How to Install (short)

To install locally, clone the repository, create a Python 3.12 virtual environment, and install the project in editable mode. Copy `.env.example` to `.env`, then fill in your Discord token, application ID, and channel IDs. You can seed a fresh database with `make seed` and start the bot with `make run`. If you prefer Docker, you don’t need a local Python install: keep your `.env` at the project root and let `docker compose up -d qdrant bot` start everything.

Quick steps
- git clone … && cd …
- make venv && make install && make env
- Edit `.env` (set DISCORD_TOKEN, DISCORD_APP_ID, channel IDs)
- Optional: make seed (create a fresh SQLite DB)
- Start locally: make run
- Or with Docker: docker compose up -d qdrant bot

## How to Start a Game (short)

Start the bot (Docker or local), then invite it to your Discord server using an OAuth2 URL with the `bot` and `application.commands` scopes. On first run, the game will seed an initial roster if none exists. The Gazette publishes digests twice a day at the configured times, and the weekly symposium is scheduled automatically. Once connected, you can verify the bot by running `/status` in your server; it should reply with a summary and begin posting to the Gazette and Table‑Talk channels when actions occur.

Quick steps
- Start bot (local: make run, Docker: docker compose up -d qdrant bot)
- Create OAuth2 invite (bot + application.commands) and invite the bot to your server
- Watch logs for “connected” and “Synced commands”
- In Discord, run /status to verify it responds
- Optional: docker compose up -d telemetry_dashboard and open http://localhost:8081

## How to Play (short)

Players use slash commands. They propose ideas with `/submit_theory`, staking reputation according to the wager table visible via `/wager`. They fund and prepare expeditions, which resolve at the daily Gazette digests as discovery reports or retractions. Each week the community debates a symposium topic; proposals and votes shape the public stance. Along the way, players build influence with faction investments, polish standing with archive endowments, and add colour with `/table_talk`. Everything is public and permanent; the Gazette and the archive are the table.

Quick steps
- Start with /status to see reputation, influence, thresholds
- Publish a theory via /submit_theory (choose a confidence)
- Review the wager table with /wager
- Prepare and queue an /expedition (think tank, field, or great project)
- Read outcomes in the Gazette after each digest; use /gazette for recent headlines
- Join the weekly debate: /symposium_propose, /symposium_vote, /symposium_status
- Shape the economy: /invest (faction investments), /endow_archive (reputation)
- Add colour or prompts via /table_talk

## Getting ready

Create a Discord application, enable the bot feature, and note the bot token and application ID. Copy `.env.example` to `.env` and fill in your token and application ID. The game announces itself in public channels, so it helps to provide numeric channel IDs for Orders, Gazette, Table‑Talk, Admin (and optional Upcoming) at the same time. The bot works with or without an LLM and moderation, but for production you’ll usually point `LLM_API_BASE` to your model endpoint with `LLM_SAFETY_ENABLED=true` and turn on Guardian moderation either in “local” mode (load the model from disk) or “sidecar” (call an HTTP server). If you want semantic search later, switch on Qdrant (`docker compose up -d qdrant`) and set `GREAT_WORK_QDRANT_INDEXING=true`.

You can run the bot locally (`make venv && make install && make env; make run`) or with Docker (`docker compose up -d qdrant bot`). When it starts, the console will report that it connected, synced its slash commands, and scheduled daily digests and the weekly symposium. Invite the bot to your server using an OAuth2 URL with the `bot` and `application.commands` scopes. On first run, if no scholars exist yet, the world seeds a roster automatically.

## The core loop: how to play

Players speak to the game through slash commands and everything they do is public. A good way to start is `/status`, which shows a player’s reputation, influence across five factions, action thresholds, and any active cooldowns. Players build reputation by publishing theories and taking risks. A theory is proposed with `/submit_theory` and must be accompanied by a confidence wager. The wager table is visible at `/wager`: low stakes nudge reputation gently, high stakes can produce big swings and even lock recruitment for a time. The Gazette prints the outcome of each theory and preserves it forever in the archive.

Ambitious players fund expeditions. There are three kinds: think tanks (lightweight theoretical work), field expeditions (evidence‑gathering), and great projects (high cost, high impact). Preparation matters. Players assemble a team, choose objectives and funding, and queue the expedition. The scheduler resolves expeditions at the daily digests and publishes discovery reports or retractions. Not all failures are equal: spectacular failures can create sideways discoveries that push stories in interesting directions. The Gazette summarises everything; `/gazette` shows the latest headlines if you miss a digest.

Each real‑world week the community meets at a symposium. Topics are announced in advance and anyone can propose, pledge, and vote using the symposium commands. Influence and reputation shape how much a voice counts; missing commitments accrues a form of social debt. At the end of the week the game tallies positions and records the outcome as public stance. The symposium rhythm gives the game a regular heartbeat: daily press cycles punctuated by a weekly argument the community can rally around.

Beneath the drama is a small economy. Players can invest in factions to earn goodwill, endow the public archive to polish their reputation, and sign seasonal commitments that must be paid down over time. Influence has soft caps that rise with reputation, so lasting renown unlocks more room to manoeuvre. When the game needs a lighter touch, `/table_talk` lets players add colour and banter without formal moves.

## Running the world

As an operator you rarely need to intervene. The scheduler publishes to the Gazette at the configured hours (by default 13:00 and 21:00) and exports the web archive after each digest. If you enable the optional dashboard (`docker compose up -d telemetry_dashboard`), you can watch command usage, digest health, and simple guardrails (digest latency, queue depth, LLM latency) at `http://localhost:8081`. If the LLM or moderation goes offline, the game can pause itself; you can also pause and resume manually with the admin commands. The admin namespace exposes tools to inspect or cancel delayed orders, and to create or update seasonal commitments and faction projects if you’re curating a particular narrative.

If you enable Qdrant, the game will embed and index press releases so you can search the archive semantically. This is optional and safe to turn on later in a campaign. With embeddings in place, tools like the knowledge manager can set up collections and report stats.

## Troubleshooting, gently

If commands never appear, make sure the bot was invited with `application.commands` and it had time to sync after connecting. If public posts never show up, double‑check you entered numeric channel IDs (Discord’s UI labels aren’t IDs). If an LLM endpoint runs on your host while the bot runs in a container, point `LLM_API_BASE` at a host‑reachable address (host IP or a compose service name) rather than `localhost`. The scheduler normalises weekday names for the symposium; if you change the `symposium_day` in settings, use a full day name or a three‑letter short form.

For moderation you can run strictly or permissively. In strict mode, if the Guardian model is unavailable the game will pause rather than let unsafe content slip through. In permissive mode, it will log warnings, fall back to template text when necessary, and keep going. Everything the system does—press releases, pauses, admin actions—flows through the Gazette and the archive, so the table stays transparent even when something goes wrong.

Once the world is running and players are experimenting, the best thing you can do is read the Gazette, post occasional admin summaries in Table‑Talk, and let the archive do its work. The Great Work is most alive when the community discovers that their brave claims and spectacular failures matter because they’re on the record.

For deployment specifics and knobs, see `DEPLOYMENT.md`. For embedding and search, see `docs/QDRANT_SETUP.md`.
