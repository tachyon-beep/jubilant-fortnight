# Implementation Plan - Full Design Build

Last Updated: 2025-09-19 (Post-Review Update)

## Design Commitment

We're building the full design vision with no deferrals. Great Projects are already implemented correctly. Focus is on completing missing features to deliver the complete game experience.

## Existing Infrastructure to Leverage

The codebase has several partially implemented or unused components that can accelerate development:

1. **Offers Table**: Database table exists but unused - ready for offer/contract mechanics
2. **Followups System**: Working infrastructure for delayed actions (currently used for defection grudges)
3. **Defection Logic**: `evaluate_defection_offer()` method exists in service layer, needs Discord exposure
4. **Career Progression**: `_progress_careers()` method exists, needs player-driven control added
5. **Press Templates**: Robust template system in place, easy to extend for new event types
6. **Event Sourcing**: Complete event log infrastructure for audit trails
7. **Influence System**: Fully functional 5-faction economy with soft caps

## Priority Order

Implementation should proceed in phases to deliver core functionality first.

**Note**: Some backend infrastructure exists (defection evaluation, follow-ups table, offers table) but lacks Discord exposure and full implementation.

### Phase 1 - Core Gameplay (Weeks 1-2)

- Conference mechanics and `/conference` command
- Mentorship system and `/mentor` command
- Generic order batching infrastructure
- Sideways discovery mechanics (influence shifts, queued orders)

### Phase 2 - Community Features (Weeks 3-4)

- Full symposium implementation (topics, voting, participation)
- Admin tools and moderation commands
- Multi-stage defection and return arcs
- Contract and offer mechanics

### Phase 3 - Polish & Narrative (Weeks 5-6)

- LLM narrative generation with persona voices
- Public web archive with permalinks
- Enhanced status displays and telemetry
- Moderation and safety systems

## 1. Mentorship System and Scholar Careers

- **Priority: HIGH** - Core gameplay mechanic missing
- Add player-driven mentorship replacing automatic career progression【F:great_work/service.py†L617-L686】
- Create `/mentor` and `/assign_lab` Discord commands with validation
- Queue mentorship orders for batch resolution during digests
- Persist mentorship relationships and career advancement events

**Deliverables:**

- Database: Add `mentorships` table with mentor_id, scholar_id, start_date, status
- Service: `queue_mentorship()`, `resolve_mentorships()` methods (note: `_progress_careers()` exists but is automatic only)
- Discord: `/mentor <scholar>` and `/assign_lab <scholar> <lab>` commands (currently missing)
- Press: Mentorship announcements and career advancement notices

**Implementation Steps:**

1. Create mentorships table migration
2. Add MentorshipOrder dataclass
3. Implement queue/resolve logic in GameService
4. Add Discord command handlers
5. Create press templates for mentorship events

## 2. Conference Mechanics

- **Priority: HIGH** - Major missing gameplay feature
- Implement public wager conferences with reputation stakes
- Create `/conference` Discord command for theory debates
- Apply existing confidence wager mechanics to conference outcomes
- Generate press releases for conference proceedings

**Deliverables:**

- Discord: `/conference <theory> <confidence>` command
- Service: `launch_conference()` and `resolve_conference()` methods
- Database: Conference queue table similar to expeditions
- Press: Conference announcements, debate transcripts, outcome reports

**Implementation Steps:**

1. Create conferences table (similar to expeditions table structure)
2. Add ConferenceOrder dataclass (similar to existing ExpeditionOrder)
3. Implement launch/queue/resolve logic in GameService
4. Add `/conference` Discord slash command
5. Create conference press templates (extend press.py)

## 3. Generic Order Batching Infrastructure

- **Priority: HIGH** - Required for mentorship and conferences
- Create unified order queue system for all delayed actions
- Support different order types (mentorship, conference, contract)
- Batch resolution during digest processing
- Maintain order history and audit trail

**Deliverables:**

- Database: Generic `orders` table with type, payload, scheduled_for (note: expeditions table already exists)
- Service: `queue_order()`, `resolve_orders()` methods
- Model: OrderType enum, Order base class
- Integration: Update digest processing to resolve all order types (currently only handles expeditions and followups)

**Implementation Steps:**

1. Design generic order schema
2. Create orders table migration
3. Implement order queue/resolution framework
4. Migrate expeditions to use new system
5. Add mentorship/conference order types

## 4. Sideways Discovery Mechanics

- **Priority: HIGH** - Core gameplay feature incomplete
- Make sideways discoveries mechanically meaningful
- Trigger faction influence shifts from discoveries
- Queue follow-up orders and research threads
- Generate multi-stage gossip chains

**Deliverables:**

- Service: Side effect registry and application logic
- Model: SidewaysEffect class with influence/order payloads
- Database: Track discovery chains and consequences
- Press: Multi-part discovery narratives

**Implementation Steps:**

1. Design sideways effect types and triggers
2. Map discoveries to mechanical outcomes
3. Implement effect application in resolver
4. Create follow-up order generation
5. Test discovery chain propagation

## 5. Symposium Implementation

- **Priority: MEDIUM** - Weekly community engagement feature
- Replace existing heartbeat (`_host_symposium` in scheduler.py) with full topic selection system
- Add voting mechanics and participation tracking
- Generate outcomes based on community consensus
- Archive symposium proceedings

**Deliverables:**

- Service: Topic selection algorithm, vote tallying
- Discord: `/symposium_vote <option>` command
- Database: Symposium topics, votes, outcomes tables
- Press: Topic announcements, vote reminders, outcome summaries

**Implementation Steps:**

1. Design symposium topic selection logic
2. Create voting tables and mechanics
3. Implement participation tracking
4. Add Discord voting commands
5. Generate symposium outcome press

## 6. Admin Tools and Moderation

- **Priority: MEDIUM** - Operational necessity
- Create `/gw_admin` command group for moderators
- Implement reputation/influence adjustments
- Add order cancellation and defection triggers
- Ensure all admin actions are audited

**Deliverables:**

- Discord: `/gw_admin` command group with subcommands (completely missing)
- Service: Admin override methods with audit logging (note: `evaluate_defection_offer` exists but not exposed)
- Security: Permission checks for admin-only commands
- Audit: Admin action event types and press releases

**Implementation Steps:**

1. Create admin command group structure
2. Implement permission checking
3. Add adjust_reputation, adjust_influence methods
4. Create cancel_order, force_defection methods
5. Ensure all actions generate audit events

## 7. Multi-Stage Defection Arcs

- **Priority: LOW** - Enhancement to existing feature
- Extend follow-ups to support negotiation chains
- Add return offers and counter-offers
- Create rival contract mechanics
- Generate press for each negotiation stage

**Deliverables:**

- Model: Stateful follow-up payloads for negotiations
- Service: Multi-step defection resolution logic (note: `_resolve_followups` exists but is single-step)
- Database: Enhanced followups table with state tracking (table exists with basic schema)
- Press: Negotiation updates, counter-offer announcements (note: `defection_notice` template exists)

**Implementation Steps:**

1. Design negotiation state machine
2. Extend followups table schema
3. Implement multi-step resolution
4. Add negotiation press templates
5. Test complex defection scenarios

## 8. Public Web Archive

- **Priority: LOW** - Nice-to-have for permanence
- Create static site generator for press archive
- Implement automatic export during digests
- Deploy to GitHub Pages or S3
- Add permalink system for citations

**Deliverables:**

- Tool: `export_gazette.py` static site generator
- Templates: HTML templates for press archive
- Automation: Export hook in digest processing
- Deployment: GitHub Actions or S3 sync

**Implementation Steps:**

1. Create static site generator tool
2. Design HTML templates
3. Add export hook to scheduler
4. Set up GitHub Pages deployment
5. Document archive URL structure

## 9. LLM Narrative Integration

- **Priority: MEDIUM** - Essential for full narrative experience
- Integrate OpenAI/Anthropic API for persona voices
- Implement prompt templates for each scholar
- Add moderation and safety controls
- Maintain template fallbacks

**Deliverables:**

- Integration: LLM API client with retry logic
- Prompts: Persona prompt templates
- Safety: Blocklist, rate limiting, content filtering
- Config: API keys, model selection, fallback settings

**Implementation Steps:**

1. Add LLM client library
2. Create prompt template system
3. Implement safety controls
4. Add configuration options
5. Test with gradual rollout

## Current Test Coverage

Existing test files:

- `test_scholar_generation.py` - Scholar generation
- `test_expedition_resolver.py` - d100 mechanics
- `test_defection_probability.py` - Loyalty curves
- `test_game_service.py` - Service integration
- `test_press_templates.py` - Press generation
- `test_rng_determinism.py` - RNG consistency
- Additional coverage tests for edge cases

## Testing Strategy

Each new feature should include:

- Unit tests for new service methods
- Integration tests for Discord commands
- Database migration tests
- Press generation validation
- End-to-end digest processing tests

## Success Metrics

Track implementation success through:

- Feature completion percentage
- Test coverage metrics
- Discord command usage statistics
- Player engagement with new features
- Press archive accessibility

## Risk Mitigation

- **Database migrations**: Test on copy of production data
- **Discord commands**: Deploy to test server first
- **Order batching**: Maintain backward compatibility
- **LLM integration**: Keep template fallbacks functional
- **Full feature scope**: Prioritize core gameplay over polish if timeline pressures emerge

## Note on Scope

This plan commits to the full design vision. All features are targeted for implementation within the 6-week timeline. If timeline pressures emerge, deprioritize Phase 3 polish features rather than Phase 1-2 core gameplay.
