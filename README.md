# EpistForge

> A research claim should not become a conclusion just because an agent said it.

EpistForge is a local protocol for AI-assisted research where claims have to **earn their way into the final report**.

It sits between research agents and their output and keeps a machine-checkable record of:

`hypothesis → experiment → artifact → finding → evidence → claim → verification`

Agents may propose, criticize, run experiments, or write.

They do not decide by themselves what counts as established knowledge.

---

## The idea

Most agent workflows optimize for finishing the research task.

EpistForge optimizes for something different:

**being able to explain why a conclusion was allowed to exist.**

A result is not promoted because several agents agree with it.

A result is promoted only when the required evidence exists and the protocol gates pass.

For example:

```text
Hypothesis
   │
   ├── mechanism recorded
   ├── predictions recorded
   └── falsifiers recorded
          │
          ▼
Registered experiment
   │
   ├── baseline
   ├── controls
   ├── metrics
   └── success / failure thresholds
          │
          ▼
Immutable artifacts
          │
          ▼
Finding + Evidence
          │
          ▼
Independent verification
          │
          ▼
Novelty check
          │
          ▼
Promotable claim
          │
          ▼
Final report
```

If a required step fails, the claim stops there.

---

## Claims have states

EpistForge treats research conclusions as objects with a lifecycle rather than free-form text.

A claim can be unsupported, disputed, verified, novelty-checked, promoted, or retracted.

Negative and inconclusive results are not deleted simply because they are inconvenient.

They remain part of the research record.

This makes it possible to ask not only:

> “What did the agents conclude?”

but also:

> “Which evidence allowed this claim to be written?”

---

## Fail closed

EpistForge deliberately rejects incomplete research.

An experiment can fail validation because it was not registered before execution.

Evidence can fail because its artifact is missing or its content hash is invalid.

Verification can fail because the verifier is the same agent that produced the result.

A novelty claim can fail because the search coverage was not recorded.

A final report can fail because the writer introduced a claim that did not exist in the validated research graph.

```text
agent output ≠ evidence
evidence ≠ verified claim
verified claim ≠ novel claim
novel claim ≠ unrestricted conclusion
```

Those distinctions are the point of EpistForge.

---

## Blind verification

Verification is separated from production.

The verifier records an initial verdict without inheriting the producer's conclusion and, where possible, recomputes metrics from the underlying artifacts.

Critical unresolved verification issues prevent promotion.

This is intended to reduce a common failure mode in agent teams where the “reviewer” merely rationalizes the previous agent's answer.

---

## Evidence is traceable

Raw artifacts are stored with provenance information and hashes.

Evidence references those artifacts explicitly rather than relying on prose summaries.

The research graph keeps relationships between:

```text
Claim
  └── Evidence
       └── Finding
            └── Experiment
                 └── Artifact
```

The final writer therefore works from validated claims, not directly from arbitrary agent conversations.

---

## Quick start

Requires Python 3.11+.

From a checkout:

```bash
uvx --from . research-tool --help
```

Or install it:

```bash
uv tool install .
research-tool --help
```

Development setup:

```bash
uv pip install -e ".[dev]"
python -m pytest
```

Create a research workspace:

```bash
research-tool init ./research-project
research-tool status --project ./research-project
```

Start the MCP server:

```bash
research-tool mcp --project ./research-project
```

EpistForge can then act as the protocol layer for MCP-capable coding and research agents.

---

## Before a claim can be written

Validation is explicit:

```bash
research-tool validate \
  --project ./research-project \
  --claim C-001 \
  --limitation "Only the registered benchmark was evaluated"
```

A final report can be generated only after the required gates pass:

```bash
research-tool report \
  --project ./research-project \
  --claim C-001 \
  --limitation "Only the registered benchmark was evaluated"
```

The CLI returns structured JSON so agents can reason about failures instead of parsing human-oriented terminal output.

---

## What EpistForge is not

EpistForge is not an LLM.

It is not a web-search engine.

It does not claim to determine scientific truth.

It does not make several agents agreeing with each other equivalent to verification.

It does not hide negative, disputed, or inconclusive results.

It provides the protocol and evidence boundary around agents that perform the actual research work.

---

## Integrations

EpistForge exposes its research workflow through an MCP stdio server and can be used with MCP-capable coding agents.

Configuration examples are available in:

[`docs/integrations.md`](docs/integrations.md)

---

## Design principle

EpistForge follows one rule:

> **No conclusion without a trail.**

If the system cannot reconstruct how a claim moved from hypothesis to evidence to verification, that claim should not appear as established knowledge.

---

## Status

EpistForge is under active development.

The current implementation focuses on the protocol layer:

* typed research objects
* explicit state transitions
* machine-checkable promotion gates
* immutable artifact provenance
* blind independent verification
* novelty-search records
* controlled synthesis
* CLI and MCP interfaces

The next goal is not to add more agents.

It is to make the evidence trail harder to fake, easier to inspect, and easier to reproduce.
