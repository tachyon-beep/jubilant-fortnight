# Agent Guidelines

Welcome! Please follow these instructions when working in this repository:

1. **Documentation formatting**
   - Preserve Markdown heading hierarchy and ordered lists.
   - Wrap text at a reasonable width only if already wrapped; otherwise leave paragraphs as single lines.
   - Do not invent new product requirements unless the user explicitly requests them.

2. **Testing expectations**
   - Run `pytest` for any code changes under `great_work/` or `tests/`.
   - Documentation-only updates do not require automated tests, but call this out in the final report.

3. **Commit hygiene**
   - Keep commits focused and descriptive. One logical change per commit is preferred.
   - Ensure `git status` is clean before finishing.

4. **PR messaging**
   - When summarizing changes, mention the impacted directories explicitly (for example, `docs/` or `great_work/`).

5. **Style**
   - Follow the existing Python formatting (PEP 8) and use `ruff` if linting is needed.

Thank you, and good luck!
