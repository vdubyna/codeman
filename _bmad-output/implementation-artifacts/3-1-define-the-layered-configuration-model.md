# Story 3.1: Define the Layered Configuration Model

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a maintainer,
I want codeman to resolve configuration from defaults, local config, CLI overrides, and environment secrets,
so that retrieval experiments can be run consistently without hard-coded settings.

## Acceptance Criteria

1. Given project defaults, optional local config, CLI flags, and environment variables, when codeman resolves runtime configuration, then it applies a deterministic precedence order across those layers and produces a validated runtime configuration object.
2. Given an invalid or conflicting configuration, when configuration resolution runs, then codeman fails with a clear validation error and stable non-zero exit behavior and does not start the indexing or query workflow with partial settings.

## Tasks / Subtasks

- [x] Establish the layered configuration resolution foundation and path helpers. (AC: 1, 2)
  - [x] Add `src/codeman/config/defaults.py` to load project defaults from `[tool.codeman]` in `pyproject.toml`, with explicit in-code fallbacks when the table is absent.
  - [x] Add `src/codeman/config/paths.py` to resolve the canonical optional user-local config path and keep it separate from workspace runtime paths under `.codeman/`.
  - [x] Add `src/codeman/config/loader.py` to merge source layers deterministically and produce one validated `AppConfig`, plus a small override DTO/dataclass for CLI-supplied values.
  - [x] Keep missing local config non-fatal, but fail on malformed TOML or invalid values before any indexing/query use case starts.

- [x] Refactor configuration models into source-agnostic validated DTOs. (AC: 1, 2)
  - [x] Update `RuntimeConfig`, `IndexingConfig`, `SemanticIndexingConfig`, and `AppConfig` so they validate resolved data instead of reading directly from `os.environ` in field default factories.
  - [x] Preserve current field names and nested structure used by `bootstrap.py`, fingerprint helpers, and indexing/query use cases.
  - [x] Keep `ConfigDict(extra="forbid")` and existing helper methods such as `resolved_vector_dimension()`.

- [x] Wire the loader into bootstrap and fail fast at CLI startup. (AC: 1, 2)
  - [x] Update `src/codeman/bootstrap.py` to resolve `AppConfig` once through the loader and to accept narrowly-scoped CLI overrides without mutating validated config after construction.
  - [x] Introduce typed configuration-resolution errors and stable error code / exit-code mapping for invalid or conflicting config.
  - [x] Ensure existing commands abort before running use cases when resolution fails, and keep JSON `stdout` clean.

- [x] Add a minimal inspection surface for the effective configuration. (AC: 1)
  - [x] Implement `uv run codeman config show` (or equivalently narrow inspect command) in `src/codeman/cli/config.py`.
  - [x] Support a focused set of CLI override flags appropriate for the foundation layer, such as config-path/runtime-path style overrides; do not attempt to implement profile management or every future retrieval knob in this story.
  - [x] Return safe text/JSON output that shows effective resolved values without printing secret contents.

- [x] Document the supported precedence and add mirrored automated coverage. (AC: 1, 2)
  - [x] Update `docs/cli-reference.md` with the config inspection command, source precedence, and failure semantics.
  - [x] Add unit coverage for precedence order, missing optional local config, malformed TOML, and model validation failures.
  - [x] Add CLI unit tests for `config show` text/json output and stable failure envelopes.
  - [x] Add e2e coverage proving the resolved config drives real command behavior and that invalid config fails before the underlying workflow starts.

## Dev Notes

### Epic Context

- Epic 3 is the configuration and provenance foundation for later profiles, run attribution, and cache identity.
- Story 3.1 should establish one authoritative configuration-resolution path that later stories 3.2-3.6 reuse instead of each feature reading env vars ad hoc.
- Do not implement profile persistence, configuration provenance storage, run manifests, or cache-key changes here; those belong to Stories 3.3-3.6.

### Current Repo State

- `src/codeman/config/models.py` still labels the top-level config as a placeholder and reads runtime defaults directly from env inside model field default factories.
- `src/codeman/config/indexing.py` and `src/codeman/config/semantic_indexing.py` currently read env vars directly in their Pydantic models. This bypasses explicit layer ordering and makes source provenance opaque.
- `src/codeman/bootstrap.py` constructs `AppConfig()` directly and mutates `config.runtime.workspace_root` only when `bootstrap(workspace_root=...)` is called.
- `src/codeman/cli/config.py` is a placeholder group with no subcommands.
- `pyproject.toml` currently has package metadata and tool config for pytest/ruff, but no `[tool.codeman]` defaults table yet.
- The planned architecture references `src/codeman/config/defaults.py`, `loader.py`, `paths.py`, and `src/codeman/infrastructure/config/`, but those modules do not exist in the implemented code yet.
- `.env.example` is referenced in the planning architecture, but it is not present in the current repository. Do not assume dotenv support already exists.

### Cross-Epic Baseline

- Stories 2.5-2.7 established the current semantic/hybrid/query baseline and already depend on `container.config.semantic_indexing` and `container.config.indexing`.
- Many existing tests and e2e workflows rely on env vars such as `CODEMAN_WORKSPACE_ROOT`, `CODEMAN_SEMANTIC_PROVIDER_ID`, `CODEMAN_SEMANTIC_LOCAL_MODEL_PATH`, and `CODEMAN_SEMANTIC_VECTOR_DIMENSION`. Story 3.1 must preserve those behaviors while routing them through the new authoritative loader.
- Reindexing already fingerprints `IndexingConfig`; this story must not accidentally change existing fingerprint inputs or silently invalidate current deterministic behavior.

### Technical Guardrails

- Keep the implementation CLI-first and local-first. Do not introduce HTTP, MCP runtime, provider auto-enablement, benchmark config profiles, or external secret managers in this story. [Source: docs/architecture/decisions.md; docs/project-context.md]
- Treat `src/codeman/config/` as the source of settings models and resolution logic. If helper loaders are needed, prefer explicit modules there and small adapters under `src/codeman/infrastructure/config/` only when they represent IO boundaries, not business rules. [Source: _bmad-output/planning-artifacts/architecture.md - Project Structure & Boundaries]
- Keep CLI handlers thin. Configuration resolution should happen in one shared path near bootstrap/startup, not be reimplemented separately in each command module. [Source: docs/architecture/patterns.md; docs/project-context.md]
- Preserve stable JSON envelope behavior on `stdout` and keep operator diagnostics/errors on `stderr`. Invalid configuration must fail before running indexing/query logic with partial settings. [Source: docs/project-context.md; docs/cli-reference.md]
- Keep configuration models strict with `ConfigDict(extra="forbid")`. Use typed `@dataclass(slots=True)` helpers for small override or source-resolution structures if helpful, matching repo style. [Source: docs/project-context.md; https://docs.python.org/3/library/dataclasses.html]
- Do not treat planned files as implemented behavior. Add only the minimum new modules actually required for this foundation story. [Source: AGENTS.md; docs/project-context.md]
- Do not silently load repository `.env` or other ambient files as an undocumented magic layer. If a local-config source is introduced, document its path, precedence, and failure behavior explicitly.
- Do not change the semantic or indexing fingerprint payload shapes in this story unless a test-backed compatibility reason requires it. Story 3.1 is about config resolution, not new provenance fields or cache identities.
- Keep secrets out of committed files, docs examples, stdout, and benchmark artifacts. If the effective config includes secret-bearing fields later, redact or omit them in human and JSON inspection output. [Source: _bmad-output/planning-artifacts/prd.md - Security & Data Handling]

### Implementation Notes

- Prefer `[tool.codeman]` in `pyproject.toml` as the project-default source. This aligns with the architecture's "project defaults in `pyproject.toml`" rule and avoids introducing a second committed defaults file.
- Introduce one documented user-local config path helper and treat the file as optional. Inference: a deterministic home-directory TOML file is a better fit for "user-local application config" than mixing committed project defaults with runtime state.
- Keep environment variables as the highest-precedence runtime layer for secrets and final overrides, preserving the current `CODEMAN_*` contract already used by tests and commands.
- A small explicit loader built on stdlib `tomllib` is likely the lowest-risk foundation because the repo does not currently depend on `pydantic-settings`. If you choose to add `pydantic-settings`, do it deliberately, justify the extra dependency, and keep the source order explicit and well tested. [Inference from `pyproject.toml` plus Pydantic settings docs]
- Prefer a read-only resolution flow: raw sources -> merged dict/DTO -> validated `AppConfig`. Avoid constructing partial Pydantic models and mutating fields later, because that weakens provenance and makes validation timing ambiguous.
- Bootstrap currently has a special-case `workspace_root` parameter. Preserve the testability benefit, but route it through the same override mechanism the loader uses so the container sees one consistent effective config.
- The first CLI surface for this story should stay narrow. A `config show` or `config inspect` command is enough to make layered resolution observable; named profiles, run provenance, and config reuse belong to later Epic 3 stories.
- If the loader introduces a config-path override, keep it additive and explicit. Missing optional file should be harmless; malformed file or invalid values should raise one typed configuration error that maps cleanly to a stable exit code.

### File Structure Requirements

- Existing files to extend:
  - `src/codeman/config/models.py`
  - `src/codeman/config/indexing.py`
  - `src/codeman/config/semantic_indexing.py`
  - `src/codeman/bootstrap.py`
  - `src/codeman/cli/config.py`
  - `src/codeman/contracts/errors.py`
  - `docs/cli-reference.md`
- Likely new files for this story:
  - `src/codeman/config/defaults.py`
  - `src/codeman/config/loader.py`
  - `src/codeman/config/paths.py`
  - optionally `src/codeman/infrastructure/config/__init__.py`
  - optionally `src/codeman/infrastructure/config/file_config_loader.py`
- Likely new tests:
  - `tests/unit/config/test_loader.py`
  - `tests/unit/cli/test_config.py`
  - `tests/e2e/test_config_show.py`
  - optionally an integration config test if file-loading behavior grows beyond simple unit seams
- Keep runtime data and any generated artifacts under `.codeman/`. Do not introduce committed config state under `src/` or write runtime config copies into indexed repositories. [Source: docs/project-context.md]

### Testing Requirements

- Add unit tests for deterministic source precedence across project defaults, optional local config, CLI overrides, and environment variables.
- Add unit tests proving invalid TOML and invalid field values surface one stable typed configuration error before workflows run.
- Add regression tests proving current env-based behavior for `CODEMAN_WORKSPACE_ROOT`, `CODEMAN_RUNTIME_ROOT_DIR`, `CODEMAN_METADATA_DATABASE_NAME`, and the existing semantic `CODEMAN_SEMANTIC_*` variables still works through the new loader.
- Add CLI tests for the config inspection command in text and JSON modes, including clean `stdout` / `stderr` separation.
- Add at least one e2e failure-path test showing an invalid resolved config prevents a real command from entering its workflow.
- Keep using `CliRunner` for CLI unit tests and temporary workspaces / subprocess-based `uv run codeman ...` for e2e flows, matching current repo patterns. [Source: docs/project-context.md; existing tests]

### Git Intelligence Summary

- Recent completed stories follow an additive pattern: extend contracts/use cases or config modules, wire them through `bootstrap.py`, add a focused CLI surface, update `docs/cli-reference.md`, and mirror the behavior with unit/integration/e2e coverage.
- Commit `5c8304a` shows the current preferred implementation shape for new workflow surfaces: one new application module, thin CLI wiring, shared helpers in `cli/common.py`, and tight contract additions instead of broad rewrites.
- Commit `d8d9d5c` matters because it reinforced the pattern of extracting the smallest reusable seam rather than duplicating logic. Story 3.1 should likewise centralize config resolution once instead of repeating merges per command.
- Commit `5966a34` matters because semantic flows already rely on stable config-derived fingerprints and failure contracts. Story 3.1 must preserve those semantics while changing how config is loaded.

### Latest Technical Information

- Python's standard-library `tomllib` parses TOML 1.0, reads files via `tomllib.load(...)`, and raises `TOMLDecodeError` on invalid documents. Inference: it is a strong fit for reading `pyproject.toml` and an optional local TOML config without adding a writer or another parsing dependency. [Source: https://docs.python.org/3/library/tomllib.html]
- Current Pydantic settings docs show support for `pyproject.toml` as a settings source and explicit source-order customization. Inference: even if the repo stays on plain Pydantic models for now, the design should keep source ordering explicit and pluggable rather than hard-coding env reads in model defaults. [Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/]
- Current Typer docs continue to support `envvar=` on CLI arguments/options. Inference: if this story exposes config-path or narrow override flags, help text can surface their env-backed equivalents without custom parsing logic. [Source: https://typer.tiangolo.com/reference/parameters/ ; https://typer.tiangolo.com/tutorial/arguments/envvar/]
- Python dataclasses continue to support `slots=True`. Inference: small override/source descriptor helpers should continue to use `@dataclass(slots=True)` to match existing repo patterns and keep the objects lightweight. [Source: https://docs.python.org/3/library/dataclasses.html]

### Project Context Reference

- `docs/project-context.md` is the canonical agent-facing implementation guide. It requires strict Pydantic boundary models, thin CLI handlers, deterministic behavior, runtime artifacts under `.codeman/`, and test coverage aligned to touched behavior.
- `docs/architecture/decisions.md` and `docs/architecture/patterns.md` define the stable CLI-first layering that this story must preserve: `cli -> application -> ports -> infrastructure -> contracts/config/runtime`.
- No separate UX artifact exists for this project. For Story 3.1, the UX requirement is a clear configuration-resolution experience through deterministic behavior, safe diagnostics, and stable text/JSON CLI output.

### Project Structure Notes

- The planning architecture shows a richer future config structure than the implemented repo currently has. Story 3.1 should close only the most immediate gap: one authoritative config resolution path plus a narrow inspection surface.
- `src/codeman/config/` is the right home for settings models and resolution logic today. Introducing parallel config resolution inside CLI modules, application use cases, or runtime helpers would create the exact architectural drift this epic is supposed to prevent.
- The config foundation must remain compatible with future stories for independent embedding settings, reusable profiles, configuration provenance, and config-aware cache keys.

### References

- [Source: docs/project-context.md]
- [Source: docs/README.md]
- [Source: docs/cli-reference.md]
- [Source: docs/architecture/decisions.md]
- [Source: docs/architecture/patterns.md]
- [Source: _bmad-output/planning-artifacts/epics.md - Epic 3; Story 3.1; Story 3.2; Story 3.4; Story 3.5; Story 3.6]
- [Source: _bmad-output/planning-artifacts/architecture.md - Core Architectural Decisions; Environment Configuration; Structure Patterns; Project Structure & Boundaries; Requirements to Structure Mapping]
- [Source: _bmad-output/planning-artifacts/prd.md - Journey 4; Integration Requirements; Functional Requirements FR13-FR18; NFR5-NFR10; NFR18-NFR23; MVP Acceptance Criteria]
- [Source: pyproject.toml]
- [Source: src/codeman/config/models.py]
- [Source: src/codeman/config/indexing.py]
- [Source: src/codeman/config/semantic_indexing.py]
- [Source: src/codeman/bootstrap.py]
- [Source: src/codeman/cli/config.py]
- [Source: src/codeman/application/indexing/build_embeddings.py]
- [Source: src/codeman/application/indexing/build_semantic_index.py]
- [Source: src/codeman/application/query/run_semantic_query.py]
- [Source: src/codeman/contracts/errors.py]
- [Source: tests/unit/config/test_semantic_indexing.py]
- [Source: tests/unit/cli/test_app.py]
- [Source: tests/e2e/test_index_build_semantic.py]
- [Source: git log --oneline -5]
- [Source: git show --stat --summary 5c8304a]
- [Source: git show --stat --summary d8d9d5c]
- [Source: git show --stat --summary 5966a34]
- [Source: https://docs.python.org/3/library/tomllib.html]
- [Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/]
- [Source: https://typer.tiangolo.com/reference/parameters/]
- [Source: https://typer.tiangolo.com/tutorial/arguments/envvar/]
- [Source: https://docs.python.org/3/library/dataclasses.html]

## Story Completion Status

- Status set to `ready-for-dev`.
- Completion note: `Ultimate context engine analysis completed - comprehensive developer guide created.`
- Recorded assumptions:
  - Project defaults should be read from a new `[tool.codeman]` section in `pyproject.toml`.
  - The optional user-local config should live behind one explicit path helper and be documented as an optional TOML file rather than an implicit magic source.
  - This foundation story should add a narrow `config show` or inspection surface, not full profile management or run-provenance persistence.
  - Environment variables remain the highest-precedence runtime layer for secrets and final overrides, preserving existing `CODEMAN_*` behavior already used by the current test suite.

## Dev Agent Record

### Agent Model Used

Codex GPT-5

### Debug Log References

- 2026-03-14: Story context generated via the `bmad-create-story` workflow for backlog story `3-1-define-the-layered-configuration-model`.
- 2026-03-14: Implemented layered configuration resolution with `src/codeman/config/defaults.py`, `paths.py`, and `loader.py`, then wired loader-backed bootstrap failure handling into CLI startup.
- 2026-03-14: Added `config show`, CLI override plumbing, precedence/unit/e2e coverage, and validated the full repo with `ruff check src tests` plus `pytest -q` (`207 passed`).
- 2026-03-14: Fixed code-review findings for malformed project defaults and missing explicit `CODEMAN_CONFIG_PATH`, then re-ran `ruff check src tests` and `pytest -q` (`210 passed`).

### Completion Notes List

- Created a ready-for-dev story that turns the placeholder config layer into an explicit, testable resolution system with deterministic precedence and early failure behavior.
- Scoped the story to a foundation layer plus a narrow inspection command so later Epic 3 stories can build on one authoritative config path.
- Preserved current local-first and env-driven behavior as a non-negotiable regression guardrail.
- Implemented project defaults from `[tool.codeman]`, canonical user-local config path resolution, CLI/runtime overrides, and environment-final precedence through one loader-backed `AppConfig`.
- Refactored runtime/indexing/semantic config models to validate resolved data without direct environment reads, including early semantic vector-dimension validation.
- Added fail-fast configuration error handling for all commands, a new `config show` inspection surface, updated CLI reference docs, and mirrored coverage across unit, CLI, and e2e tests.
- Quality gates passed on 2026-03-14: `uv run --group dev ruff check src tests` and `uv run --group dev pytest -q` (`207 passed`).
- Addressed the review follow-up gaps by making malformed project defaults map to `configuration_invalid` and treating `CODEMAN_CONFIG_PATH` as an explicit fail-fast override.
- Final close-out validation passed on 2026-03-14: `uv run --group dev ruff check src tests` and `uv run --group dev pytest -q` (`210 passed`); story is ready to move from `review` to `done`.

### File List

- _bmad-output/implementation-artifacts/3-1-define-the-layered-configuration-model.md
- _bmad-output/implementation-artifacts/sprint-status.yaml
- docs/cli-reference.md
- pyproject.toml
- src/codeman/bootstrap.py
- src/codeman/cli/app.py
- src/codeman/cli/config.py
- src/codeman/config/defaults.py
- src/codeman/config/indexing.py
- src/codeman/config/loader.py
- src/codeman/config/models.py
- src/codeman/config/paths.py
- src/codeman/config/semantic_indexing.py
- src/codeman/contracts/errors.py
- tests/e2e/test_config_show.py
- tests/e2e/test_index_build_semantic.py
- tests/unit/cli/test_app.py
- tests/unit/cli/test_config.py
- tests/unit/config/test_loader.py
- tests/unit/config/test_models.py
- tests/unit/config/test_semantic_indexing.py

## Change Log

- 2026-03-14: Created comprehensive ready-for-dev story context for layered configuration resolution.
- 2026-03-14: Implemented layered configuration loading, fail-fast CLI startup validation, `config show`, documentation updates, and mirrored automated coverage; story moved to `review`.
- 2026-03-14: Fixed review findings around explicit env config-path handling and malformed project defaults, refreshed docs/tests, and closed the story as `done`.
