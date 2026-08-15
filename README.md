# Multi-Agent Research Tool

Local Python research infrastructure for Codex, Claude Code, Kiro, Kilo Code, and Hermes. The tool is designed as an evidence/provenance boundary: agents may propose, critique, design, and execute research work, but claims are promoted only through the registered experiment, immutable artifacts, evidence graph, and independent verification gates described in [`SPEC.md`](SPEC.md) and [`RULES.md`](RULES.md).

## Status and scope

This repository contains the local MVP: strict protocol models, state transitions, append-only storage, typed evidence graph, role/gate-enforcing service, JSON CLI, and MCP stdio adapter. It is an evidence/provenance boundary, not an LLM provider or an automatic truth oracle.

The MVP deliberately does not bundle web search, cloud credentials, a database, or arbitrary experiment execution. Researchers and novelty agents provide source URLs, query logs, environment metadata, and externally produced raw outputs.

## Install

Python 3.11 or newer is required.

With `pip`:

```bash
python -m pip install -e .
```

With `uv`:

```bash
uv pip install -e .
```

For a one-shot command without creating a project virtualenv, use `uvx` (the Python-native equivalent of `npx`):

```bash
uvx --from . research-tool --help
uvx --from . research-tool init ./research-project
```

To install the command persistently for your user:

```bash
uv tool install .
research-tool --help
```

After this repository is published to GitHub, the same forms work from Git:

```bash
uvx --from git+https://github.com/ORG/REPO research-tool --help
uv tool install git+https://github.com/ORG/REPO
```

The GitHub URL is intentionally a placeholder until this checkout has a real remote. The `npx` command is not provided because this is a Python package; an npm wrapper would still need to install and manage the Python runtime and dependencies.

For development/test dependencies:

```bash
python -m pip install -e ".[dev]"
# or
uv pip install -e ".[dev]"
```

The package exposes the `research-tool` console command and the `research_tool.mcp_server` module. A successful process start is still not the same as a connected client: use the client-specific verification steps in [`docs/integrations.md`](docs/integrations.md).

## Intended CLI smoke flow

The smallest CLI smoke flow is:

```bash
research-tool --help
research-tool init ./research-project
research-tool status --project ./research-project
research-tool validate --project ./research-project --limitation "No claims registered yet"
# After the evidence and verification gates pass:
research-tool report --project ./research-project --claim C-001 --limitation "Scope is limited to the registered benchmark"
```

The flow returns machine-readable JSON. The final command is expected to return non-zero until a validated claim exists; `validate` fails closed when a completion gate fails.

For a direct MCP stdio launch, use the module entrypoint until a published `research-tool mcp` command is available:

```bash
python -m research_tool.mcp_server
```

Do not add logging or banners to stdout in an MCP server; stdout is reserved for the protocol. Diagnostics belong on stderr.

## Research workflow and role boundaries

The shared core is intentionally stricter than a chat transcript:

1. Hypothesis agents generate independent, falsifiable hypotheses before seeing peer output.
2. Critics identify fatal issues, counterexamples, and competing explanations.
3. The experiment designer registers baselines, controls, metrics, thresholds, seeds, and ablations before execution.
4. The runner records the registered protocol and raw outputs without deleting failed runs or changing the protocol after seeing outcomes.
5. An independent verifier performs a blind initial review and recomputes metrics from raw artifacts where possible.
6. The synthesizer writes only from validated claim IDs, with scope, uncertainty, limitations, and contradictions preserved.

Consensus is not evidence. A claim must retain a traceable chain:

```text
Claim -> Evidence -> Finding -> Experiment -> immutable Artifact
```

The verifier is not allowed to use the producer's conclusion or confidence for its initial verdict. Novelty is a separate gate and requires its own query log, sources, closest prior work, and coverage limits.

## Immutable artifacts and provenance

Raw outputs are append-only. A raw artifact must retain at least:

```yaml
artifact_id: ART-001
created_by: C2
created_at: 2026-08-15T00:00:00Z
input_ids: [EXP-001]
tool: example-runner
tool_version: 1.0.0
config_hash: sha256:...
content_hash: sha256:...
path: artifacts/ART-001/content
```

Existing object paths must never be overwritten. Derived artifacts point back to their raw inputs, and failed/negative runs remain queryable. These rules are integrity requirements, not optional logging conventions.

## MCP integrations

See [`docs/integrations.md`](docs/integrations.md) for client-specific configuration for Codex, Claude Code, Kiro, Kilo Code, and Hermes. All examples use local stdio and the conservative module entrypoint:

```text
python -m research_tool.mcp_server
```

The shorter `research-tool mcp` form should be used only after the CLI adapter actually exposes that subcommand.

