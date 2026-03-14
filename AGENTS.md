# AGENTS.md

Repository-level instructions for coding agents working in `codeman`.

## Start Here

1. Read `docs/project-context.md` before making implementation changes.
2. Use `docs/README.md` as the canonical documentation map and ownership guide.
3. Use `docs/cli-reference.md` for supported CLI syntax and output contracts.
4. Use `docs/architecture/decisions.md` and `docs/architecture/patterns.md` for stable engineering constraints and extension patterns.

## Repo-Specific Rules

- Default communication language for agent-facing text is Ukrainian unless the task clearly needs another language.
- Do not use `.ru` domain sources or Russian-language sources for research.
- Treat current code and tests as the source of truth for implemented behavior.
- Treat `_bmad-output/planning-artifacts/*.md` as planning and rationale artifacts, not as proof that a feature already exists in code.
- Keep the project local-first by default; do not assume MCP, semantic retrieval, hybrid retrieval, or external-provider-backed evaluation are implemented unless the code is present.
- Keep documentation updates in the canonical owner document instead of copying the same rules into multiple files.
- Use `docs/README.md` as the canonical ownership map for repository documentation.

## Conflict Resolution

When documents disagree, prefer:

1. Current code and tests.
2. `docs/cli-reference.md` for exposed CLI behavior.
3. `docs/project-context.md` for agent implementation rules.
4. `docs/architecture/*.md` for stable engineering intent.
5. `_bmad-output/planning-artifacts/*.md` for planned direction and rationale.
