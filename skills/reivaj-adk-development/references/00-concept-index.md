# 00. Indice Conceptual ADK

Este indice organiza todos los conceptos cubiertos por la skill y apunta a la
referencia donde profundizar.

## Taxonomia Principal

| Concepto | Definicion corta | Profundizar |
|---|---|---|
| ADK | SDK para crear, ejecutar y operar agentes | `02-core-adk-concepts.md` |
| agents-cli | CLI de scaffold, desarrollo, eval, deploy y publish | `01-lifecycle.md` |
| Proyecto ADK | Estructura Python/uv con agente, tests, evals y config | `01-lifecycle.md` |
| Scaffold | Creacion/enhance/upgrade de estructura estandar | `01-lifecycle.md` |
| `Agent` / `LlmAgent` | Agente LLM con modelo, instrucciones y tools | `02-core-adk-concepts.md` |
| `BaseAgent` | Agente custom para logica determinista o eventos | `02-core-adk-concepts.md` |
| Subagentes | Agentes coordinados por otro agente o workflow | `02-core-adk-concepts.md` |
| `SequentialAgent` | Orquestacion secuencial clasica | `02-core-adk-concepts.md`, `04-workflow-2.md` |
| `ParallelAgent` | Orquestacion paralela clasica | `02-core-adk-concepts.md`, `04-workflow-2.md` |
| `LoopAgent` | Orquestacion iterativa clasica | `02-core-adk-concepts.md`, `04-workflow-2.md` |
| Workflow | Grafo ADK 2.0 con nodos, rutas y eventos | `04-workflow-2.md` |
| Node | Unidad de trabajo en Workflow | `04-workflow-2.md` |
| Route | Camino condicional en Workflow | `04-workflow-2.md` |
| `Event` | Transporte de output, state, route y message | `04-workflow-2.md` |
| HITL | Human-in-the-loop / aprobacion humana | `04-workflow-2.md`, `10-ui-protocols.md` |
| Modelo | Gemini u otro LLM configurado en agente | `02-core-adk-concepts.md` |
| Vertex AI env | `GOOGLE_GENAI_USE_VERTEXAI`, project, location | `02-core-adk-concepts.md` |
| Planner | Estrategia de razonamiento/planificacion | `02-core-adk-concepts.md`, `04-workflow-2.md` |
| `BuiltInPlanner` | Planner con thinking nativo del modelo | `02-core-adk-concepts.md` |
| `PlanReActPlanner` | Planner tipo plan/reason/act | `02-core-adk-concepts.md` |
| Thinking config | `include_thoughts`, budget, reasoning metadata | `02-core-adk-concepts.md`, `03-agent-config-yaml.md` |
| Tool | Capacidad ejecutable por el agente | `02-core-adk-concepts.md`, `05-tools-grounding-citations.md` |
| `FunctionTool` | Funcion Python expuesta al modelo | `02-core-adk-concepts.md` |
| Built-in tool | Tool incluida en ADK, como `google_search` | `05-tools-grounding-citations.md` |
| `AgentTool` | Subagente usado como tool | `03-agent-config-yaml.md`, `05-tools-grounding-citations.md` |
| Toolset | Coleccion de tools: MCP, OpenAPI, SkillToolset, retrieval | `02-core-adk-concepts.md`, `07-adk-skills.md` |
| MCP | Protocolo agente-herramientas/datos | `10-ui-protocols.md` |
| Plugin | Interceptor/transversal para runtime/tool/model behavior | `02-core-adk-concepts.md` |
| Callback | Hook antes/despues de agent/model/tool | `02-core-adk-concepts.md` |
| State | Estado compartido entre agentes/nodos | `02-core-adk-concepts.md` |
| Session | Conversacion/ejecucion persistible | `02-core-adk-concepts.md` |
| Memory | Memoria cross-session | `02-core-adk-concepts.md` |
| Artifact | Archivo/output grande o binario | `02-core-adk-concepts.md` |
| Agent Config YAML | Definicion declarativa de agentes ADK | `03-agent-config-yaml.md` |
| Code refs | Rutas Python importables desde YAML | `03-agent-config-yaml.md` |
| Output schema | Pydantic/schema para salida estructurada | `03-agent-config-yaml.md` |
| Automatic function calling | Config de llamadas automaticas a tools | `03-agent-config-yaml.md` |
| Google Search | Built-in para busqueda web y grounding | `05-tools-grounding-citations.md` |
| Vertex AI Search | Retrieval sobre corpus propio/datastore | `05-tools-grounding-citations.md` |
| Grounding metadata | Chunks/supports/search entry point | `05-tools-grounding-citations.md` |
| Citation system | IDs, source registry y links seguros | `05-tools-grounding-citations.md` |
| A2A | Protocolo agente-agente | `06-a2a-runtime.md`, `10-ui-protocols.md` |
| Agent Card | Descriptor de capacidades A2A | `06-a2a-runtime.md` |
| `RemoteA2aAgent` | Consumo de agente remoto A2A | `06-a2a-runtime.md` |
| Agent Runtime | Runtime gestionado de Google para agentes | `06-a2a-runtime.md`, `09-deploy-observability.md` |
| ADK Skill | Skill cargable por un agente ADK | `07-adk-skills.md` |
| SkillToolset | Tools para listar/cargar/ejecutar ADK Skills | `07-adk-skills.md` |
| Evalset | Casos y criterios de evaluacion de comportamiento | `08-evaluation.md` |
| LLM-as-judge | Evaluacion cualitativa con modelo juez | `08-evaluation.md` |
| Tool trajectory | Secuencia esperada de tools | `08-evaluation.md` |
| Deploy | Publicacion en Agent Runtime, Cloud Run o GKE | `09-deploy-observability.md` |
| Secrets | Gestion segura de credenciales | `09-deploy-observability.md`, `12-runbook.md` |
| Observability | Trace, logs, analytics, feedback | `09-deploy-observability.md` |
| Publish | Registro en Gemini Enterprise | `09-deploy-observability.md` |
| AG-UI | Protocolo agent-user interaction | `10-ui-protocols.md` |
| A2UI | Payload UI declarativo generado por agente | `10-ui-protocols.md` |
| Samples | Repos y ejemplos oficiales estudiados | `11-samples-and-docs.md` |
| Google ADK sample agents | Inventario completo de `google/adk-samples/python/agents` | `13-google-adk-sample-agents.md` |
| Runbook | Comandos, aprobaciones y diagnostico | `12-runbook.md` |

## Relaciones Clave

| Relacion | Idea |
|---|---|
| ADK + agents-cli | ADK implementa agentes; agents-cli organiza proyecto, eval y deploy |
| Agent Config + Python | YAML para declarativo; Python para objetos, wrappers y control avanzado |
| Classic agents + Workflow | Classic orchestration sirve para casos simples; Workflow para grafos complejos |
| Tools + Grounding | Tools recuperan datos; grounding metadata prueba fuentes y soportes |
| A2A + Agent Runtime | A2A define interoperabilidad; Agent Runtime aloja y opera agentes |
| MCP + A2A + AG-UI | MCP conecta tools, A2A conecta agentes, AG-UI conecta UI de usuario |
| AG-UI + A2UI | AG-UI transporta eventos/estado; A2UI describe componentes renderizables |
| Pytest + Eval | Pytest valida codigo determinista; eval valida comportamiento LLM |
| Skills OpenCode + ADK Skills | OpenCode skills guian al coding agent; ADK Skills son tools/conocimiento para agentes ADK |
