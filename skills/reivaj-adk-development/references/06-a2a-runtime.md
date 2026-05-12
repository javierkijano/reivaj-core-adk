# 06. A2A Y Runtime

A2A permite interoperabilidad agente-a-agente. En ADK puede usarse para exponer
un agente como servicio o consumir agentes remotos.

## Conceptos

| Concepto | Uso |
|---|---|
| Agent Card | Descripcion publica del agente, capacidades y endpoint |
| `A2aAgentExecutor` | Executor ADK para peticiones A2A |
| `AgentCardBuilder` | Construccion dinamica de Agent Card |
| `to_a2a(root_agent, ...)` | Exponer agente en servidor A2A standalone/local |
| `RemoteA2aAgent` | Consumir un agente A2A remoto como agente/herramienta |
| A2A extension URI | Capacidades especificas ADK |
| Agent Runtime | Plataforma gestionada para ejecutar agentes |

## Exponer Agente

Opciones:

- `to_a2a(root_agent, ...)` para escenarios standalone/locales.
- Wiring manual con `A2aAgentExecutor`, `AgentCardBuilder` y runtime propio.
- Agent Runtime para despliegue gestionado.

Extension URI estudiada:

```text
https://google.github.io/adk-docs/a2a/a2a-extension/
```

## Consumir Agente Remoto

Preferencia investigada:

```python
RemoteA2aAgent(..., use_legacy=False)
```

Usar remoto cuando:

- Otro equipo publica una capacidad ya operativa.
- Se quiere desacoplar dominios.
- El agente proveedor tiene credenciales/herramientas que no deben replicarse.

## Agent Runtime

Notas generales:

- Validar region, proyecto, service accounts y secrets.
- Streaming puede estar limitado segun runtime.
- Usar artifact service adecuado: in-memory para local, GCS para runtime si hay
  outputs persistentes.
- Registrar feedback como operacion separada si el runtime lo soporta.
- No desplegar sin aprobacion.

## Muestras Relevantes

- `a2a_basic`
- `a2a_root`
- agent runtime templates generados por agents-cli
