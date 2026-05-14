# Implementation Playbook

## 1. Antes De Codificar

Definir una tabla de nodos con contratos semanticos y runtime:

| Nodo | Semantic input | ADK runtime input | Function signature | Normalization required | Event output | State keys | Route values |
|---|---|---|---|---|---|---|---|
| `parse_request` | user text | `Content` desde `START` | `node_input: Any` | `Content.parts` -> text -> `RequestSpec` | `RequestSpec` | none | none |
| `classify` | `RequestSpec` | `RequestSpec` output previo | Agent `input_schema=RequestSpec` | none | `Category` | `category` opcional | none |
| `route_category` | `Category` | modelo validado previo | `decision: Category` | default/fallback | none | none | exact route literal |
| `intent_gate` | texto usuario | `Content` desde chat | `node_input: Any` | texto -> `UserIntent` | `UserIntent` | none | `greeting`, `thanks`, `small_talk`, `simple_question`, `ambiguous`, `workflow_request` |

No empezar por prompts largos. Empezar por grafo y contratos.

En proyectos `agents-cli`, definir tambien el contrato de carga ADK antes de
codificar. Para `agents-cli run` desde el proyecto, `[tool.agents-cli].agent_directory`
y `App.name` deben coincidir. Si `agent_directory="app"`, `app/agent.py` exporta
`App(name="app")`. Si ademas se quiere usar `adk web <agents_dir>` desde el
directorio padre, puede existir un `agent.py` en la raiz del agente, pero debe
exportar solo `root_agent`, nunca `app`. Exportar `app` desde ambos entrypoints
mezcla nombres de sesion (`app` vs nombre del subdirectorio) y produce
`Session not found`.

Regla: en bordes externos (`START`, HITL resume, post-`JoinNode`) documentar el
objeto runtime real y usar `Any` si hay duda. ADK/Pydantic valida annotations
antes de ejecutar la funcion.

Antes de usar planners, tools, proveedores, HITL o acciones costosas, decidir si
el workflow es `general_chat_root_agent` o `dedicated_workflow`.

`general_chat_root_agent` requiere front-door de activacion. `dedicated_workflow`
puede asumir dominio solo si otro router lo invoco y esa precondicion esta
documentada.

Toda spec debe declarar `Interaction Activation Contract` cuando el agente pueda
estar expuesto a chat/playground. Campos minimos: `entrypoint_context`,
`activation_triggers`, `non_activation_inputs`, `deterministic_prechecks`,
`llm_intent_check`, `minimum_required_slots`, `clarification_policy`,
`direct_response_policy`, `hitl_policy`, `expensive_action_policy` y
`required_interaction_tests`.

Si `entrypoint_context=general_chat`, no empezar por planner, provider, tool ni
HITL. El flujo debe ser determinista primero: `START -> normalize_user_input ->
intent_gate -> rutas conversacionales/workflow_request`.

Para research/search/costly workflows, planner/proveedores/tools solo se activan
con intencion explicita (`investiga`, `busca fuentes`, `haz research`,
`compara`, `analiza en profundidad`, `consulta la web`, `prepara un informe`) y
slots minimos presentes. `Hola`, `ADK`, `que tal`, `gracias` o `si` sin contexto
no activan investigacion.

## 2. Elegir Tipos De Nodos

- Funcion Python: transformacion determinista, validacion, routing, formatting.
- Agent: clasificacion semantica, extraccion incierta, generacion, evaluacion LLM.
- Tool: accion externa encapsulada.
- Workflow anidado: subproceso reusable con contrato claro.
- JoinNode: fan-in de ramas paralelas estaticas.
- Orquestador `@node`: patron secundario para fan-out dinamico, loops con codigo
  o HITL/resume complejo; explicar alternativas antes de usarlo.

## 3. Plantilla Front-Door Conversacional

Usar cuando el `Workflow` es `root_agent` expuesto a chat/playground:

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
        for trigger in ["investiga", "busca fuentes", "haz research", "consulta la web", "prepara un informe"]
    ):
        return Event(
            output=UserIntent(label="workflow_request", text=text, confidence="high", reason="Explicit workflow trigger"),
            route="workflow_request",
        )
    return Event(
        output=UserIntent(label="ambiguous", text=text, confidence="medium", reason="No explicit workflow trigger"),
        route="ambiguous",
    )


def greeting_response(intent: UserIntent) -> Event:
    return Event(message="Hola. Que quieres investigar o resolver hoy?")


def thanks_response(intent: UserIntent) -> Event:
    return Event(message="De nada. Si quieres que investigue algo, dime el tema.")


def smalltalk_response(intent: UserIntent) -> Event:
    return Event(message="Estoy aqui para ayudarte. Si quieres investigacion, indicame el tema.")


def simple_answer(intent: UserIntent) -> Event:
    return Event(message="Puedo responder preguntas simples o investigar si lo pides explicitamente.")


def clarification(intent: UserIntent) -> Event:
    return Event(message="Quieres que haga una investigacion sobre esto, o solo estas conversando?")


planner = Agent(
    name="planner",
    instruction="Plan only explicit workflow_request inputs.",
    input_schema=UserIntent,
    output_schema=str,
)


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

No interpretar `str(node_input)` como tarea valida. `Any` resuelve compatibilidad
runtime, no activacion semantica.

## 4. Plantilla Secuencial Dedicada

Usar solo si el workflow ya fue activado por un router externo o no esta expuesto
directamente a chat general.

```python
from typing import Any

from google.adk import Agent, Event, Workflow
from google.genai.types import Content
from pydantic import BaseModel


class ParsedRequest(BaseModel):
    topic: str


def parse_request(node_input: Any) -> Event:
    text = content_to_text(node_input)
    return Event(output=ParsedRequest(topic=text))


def content_to_text(node_input: Any) -> str:
    if isinstance(node_input, Content):
        parts = node_input.parts or []
        return " ".join(part.text for part in parts if getattr(part, "text", None)).strip()
    return str(node_input).strip()

research_agent = Agent(
    name="research_agent",
    instruction="Research the topic: {ParsedRequest.topic}",
    input_schema=ParsedRequest,
    output_schema=str,
)

def final_message(node_input: str):
    return Event(message=node_input)

root_agent = Workflow(
    name="root_agent",
    edges=[("START", parse_request, research_agent, final_message)],
)
```

## 5. Plantilla De Routing

```python
class RouteDecision(BaseModel):
    route: Literal["fast", "deep", "unsupported"]

classifier = Agent(..., input_schema=ParsedRequest, output_schema=RouteDecision)

def route(decision: RouteDecision):
    return Event(route=decision.route)

root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", parse_request, classifier, route),
        (route, {"fast": fast_path, "deep": deep_path, "unsupported": unsupported}),
    ],
)
```

## 6. Plantilla Fan-Out/Fan-In

```python
join = JoinNode(name="join_results")

def aggregate(node_input: Any):
    joined = normalize_join_input(node_input)
    return Event(output=AggregateResult(results=joined))

root_agent = Workflow(
    name="root_agent",
    edges=[("START", (branch_a, branch_b, branch_c), join, aggregate, final)],
)
```

Cada branch debe emitir output. Si una branch puede fallar, capturar excepcion y
emitir un resultado de error estructurado.

El nodo post-`JoinNode` siempre acepta `Any`. Debe normalizar `dict`, `list`,
`tuple`, `Event.output` o modelos ya validados antes de construir su schema de
agregacion.

## 7. Plantilla Dynamic Fan-Out

No usar esta plantilla por defecto. Primero intentar fan-out estatico con
`JoinNode` o branches enumerables. Usarla solo si el cardinal de tareas depende
del runtime o si el grafo estatico seria artificialmente complejo. Antes de
implementarla, comentar el tradeoff al usuario.

```python
@node(rerun_on_resume=True)
async def orchestrate(ctx: Context, node_input: Any):
    batch = BatchSpec.model_validate(normalize_batch_input(node_input))
    tasks = [
        ctx.run_node(worker, node_input=item, use_sub_branch=True)
        for item in batch.items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return normalize_results(results)
```

Si el orquestador esta conectado a `START`, `normalize_batch_input` debe aceptar
`Content` y convertir `Content.parts` antes de validar `BatchSpec`.

Usar `return_exceptions=True` en sistemas reales para evitar que una branch mate
todo el batch sin salida diagnosable.

## 8. Plantilla HITL

`RequestInput` no reemplaza al front-door conversacional. Solo usarlo despues de
`intent_gate` y cuando haya una decision humana real.

```python
@node(rerun_on_resume=True)
def approve(ctx: Context, proposal: Proposal):
    raw_resume = ctx.resume_inputs.get("approval")
    if raw_resume is None:
        yield RequestInput(
            interrupt_id="approval",
            message="Approve this proposal?",
            payload=proposal,
            response_schema=ApprovalDecision,
        )
        return
    decision = ApprovalDecision.model_validate(normalize_hitl_response(raw_resume))
    yield Event(route="approved" if decision.approved else "rejected")
```

## 9. Validaciones Obligatorias

- Import/export: el modulo exporta `root_agent` y es `Workflow`.
- App/session name: si el proyecto usa `agents-cli`, `App.name` coincide con
  `[tool.agents-cli].agent_directory`; si tambien hay `agent.py` raiz para
  `adk web <agents_dir>`, ese archivo exporta solo `root_agent`, no `app`.
- Primer nodo conectado a `START` acepta `Content(role="user", parts=[Part(text="...")])`.
- Si es `general_chat_root_agent`, existe `intent_gate` antes de planner/tools/HITL.
- `Hola` responde con `Event(message=...)` y no llega al planner.
- `Gracias` responde natural y no ejecuta tools.
- Input vacio y `ADK` piden aclaracion si no hay intencion explicita.
- `Investiga ADK 2.0 Workflow` llega al planner.
- Ningun saludo produce `RequestInput` ni ejecuta proveedores/tools.
- `RequestInput` solo aparece despues de `intent_gate` y bajo politica HITL.
- Router emite rutas exactas que existen como keys del edge dict.
- Branches hacia `JoinNode` siempre emiten output, incluso en fallo.
- Post-`JoinNode` normaliza multiples formas de input.
- HITL cubre primera interrupcion y resume.
- Cada loop tiene criterio de salida o limite.
- Cada nodo con auth enmascara credenciales.
- Schemas Pydantic validan outputs de LLM usados para routing.

## 10. Migration Playbook

Para migrar un flujo existente:

1. Extraer lista de pasos reales.
2. Separar pasos deterministas de pasos LLM.
3. Convertir callbacks/transforms en FunctionNodes.
4. Convertir subagentes a Agent nodes con `input_schema`/`output_schema`.
5. Convertir `LoopAgent` en route loop; usar dynamic orchestrator solo si el loop
   necesita logica programatica compleja y tras explicar alternativas.
6. Convertir `ParallelAgent` en fan-out + `JoinNode`.
7. Escribir tests de rutas antes de ajustar prompts.
8. Mantener el modelo existente salvo peticion explicita.

## 11. Definition Of Done

- El grafo es legible sin leer prompts largos.
- Esta claro si es root conversacional o subworkflow dedicado.
- La politica de activacion esta antes de planners, tools, proveedores y HITL.
- Hay rutas conversacionales que terminan en `Event(message=...)`.
- Hay tests de no activacion para saludos, thanks e inputs ambiguos.
- Los contratos de datos estan expresados con schemas o docstrings.
- Las rutas son enumeradas y testeables.
- Los nodos fallan con mensajes accionables.
- Los outputs finales salen por `Event(message=...)`.
- Los datos internos no dependen de mensajes visibles.
- Tests deterministas pasan; evals quedan para comportamiento LLM.
