# Documentation Map

This folder contains the canonical human-facing and agent-facing documentation for `codeman`.

## Documentation Zones

- `../README.md`
  Human entrypoint: quick start, repo overview, and top-level pointers.
- `../AGENTS.md`
  Short repo instructions for coding agents and the documentation precedence map.
- `project-context.md`
  Canonical implementation rules for AI agents. This file is optimized for agent consumption and should stay lean and directive.
- `cli-reference.md`
  Supported CLI commands, flags, and output contracts. This file owns user-facing command syntax and JSON/text output expectations.
- `benchmarks.md`
  Benchmark and evaluation policy: dataset rules, metadata requirements, reproducibility, privacy boundaries, and provider transparency.
- `architecture/decisions.md`
  Stable architectural decisions and invariants that contributors should preserve.
- `architecture/patterns.md`
  Current code organization, layering, and extension patterns for implementation work.
- `../_bmad-output/planning-artifacts/*.md`
  Planning artifacts and rationale from BMAD workflows. Use these for intended direction, not as the first source for current operational behavior.

## Update Rules

- If user-facing CLI behavior changes, update `cli-reference.md` and only update `README.md` if the quick-start path changes.
- If agent implementation rules change, update `project-context.md` and `AGENTS.md` only when the repo-level workflow guidance also changes.
- If a stable architectural invariant changes, update `architecture/decisions.md` and, if extension guidance changed, `architecture/patterns.md`.
- If benchmark or evaluation semantics change, update `benchmarks.md` and add agent-facing constraints to `project-context.md` only when agents must actively follow them during implementation.
- When two docs overlap, keep the shorter one and link to the canonical owner instead of copying the same content twice.

## Practical Precedence

1. Code and tests define current implemented behavior.
2. `cli-reference.md` defines the supported CLI contract.
3. `project-context.md` defines implementation rules for AI agents.
4. `architecture/*.md` defines stable engineering intent and extension boundaries.
5. `_bmad-output/planning-artifacts/*.md` defines product and architecture direction beyond what is currently implemented.
