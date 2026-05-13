# 05. Tools, Grounding Y Citaciones

## Herramientas Built-in Y Toolsets

| Herramienta | Uso |
|---|---|
| `google_search` | Busqueda web publica y grounding con Google Search |
| `load_web_page` | Cargar contenido de paginas especificas |
| `VertexAiSearchTool` / Agent Platform Search | Busqueda en corpus/datastore propio |
| OpenAPI tools | APIs externas descritas por OpenAPI |
| MCP toolset | Herramientas y datos via MCP |
| Google API tools | Integraciones con APIs Google |
| API Hub / API Registry tools | Convertir APIs documentadas o servicios Google Cloud en tools/MCP |
| Application Integration tools | Conectores enterprise para apps SaaS/procesos de negocio |
| Data Agent toolset | Consultar Data Agents conversacionales sobre BigQuery/Looker |
| Toolbox/database toolsets | MCP Toolbox, BigQuery, Spanner, Bigtable, MongoDB, Couchbase, etc. |
| Retrieval tools | RAG, documentos, chunks, vector/document search |
| `AgentTool` | Subagente como herramienta de alto nivel |

Separar built-ins en agentes dedicados cuando haya limites de combinacion de
tools. Usar `bypass_multi_tools_limit=True` solo con necesidad concreta.

La fuente autoritativa para integraciones prebuilt es
`https://adk.dev/integrations/`. Ver `15-adk-integrations-python-api.md` antes de
implementar conectores propios.

## Grounding Metadata

Campos importantes vistos en GenAI/ADK:

| Campo | Uso |
|---|---|
| `grounding_chunks` | Referencias recuperadas |
| `grounding_supports` | Claims y indices de chunks que los soportan |
| `grounding_chunk_indices` | Enlaces claim -> source chunks |
| `segment.text` | Texto del claim soportado |
| `search_entry_point.rendered_content` | Widget/snippet de Google Search para UI/compliance |
| `web_search_queries` | Queries web usadas |
| `retrieval_queries` | Queries de retrieval usadas |

Formas de source chunk a soportar:

- `web.uri` y `web.title` para Google Search.
- `retrieved_context.uri` y `retrieved_context.title` para retrieval.
- `document.uri`, `document.url` o `document.link` con `title`/`name` para
  grounding de documentos.

## Citaciones Deterministas

Patron recomendado:

1. Collect callback lee `grounding_metadata` de eventos.
2. Normaliza URLs y asigna IDs estables `src-N`.
3. Guarda `sources` y mapping URL -> ID en state.
4. El agente final usa tags internos como `<cite source="src-1" />`.
5. Callback final reemplaza tags por markdown seguro.

Ventajas:

- Menos dependencia de que el LLM formatee enlaces correctamente.
- URLs se validan antes de renderizarse.
- Claims pueden asociarse a fuentes reales.
- Se puede preservar metadata de UI/compliance.

## Seguridad De URLs

Reglas recomendadas:

- Permitir solo `http` y `https`.
- Requerir `netloc`.
- Rechazar whitespace, `<` y `>`.
- Escapar parentesis para markdown: `(` -> `%28`, `)` -> `%29`.
- Unknown citation: `[citation unavailable]`.
- Unsafe stored URL: `[source unavailable]`.

## Google Search Display

Si Google Search devuelve `search_entry_point.rendered_content`, preservarlo. En
interfaces web o app puede ser necesario mostrarlo como parte del cumplimiento
de busqueda/grounding.

## Vertex AI Search / Agent Platform Search

Usar cuando hay un corpus propio, documentos internos, datastore o busqueda
enterprise. Antes de implementar:

- Confirmar datastore y region.
- Confirmar permisos y auth.
- Confirmar formato de resultados y grounding metadata.
- Agregar tests deterministas para parser/callback de metadata.
- Considerar `AgentTool(..., propagate_grounding_metadata=True)` en agentes
  anidados.

## Muestras Relevantes

- `agent_tool_with_grounding_metadata`
- `tool_builtin_config`
- `tool_agent_tool_config`
- `built_in_multi_tools`
- `deep-search`
- `llm-auditor`
