# Workflow API Core

## Imports Principales

Patrones vistos en docs y samples:

```python
from typing import Any

from google.adk import Agent, Context, Event, Workflow
from google.adk.workflow import JoinNode, RetryConfig, node
from google.adk.workflow._base_node import START  # opcional; "START" tambien aparece en samples
from google.adk.events import RequestInput
from google.genai.types import Content
```

Para auth:

```python
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes
```

## `Workflow`

Un workflow se define con nombre y lista de edges:

```python
root_agent = Workflow(
    name="root_agent",
    edges=[("START", step_a, step_b, step_c)],
)
```

Cada elemento de `edges` describe rutas de ejecucion. Puede ser:

- Secuencia: `("START", a, b, c)`.
- Branch: `(router, {"ROUTE_A": a, "ROUTE_B": b})`.
- Fan-out: `("START", (a, b, c), join, aggregate)`.
- Multiples triggers iniciales: varias edges que empiezan en `"START"`.

## Tipos De Nodo

Un nodo puede ser:

- `Agent` / `LlmAgent` orientado a una tarea.
- Funcion sync o async.
- Funcion decorada con `@node(...)`.
- Tool compatible.
- `Workflow` anidado.
- `JoinNode`.
- Nodo HITL que retorna/yield `RequestInput`.

## Function Nodes

Una funcion puede devolver datos simples o `Event`:

```python
def uppercase(node_input: str):
    return node_input.upper()

def uppercase_event(node_input: str):
    return Event(output=node_input.upper())
```

Si el retorno no es `Event`, el framework lo envuelve como output para el nodo
siguiente.

Estas firmas estrechas son validas solo cuando un upstream ya normalizo el dato.
No usarlas como primer nodo conectado directamente a `START`.

## Binder Y Runtime Boundaries

ADK convierte funciones en `FunctionNode` y valida sus parametros con las type
annotations antes de ejecutar el cuerpo. En `START`, el input runtime real puede
ser `google.genai.types.Content`, por ejemplo
`Content(role="user", parts=[Part(text="...")])`. Si la firma dice `str`,
`ResearchQuery`, `str | ResearchQuery` o un modelo Pydantic propio, el binder
puede fallar antes de que la funcion pueda normalizar.

Reglas de frontera:

- Nodos conectados directamente a `START`: firma `Any` o `Content`.
- Si `START` viene de chat/playground general: `Any`/`Content` debe ir seguido
  de normalizacion e `intent_gate` antes de planner/tools/HITL.
- HITL resume: tratar `ctx.resume_inputs[interrupt_id]` como payload externo.
- Post-`JoinNode`: firma `Any` y normalizacion interna.
- Validar con Pydantic despues de convertir el objeto runtime a la forma
  semantica esperada.

`Any` evita fallos del binder, pero no decide si el workflow debe activarse.
Prohibido tratar `str(node_input)` como tarea valida en un root conversacional
sin politica de intencion.

Plantilla segura para primer nodo:

```python
from typing import Any

from google.adk import Event
from google.genai.types import Content


def parse_request(node_input: Any) -> Event:
    text = content_to_text(node_input)
    return Event(output=ParsedRequest(topic=text))


def content_to_text(node_input: Any) -> str:
    if isinstance(node_input, Content):
        parts = node_input.parts or []
        return " ".join(part.text for part in parts if getattr(part, "text", None)).strip()
    return str(node_input).strip()
```

## `@node`

Usar `@node` cuando necesitas configuracion extra:

```python
@node(retry_config=RetryConfig(max_attempts=5, initial_delay=1))
def flaky_node(ctx: Context):
    ...

@node(rerun_on_resume=True)
def human_review(ctx: Context):
    ...

@node(parallel_worker=True)
def worker(item: str):
    return item.upper()
```

Usos observados:

- `rerun_on_resume=True` para HITL/auth y nodos dinamicos.
- `retry_config=RetryConfig(...)` para llamadas fragiles.
- `parallel_worker=True` para procesar cada item de una lista.
- `auth_config=...` para pausar y pedir credenciales.

## `Context`

`Context` da acceso a:

- `ctx.state`: estado compartido pequeno de la session/workflow.
- `ctx.run_node(node, node_input=..., use_sub_branch=True, use_as_output=True)`:
  ejecutar nodos dinamicamente dentro de un orquestador. Patron secundario; ver
  `09-secondary-dynamic-workflows.md` antes de implementarlo.
- `ctx.resume_inputs`: respuestas de interrupciones HITL al reanudar.
- `ctx.get_auth_response(auth_config)`: credenciales recibidas tras auth.
- `ctx.attempt_count`: intento actual en nodos con retry.

## `Agent` Dentro De Workflow

Los agentes se usan como nodos LLM. Para datos robustos, definir schemas:

```python
agent = Agent(
    name="extract",
    instruction="Extract structured fields from the input.",
    input_schema=InputModel,
    output_schema=OutputModel,
    output_key="extract_result",
)
```

Precauciones:

- Tratar agentes como single-turn/task nodes.
- Evitar chats interactivos paralelos dentro de la misma session.
- Usar `output_schema` para decisiones de ruta y contratos entre nodos.
- No confiar en texto libre para rutas criticas.

## Root Agent Export

El modulo del agente debe exportar:

```python
root_agent = Workflow(...)
```

Esto mantiene compatibilidad con runners y convenciones ADK/agents-cli.
