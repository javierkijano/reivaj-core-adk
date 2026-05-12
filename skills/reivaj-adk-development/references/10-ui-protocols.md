# 10. UI Protocols: AG-UI Y A2UI

AG-UI y A2UI resuelven problemas distintos. No sustituyen ADK ni A2A; se
integran cuando hay una interfaz de usuario que lo requiere.

## Comparacion

| Protocolo | Relacion | Uso |
|---|---|---|
| MCP | Agent <-> tools/data | Herramientas, recursos, APIs |
| A2A | Agent <-> agent | Interoperabilidad entre agentes |
| AG-UI | Agent <-> user-facing app | Eventos, estado, mensajes, tools frontend |
| A2UI | UI payload format | JSON declarativo para componentes UI |

## AG-UI

AG-UI es Agent-User Interaction Protocol.

Caracteristicas:

- Event-based.
- Bidireccional.
- Transport-agnostic.
- Puede usar SSE, webhooks, WebSockets u otros transportes.
- Puede frontar MCP/A2A mediante handshakes.
- Soporta herramientas definidas por frontend con JSON Schema.

Abstraccion central documentada:

```text
run(input: RunAgentInput) -> Observable<BaseEvent>
```

Familias de eventos:

- `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`
- `TEXT_MESSAGE_*`
- `TOOL_CALL_*`, `TOOL_CALL_RESULT`
- `STATE_SNAPSHOT`, `STATE_DELTA`
- `MESSAGES_SNAPSHOT`
- `ACTIVITY_*`
- `REASONING_*`
- `RAW`
- `CUSTOM`

Usar AG-UI cuando se necesite:

- Streaming de eventos a frontend.
- Sincronizacion de estado.
- Interrupts o aprobaciones humanas UI.
- Tools ejecutadas por el frontend.
- Visualizar razonamiento/actividad en cliente.

## A2UI

A2UI es formato declarativo de payload UI generado por agentes.

Caracteristicas:

- JSON declarativo, no codigo ejecutable.
- Componentes de catalogo preaprobado.
- Cards, forms, charts, tables y layouts.
- Transport-agnostic sobre A2A, MCP, REST, WebSockets, etc.
- Soporta generacion progresiva/streaming.
- Renderizable en web/mobile/desktop segun renderer.
- Apache 2.0; creado por Google con contribuciones open-source.

Integracion ADK estudiada:

- `a2ui-agent-sdk`
- `A2uiSchemaManager`
- `BasicCatalog`
- `CatalogConfig.from_path(...)` para catalogos custom.

Si `A2uiSchemaManager(catalogs=...)` omite catalogos, usa Basic Catalog con
componentes comunes como Text, Card, Button e Image.

Payload A2A:

```python
create_a2ui_part({"type": "Card", "props": {"title": "Hello"}})
```

Devuelve `DataPart` con metadata:

```json
{"mimeType": "application/json+a2ui"}
```

Versiones estudiadas:

| Version | Estado | Notas |
|---|---|---|
| v0.8 | estable/produccion | surfaces, components, data binding, adjacency-list model |
| v0.9 | actual | `createSurface`, client-side functions, custom catalogs, extension spec |

Usar A2UI cuando el agente debe emitir UI estructurada, no solo markdown.

## Referencias

- `https://docs.ag-ui.com/`
- `https://docs.ag-ui.com/agentic-protocols`
- `https://docs.ag-ui.com/llms.txt`
- `https://adk.dev/integrations/a2ui/`
- `https://a2ui.org/`
