# 02. Fundamentos ADK

## Agentes

| Concepto | Uso |
|---|---|
| `Agent` / `LlmAgent` | Agente LLM principal con instrucciones, modelo y herramientas |
| `BaseAgent` | Logica custom, control flow o eventos sin llamada LLM directa |
| `SequentialAgent` | Ejecuta subagentes en orden; en ADK 2.0 beta aparece deprecado frente a Workflow |
| `ParallelAgent` | Ejecuta subagentes en paralelo cuando el framework lo soporta |
| `LoopAgent` | Itera subagentes hasta max iterations o escalacion; deprecado frente a Workflow en ADK 2.0 beta |
| `Workflow` | Grafo beta/pre-GA para control flow explicito |

Ejemplo minimo code-first:

```python
from google.adk.agents import Agent

root_agent = Agent(
    name="assistant",
    model="gemini-flash-latest",
    instruction="You are a helpful assistant.",
    tools=[],
)
```

No cambiar `model=` en agentes existentes salvo peticion explicita.

## Modelos Y Vertex AI

Variables habituales:

```bash
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=global
```

Si un modelo devuelve 404, primero verificar region/model listing antes de
cambiar el modelo. `global` suele evitar problemas de disponibilidad regional.

## Planners Y Thinking

| Planner/config | Uso |
|---|---|
| `BasePlanner` | Interfaz base para planificacion |
| `BuiltInPlanner` | Usa thinking nativo del modelo mediante `ThinkingConfig` |
| `PlanReActPlanner` | Patron plan/reason/act para pasos explicitos |
| `thinking_config.include_thoughts` | Pide pensamientos/razonamiento cuando el modelo lo soporta |
| `thinking_config.thinking_budget` | Presupuesto de tokens de razonamiento |

Reglas:

- No activar thinking en agentes existentes sin opt-in.
- Si hay `planner.thinking_config` y `generate_content_config.thinking_config`,
  el planner puede prevalecer y generar warnings.
- En YAML, si no hay campo `planner` soportado por schema, usar
  `generate_content_config.thinking_config` solo tras aprobacion.
- Para workflows complejos, preferir control flow explicito frente a depender de
  razonamiento implicito del modelo.

## Herramientas

| Tipo | Uso |
|---|---|
| Funcion Python | Tool simple con docstring y type hints |
| `FunctionTool` | Wrapper explicito de funcion |
| Built-in tools | `google_search`, `load_web_page`, retrieval, etc. |
| `AgentTool` | Usar un subagente como herramienta |
| Toolsets | MCP, OpenAPI, Google API, SkillToolset, retrieval |
| Plugins | Modificar comportamiento transversal de app/model/tool calls |

Import correcto para algunos built-ins:

```python
from google.adk.tools.load_web_page import load_web_page
```

Evitar:

```python
from google.adk.tools import load_web_page
```

## Callbacks

Callbacks comunes:

| Callback | Momento |
|---|---|
| `before_agent_callback` | Antes de ejecutar un agente |
| `after_agent_callback` | Despues de ejecutar un agente |
| `before_model_callback` | Antes de llamar al modelo |
| `after_model_callback` | Despues de llamar al modelo |
| `before_tool_callback` | Antes de ejecutar herramienta |
| `after_tool_callback` | Despues de ejecutar herramienta |

Ejemplo:

```python
from google.adk.agents.callback_context import CallbackContext

async def initialize_state(callback_context: CallbackContext) -> None:
    callback_context.state.setdefault("history", [])
```

Usar callbacks para inicializacion de estado, guardrails deterministas,
normalizacion de salidas, citaciones, auditoria o coleccion de metadata.

## Estado, Sesiones Y Artefactos

| Concepto | Uso |
|---|---|
| State | Datos estructurados de ejecucion: planes, evaluaciones, IDs, metadata |
| Session service | Persistencia de conversaciones/sesiones |
| Memory | Recuerdo entre sesiones cuando el producto lo requiere |
| Artifacts | Archivos, outputs grandes, binarios, reportes extensos |

Regla practica:

- Estado para claves pequenas y contratos entre nodos/agentes.
- Artefactos para datos grandes o binarios.
- Memoria para hechos/preferencias cross-session aprobadas por diseno.

## Plugins

Patrones investigados:

- `ReflectAndRetryToolPlugin` para robustez de tool calls.
- Debug logging plugin para inspeccion de requests/responses.
- Safety plugins o guardrails cuando el agente opera en dominios sensibles.

Usar plugins cuando una politica aplica transversalmente a muchos agentes o
herramientas.
