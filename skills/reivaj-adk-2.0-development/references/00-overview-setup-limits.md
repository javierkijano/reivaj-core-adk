# ADK 2.0 Overview, Setup And Limits

Fuentes estudiadas:

- `https://adk.dev/2.0/`
- `https://adk.dev/workflows/`
- `https://adk.dev/workflows/graph-routes/`
- `https://adk.dev/workflows/data-handling/`
- `https://adk.dev/workflows/human-input/`
- `google/adk-python` rama `v2`, directorio `contributing/workflow_samples`

## Estado Del Producto

ADK 2.0 esta en beta. La documentacion indica que puede introducir breaking
changes y no debe usarse cuando el proyecto requiera compatibilidad estricta o
estabilidad de produccion. Es compatible en principio con agentes ADK 1.x, pero
se esperan incompatibilidades en agentes avanzados.

## Instalacion

ADK 2.0 no se instala automaticamente mientras sea pre-GA. Requiere opt-in:

```bash
pip install google-adk --pre
```

En proyectos con `uv`, preferir expresar la dependencia en `pyproject.toml`:

```toml
dependencies = [
  "google-adk>=2.0.0b1",
]
```

Si existe ADK 1.x en el entorno, `--pre` puede no actualizarlo. La documentacion
menciona `--force`, pero en proyectos reales es mejor crear un entorno nuevo y
mantener backup antes de migrar.

## Que Aporta Workflow 2.0

- Grafos explicitos de ejecucion con nodos y edges.
- Combinacion de agentes LLM, funciones Python, Tools, workflows anidados,
  human input y auth.
- Routing determinista y branches por `Event(route=...)`.
- Control preciso de datos entre nodos con `Event(output=...)`, `Event(state=...)`
  y schemas.
- Orquestacion dinamica con `Context.run_node` cuando el usuario lo pida o el
  grafo estatico sea claramente peor; tratarlo como patron secundario.
- Mayor predictibilidad que prompts largos con instrucciones procedimentales.

## Cuando Usarlo

Usar Workflow 2.0 cuando:

- El proceso tiene pasos obligatorios que no deben quedar a criterio del LLM.
- Hay rutas, branches, retries, joins, HITL o autorizaciones.
- Hay que mezclar codigo determinista y razonamiento LLM.
- El flujo necesita trazabilidad por nodos.
- La fragilidad principal esta en control-flow, no en calidad de lenguaje.

No usar Workflow 2.0 cuando:

- Un solo `Agent` con herramientas resuelve el problema de forma robusta.
- La organizacion exige estabilidad GA o compatibilidad estricta ADK 1.x.
- El requisito principal es Live Streaming.
- Las integraciones requeridas no han sido validadas con workflows.

## Limitaciones Conocidas

- Live Streaming no es compatible con graph-based workflows.
- Algunas integraciones de terceros pueden no ser compatibles.
- No todos los nodos/agentes son seguros para paralelismo.
- Multiples sesiones interactivas de chat en paralelo dentro de la misma session
  no son una forma valida de paralelismo.
- `JoinNode` se queda atascado si algun upstream no emite salida.
- `Event.output` solo puede emitirse una vez por ejecucion de nodo.

## Migracion Desde ADK 1.x

Regla practica:

- `SequentialAgent` -> `Workflow(edges=[("START", a, b, c)])`.
- `ParallelAgent` -> fan-out con tuple o multiples `START` + `JoinNode`.
- `LoopAgent` -> primero edge de vuelta condicionado por `Event(route=...)`; solo
  usar nodo orquestador con `while` y `Context.run_node` si el loop necesita
  logica programatica compleja y tras explicar alternativas.
- `BaseAgent` custom que solo transforma estado -> FunctionNode que emite
  `Event(output=...)` o `Event(state=...)`.

Migrar solo si aporta control o simplifica. No migrar YAML/ADK 1.x estable solo
por novedad.
