# MCP integrations

This project is intended to expose one local MCP stdio server to several coding agents. The client supplies the model and agent loop; `research-tool` supplies the shared research protocol boundary, role checks, state transitions, provenance, immutable artifact storage, evidence-chain validation, and completion gates.

## Before configuring a client

Install the project in the environment from which the client will launch the process:

```bash
python -m pip install -e .
# or
uv pip install -e .
```

For an `npx`-style one-shot invocation, use `uvx`:

```bash
uvx --from . research-tool --help
uvx --from . research-tool mcp
```

For a persistent user installation:

```bash
uv tool install .
research-tool --help
```

Once a real GitHub remote exists, replace `ORG/REPO` in these commands:

```bash
uvx --from git+https://github.com/ORG/REPO research-tool --help
uv tool install git+https://github.com/ORG/REPO
```

The checkout contains `research_tool.mcp_server` and the `research-tool mcp` console command. The repository now includes project-local client configuration files. They all use the module entrypoint:

```text
python -m research_tool.mcp_server
```

Do not claim a connection from configuration alone. Verify, per client, that the server process starts, MCP initialization succeeds, the expected tools are listed, and a harmless read-only project/status call works.

## Codex

OpenAI documents MCP configuration in `~/.codex/config.toml`, project-scoped `.codex/config.toml`, and the `codex mcp` subcommand. This repository includes `.codex/config.toml`. Add the server with the CLI if you prefer:

```bash
codex mcp add research-tool -- python -m research_tool.mcp_server
codex mcp list
```

The checked-in TOML is:

```toml
[mcp_servers.research-tool]
command = "python"
args = ["-m", "research_tool.mcp_server"]
```

The TOML key is `mcp_servers` (snake case), not the JSON `mcpServers` spelling used by several other clients. The local server process and tool discovery are verified. Codex is installed on this machine, but a live client `/mcp` discovery check is still pending.

Official source: [Codex MCP documentation](https://developers.openai.com/codex/mcp/).

## Claude Code

Project-scoped Claude Code configuration is checked in at `.mcp.json`:

```json
{
  "mcpServers": {
    "research-tool": {
      "command": "python",
      "args": ["-m", "research_tool.mcp_server"]
    }
  }
}
```

Or add it through the CLI (the exact flag spelling should be checked against the installed Claude Code version):

```bash
claude mcp add --transport stdio research-tool --scope project -- python -m research_tool.mcp_server
claude mcp list
```

Claude Code may prompt for approval before using a project-scoped `.mcp.json` server. No secrets are required for this local server. Connection and tool discovery in Claude Code are not verified here.

Official source: [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).

## Kiro

For workspace scope, this repository includes `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "research-tool": {
      "command": "python",
      "args": ["-m", "research_tool.mcp_server"],
      "disabled": false
    }
  }
}
```

Kiro also supports a user-level configuration at `~/.kiro/settings/mcp.json`. Check the MCP panel or `/mcp` to confirm the server is loaded and inspect its tools. The server process and MCP tool list are verified locally; Kiro workspace loading is not verified here.

Official sources: [Kiro IDE MCP configuration](https://kiro.dev/docs/mcp/configuration/), [Kiro CLI MCP configuration](https://kiro.dev/docs/cli/mcp/configuration/).

## Kilo Code

Kilo Code uses a top-level `mcp` map. This repository includes `.kilo/kilo.json`:

```json
{
  "mcp": {
    "research-tool": {
      "type": "local",
      "command": ["python", "-m", "research_tool.mcp_server"],
      "enabled": true
    }
  }
}
```

Kilo's local server format uses an argv array. Restart/reload the client as needed, then confirm that the server is enabled and its tools are visible. Kilo integration is **not verified** in this checkout.

Official sources: [Using MCP in Kilo Code](https://kilo.ai/docs/automate/mcp/using-in-kilo-code), [Using MCP in the Kilo CLI](https://kilo.ai/docs/automate/mcp/using-in-cli).

## Hermes

Hermes reads stdio servers from `mcp_servers` in its YAML configuration, commonly `~/.hermes/config.yaml`. Hermes does not document a project-local MCP file, so the ready-to-merge snippet lives at `integrations/hermes.mcp.yaml`:

```yaml
mcp_servers:
  research-tool:
    command: python
    args:
      - -m
      - research_tool.mcp_server
    enabled: true
```

Merge that entry into the active Hermes config, start Hermes, inspect its MCP status/tools, and reload MCP configuration after edits. Do not enable parallel calls for this server because the service writes shared append-only state. Hermes is not installed or connected in this checkout.

Official sources: [Hermes MCP feature documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), [Hermes MCP config reference](https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference).

## Shared safety and research-integrity contract

All clients connect to the same boundary; none gets permission to bypass it:

- Hypothesis generation, criticism, experiment design, execution, blind verification, novelty search, and synthesis remain separate roles.
- A verifier must receive the hypothesis, registered protocol, code, raw artifacts, and environment, but not the producer's conclusion/confidence before its initial verdict.
- Raw artifacts are create-only and content/config hashed. Failed, null, refuted, and disputed results are retained.
- A claim cannot be finalized without a valid `Claim -> Evidence -> Finding -> Experiment -> Artifact` chain and the required verification/novelty gates.
- Client configuration is not proof of scientific validity, reproducibility, or MCP connectivity.

## Verification matrix

| Item | Status in this checkout |
|---|---|
| Client config shapes and official links | Project files and docs cross-checked against vendor pages on 2026-08-15 |
| `research-tool mcp` generic command | CLI path is implemented; editable-install invocation not separately exercised |
| `uvx --from . research-tool --help` | Passed from a clean uv tool environment |
| `python -m research_tool.mcp_server` | Verified as a real stdio subprocess |
| MCP initialize/list-tools smoke test | Passed in `tests/test_mcp_subprocess.py` |
| Project config syntax | Passed by `tests/test_client_configs.py` |
| Five client connections | Not run; only Codex CLI is installed on this machine |
| End-to-end claim/evidence/verification/report flow | Passed by service tests; external experiment execution is out of scope |
| GitHub remote, push, or pull request | Not available; this checkout has no remote configured |
