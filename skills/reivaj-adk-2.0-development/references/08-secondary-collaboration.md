# Secondary Pattern: Collaborative Agents

Fuente estudiada: `https://adk.dev/workflows/collaboration/`.

## Politica De Uso

Collaborative agents es un patron secundario para esta skill. No recomendarlo ni
implementarlo directamente salvo que:

- El usuario pida explicitamente collaborative agents, coordinator agents,
  subagent modes, `mode="task"` o `mode="single_turn"`.
- El problema necesite delegacion menos estructurada, con subagentes expertos y
  retorno automatico al coordinador.
- Un grafo `Workflow` estatico se vuelva artificial, fragil o demasiado rigido
  para el proceso real.

Antes de implementarlo, comentar alternativas primarias:

- Workflow graph con rutas explicitas.
- `JoinNode` para paralelismo controlado.
- Workflow anidado para subprocesos reutilizables.
- Agent nodes `single_turn` dentro de un workflow si el control-flow debe ser
  determinista.

No implementar collaborative agents directamente por comodidad.

## Que Es

Un equipo colaborativo usa un coordinator/root agent con `sub_agents`. El
coordinador delega tareas a subagentes especializados y estos retornan al padre
automaticamente en modos `task` o `single_turn`.

Ejemplo conceptual:

```python
weather_agent = Agent(
    name="weather_checker",
    mode="single_turn",
    tools=[get_weather],
)

flight_agent = Agent(
    name="flight_booker",
    mode="task",
    input_schema=FlightInput,
    output_schema=FlightResult,
    tools=[search_flights, book_flight],
)

root_agent = Agent(
    name="travel_planner",
    sub_agents=[weather_agent, flight_agent],
)
```

El parent auto-inyecta herramientas de delegacion tipo `request_task_<subagent>`.

## Modos

| Mode | Uso | HITL | Retorno | Paralelo |
|---|---|---|---|---|
| `chat` | Conversacion libre, default | Completo | Manual | No soportado |
| `task` | Subtarea con posibles aclaraciones | Solo aclaraciones | Automatico con `complete_task` | No soportado |
| `single_turn` | Tarea cerrada sin usuario | No permitido | Automatico con resultado | Puede ejecutarse en paralelo |

Regla critica: `mode` es para subagentes invocados por un parent, no para root
agent.

## Cuando Conviene

- El proceso requiere subagentes expertos con autonomia limitada.
- La delegacion exacta depende de razonamiento del coordinador.
- Las subtareas son sustanciales, no simples transforms.
- El retorno automatico al coordinador mejora control frente a `chat` default.
- `single_turn` permite paralelizar tareas independientes con contexto aislado.

## Cuando No Conviene

- El flujo requiere orden, rutas y joins deterministas: usar `Workflow` graph.
- Solo hay pasos fijos: usar edges secuenciales.
- El subagente debe tener subagentes propios: task mode agents deben ser leaf.
- Se necesita observar/controlar cada branch como DAG explicito.

## Contexto De Invocacion

El comportamiento al completar depende de como se invoca:

- Como nodo de workflow graph: avanza al siguiente nodo del grafo.
- Transferido desde `LlmAgent`: retorna al agente que llamo tras `complete_task`.

Esto permite reutilizar el mismo task agent en ambos contextos, pero obliga a
documentar el modo de invocacion.

## Aislamiento De Contexto

Task/single-turn agents operan en ramas de sesion aisladas. En paralelo, cada
subagente ve solo su branch, no los eventos de peers. El parent recibe resultados
al terminar las ramas.

## Checklist Antes De Usar

- Usuario pidio este patron o hay necesidad clara.
- Se explicaron alternativas de `Workflow` graph.
- Los subagentes tienen `input_schema` / `output_schema` si el resultado es usado
  por codigo.
- Los subagentes `task` son leaf agents.
- No se configura `mode` en root agent.
- Se prueba retorno automatico al parent.
- Si hay paralelismo, solo se usan subagentes `single_turn`.
