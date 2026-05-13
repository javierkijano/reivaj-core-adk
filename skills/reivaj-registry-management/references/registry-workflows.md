# Registry Workflows

## Principios

- YAML es la unica fuente estructurada.
- Markdown solo explica contexto, no duplica registros.
- El registro debe responder dos preguntas: que existe y cuando conviene
  reutilizarlo.
- Un recurso externo no es implementacion interna; es referencia trazable.
- Un recurso interno debe apuntar a codigo o conocimiento mantenido en este repo.

## Seleccion De Catalogo

| Necesidad | Catalogo |
|---|---|
| Agente interno, workflow propio, skill interna o herramienta propia | `registry/internal/resources.yaml` |
| Sample completo de `google/adk-samples` | `registry/external/adk-samples/agent-catalog.yaml` |
| Skill dentro de sample externo | `registry/external/adk-samples/skills.yaml` |
| Conteos o inventario de componentes de sample externo | `registry/external/adk-samples/component-inventory.yaml` |
| Patron reutilizable observado en samples externos | `registry/external/adk-samples/reusable-functionality.yaml` |
| Sample de ADK 2.0 Workflow en `google/adk-python` | `registry/external/workflow-samples/workflow-catalog.yaml` |

## Decision Reuse Vs New

Reutilizar recurso interno si:

- Tiene tags que coinciden con la necesidad.
- Su `source` apunta a codigo o skill local mantenible.
- Su maturity es `maturity:adapted` o mejor, o `observed/candidate` pero simple.

Adaptar recurso externo si:

- No hay recurso interno equivalente.
- El sample externo cubre el patron principal.
- El usuario acepta revisar licencia, dependencias, auth y supuestos cloud.

Crear recurso nuevo si:

- No hay resultados relevantes.
- Los resultados existentes solo cubren subproblemas no composables.
- El nuevo recurso define un contrato claro y reusable.

Extraer abstraccion comun si:

- `overlap` muestra varios recursos con tags/summaries parecidos.
- Hay implementaciones repetidas con pequenas variaciones.
- El patron aparece tanto en recursos internos como externos.

## Calidad De Una Entrada

Una entrada util debe tener:

- `id` estable.
- `name` claro.
- `source` trazable.
- `summary` que diga que hace y por que importa.
- Al menos un `entity:*` y un tag de capability, pattern, integration o domain.
- `maturity` conservador.
- `metadata` solo cuando aporta informacion adicional no cubierta por el esquema.

## Anti-Patrones

- Registrar una entrada externa con ruta `third-party/`.
- Registrar una entrada interna con URL externa como source principal.
- Duplicar la misma lista de recursos en Markdown.
- Crear tags nuevos sin revisar `taxonomy.yaml`.
- Marcar `productionized` sin pruebas/evals/revision.
- Copiar un agente completo cuando solo se necesita una herramienta o patron.
