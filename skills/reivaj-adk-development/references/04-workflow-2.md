# 04. ADK 2.0 Workflow

ADK 2.0 Workflow introduce orquestacion basada en grafos. Es beta/pre-GA y debe
ser opt-in cuando se migra un proyecto existente.

## Conceptos

| Concepto | Descripcion |
|---|---|
| `Workflow` | Grafo de nodos conectados por rutas |
| Node | Unidad de trabajo: funcion, agente, join, tool wrapper, etc. |
| Route | Selecciona el siguiente nodo o camino |
| `Event` | Transporta `state`, `output`, `message`, `route` |
| `FunctionNode` | Nodo Python funcional |
| `JoinNode` | Fan-in / union de resultados paralelos |
| `RetryConfig` | Politicas de reintento |
| `RequestInput` | Entrada de request |
| `ResumabilityConfig` | Reanudacion de ejecuciones |

Simbolos verificados localmente:

- `Workflow`
- `FunctionNode`
- `JoinNode`
- `BaseNode`
- `node`
- `RetryConfig`
- `RequestInput`
- `App`
- `ResumabilityConfig`

Patrones `Event(...)` verificados:

```python
Event(message=...)
Event(route=...)
Event(state=...)
Event(output=..., route=..., state=..., message=...)
```

## Cuando Workflow Aporta Valor

- Pipeline con control flow determinista.
- Rutas condicionales explicitas.
- Fan-out/fan-in paralelo.
- Human-in-the-loop e interrupts.
- Reintentos por nodo.
- Tipado fuerte de outputs.
- Sustituir `SequentialAgent` / `LoopAgent` deprecados en ADK 2.0 beta.
- Procesamiento dinamico de listas o tareas generadas por el modelo.

## Riesgos

- API beta/pre-GA, sujeta a cambios.
- Requiere `google-adk >= 2.0.0` y Python >= 3.11.
- Incompatible con Live Streaming segun notas locales de skills.
- No se observo soporte directo en Agent Config YAML.
- Puede cambiar forma de estado, eventos, tests y depuracion.

## Estrategia De Migracion

1. Pedir opt-in explicito.
2. Congelar comportamiento actual con tests/evals.
3. Mapear agentes existentes a nodos.
4. Definir contratos Pydantic para inputs/outputs.
5. Convertir loops en rutas dinamicas con condicion de salida.
6. Convertir paralelismo en fan-out/fan-in cuando tenga beneficio claro.
7. Preservar callbacks o moverlos a nodos deterministas.
8. Validar con imports, unit tests y evals aprobadas.

## Patrones

| Patron | Uso |
|---|---|
| Sequential graph | Sustituye pipeline lineal |
| Conditional route | Evaluador decide pass/fail, approve/revise, safe/block |
| Dynamic workflow | Iteraciones o tareas generadas en runtime |
| Fan-out/fan-in | Investigar secciones, documentos o queries en paralelo |
| HITL interrupt | Aprobacion humana antes de accion irreversible |
| Retry node | Llamadas tool/API fragiles |

## Muestras Relevantes

- `workflow-concurrent_research_writer`: fan-out/fan-in de investigacion y escritura.
- `workflows-sequential`: ejemplo basico de secuencia.
- `deep-search`: blueprint funcional que podria migrarse a Workflow.
