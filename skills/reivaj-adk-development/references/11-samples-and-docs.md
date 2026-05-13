# 11. Samples Y Documentacion

## Referencias Locales Oficiales

Skills y referencias ya disponibles localmente:

| Recurso | Uso |
|---|---|
| `google-agents-cli-workflow` | Ciclo de vida ADK completo |
| `google-agents-cli-adk-code` | Patrones Python ADK, agents, tools, callbacks, state |
| `google-agents-cli-eval` | Evalsets, metodologia, eval-fix loop |
| `google-agents-cli-deploy` | Agent Runtime, Cloud Run, GKE, secrets, CI/CD |
| `google-agents-cli-observability` | Trace, logs, analytics, integraciones |
| `google-agents-cli-scaffold` | Crear, enhance, upgrade proyectos |
| `google-agents-cli-publish` | Publicacion Gemini Enterprise |
| `references/adk-python.md` | Referencia local ADK Python |
| `references/adk-2.0.md` | Referencia local ADK 2.0 Workflow |
| `references/internals.md` | Internals de agents-cli |

## Docs Web Consultadas

| URL | Tema |
|---|---|
| `https://adk.dev/llms.txt` | Indice docs ADK |
| `https://adk.dev/agents/config/index.md` | Agent Config docs |
| `https://github.com/google/adk-docs/blob/main/docs/agents/config.md` | Agent Config markdown |
| `https://adk.dev/api-reference/agentconfig/` | API reference Agent Config |
| `https://docs.ag-ui.com/` | AG-UI docs |
| `https://docs.ag-ui.com/agentic-protocols` | Relacion AG-UI con MCP/A2A |
| `https://docs.ag-ui.com/llms.txt` | Indice docs AG-UI |
| `https://adk.dev/integrations/a2ui/` | Integracion A2UI con ADK |
| `https://a2ui.org/` | A2UI spec/site |
| `https://adk.dev/skills/` | ADK Skills, SkillToolset y progressive disclosure |
| `https://agentskills.io/specification` | Especificacion Agent Skills y formato `SKILL.md` |
| `https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/` | Guia oficial con patrones inline, file-based, external y meta |
| `https://adk.dev/integrations/` | Catalogo oficial de herramientas e integraciones ADK |
| `https://adk.dev/api-reference/python/` | Referencia API Python `google.adk.*` |

## ADK Samples Estudiados

La referencia completa de agentes de ejemplo oficiales esta en
`13-google-adk-sample-agents.md`. Este archivo mantiene solo el resumen de
fuentes y muestras especialmente reutilizables.

| Sample | Patron reutilizable |
|---|---|
| `deep-search` | Research agent iterativo, citaciones, evaluador, refinamiento |
| `workflow-concurrent_research_writer` | Workflow con fan-out/fan-in paralelo |
| `workflows-sequential` | Workflow secuencial basico |
| `llm-auditor` | Critic/reviser/fact-checking, referencias grounding |
| `academic-research` | Research domain agent |
| `agent_tool_with_grounding_metadata` | Propagacion de grounding metadata via AgentTool |
| `tool_builtin_config` | Built-in tools en config |
| `tool_agent_tool_config` | AgentTool en config |
| `built_in_multi_tools` | Multiples built-ins y `bypass_multi_tools_limit` |
| `plugin_reflect_tool_retry` | Plugin de retry/reflection para tools |
| `skills_agent` | ADK SkillToolset local |
| `skills_agent_gcs` | ADK SkillToolset desde GCS |
| `agent-skills-tutorial` | SkillToolset con progressive disclosure e inline/file/external/meta skills |
| `a2a_basic` | A2A basico |
| `a2a_root` | A2A root agent |
| `fields_planner` | Planner field/sample patterns |

Otros samples oficiales relevantes por fase:

| Sample | Cuando mirarlo |
|---|---|
| `ambient-expense-agent` | Agentes ambient/scheduled/event-driven |
| `adk-ae-oauth` | OAuth 2.0, user consent, Drive, Agent Runtime |
| `genmedia-for-commerce` | Full-stack React, MCP, media generation, Enterprise |
| `safety-plugins` | Guardrails, filters, Model Armor |
| `data-science` | SQL, BigQuery, code execution, sandbox |
| `memory-bank` | Memoria cross-session y Memory Bank |

## Seleccion Rapida De Sample

| Necesidad | Sample preferido |
|---|---|
| Research con citaciones | `deep-search` |
| Research paralelo | `workflow-concurrent_research_writer` |
| Auditoria/fact-check | `llm-auditor` |
| SkillToolset local/GCS | `skills_agent`, `skills_agent_gcs` |
| SkillToolset progressive disclosure y meta skills | `agent-skills-tutorial` |
| A2A | `a2a_basic`, `a2a_root` |
| Tool retry | `plugin_reflect_tool_retry` |
| Grounding metadata anidada | `agent_tool_with_grounding_metadata` |
| Seguridad | `safety-plugins` |
| Memoria | `memory-bank` |
| OAuth | `adk-ae-oauth` |
