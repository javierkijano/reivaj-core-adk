# 07. ADK Skills Y SkillToolset

ADK Skills no son lo mismo que OpenCode skills. OpenCode skills instruyen al
coding agent. ADK Skills son recursos/herramientas que un agente ADK puede
listar, cargar y ejecutar durante una conversacion.

## APIs Estudiadas

- `SkillToolset`
- `load_skill_from_dir`
- `load_skill_from_gcs_dir`
- `list_skills`
- `load_skill`
- `load_skill_resource`
- `run_skill_script`
- `metadata.adk_additional_tools`

## Herramientas Visibles Para El Modelo

SkillToolset expone capacidades como:

| Tool | Uso |
|---|---|
| `list_skills` | Descubrir skills disponibles |
| `load_skill` | Cargar instrucciones de una skill |
| `load_skill_resource` | Leer recursos de la skill |
| `run_skill_script` | Ejecutar scripts autorizados de la skill |

## Estructura Conceptual

Una ADK Skill puede incluir:

- Frontmatter con `name`, `description`, metadata.
- Instrucciones en markdown.
- `references/` con documentacion, ejemplos o schemas.
- Recursos estaticos.
- Scripts autorizados.
- Herramientas adicionales declaradas en metadata.

Restricciones observadas:

- `Frontmatter.name` debe ser kebab case o snake case.
- `Frontmatter.description` maximo 1024 caracteres.

## Cuando Usar ADK SkillToolset

Usar cuando el agente en runtime necesita:

- Consultar paquetes de conocimiento por demanda.
- Reusar procedimientos/documentacion versionada.
- Ejecutar scripts controlados como parte de una tarea.
- Separar habilidades por dominio sin inflar el prompt base.

No usar solo porque el coding assistant tenga OpenCode skills. Son superficies
distintas.

## Riesgos

- Superficie experimental.
- Hay que controlar que scripts pueden ejecutarse.
- Los recursos cargados pueden aumentar contexto/coste.
- Debe auditarse el contenido expuesto al modelo.

## Muestras Relevantes

- `skills_agent`
- `skills_agent_gcs`
- `agent-skills-tutorial`
