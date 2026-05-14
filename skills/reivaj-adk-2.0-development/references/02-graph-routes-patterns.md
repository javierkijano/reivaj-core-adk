# Graph Routes And Workflow Patterns

## Secuencia

Usar para pipelines lineales:

```python
root_agent = Workflow(
    name="sequence",
    edges=[("START", parse_input, enrich, summarize)],
)
```

`parse_input` esta en frontera `START`: si es FunctionNode, su firma debe ser
`Any` o `Content` y debe normalizar `Content.parts` antes de validar schemas
propios.

Muestra oficial: `sequence/agent.py`.

## Routing Condicional

Un nodo router debe emitir `Event(route=...)`. Las claves del dict deben coincidir
exactamente:

```python
def route_on_category(category: InputCategory):
    yield Event(route=category.category)

root_agent = Workflow(
    name="routing",
    edges=[
        ("START", process_input, classify_input, route_on_category),
        (route_on_category, {
            "question": answer_question,
            "statement": comment_on_statement,
            "other": handle_other,
        }),
    ],
)
```

Muestra oficial: `route/agent.py`.

Buenas practicas:

- Si `process_input` esta conectado a `START`, usar firma `Any`/`Content` y
  normalizacion interna antes del clasificador.
- Ruta con `Literal[...]` o enum Pydantic.
- Handler por defecto para `other` o errores.
- Tests por cada route key.

## Activation Gate Para Root Conversacional

Si el `Workflow` es el `root_agent` expuesto a chat/playground, el primer routing
no debe ser planner, tool ni HITL. Debe ser una compuerta de intencion:

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

Reglas:

- `greeting`, `thanks`, `small_talk`, `simple_question` y `ambiguous` terminan
  con `Event(message=...)`.
- `workflow_request` es la unica ruta que puede activar planner, tools,
  proveedores, HITL o acciones costosas.
- Inputs como `Hola`, `Gracias`, `ADK` o string vacio no deben llegar al planner
  salvo que la politica de dominio los clasifique explicitamente como request.
- Confirmaciones sueltas como `si`, `ok` o `dale` no activan el workflow sin
  contexto previo verificable.

`Any` en la firma solo resuelve el contrato runtime con ADK; no sustituye la
politica de activacion.

## Fan-Out / Fan-In Estatico

Para paralelismo conocido de antemano:

```python
join_node = JoinNode(name="join_for_results")

root_agent = Workflow(
    name="fanout",
    edges=[("START", (task_a, task_b, task_c), join_node, aggregate)],
)
```

En samples, `JoinNode` puede entregar un dict con outputs por nombre de nodo.
Muestra oficial: `fan_out_fan_in/agent.py`.

Regla critica: cada upstream debe emitir salida. Si uno falla sin fallback output,
el join se atasca.

El nodo posterior a `JoinNode` es otra frontera runtime: debe aceptar `Any` y
normalizar internamente. No asumir una unica forma. Segun upstream/runtime puede
llegar `dict`, `list`, `tuple`, un `Event.output` ya desempaquetado o modelos ya
validados.

```python
def aggregate(node_input: Any) -> Event:
    joined = normalize_join_input(node_input)
    return Event(output=AggregateResult(results=joined))
```

## Multiples Triggers Iniciales

Se pueden iniciar varias ramas desde `START`:

```python
edges=[
    ("START", task_a),
    ("START", task_b),
    ("START", task_c),
]
```

Tambien aparece el patron `("START", (a, b, c), next_node)` donde varios nodos se
disparan sobre el mismo input y el siguiente nodo recibe disparos multiples.
Muestra oficial: `multi_triggers/agent.py`.

Cada nodo disparado directamente desde `START` sigue la regla `Any`/`Content` +
normalizacion. No tipar esos nodos como `str` o modelos Pydantic propios.

## Dynamic Fan-Out / Fan-In

Patron secundario. No recomendar ni implementar directamente salvo peticion
explicita o necesidad clara. Primero evaluar alternativas primarias:

- Fan-out/fan-in estatico con tuple + `JoinNode`.
- Multiples `START` si el paralelismo es fijo.
- Branches con `Event(route=...)` si las rutas son enumerables.

Cuando el numero de tareas depende realmente del input, comentar el tradeoff y
solo entonces usar un orquestador:

```python
@node(rerun_on_resume=True)
async def orchestrator(ctx: Context, node_input: Any):
    text = content_to_text(node_input)
    items = [item.strip() for item in text.split(",")]
    tasks = [ctx.run_node(worker, node_input=item, use_sub_branch=True) for item in items]
    results = await asyncio.gather(*tasks)
    yield Event(message=format_results(results))
```

Muestra oficial: `dynamic_fan_out_fan_in/agent.py`. Ver tambien
`references/09-secondary-dynamic-workflows.md`.

Usar `use_sub_branch=True` para aislar ejecuciones paralelas dinamicas.

## Dynamic Nodes Para Loops Complejos

Patron secundario. Preferir loop por route si el ciclo es simple y enumerable.
Usar un orquestador solo si el loop necesita codigo, checkpointing, counters,
condiciones complejas o varios sub-nodos internos. Primero explicar alternativas.

Un orquestador puede llamar agentes en un `while`:

```python
@node(rerun_on_resume=True)
async def orchestrate(ctx: Context, node_input: Any):
    topic = content_to_text(node_input)
    yield Event(state={"topic": topic})
    while True:
        candidate = await ctx.run_node(generate)
        feedback = Feedback.model_validate(await ctx.run_node(evaluate, node_input=candidate))
        if feedback.grade == "ok":
            yield candidate
            break
```

Muestra oficial: `dynamic_nodes/agent.py`. Ver tambien
`references/09-secondary-dynamic-workflows.md`.

Incluir limite maximo en proyectos reales.

## Loops Por Ruta

Un edge puede devolver a un nodo anterior:

```python
edges=[
    ("START", process_input, generate, evaluate, route_result),
    (route_result, {"retry": generate}),
]
```

Muestra oficial: `loop/agent.py`.

Un nodo tambien puede rutear a si mismo:

```python
edges=[
    ("START", validate_input, guess_number),
    (guess_number, {"guessed_wrong": guess_number}),
]
```

Muestra oficial: `loop_self/agent.py`.

Riesgos:

- Loop infinito si no hay criterio de salida.
- Rutas no emitidas si el nodo falla antes de `Event(route=...)`.
- Necesidad de state para counters o feedback.

## Nested Workflows

Un `Workflow` puede ser nodo de otro workflow:

```python
sub_workflow = Workflow(name="sub", edges=[("START", a, b)])
root_agent = Workflow(name="parent", edges=[("START", sub_workflow, c)])
```

La documentacion indica que los eventos de nodos internos burbujean para
trazabilidad y que el parent usa la salida final de las hojas del nested workflow.

Muestra oficial `nested_workflow/agent.py` esta marcada como `NOT WORKING YET`;
usar como patron conceptual, no copiar sin validar.

## Retry

Usar `RetryConfig` en nodos deterministas o llamadas fragiles:

```python
@node(retry_config=RetryConfig(max_attempts=5, initial_delay=1))
def get_weather(ctx: Context):
    yield Event(message=f"Getting weather... attempt {ctx.attempt_count}")
    ...
```

Muestra oficial: `retry/agent.py`.

No usar retry para ocultar bugs de schema o rutas incorrectas.

## Parallel Worker

La muestra `parallel_worker/agent.py` usa `@node(parallel_worker=True)` y agentes
con `parallel_worker=True` para procesar listas. Esta muestra esta marcada como
`NOT WORKING YET`; tratarla como API exploratoria hasta validar con la version
instalada.
