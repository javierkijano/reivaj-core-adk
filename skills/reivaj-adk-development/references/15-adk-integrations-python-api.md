# 15. ADK Integrations Y Python API Reference

Fuentes analizadas:

- `https://adk.dev/integrations/`
- `https://adk.dev/api-reference/python/`

Usar esta referencia antes de crear tools, toolsets, plugins, servicios de
session/memory/artifacts, observabilidad, UI o conectores custom. El objetivo es
evitar reinventar integraciones existentes y confirmar imports contra la API
Python actual.

## Lectura Ejecutiva

`adk.dev/integrations` es el catalogo oficial de integraciones prebuilt. Agrupa
capacidades por filtros como `Code`, `Connectors`, `Data`, `Google`, `MCP`,
`Observability`, `Resilience` y `Search`.

`adk.dev/api-reference/python` es el mapa autoritativo de modulos, clases y
metodos `google.adk.*`. Usarlo para confirmar nombres reales de modulos y clases
antes de copiar imports de samples o posts.

## Decision Antes De Crear Una Tool Custom

1. Buscar si existe built-in directo en `google.adk.tools`.
2. Buscar si existe toolset o conector en `adk.dev/integrations`.
3. Si es API Google/enterprise, revisar API Hub, API Registry, Google API tools o
   Application Integration.
4. Si es base de datos o SaaS, revisar MCP Toolbox, StackOne, n8n, Postman o MCP
   server especifico.
5. Si requiere busqueda/retrieval, elegir entre Google Search, Agent Search,
   Knowledge Engine, Vertex AI RAG, vector DBs o MCP Toolbox.
6. Solo crear `FunctionTool` custom si no hay integracion mantenida o si la
   logica es especifica del dominio.

## Categorias Del Catalogo De Integraciones

| Categoria | Ejemplos observados | Cuando usar |
|---|---|---|
| UI | A2UI, AG-UI | Interfaces ricas, streaming, state sync, acciones agenticas |
| Google / Cloud | Agent Registry, API Registry, Apigee API Hub, Application Integration, Agent Search, Knowledge Engine, Express Mode | Integraciones GCP, APIs empresariales, private search, prototipos cloud |
| Search / Retrieval | Google Search, Agent Search, Knowledge Engine, Chroma, Pinecone, Qdrant, GoodMem | Grounding publico, corpus privado, vector search, memoria semantica |
| Data | BigQuery Tools, Data Agents, Bigtable, Spanner, MCP Toolbox for Databases, Couchbase, MongoDB | Analitica, NL2SQL, herramientas DB, data agents conversacionales |
| Code / Environments | Code Execution, Code Execution Tool with Agent Runtime, GKE Code Executor, Daytona, Environment Toolset, Computer Use | Ejecucion de codigo, sandboxes, UI automation |
| Connectors / SaaS | Asana, Atlassian, GitHub, GitLab, Linear, Mailgun, Notion, Paypal, Postman, Stripe, ZoomInfo, StackOne, n8n | Apps SaaS, project management, pagos, emails, workflows |
| Observability | Cloud Trace, BigQuery Agent Analytics, AgentOps, Arize AX, Datadog, Freeplay, Galileo, Grafana Cloud, LangWatch, MLflow Tracing, Monocle, Phoenix, W&B Weave | Trazas, replays, metricas, evaluacion, debugging, analytics |
| Resilience / Long-running | Dapr, DBOS, Restate, Temporal | Agentes durables, reintentos, aprobaciones humanas, versionado seguro |
| Safety / Security | Cisco AI Defense, Model Armor via safety samples, guardrail integrations | Bloquear/monitorizar prompts, tool calls y riesgos |
| Marketing / Ads / GTM | Adspirer, Markifact, Supermetrics, Windsor.ai | Ads, campanas, marketing analytics, CRM/sales data |
| Voice / Messaging | AgentMail, AgentPhone, Cartesia, ElevenLabs | Email, telefono, SMS, voz, audio, transcripcion |

## Integraciones Google Especialmente Relevantes

| Integracion | Uso | Notas |
|---|---|---|
| Google Search | Busqueda web publica y grounding | Preservar grounding metadata y requisitos de display |
| Agent Search / Vertex AI Search | Busqueda privada sobre datastores configurados | Requiere datastore, permisos y region |
| Knowledge Engine / Vertex AI RAG | Retrieval privado con corpus RAG | Puede tener limitacion de combinacion de tools; validar en docs actuales |
| Google Cloud API Registry | Exponer servicios Cloud como MCP tools | Usa ADC; requiere permisos como viewer de API Registry y permisos del servicio destino |
| Apigee API Hub | Convertir APIs documentadas en tools | Bueno para APIs enterprise gobernadas |
| Application Integration | Conectores enterprise y workflows SaaS | Util para ServiceNow, ordenes, procesos de negocio |
| Data Agents | Toolset para Data Agents conversacionales | BigQuery/Looker/Looker Studio; incluye `list_accessible_data_agents`, `get_data_agent_info`, `ask_data_agent` |
| BigQuery Agent Analytics | Analitica de comportamiento y logging | Revisar privacidad antes de activar logs de prompts/respuestas |
| Cloud Trace | Trazas de ejecucion y latencia | Complementar con skill de observabilidad |
| Express Mode | Prototipo con servicios Vertex AI sin proyecto completo | No sustituye estrategia prod; revisar auth y limites |

## Mapa De API Python Por Area

La API reference lista modulos y clases principales. Usar esta tabla como mapa
de busqueda rapida, no como sustituto de leer la pagina concreta.

| Area | Modulos/clases observadas | Uso |
|---|---|---|
| Agentes | `google.adk.agents`, `Agent`, `LlmAgent`, `BaseAgent`, `SequentialAgent`, `ParallelAgent`, `LoopAgent` | Definir agentes y orquestacion clasica |
| Contexto runtime | `Context`, `InvocationContext`, `RunConfig`, `LiveRequest`, `LiveRequestQueue` | Estado, artifacts, auth, HITL, streaming, limites de llamadas |
| Eventos | `google.adk.events`, `Event`, `EventActions` | Function calls/responses, state delta, transfer, escalation, UI widgets |
| Herramientas base | `BaseTool`, `BaseToolset`, `FunctionTool`, `ToolContext`, `LongRunningFunctionTool` | Crear y envolver tools |
| Toolsets/integraciones | `AgentTool`, `McpToolset`, `OpenAPIToolset`, `ToolboxToolset`, `ApiHubToolset`, `ApplicationIntegrationToolset`, `GoogleApiTool`, `VertexAiSearchTool` | Conectar agentes, MCP, OpenAPI, DB toolbox, APIs y search |
| Built-ins utiles | `google_search`, `load_web_page`, `load_artifacts_tool`, `load_memory_tool`, `preload_memory_tool`, `url_context_tool`, `exit_loop_tool`, `transfer_to_agent_tool`, `get_user_choice_tool` | Capacidades listas para usar |
| Auth | `google.adk.auth`, authenticated tools, credential helpers in `Context` | OAuth/API auth y credenciales por tool |
| Sessions | `BaseSessionService`, `InMemorySessionService`, `DatabaseSessionService`, `VertexAiSessionService`, `Session` | Persistencia de conversaciones y state |
| Memory | `BaseMemoryService`, `InMemoryMemoryService`, `VertexAiMemoryBankService`, `VertexAiRagMemoryService` | Memoria cross-session y recall |
| Artifacts | `BaseArtifactService`, `InMemoryArtifactService`, `FileArtifactService`, `GcsArtifactService` | Archivos y outputs grandes |
| Code execution | `BaseCodeExecutor`, `BuiltInCodeExecutor`, `UnsafeLocalCodeExecutor`, `CodeExecutorContext` | Ejecucion de codigo y manejo de resultados |
| Models | `BaseLlm`, `Gemini`, `LiteLlm`, `Claude`, `Gemma`, `LLMRegistry` | Modelos y proveedores |
| Planners | `BasePlanner`, `BuiltInPlanner`, `PlanReActPlanner` | Thinking/planning explicito |
| Plugins | `BasePlugin`, `PluginManager`, `LoggingPlugin`, `DebugLoggingPlugin`, `ReflectAndRetryToolPlugin` | Observabilidad, debug, retry, politicas transversales |
| Evaluation | `AgentEvaluator` | Evaluar agentes y evalsets |
| Apps/Runners | `App`, `ResumabilityConfig`, `Runner`, `InMemoryRunner` | Empaquetado, ejecucion y resumability |
| A2A/platform | `google.adk.a2a`, `google.adk.platform` | Interoperabilidad y runtime/platform APIs |

## Reglas De Import Y Verificacion

- No inferir imports desde nombres del catalogo; confirmar en la API Python.
- Algunos built-ins tienen imports especificos, por ejemplo
  `from google.adk.tools.load_web_page import load_web_page`.
- Confirmar si una integracion es tool, toolset, plugin, service o deployment
  asset antes de cablearla en `tools=[...]`.
- Verificar si requiere ADC, API key, OAuth, service account, IAM, region,
  datastore, corpus, MCP server o endpoint externo.
- Si una integracion ejecuta codigo, opera UI, llama APIs externas o modifica
  recursos cloud, pedir aprobacion antes de probar con credenciales reales.

## Riesgos Y Puertas De Aprobacion

Pedir confirmacion antes de:

- Habilitar o configurar integraciones que crean/modifican recursos cloud.
- Ejecutar conectores de pagos, email, telefono, SMS, ads, GitHub/GitLab writes,
  ServiceNow, Application Integration o workflows SaaS.
- Activar code execution, computer use, GKE Code Executor, Daytona o sandboxes
  que ejecuten codigo generado.
- Habilitar observabilidad que capture prompts, respuestas, state o PII.
- Conectar vector DBs, memory services o retrieval sobre datos privados.

## Como Integrar Con La Registry Interna

Cuando se anada una integracion al `registry/`:

- Usar tags `integration:*`, `capability:*`, `entity:tool` o `entity:plugin`.
- Guardar URL oficial y modulo/clase Python si aplica.
- Registrar auth, permisos, variables y side effects.
- Marcar madurez como `maturity:observed` hasta que haya prueba local segura.
- Enlazar samples ADK que demuestren esa integracion cuando existan.
