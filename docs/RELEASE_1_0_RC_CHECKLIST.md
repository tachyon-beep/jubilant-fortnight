# Release Candidate Checklist (1.0.0-rc1)

Use this checklist when preparing the 1.0.0 release candidate. Complete each section before tagging and notifying reviewers.

## 1. Version & Documentation

- [ ] Confirm version badge in `README.md` matches `1.0.0-rc1` and test badge reflects latest pytest count.
- [ ] Update `CHANGELOG.md` with RC highlights and ensure entries reference new tooling (deployment smoke, roadmap consolidation).
- [ ] Verify `docs/ROADMAP.md` captures all post-1.0 concepts (Gameplay, Telemetry Cohorts, Player Portal).
- [ ] Review `docs/ARCHIVE_LOG.md` and record any additional documents moved or pending deletion.
- [ ] Ensure `docs/deployment.md`, `docs/TELEMETRY_RUNBOOK.md`, and `docs/SAFETY_PLAN.md` reflect latest Guardian incident response steps.

## 2. Preflight Smoke & Tests

- [ ] `python -m great_work.tools.deployment_smoke` (confirm output shows only OK/WARNING lines).
- [ ] `pytest -q` (expect 280+ tests; investigate any failures).
- [ ] Optional: `python -m great_work.tools.simulate_seasonal_economy --config docs/examples/seasonal_scenario.json` if seasonal tuning is under review.
- [ ] Validate Docker Compose boot (`docker compose up -d`) and check `docker compose logs -f bot` for telemetry/Guardian health messages.

## 3. Operational Snapshot

- [ ] `/telemetry_report` in staging shows green health checks (digest runtime, queue depth, seasonal debt, Guardian metrics).
- [ ] `/gw_admin moderation_recent --since 24h` returns expected categories; override list is empty or justified.
- [ ] `/gw_admin calibration_snapshot` posts successfully to the admin channel.
- [ ] Telemetry dashboard (`/api/kpi_history`, `/api/calibration_snapshot`) responds with JSON.

## 4. Packaging & Tagging

- [ ] Create a release branch if required (e.g., `release/1.0.0-rc1`).
- [ ] Tag the commit (`git tag -a v1.0.0-rc1 -m "1.0.0 release candidate"`).
- [ ] Draft GitHub release notes summarising major features, tooling changes, and links to deployment docs.
- [ ] Attach any supporting assets (archive snapshot, screenshots) if needed.

## 5. Communication & Handoff

- [ ] Share the release summary in the ops channel (include smoke/test results and outstanding risks).
- [ ] Update issue tracker / project board to reflect RC status.
- [ ] Schedule post-RC review (bugs triage, telemetry monitoring cadence).

## 6. Post-Release Follow-up

- [ ] Monitor telemetry alerts for 24–48 hours; document incidents in ops log.
- [ ] Begin backlog grooming for roadmap items (refer to `docs/ROADMAP.md`).
- [ ] Archive superseded documents listed in `docs/ARCHIVE_LOG.md` once RC graduates to GA.

Keep this checklist in sync with CI and operational tooling. Update it when new smoke tests or deployment steps are added.

