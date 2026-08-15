# MVP Task Checklist

## P0 protocol and integrity

- [x] Models for hypotheses, critiques, experiments, artifacts, evidence, claims, verification, novelty, and provenance.
- [x] Allowed state transitions and completion gate.
- [x] Typed graph with evidence-chain and orphan-claim validation.
- [x] Immutable raw artifact storage with content/config hashes.
- [x] Blind verifier context excluding producer conclusion.

## P1 interfaces

- [x] Core service with role and phase enforcement.
- [x] CLI with JSON output and deterministic exit codes.
- [x] MCP stdio server exposing the core service.
- [x] Setup docs/config examples for Codex, Claude Code, Kiro, Kilo Code, Hermes.

## P0/P1 tests

- [x] Invalid state transitions fail.
- [x] Orphan claims fail the evidence gate.
- [x] Raw artifacts cannot be overwritten.
- [x] Hypothesis peers are hidden before round close.
- [x] Blind verifier context excludes producer conclusion.
- [x] Protocol changes require a revision through create-only experiment records.
- [x] Failed experiments are retained.
- [x] Unsupported claims cannot reach final report.
- [ ] Citation/source IDs resolve (external source registry remains an explicit follow-up).
- [x] End-to-end happy path and incomplete path.

## Release gates

- [x] `python -m pytest` — 28 passed.
- [x] `python -m compileall research_tool tests`
- [x] README install/smoke flow verified.
- [x] Git diff reviewed; no secrets or build artifacts.
- [ ] Local commit created.
- [x] Remote/PR status reported honestly.

## One-command installation follow-up

- [x] Verify `uvx --from . research-tool --help`.
- [x] Document `uv tool install .` and `uvx --from <source>` usage.
- [x] Add packaging smoke coverage without changing the MCP protocol.
