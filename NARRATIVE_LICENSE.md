# Narrative Asset Licensing

_Last updated: 2025-09-30_

The narrative assets bundled with The Great Work (press tone packs, recruitment blurbs, sidecast arcs, epilogues, vignettes, and landmark preparations) are released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license unless otherwise noted. This allows downstream projects to reuse and remix the content for commercial or non-commercial purposes provided credit is given to the original authors.

## Scope

- `great_work/data/sidecast_arcs.yaml`
- `great_work/data/sideways_vignettes.yaml`
- `great_work/data/defection_epilogues.yaml`
- `great_work/data/recruitment_press.yaml`
- `great_work/data/table_talk_press.yaml`
- `great_work/data/landmark_preparations.yaml`
- Example snippets embedded in `docs/WRITING_GUIDE.md`

## Attribution Requirements

When redistributing or adapting these materials, please include:

- Project name: **The Great Work**
- Repository URL: https://github.com/tachyon-beep/jubilant-fortnight
- Attribution statement such as: "Narrative content adapted from *The Great Work* (CC BY 4.0)."

## Contributor Guidelines

- Contributions to narrative YAML files or documentation must be original works you are permitted to license under CC BY 4.0.
- If incorporating third-party text (for example, historical quotations), ensure it is either in the public domain or compatible with CC BY 4.0 and clearly cite the source in a YAML comment.
- Include any content warnings or sensitive-topic notes inline so moderation tooling and human reviewers can respond appropriately.

## Manual Review & Moderation

- All new narrative submissions pass through the Guardian moderation pipeline before publication.
- Use `python -m great_work.tools.validate_narrative --all` to lint structure and `python -m great_work.tools.preview_narrative` to generate review packets for the creative team.
- Document overrides or exceptions (e.g., locale-specific idioms) in `docs/WRITING_GUIDE.md` along with rationale.

## Contact

For questions about licensing or attribution, please open an issue in the repository or contact the maintainers at ops@greatwork.example.
