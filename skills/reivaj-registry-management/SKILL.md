---
name: reivaj-registry-management
description: >
  Skill para mantener y aprovechar el Resource Registry de Reivaj. Usar cuando
  haya que actualizar el registro con nueva informacion, buscar recursos,
  lanzar la webapp del registry, analizar solapamientos, identificar mejoras o
  recomendar a un agente recursos existentes frente a crear nuevos.
metadata:
  author: Reivaj / OpenCode
  license: Internal
  version: 1.0.0
  requires:
    bins:
      - ruby
---

# Reivaj Registry Management

Esta skill convierte `registry/` en una fuente de conocimiento operativa para
agentes. El registry es la fuente de verdad sobre recursos internos y externos
reutilizables: agentes, workflows, skills, patrones, herramientas, integraciones
y candidatos de extraccion.

## Uso Correcto

Usar esta skill cuando haya que:

- Buscar recursos disponibles antes de implementar algo nuevo.
- Actualizar catalogos del registry con informacion nueva.
- Validar que los catalogos YAML siguen el esquema comun.
- Lanzar la webapp local del registry.
- Analizar solapamientos entre agentes, skills, workflows o patrones.
- Identificar mejoras del registry: registros debiles, duplicados, tags faltantes
  o candidatos para extraccion.
- Ayudar a otro agente a decidir si debe reutilizar un recurso existente o crear
  uno nuevo.

No usar esta skill para:

- Reemplazar la lectura del codigo fuente real antes de reutilizar un recurso.
- Ejecutar despliegues, provisionar cloud o modificar credenciales.
- Duplicar informacion estructurada en Markdown.

## Fuente De Verdad

- Esquema autoritativo: `registry/schema.yaml`.
- Taxonomia autoritativa: `registry/taxonomy.yaml`.
- Catalogos estructurados: `registry/**/*.yaml`.
- Markdown en `registry/**/*.md`: solo descripcion general y navegacion.

Regla central: no crear ni mantener tablas Markdown con registros. Toda entrada
estructurada debe estar en YAML.

## Comandos Utiles

Ejecutar desde la raiz del repo:

```bash
ruby skills/reivaj-registry-management/scripts/registry.rb validate
ruby skills/reivaj-registry-management/scripts/registry.rb search "markdown report"
ruby skills/reivaj-registry-management/scripts/registry.rb search "workflow" --tag entity:workflow
ruby skills/reivaj-registry-management/scripts/registry.rb overlap
ruby skills/reivaj-registry-management/scripts/registry.rb improvements
ruby skills/reivaj-registry-management/scripts/registry.rb serve 8000
```

Para anadir una entrada desde un archivo YAML temporal:

```bash
ruby skills/reivaj-registry-management/scripts/registry.rb add registry/internal/resources.yaml /tmp/new-item.yaml
```

El archivo temporal debe contener un unico item con los campos del esquema:

```yaml
id: markdown-document-writer
name: Markdown Document Writer
source: agents/example/tools/markdown_document_writer.py
summary: Creates long-form Markdown documents from outlines, sections, citations, and style constraints.
tags:
  - entity:tool
  - capability:content-generation
  - domain:horizontal
maturity: maturity:candidate
```

## Flujo Para Buscar Recursos

1. Ejecutar `search` con terminos de dominio, capacidad, tecnologia y tipo de
   recurso.
2. Filtrar por tags cuando sea posible: `entity:*`, `capability:*`, `pattern:*`,
   `integration:*`, `domain:*`, `maturity:*`, `source_type:*`.
3. Revisar tanto recursos internos como externos.
4. Si existe un recurso interno adecuado, recomendar reutilizarlo primero.
5. Si solo existe un recurso externo, recomendar leer la fuente y extraer el
   componente minimo.
6. Si no existe nada adecuado, recomendar crear un nuevo recurso y registrarlo.

## Flujo Para Actualizar El Registro

1. Identificar el catalogo correcto:
   - Recursos propios: `registry/internal/resources.yaml`.
   - Samples externos ADK: `registry/external/adk-samples/*.yaml`.
   - Workflow samples externos ADK 2.0: `registry/external/workflow-samples/workflow-catalog.yaml`.
2. Verificar `source_type`:
   - `external`: `source` debe ser URL web.
   - `internal`: `source` debe ser ruta relativa del repo.
3. Usar tags existentes de `registry/taxonomy.yaml`.
4. Mantener `summary` corto y accionable.
5. Usar `metadata` solo para datos especificos del catalogo; no redefinir el
   esquema.
6. Ejecutar `validate` despues de editar.

## Analisis De Solapamientos

Usar `overlap` para detectar recursos con alta similitud por tags y texto. El
resultado no implica duplicado automaticamente; sirve para decidir:

- Fusionar registros si describen el mismo recurso.
- Mantener ambos si uno es externo y otro interno adaptado.
- Crear una abstraccion comun si varios recursos implementan el mismo patron.
- Promover un recurso interno si reemplaza a varios candidatos externos.

## Identificacion De Mejoras

Usar `improvements` para encontrar:

- Summaries demasiado cortos.
- Entradas sin tags.
- Entradas sin `entity:*`.
- Entradas externas sin URL.
- Entradas internas con URL.
- IDs duplicados entre catalogos.

Priorizar mejoras que aumenten la capacidad de decision de otros agentes: tags
precisos, resumen claro, source trazable y maturity honesta.

## Guia Para Otros Agentes

Cuando otro agente necesite ayuda para aprovechar recursos disponibles:

1. Traducir la necesidad a tags y palabras clave.
2. Buscar recursos internos y externos.
3. Comparar candidatos por source type, maturity, tags y cercania semantica.
4. Recomendar una de estas acciones:
   - Reutilizar recurso interno existente.
   - Adaptar un recurso externo y registrar el resultado interno.
   - Extraer un componente comun desde varios recursos solapados.
   - Crear un recurso nuevo porque no existe cobertura suficiente.
5. Si se crea o adapta algo, actualizar el YAML correspondiente y validar.

## Referencias

- Workflow detallado: `references/registry-workflows.md`.
- Script operativo: `scripts/registry.rb`.
