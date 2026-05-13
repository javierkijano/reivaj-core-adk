---
name: reivaj-adk-development
description: >
  Skill completa para desarrollar agentes con Google ADK y agents-cli. Cubre
  ciclo de vida, Agent Config YAML, agentes, herramientas, callbacks, estado,
  artefactos, grounding, citaciones, evaluacion, despliegue, A2A, ADK Skills,
  ADK 2.0 Workflow, observabilidad, AG-UI, A2UI, patrones de muestras y
  referencias oficiales. Usar antes de disenar, implementar, depurar, evaluar,
  desplegar o integrar agentes ADK.
metadata:
  author: Reivaj / OpenCode
  license: Internal
  version: 1.0.0
  requires:
    bins:
      - uv
      - agents-cli
---

# Reivaj ADK Development

Esta skill es una guia general y completa para desarrollo con Google ADK. No es
una memoria de una app concreta. Cuando una tarea requiera contexto de un
proyecto especifico, leer primero los archivos del proyecto y mantener esa
arquitectura en una referencia separada.

## Uso Correcto

Usar esta skill cuando haya que:

- Crear o mejorar un proyecto ADK.
- Definir agentes, subagentes, workflows, herramientas, callbacks o plugins.
- Trabajar con Agent Config YAML o migrar entre YAML y Python code-first.
- Implementar grounding, busqueda, citaciones o retrieval.
- Exponer o consumir agentes con A2A.
- Incorporar ADK Skills / SkillToolset.
- Evaluar, desplegar, publicar u observar agentes.
- Valorar integraciones con AG-UI o A2UI.
- Consultar referencias, muestras o decisiones tecnicas ya investigadas.

## Relacion Con Skills Oficiales

Esta skill agrega y organiza conocimiento. Antes de ejecutar una fase, cargar la
skill oficial correspondiente si esta disponible:

| Fase | Skill oficial |
|---|---|
| Ciclo de vida completo | `google-agents-cli-workflow` |
| Codigo ADK, agentes, herramientas, callbacks, estado | `google-agents-cli-adk-code` |
| Scaffolding, upgrade, enhancement | `google-agents-cli-scaffold` |
| Evaluacion | `google-agents-cli-eval` |
| Despliegue e infraestructura | `google-agents-cli-deploy` |
| Publicacion en Gemini Enterprise | `google-agents-cli-publish` |
| Observabilidad | `google-agents-cli-observability` |

## Principios No Negociables

- No modificar modelos existentes salvo peticion explicita.
- No eliminar ni cambiar `.env`, defaults de Vertex AI o configuracion de auth
  salvo peticion explicita.
- No imprimir tokens, credenciales, secretos ni salidas que los contengan.
- No ejecutar comandos cloud-changing sin aprobacion explicita.
- No desplegar, provisionar infraestructura, publicar ni ejecutar evals con
  credenciales reales sin aprobacion explicita.
- No usar pytest para validar contenido LLM no determinista; usar evals.
- Preferir cambios minimos, verificables y con contratos claros de estado.
- Preservar arquitectura del proyecto concreto; esta skill no sustituye la
  lectura de codigo.
- Tratar ADK 2.0 Workflow y Agent Config como superficies experimentales/beta
  cuando aplique.

## Mapa Conceptual

| Area | Que cubre | Referencia |
|---|---|---|
| Indice conceptual | Taxonomia completa de conceptos ADK y relaciones | `references/00-concept-index.md` |
| Ciclo de vida | entender, scaffold, construir, evaluar, desplegar, publicar, observar | `references/01-lifecycle.md` |
| Fundamentos ADK | agentes, modelos, herramientas, estado, sesiones, artefactos, callbacks | `references/02-core-adk-concepts.md` |
| Agent Config YAML | schema, refs, limitaciones, patrones seguros, YAML vs Python | `references/03-agent-config-yaml.md` |
| ADK 2.0 Workflow | grafo, nodos, rutas, eventos, HITL, paralelismo, migracion | `references/04-workflow-2.md` |
| Herramientas y grounding | built-ins, Google Search, Vertex AI Search, metadata, citaciones | `references/05-tools-grounding-citations.md` |
| A2A y runtime | Agent Card, executor, RemoteA2aAgent, Agent Runtime, extensiones | `references/06-a2a-runtime.md` |
| ADK Skills | SkillToolset, recursos, scripts, progressive disclosure, patrones inline/file/external/meta | `references/07-adk-skills.md`, `references/14-agent-skills-tutorial-analysis.md` |
| Evaluacion | evalsets, criterios, tool trajectory, pytest vs eval, bucle eval-fix | `references/08-evaluation.md` |
| Deploy y observabilidad | Agent Runtime, Cloud Run, GKE, secrets, tracing, logs, analytics | `references/09-deploy-observability.md` |
| UI protocols | AG-UI, A2UI, relacion con MCP y A2A | `references/10-ui-protocols.md` |
| Muestras y docs | samples estudiados, docs oficiales, referencias locales | `references/11-samples-and-docs.md` |
| Runbook | comandos, aprobaciones, diagnostico, checklist | `references/12-runbook.md` |
| Google ADK samples | inventario completo y seleccion de `google/adk-samples/python/agents` | `references/13-google-adk-sample-agents.md` |
| Agent Skills tutorial | analisis profundo de `agent-skills-tutorial` y como reutilizar sus patrones | `references/14-agent-skills-tutorial-analysis.md` |
| Integraciones y API Python | catalogo `adk.dev/integrations`, mapa de modulos `google.adk.*`, decision tool/integration | `references/15-adk-integrations-python-api.md` |

## Flujo De Trabajo Recomendado

1. Entender objetivo, restricciones, herramientas externas y destino de despliegue.
2. Leer `DESIGN_SPEC.md` si existe; si no existe y el trabajo es grande, pedir
   datos minimos antes de implementar.
3. Comprobar si el proyecto ya esta en formato agents-cli con `agents-cli info`.
4. Estudiar muestras relevantes antes de inventar arquitectura nueva.
5. Elegir entre Agent Config YAML, Python code-first o ADK 2.0 Workflow segun
   necesidades y estabilidad requerida.
6. Implementar con cambios pequenos y contratos explicitos de estado/output.
7. Verificar imports, lint y tests deterministas.
8. Evaluar comportamiento con `agents-cli eval run` solo con aprobacion.
9. Desplegar/publicar/observar solo con aprobacion y skill oficial correspondiente.

## Decision Rapida

| Necesidad | Opcion recomendada |
|---|---|
| Prototipo o agente sencillo | `LlmAgent` code-first o YAML simple |
| Proyecto nuevo con convenciones completas | `agents-cli scaffold create` |
| Proyecto existente que necesita estructura agents-cli | `agents-cli scaffold enhance .` |
| Orquestacion simple existente | Mantener `SequentialAgent`, `ParallelAgent`, `LoopAgent` si ya funcionan |
| Orquestacion compleja nueva | Considerar ADK 2.0 Workflow con opt-in |
| Herramienta Python directa | `FunctionTool` o funcion importable |
| Subagente como herramienta | `AgentTool` |
| Agente remoto | `RemoteA2aAgent` o A2A runtime |
| Conocimiento modular cargado bajo demanda | `SkillToolset` con ADK Skills |
| Skill pequena y estable | Skill inline con `models.Skill` |
| Skill compleja o reusable | Skill file-based con `SKILL.md`, `references/`, `assets/`, `scripts/` |
| Reutilizar skills de terceros | Cargar directorio validado con `load_skill_from_dir` |
| Generar nuevas skills | Meta skill tipo `skill-creator` con revision humana |
| Busqueda web publica | `google_search` |
| Busqueda sobre corpus propio | Vertex AI Search / Agent Platform Search |
| Integracion Google/enterprise prebuilt | Revisar `references/15-adk-integrations-python-api.md` antes de crear tool custom |
| API Python concreta | Confirmar modulo/clase en `https://adk.dev/api-reference/python/` antes de importar |
| UI por eventos y estado | AG-UI |
| UI declarativa generada por agente | A2UI |
| Validar codigo determinista | pytest |
| Validar comportamiento LLM | agents-cli eval |

## Puertas De Aprobacion

Pedir confirmacion antes de:

- Ejecutar `agents-cli eval run`, `agents-cli playground`, `agents-cli deploy`,
  `agents-cli infra single-project`, `agents-cli infra cicd`, `agents-cli
  publish gemini-enterprise`.
- Crear o modificar recursos cloud.
- Cambiar modelos existentes.
- Migrar a ADK 2.0 Workflow.
- Activar `thinking_config.include_thoughts` en agentes existentes.
- Introducir Vertex AI Search, ADK SkillToolset, AG-UI o A2UI si no esta en el
  diseno aprobado.
