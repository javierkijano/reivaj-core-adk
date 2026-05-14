# Official Workflow Samples Catalog

Fuente: `google/adk-python` rama `v2`, `contributing/workflow_samples`.

## Catalogo Rapido

| Sample | Patron | Leccion |
|---|---|---|
| `sequence` | Secuencia simple | `Workflow(edges=[("START", a, b)])` es reemplazo directo de pasos lineales. |
| `route` | Clasificar y branch | Router emite `Event(route=...)`; dict de routes decide siguiente nodo. |
| `fan_out_fan_in` | Paralelismo + join | Tuple de nodos paralelos + `JoinNode` + agregador. |
| `dynamic_fan_out_fan_in` | Fan-out dinamico secundario | Orquestador `@node` usa `ctx.run_node` y `asyncio.gather`; usar solo tras descartar fan-out estatico/JoinNode. |
| `dynamic_nodes` | Loop/orquestacion dinamica secundaria | `ctx.run_node` dentro de `while`; usar solo cuando route-loop sea insuficiente. |
| `loop` | Loop por route | Edge desde router de vuelta al generador. |
| `loop_self` | Nodo que se llama a si mismo | El propio nodo emite route para repetir. |
| `nested_workflow` | Workflow como nodo | Concepto util, sample marcado `NOT WORKING YET`. |
| `state` | State handling | `ctx.state`, `Event(state=...)`, parametros inyectados. |
| `node_output` | Outputs y Pydantic | Strings, Events y schemas; sample marcado `NOT WORKING YET`. |
| `use_as_output` | Output de nodo dinamico | `ctx.run_node(..., use_as_output=True)`. |
| `message` | Mensajes usuario | Strings, multimodal, multiples mensajes, partial chunks. |
| `request_input` | HITL simple | Revision humana dedicada; no usar como front-door conversacional. |
| `request_input_advanced` | HITL schema/payload | Decision determinista decide si pedir humano; mejor patron que pedir HITL sin gate. |
| `request_input_rerun` | Resume robusto | `@node(rerun_on_resume=True)` + `ctx.resume_inputs`. |
| `multi_triggers` | Multiples disparos | Fan-out hacia un nodo siguiente sin join explicito. |
| `retry` | Retry determinista | `RetryConfig`, `ctx.attempt_count`, errores transitorios. |
| `parallel_worker` | Worker paralelo por item | API exploratoria; sample marcado `NOT WORKING YET`. |
| `auth_api_key` | Auth API key | `auth_config`, `credential_key`, `ctx.get_auth_response`. |
| `auth_oauth` | OAuth2 | OAuth authorization code flow en FunctionNode. |

## Samples Marcados Como No Listos

Los siguientes tienen comentario `NOT WORKING YET`:

- `nested_workflow/agent.py`
- `node_output/agent.py`
- `parallel_worker/agent.py`
- `request_input/agent.py`

No copiarlos literalmente sin validarlos contra la version instalada.
Aunque un sample muestre firmas estrechas, en codigo de proyecto todo
FunctionNode conectado directamente a `START` debe aceptar `Any` o `Content` y
normalizar `Content.parts` antes de schemas propios.

Lecciones HITL de samples:

- `request_input` es un workflow dedicado de revision, no un patron para root
  agents conversacionales.
- `request_input` esta marcado como `NOT WORKING YET`; no copiar literalmente.
- `request_input_advanced` muestra mejor separacion: una decision determinista
  decide si pedir humano o continuar.
- La doc indica que `RequestInput` puede pedir datos sin IA, pero
  `response_schema` no transforma respuestas libres; para UX normal, usar
  prompts simples o UI especifica.

## Patrones Reutilizables

### Clasificacion + routing

Usar schema `Literal` para controlar rutas:

```python
class InputCategory(BaseModel):
    category: Literal["question", "statement", "other"]
```

Si el workflow es `root_agent` conversacional, esta clasificacion debe ser una
politica de activacion antes de planners/tools/HITL, con rutas como `greeting`,
`thanks`, `small_talk`, `simple_question`, `ambiguous` y `workflow_request`.

### Join agregado

El agregador puede recibir dict por nombre de nodo, pero no debe asumirlo como
unica forma runtime:

```python
async def aggregate(node_input: Any):
    joined = normalize_join_input(node_input)
    yield Event(message=joined["make_uppercase"])
```

### Loop generate/evaluate

Mantener feedback en state o output_key:

```python
generate_headline = Agent(... instruction="The feedback: {feedback?}")
evaluate_headline = Agent(... output_schema=Feedback, output_key="feedback")
```

### Dynamic orchestrator

Patron secundario. Antes de usarlo, explicar alternativas primarias (`JoinNode`,
branches, route loops) y por que no bastan.

Usar `@node(rerun_on_resume=True)` cuando el nodo invoca otros nodos o puede
reanudar:

```python
tasks = [ctx.run_node(generator, node_input=item, use_sub_branch=True) for item in items]
results = await asyncio.gather(*tasks)
```

### Human review loop

Pedir input humano, rutear y volver a draft si hay feedback:

```python
(handle_human_review, {"revise": draft_email, "approved": send_email})
```

### Retry

Usar mensajes de progreso con attempt count:

```python
yield Event(message=f"Getting weather... attempt {ctx.attempt_count}")
```

## Anti-Patrones Detectados En Samples

- Copiar samples con `NOT WORKING YET` sin probar.
- Usar loops sin limite maximo en sistemas reales.
- Exponer un workflow especializado como root conversacional sin `intent_gate`.
- Usar `RequestInput` como compuerta generica para saludos o inputs ambiguos.
- Tipar el primer FunctionNode desde `START` como `str`, union estrecha o modelo
  Pydantic propio.
- Tipar el agregador post-`JoinNode` como una unica forma sin normalizador.
- Imprimir credenciales aunque sea enmascaradas sin necesidad.
- Depender de nombres de nodos implicitos sin documentar output contract.
- Mezclar mensaje de usuario y datos internos.
