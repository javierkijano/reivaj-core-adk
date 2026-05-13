# Data Handling In Workflow Nodes

## Eventos

Los nodos consumen y emiten datos mediante `Event`.

Parametros clave:

- `output`: dato para el siguiente nodo.
- `message`: respuesta o progreso visible para el usuario.
- `state`: estado pequeno persistido durante la session/workflow.
- `route`: decision de routing para branch edges.
- `partial=True`: chunk de mensaje parcial/streaming de mensaje, no Live Streaming
  de workflow completo.

## `Event.output`

Usar para pasar datos internos:

```python
def parse(node_input: str):
    return Event(output={"text": node_input.strip()})
```

Si una funcion devuelve un valor simple, el framework puede envolverlo como
output:

```python
def normalize(node_input: str):
    return node_input.upper()
```

Limitacion critica: un nodo solo puede emitir un `Event.output` por ejecucion.
Puede emitir varios mensajes, pero no varios outputs.

## `Event.message`

Usar solo para usuario/progreso:

```python
async def notify_start():
    yield Event(message="Beginning research process...")
```

No usar `message` para alimentar el siguiente nodo. Para eso usar `output` o
`state`.

El sample `message/agent.py` muestra:

- Mensajes string.
- Mensajes multimodales con `types.Part`.
- Multiples mensajes desde el mismo nodo.
- Chunks con `partial=True`.

## `Event.state` Y `ctx.state`

Usar para datos pequenos de sesion:

```python
def process_input(node_input: str):
    return Event(state={"original_text": node_input})

def read_state(ctx: Context):
    return ctx.state["original_text"].upper()

def read_state_via_param(original_text: str):
    return original_text.upper()
```

El sample `state/agent.py` muestra tres formas:

- Modificar `ctx.state[...]` directamente.
- Emitir `Event(state={...})`.
- Recibir state keys como parametros de funcion.

No guardar datos grandes en state. Para documentos, archivos, datasets o caches,
usar artifacts, storage o tools/database.

## Schemas Pydantic

Para contratos robustos:

```python
class FlightSearchInput(BaseModel):
    origin: str
    destination: str

class FlightSearchOutput(BaseModel):
    flights: list[str]

flight_searcher = Agent(
    name="flight_searcher",
    instruction="Search for available flights.",
    input_schema=FlightSearchInput,
    output_schema=FlightSearchOutput,
)
```

Tambien se puede tipar una FunctionNode:

```python
def consume(node_input: FlightSearchOutput):
    return len(node_input.flights)
```

El sample `node_output/agent.py` muestra retorno string, `Event(output=...)`,
`Agent(output_schema=...)` y consumo tipado. Esta muestra esta marcada `NOT
WORKING YET` para output passing desde LLM; validar con la version instalada.

## Instrucciones Con Datos Estructurados

La documentacion muestra dos formas de acceder datos en instrucciones:

```python
instruction="It is {CityTime.time_info} in {CityTime.city}."
```

Y con fuente explicita:

```python
instruction="""
It is <CityTime.time_info from lookup_time_function> in
<CityTime.city from lookup_time_function>.
"""
```

Usar fuente explicita cuando varios nodos producen el mismo schema o campos con
nombres repetidos.

## `output_key`

Algunos samples usan `output_key` para guardar salida en state:

```python
classify_input = Agent(
    name="classify_input",
    output_schema=InputCategory,
    output_key="category",
)
```

Esto permite que nodos posteriores accedan al dato por parametro o instruction.

## `use_as_output`

El sample `use_as_output/agent.py` muestra un orquestador que llama un nodo y usa
su resultado como output del orquestador:

Este es un patron dinamico secundario. No usarlo como default si una secuencia
normal con `Workflow(edges=[...])` expresa el flujo con claridad.

```python
@node(rerun_on_resume=True)
async def orchestrate(ctx: Context, node_input: str) -> str:
    return await ctx.run_node(summarizer, node_input=node_input, use_as_output=True)
```

Usar cuando un nodo dinamico interno debe ser la salida canonica del nodo
orquestador.

## Checklist De Datos

- Cada nodo tiene input y output esperados documentados.
- Cada frontera LLM/funcion critica tiene schema.
- `message` solo se usa para usuario.
- `state` solo guarda datos pequenos.
- No hay dos `Event.output` en el mismo nodo.
- Las instructions usan `{field}` o `<field from node>` cuando consumen datos
  estructurados.
