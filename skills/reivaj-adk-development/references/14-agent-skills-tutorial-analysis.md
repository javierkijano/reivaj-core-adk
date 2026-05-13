# 14. Agent Skills Tutorial Analysis

Fuente local analizada:

- `third-party/adk-samples/python/agents/agent-skills-tutorial/README.md`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/app/agent.py`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/app/skills/blog-writer/SKILL.md`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/app/skills/blog-writer/references/style-guide.md`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/app/skills/content-research-writer/SKILL.md`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/app/skills/content-research-writer/references/seo-guidelines.md`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/pyproject.toml`
- `third-party/adk-samples/python/agents/agent-skills-tutorial/.env.example`

Referencias web revisadas:

- `https://adk.dev/skills/`
- `https://agentskills.io/specification`
- `https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/`

## Tesis Del Sample

`agent-skills-tutorial` demuestra que ADK Skills sirven para sacar conocimiento
especializado del prompt base y cargarlo bajo demanda. El agente no contiene
todas las reglas de escritura, SEO y research en la instruccion raiz. En su
lugar, registra cuatro skills dentro de un `SkillToolset` y deja que el modelo
liste, cargue y consulte recursos cuando la tarea lo requiere.

El resultado es un agente simple en codigo, pero extensible en conocimiento:
mantiene un catalogo ligero L1 y activa L2/L3 solo para tareas relevantes.

## Arquitectura Implementada

El sample usa un unico archivo de agente:

```python
from google.adk import Agent
from google.adk.skills import load_skill_from_dir, models
from google.adk.tools.skill_toolset import SkillToolset
```

Componentes:

| Componente | Tipo | Funcion |
|---|---|---|
| `seo_skill` | Inline `models.Skill` | Checklist SEO corta definida en Python |
| `blog_writer_skill` | `load_skill_from_dir` | Skill local con `SKILL.md` y `references/style-guide.md` |
| `content_researcher_skill` | `load_skill_from_dir` | Skill tratada como externa, cargada desde directorio local descargado |
| `skill_creator` | Inline `models.Skill` con `models.Resources` | Meta skill que genera nuevas definiciones `SKILL.md` |
| `skill_toolset` | `SkillToolset` | Agrupa las cuatro skills y expone tools al modelo |
| `root_agent` | `Agent` | Agente conversacional que decide que skill cargar |

La instruccion raiz enumera las skills disponibles, pero no copia sus reglas
completas. Esto mantiene el prompt base compacto y delega el detalle al
`SkillToolset`.

## Progressive Disclosure L1/L2/L3

El patron central es progressive disclosure:

| Nivel | En el sample | Interpretacion |
|---|---|---|
| L1 metadata | `frontmatter.name` y `frontmatter.description` | Menu que el agente usa para elegir skill |
| L2 instrucciones | `instructions` inline o cuerpo de `SKILL.md` | Procedimiento principal de la skill |
| L3 recursos | `models.Resources.references` o archivos `references/*.md` | Detalle cargado solo cuando L2 lo solicita |

`SkillToolset` auto-genera tools que mapean estos niveles:

| Tool | Nivel | Uso |
|---|---|---|
| `list_skills` | L1 | Ver catalogo de skills disponibles |
| `load_skill` | L2 | Leer instrucciones completas de una skill |
| `load_skill_resource` | L3 | Leer referencias, assets o scripts de la skill |

La leccion de diseno: el agente raiz debe indicar que cargue skills relevantes
antes de responder y que use `load_skill_resource` cuando las instrucciones lo
pidan. La skill debe pedir explicitamente sus recursos L3.

## Patron 1: Inline Skill

Implementacion analizada: `seo_skill`.

Uso recomendado:

- Checklists pequenas.
- Reglas estables.
- Conocimiento sin referencias externas.
- Casos donde versionar la regla junto al agente es suficiente.

Ventajas:

- Menos archivos.
- Facil de leer en un solo `agent.py`.
- Adecuado para prototipos y reglas cortas.

Costes:

- Menos reusable por otros agentes.
- Puede ensuciar `agent.py` si crece.
- No separa bien L3 si aparecen referencias largas.

Decision: usar inline solo si la skill completa cabe razonablemente en pocas
lineas y no necesita assets, scripts ni documentos.

## Patron 2: File-Based Skill

Implementacion analizada: `blog-writer`.

Estructura:

```text
skills/blog-writer/
  SKILL.md
  references/style-guide.md
```

`SKILL.md` contiene frontmatter y pasos. En el paso 1 ordena leer
`references/style-guide.md` con `load_skill_resource`. El archivo de referencia
contiene voz, estructura, formato y anti-patrones.

Uso recomendado:

- Skills complejas.
- Skills que necesitan style guides, schemas, templates o ejemplos.
- Skills compartibles entre agentes.
- Conocimiento que debe actualizarse sin tocar logica Python.

Leccion: `SKILL.md` no debe ser un volcado masivo. Debe ser el procedimiento y
apuntar a recursos L3 enfocados.

## Patron 3: External Skill

Implementacion analizada: `content-research-writer`.

El codigo usa la misma API que una file-based skill:

```python
content_researcher_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "skills" / "content-research-writer"
)
```

La diferencia es conceptual: el directorio podria venir de un repositorio
externo o de una biblioteca interna. `load_skill_from_dir` no distingue el
origen si la estructura cumple la especificacion.

Checklist para importar skills externas:

- Leer `SKILL.md` completo.
- Revisar cada archivo en `references/`, `assets/` y `scripts/`.
- Confirmar licencia y origen.
- Verificar que el nombre es kebab-case y coincide con el directorio.
- Confirmar que la descripcion activa la skill correctamente.
- Quitar scripts no necesarios o exigir aprobacion para ejecutarlos.
- Crear evals si la skill afecta comportamiento relevante.

## Patron 4: Meta Skill / Skill Factory

Implementacion analizada: `skill_creator`.

La meta skill es inline, pero incluye recursos L3 embebidos mediante
`models.Resources`:

```python
resources=models.Resources(
    references={
        "skill-spec.md": "...",
        "example-skill.md": "...",
    }
)
```

Su proposito no es ejecutar una tarea de dominio, sino generar un nuevo
`SKILL.md` desde requisitos. Para hacerlo carga dos recursos: una especificacion
y un ejemplo.

Reglas extraidas:

- Nombre kebab-case, maximo 64 caracteres.
- Descripcion bajo 1024 caracteres, especifica y orientada a activacion.
- Instrucciones claras y paso a paso.
- Detalles largos en `references/`, no en `SKILL.md`.
- `SKILL.md` bajo 500 lineas como regla practica.
- La salida debe ser revisable por humanos antes de incorporarse.

Uso recomendado:

- Crear borradores de skills internas.
- Capturar nuevos workflows repetibles desde una conversacion.
- Acelerar expansion de capacidades manteniendo formato estandar.

No usar sin:

- Revision humana.
- Validacion de formato.
- Evaluaciones de comportamiento si la skill se va a activar en produccion.

## Contrato Del Agente Raiz

La instruccion raiz del sample contiene cuatro reglas clave:

1. Cargar las skills relevantes antes de escribir, investigar u optimizar.
2. Usar `load_skill_resource` para materiales referenciados.
3. Seguir instrucciones paso a paso de la skill cargada.
4. Explicar que skill se usa y por que.

Este contrato es tan importante como la definicion de las skills. Sin el, el
modelo puede responder desde conocimiento general y saltarse L2/L3.

## Estructura De Proyecto

El sample es deliberadamente pequeno:

```text
agent-skills-tutorial/
  app/
    __init__.py
    agent.py
    skills/
      blog-writer/
        SKILL.md
        references/style-guide.md
      content-research-writer/
        SKILL.md
        references/seo-guidelines.md
  pyproject.toml
  .env.example
  README.md
```

Dependencias relevantes:

- `google-adk>=1.0.0,<2.0.0` en el sample local.
- La documentacion actual indica soporte de Skills en ADK Python v1.25.0 y lo
  marca experimental.
- `.env.example` usa `GOOGLE_API_KEY`; no copiar este auth model si el proyecto
  destino ya usa Vertex AI.

## Como Reutilizar En Proyectos Reivaj

Al incorporar ADK Skills en un proyecto:

1. Confirmar que el problema justifica skills: bloat de prompt, reuso,
   modularidad o capacidades cargadas bajo demanda.
2. Elegir patron: inline para reglas pequenas; file-based para knowledge packs;
   external para capacidades auditadas; meta para generar borradores.
3. Disenar buenas descripciones L1, porque son el mecanismo de routing.
4. Mantener la instruccion raiz corta pero explicita: cargar skill, cargar
   recursos, seguir pasos y explicar uso.
5. Evitar cambiar modelo, auth o region existentes por copiar el sample.
6. Auditar skills externas como dependencias.
7. Evaluar comportamiento LLM con evals, no con pytest de texto libre.

## Anti-Patrones Detectados

- Meter todo el conocimiento en `root_agent.instruction`.
- Crear una skill file-based sin referencias L3 aunque tenga mucho detalle.
- Usar descripciones vagas que no ayudan al modelo a decidir activacion.
- Importar skills externas sin leer scripts o licencias.
- Permitir que una meta skill escriba o active nuevas skills sin revision.
- Copiar `GOOGLE_API_KEY` como patron en proyectos que ya usan Vertex AI.

## Decision Rapida

| Situacion | Decision |
|---|---|
| Checklist de menos de 20 lineas | Inline `models.Skill` |
| Procedimiento con guia o schema | File-based `load_skill_from_dir` |
| Skill compartida por otro equipo | External skill auditada y versionada |
| Necesidad de crear nuevas skills | Meta skill, salida revisada por humano |
| Muchas capacidades raramente usadas | `SkillToolset` para progressive disclosure |
| Capacidad usada en cada llamada | Mantener en prompt base o instruccion raiz |

## Verificacion Minima

Para cambios relacionados con ADK Skills:

- Smoke import: `uv run python -c "from app.agent import root_agent; print(root_agent.name)"`.
- Revisar que cada directorio de skill contiene `SKILL.md`.
- Revisar que `name` coincide con el directorio.
- Revisar que recursos mencionados existen.
- Ejecutar lint si el proyecto lo soporta.
- Pedir aprobacion antes de ejecutar evals o comandos cloud.
