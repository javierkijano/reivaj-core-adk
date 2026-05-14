# Resource Registry

This registry standardizes how reusable agent resources are discovered,
classified, and maintained across external sources and internal projects.

The goal is to make agents, tools, skills, prompts, workflows, integrations, and
interesting implementation patterns decomposable into reusable components.

## Structure

| Path | Purpose |
|---|---|
| `index.html` | Static browser for searching and filtering registry YAML catalogs |
| `schema.yaml` | Authoritative entry schema and maintenance rules for registry records |
| `schema.md` | Human-readable schema overview |
| `taxonomy.yaml` | Authoritative controlled vocabulary for tags |
| `taxonomy.md` | Human-readable taxonomy overview |
| `external/adk-samples/README.md` | External source index for Google ADK samples |
| `external/adk-samples/agent-catalog.yaml` | Catalog of upstream Google ADK sample agents |
| `external/adk-samples/component-inventory.yaml` | Component-level inventory: agent files, tools, skills, prompts, evals, deployment assets |
| `external/adk-samples/skills.yaml` | ADK Skill inventory found inside external samples |
| `external/adk-samples/reusable-functionality.yaml` | Cross-sample reusable patterns and implementation ideas |
| `external/workflow-samples/README.md` | External source index for ADK 2.0 Workflow samples |
| `external/workflow-samples/workflow-catalog.yaml` | Catalog of upstream `google/adk-python` workflow samples |
| `external/adk-integrations/README.md` | External source index for ADK public tools and integrations |
| `external/adk-integrations/integrations-catalog.yaml` | Catalog of public `adk.dev/integrations` resources |
| `internal/README.md` | Internal source index for repository-owned resources |
| `internal/resources.yaml` | Catalog of internal agents and skills |

## Registry Principles

- Keep source inventory separate from reusable abstractions.
- Keep external knowledge sources under `external/` and internal knowledge
  sources under `internal/`.
- Keep structured registry data in YAML files; Markdown files are for general
  descriptions and navigation only.
- External registry entries must use web URLs in `source`; internal registry
  entries must use repository-relative paths.
- Tag everything with controlled tags, but allow provisional tags when needed.
- Record source references so every reusable component is traceable to code.
- Prefer small reusable components over copying whole agents.
- Track maturity: `observed`, `candidate`, `extracted`, `adapted`, `productionized`.
- Avoid secrets, environment-specific config, and cloud-changing commands in registry content.

## Reuse Flow

1. Identify a source sample in `external/adk-samples/agent-catalog.yaml` or an
   internal resource in `internal/resources.yaml`.
2. Inspect component counts and source paths in `external/adk-samples/component-inventory.yaml`.
3. Find reusable implementation patterns in `external/adk-samples/reusable-functionality.yaml`.
4. Create or update a component entry using `schema.yaml`.
5. Promote the component maturity only after code review, tests, and evals where relevant.

## Browser

Open `registry/index.html` through a local static server:

```bash
python3 -m http.server
```

Then visit `http://localhost:8000/registry/`.

The browser loads YAML catalogs from configured registry files and turns items
into searchable cards. To add more sources later, extend the `REGISTRY_SOURCES`
array in `index.html` or use the file loader in the sidebar.
