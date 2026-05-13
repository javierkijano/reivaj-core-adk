---
name: reivaj-adk-2.0-development
description: >
  Skill especializada para disenar, implementar, depurar y verificar agentes con
  ADK 2.0 Workflow. Cubre Workflow graph API, edges, rutas, JoinNode,
  Event output/message/state, schemas, RequestInput, auth/resume, retry,
  patrones de samples oficiales y criterios de decision frente a ADK 1.x.
  Tambien documenta dynamic workflows y collaborative agents como patrones
  secundarios que requieren opt-in o necesidad clara. Usar cuando el usuario
  pida workflows ADK 2.0, graph-based workflows, HITL, fan-out/fan-in o
  migracion desde SequentialAgent/LoopAgent/ParallelAgent a Workflow.
metadata:
  author: Reivaj / OpenCode
  license: Internal
  version: 1.0.0
  requires:
    bins:
      - uv
---

# Reivaj ADK 2.0 Workflow Development

Esta skill es una guia operativa para construir agentes con ADK 2.0 Workflow.
ADK 2.0 esta en beta: no tratarlo como una superficie estable de produccion si
el proyecto exige compatibilidad estricta con ADK 1.x.

## Uso Correcto

Usar esta skill cuando haya que:

- Crear un `Workflow` de ADK 2.0 con grafos explicitos.
- Disenar rutas condicionales, loops, fan-out/fan-in o joins.
- Pasar datos entre nodos con `Event(output=...)`, `Event(state=...)` o schemas.
- Implementar HITL con `RequestInput`, `interrupt_id` y `rerun_on_resume`.
- Integrar auth en FunctionNodes con `auth_config` y `ctx.get_auth_response`.
- Migrar un flujo basado en `SequentialAgent`, `ParallelAgent` o `LoopAgent` a
  ADK 2.0 Workflow.
- Depurar un workflow atascado, una ruta que no dispara, un join incompleto o
  una transferencia de datos mal tipada.
- Evaluar si dynamic workflows o collaborative agents son realmente necesarios,
  sin implementarlos directamente por defecto.

No usar esta skill para:

- Proyectos ADK 1.x clasicos sin opt-in a Workflow 2.0.
- Despliegue, observabilidad o publicacion salvo que sea necesario explicar una
  limitacion especifica de Workflow.
- Evaluar comportamiento LLM no determinista con pytest.

## Relacion Con Otras Skills

- Cargar `reivaj-adk-development` antes si el trabajo implica decisiones ADK
  generales, agents-cli, despliegue, eval o arquitectura completa.
- Cargar `google-agents-cli-adk-code` si necesitas patrones ADK Python fuera de
  Workflow 2.0.
- Cargar `google-agents-cli-eval` antes de ejecutar `agents-cli eval run`.
- Cargar `google-agents-cli-deploy` antes de cualquier despliegue.

## Principios No Negociables

- Confirmar que el proyecto acepta ADK 2.0 beta antes de migrar o introducir
  `google-adk --pre`.
- No cambiar modelos existentes salvo peticion explicita.
- No desplegar, publicar, provisionar infra ni ejecutar evals con credenciales
  reales sin aprobacion.
- No usar Live Streaming como requisito con graph-based workflows: la documentacion
  lo marca como no compatible.
- No usar `Event(message=...)` para pasar datos internos entre nodos; usar
  `Event(output=...)` o `Event(state=...)`.
- No emitir mas de un `Event.output` por ejecucion de nodo.
- Todo `JoinNode` debe recibir salida de todos sus upstreams, incluso en fallos.
- Los agentes dentro de workflows deben ser de tarea/single-turn, no chats
  interactivos paralelos.
- Dynamic workflows (`@node` + `Context.run_node` como orquestador) y
  collaborative agents (`Agent(sub_agents=..., mode=...)`) son patrones
  secundarios: no recomendarlos salvo que el usuario los pida explicitamente o
  que el problema los necesite claramente.
- Si dynamic workflows o collaborative agents parecen convenientes, comentar
  primero alternativas primarias basadas en graph routes, `JoinNode`, rutas o
  workflow estatico. No implementarlos directamente sin explicar el tradeoff.

## Mapa De Referencias

| Area | Referencia |
|---|---|
| Vision, beta, instalacion, compatibilidad | `references/00-overview-setup-limits.md` |
| API central: `Workflow`, `Event`, `Context`, `node`, schemas | `references/01-workflow-api-core.md` |
| Edges, rutas, branches, fan-out/fan-in, loops, nested workflows | `references/02-graph-routes-patterns.md` |
| Data handling: output, message, state, schemas e instrucciones | `references/03-data-handling.md` |
| Human input, resume y auth en workflows | `references/04-human-input-auth.md` |
| Catalogo analizado de samples oficiales `workflow_samples` | `references/05-official-workflow-samples.md` |
| Playbook de implementacion para agentes de codigo | `references/06-implementation-playbook.md` |
| Testing, debugging y fallos comunes | `references/07-testing-debugging.md` |
| Patrones secundarios: collaborative agents | `references/08-secondary-collaboration.md` |
| Patrones secundarios: dynamic workflows | `references/09-secondary-dynamic-workflows.md` |

## Decision Rapida

| Necesidad | Patron recomendado |
|---|---|
| Pasos estrictamente secuenciales | `Workflow(edges=[("START", a, b, c)])` |
| Clasificar y enrutar | Nodo router que emite `Event(route=...)` + edge dict |
| Varias tareas independientes y join | Fan-out tuple o multiples `START` + `JoinNode` |
| Numero dinamico de tareas | Primero evaluar fan-out estatico/`JoinNode`; si el cardinal es realmente dinamico, explicar tradeoff y solo entonces usar dynamic workflow con `ctx.run_node(...)` |
| Reintentos deterministas | `@node(retry_config=RetryConfig(...))` |
| Loop por condicion | Edge desde router/nodo al nodo anterior o a si mismo |
| HITL simple | Nodo que yield `RequestInput(message=...)` |
| HITL robusto tras resume | `@node(rerun_on_resume=True)`, `interrupt_id`, `ctx.resume_inputs` |
| Credenciales API key/OAuth | FunctionNode con `auth_config` y `ctx.get_auth_response(auth_config)` |
| Datos estructurados entre nodos | Pydantic `input_schema` / `output_schema` |
| Mensajes al usuario | `Event(message=...)`, no `output` |
| Estado pequeno de workflow | `Event(state=...)` o `ctx.state[...]` |
| Datos grandes o persistentes | Artifact/database/tool externo, no `Event(state=...)` |
| Delegacion menos estructurada entre subagentes | Patron secundario: collaborative agents; explicar alternativa con Workflow graph y pedir opt-in si no fue solicitado |

## Workflow Base Minimo

```python
from google.adk import Agent, Event, Workflow

classify = Agent(
    name="classify",
    instruction="Classify the input as question, statement or other.",
    output_schema=str,
)

answer_question = Agent(
    name="answer_question",
    instruction="Answer the user's question.",
    output_schema=str,
)

comment = Agent(
    name="comment",
    instruction="Acknowledge or briefly comment on the statement.",
    output_schema=str,
)

def router(node_input: str):
    return Event(route=node_input)

def handle_other():
    return Event(message="Unsupported input.")

root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", classify, router),
        (router, {"question": answer_question, "statement": comment, "other": handle_other}),
    ],
)
```

## Flujo De Trabajo Recomendado

1. Verificar version ADK y consentimiento de beta.
2. Escribir contrato de grafo antes de codificar: nodos, inputs, outputs,
   routes, state keys, errores, joins y criterios de parada.
3. Separar nodos deterministas de nodos LLM.
4. Definir schemas Pydantic para toda frontera fragil entre nodos.
5. Implementar primero el grafo minimo secuencial y tests de import.
6. Agregar rutas, joins, retry, HITL y auth en incrementos pequenos.
7. Si surge necesidad de dynamic workflows o collaborative agents, detenerse y
   explicar alternativas primarias antes de implementarlos.
8. Probar que cada ruta emite `Event(route=...)` esperado.
9. Probar que cada branch que llega a `JoinNode` siempre emite salida.
10. Verificar con tests deterministas el codigo y con evals el comportamiento LLM.

## Checklist Final

- `root_agent` es un `Workflow` exportado desde el modulo esperado.
- Hay al menos una edge que empieza en `"START"` o `START`.
- Cada node tiene una responsabilidad y contrato de entrada/salida.
- Los datos internos usan `output` o `state`; la respuesta de usuario usa
  `message`.
- Las rutas emitidas coinciden exactamente con las claves del edge dict.
- Los joins tienen salida garantizada desde todos los upstreams.
- Los loops tienen criterio de salida y no dependen solo de esperanza LLM.
- HITL usa `RequestInput` con `interrupt_id` estable si requiere resume.
- Auth no imprime tokens y enmascara secretos en mensajes.
- Tests cubren import, rutas principales, errores y al menos un caso de resume
  si hay HITL/auth.
