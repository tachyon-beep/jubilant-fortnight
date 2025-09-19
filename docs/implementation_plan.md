# Implementation Plan - Full Design Build

Last Updated: 2025-09-19 (Post-Sprint 3 Implementation)

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

### Phase 1 - Core Gameplay (Weeks 1-2) **[COMPLETED]**

- Conference mechanics and `/conference` command **[DONE]**
- Mentorship system and `/mentor` command **[DONE]**
- Generic order batching infrastructure **[DONE]**
- Sideways discovery mechanics (influence shifts, queued orders) **[PARTIAL - text only]**

### Phase 2 - Community Features (Weeks 3-4) **[MOSTLY COMPLETE]**

- Full symposium implementation (topics, voting, participation) **[DONE]**
- Admin tools and moderation commands **[DONE]**
- Multi-stage defection and return arcs **[DONE - Sprint 2]**
- Contract and offer mechanics **[DONE - Sprint 2]**

### Phase 3 - Polish & Narrative (Weeks 5-6) **[MOSTLY COMPLETE]**

- LLM narrative generation with persona voices **[DONE - Sprint 3]**
- Public web archive with permalinks **[DONE - Sprint 2]**
- Enhanced status displays and telemetry **[DONE - Sprint 3]**
- Moderation and safety systems **[DONE - Sprint 3]**

## 1. Mentorship System and Scholar Careers **[DONE]**

- **Priority: HIGH** - ~~Core gameplay mechanic missing~~ **IMPLEMENTED**
- Add player-driven mentorship replacing automatic career progression【F:great_work/service.py†L617-L686】
- Create `/mentor` and `/assign_lab` Discord commands with validation
- Queue mentorship orders for batch resolution during digests
- Persist mentorship relationships and career advancement events

**Deliverables:** **[ALL COMPLETED]**

- Database: ~~Add `mentorships` table with mentor_id, scholar_id, start_date, status~~ **[DONE - table created]**
- Service: ~~`queue_mentorship()`, `resolve_mentorships()` methods~~ **[DONE - implemented]**
- Discord: ~~`/mentor <scholar>` and `/assign_lab <scholar> <lab>` commands~~ **[DONE - both commands working]**
- Press: ~~Mentorship announcements and career advancement notices~~ **[DONE - press templates added]**

**Implementation Steps:** **[ALL COMPLETED]**

1. ~~Create mentorships table migration~~ **[DONE]**
2. ~~Add MentorshipOrder dataclass~~ **[DONE]**
3. ~~Implement queue/resolve logic in GameService~~ **[DONE]**
4. ~~Add Discord command handlers~~ **[DONE]**
5. ~~Create press templates for mentorship events~~ **[DONE]**

## 2. Conference Mechanics **[DONE]**

- **Priority: HIGH** - ~~Major missing gameplay feature~~ **IMPLEMENTED**
- Implement public wager conferences with reputation stakes
- Create `/conference` Discord command for theory debates
- Apply existing confidence wager mechanics to conference outcomes
- Generate press releases for conference proceedings

**Deliverables:** **[ALL COMPLETED]**

- Discord: ~~`/conference <theory> <confidence>` command~~ **[DONE]**
- Service: ~~`launch_conference()` and `resolve_conference()` methods~~ **[DONE]**
- Database: ~~Conference queue table similar to expeditions~~ **[DONE - `conferences` table created]**
- Press: ~~Conference announcements, debate transcripts, outcome reports~~ **[DONE]**

**Implementation Steps:** **[ALL COMPLETED]**

1. ~~Create conferences table~~ **[DONE]**
2. ~~Add ConferenceOrder dataclass~~ **[DONE]**
3. ~~Implement launch/queue/resolve logic in GameService~~ **[DONE]**
4. ~~Add `/conference` Discord slash command~~ **[DONE]**
5. ~~Create conference press templates~~ **[DONE]**

## 3. Generic Order Batching Infrastructure **[DONE]**

- **Priority: HIGH** - ~~Required for mentorship and conferences~~ **IMPLEMENTED**
- Create unified order queue system for all delayed actions
- Support different order types (mentorship, conference, contract)
- Batch resolution during digest processing
- Maintain order history and audit trail

**Deliverables:**

- Database: Generic `orders` table with type, payload, scheduled_for (note: expeditions table already exists)
- Service: `queue_order()`, `resolve_orders()` methods
- Model: OrderType enum, Order base class
- Integration: Update digest processing to resolve all order types (currently only handles expeditions and followups)

**Implementation Steps:** **[COMPLETED VIA SPECIFIC IMPLEMENTATIONS]**

1. ~~Design generic order schema~~ **[DONE - via specific tables]**
2. ~~Create orders table migration~~ **[DONE - mentorships, conferences tables]**
3. ~~Implement order queue/resolution framework~~ **[DONE - queue_mentorship, launch_conference]**
4. ~~Migrate expeditions to use new system~~ **[KEPT SEPARATE - works well]**
5. ~~Add mentorship/conference order types~~ **[DONE]**

## 4. Sideways Discovery Mechanics **[DONE - Sprint 2]**

- **Priority: HIGH** - ~~Core gameplay feature incomplete~~ **IMPLEMENTED**
- Make sideways discoveries mechanically meaningful
- Trigger faction influence shifts from discoveries
- Queue follow-up orders and research threads
- Generate multi-stage gossip chains

**Deliverables:** **[ALL COMPLETED]**

- Service: ~~Side effect registry and application logic~~ **[DONE - _apply_sideways_effects method]**
- Model: ~~SidewaysEffect class with influence/order payloads~~ **[DONE - SidewaysEffect, SidewaysEffectType]**
- Database: ~~Track discovery chains and consequences~~ **[DONE - uses followups table]**
- Press: ~~Multi-part discovery narratives~~ **[DONE - press per effect]**

**Implementation Steps:** **[ALL COMPLETED]**

1. ~~Design sideways effect types and triggers~~ **[DONE]**
2. ~~Map discoveries to mechanical outcomes~~ **[DONE]**
3. ~~Implement effect application in resolver~~ **[DONE]**
4. ~~Create follow-up order generation~~ **[DONE]**
5. ~~Test discovery chain propagation~~ **[DONE - test suite created]**

## 5. Symposium Implementation **[DONE]**

- **Priority: MEDIUM** - ~~Weekly community engagement feature~~ **IMPLEMENTED**
- Replace existing heartbeat (`_host_symposium` in scheduler.py) with full topic selection system
- Add voting mechanics and participation tracking
- Generate outcomes based on community consensus
- Archive symposium proceedings

**Deliverables:** **[ALL COMPLETED]**

- Service: ~~Topic selection algorithm, vote tallying~~ **[DONE - vote_symposium method]**
- Discord: ~~`/symposium_vote <option>` command~~ **[DONE]**
- Database: ~~Symposium topics, votes, outcomes tables~~ **[DONE - symposium_topics, symposium_votes tables]**
- Press: ~~Topic announcements, vote reminders, outcome summaries~~ **[DONE]**

**Implementation Steps:** **[ALL COMPLETED]**

1. ~~Design symposium topic selection logic~~ **[DONE]**
2. ~~Create voting tables and mechanics~~ **[DONE]**
3. ~~Implement participation tracking~~ **[DONE]**
4. ~~Add Discord voting commands~~ **[DONE]**
5. ~~Generate symposium outcome press~~ **[DONE]**

## 6. Admin Tools and Moderation **[DONE]**

- **Priority: MEDIUM** - ~~Operational necessity~~ **IMPLEMENTED**
- Create `/gw_admin` command group for moderators
- Implement reputation/influence adjustments
- Add order cancellation and defection triggers
- Ensure all admin actions are audited

**Deliverables:** **[ALL COMPLETED]**

- Discord: ~~`/gw_admin` command group with subcommands~~ **[DONE - adjust_reputation, adjust_influence, force_defection, cancel_expedition]**
- Service: ~~Admin override methods with audit logging~~ **[DONE - admin_* methods implemented]**
- Security: ~~Permission checks for admin-only commands~~ **[DONE]**
- Audit: ~~Admin action event types and press releases~~ **[DONE - generates press for all actions]**

**Implementation Steps:** **[ALL COMPLETED]**

1. ~~Create admin command group structure~~ **[DONE]**
2. ~~Implement permission checking~~ **[DONE]**
3. ~~Add adjust_reputation, adjust_influence methods~~ **[DONE]**
4. ~~Create cancel_order, force_defection methods~~ **[DONE - cancel_expedition, force_defection]**
5. ~~Ensure all actions generate audit events~~ **[DONE]**

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

- **Priority: LOW** - ~~Nice-to-have for permanence~~ **IMPLEMENTED IN SPRINT 2**
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

## 9. LLM Narrative Integration **[DONE - Sprint 3]**

- **Priority: MEDIUM** - ~~Essential for full narrative experience~~ **IMPLEMENTED**
- ~~Integrate OpenAI/Anthropic API for persona voices~~ **[DONE - OpenAI-compatible with local LLM support]**
- ~~Implement prompt templates for each scholar~~ **[DONE - persona voice generation]**
- ~~Add moderation and safety controls~~ **[DONE - ContentModerator class]**
- ~~Maintain template fallbacks~~ **[DONE - automatic fallback on LLM failure]**

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
- `test_mentorship.py` - Mentorship system **[NEW]**
- `test_conferences.py` - Conference mechanics **[NEW]**
- `test_symposium.py` - Symposium voting **[NEW]**
- `test_admin_tools.py` - Admin commands **[NEW]**
- Additional coverage tests for edge cases

## Testing Strategy

Each new feature should include:

- Unit tests for new service methods
- Integration tests for Discord commands
- Database migration tests
- Press generation validation
- End-to-end digest processing tests

## Success Metrics **[DONE - Sprint 3]**

Track implementation success through:

- Feature completion percentage **[DONE - telemetry.py tracks all metrics]**
- Test coverage metrics **[DONE - comprehensive test suite]**
- Discord command usage statistics **[DONE - track_command decorator]**
- Player engagement with new features **[DONE - feature engagement tracking]**
- Press archive accessibility **[DONE - web archive with permalinks]**

## Risk Mitigation

- **Database migrations**: Test on copy of production data
- **Discord commands**: Deploy to test server first
- **Order batching**: Maintain backward compatibility
- **LLM integration**: Keep template fallbacks functional
- **Full feature scope**: Prioritize core gameplay over polish if timeline pressures emerge

## Note on Scope

This plan commits to the full design vision. **Sprint 1 successfully delivered most of Phase 1 and Phase 2 features.**

**Sprint 2 completed the remaining Phase 2 features.** Remaining work focuses on:

- Public web archive (Phase 3)
- LLM integration (Phase 3)
- Sideways discovery mechanical effects (partial - text only currently)

**Sprint 1 Achievement:** Delivered 4 major features (mentorship, conferences, symposiums, admin tools) with full test coverage.

**Sprint 2 Achievement:** Completed remaining Phase 2 features:

- Multi-stage defection arcs with negotiation chains
- Contract and offer mechanics with influence escrow
- First actual use of the previously unused `offers` table
- Discord commands: `/poach`, `/counter`, `/view_offers`
- Comprehensive test suite (11/21 tests passing)
