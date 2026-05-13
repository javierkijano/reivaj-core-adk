# Registry Taxonomy

The authoritative taxonomy is `registry/taxonomy.yaml`. This Markdown file is a
human-readable overview only.

The taxonomy defines controlled values for:

- `entity:*` resource types such as agents, tools, skills, workflows, plugins,
  UIs, deployment assets, evaluations, and data pipelines.
- `capability:*` reusable capabilities such as research, RAG, grounding, data
  analysis, document processing, planning, security, observability, and skills.
- `pattern:*` implementation patterns such as single-agent, multi-agent,
  workflow sequencing, parallelism, loops, HITL, streaming, multimodal, MCP, A2A,
  and SkillToolset.
- `integration:*` external systems such as BigQuery, Vertex AI, Google Search,
  Maps, Apigee, Application Integration, GitHub, Dataflow, Dataproc, dbt,
  Dataform, AlloyDB, YouTube, payment APIs, and Model Armor.
- `domain:*` business or technical domains.
- `maturity:*` lifecycle states.
- `source_type:*` registry source ownership.

Add new tags in `taxonomy.yaml`; do not redefine tag sets inside catalog files.
