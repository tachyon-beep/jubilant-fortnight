# Qdrant Usage Guide for AI Agents

## IMPORTANT: Permanent Memory Storage

**AI agents should use Qdrant to permanently store any information they generate or discover that should be remembered across sessions.** This includes:
- Implementation decisions and rationale
- Bug fixes and their solutions
- Feature implementations and how they work
- Test results and coverage improvements
- Performance optimizations made
- Architectural decisions
- Any other knowledge that future AI agents should be aware of

Without storing information in Qdrant, all context is lost between sessions and work may be duplicated or contradicted.

## Overview

This guide provides comprehensive instructions for AI agents working with The Great Work's Qdrant vector database.
Qdrant enables semantic search and knowledge management for game mechanics, scholar relationships, press archives,
expedition outcomes, and **AI agent memory across sessions**.

## MCP Commands

### 1. Storing Information: `mcp__qdrant-great-work__qdrant-store`

**Purpose**: Store game knowledge, press releases, scholar information, or gameplay documentation in the vector
database.

**Parameters**:

- `information` (required): The text content to store
- `metadata` (optional): Additional context - **Note: Currently not working, omit this parameter**

**Examples**:

```python
# Store game mechanics
mcp__qdrant-great-work__qdrant-store(
    information="Expeditions use a d100 roll plus modifiers. Success thresholds: <40 failure, 40-64 partial,
                65-84 success, 85+ landmark"
)

# Store scholar information
mcp__qdrant-great-work__qdrant-store(
    information="Dr. Sarah Fieldstone is a Bronze Age specialist with expertise in metallurgy.
                She has a rivalry with Dr. Zathras due to a credit dispute in Y53."
)

# Store press release
mcp__qdrant-great-work__qdrant-store(
    information="ACADEMIC BULLETIN #42: Professor Morrison stakes career on volcanic winter theory.
                Confidence: Stake My Career. Team includes Dr. Fieldstone and Dr. Ironquill."
)
```

### 2. Searching Information: `mcp__qdrant-great-work__qdrant-find`

**Purpose**: Search the knowledge base using natural language queries.

**Parameters**:

- `query` (required): Natural language search query

**Returns**: Array of relevant entries with content and metadata

**Examples**:

```python
# Search for game mechanics
mcp__qdrant-great-work__qdrant-find(
    query="How do confidence wagers work?"
)

# Search for scholar relationships
mcp__qdrant-great-work__qdrant-find(
    query="Which scholars have grudges or rivalries?"
)

# Search for specific expeditions
mcp__qdrant-great-work__qdrant-find(
    query="Bronze Age expeditions with spectacular failures"
)
```

## Content Schema and Best Practices

### 1. AI Agent Memory and Context

**What to Store**:

- Implementation decisions and their rationale
- Bug fixes with root causes and solutions
- Test improvements and coverage changes
- Performance optimizations and their impact
- Architectural decisions and design patterns used
- Refactoring work and why it was needed
- Integration points and how they work
- Any gotchas or non-obvious behaviors discovered

**Schema Pattern**:

```plaintext
[DATE] - [AGENT TYPE] - [TASK]: [What was done].
Context: [Why it was needed].
Implementation: [How it was achieved].
Impact: [What changed as a result].
Notes: [Important details for future agents].
```

**Example**:

```plaintext
2025-09-19 - architecture-reviewer - Documentation Review: Updated gap analysis, implementation plan, and requirements evaluation.
Context: Documentation was out of sync with actual implementation.
Implementation: Compared all docs/ files against great_work/ codebase systematically.
Impact: Found 44% fully implemented, 22% partial, identified missing Discord commands.
Notes: Conference, mentor, and symposium_vote commands are missing but have backend support.
```

### 2. Game Mechanics

**What to Store**:

- Confidence wager tables and payoffs
- Expedition resolution rules
- Influence economy mechanics
- Reputation thresholds
- Cooldown timers
- Digest processing rules

**Schema Pattern**:

```plaintext
[MECHANIC NAME]: [Clear description of how it works].
Key values: [specific numbers/thresholds].
Effects: [what happens as a result].
Example: [concrete example if helpful].
```

**Example**:

```plaintext
Reputation Bounds: Player reputation ranges from -50 to +50.
Key thresholds: Recruitment unlocked at -10, Field Expeditions at 0, Great Projects at +10.
Effects: Reputation changes from wager outcomes are clamped within bounds.
Example: A player at +45 rep gaining +15 would cap at +50.
```

### 2. Scholar Profiles

**What to Store**:

- Full name and title
- Expertise and specializations
- Personality traits and catchphrases
- Relationship histories
- Career progression
- Notable achievements or failures

**Schema Pattern**:

```plaintext
[SCHOLAR NAME] ([TITLE]): [Primary expertise].
Personality: [2-3 key traits].
Relationships: [Key allies/rivals].
History: [1-2 major events].
Current status: [Career level, faction alignment].
```

**Example**:

```plaintext
Dr. Sarah Fieldstone (Bronze Age Specialist): Expert in ancient metallurgy and trade routes.
Personality: Meticulous, skeptical of grand theories, values empirical evidence.
Relationships: Rivalry with Dr. Zathras (credit dispute Y53), respects Morrison despite disagreements.
History: Discovered iron deposits during failed volcano expedition, revolutionized dating methods.
Current status: Associate Professor, strong Academic faction alignment.
```

### 3. Press Releases

**What to Store**:

- Full press release text
- Bulletin numbers and timestamps
- Associated scholars and players
- Confidence levels and outcomes
- Public reactions

**Schema Pattern**:

```plaintext
[PRESS TYPE] #[NUMBER] - [DATE]: [HEADLINE].
Details: [Main content].
Participants: [Who's involved].
Stakes: [Confidence level, reputation at risk].
Outcome: [What happened, if resolved].
```

**Example**:

```plaintext
ACADEMIC BULLETIN #127 - Year 54, Day 203: Morrison Stakes Career on Volcanic Winter Theory.
Details: Expedition to Santorini seeks evidence of Bronze Age climate catastrophe.
Participants: Dr. Morrison (lead), Dr. Fieldstone (metallurgy), Dr. Ironquill (chronicles).
Stakes: Stake My Career, -25 reputation if wrong.
Outcome: Pending resolution at next digest.
```

### 4. Expedition Records

**What to Store**:

- Expedition codes and types
- Objectives and theories
- Team composition
- Preparation details
- Outcomes and discoveries
- Sideways discoveries

**Schema Pattern**:

```plaintext
EXPEDITION [CODE] ([TYPE]): [Objective].
Team: [Scholar names and roles].
Preparation: [Depth, modifiers].
Roll: [d100 result + modifiers = final].
Outcome: [Success level, discoveries].
Consequences: [Reputation changes, influence gains, follow-ups].
```

**Example**:

```plaintext
EXPEDITION EXP_054_007 (Field): Investigate Minoan palace for volcanic evidence.
Team: Morrison (lead), Fieldstone (archaeology), Ironquill (translations).
Preparation: Deep, +15 expertise, -5 site friction, +10 total modifier.
Roll: 67 + 10 = 77.
Outcome: Success, found ash layers confirming eruption timeline.
Consequences: Morrison +5 reputation, gained 2 Government influence, Fieldstone discovers metal workshop.
```

### 5. Game State and Events

**What to Store**:

- Timeline progression
- Player status changes
- Scholar defections
- Symposium outcomes
- Digest summaries

**Schema Pattern**:

```plaintext
[EVENT TYPE] - [TIMESTAMP]: [What happened].
Actors: [Who was involved].
Changes: [State changes].
Follow-ups: [Scheduled consequences].
```

## Search Strategies

### Effective Query Patterns

1. **Concept Queries**: "How does [X] work in The Great Work?"
2. **Relationship Queries**: "What is the relationship between [A] and [B]?"
3. **Historical Queries**: "What happened with [event/person] in [timeframe]?"
4. **Mechanical Queries**: "What are the rules for [gameplay element]?"
5. **Status Queries**: "Current status of [scholar/player/expedition]?"
6. **AI Context Queries**: "What work has been done on [feature/bug/system]?"
7. **Implementation Queries**: "How was [X] implemented by previous agents?"

### Multi-Step Research

When answering complex questions, use multiple searches:

```python
# First, understand the mechanic
results1 = qdrant_find("expedition resolution rules and thresholds")

# Then, find examples
results2 = qdrant_find("successful Great Project expeditions")

# Finally, check for special cases
results3 = qdrant_find("spectacular failures with sideways discoveries")
```

## Maintenance Best Practices

### 1. Regular Information Updates

**For AI Agents - Store after completing work**:

- Implementation decisions with rationale
- Bug fixes with solutions and root causes
- Test improvements with coverage metrics
- Performance optimizations with benchmarks
- Architectural changes with design reasoning
- Integration work with API documentation
- Configuration changes with impact analysis

**For Game Events - Store after occurrence**:

- New press releases immediately after generation
- Scholar relationship changes after defections
- Expedition outcomes after resolution
- Player status after reputation changes

### 2. Avoiding Duplicates

Before storing, search for similar content:

```python
# Check if already stored
existing = qdrant_find("Morrison volcanic winter theory expedition")
if not relevant_match(existing):
    qdrant_store(new_information)
```

### 3. Information Completeness

Always include:

- WHO is involved (scholars, players)
- WHAT happened (action, outcome)
- WHEN it occurred (year, digest)
- WHY it matters (consequences, stakes)
- HOW it affects the game (mechanical changes)

### 4. Cross-References

When storing related information, mention connections:

```plaintext
"This expedition follows up on Dr. Fieldstone's Y53 discovery.
Related to the Morrison-Zathras rivalry established in Bulletin #89.
Builds on the volcanic winter theory first proposed in Theory #234."
```

## Common Use Cases

### 1. Answering Player Questions

```python
# Player asks: "What happens if I stake my career and fail?"
results = qdrant_find("stake my career failure consequences reputation")
# Provide comprehensive answer including -25 reputation, cooldowns, examples
```

### 2. Generating Contextual Narratives

```python
# Before writing press about Dr. Fieldstone
context = qdrant_find("Dr. Fieldstone personality history relationships")
# Use retrieved context to maintain character consistency
```

### 3. Tracking Game Patterns

```python
# Identify successful strategies
patterns = qdrant_find("successful expeditions with high confidence")
# Analyze what preparation levels and team compositions work
```

### 4. Maintaining Continuity

```python
# Before introducing new scholar interaction
history = qdrant_find("Dr. Morrison Dr. Ironquill past interactions")
# Ensure new events respect established relationships
```

## Error Handling

### Common Issues and Solutions

1. **Empty Results**
   - Try broader search terms
   - Check for typos in names
   - Search for partial matches

2. **Too Many Results**
   - Add more specific terms
   - Include time ranges
   - Specify the type of information needed

3. **Metadata Errors**
   - Currently metadata parameter doesn't work
   - Store all context in the information field
   - Use descriptive text instead of structured metadata

## Performance Tips

1. **Batch Related Stores**: When storing multiple related items, do them in sequence for better embedding relationships

2. **Search Before Store**: Always search to avoid duplicates and find related content to reference

3. **Use Natural Language**: The embedding model understands context better than keywords alone

4. **Include Examples**: When storing rules, include concrete examples for better retrieval

5. **Regular Summaries**: Periodically store digest summaries that consolidate multiple events

## Integration Checklist

When implementing a new game feature:

- [ ] Store the mechanical rules
- [ ] Store examples of the feature in action
- [ ] Store any new scholar behaviors related to it
- [ ] Store press templates or examples
- [ ] Update existing related entries with cross-references
- [ ] Test searching for the feature from multiple angles
- [ ] Document any special patterns or edge cases

## Summary

The Qdrant integration provides The Great Work with semantic search capabilities essential for maintaining game continuity and narrative richness. By following these patterns and best practices, AI agents can effectively store and retrieve game knowledge, ensuring consistent and contextual responses to player actions.

Remember: Every piece of information stored should tell part of The Great Work's story - who did what, when, why it mattered, and what happened as a result.
