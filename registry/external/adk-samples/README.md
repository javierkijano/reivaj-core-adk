# External ADK Samples Registry

Source type: `external`

External source:

- Upstream: `https://github.com/google/adk-samples/tree/main/python/agents`

This registry covers the 73 Python ADK sample directories from the upstream
`google/adk-samples` repository. External entries must point to web URLs, not to
local downloads under `third-party/`. It separates full sample agents from
subcomponents so that patterns can later be extracted into reusable internal
resources.

## Files

| File | Purpose |
|---|---|
| `agent-catalog.yaml` | All sample agents and primary tags |
| `component-inventory.yaml` | Counts and source-oriented component inventory per sample |
| `skills.yaml` | ADK Skills discovered under samples |
| `reusable-functionality.yaml` | Cross-sample reusable patterns and candidate abstractions |
| `*.md` | General descriptions only; do not duplicate structured records |

## Current Inventory Summary

| Metric | Count |
|---|---:|
| Sample directories | 73 |
| Sample directories with `README.md` | 73 |
| Sample directories with `pyproject.toml` | 72 |
| Discovered `agent.py` files | 143 |
| Discovered Python tool modules under `tools/` | 118 |
| Discovered `SKILL.md` files | 14 |

Counts are source-discovery counts, not reviewed reusable components. A sample
with many `agent.py` files usually contains root agents plus subagents.
