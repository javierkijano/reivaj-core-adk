# Registry Schema

The authoritative schema is `registry/schema.yaml`. This Markdown file is only a
human-readable overview.

Catalog YAML files use one shared envelope:

- `source`: metadata about the knowledge source, including `source_type`.
- `items`: structured registry records for agents, skills, workflows, patterns,
  tools, or internal resources.

Example:

```yaml
source:
  id: adk-sample-agents
  label: External ADK sample agents
  source_type: external
  upstream_root: https://github.com/google/adk-samples/tree/main/python/agents
items:
  - id: fun-facts
    name: fun-facts
    source: https://github.com/google/adk-samples/tree/main/python/agents/fun-facts
    summary: Minimal ADK agent and simple deployment baseline.
    tags:
      - entity:agent
      - pattern:single-agent
      - domain:horizontal
    maturity: maturity:observed
```

## Maintenance Rules

- Add structured records to YAML catalogs, not Markdown descriptions.
- Keep this schema centralized in `schema.yaml`; do not redefine fields per
  catalog.
- External entries must use web URLs and must not point to local downloads such
  as `third-party/`.
- Internal entries must use repository-relative paths.
- Tags should come from `taxonomy.yaml`; add provisional tags only with a note.
- Do not include secrets or real environment values.
- Do not mark a component `productionized` unless it has review, tests, and evals when LLM behavior matters.
- If a source component is cloud-changing, mark the dependency and approval requirement.
