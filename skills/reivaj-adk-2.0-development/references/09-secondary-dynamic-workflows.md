# Secondary Pattern: Dynamic Workflows

Fuente estudiada: `https://adk.dev/workflows/dynamic/`.

## Politica De Uso

Dynamic workflows es un patron secundario. No recomendar ni implementar
directamente salvo que:

- El usuario pida explicitamente dynamic workflows, `Context.run_node`, nodos
  dinamicos, loops programaticos o checkpointing dinamico.
- El numero de nodos o branches depende del runtime y no puede representarse de
  forma limpia con graph routes.
- El control-flow requiere `while`, recursion, condiciones complejas,
  `asyncio.gather`, custom resume logic o encapsulacion programatica.

Antes de usarlo, comentar alternativas primarias:

- Secuencia con `Workflow(edges=[("START", ...)])`.
- Branches con `Event(route=...)`.
- Fan-out/fan-in estatico con tuple + `JoinNode`.
- Loops por route cuando el ciclo es simple y enumerable.

No implementar dynamic workflows directamente solo porque Python sea mas comodo.

## Que Es

Dynamic workflows permiten poner control-flow en codigo usando `@node` y
`ctx.run_node(...)`. El root sigue siendo un `Workflow`, pero la logica compleja
vive dentro de un nodo orquestador.

```python
@node(rerun_on_resume=True)
async def my_workflow(ctx: Context, node_input: Any) -> str:
    text = content_to_text(node_input)
    result = await ctx.run_node(my_node, node_input=text)
    return result

root_agent = Workflow(
    name="root_agent",
    edges=[("START", my_workflow)],
)
```

Si `my_workflow` es root expuesto a chat general, no debe ser el primer nodo
especializado. Agregar antes `intent_gate` y rutear a `my_workflow` solo en
`workflow_request`.

## Building Blocks

- `@node`: wrapper conveniente para convertir funciones en workflow nodes.
- `FunctionNode`: wrapper explicito util para librerias externas, multiples
  configuraciones o registries.
- `Context.run_node`: ejecuta un nodo y retorna su output directamente.
- `rerun_on_resume=True`: necesario en parent nodes que llaman `ctx.run_node` si
  puede haber interrupciones o resume.
- IDs deterministas: ADK checkpointa sub-nodos exitosos y los salta al reanudar.

## Data Handling

En dynamic workflows, `ctx.run_node` devuelve el output directamente:

```python
raw_draft = await ctx.run_node(draft_agent, user_request)
formatted = await ctx.run_node(format_function_node, raw_draft)
return formatted
```

Tambien admite schemas:

```python
city_time = await ctx.run_node(city_time_function, "Paris")
report = await ctx.run_node(city_report_agent, city_time)
```

## Loops Programaticos

Usar cuando el loop no es una simple route:

```python
@node
async def code_workflow(ctx: Context, user_request: Any):
    request_text = content_to_text(user_request)
    code = await ctx.run_node(coder_agent, request_text)
    check = await ctx.run_node(compile_lint_check, code)
    while check.findings:
        yield Event(state={"code": code, "findings": check.findings})
        code = await ctx.run_node(fixer_agent, {"code": code, "findings": check.findings})
        check = await ctx.run_node(compile_lint_check, code)
    return code
```

En produccion, agregar limite maximo, diagnostics y salida de fallo.

## Paralelismo Programatico

Usar `asyncio.gather` cuando el fan-out es dinamico:

```python
@node(rerun_on_resume=True)
async def parallel_supervisor(ctx: Context, items: list[Any], real_node: BaseNode):
    tasks = [ctx.run_node(real_node, item) for item in items]
    return await asyncio.gather(*tasks)
```

Tip oficial: al reanudar, el framework reejecuta solo workers fallidos o
interrumpidos.

## HITL En Dynamic Workflows

El parent que llama un nodo interactivo debe usar `rerun_on_resume=True`:

```python
@node(rerun_on_resume=False)
async def get_user_approval(ctx: Context, node_input: Any):
    yield RequestInput(message="Please approve this request (Yes/No)")

@node(rerun_on_resume=True)
async def handle_process(ctx: Context, node_input: Any):
    user_response = await ctx.run_node(get_user_approval)
    return "Approved" if user_response.lower() == "yes" else "Denied"
```

## Execution IDs

ADK genera IDs deterministas para sub-nodos a partir del parent ID y un contador.
Esto permite checkpointing y resume. Custom `run_id` existe, pero evitarlo salvo
necesidad fuerte.

Si se usa custom `run_id`:

- Debe ser determinista.
- Debe permanecer logicamente igual para el mismo input.
- Debe contener al menos un caracter no numerico para evitar colision con IDs
  secuenciales automaticos.

## Checklist Antes De Usar

- Usuario lo pidio o el grafo estatico seria claramente peor.
- Se explicaron alternativas primarias.
- Si el orquestador esta expuesto a chat, hay `intent_gate` previo.
- El orquestador tiene `rerun_on_resume=True` si llama nodos que pueden pausar.
- Loops tienen limite o criterio de salida verificable.
- Paralelismo usa `asyncio.gather` con manejo de errores cuando importa.
- `ctx.run_node` pasa schemas, no dicts ambiguos, en fronteras criticas.
- No se usan custom run IDs salvo necesidad documentada.
