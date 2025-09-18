# Qdrant Document Schemas for The Great Work

## Document Categories

All documents stored in Qdrant should follow these schemas for consistency and optimal retrieval.

## 1. Game Mechanics Documents

### Game Mechanics Schema

```json
{
  "category": "mechanics",
  "subcategory": "wagers|expeditions|influence|scholars|timeline",
  "content": "Complete description of the mechanic",
  "keywords": ["relevant", "search", "terms"],
  "version": "game version or date"
}
```

### Game Mechanics Examples

#### Confidence Wagers

```plaintext
Category: mechanics/wagers
Content: The confidence wager system requires players to declare their certainty level when making theories or
launching expeditions. Three levels exist:
- SUSPECT: Low risk/reward (+2/-1 reputation), approximately 33% break-even rate
- CERTAIN: Moderate risk/reward (+5/-7 reputation), approximately 58% break-even rate
- STAKE MY CAREER: High risk/reward (+15/-25 reputation), approximately 63% break-even rate
Special rule: After any "stake my career" declaration, recruitment success rates are halved for two digest cycles
(one full day) regardless of outcome.
Keywords: confidence, wager, reputation, stakes, career, cooldown, recruitment
```

#### Expedition Resolution

```plaintext
Category: mechanics/expeditions
Content: Expedition resolution follows a d100 + modifiers system:
1. Base roll: d100
2. Add preparation modifiers: expertise (+0 to +20), resources (+0 to +10), timing (+0 to +5)
3. Subtract friction: site difficulty (0 to -15), political tensions (0 to -10)
4. Final score determines outcome:
   - Below 40: FAILURE (consult failure tables by expedition type and depth)
   - 40-64: PARTIAL (sideways discovery possible)
   - 65-84: SUCCESS (objectives achieved)
   - 85+: LANDMARK (major breakthrough + sideways discovery)
Keywords: expedition, resolution, d100, modifiers, success, failure, partial, landmark
```

## 2. Scholar Documents

### Scholar Schema

```json
{
  "category": "scholar",
  "scholar_id": "unique_identifier",
  "name": "Full name with title",
  "content": "Complete profile and history",
  "relationships": ["list of related scholars"],
  "faction_alignment": "primary faction",
  "career_stage": "current position"
}
```

### Scholar Examples

#### Scholar Profile

```plaintext
Category: scholar
Scholar ID: fieldstone_sarah
Name: Dr. Sarah Fieldstone
Content: Bronze Age specialist renowned for empirical methodology and skepticism toward grand unified theories.
Discovered revolutionary iron dating techniques during failed volcanic expedition (Y53). Known for meticulous
documentation and requiring three independent sources before accepting claims.
Personality traits: Methodical, skeptical, protective of reputation.
Catchphrase: "Extraordinary claims require extraordinary evidence, and even then I want a second opinion."
Career: Started as Postdoc under Professor Hadrian, promoted to Associate after iron discovery, currently heads
the Empirical Methods Lab.
Relationships: Professional rivalry with Dr. Zathras (credit dispute Y53), grudging respect for Morrison despite
theoretical differences, mentors young empiricists.
Scars: Betrayal by Zathras when he published her preliminary findings without attribution.
Keywords: Bronze Age, metallurgy, empirical, skeptical, fieldstone, iron, dating methods
```

#### Scholar Relationship

```plaintext
Category: scholar/relationship
Content: The Fieldstone-Zathras rivalry began in Year 53 when both scholars investigated Bronze Age trade routes.
Fieldstone shared preliminary findings with Zathras in confidence, seeking peer review. Zathras published a
bulletin claiming the discoveries as his own, earning promotion to Full Professor. Fieldstone's subsequent
correction was seen as "sour grapes" despite evidence. The betrayal created a permanent Scar in Fieldstone's
memory model. She now refuses collaboration with Zathras and actively undermines his theories when possible.
This rivalry affects team formation - they cannot be recruited for the same expedition.
Keywords: rivalry, betrayal, fieldstone, zathras, credit, scar, Y53, trade routes
```

## 3. Press Release Documents

### Press Release Schema

```json
{
  "category": "press",
  "press_type": "bulletin|manifesto|report|retraction|gossip",
  "bulletin_number": "sequential ID",
  "content": "Full press text",
  "participants": ["involved parties"],
  "timestamp": "Year.Day",
  "outcome": "if resolved"
}
```

### Press Release Examples

#### Academic Bulletin

```plaintext
Category: press/bulletin
Bulletin Number: 247
Content: ACADEMIC BULLETIN #247 - YEAR 56, DAY 89
HEADLINE: Morrison's Volcanic Winter Theory Gains Momentum
Professor James Morrison, backed by industrial magnate Rothschild, announced a Great Project expedition to
definitively prove Bronze Age volcanic winter. "The ash layers don't lie," Morrison declared at yesterday's
symposium. The ambitious project will require unprecedented cooperation between Academic, Government, and Industry
factions. Morrison has wagered his career on the outcome. Team formation begins next digest cycle. Skeptics, led
by Dr. Fieldstone, demand "more than dramatic pronouncements and ash samples."
Participants: Morrison (lead), Rothschild (funding), Fieldstone (opposition)
Stakes: Stake My Career, Great Project costs (2 Academic, 2 Government, 2 Industry)
Keywords: Morrison, volcanic winter, Great Project, stake career, Rothschild, Fieldstone
```

#### Discovery Report

```plaintext
Category: press/report
Content: DISCOVERY REPORT - EXPEDITION EXP_056_089
OUTCOME: Landmark Success
The Morrison expedition to Santorini has achieved a landmark discovery, validating the volcanic winter hypothesis
with overwhelming evidence. Core samples reveal a precise ash layer dated to 1628 BCE, with pottery fragments both
above and below confirming timeline. Additionally, the team discovered (sideways finding) a preserved workshop with
Late Bronze Age metallurgical tools that Dr. Fieldstone grudgingly admits "revolutionize our understanding of
technological progression." Morrison's reputation soars (+15), while even critics acknowledge the thoroughness of
evidence. The discovery unlocks new research domain: Climate Catastrophe Studies.
Participants: Morrison, Fieldstone, Ironquill, Rothschild
Outcome: Landmark success, +15 reputation, new domain unlocked
Keywords: landmark, discovery, Morrison, volcanic winter, Santorini, validation, climate studies
```

## 4. Expedition Documents

### Expedition Schema

```json
{
  "category": "expedition",
  "expedition_code": "unique ID",
  "content": "Full expedition details",
  "status": "queued|resolved",
  "expedition_type": "think_tank|field|great_project",
  "outcome": "if resolved"
}
```

### Expedition Examples

#### Queued Expedition

```plaintext
Category: expedition/queued
Expedition Code: EXP_057_023
Content: THINK TANK - "Reinterpreting Minoan Collapse"
Objective: Synthesize recent volcanic evidence with existing collapse theories
Team: Dr. Morrison (lead theorist), Dr. Ironquill (chronicler), Dr. Blackwood (climatologist)
Preparation: Shallow (rushed to capitalize on momentum)
Confidence: Certain
Influences: 1 Academic (think tank cost)
Modifiers: +12 expertise, -5 rushed preparation, +7 total
Scheduled: Resolution at Evening Digest Y57.D24
Keywords: think tank, Morrison, Minoan, collapse, volcanic, scheduled
```

## 5. Game State Documents

### Game State Schema

```json
{
  "category": "gamestate",
  "state_type": "player|timeline|roster|event",
  "content": "State information",
  "timestamp": "when recorded"
}
```

### Game State Examples

#### Player Status

```plaintext
Category: gamestate/player
Player ID: player_001
Content: Player "ArchaeologyFan" current status:
- Reputation: +23 (can attempt all expedition types)
- Influence: Academic 4/7, Government 3/5, Industry 1/4, Religious 0/4, Foreign 2/4
- Cooldowns: Recruitment penalty active (1 digest remaining) from stake_career at Y57.D18
- Recent actions: Successful field expedition (+5 rep), Failed recruitment (cooldown applied)
- Upcoming: Think tank scheduled for Y57.D20 resolution
Keywords: player status, reputation, influence, cooldowns, archaeologyfan
```

#### Timeline Event

```plaintext
Category: gamestate/timeline
Content: YEAR 57, DAY 19 - Morning Digest
Events processed:
1. Timeline advanced one year (Day 19 = Year 57 in game time)
2. Cooldowns decremented (3 players now eligible for full recruitment)
3. Roster maintenance: Retired Dr. Hadrian (age limit), Generated Dr. Newbridge (materials science)
4. Career progressions: Fieldstone promoted to Full Professor, Ironquill remains Associate
5. Expeditions resolved: 2 successes, 1 partial, 1 failure
6. Follow-ups triggered: Zathras defection offer delayed to Y57.D22
Press generated: 7 items (see Bulletin #248-254)
Keywords: digest, timeline, Y57.D19, roster, careers, expeditions
```

## 6. Symposium Documents

### Symposium Schema

```json
{
  "category": "symposium",
  "symposium_number": "sequential ID",
  "content": "Topic and outcomes",
  "participants": ["who voted/participated"],
  "result": "consensus or division"
}
```

### Symposium Examples

#### Symposium Record

```plaintext
Category: symposium
Symposium Number: 8
Content: WEEKLY SYMPOSIUM #8 - "The Role of Climate in Bronze Age Collapse"
Topic: Following Morrison's discovery, the community debated whether climate should be considered the primary driver of Bronze Age collapse.
Positions:
- Climate Primary (Morrison, Blackwood): Volcanic winter caused agricultural collapse, forcing migrations
- Multi-Factor (Fieldstone, Ironquill): Climate was one of many factors including war, trade disruption
- Climate Minimal (Zathras): Political factors predominated, climate is overemphasized
Voting: 5 Climate Primary, 3 Multi-Factor, 1 Climate Minimal
Outcome: Climate Primary consensus achieved. Research bonus (+5) to climate-related expeditions next week.
Keywords: symposium, climate, Bronze Age, collapse, Morrison, consensus, voting
```

## Best Practices for Document Storage

### 1. Completeness

Every document should contain enough context to be understood independently. Include:

- WHO is involved
- WHAT happened or is being described
- WHEN it occurred or applies
- WHY it matters
- HOW it affects gameplay

### 2. Cross-References

Always mention related documents or events:

- "Following up on Bulletin #234"
- "Related to the Fieldstone-Zathras rivalry"
- "Builds on Expedition EXP_055_012"

### 3. Keywords

Include varied search terms:

- Full names and shortened versions
- Concept names and synonyms
- Time references (years, digest numbers)
- Mechanical terms

### 4. Consistency

Maintain consistent formatting:

- Dates as "Year XX, Day YY" or "YXX.DYY"
- Names with titles on first mention
- Reputation always with + or - sign
- Influence as "current/cap"

### 5. Updates vs New Documents

- UPDATE existing documents for: Status changes, career progressions
- CREATE new documents for: New events, discoveries, relationships

## Search Optimization

### Effective Content Structure

1. **Lead with the most important information** - First sentence should contain the key fact

2. **Use consistent terminology** - "reputation" not "rep", "expedition" not "exp"

3. **Include temporal context** - Always mention when something happened or will happen

4. **Specify relationships explicitly** - "A rivals B" and "B rivals A" for bidirectional search

5. **Quantify when possible** - Include specific numbers for reputation, influence, modifiers

### Query Matching Patterns

Store information to match common query patterns:

- **"How does X work?"** → Start with "X is a system/mechanic that..."
- **"What happened with Y?"** → Start with "EVENT: Y occurred when..."
- **"Who is Z?"** → Start with "Z is a [role/title] who..."
- **"What's the relationship between A and B?"** → Start with "A and B have a [type] relationship..."

## Document Lifecycle

### 1. Initial Creation

When a new game element is introduced:

- Create comprehensive base document
- Include all known information
- Add placeholder for future updates

### 2. Event Updates

After game events:

- Store new press releases immediately
- Update scholar relationships if changed
- Record expedition outcomes
- Update player status

### 3. Periodic Consolidation

After each digest:

- Store digest summary
- Update timeline document
- Consolidate related events
- Archive completed expeditions

### 4. Relationship Evolution

When relationships change:

- Create new relationship document for major changes
- Update existing profiles with new information
- Maintain history of relationship evolution

## Validation Checklist

Before storing any document, verify:

- [ ] Content is complete and self-contained
- [ ] Category and subcategory are correct
- [ ] Keywords cover various search angles
- [ ] Cross-references are included where relevant
- [ ] Formatting is consistent with schemas
- [ ] No duplicate information already stored
- [ ] Temporal context is clear
- [ ] Mechanical effects are specified

This schema guide ensures consistent, searchable, and comprehensive knowledge storage for The Great Work's Qdrant integration.
