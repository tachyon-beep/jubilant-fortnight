# Narrative Writing Guide

The Great Work blends templated prose with persona-driven LLM flourishes. Use this guide to
ship consistent, mechanically aware copy across every surface.

## 1. Quick Start Checklist

1. Scan the surface map (Section 2) and open the matching YAML file under `great_work/data/`.
2. Skim the relevant example in Section 4 and the good/bad comparisons in Section 5.
3. Draft copy in YAML, respecting placeholder tables and tone pack cues.
4. Hint at mechanical consequences (Section 6) so players understand what changed.
5. Run local validation (Section 9) before opening a PR.
6. Attach context in the PR (surface, test command, notable placeholders).

## 2. Narrative Surface Map

| Surface | YAML file | MultiPress entry | Typical outputs |
| --- | --- | --- | --- |
| Recruitment follow-ups | `great_work/data/recruitment_press.yaml` | `generate_recruitment_layers` | Gossip quotes, digest summary |
| Table-talk follow-ups | `great_work/data/table_talk_press.yaml` | `generate_table_talk_layers` | Commons gossip, digest notes |
| Mentorship beats | `great_work/data/mentorship_press.yaml` | `generate_mentorship_layers` | Fast quotes, long-form briefs |
| Sidecast arcs | `great_work/data/sidecast_arcs.yaml` | `generate_sidecast_layers` | Gossip + spotlight brief chain |
| Defection epilogues | `great_work/data/defection_epilogues.yaml` | `generate_defection_epilogue_layers` | Epilogue brief, faction memo |
| Sideways vignettes | `great_work/data/sideways_vignettes.yaml` | `queue_order:followup:sideways_vignette` | Gazette vignette + gossip |
| Landmark preparation briefs | `great_work/data/landmark_preparations.yaml` | `generate_expedition_layers` (landmark layer) | Landmark discovery flavour + prep brief |
| Tone packs | `great_work/data/press_tone_packs.yaml` | `press_tone.get_tone_seed` | Headline/blurbs/callouts |
| Seasonal commitments | Procedural (service) | `seasonal_commitment_update` / `_complete` | Cost + loyalty status briefs |
| Faction investments | Procedural (service) | `faction_investment` | Infrastructure upgrades, faction goodwill tone |
| Archive endowments | Procedural (service) | `archive_endowment` | Donation acknowledgement, archive mission focus |
| Faction projects | Procedural (service) | `faction_project_update` / `_complete` | Progress bulletins |

## 3. Voice & Tone Foundations

- Public record: everything is diegetic press read by rivals, sponsors, and scholars.
- Keep bodies to 2–5 sentences and ≤320 characters. Gossip quotes are single sentences.
- PG-13 language only. No real-world slurs, gore, or explicit politics.
- Agency first: narrate consequences, not forced player actions.
- Placeholders are literal—never invent `{foo}` without coordinating with engineers.

### Scholar Archetype Voice Cheat Sheet

| Archetype | Voice cues | Sample verbs |
| --- | --- | --- |
| Empiricist | data-forward, cautious optimism | "corroborates", "notes", "catalogues" |
| Visionary | big metaphors, dramatic stakes | "proclaims", "sketches", "prophecies" |
| Mystic | sacred resonance, ritual language | "intones", "consecrates", "augurs" |
| Postdoc | eager, informal, hungry for credit | "grins", "jitters", "live-blogs" |

Use one or two archetype cues per quote; combine with faction lean if known.

## 4. YAML Reference by Surface

### 4.1 Recruitment Follow-ups (`recruitment_press.yaml`)

```yaml	recruitment:
  success:
    reactions:
      - "{commentator} applauds {player}'s odds at {chance_pct}."
    digest:
      headline: "Recruitment Win — {scholar}"
      body: |
        {scholar} accepts {player}'s offer. Voices: {voices}.
```

- `reactions` feeds fast gossip layers; 3–4 entries are plenty.
- `digest.body` should reference `{voices}` to echo the gathered reactions.

### 4.2 Table-talk Follow-ups (`table_talk_press.yaml`)

```yaml	table_talk:
  failure:
    reactions:
      - "Commons mutter that {player} misread the room."
    digest:
      body: |
        Table-talk fizzles. {voices}
```

- Keep Commons gossip light and collaborative; table-talk is opt-in chatter.

### 4.3 Mentorship Beats (`mentorship_press.yaml`)

```yaml	phases:
  progression:
    fast:
      - "{scholar} nails the {track_descriptor} drill; {mentor} files glowing notes."
    long:
      - "{mentor} documents {scholar}'s breakthroughs across the {track_descriptor} labs."
    headline: "Mentorship Briefing — {scholar}"
```

- `fast` entries become gossip quotes. `long` entries map to delayed briefs.
- `{track_descriptor}` comes from YAML; keep it lore-friendly ("Applied Myth Cartography").

### 4.4 Sidecast Arcs (`sidecast_arcs.yaml`)

```yaml	sidecasts:
  local_junior:
    phases:
      debut:
        gossip:
          - "{scholar} follows {sponsor} with armfuls of field notes."
        briefs:
          - headline: "Hallway Buzz — {scholar} Joins"
            body: |
              {scholar} explains how {sponsor}'s crew pulled them into the dig.
        next:
          phase: integration
          delay_hours: 24
```

- Provide three phases (`debut`, `integration`, `spotlight`) when possible.
- Each phase should push toward a decision (mentorship offer, faction courtship).

### 4.5 Defection Epilogues (`defection_epilogues.yaml`)

```yaml	epilogues:
  reconciliation:
    primary:
      headline: "Reconciliation Wire — {scholar}"
      body: |
        {scholar} honours promises to {former_faction}."
    faction_brief:
      headline: "Faction Briefing: {former_faction}"
      body: |
        Logistics outline reparations and renewed access rights.
    gossip:
      - "{scholar} sends thank-you notes to {former_faction} staff."
```

- `primary` is the public dispatch; `faction_brief` is an internal memo tone.
- Use `gossip` to hint at rival sentiments or remaining grudges.
- Negotiation press now appends a **Loyalty snapshot** line summarising feelings toward the rival and
  current patron; keep epilogues consistent with those loyalty shifts.

### 4.6 Sideways Vignettes (`sideways_vignettes.yaml`)

```yaml	vignettes:
  field:
    deep:
      - id: "field_hidden_archive"
        headline: "Hidden Archive Unearthed"
        body: |
          An archive sealed with sigils reveals rival guild correspondences.
        gossip:
          - "Archivists debate who gets stewardship rights."
        tags: ["archives", "field"]
```

- Include at least three entries per depth (`shallow`, `standard`, `deep`).
- Tags fuel Gazette highlights and telemetry dashboards—make them actionable.

### 4.7 Landmark Preparations (`landmark_preparations.yaml`)

```yaml
landmark_preparations:
  think_tank:
    deep:
      discoveries:
        - "Simulators stage night-long runs so {objective}'s landmark proof can survive every hostile interrogation."
      briefs:
        - headline: "Deep Prep Ledger — Expedition {code}"
          body: |
            After deep preparation, {player}'s analysts tout {strengths_text}. They document {frictions_text} as final
            debate traps while {team_summary} script the landmark reveal.
```

- `discoveries` feed the fallback copy for landmark successes when the failure tables do not provide
  bespoke text. Keep these celebratory but grounded in the expedition type and prep depth.
- `briefs` populate the new `landmark_preparation` press layer. Required placeholders: `{player}`,
  `{objective}`, `{code}`, `{prep_depth_title}`, `{prep_depth_title_lower}`, `{strengths_text}`,
  `{frictions_text}`, `{team_summary}`. Use `{prep_depth_title_lower}` instead of calling `.lower()`
  in templates.
- `strengths_text` and `frictions_text` arrive as pre-joined fragments (e.g., `Think tank modelling +8`).
  Focus on why those strengths or risks matter for the reveal rather than repeating raw numbers.
- Preview with `python -m great_work.tools.preview_narrative landmark-prep` and keep lines ≤100 characters.

### 4.8 Seasonal Commitments (programmatic)

Generated directly from the service layer. Keep focus on upkeep cost, relationship modifiers, and whether debt carried forward.

```
Seasonal Commitment Update — Mentor Hal
Mentor Hal maintains a seasonal pledge with Academia. Cost: 3. Relationship modifier +20%. Outstanding debt: 0.
```

### 4.9 Faction Projects (programmatic)

Progress updates summarise aggregate progress and spotlight the top contributors.

```
Faction Project Update — Sky Array
Sky Array advances under Academia stewardship. Progress: 1.2/3.0 (40.0%). Top contributors: Mentor Hal (+0.6), Team Lyra (+0.2).
```

## 5. Good vs Bad Examples

### 5.1 Gossip Quote

- **Good:** "Dr Lyra Anselm murmurs that the archive locks 'clicked like they wanted to be opened'."
  - Why: persona cue (murmurs), tangible detail (locks), implies wonder.
- **Bad:** "Lyra says the archive is cool." — flat tone, no flavour, no stakes.

### 5.2 Long-form Brief

- **Good:** "After twelve hours in the vault, {scholar} cross-maps sigils to the {expedition_code}
  codex, unlocking disputed provenance." — references mechanics and future friction.
- **Bad:** "{scholar} did a great job and everyone claps." — vague, no hook.

### 5.3 Mechanical Hint

- **Good:** "Industry envoys demand first refusal rights within two dig cycles." — foreshadows
  influence costs.
- **Bad:** "Everyone is happy forever." — no consequence, no follow-up signal.

## 6. Hinting at Mechanical Consequences

- Flag resource changes: "costs {faction} three influence" or "boosts recruitment odds by a
  whisper".
- Signal follow-ups: "Expect a symposium vote within the week" or "Mentorship offer pending".
- Reference debts: "Fails to pay upkeep, triggering reprisal level {reprisal_level}."
- Use tags and metadata (`tags: ["debt", "symposium"]`) for dashboards.
- Seasonal commitments: highlight how loyalty reduced or increased the bill for the week.
- Faction projects: call out high-performing contributors and how their loyalty sped progress.

## 7. Tone Packs

Tone packs rotate headlines, blurbs, and callouts per aesthetic.

```yaml	settings:
  high_fantasy:
    digest_highlight:
      headline:
        - "Moonlit Gazette — {count} oaths stir"
      blurb_template:
        - "{headline} due in {relative_time}; heralds polish trumpets."
      callout:
        - "Scribes, ready vellum." 
```

- Add two variants per slot to avoid repetition.
- Keep callouts actionable ("Notify moderators" beats "Yay!").
- When introducing a new surface, add matching tone keys (e.g., `sidecast_followup`).

## 8. LLM Integration & Persona Metadata

- `GameService._enhance_press_release` wraps every release with persona metadata and optional
  tone seeds. Supply concrete nouns so the LLM can riff ("fault line archive", not "place").
- `MultiPressGenerator` passes `tone_seed` derived from the active tone pack; keep headlines
  compatible with both base and enhanced text.
- Avoid sarcasm or ambiguous phrasing—the LLM expands on your intent.
- For scholar quotes, provide a clean grammatical sentence; the LLM adjusts cadence but does not
  fix typos.

## 9. Testing & Validation

Run tests from the project root with the virtual environment active:

- Static validation: `python -m great_work.tools.validate_narrative --all`
- Narrative preview: `python -m great_work.tools.preview_narrative` (or pass a specific surface, e.g., `-- recruitment`)
- Layered narrative sanity: `./.venv/bin/python -m pytest tests/test_multi_press.py -q`
- Sidecast + vignette flows: `./.venv/bin/python -m pytest tests/test_service_edge_cases.py -k "sidecast or vignette" -q`
- Mentorship lifecycle: `./.venv/bin/python -m pytest tests/test_mentorship.py -q`
- Seasonal commitments & faction projects: `./.venv/bin/python -m pytest tests/test_commitments_projects.py -q`

YAML tip: run `yamllint great_work/data/<file>.yaml` (install via `pip install yamllint`) before
committing large batches.

## 10. Troubleshooting

- **PlaceholderError** in tests: check braces—use `{scholar}` not `{Scholar}`.
- **LLM output too spicy:** tighten verbs, remove sarcasm, add neutral phrasing like "observes".
- **Digest highlight missing entry:** ensure vignette/tag metadata includes `tags` and
  `headline` fields.
- **Follow-up never fires:** confirm `next.phase` exists and `delay_hours` is numeric.
- **Callout repeats:** provide at least two callouts per tone key to allow rotation.

Document updates should always reference this guide when reviewing narrative PRs.
