# The Great Work: Collaborative Knowledge Game

## Detailed Design Document

_Consolidated from our discussion. Uses the latest choices where things changed. No new content invented._

---

## 1. Core Concept

**The Great Work** is an asynchronous multiplayer game for small groups (typically 4 to 8 players). Players are research leaders in a fantasy or historical world who make public proclamations, compete for reputation, and collaborate or feud to uncover ancient mysteries. Every action is public, performative, and carries reputation stakes—there are no private moves.

- **Time scale:** one real day equals one in-game year.
- **Interface:** play occurs entirely through chat with a Discord bot as the primary interface.
- **Narrative support:** an AI system embodies scholar personalities, remembers history, and generates dramatic public responses.
- **Target audience:** small friend groups that enjoy collaborative worldbuilding, complex strategy, and dramatic roleplay. This is not a mass market product.
- **Core loop:** make bold public claims → marshal evidence and scholars → double down with expeditions → experience spectacular success or failure → live with permanent consequences.
- **Public by default:** all moves generate press releases and scholar commentary. Abandoning a theory or recruiting in secret is impossible—everything is on the record forever.

---

## 2. Key Mechanics

### 2.1 Scholars

A pool of 20 to 30 named scholars exists at any time so that each becomes a memorable character.

- Scholars have distinct personality, expertise, methods, and catchphrases.
- They remember everything: failures, successes, betrayals.
- Grudges, friendships, and rivalries persist across games.
- Example vibe: “Dr Zathras? That backstabber who stole credit for my Bronze Age discovery.”

#### Procedural generation and hand-crafted mix

- Ship a small set of hand-written legends, then allow procedural generation for the rest.
- Scholars can emerge from expeditions as side discoveries and grow into major figures.
- Players can mentor, place, and watch them rise—risking public betrayal if they defect to a rival faction.

#### Memory model

- **Facts:** timestamped canonical events, e.g., “credit stolen on 16 Sep Y53”.
- **Feelings:** emotion scores toward players and scholars that decay slowly but never reach zero. Major betrayals create Scars that do not decay.

### 2.2 Confidence Wager System

Players must declare confidence when they act. The latest tuning is shown below.

| Confidence level      | Reputation if correct | Reputation if wrong | Break-even success rate |
|-----------------------|-----------------------|---------------------|-------------------------|
| Suspect               | +2                    | −1                  | ~33%                    |
| Certain               | +5                    | −7                  | ~58%                    |
| Stake my career       | +15                   | −25                 | ~63%                    |

- **Cooldown:** after any “stake my career”, recruitment chances are halved for two ticks regardless of outcome.
- This pushes honest calibration while keeping drama.

### 2.3 Expedition Types

1. **Research Think Tanks:** theoretical work with existing knowledge (low influence cost).
2. **Field Expeditions:** digs and surveys that find new primary sources (medium cost).
3. **Great Projects:** large science efforts that unlock new research domains (high cost).

### 2.4 Influence Economy

Players earn and spend soft power with five factions rather than a single currency:

- Academic Institutions: recruit talent
- Government: funding and site access
- Industry: equipment and logistics
- Religious Orders: sacred sites and texts
- Foreign Powers: international collaboration

Influence is a five-dimensional vector. Soft caps rise as total reputation rises to prevent single-faction steamrolling.

### 2.5 Spectacular Failure System

Failures can lead to unexpected discoveries.

- “Your Bronze Age flight theory was nonsense, but you discovered advanced metallurgy.”
- “The timeline was wrong by 500 years, but you found evidence of climate catastrophe.”

**Anti-exploit rule:** failure results scale with preparation depth. Thin prep yields scraps. Deep prep yields meaningful sideways progress.

### 2.6 Automatic Press Release Generation

Every action triggers AI-generated public artefacts:

- **Academic Bulletin:** theory submissions and scholar reactions.
- **Research Manifesto:** expedition launches.
- **Discovery Report** or **Retraction Notice:** results.
- **Academic Gossip:** recruitment and social events.

All artefacts remain public, permanent, and citable.

---

## 3. Timing and Pacing

- **Sim time:** one real day equals one in-game year.
- **Gazette cadence:** two digests per day (e.g., 13:00 and 21:00 AEST). Actions thread under each digest.
- **Orders:** players can queue orders any time; orders provide immediate UI feedback while official effects post in the next digest.
- **Symposium:** a weekly event in real time (decadal symposia in fiction) that forces public stances on a hot topic.

This keeps the game idle-friendly and avoids a second job feeling.

---

## 4. Systems and Numbers

### 4.1 Reputation and Influence

- Reputation uses a bounded scale (e.g., −50 to +50). Thresholds unlock or lock social options.
- Influence is tracked per faction as a five-vector with soft caps scaling alongside reputation.

### 4.2 Expedition Resolution

A legible, fair recipe:

1. Roll d100.
2. Add preparation from think tanks (0 to 30).
3. Add expertise matches from team scholars (+5 each, cap +15).
4. Apply site friction and political friction (0 to −25).
5. Confidence affects the payoff, not the success chance.

#### Outcomes

- Below 40: Failure (roll on failure table).
- 40 to 64: Partial success.
- 65 to 84: Solid success.
- 85 and above: Landmark discovery that opens a new domain tag.

### 4.3 Failure Tables

- **Shallow prep:** 60% nothing, 30% minor clue, 10% funny disaster that changes social state.
- **Deep prep:** 40% minor clue, 40% adjacent-field discovery, 20% major sideways unlock.

---

## 5. Procedural Scholar System

### 5.1 Lifecycle

- **Spawn:** from seed lists or as expedition sidecasts (e.g., a local translator who impressed the team).
- **Nurture:** mentor, coauthor, or place them in a lab to raise skill, loyalty, and faction standing.
- **Career beats:** Postdoc → Lecturer → Associate → Chair, with potential divergence to Industry, Government, Religious Orders, or Foreign Powers.
- **Poaching and defection:** timed offers arrive from rivals and factions; defections are always public.
- **Return arcs:** defectors can return with strings attached or become your greatest rivals.

### 5.2 Proc-gen Recipe

- **Table driven** with deterministic seeds for reproducibility.
- **Archetypes:** Empiricist, Visionary, Trickster, Administrator, Gadfly, Field Engineer, Archivist, Mystic, Polymath.
- **Disciplines:** Archaeology, Epigraphy, Metallurgy, Palaeoclimatology, Geodesy, Comparative Myth, Experimental Archaeology, Chronology, Remote Sensing, Conservation.
- **Methods:** textual analysis, survey and trench, material science, experimental reconstruction, satellite and aerial imaging, statistical inference, oral history.
- **Drives:** Truth, Fame, Patronage, Legacy, Piety, Wealth.
- **Vices:** credit theft, cowardice, recklessness, vanity, secrecy, dogmatism.
- **Virtues:** integrity, curiosity, diligence, humility, courage, patience, pedagogy.
- **Stats:** talent, reliability, integrity, theatrics, loyalty, risk appetite (all 0 to 10).
- **Politics tilt:** per faction, −3 to +3.
- **Catchphrases** (examples):
  - “Show me {evidence} or I am not buying it.”
  - “As I have long suspected, {topic} hinges on {concept}.”
  - “Have we tried {reckless_method} yet.”
  - “Bear with me. If {premise}, then {wild leap}.”
- **Taboos:** second author twice in a row; excavation without a conservation plan; slander about a mentor; publishing without data release.
- **Names:** given and surnames by region, with occasional alliteration. Expedition locations bias local name pools.

### 5.3 Emergent Scholars from Digs

- On partial or better outcomes, roll a Discovery Sidecast: Local Junior, Archive Ghost, Industry Whisperer, or Ecclesiastical Adept.
- Each sidecast spawns with a short Gazette scene to enter the meme stream.
- New juniors start as Postdocs with Loyalty 4 to the sponsor. If unattended for three ticks they normalise to Loyalty 2 and become poachable.

### 5.4 Defection Logic

Defection chance each offer window uses a logistic function with these inputs:

- Base temptation from offer quality.
- Recent mistreatment score (e.g., authorship snubs, unpaid promises, public humiliation).
- Ideological alignment with the offering faction.
- Career plateau at current home.
- Negative weights for loyalty and integrity.

```python
def defection_probability(scholar, offer):
    base = offer.quality  # 0 to 1
    mistreatment = recent_mistreatment_score(scholar)  # 0 to 1
    align = faction_alignment(scholar, offer.faction)  # -0.3 to +0.3
    plateau = career_plateau(scholar)  # 0 to 0.4
    loyalty = scholar.stats["loyalty"] / 10  # 0 to 1
    integrity = scholar.stats["integrity"] / 10  # 0 to 1
    x = base + mistreatment + align + plateau - 0.6 * loyalty - 0.4 * integrity
    return 1 / (1 + math.exp(-6 * (x - 0.5)))
```

#### Public outcomes

- If they defect, the Gazette prints the resignation letter, the new contract summary, and reactions. Reputation hits scale with their integrity and how justified the move appears.
- If they refuse, they gain Resolve. Next time they are harder to poach but will expect a raise or title.

### 5.5 Data Model Sketch

**Tables:** players, scholars, factions, relationships, theories, expeditions, offers, events, press_releases, contracts.

**Scholar JSON example:**

```json
{
  "id": "s.coastal-613",
  "name": "Dr Elara Ironquill",
  "seed": 4139021,
  "archetype": "Empiricist",
  "discipline": ["Archaeology"],
  "methods": ["survey and trench", "material science"],
  "drives": ["Truth", "Legacy"],
  "virtues": ["Diligence", "Courage"],
  "vices": ["Dogmatism"],
  "stats": {"talent": 8, "reliability": 9, "integrity": 8, "theatrics": 3, "loyalty": 6, "risk": 4},
  "politics": {"Academia": 2, "Government": 0, "Industry": -1, "Religion": 1, "Foreign": 0},
  "catchphrase": "Show me the artifacts or I am not buying it.",
  "taboos": ["excavation without conservation plan"],
  "memory": {
    "facts": [{"t": "Y51-09-16", "type": "credit_theft", "who": "zathras"}],
    "feelings": {"players": {"sarah": 3}, "scholars": {"zathras": -6}, "decay": 0.98},
    "scars": ["credit_theft"]
  },
  "career": {"tier": "Associate", "track": "Academia", "titles": ["Keeper of Graves"]},
  "contract": {"employer": "Royal Institute", "term_years": 6, "clauses": ["data_release_required"]}
}
```

---

## 6. UX and Flow

### Discord-first approach

Discord provides slash commands, threads, roles, and webhooks. Additional platforms (Signal, Telegram) can be added based on community needs.

#### Channels

- `#orders` for commands
- `#gazette` for digests and threaded events
- `#table-talk` for banter and memes

#### Commands

`/submit_theory`, `/wager`, `/recruit`, `/launch_expedition`, `/conference`, `/status`, `/export_log`

One admin command exists to hotfix if something goes off the rails.

#### Press release discipline

Short, quotable, and consistent. Examples:

- **Academic Bulletin**
  - “Bulletin No. {N} — {Player} submits {theory} at {confidence}. Supporting scholars: {list}. Counter-claims invited before {deadline}.”
- **Research Manifesto**
  - “{Player} announces Expedition {code}. Objective: {objective}. Team: {scholars}. Funding: {factions}.”
- **Discovery Report** or **Retraction Notice**
  - “Outcome: {verdict}. Evidence summary: {3 bullets}. Reputation change: {+x or −y}. Scholarly reactions: {3 one-liners}.”
- **Academic Gossip**
  - “{Scholar}: “{quippy line}”  Context: {trigger}.”

#### Sample digest slice

> Academic Bulletin No. 25  
> Player Sarah submits: “Pre-dynastic sky burials”, confidence: certain. Support: Ironquill, Morrison. Counter-claims close Friday 20:00 AEST.
>
> Discovery Report  
> Expedition AR-17 outcome: Partial. Evidence: aligned cairns, mixed isotope data, anomalous ash layer.  
> Sidecast: “Local surveyor Nadiya Ashraf has accepted a junior fellowship in Remote Sensing.”  
> Reputation change: Sarah +2, Zathras −1.  
> Reactions: Ironquill “Show me more cores.” Blackstone “If the cairns will not align, we can make them.”
>
> Poaching Wire  
> The Foreign Academy offers Nadiya a three year satellite time grant. Counter-offers accepted until next digest.

---

## 7. Narrative Examples

### User stories

- **Public Humiliation Arc:** certainty claim about a volcanic winter fails, reputation craters, Zathras mocks, you discover unusual iron deposits and become the “Failed Volcano Guy” who revolutionised metallurgy.
- **Backstab Revenge:** Zathras supports then steals credit; you need his expertise for a Great Project, so you choose between forgiving him or trusting Morrison's 5 percent genius.
- **Conference Showdown:** weekly symposium forces a public stance on Bronze Age astronomy; Ironquill demands evidence; you go all-in while the community watches.

### Career arc: Dr Sarah Fieldstone

- **Month 1:** bold entrance, partial success, reputation mixed.
- **Months 2–3:** credit theft by Zathras, public academic war, scholars take sides.
- **Months 4–5:** “stake my career” success on a theory he said would fail, vindication.
- **Month 6:** enough influence for Great Projects, half the scholars have strong opinions, choice to reconcile or continue the feud.

### Sample generated scholar: Dr Nadiya Ashraf

- Archetype: Archivist
- Discipline: Remote Sensing
- Methods: satellite and aerial imaging, statistical inference
- Drives: Legacy, Patronage
- Virtues: Diligence, Curiosity
- Vices: Vanity
- Stats: Talent 7, Reliability 6, Integrity 6, Theatrics 5, Loyalty 4, Risk 3
- Catchphrase: “If it cannot be seen from orbit, perhaps it is not there.”
- Taboo: publishing without data release
- Career: Postdoc sponsored by Player Sarah at the Royal Institute
- Hook: poachable by Foreign Powers if promised exclusive satellite time

---

## 8. Technical Implementation

### Core components

- Discord bot handles all player inputs and broadcast outputs.
- LLM integration generates scholar reactions, press releases, and keeps style consistent via persona sheets and templates.
- State manager uses simple JSON events plus SQLite for persistence.
- Daily cron advances sim time, resolves expeditions, triggers events, and updates influence.

### API-first event log

Every action is a public API call that creates an append-only JSON event.

```json
{
  "action": "submit_theory",
  "player": "sarah",
  "claim": "Bronze Age astronomical alignment",
  "confidence": "certain",
  "supporting_scholars": ["ironquill", "morrison"],
  "reputation_wager": 5,
  "public_statement": "The monuments form a star map. I am certain.",
  "generates": ["academic_bulletin", "scholar_reactions", "rival_challenges"]
}
```

### Stack sketch

- Python with `discord.py` and APScheduler for the daily tick.
- SQLite for persistence, schema versioned in repo.
- Seed data for 20 scholars.
- State model: Players, Scholars, Theories, Expeditions, Factions, Relationships, Events, PressReleases.

### LLM wrapper

- Deterministic system prompts per scholar.
- Temperature 0.4 to 0.6 for reactions, 0.2 for official bulletins.
- Persona and style snippets cached.
- Hard character cap per message.
- Strict templates to reduce drift.

### Testing and ops

- Fixed RNG seed mode for reproducible replays.
- Full event log to reconstruct state for audits or memes.

### Cost control

- Two Gazette digests per day rather than many small posts.
- One-line reactions per scholar, batched generation.

### Licensing and safety

- Code: MIT or MPL-2.0.
- Narrative content and persona sheets: CC BY-SA 4.0.
- Simple blocklist for generated text with manual overwrite before posting.

---

## 9. MVP Scope

Target size: about 2 to 4 weeks and roughly 2000 lines of Python.

1. Scholar personality generator plus memory system.
2. Reputation tracker and five-vector influence.
3. Expedition resolver with d100 recipe and failure tables that respect prep depth.
4. Discord bot interface and commands.
5. Daily update cron job and twice daily Gazette digests.
6. Automatic press release generation with templates.
7. Weekly Symposium event.
8. JSON event log plus `/export_log`.
9. One admin hotfix command.
10. Defer Great Projects until after first playtests.

---

## 10. Success Metrics

The game succeeds when:

- Players refer to scholars by name in normal chat, e.g., “Classic Zathras move”.
- Failed theories become group memes.
- Players write real manifestos before expeditions.
- Feuds mirror actual friend group dynamics.
- “Remember when you staked your career on Bronze Age flight?” becomes a running joke.

### Playtest protocol

- Group size: 4 to 6 for the first run.
- Duration: two weeks real time, one Symposium per week.

### Success bar

- At least two nicknames emerge for scholars.
- At least three screenshots of press releases shared in other chats.
- Players voluntarily write one short manifesto each.

If any target is missed, rebalance confidence payoffs and reduce posting volume.

---

## 11. Open Source Potential

Publishing on GitHub allows:

- Other groups to run their own instances with different mythologies.
- Forks for alternate themes (e.g., corporate research, space exploration, culinary history).
- Community contributions of new scholar personas.
- Shared failure tables for the failure-to-discovery pipeline.

### Repo assets

- `scholars_base.yaml` with 10 handcrafted legends.
- `namebanks.yaml` per region.
- `archetypes.yaml`, `disciplines.yaml`, `methods.yaml`, `drives.yaml`, `virtues.yaml`, `vices.yaml`, `taboos.yaml`.
- `failure_tables.yaml` with shallow and deep prep variants.
- `factions.yaml` for the five vectors and sample contracts.
- `settings.yaml` for time scale, payout numbers, and posting cadence.

### MVP coding order for proc-gen

1. Deterministic RNG wrapper with seeds by campaign and event index.
2. Scholar factory from seed or sidecast templates.
3. Memory module with facts, feelings, scars, and decay.
4. Offer and defection system with public Gazette output.
5. Mentorship and authorship actions that affect loyalty and career tier.
6. Admin tools to pin or retire a scholar if tone goes weird.

---

## 12. Example Scholar Personalities

- **Dr Elara Ironquill**
  - Expertise: archaeological methods, empirical evidence.
  - Personality: respects bold claims backed by evidence, despises speculation.
  - Catchphrase: “Show me the artifacts or stop wasting my time.”
  - Drama: does not forgive proven wrong theories.
- **Professor Zathras**
  - Expertise: ancient linguistics.
  - Personality: brilliant and always claims credit.
  - Catchphrase: “As I have always maintained.”
  - Drama: will backstab for sole authorship.
- **“Boom-Boom” Blackstone**
  - Expertise: experimental archaeology, explosives.
  - Personality: solves problems with dynamite, respects spectacular failures.
  - Catchphrase: “Have we tried blowing it up.”
  - Drama: destroyed three sites, found two lost cities.
- **Dr “Wild Card” Morrison**
  - Expertise: comparative mythology.
  - Personality: 5 percent genius, 95 percent nonsense.
  - Catchphrase: “Bear with me here.”
  - Drama: once revolutionised chronology by accident.

---

## 13. Sample Moment

> Academic Bulletin No. 12  
> Sarah submits “Bronze Age astronomical alignment”, certain.  
> Support: Ironquill, Morrison.  
> Counter-claims accepted until Friday 20:00 AEST.
>
> Gossip  
> Zathras: “As I have long argued, the stars favour those who cite me.”  
> Blackstone: “If the sky will not align, I have charges.”

---

## 14. Final Notes

- Keep everything public.
- Tune confidence incentives as given.
- Maintain a slow cadence with twice daily digests and a weekly Symposium.
- Use strict templates and persona sheets to maintain tone and continuity.
- Defer Great Projects until after group momentum builds.
