# Implementation Playbook

## 1. Antes De Codificar

Definir una tabla de nodos:

| Nodo | Tipo | Input | Output | State keys | Route | Error handling |
|---|---|---|---|---|---|---|
| `parse_request` | function | user text | `RequestSpec` | none | none | validation message |
| `classify` | Agent | `RequestSpec` | `Category` | `category` | none | schema failure |
| `route_category` | function | `Category` | none | none | category literal | default route |

No empezar por prompts largos. Empezar por grafo y contratos.

## 2. Elegir Tipos De Nodos

- Funcion Python: transformacion determinista, validacion, routing, formatting.
- Agent: clasificacion semantica, extraccion incierta, generacion, evaluacion LLM.
- Tool: accion externa encapsulada.
- Workflow anidado: subproceso reusable con contrato claro.
- JoinNode: fan-in de ramas paralelas estaticas.
- Orquestador `@node`: patron secundario para fan-out dinamico, loops con codigo
  o HITL/resume complejo; explicar alternativas antes de usarlo.

## 3. Plantilla Secuencial

```python
from google.adk import Agent, Event, Workflow
from pydantic import BaseModel

class ParsedRequest(BaseModel):
    topic: str

def parse_request(node_input: str):
    return Event(output=ParsedRequest(topic=node_input.strip()))

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

## 4. Plantilla De Routing

```python
class RouteDecision(BaseModel):
    route: Literal["fast", "deep", "unsupported"]

classifier = Agent(..., output_schema=RouteDecision)

def route(decision: RouteDecision):
    return Event(route=decision.route)

root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", classifier, route),
        (route, {"fast": fast_path, "deep": deep_path, "unsupported": unsupported}),
    ],
)
```

## 5. Plantilla Fan-Out/Fan-In

```python
join = JoinNode(name="join_results")

def aggregate(node_input: dict[str, Any]):
    return Event(output=AggregateResult(...))

root_agent = Workflow(
    name="root_agent",
    edges=[("START", (branch_a, branch_b, branch_c), join, aggregate, final)],
)
```

Cada branch debe emitir output. Si una branch puede fallar, capturar excepcion y
emitir un resultado de error estructurado.

## 6. Plantilla Dynamic Fan-Out

No usar esta plantilla por defecto. Primero intentar fan-out estatico con
`JoinNode` o branches enumerables. Usarla solo si el cardinal de tareas depende
del runtime o si el grafo estatico seria artificialmente complejo. Antes de
implementarla, comentar el tradeoff al usuario.

```python
@node(rerun_on_resume=True)
async def orchestrate(ctx: Context, node_input: BatchSpec):
    tasks = [
        ctx.run_node(worker, node_input=item, use_sub_branch=True)
        for item in node_input.items
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return normalize_results(results)
```

Usar `return_exceptions=True` en sistemas reales para evitar que una branch mate
todo el batch sin salida diagnosable.

## 7. Plantilla HITL

```python
@node(rerun_on_resume=True)
def approve(ctx: Context, proposal: Proposal):
    resume = ctx.resume_inputs.get("approval")
    if resume is None:
        yield RequestInput(
            interrupt_id="approval",
            message="Approve this proposal?",
            payload=proposal,
            response_schema=ApprovalDecision,
        )
        return
    decision = ApprovalDecision.model_validate(resume)
    yield Event(route="approved" if decision.approved else "rejected")
```

## 8. Validaciones Obligatorias

- Import smoke test: el modulo exporta `root_agent` y es `Workflow`.
- No hay edges con route keys imposibles.
- Cada branch hacia `JoinNode` emite output.
- Cada loop tiene criterio de salida o limite.
- Cada HITL tiene path de resume.
- Cada nodo con auth enmascara credenciales.
- Schemas Pydantic validan outputs de LLM usados para routing.

## 9. Migration Playbook

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

## 10. Definition Of Done

- El grafo es legible sin leer prompts largos.
- Los contratos de datos estan expresados con schemas o docstrings.
- Las rutas son enumeradas y testeables.
- Los nodos fallan con mensajes accionables.
- Los outputs finales salen por `Event(message=...)`.
- Los datos internos no dependen de mensajes visibles.
- Tests deterministas pasan; evals quedan para comportamiento LLM.
