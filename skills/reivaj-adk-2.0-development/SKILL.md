---
name: reivaj-adk-2.0-development
description: >
  Skill especializada para disenar, implementar, depurar y verificar agentes con
  ADK 2.0 Workflow. Cubre Workflow graph API, edges, rutas, JoinNode,
  contratos runtime reales, diseno de interaccion y activacion, Event
  output/message/state, schemas, RequestInput, auth/resume, retry, patrones de
  samples oficiales y criterios de decision frente a ADK 1.x.
  Tambien documenta dynamic workflows y collaborative agents como patrones
  secundarios que requieren opt-in o necesidad clara. Usar cuando el usuario
  pida workflows ADK 2.0, graph-based workflows, HITL, fan-out/fan-in o
  migracion desde SequentialAgent/LoopAgent/ParallelAgent a Workflow.
metadata:
  author: Reivaj / OpenCode
  license: Internal
  version: 1.2.0
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
- Documentar contratos runtime reales en fronteras `START`, HITL resume y
  post-`JoinNode`, no solo contratos semanticos.
- Disenar la politica de activacion de un `root_agent` conversacional antes de
  planners, tools, proveedores, HITL o acciones costosas.
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
- En proyectos `agents-cli`, el nombre de app/sesion debe coincidir con la forma
  de carga. Para `agents-cli run` desde el proyecto, `[tool.agents-cli].agent_directory`
  y `App.name` deben coincidir; si `agent_directory="app"`, `app/agent.py` exporta
  `App(name="app")`. Si tambien se soporta `adk web` desde el directorio padre de
  agentes, el `agent.py` de la raiz del agente puede existir, pero debe exportar
  solo `root_agent`, nunca `app`, para que ADK use el nombre del subdirectorio
  como app name y no mezcle sesiones `app` con `root_<nombre>`.
- No usar `Event(message=...)` para pasar datos internos entre nodos; usar
  `Event(output=...)` o `Event(state=...)`.
- No emitir mas de un `Event.output` por ejecucion de nodo.
- Todo nodo conectado directamente a `START` debe aceptar
  `google.genai.types.Content` o `Any` en su firma runtime.
- Todo nodo conectado directamente a `START` debe normalizar explicitamente
  `Content.parts` a texto antes de validar contra schemas Pydantic propios.
- No usar `str`, `ResearchQuery`, unions estrechas ni modelos Pydantic como firma
  directa del primer nodo salvo que un nodo anterior ya haya normalizado el
  objeto runtime real.
- ADK valida parametros de `FunctionNode` usando las type annotations antes de
  ejecutar la funcion; si la annotation no acepta el objeto runtime real, el nodo
  falla antes de poder normalizar.
- En bordes externos del grafo (`START`, HITL resume, post-`JoinNode`) preferir
  `Any` y validar internamente despues de normalizar.
- Usar `Any` en fronteras runtime no autoriza a tratar `str(node_input)` como
  tarea valida. Despues de normalizar, debe haber validacion semantica o
  `intent_gate` antes de activar planners, tools, proveedores, HITL o acciones
  costosas.
- Si un `Workflow` es el `root_agent` expuesto a chat/playground, debe tener una
  capa inicial de interaccion: normalizacion de input, intent/activation gate,
  rutas conversacionales, aclaracion para inputs ambiguos y activacion del
  workflow solo con intencion suficiente.
- Un `general_chat_root_agent` no puede asumir intencion de dominio: debe filtrar
  saludos, small talk, agradecimientos, confirmaciones sueltas y mensajes
  ambiguos antes de planners/tools/HITL.
- Un `dedicated_workflow` puede asumir que el input pertenece al dominio solo si
  otro router o caller ya hizo la activacion y esa precondicion esta documentada.
- `RequestInput` no es una compuerta conversacional generica. Debe aparecer
  despues de validar intencion y solo cuando hay una decision real que requiere
  humano.
- Todo `JoinNode` debe recibir salida de todos sus upstreams, incluso en fallos.
- El nodo posterior a un `JoinNode` debe aceptar `Any`, normalizar `dict`,
  `list`, `tuple`, `Event.output` o modelos ya validados, y no asumir una unica
  forma de input post-join.
- Un nodo HITL debe tratar `ctx.resume_inputs[interrupt_id]` como `str`, `dict` o
  payload estructurado segun UI/runtime y normalizar antes de emitir rutas
  criticas.
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
| Primer nodo desde `START` | Funcion con firma `Any` o `Content`, `content_to_text(...)`, luego schema propio |
| Root conversacional | `START -> normalize_input -> intent_gate -> rutas conversacionales/workflow_request` |
| Subworkflow dedicado | Documentar caller/router que ya valido intencion de dominio |
| Clasificar y enrutar | Nodo router que emite `Event(route=...)` + edge dict |
| Varias tareas independientes y join | Fan-out tuple o multiples `START` + `JoinNode` |
| Agregador post-join | Firma `Any`, normalizacion interna de dict/list/tuple/output/modelos |
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

## Contextos De Activacion

Antes de implementar, clasificar el workflow:

| Contexto | Regla |
|---|---|
| `dedicated_workflow` | Puede asumir que el input pertenece al dominio porque otro router lo invoco; documentar ese caller y no exponerlo directamente a chat general sin front-door. |
| `general_chat_root_agent` | No puede asumir intencion; debe filtrar saludos, small talk, thanks, confirmaciones sueltas y mensajes ambiguos antes de activar el flujo especializado. |

## Interaction Activation Contract

Toda spec ADK 2.0 que pueda llegar a chat/playground debe incluir esta seccion
antes de planners, HITL, tools, proveedores o acciones costosas:

| Campo | Requisito |
|---|---|
| `entrypoint_context` | `general_chat`, `dedicated_workflow`, `tool_invoked` o `subworkflow`. |
| `activation_triggers` | Frases/intenciones que si activan el workflow. Para research/search: `investiga`, `busca fuentes`, `haz research`, `compara`, `analiza en profundidad`, `consulta la web`, `prepara un informe`. |
| `non_activation_inputs` | Saludos, thanks, small talk, confirmaciones sueltas, mensajes vacios e inputs ambiguos como `ADK`. |
| `deterministic_prechecks` | Reglas baratas sin IA para vacio, saludos, thanks, small talk, confirmaciones sueltas y comandos claros. |
| `llm_intent_check` | Usar clasificador LLM solo cuando reglas deterministas no resuelven la intencion. |
| `minimum_required_slots` | Datos minimos antes de ejecutar el flujo costoso. |
| `clarification_policy` | Cuando preguntar antes de planificar. |
| `direct_response_policy` | Cuando responder con `Event(message=...)` sin plan. |
| `hitl_policy` | `RequestInput` solo por accion sensible, coste/riesgo, side effect irreversible, baja confianza, ambiguedad real o peticion explicita de revision. |
| `expensive_action_policy` | Tools, busquedas, proveedores y side effects solo tras intencion explicita y slots minimos. |
| `required_interaction_tests` | Casos obligatorios de activacion/no activacion. |

Tests minimos obligatorios:

- `Hola` devuelve `Event(message=...)` natural y no crea plan.
- `Gracias` devuelve respuesta natural y no ejecuta workflow.
- Input vacio o whitespace pide input util sin plan.
- `ADK` pide aclaracion y no ejecuta proveedores.
- `Investiga ADK 2.0 Workflow con fuentes` activa planner.
- El primer nodo acepta `Content`.
- Ningun `RequestInput` se emite antes de `intent_gate`.
- Tools/proveedores no se ejecutan para saludos, small talk o inputs ambiguos.

Patron recomendado para `general_chat_root_agent`:

```text
START
  -> normalize_input
  -> intent_gate
  -> {
       greeting: greeting_response,
       thanks: thanks_response,
       small_talk: smalltalk_response,
       simple_question: simple_answer,
       ambiguous: clarification,
       workflow_request: planner
     }
```

## Front-Door Conversacional Seguro

```python
from typing import Any, Literal

from google.adk import Agent, Event, Workflow
from google.genai.types import Content
from pydantic import BaseModel


IntentLabel = Literal[
    "greeting",
    "thanks",
    "small_talk",
    "simple_question",
    "ambiguous",
    "workflow_request",
]


class UserIntent(BaseModel):
    label: IntentLabel
    text: str
    confidence: Literal["low", "medium", "high"]
    reason: str


def normalize_text(node_input: Any) -> str:
    if isinstance(node_input, Content):
        return " ".join(
            part.text for part in (node_input.parts or [])
            if getattr(part, "text", None)
        ).strip()
    return str(node_input).strip()


def intent_gate(node_input: Any) -> Event:
    text = normalize_text(node_input)
    lowered = text.lower()

    if not text:
        return Event(
            output=UserIntent(label="ambiguous", text=text, confidence="high", reason="Empty input"),
            route="ambiguous",
        )

    if lowered in {"hola", "buenas", "hey", "hello"}:
        return Event(
            output=UserIntent(label="greeting", text=text, confidence="high", reason="Greeting"),
            route="greeting",
        )

    if lowered in {"gracias", "thanks", "thank you"}:
        return Event(
            output=UserIntent(label="thanks", text=text, confidence="high", reason="Thanks"),
            route="thanks",
        )

    if lowered in {"como estas", "que tal", "how are you"}:
        return Event(
            output=UserIntent(label="small_talk", text=text, confidence="high", reason="Small talk"),
            route="small_talk",
        )

    if lowered in {"que puedes hacer", "que puedes hacer?", "help"}:
        return Event(
            output=UserIntent(label="simple_question", text=text, confidence="high", reason="Simple question"),
            route="simple_question",
        )

    if any(
        trigger in lowered
        for trigger in [
            "investiga",
            "busca fuentes",
            "haz research",
            "consulta la web",
            "prepara un informe",
        ]
    ):
        return Event(
            output=UserIntent(
                label="workflow_request",
                text=text,
                confidence="high",
                reason="Explicit workflow trigger",
            ),
            route="workflow_request",
        )

    return Event(
        output=UserIntent(
            label="ambiguous",
            text=text,
            confidence="medium",
            reason="No explicit workflow trigger",
        ),
        route="ambiguous",
    )


def greeting_response(intent: UserIntent) -> Event:
    return Event(message="Hola. Que quieres investigar o resolver hoy?")


def thanks_response(intent: UserIntent) -> Event:
    return Event(message="De nada. Si quieres que investigue algo, dime el tema.")


def clarification(intent: UserIntent) -> Event:
    return Event(message="Quieres que haga una investigacion sobre esto, o solo estas conversando?")


planner = Agent(
    name="planner",
    instruction="Plan the requested research only after intent_gate routes workflow_request.",
    input_schema=UserIntent,
    output_schema=str,
)


def simple_answer(intent: UserIntent) -> Event:
    return Event(message="Puedo responder preguntas simples o investigar si lo pides explicitamente.")


def smalltalk_response(intent: UserIntent) -> Event:
    return Event(message="Estoy aqui para ayudarte. Si quieres investigacion, indicame el tema.")

root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", intent_gate),
        (intent_gate, {
            "greeting": greeting_response,
            "thanks": thanks_response,
            "small_talk": smalltalk_response,
            "simple_question": simple_answer,
            "ambiguous": clarification,
            "workflow_request": planner,
        }),
    ],
)
```

Este patron combina compatibilidad runtime (`Any`/`Content`) con seguridad
conversacional. `Any` permite recibir `Content`, pero no decide si el workflow
debe activarse; esa decision pertenece al `intent_gate`.

## Runtime Boundary Contracts

ADK runtime input no siempre coincide con el input semantico del nodo. El binder
de ADK/Pydantic valida las type annotations de `FunctionNode` antes de ejecutar
la funcion. Si la annotation no acepta el objeto real, por ejemplo
`Content(role="user", parts=[Part(text="...")])`, el nodo falla antes de poder
normalizar.

Para cada nodo documentar este contrato antes de implementar:

| Campo | Pregunta que debe responder |
|---|---|
| Semantic input | Que dato de negocio espera el nodo despues de normalizar |
| ADK runtime input | Que objeto puede entregar ADK en esa edge real |
| Function signature | Annotation segura que acepta el objeto runtime |
| Normalization required | Conversion antes de Pydantic o routing |
| Event output | Tipo exacto emitido por `Event(output=...)` |
| State keys | Keys leidas/escritas en `state` |
| Route values | Valores exactos emitidos por `Event(route=...)` |

Ejemplo minimo:

| Nodo | Semantic input | ADK runtime input | Function signature | Normalization required | Event output | State keys | Route values |
|---|---|---|---|---|---|---|---|
| `parse_request` | texto usuario | `Content` desde `START` | `node_input: Any` | `Content.parts` -> texto | `ParsedRequest` | none | none |
| `router` | categoria validada | `str` desde Agent | `node_input: str` | trim/lower opcional | none | none | `question`, `statement`, `other` |
| `aggregate` | resultados paralelos | forma post-`JoinNode` variable | `node_input: Any` | dict/list/tuple/modelo -> `AggregateInput` | `AggregateResult` | none | none |
| `intent_gate` | texto usuario + politica de activacion | `Content` desde `START` | `node_input: Any` | texto -> `UserIntent` | `UserIntent` | none | `greeting`, `thanks`, `small_talk`, `simple_question`, `ambiguous`, `workflow_request` |
| `planner` | request validado | `UserIntent` con `workflow_request` | Agent `input_schema=UserIntent` | none | plan/schema de dominio | opcional | none |

## Flujo De Trabajo Recomendado

1. Verificar version ADK y consentimiento de beta.
2. Clasificar el contexto como `general_chat_root_agent` o `dedicated_workflow`.
3. Escribir contrato de grafo antes de codificar: nodos, semantic input, ADK
   runtime input, firma, normalizacion, politica de activacion, outputs, routes,
   state keys, errores, joins y criterios de parada.
4. Separar front-door conversacional, nodos deterministas y nodos LLM.
5. Definir schemas Pydantic para toda frontera fragil entre nodos.
6. Implementar primero `normalize_input`/`intent_gate` si el workflow es root
   conversacional.
7. Implementar el grafo minimo secuencial y tests de import.
8. Agregar rutas, joins, retry, HITL y auth en incrementos pequenos.
9. Si surge necesidad de dynamic workflows o collaborative agents, detenerse y
   explicar alternativas primarias antes de implementarlos.
10. Probar que cada ruta emite `Event(route=...)` esperado.
11. Probar que saludos, thanks e inputs ambiguos devuelven `Event(message=...)`
    sin planner, tools ni `RequestInput`.
12. Probar que cada branch que llega a `JoinNode` siempre emite salida.
13. Probar que el primer nodo acepta `Content(role="user", parts=[Part(text="...")])`.
14. Probar que el nodo post-`JoinNode` normaliza multiples formas de input.
15. Verificar con tests deterministas el codigo y con evals el comportamiento LLM.

## Checklist Final

- `root_agent` es un `Workflow` exportado desde el modulo esperado.
- En proyectos `agents-cli`, `App.name == [tool.agents-cli].agent_directory` para
  la carga desde el proyecto. Si se necesita carga por `adk web <agents_dir>`, el
  `agent.py` raiz del agente exporta solo `root_agent`, no `app`.
- Se respondio si el workflow es root conversacional o subworkflow dedicado.
- Hay al menos una edge que empieza en `"START"` o `START`.
- Todo primer nodo desde `START` acepta `Content` o `Any` y tiene test con
  `Content(role="user", parts=[Part(text="...")])`.
- Si el workflow esta expuesto a chat/playground, existe `intent_gate` antes de
  planner/tools/proveedores/HITL.
- Estan documentados los inputs que no deben activar el workflow.
- Las rutas conversacionales (`greeting`, `thanks`, `small_talk`,
  `simple_question`, `ambiguous`) devuelven `Event(message=...)` directamente.
- La condicion exacta que permite planner/tools/HITL esta documentada y testeada.
- Cada node tiene una responsabilidad y contrato de entrada/salida.
- Cada contrato distingue semantic input, ADK runtime input, firma,
  normalizacion, output, state y route values.
- Los datos internos usan `output` o `state`; la respuesta de usuario usa
  `message`.
- Las rutas emitidas coinciden exactamente con las claves del edge dict.
- Los joins tienen salida garantizada desde todos los upstreams.
- Los nodos post-`JoinNode` aceptan `Any` y normalizan dict/list/tuple/output/modelos.
- Los loops tienen criterio de salida y no dependen solo de esperanza LLM.
- HITL usa `RequestInput` con `interrupt_id` estable si requiere resume y
  normaliza `ctx.resume_inputs[interrupt_id]` antes de rutas criticas.
- Ningun saludo o small talk produce `RequestInput` ni ejecuta proveedores/tools.
- Auth no imprime tokens y enmascara secretos en mensajes.
- Tests cubren import/export, primer nodo con `Content`, rutas exactas, branches
  hacia `JoinNode`, no activacion conversacional, post-join con multiples formas
  de input y primera interrupcion/resume si hay HITL/auth.

Preguntas finales antes de dar una implementacion por buena:

- Este workflow es root conversacional o subworkflow dedicado?
- Que inputs no deben activar el workflow?
- Donde esta el `intent_gate`?
- Que rutas devuelven `Event(message=...)` directamente?
- Que condicion exacta permite planner/tools/HITL?
- Hay tests de no activacion?
