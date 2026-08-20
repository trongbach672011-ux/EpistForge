# EpistForge

A research protocol for AI agents that have to show their work.

AI agents can produce a convincing conclusion before they have enough evidence for it. EpistForge puts a machine-checkable research process between the initial idea and the final report.

It runs locally as a Python CLI and an MCP stdio server. Agents can propose hypotheses, run experiments, challenge results, verify claims, and write reports, but they cannot skip the evidence trail.

```text
Hypothesis
    ↓
Critique
    ↓
Registered experiment
    ↓
Raw artifact
    ↓
Finding
    ↓
Evidence
    ↓
Claim
    ↓
Independent verification
    ↓
Novelty check
    ↓
Final report
```

If a required step is missing, the claim does not move forward.

## Why EpistForge exists

A multi-agent setup does not automatically make research reliable.

Five agents agreeing with each other can still be five agents repeating the same mistake.

EpistForge treats agreement and evidence as different things. Instead of asking agents to decide among themselves whether a result is good enough, it records the research state and checks explicit rules before a claim can be promoted.

The result is a research history you can inspect after the agents finish.

You can see:

* which hypothesis produced an experiment
* what the experiment was supposed to measure
* which artifacts came from the run
* which findings depend on those artifacts
* what evidence supports or contradicts a claim
* who verified the result
* what was checked for novelty
* why a claim was allowed into the report

Failed and inconclusive results stay in the record too.

## Research is stored as evidence, not chat history

EpistForge uses typed research objects instead of treating an agent conversation as the source of truth.

The basic evidence chain is:

```text
Claim
  └── Evidence
        └── Finding
              └── Experiment
                    └── Artifact
```

Raw artifacts include provenance and hashes so later stages can refer back to the actual output rather than a summary written by another agent.

This matters when several agents work on the same project. The verifier should be checking the experiment and its artifacts, not trusting the producer's explanation of what happened.

## Gates

EpistForge checks each stage before allowing the research to continue.

### Hypothesis

A hypothesis needs more than a statement.

It must record:

* a proposed mechanism
* assumptions
* predictions
* falsifiers

Fatal critique issues have to be resolved before it passes the hypothesis gate.

### Experiment

Experiments are registered before execution.

The protocol requires baselines, controls, metrics, success thresholds, failure thresholds, and expected artifacts.

This prevents an agent from running an experiment first and deciding afterward what should count as success.

### Evidence

Evidence must point to real artifacts.

EpistForge checks that referenced artifacts exist, that their content hashes are valid, and that the corresponding finding has a recorded source.

### Verification

The verifier cannot be the same agent that produced the result.

Verification records an initial blind verdict and checks experiment compliance. The verifier also recomputes metrics when possible, or records why recomputation was not possible.

Unresolved P0 verification issues block promotion.

### Novelty

A claim cannot simply be labeled "novel."

The novelty record stores the queries used, sources checked, closest prior work, search limits, and whether the wording of the claim stays inside the coverage of that search.

A failed search is still a result. It has to be recorded instead of silently becoming "no prior work exists."

### Writing

The writer does not get to invent new research claims.

Major claims in the final draft must already exist in the validated research state. Disputed claims cannot be written as settled facts, and limitations have to be included.

The report is the last consumer of the evidence graph, not another place to create evidence.

## Quick start

EpistForge requires Python 3.11 or newer.

Run it directly from a checkout with `uvx`:

```bash
uvx --from . research-tool --help
```

Install the command with `uv`:

```bash
uv tool install .
research-tool --help
```

Or install it into the active Python environment:

```bash
python -m pip install -e .
research-tool --help
```

## Create a research project

Initialize a workspace:

```bash
research-tool init ./research-project
```

Check its current state:

```bash
research-tool status --project ./research-project
```

CLI output is JSON so coding agents can consume the result without scraping terminal prose.

## Use EpistForge through MCP

Start the MCP stdio server:

```bash
research-tool mcp --project ./research-project
```

EpistForge can then provide the research protocol to MCP-capable coding agents.

Project-local configuration is included for Codex, Claude Code, Kiro, and Kilo Code. Hermes has a ready-to-merge configuration snippet because its MCP configuration is user scoped.

See [`docs/integrations.md`](docs/integrations.md) for setup and client-specific checks.

## Validate a claim

Before producing a report, validate the research state:

```bash
research-tool validate \
  --project ./research-project \
  --claim C-001 \
  --limitation "Only the registered benchmark was evaluated"
```

Validation fails if the required evidence, verification, novelty, or writing checks are incomplete.

Once the gates pass, generate the report:

```bash
research-tool report \
  --project ./research-project \
  --claim C-001 \
  --limitation "Only the registered benchmark was evaluated"
```

## What happens to bad results?

They stay.

A negative result should not disappear because another hypothesis looks more promising. A disputed claim should not quietly become accepted later. An inconclusive experiment should not be rewritten as a weak success.

EpistForge keeps failed, negative, disputed, and inconclusive results queryable so later agents can see what was already tried and why it did not pass.

## What EpistForge does not do

EpistForge does not provide an LLM.

It does not bundle web search or cloud credentials.

It does not execute arbitrary experiments for the agent.

It does not decide whether a scientific statement is ultimately true.

Its job is narrower: keep the research process explicit, preserve the evidence trail, and stop unsupported claims from moving through the workflow unnoticed.

External agents still provide sources, environment information, experiment execution, and raw outputs.

## Development

Install the development dependencies:

```bash
uv pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest
```

The tests cover protocol gates, state transitions, storage and graph behavior, service operations, packaging, MCP interfaces, and client configuration.
