# 07. ADK Skills Y SkillToolset

ADK Skills no son lo mismo que OpenCode skills. OpenCode skills instruyen al
coding agent. ADK Skills son paquetes de instrucciones, recursos y herramientas
que un agente ADK puede descubrir y cargar durante una conversacion.

La idea central es evitar prompts monoliticos: el agente mantiene un catalogo
ligero de skills disponibles y solo carga las instrucciones o recursos completos
cuando la tarea lo exige.

## APIs Estudiadas

- `SkillToolset`
- `load_skill_from_dir`
- `load_skill_from_gcs_dir`
- `list_skills`
- `load_skill`
- `load_skill_resource`
- `run_skill_script`
- `metadata.adk_additional_tools`

## Progressive Disclosure

SkillToolset implementa carga progresiva en tres niveles:

| Nivel | Contenido | Cuando se carga | Coste esperado |
|---|---|---|---|
| L1 metadata | `name` y `description` | Startup / cada llamada como catalogo | ~50-100 tokens por skill |
| L2 instrucciones | Cuerpo completo de `SKILL.md` o `instructions` inline | Cuando el agente activa una skill | <5000 tokens recomendado |
| L3 recursos | `references/`, `assets/`, `scripts/` | Solo cuando las instrucciones lo pidan | Variable |

Regla practica: si una capacidad no se usa en casi todas las llamadas, no debe
estar pegada al prompt base. Convertirla en skill permite mantener muchas
capacidades disponibles con bajo coste de contexto.

## Herramientas Visibles Para El Modelo

SkillToolset expone capacidades como:

| Tool | Nivel | Uso |
|---|---|---|
| `list_skills` | L1 | Descubrir skills disponibles y sus descripciones |
| `load_skill` | L2 | Cargar instrucciones completas de una skill |
| `load_skill_resource` | L3 | Leer recursos de la skill, como `references/*` o `assets/*` |
| `run_skill_script` | L3 ejecucion | Ejecutar scripts autorizados de la skill |

## Estructura Conceptual

Una ADK Skill puede incluir:

- Frontmatter con `name`, `description`, metadata.
- Instrucciones en markdown.
- `references/` con documentacion, ejemplos o schemas.
- Recursos estaticos.
- Scripts autorizados.
- Herramientas adicionales declaradas en metadata.

Restricciones observadas:

- `Frontmatter.name` debe ser kebab case para compatibilidad con Agent Skills.
- El directorio de la skill debe coincidir con `Frontmatter.name`.
- `Frontmatter.name` maximo 64 caracteres; usar minusculas, numeros y guiones.
- `Frontmatter.description` maximo 1024 caracteres.
- `description` debe explicar que hace la skill y cuando usarla; es la API de
  descubrimiento del modelo.
- Mantener `SKILL.md` pequeno; mover detalles extensos a `references/`.
- Usar rutas relativas desde la raiz de la skill al mencionar recursos.

## Patrones De Implementacion

`agent-skills-tutorial` demuestra cuatro patrones complementarios:

| Patron | API | Usar cuando | Evitar cuando |
|---|---|---|---|
| Inline | `models.Skill(...)` | Reglas pequenas, estables, sin archivos externos | La skill tiene docs, plantillas o necesita reuso entre agentes |
| File-based | `load_skill_from_dir(path)` | Skills complejas con `SKILL.md`, referencias o assets | Solo hay una checklist corta que vive mejor en codigo |
| External | `load_skill_from_dir(path)` sobre skill descargada | Reusar skills de comunidad u organizacion | No se ha auditado contenido, licencia o scripts |
| Meta skill | `models.Skill` que genera `SKILL.md` | Crear nuevas skills desde requisitos | No hay revision humana ni eval antes de activarla |

### Inline Skill

Bueno para checklists cortas y versionadas junto al agente. Ejemplo minimo:

```python
from google.adk.skills import models

seo_skill = models.Skill(
    frontmatter=models.Frontmatter(
        name="seo-checklist",
        description="SEO checklist for blog posts. Use for title, metadata, headings, keywords, and readability review.",
    ),
    instructions=(
        "When optimizing a blog post for SEO, check title, meta description, "
        "heading hierarchy, keyword placement, links, images, and URL slug."
    ),
)
```

### File-Based Skill

Bueno cuando hace falta estructura, referencias o reuso:

```text
skills/blog-writer/
  SKILL.md
  references/style-guide.md
```

```python
import pathlib
from google.adk.skills import load_skill_from_dir

blog_writer_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "blog-writer"
)
```

El `SKILL.md` debe decir explicitamente cuando cargar recursos, por ejemplo:
`Use load_skill_resource to read references/style-guide.md`.

### External Skill

Una skill externa usa la misma API que una local. La diferencia es el origen del
directorio: repo comunitario, repositorio interno, paquete descargado o artefacto
versionado. Antes de incorporarla:

- Auditar `SKILL.md`, `references/`, `assets/` y `scripts/`.
- Confirmar licencia y compatibilidad.
- Eliminar o bloquear scripts no necesarios.
- Adaptar nombres, rutas y supuestos de entorno al proyecto.

### Meta Skill / Skill Factory

Una meta skill genera nuevas skills. El patron util es incluir como L3 recursos
la especificacion Agent Skills y un ejemplo valido, y pedir al agente que genere
un `SKILL.md` completo.

Reglas para meta skills:

- Generar solo contenido de skill, no escribirlo ni activarlo sin permiso.
- Exigir nombre kebab-case y descripcion especifica.
- Mantener instrucciones paso a paso.
- Poner conocimiento extenso en `references/`.
- Revisar como dependencia de codigo antes de usar en produccion.
- Crear evals si la skill afecta comportamiento de negocio.

## Wiring Recomendado

Usar un solo `SkillToolset` para agrupar skills relacionadas:

```python
from google.adk import Agent
from google.adk.tools.skill_toolset import SkillToolset

skill_toolset = SkillToolset(
    skills=[seo_skill, blog_writer_skill, content_researcher_skill, skill_creator]
)

root_agent = Agent(
    model="gemini-2.5-flash",
    name="blog_skills_agent",
    description="A blog-writing agent powered by reusable skills.",
    instruction=(
        "Load relevant skills before specialized work. "
        "Use load_skill_resource for referenced materials. "
        "Follow loaded skill instructions exactly and explain which skill is used."
    ),
    tools=[skill_toolset],
)
```

No cambiar `model=` en agentes existentes solo por copiar un sample.

## Diseno De Descripciones

La descripcion es el contrato L1 que decide si la skill se carga. Debe incluir:

- Dominio o tarea concreta.
- Senales de activacion, como palabras del usuario o tipos de archivo.
- Resultado esperado.

Evitar descripciones genericas como `Helps with writing`. Preferir:
`Writes technical blog posts with outline, section flow, code examples, and style-guide checks. Use when drafting or polishing technical articles.`

## Cuando Usar ADK SkillToolset

Usar cuando el agente en runtime necesita:

- Consultar paquetes de conocimiento por demanda.
- Reusar procedimientos/documentacion versionada.
- Ejecutar scripts controlados como parte de una tarea.
- Separar habilidades por dominio sin inflar el prompt base.
- Compartir capacidades entre agentes o equipos con formato estandar.
- Permitir crecimiento controlado de capacidades mediante meta skills revisadas.

No usar solo porque el coding assistant tenga OpenCode skills. Son superficies
distintas.

## Riesgos

- Superficie experimental en ADK.
- Hay que controlar que scripts pueden ejecutarse.
- Recursos L3 grandes pueden aumentar contexto/coste si la skill esta mal escrita.
- Debe auditarse el contenido expuesto al modelo.
- Skills externas son dependencias: pueden traer instrucciones inseguras,
  supuestos de entorno, licencias incompatibles o scripts peligrosos.
- Skills generadas por meta skills requieren revision humana y evaluacion.

## Checklist Antes De Introducir SkillToolset

- Confirmar que el problema es bloat de contexto, reuso de conocimiento o
  modularidad real.
- Elegir inline vs file-based vs external vs meta segun la tabla de patrones.
- Revisar que cada descripcion active la skill correcta sin ambiguedad.
- Verificar que `SKILL.md` referencia recursos L3 explicitamente y no carga todo.
- Auditar scripts y recursos externos.
- Hacer smoke import del agente y eval de comportamiento si la skill decide
  respuestas LLM relevantes.

## Muestras Relevantes

- `skills_agent`
- `skills_agent_gcs`
- `agent-skills-tutorial`

Ver tambien `14-agent-skills-tutorial-analysis.md` para el analisis completo del
sample `third-party/adk-samples/python/agents/agent-skills-tutorial`.
