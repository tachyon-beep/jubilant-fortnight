# Safety Plan: Guardian Sidecar Moderation

_Last updated: 2025-09-30_

## Goals

- Provide layered safeguards around live Discord interactions without adding material latency.
- Keep moderation logic outside the bot process so LLM regressions or heavy traffic cannot stall gameplay.
- Document the operational checklist so on-call staff can validate guardrail health before 1.0.

## Architecture Overview

- **Sidecar process:** A long-lived Guardian model (2B) runs as a separate service. The Discord bot drops moderation jobs onto a local IPC queue (e.g., Unix domain socket, gRPC, or ZeroMQ). Keeping the model warm avoids cold-start penalties and isolates crashes from core gameplay.
- **Two-pass moderation:**
  - **Pre-pass (player input):** Screen incoming slash command arguments, free-form text, and theory submissions before they reach the game service.
  - **Post-pass (generated output):** Review the press lines, scholar quips, and other LLM or template outputs scheduled for publication.
- **Prefilter + model:** A lightweight regex/keyword filter rapidly whitelists safe content. Only suspicious excerpts are escalated to Guardian, reducing false positives and compute cost.
- **Single-token scoring:** Guardian is invoked in scoring mode (Yes/No classification). Prompts follow IBM’s template with a system instruction that defines the category under evaluation, the user text as the payload, and the expected response limited to `Yes` or `No`.

## Model & Deployment

- **Model choice:** Granite Guardian 3.2 3B (A800M variant) hosted locally. The INT8 quantised build remains lightweight enough for workstations while providing stronger safety coverage.
- **Runtime options:**
  - **Sidecar binary:** Run via Ollama (`ollama run granite-guardian:2b`) or a custom container. Ensure the service exposes a simple RPC endpoint for scoring requests.
  - **Process supervision:** Use systemd or a Docker container with restart policies. Telemetry should confirm the sidecar’s liveness (heartbeat check every minute).
- **Fetching weights:** Run `python -m great_work.tools.download_guardian_model --target ./models/guardian` to fetch the Hugging Face snapshot (defaults to `ibm-granite/granite-guardian-3.2-3b-a800m`). The script depends on `huggingface_hub`; install it locally before executing. We keep the repository free of large binaries by relying on this helper.
- **Integration modes:** Set `GREAT_WORK_GUARDIAN_MODE=sidecar` (default) to call an HTTP service at `GREAT_WORK_GUARDIAN_URL`, or `GREAT_WORK_GUARDIAN_MODE=local` to load the downloaded weights directly (requires `transformers`). In local mode point `GREAT_WORK_GUARDIAN_LOCAL_PATH` at the snapshot directory.
- **Latency budget:**
  - Prefilter: sub-millisecond per request.
  - Guardian 2B INT8 on CPU: **~100–300 ms** per call when warm.
  - Two-stage pass keeps worst-case moderation under 600 ms, well inside the “couple of seconds” allowance.
  - Optional GPU placement drops inference to <100 ms but is not required for launch.

## Policy Configuration

- **Categories enabled:** Hate/Abuse/Profanity (HAP), sexual content, violence, self-harm, illicit behaviour. Toggle groundedness/relevance checks later if Gazette drift becomes an issue.
- **Prompt template:**
  - System prompt sets the category and desired severity threshold.
  - User message contains the text under review.
  - Assistant must answer strictly `Yes` (violation) or `No` (safe). Reject any other token.
- **Escalation logic:**
  1. Prefilter flags high-risk patterns (e.g., explicit slurs, self-harm phrases). Immediate block and log without Guardian call if a direct hit occurs.
  2. Otherwise, wrap the text in the Guardian template, request scoring, and interpret `Yes` as a block-worthy violation.
  3. When Guardian rejects an item, write an audit entry (player, text excerpt hash, category) and notify moderators in the admin channel.
  4. Repeat offenders trigger soft locks (cooldown on commands) tracked via the `players` table.

## Integration Points

- **Pre-pass hooks:**
  - Slash command decorators intercept text fields before the bot hands control to command handlers.
  - Theory submission flows call the moderation service prior to persisting new theories.
- **Post-pass hooks:**
  - `MultiPressGenerator` output runs through moderation before enqueuing press releases.
- The orders dispatcher re-checks press content immediately before sending to Discord in case templates changed while queued.
- **Failure handling:**
  - If the sidecar is unreachable, fall back to prefiler-only mode and raise an admin alert. Operators can decide whether to pause the game.
  - Include a `GREAT_WORK_MODERATION_STRICT` flag to decide whether to hard-block on sidecar downtime or allow degraded operation.

## Operations & Monitoring

- **Telemetry:**
  - Track total moderated items, Guardian invocation counts, and block rates per category.
  - Emit `moderation_sidecar_offline` events when health checks fail.
  - Capture latency percentiles for both passes to spotlight regressions.
- **Runbook additions:**
  - Document restart steps for the Guardian sidecar (systemd service name, Docker compose target).
  - Provide a sample payload for manual validation (`python scripts/moderation_probe.py --text "example"`).
  - Outline escalation path when moderation rejects legitimate player content (manual override, whitelist phrases, etc.).
- **Testing:**
  - Add contract tests that mock the Guardian RPC and confirm the bot blocks/approves text as expected.
  - Include regression samples for each category to guard against policy drift.

## Roadmap Considerations

- Expand the category set to include groundedness/relevance once Gazette copy volume stabilises.
- Explore secondary checks (e.g., Llama Guard) if Guardian false negatives become a concern.
- Evaluate optional caching for repeated short phrases to shave latency off high-volume channels.
- Investigate moderator tooling (dashboard or Discord slash command) for reviewing and clearing moderation hits.

## Dependencies & Next Steps

1. Implement the IPC queue and Guardian RPC client.
2. Wire decorators and press moderation hooks in the bot/service layers.
3. Extend telemetry schema with moderation events.
4. Add operator documentation (TELEMETRY_RUNBOOK, deployment environment variables).
5. Pilot with dry-run logging before enabling hard blocks to tune thresholds and keyword lists.
