# Testing And Debugging ADK 2.0 Workflows

## Tests Deterministas

Probar con pytest:

- Import/export del modulo y tipo de `root_agent` como `Workflow`.
- En proyectos `agents-cli`, `App.name` coincide con
  `[tool.agents-cli].agent_directory`. Si existe un `agent.py` raiz para soportar
  `adk web <agents_dir>`, exporta solo `root_agent`, no `app`.
- Primer nodo conectado a `START` con
  `Content(role="user", parts=[Part(text="...")])`.
- Funciones deterministas de parsing, routing y aggregation.
- Schemas Pydantic.
- Rutas exactas con cada route key.
- Workflows expuestos a chat: no activacion para saludos, thanks, input vacio y
  mensajes ambiguos.
- Workflows expuestos a chat: activacion solo con intencion explicita suficiente.
- Branches hacia `JoinNode` siempre emiten output.
- Post-`JoinNode` normaliza `dict`, `list`, `tuple`, `Event.output` o modelos ya
  validados.
- Fallbacks de branch.
- Reintentos simulando errores transitorios.
- HITL: primera ejecucion emite `RequestInput`, resume procesa respuesta.
- HITL: ningun saludo produce `RequestInput`; `RequestInput` solo aparece despues
  de `intent_gate` y bajo politica HITL.

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

## Smoke Test De Frontera START

```python
from google.genai.types import Content, Part

from app.agent import ParsedRequest, parse_request


def test_first_node_accepts_content():
    event = parse_request(Content(role="user", parts=[Part(text="research ADK")]))
    assert event.output == ParsedRequest(topic="research ADK")
```

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

## Tests De Activacion Conversacional

Obligatorios si el `Workflow` es `root_agent` expuesto a chat/playground:

- `Hola` responde con `Event(message=...)` y no llega al planner.
- `Gracias` responde natural y no ejecuta tools.
- String vacio pide aclaracion.
- `ADK` pide aclaracion si no hay intencion explicita.
- `Investiga ADK 2.0 Workflow con fuentes` llega al planner.
- Ningun saludo produce `RequestInput`.
- Ningun saludo ejecuta proveedores/tools.
- `RequestInput` solo aparece despues de `intent_gate` y bajo la politica HITL.
- El primer nodo acepta `Content` y normaliza antes de validar schema propio.

Si estos tests fallan, el problema no es la firma `Any`; falta una politica de
activacion o esta situada demasiado tarde.

## Debug De Activacion Incorrecta

Sintomas:

- `Hola` termina en `planning_node`.
- Small talk dispara tools/proveedores.
- Input ambiguo produce `RequestInput`.
- Confirmaciones sueltas activan un workflow sin contexto.

Checklist:

- El grafo distingue `general_chat_root_agent` de `dedicated_workflow`.
- Hay `intent_gate` antes de planner/tools/HITL.
- `greeting`, `thanks`, `small_talk`, `simple_question` y `ambiguous` tienen
  handlers que devuelven `Event(message=...)` directamente.
- La ruta `workflow_request` requiere triggers explicitos o confianza alta.
- `RequestInput` no se usa como pregunta generica de activacion.

## Debug De FunctionNode Binder

Sintoma:

```text
ValidationError for union[str, ResearchQuery] ... input_type=Content
```

Causa probable: un nodo conectado directamente a `START` tiene una firma runtime
demasiado estrecha (`str`, `ResearchQuery`, union estrecha o modelo Pydantic). ADK
valida las annotations antes de ejecutar la funcion, asi que el nodo falla antes
de poder normalizar `Content.parts`.

Solucion: cambiar la firma a `Any` o `Content`, normalizar internamente y validar
despues con el schema propio. Anadir un test con
`Content(role="user", parts=[Part(text="...")])`.

## Debug De Joins

Sintoma: workflow queda atascado en `JoinNode`.

Checklist:

- Todos los upstreams llegan al mismo `JoinNode`.
- Todos los upstreams emiten output aun en errores.
- No hay branch que emita solo `message` y no output.
- El agregador acepta `Any` y normaliza dict/list/tuple/output/modelos.
- El agregador no asume una unica forma post-join sin test.

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
- Normalizar respuestas `str`, `dict` o payload estructurado antes de validar.
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
- Duplicar entrypoints ADK exportando `app` desde ambos (`app/agent.py` y
  `agent.py` raiz) en proyectos `agents-cli`, provocando `Session not found` por
  mismatch entre app name del runner y directorio desde el que ADK cargo el
  agente. El entrypoint raiz para `adk web <agents_dir>` debe exportar solo
  `root_agent`.
- Introducir Workflow 2.0 en proyecto ADK 1.x sin actualizar dependencia.
- Pasar datos internos por `message`.
- Exponer un workflow especializado a chat general sin front-door de intencion.
- Tratar `str(node_input)` como tarea valida solo porque la firma acepta `Any`.
- Usar `RequestInput` para decidir si un saludo debe activar el workflow.
- Firmar el primer FunctionNode desde `START` como `str`, union estrecha o modelo
  Pydantic y fallar con `input_type=Content`.
- Usar rutas libres generadas por LLM sin `Literal`/schema.
- Joins sin fallback output.
- Agregador post-`JoinNode` tipado como una unica forma sin normalizador.
- Loops sin limite.
- HITL sin `interrupt_id` o sin normalizar `ctx.resume_inputs`.
- Auth que muestra secretos.
- Copiar samples marcados `NOT WORKING YET` sin validar.
