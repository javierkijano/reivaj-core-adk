# Testing And Debugging ADK 2.0 Workflows

## Tests Deterministas

Probar con pytest:

- Import del modulo y tipo de `root_agent`.
- Funciones deterministas de parsing, routing y aggregation.
- Schemas Pydantic.
- Rutas con cada route key.
- Fallbacks de branch.
- Reintentos simulando errores transitorios.
- HITL: primera ejecucion emite `RequestInput`, resume procesa respuesta.

No usar pytest para verificar contenido creativo de LLM. Usar evals.

## Smoke Test De Import

```python
from google.adk import Workflow
from app.agent import root_agent

def test_root_agent_is_workflow():
    assert isinstance(root_agent, Workflow)
```

Si `Workflow` no es importable por version, comprobar dependencia `google-adk` y
si se instalo pre-release.

## Debug De Rutas

Sintomas:

- Branch no corre.
- Workflow termina antes de lo esperado.
- Nodo equivocado se ejecuta.

Checklist:

- El router emite `Event(route="exact_key")`.
- La key existe exactamente en el dict de edge.
- El output_schema del clasificador no permite valores fuera de ruta.
- No se esta devolviendo string cuando se necesita `Event(route=...)`.

## Debug De Joins

Sintoma: workflow queda atascado en `JoinNode`.

Checklist:

- Todos los upstreams llegan al mismo `JoinNode`.
- Todos los upstreams emiten output aun en errores.
- No hay branch que emita solo `message` y no output.
- El agregador espera las claves correctas, normalmente nombres de nodos.

## Debug De Data Passing

Sintomas:

- Parametro de funcion no recibe dato esperado.
- Agent instruction muestra placeholders vacios.
- Pydantic falla validacion.

Checklist:

- Usar `Event(output=...)` para pasar dato al siguiente nodo.
- Usar `Event(state={...})` o `output_key` para keys persistidas.
- Confirmar nombres exactos de schema y campos en instruction.
- Si hay varios producers del mismo schema, usar `<field from node_name>`.
- No emitir mas de un `Event.output` por ejecucion.

## Debug De HITL/Resume

Sintomas:

- El nodo pide input otra vez infinitamente.
- La respuesta humana no llega al handler.
- La ruta approve/reject no dispara.

Checklist:

- Nodo decorado con `@node(rerun_on_resume=True)` cuando debe reanudarse.
- `interrupt_id` estable.
- Leer `ctx.resume_inputs[interrupt_id]`.
- Retornar despues de `RequestInput` si no hay resume input.
- Validar respuesta antes de route.

## Debug De Auth

Checklist:

- `auth_config` adjunto al nodo con `@node(auth_config=..., rerun_on_resume=True)`.
- `credential_key` estable.
- `ctx.get_auth_response(auth_config)` retorna credencial.
- Env vars para OAuth existen.
- No imprimir tokens.

## Comandos Utiles

En proyecto agents-cli:

```bash
agents-cli info
agents-cli lint
uv run pytest tests/unit
```

Para comportamiento LLM, usar `agents-cli eval run` solo con aprobacion.
Para playground o deploy, pedir aprobacion explicita.

## Fallos Comunes

- Tratar Workflow 2.0 como estable GA.
- Introducir Workflow 2.0 en proyecto ADK 1.x sin actualizar dependencia.
- Pasar datos internos por `message`.
- Usar rutas libres generadas por LLM sin `Literal`/schema.
- Joins sin fallback output.
- Loops sin limite.
- HITL sin `interrupt_id`.
- Auth que muestra secretos.
- Copiar samples marcados `NOT WORKING YET` sin validar.
