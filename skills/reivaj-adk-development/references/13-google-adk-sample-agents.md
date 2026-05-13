# 13. Google ADK Sample Agents

Fuente oficial:

- `https://github.com/google/adk-samples/tree/main/python/agents`
- README indice: `https://raw.githubusercontent.com/google/adk-samples/main/python/agents/README.md`

Esta referencia integra el inventario de agentes de ejemplo oficiales de Google
ADK en `python/agents`. Usarla antes de disenar una arquitectura nueva: casi
siempre hay un sample que ya demuestra una parte del patron.

## Como Usar Esta Referencia

1. Buscar primero por patron o vertical en la matriz de seleccion.
2. Abrir el README del sample concreto.
3. Leer `agent.py`, `prompt.py`, `tools/`, `sub_agents/`, `eval/`, `tests/` y
   `deployment/` si existen.
4. Reutilizar el patron, no copiar ciegamente el codigo.
5. Adaptar dependencias, auth, region, modelos, permisos y evals al proyecto.

## Estructura Tipica De Un Sample

La estructura oficial documentada por Google suele ser:

```text
agent-name/
  agent_name/
    shared_libraries/
    sub_agents/
      <sub_agent>/
        tools/
        agent.py
        prompt.py
    tools/
    __init__.py
    agent.py
    prompt.py
  deployment/
  eval/
  tests/
  agent_pattern.png
  .env.example
  pyproject.toml
  README.md
```

Regla practica: el directorio externo suele usar guiones y el paquete Python
interno suele usar guiones bajos.

## Matriz Rapida De Seleccion

| Necesidad | Samples recomendados |
|---|---|
| Primer agente simple | `fun-facts`, `currency-agent`, `story_teller` |
| Multi-agent conversacional | `travel-concierge`, `data-science`, `customer-service` |
| Workflow secuencial | `workflows-sequential`, `podcast_transcript_agent`, `google-trends-agent` |
| Workflow HITL | `workflows-HITL_concierge`, `order-processing`, `deep-search` |
| Workflow paralelo / fan-out | `workflow-concurrent_research_writer`, `parallel_task_decomposition_execution` |
| Research con web y citaciones | `deep-search`, `academic-research`, `llm-auditor`, `fomc-research` |
| Auditoria/fact-checking | `llm-auditor`, `ai-security-agent`, `safety-plugins` |
| RAG/documentos | `RAG`, `multiformat-hybrid-rag`, `high-volume-document-analyzer`, `invoice-processing` |
| Data/BigQuery | `data-science`, `data-engineering`, `agent-observability-bq`, `google-trends-agent` |
| Data pipelines | `plumber-data-engineering-assistant`, `airflow_version_upgrade_agent`, `data-engineering` |
| ML engineering / benchmarks | `machine-learning-engineering`, `swe-benchmark-agent`, `tau2-benchmark-agent` |
| OAuth / user consent | `adk-ae-oauth` |
| Observabilidad | `agent-observability-bq`, `safety-plugins` |
| Agent Runtime / produccion | `adk-ae-oauth`, `ambient-expense-agent`, `genmedia-for-commerce`, `memory-bank` |
| A2A + MCP | `currency-agent` |
| MCP tools | `currency-agent`, `antom-payment`, `gemma-food-tour-guide`, `genmedia-for-commerce` |
| Application Integration connectors | `incident-management`, `order-processing` |
| Apigee / API hub | `auto-insurance-agent` |
| Memory Bank | `memory-bank` |
| ADK Skills / SkillToolset | `agent-skills-tutorial`; ver `14-agent-skills-tutorial-analysis.md` |
| Safety plugins / guardrails | `safety-plugins`, `camel`, `ai-security-agent`, `cyber-guardian-agent` |
| Realtime / streaming / multimodal | `bidi-demo`, `realtime-conversational-agent`, `customer-service` |
| Genmedia / Imagen / video | `genmedia-for-commerce`, `on-brand-genmedia`, `image-scoring`, `short-movie-agents` |
| Brand/marketing generation | `marketing-agency`, `brand-aligner`, `brand-aligned-presentations`, `product-catalog-ad-generation` |
| Healthcare workflows | `medical-pre-authorization`, `claim-adjudication-agent`, `nurse-handover` |
| Finance / insurance / payments | `financial-advisor`, `auto-insurance-agent`, `small-business-loan-agent`, `antom-payment` |
| Supply chain / operations | `supply-chain`, `hierarchical-workflow-automation`, `nexshift-agent` |
| Geospatial / maps / location | `earth-engine-geospatial`, `retail-ai-location-strategy`, `gemma-food-tour-guide` |
| Software development lifecycle | `software-bug-assistant`, `sdlc-user-story-refiner`, `sdlc-task-planner`, `sdlc-technical-designer` |

## Inventario Completo Por Categoria

### Fundamentos Y Agentes Pequenos

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`fun-facts`](https://github.com/google/adk-samples/tree/main/python/agents/fun-facts) | Agente ADK minimo y deployment basico | Primer contacto, estructura simple, despliegue sencillo |
| [`currency-agent`](https://github.com/google/adk-samples/tree/main/python/agents/currency-agent) | A2A + ADK + MCP para tipos de cambio | Integrar A2A, MCP y herramienta externa simple |
| [`story_teller`](https://github.com/google/adk-samples/tree/main/python/agents/story_teller) | Multi-agent colaborativo para escritura de historias | Ejemplo pequeno de colaboracion entre agentes |

### Skills, Memoria Y Extensibilidad

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`agent-skills-tutorial`](https://github.com/google/adk-samples/tree/main/python/agents/agent-skills-tutorial) | Inline, file-based, external y meta skills | ADK SkillToolset, L1/L2/L3 progressive disclosure y skill factory |
| [`memory-bank`](https://github.com/google/adk-samples/tree/main/python/agents/memory-bank) | Memory Bank integration | Preferencias/hechos cross-session y variantes de deployment |

### Workflow Y Orquestacion

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`workflows-sequential`](https://github.com/google/adk-samples/tree/main/python/agents/workflows-sequential) | Workflow secuencial simple | Migrar o disenar pipeline lineal en Workflow |
| [`workflows-HITL_concierge`](https://github.com/google/adk-samples/tree/main/python/agents/workflows-HITL_concierge) | Workflow con human-in-the-loop | Pausas, aprobaciones o input humano en flujo |
| [`workflow-concurrent_research_writer`](https://github.com/google/adk-samples/tree/main/python/agents/workflow-concurrent_research_writer) | Research + escritura + publicacion con concurrencia | Fan-out/fan-in, research paralelo, blog writing |
| [`workflow-morning_email_debrief`](https://github.com/google/adk-samples/tree/main/python/agents/workflow-morning_email_debrief) | Workflow disparado por horario | Agentes timed/scheduled y debrief diario |
| [`parallel_task_decomposition_execution`](https://github.com/google/adk-samples/tree/main/python/agents/parallel_task_decomposition_execution) | Descomposicion y ejecucion paralela | Dividir objetivo complejo en subacciones concurrentes |
| [`hierarchical-workflow-automation`](https://github.com/google/adk-samples/tree/main/python/agents/hierarchical-workflow-automation) | Automatizacion jerarquica multi-sistema | Workflows estructurados con ordenes, BigQuery y Agent Tool |
| [`podcast_transcript_agent`](https://github.com/google/adk-samples/tree/main/python/agents/podcast_transcript_agent) | Sequential agent con subagentes | Generar transcripts por etapas |
| [`google-trends-agent`](https://github.com/google/adk-samples/tree/main/python/agents/google-trends-agent) | Sequential agent + BigQuery trends | Tendencias por region/tiempo y analitica marketing |

### Research, Escritura Y Analisis

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`deep-search`](https://github.com/google/adk-samples/tree/main/python/agents/deep-search) | Research fullstack, web search, modular agents, HITL | Research profundo, citas, frontend React/FastAPI |
| [`gemini-fullstack`](https://github.com/google/adk-samples/tree/main/python/agents/gemini-fullstack) | Renombrado a Deep Search | Compatibilidad historica; usar `deep-search` |
| [`academic-research`](https://github.com/google/adk-samples/tree/main/python/agents/academic-research) | Multi-agent para publicaciones y areas emergentes | Research academico, evaluacion, custom tools |
| [`llm-auditor`](https://github.com/google/adk-samples/tree/main/python/agents/llm-auditor) | Fact-checking, critic/reviser, Google Search | Auditoria de respuestas LLM y grounding |
| [`fomc-research`](https://github.com/google/adk-samples/tree/main/python/agents/fomc-research) | Research FOMC multimodal y reportes | Analisis de eventos de mercado y reporting avanzado |
| [`economic-research-agent`](https://github.com/google/adk-samples/tree/main/python/agents/economic-research-agent) | Inteligencia economica regional multi-agent | Labor market, site selection, analisis economico |
| [`financial-advisor`](https://github.com/google/adk-samples/tree/main/python/agents/financial-advisor) | Equipo de agentes para asesores financieros | Riesgo, estrategia, resumen y report generation |
| [`blog-writer`](https://github.com/google/adk-samples/tree/main/python/agents/blog-writer) | Multi-agent para blogs tecnicos | Escritura asistida, ideacion, drafting y revision |
| [`marketing-agency`](https://github.com/google/adk-samples/tree/main/python/agents/marketing-agency) | Agencia creativa multi-agent | Websites, dominios, estrategias y brand assets |
| [`youtube-analyst`](https://github.com/google/adk-samples/tree/main/python/agents/youtube-analyst) | Multi-agent + YouTube API + charts | Analitica de contenido/canales con graficos interactivos |
| [`brand-search-optimization`](https://github.com/google/adk-samples/tree/main/python/agents/brand-search-optimization) | Search result comparison + BigQuery | Optimizacion de titulos/product data para retail search |

### RAG, Documentos Y Extraccion

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`RAG`](https://github.com/google/adk-samples/tree/main/python/agents/RAG) | Vertex AI RAG Engine con citaciones | Q&A sobre documentos subidos a Vertex AI RAG Engine |
| [`multiformat-hybrid-rag`](https://github.com/google/adk-samples/tree/main/python/agents/multiformat-hybrid-rag) | RAG productivo GCS + Vector Search 2.0 | Ingestion multi-formato, chunking, hybrid search |
| [`high-volume-document-analyzer`](https://github.com/google/adk-samples/tree/main/python/agents/high-volume-document-analyzer) | Analisis masivo de documentos | Colecciones grandes no estructuradas en enterprise |
| [`invoice-processing`](https://github.com/google/adk-samples/tree/main/python/agents/invoice-processing) | Procesamiento documental + aprendizaje interactivo | Inference pipeline para facturas/documentos |
| [`medical-pre-authorization`](https://github.com/google/adk-samples/tree/main/python/agents/medical-pre-authorization) | Analisis de registros y polizas medicas | Cobertura, elegibilidad y report generation sanitario |
| [`claim-adjudication-agent`](https://github.com/google/adk-samples/tree/main/python/agents/claim-adjudication-agent) | Workflow multi-agent de claims | Procesamiento/adjudicacion de seguros de salud |
| [`policy-as-code`](https://github.com/google/adk-samples/tree/main/python/agents/policy-as-code) | Data governance con lenguaje natural | Definir, validar y aplicar politicas de datos |
| [`podcast_transcript_agent`](https://github.com/google/adk-samples/tree/main/python/agents/podcast_transcript_agent) | Documento de entrada a transcript secuencial | Transformacion estructurada por fases |

### Data, ML, Analytics Y Software Engineering

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`data-science`](https://github.com/google/adk-samples/tree/main/python/agents/data-science) | Multi-agent data analysis, NL2SQL, Python tools | Analisis sofisticado, SQL, DB, Agent Tool |
| [`data-engineering`](https://github.com/google/adk-samples/tree/main/python/agents/data-engineering) | BigQuery/Dataform/ELT pipelines | Data engineering conversacional avanzado |
| [`plumber-data-engineering-assistant`](https://github.com/google/adk-samples/tree/main/python/agents/plumber-data-engineering-assistant) | Dataflow, Dataproc, dbt, GCP data stack | Crear y desplegar pipelines big data |
| [`airflow_version_upgrade_agent`](https://github.com/google/adk-samples/tree/main/python/agents/airflow_version_upgrade_agent) | Migracion agentica de DAGs Airflow | Upgrade de versiones Airflow y refactor automatizado |
| [`machine-learning-engineering`](https://github.com/google/adk-samples/tree/main/python/agents/machine-learning-engineering) | MLE-STAR multi-agent | Entrenar modelos ML en tareas variadas |
| [`software-bug-assistant`](https://github.com/google/adk-samples/tree/main/python/agents/software-bug-assistant) | RAG + MCP + bug tracking + web search | Triage y resolucion de bugs con fuentes internas/externas |
| [`swe-benchmark-agent`](https://github.com/google/adk-samples/tree/main/python/agents/swe-benchmark-agent) | SWE-bench / TerminalBench principles | Agentes para problemas de software engineering benchmarks |
| [`tau2-benchmark-agent`](https://github.com/google/adk-samples/tree/main/python/agents/tau2-benchmark-agent) | Tau2-Bench integration | Evaluacion de agentes contra framework tau2-bench |
| [`sdlc-user-story-refiner`](https://github.com/google/adk-samples/tree/main/python/agents/sdlc-user-story-refiner) | Refinamiento de user stories | Parte de workflow SDLC multi-agent |
| [`sdlc-task-planner`](https://github.com/google/adk-samples/tree/main/python/agents/sdlc-task-planner) | Planificacion de tareas SDLC | Breakdown de trabajo dentro de SDLC |
| [`sdlc-technical-designer`](https://github.com/google/adk-samples/tree/main/python/agents/sdlc-technical-designer) | Diseno tecnico SDLC | Arquitectura/technical design en cadena SDLC |
| [`agent-observability-bq`](https://github.com/google/adk-samples/tree/main/python/agents/agent-observability-bq) | BigQuery agent + analytics plugin | Observabilidad y logging de agentes con BigQuery |

### Business Process, Customer Ops Y Verticales

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`customer-service`](https://github.com/google/adk-samples/tree/main/python/agents/customer-service) | Retail customer service, async tools, live streaming | Servicio cliente con sistemas externos y multimodalidad |
| [`travel-concierge`](https://github.com/google/adk-samples/tree/main/python/agents/travel-concierge) | Multi-agent travel assistant | Dynamic instructions, schemas, updatable context |
| [`personalized-shopping`](https://github.com/google/adk-samples/tree/main/python/agents/personalized-shopping) | Product recommendation agent | E-commerce, discovery y personalization |
| [`auto-insurance-agent`](https://github.com/google/adk-samples/tree/main/python/agents/auto-insurance-agent) | Apigee API hub + insurance operations | Miembros, claims, rewards, roadside assistance |
| [`small-business-loan-agent`](https://github.com/google/adk-samples/tree/main/python/agents/small-business-loan-agent) | Loan processing multi-agent | Automatizar prestamos para banca pequena empresa |
| [`antom-payment`](https://github.com/google/adk-samples/tree/main/python/agents/antom-payment) | Antom payment MCP | Pagos, refunds y APIs externas via MCP |
| [`incident-management`](https://github.com/google/adk-samples/tree/main/python/agents/incident-management) | ServiceNow + Application Integration connectors | Dynamic identity propagation y incident ops |
| [`order-processing`](https://github.com/google/adk-samples/tree/main/python/agents/order-processing) | Application Integration + HITL | Automatizar ordenes con aprobacion humana |
| [`supply-chain`](https://github.com/google/adk-samples/tree/main/python/agents/supply-chain) | Market/weather/ops/demand optimization | Supply chain de power & energy con BigQuery/Search |
| [`hierarchical-workflow-automation`](https://github.com/google/adk-samples/tree/main/python/agents/hierarchical-workflow-automation) | Cookie delivery order system | Customer ops, scheduling y comunicaciones |
| [`nexshift-agent`](https://github.com/google/adk-samples/tree/main/python/agents/nexshift-agent) | Nurse rostering multi-agent | Generar, validar y gestionar turnos de enfermeria |
| [`nurse-handover`](https://github.com/google/adk-samples/tree/main/python/agents/nurse-handover) | Clinical handover summarization | Procesar detalles clinicos para cambio de turno |
| [`global-kyc-agent`](https://github.com/google/adk-samples/tree/main/python/agents/global-kyc-agent) | KYC/compliance UK/US | Compliance queries multi-jurisdiccion |
| [`retail-ai-location-strategy`](https://github.com/google/adk-samples/tree/main/python/agents/retail-ai-location-strategy) | Retail site selection pipeline | Location strategy, geospatial/retail analysis |

### Media, Multimodalidad, Brand Y Generative Media

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`genmedia-for-commerce`](https://github.com/google/adk-samples/tree/main/python/agents/genmedia-for-commerce) | Full-stack commerce media generation | VTO, video, 360-degree spin, MCP, React, Terraform |
| [`on-brand-genmedia`](https://github.com/google/adk-samples/tree/main/python/agents/on-brand-genmedia) | Imagen generation + policy scoring | Generar/evaluar imagenes con politicas de marca |
| [`image-scoring`](https://github.com/google/adk-samples/tree/main/python/agents/image-scoring) | Imagen + Loop Agent + policy compliance | Scoring automatico de imagenes generadas |
| [`short-movie-agents`](https://github.com/google/adk-samples/tree/main/python/agents/short-movie-agents) | End-to-end video agents | Construccion de videos desde intencion de usuario |
| [`product-catalog-ad-generation`](https://github.com/google/adk-samples/tree/main/python/agents/product-catalog-ad-generation) | Ads grounded in product catalog | Generacion de anuncios cortos desde catalogo |
| [`brand-aligner`](https://github.com/google/adk-samples/tree/main/python/agents/brand-aligner) | Evaluacion de assets visuales | Comprobar imagen/video contra brand guidelines |
| [`brand-aligned-presentations`](https://github.com/google/adk-samples/tree/main/python/agents/brand-aligned-presentations) | Presentaciones PowerPoint on-brand | Automatizar decks adherentes a marca |
| [`gemma-food-tour-guide`](https://github.com/google/adk-samples/tree/main/python/agents/gemma-food-tour-guide) | Gemma + Google Maps MCP + multimodal | Food tours desde imagen/texto, ubicacion y presupuesto |
| [`bidi-demo`](https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo) | Gemini Live API + WebSocket streaming | Realtime bidirectional streaming con FastAPI |
| [`realtime-conversational-agent`](https://github.com/google/adk-samples/tree/main/python/agents/realtime-conversational-agent) | Full-stack realtime multimodal template | Agentes conversacionales realtime reutilizables |

### Seguridad, Compliance Y Guardrails

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`safety-plugins`](https://github.com/google/adk-samples/tree/main/python/agents/safety-plugins) | Plugins de safety agent-agnostic | Gemini judge, Model Armor, jailbreak filters |
| [`ai-security-agent`](https://github.com/google/adk-samples/tree/main/python/agents/ai-security-agent) | Red team testing framework | AI safety testing y vulnerability assessment |
| [`cyber-guardian-agent`](https://github.com/google/adk-samples/tree/main/python/agents/cyber-guardian-agent) | Cyber incident triage/investigation | Hierarchical multi-agent cybersecurity operations |
| [`camel`](https://github.com/google/adk-samples/tree/main/python/agents/camel) | CaMeL secure agent demo | Control de data flow y seguridad para LLM agents |
| [`global-kyc-agent`](https://github.com/google/adk-samples/tree/main/python/agents/global-kyc-agent) | KYC/compliance | Compliance conversacional por jurisdiccion |
| [`policy-as-code`](https://github.com/google/adk-samples/tree/main/python/agents/policy-as-code) | Governance as policy | Validacion y enforcement de politicas de datos |

### Deployment, Runtime, Auth, Observability Y Ambient Agents

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`adk-ae-oauth`](https://github.com/google/adk-samples/tree/main/python/agents/adk-ae-oauth) | Agent Runtime + OAuth 2.0 + Google Drive | User consent y auth delegada en produccion |
| [`ambient-expense-agent`](https://github.com/google/adk-samples/tree/main/python/agents/ambient-expense-agent) | Ambient scheduled/event-driven expense processing | Agentes no interactivos con eventos/schedule |
| [`agent-observability-bq`](https://github.com/google/adk-samples/tree/main/python/agents/agent-observability-bq) | BigQueryAgentAnalyticsPlugin | Observabilidad y logging estructurado |
| [`memory-bank`](https://github.com/google/adk-samples/tree/main/python/agents/memory-bank) | Memory Bank integration | Preferencias/hechos cross-session y deployment variants |
| [`genmedia-for-commerce`](https://github.com/google/adk-samples/tree/main/python/agents/genmedia-for-commerce) | Full-stack + Agent Runtime + Terraform | Deployment de app completa con frontend/backend/MCP |

### Geospatial, Local Discovery Y Location Strategy

| Sample | Patron principal | Cuando leerlo |
|---|---|---|
| [`earth-engine-geospatial`](https://github.com/google/adk-samples/tree/main/python/agents/earth-engine-geospatial) | Google Earth Engine | Analisis geospatial y datos ambientales |
| [`retail-ai-location-strategy`](https://github.com/google/adk-samples/tree/main/python/agents/retail-ai-location-strategy) | Retail location strategy | Site selection y analisis comercial/geografico |
| [`gemma-food-tour-guide`](https://github.com/google/adk-samples/tree/main/python/agents/gemma-food-tour-guide) | Google Maps MCP route planning | Tours culinarios personalizados y local discovery |

## Inventario Alfabetico Completo

El directorio oficial contenia estos 73 samples al consultar `main`:

```text
RAG
academic-research
adk-ae-oauth
agent-observability-bq
agent-skills-tutorial
ai-security-agent
airflow_version_upgrade_agent
ambient-expense-agent
antom-payment
auto-insurance-agent
bidi-demo
blog-writer
brand-aligned-presentations
brand-aligner
brand-search-optimization
camel
claim-adjudication-agent
currency-agent
customer-service
cyber-guardian-agent
data-engineering
data-science
deep-search
earth-engine-geospatial
economic-research-agent
financial-advisor
fomc-research
fun-facts
gemini-fullstack
gemma-food-tour-guide
genmedia-for-commerce
global-kyc-agent
google-trends-agent
hierarchical-workflow-automation
high-volume-document-analyzer
image-scoring
incident-management
invoice-processing
llm-auditor
machine-learning-engineering
marketing-agency
medical-pre-authorization
memory-bank
multiformat-hybrid-rag
nexshift-agent
nurse-handover
on-brand-genmedia
order-processing
parallel_task_decomposition_execution
personalized-shopping
plumber-data-engineering-assistant
podcast_transcript_agent
policy-as-code
product-catalog-ad-generation
realtime-conversational-agent
retail-ai-location-strategy
safety-plugins
sdlc-task-planner
sdlc-technical-designer
sdlc-user-story-refiner
short-movie-agents
small-business-loan-agent
software-bug-assistant
story_teller
supply-chain
swe-benchmark-agent
tau2-benchmark-agent
travel-concierge
workflow-concurrent_research_writer
workflow-morning_email_debrief
workflows-HITL_concierge
workflows-sequential
youtube-analyst
```

## Samples En README Oficial Curado

El README oficial de `python/agents` incluye una tabla curada con campos de use
case, tags, interaction type, complexity, agent type y vertical. Los samples con
entrada curada son especialmente buenos como primera referencia:

```text
agent-skills-tutorial
academic-research
brand-search-optimization
customer-service
currency-agent
data-engineering
data-science
financial-advisor
fomc-research
deep-search
gemma-food-tour-guide
llm-auditor
marketing-agency
medical-pre-authorization
personalized-shopping
RAG
safety-plugins
short-movie-agents
software-bug-assistant
supply-chain
travel-concierge
youtube-analyst
auto-insurance-agent
image-scoring
antom-payment
incident-management
order-processing
google-trends-agent
hierarchical-workflow-automation
plumber-data-engineering-assistant
genmedia-for-commerce
```

## Samples Adicionales No Curados En Esa Tabla

Estos existen como directorios con README propio o contenido especifico, aunque
no aparecian en la tabla curada del README principal al momento de consulta:

```text
adk-ae-oauth
agent-observability-bq
ai-security-agent
airflow_version_upgrade_agent
ambient-expense-agent
bidi-demo
blog-writer
brand-aligned-presentations
brand-aligner
camel
claim-adjudication-agent
cyber-guardian-agent
earth-engine-geospatial
economic-research-agent
fun-facts
gemini-fullstack
global-kyc-agent
high-volume-document-analyzer
invoice-processing
machine-learning-engineering
memory-bank
multiformat-hybrid-rag
nexshift-agent
nurse-handover
on-brand-genmedia
parallel_task_decomposition_execution
podcast_transcript_agent
policy-as-code
product-catalog-ad-generation
realtime-conversational-agent
retail-ai-location-strategy
sdlc-task-planner
sdlc-technical-designer
sdlc-user-story-refiner
small-business-loan-agent
story_teller
swe-benchmark-agent
tau2-benchmark-agent
workflow-concurrent_research_writer
workflow-morning_email_debrief
workflows-HITL_concierge
workflows-sequential
```

## Que Leer Dentro De Cada Sample

| Objetivo | Archivos |
|---|---|
| Entender proposito | `README.md`, `agent_pattern.png` |
| Entender agente principal | `<package>/agent.py`, `<package>/prompt.py` |
| Entender multi-agent | `<package>/sub_agents/**/agent.py`, prompts y tools |
| Entender tools | `<package>/tools/**`, `shared_libraries/**` |
| Entender estado/schema | `agent.py`, `prompt.py`, modelos Pydantic, eval data |
| Entender eval | `eval/**`, `tests/**` |
| Entender deployment | `deployment/**`, `.env.example`, `pyproject.toml` |
| Entender auth | `.env.example`, README prerequisites, deployment scripts |

## Reglas De Reuso

- Reusar patrones, no copiar configuracion cloud ni secretos.
- Verificar version ADK del sample; algunos pueden usar Poetry o versiones ADK
  distintas del proyecto destino.
- Adaptar estructura a `agents-cli` si el proyecto destino lo usa.
- No cambiar modelos existentes solo porque el sample use otro.
- Si el sample usa servicios cloud, confirmar APIs, IAM, region y coste antes
  de ejecutar.
- Si el sample incluye evals, portarlas como comportamiento esperado, no como
  tests pytest de texto LLM.
