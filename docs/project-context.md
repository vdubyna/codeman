---
project_name: 'codeman'
user_name: 'Vdubyna'
date: '2026-03-14T13:04:22+0200'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
existing_patterns_found: 8
status: 'complete'
rule_count: 90
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss. This is the canonical agent-facing implementation context for the repository._

---

## Technology Stack & Versions

- Python `>=3.13,<3.14`; agents must keep syntax, typing, and dependency choices compatible with Python 3.13.
- Project packaging and command execution use `uv` with `uv_build`; do not introduce another package manager as the primary developer workflow.
- The CLI entrypoint is `codeman = "codeman.cli.app:main"` and the command surface is built with `typer>=0.20.0,<0.21.0` under `src/codeman/cli/`.
- Configuration and contract DTOs use `pydantic>=2.12.5,<3.0.0`; the default strictness pattern is `ConfigDict(extra="forbid")`.
- Metadata persistence uses `sqlalchemy>=2.0.44,<2.1.0` with `alembic>=1.17.2,<1.18.0`; agents should prefer explicit persistence and migrations over ORM-heavy domain modeling.
- Linting and import ordering use `ruff>=0.11.0,<0.12.0` with line length `100`, import sorting enabled through Ruff, and target version `py313`.
- Testing uses `pytest>=8.0,<9.0`; the configured test root is `tests/`, with both `tests/unit/` and `tests/e2e/` present in the current codebase.
- Runtime state is workspace-local under `.codeman/` and includes `artifacts/`, `indexes/`, `cache/`, `logs/`, `tmp/`, and `metadata.sqlite3`; agents should keep generated runtime data inside this boundary.
- Runtime path defaults can be overridden only through `CODEMAN_WORKSPACE_ROOT`, `CODEMAN_RUNTIME_ROOT_DIR`, and `CODEMAN_METADATA_DATABASE_NAME`.
- Indexed repository languages for the MVP are PHP, JavaScript, HTML, and Twig.
- The current implemented retrieval baseline is local-first with SQLite-backed metadata storage and SQLite FTS5 lexical indexing.
- JSON-capable CLI response contracts already exist through shared envelopes in `codeman.contracts.*`; new command outputs should stay compatible with that direction.
- MCP is planned as a later interface and must reuse the same retrieval core; agents must not treat MCP as a required current implementation surface unless the relevant code is added.
- OpenAI-assisted evaluation workflows are part of the documented product direction, but they remain optional and must not be treated as mandatory or already fully implemented unless the code and configuration are present.

## Critical Implementation Rules

### Language-Specific Rules

- Use `from __future__ import annotations` in Python modules to match the existing codebase style.
- Keep application services and bootstrap containers as typed `@dataclass(slots=True)` classes when they hold injected dependencies or use-case state.
- Use Pydantic models for config, request/response DTOs, and contract envelopes; default to `ConfigDict(extra="forbid")` unless a boundary explicitly needs looser input.
- Prefer `Literal`, constrained `Field(...)`, and explicit model fields to make CLI and persistence boundaries deterministic.
- Use `pathlib.Path` for filesystem paths throughout the codebase; do not pass raw path strings through core contracts when `Path` is the real type.
- Keep imports absolute from `codeman.*`; avoid relative imports across application, contracts, infrastructure, and CLI layers.
- Put orchestration and user interaction in `src/codeman/cli/*.py`; keep business logic in application use cases and adapter logic in infrastructure modules.
- Translate domain failures into typed exception classes with stable `error_code` and `exit_code`; do not bury operational failures behind generic `Exception` or ad hoc string matching.
- Keep CLI commands thin: validate input, resolve the container, call a use case, and render either text output or JSON envelopes.
- Use `SuccessEnvelope` and `FailureEnvelope` for JSON-capable command responses instead of inventing per-command JSON shapes.
- Keep runtime provisioning explicit: use the existing runtime path helpers instead of creating ad hoc directories or side effects in unrelated modules.
- Preserve deterministic behavior for indexing and evaluation metadata by preferring explicit inputs, stable ordering, and version/fingerprint helpers over implicit defaults.

### Framework-Specific Rules

- Treat Typer as the only required CLI framework for MVP command surfaces; new user-facing operations should be added as subcommands under the existing grouped apps in `src/codeman/cli/`.
- Keep each command group as its own `typer.Typer(...)` module with `no_args_is_help=True` and a lightweight `@app.callback()` docstring-only function.
- Build the root CLI in `codeman.cli.app:create_app()` and attach new command groups through `app.add_typer(...)`; do not create alternate root entrypoints.
- Use `get_container(ctx)` to resolve the shared `BootstrapContainer`; do not instantiate infrastructure dependencies directly inside command functions.
- Keep `bootstrap()` as the composition root for wiring runtime paths, stores, registries, artifact storage, and use cases; framework code should consume the container, not rebuild it piecemeal.
- Follow the existing command pattern: parse Typer arguments/options, call one use case, map typed domain errors to `FailureEnvelope`, and render either text output or JSON through the shared helpers.
- Preserve the shared `--output-format` behavior by using `OutputFormat`, `build_command_meta(...)`, and `emit_json_response(...)` instead of bespoke JSON flags or serializers.
- When a command can receive option-like user input, follow the existing Typer escape pattern of positional input plus an explicit option such as `--query`.
- Use `typer.secho(..., err=True, fg=typer.colors.RED)` for human-readable failures and `typer.Exit(code=...)` with stable exit codes from typed exceptions.
- Keep long-running progress messages on stderr when they are operational status lines, so JSON stdout remains machine-readable.
- Treat `eval` and `config` command groups as real extension points but not as permission to add placeholder logic without contracts, use cases, and tests.
- Keep framework behavior testable through `typer.testing.CliRunner` and stubbed container use cases rather than full-stack command tests by default.

### Testing Rules

- Keep tests under `tests/unit/` for isolated module behavior, `tests/integration/` for adapter and persistence seams, and `tests/e2e/` for real CLI flows executed through `uv run codeman ...`.
- Use `pytest` and the standard library only; prefer simple fakes, stubs, and real DTOs over custom helper frameworks.
- For CLI unit tests, use `typer.testing.CliRunner` with an injected `BootstrapContainer` or stubbed use case on the container instead of building full runtime state.
- For application unit tests, use explicit fake stores and fake adapters as dataclasses with minimal behavior; keep their APIs aligned with the relevant ports.
- Build expected results with real contract DTOs such as `RepositoryRecord`, `SnapshotRecord`, `RunLexicalQueryResult`, and related diagnostics models instead of loose dictionaries.
- Assert stable user-facing behavior: exit codes, error codes, JSON envelope shape, key stdout lines, and deterministic metadata fields.
- When testing JSON output, parse `result.stdout` as JSON and assert envelope fields like `ok`, `data`, `error.code`, and `meta.command`.
- Keep end-to-end tests focused on realistic CLI workflows, using temporary workspaces and `CODEMAN_WORKSPACE_ROOT` so runtime artifacts stay isolated per test.
- For e2e execution, prefer `subprocess.run(..., check=False)` and assert return codes plus stdout/stderr explicitly rather than relying on implicit success.
- Use `.local/uv-cache` in tests that invoke `uv` so dependency cache behavior stays local to the repository.
- Preserve deterministic ordering in tests by constructing fixtures and expectations with explicit paths, ranks, timestamps, or sorted inputs when the production code guarantees stable ordering.
- Test both happy paths and contract-level failures, especially missing baselines, missing artifacts, corrupt payloads, and repository registration errors.
- New CLI commands are not complete until they have unit tests for text mode and JSON mode, plus at least one error-path test with the expected exit code and envelope.

### Code Quality & Style Rules

- Keep module, function, and test file names in `snake_case`; current package structure uses descriptive, role-based module names such as `build_lexical_index.py`, `repository_repository.py`, and `test_query.py`.
- Prefer short, factual module and function docstrings that state responsibility directly; follow the existing one-line docstring style instead of long narrative comments.
- Add comments sparingly; only annotate non-obvious logic, invariants, or corruption checks that would otherwise be easy to misread.
- Keep line length compatible with Ruff's `100` character limit.
- Preserve the current layered package layout: `cli`, `application`, `contracts`, `config`, `infrastructure`, `domain`, and `mcp`.
- Keep ports in `src/codeman/application/ports/` and adapter implementations in `src/codeman/infrastructure/`; do not collapse adapter code into application modules.
- Prefer explicit helper functions for reusable normalization or validation steps, such as path normalization and payload integrity checks, instead of embedding long inline conditionals in command handlers.
- Use narrow, descriptive error classes and DTO names that reflect the specific failure or boundary they model; avoid vague names like `Result`, `Data`, or `Utils`.
- Keep public contracts stable and machine-readable; when extending DTOs, prefer additive fields with explicit defaults over shape-breaking changes.
- Maintain deterministic helper naming around ordering, matching, fingerprinting, and formatting; this codebase values traceable function names over clever abstraction.
- Prefer ASCII-only source unless an existing file already requires otherwise.
- Follow the repository editing discipline: use focused changes, preserve unrelated worktree changes, and avoid destructive git operations when implementing or refactoring.
- For manual file edits, prefer patch-style changes that keep diffs tight and reviewable rather than rewriting whole files without need.

### Development Workflow Rules

- Use `uv` as the official workflow for dependency installation, CLI execution, testing, and linting; prefer `uv sync --group dev`, `uv run codeman ...`, and `uv run --group dev ...`.
- Treat `README.md` and `docs/cli-reference.md` as the baseline operational contract for CLI examples; keep new commands and options documented in the same style when the command surface changes.
- Keep production code under `src/`, tests under `tests/`, docs under `docs/`, and planning artifacts under `_bmad/` or `_bmad-output/`; do not mix generated planning content into runtime modules.
- Use workspace-local runtime isolation for development and tests; prefer `CODEMAN_WORKSPACE_ROOT` when a workflow needs a temporary or alternate runtime root.
- Keep runtime artifacts inside `.codeman/` rather than scattering generated files across the repository or target repositories.
- Prefer JSON output mode for automation, tests, and repeatable evaluation workflows; treat text mode as the human-readable default and JSON mode as the stable machine interface.
- When adding or changing CLI workflows, keep both text and JSON outputs aligned with the same underlying use-case result rather than implementing two separate execution paths.
- Run focused validation for touched areas before considering work complete: at minimum the affected `pytest` tests, and when formatting/imports may change, the relevant `ruff check` and `ruff format --check` commands.
- Do not treat placeholder modules like `eval`, `compare`, or `config` as permission to invent behavior; extend them only when the supporting contracts, application logic, and tests are ready.
- Keep local-first assumptions intact during development: external-provider-backed or MCP-oriented behavior must remain explicit, optional, and separated from baseline CLI workflows unless the implementation deliberately changes that contract.
- When adding new operational commands, preserve stderr for progress/status messages and stdout for primary output so shell usage and tests stay predictable.
- Prefer incremental, reviewable changes over broad rewrites; this repository is already structured for layered evolution, so extend the nearest fitting module instead of introducing parallel patterns.

### Critical Don't-Miss Rules

- Do not treat planned surfaces as implemented surfaces: MCP, semantic retrieval, hybrid retrieval, and OpenAI-assisted evaluation are documented product directions, but agents must verify the current code before wiring against them.
- Keep the project local-first by default. Do not send repository content, chunks, embeddings, or query content to external providers unless that behavior is explicitly implemented and opt-in by configuration.
- Do not write runtime artifacts into the indexed target repository. Snapshot manifests, chunk payloads, indexes, caches, logs, and temp files belong under the workspace `.codeman/` tree.
- Do not bypass snapshot integrity checks. Chunk generation and later stages must respect the stored snapshot identity and fail safely when the live repository no longer matches it.
- Do not assume every readable file is a source file. The scanner intentionally ignores directories like `.git`, `.codeman`, `node_modules`, `vendor`, virtualenvs, and common caches, and it skips binary, unreadable, symlinked, and unsupported files.
- Do not weaken deterministic ordering. Source files, chunks, payload loading, and result formatting should stay stable across runs so benchmarks, tests, and diffs remain comparable.
- Do not silently recover from payload corruption or missing artifacts. Missing chunk payloads, mismatched metadata, and invalid JSON artifacts are explicit failure conditions with typed errors.
- Do not collapse parsing, chunking, indexing, and formatting into one module. The current architecture depends on narrow boundaries between application ports, infrastructure adapters, contracts, and CLI orchestration.
- Do not invent ad hoc output shapes for convenience. JSON output is a contract surface and should remain envelope-based and machine-stable.
- Do not let stderr/stdout responsibilities drift. Human progress messages belong on stderr when needed; primary command output belongs on stdout.
- Do not use fallback behavior as if it were equivalent to structural success. The codebase records fallback and degraded chunking explicitly, and agents should preserve those diagnostics rather than hiding them.
- Do not promote synthetic evaluation data or LLM-judge signals to canonical truth without review. The PRD requires reviewed, versioned baselines and treats judge outputs as auxiliary evidence, not the sole source of truth.
- Do not hide provider, model, grader version, or evaluation configuration when working on benchmark or judge workflows. Traceability is a product requirement, not optional metadata.
- Do not "fix" unrelated dirty worktree changes while implementing a task. Keep edits scoped to the requested change and preserve user work outside that scope.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code.
- Follow all rules unless the current task explicitly requires a documented exception.
- When the codebase and planning artifacts differ, trust the implemented code for current behavior and use the planning artifacts for intended direction.
- Update this file when new implementation patterns become stable and repeated.

**For Humans:**

- Keep this file lean and focused on unobvious agent-facing rules.
- Update it when the technology stack, runtime boundaries, output contracts, or evaluation model changes.
- Review it periodically and remove rules that have become obsolete or overly obvious.
- Treat it as the fast-start context for future implementation agents, not as a replacement for architecture or PRD artifacts.

Last Updated: 2026-03-14T13:04:22+0200
