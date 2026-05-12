# 03. Agent Config YAML

Agent Config permite definir agentes en YAML. Es util para grafos declarativos,
pero hay que respetar el schema de la version instalada.

## Estado Observado En ADK 2.0.0b1

- Agent Config es experimental.
- Se observaron warnings de `FeatureName.AGENT_CONFIG`.
- Clases ADK reconocidas localmente: `LlmAgent`, `LoopAgent`, `ParallelAgent`,
  `SequentialAgent`.
- `LlmAgentConfig` tiene `extra='forbid'`; campos no soportados fallan.
- `BaseAgentConfig` tiene `extra='allow'` para bloques custom.
- No se observo soporte directo YAML para la nueva API `Workflow`.

## Estructura Basica

```yaml
agent_class: LlmAgent
name: research_agent
model: gemini-2.5-flash
description: Performs research.
instruction: |
  You are a research agent.
tools:
  - name: google_search
output_key: research_findings
```

## Referencias A Codigo

Las referencias deben ser rutas importables de Python desde el proyecto:

```yaml
after_agent_callbacks:
  - name: callbacks.research_callbacks.collect_sources
```

No usar nombres de carpetas no importables como prefijo.

## AgentTool En YAML

Patron observado correcto:

```yaml
tools:
  - name: AgentTool
    args:
      agent:
        config_path: plan_generator.yaml
```

## Output Schema

Patron con Pydantic:

```yaml
output_schema:
  name: agents.schemas.ResearchEvaluation
generate_content_config:
  response_mime_type: application/json
```

El prompt debe pedir JSON raw compatible con el schema.

## Automatic Function Calling

Usar forma dict:

```yaml
generate_content_config:
  automatic_function_calling:
    disable: false
```

## Thinking Config

YAML puede expresar:

```yaml
generate_content_config:
  thinking_config:
    include_thoughts: true
```

Pedir opt-in antes de activarlo porque puede cambiar coste, metadata y conducta.

## Cuando Usar YAML

Usar YAML cuando:

- La arquitectura ya encaja con clases soportadas.
- Se busca trazabilidad declarativa.
- Los cambios son instrucciones, modelos, output keys, tools simples o callbacks.

Usar Python code-first cuando:

- Hace falta `Workflow`.
- Hace falta construir objetos no expresables por YAML.
- Se necesitan wrappers complejos, toolsets, planners, plugins o factories.
- Se requiere validacion dinamica o control flow no trivial.

## Errores Comunes

| Problema | Causa habitual | Solucion |
|---|---|---|
| Campo rechazado | `LlmAgentConfig.extra='forbid'` | Ver schema instalado o usar code-first |
| Import callback falla | Ruta no importable | Usar paquete real desde project root |
| Tool args no cargan | Forma YAML incorrecta | Seguir docs/schema o envolver en Python |
| JSON schema falla | Prompt y schema no alineados | Ajustar instrucciones y tests |
| Built-in incompatible con otras tools | Limitacion de multi-tools | Separar en agente dedicado o evaluar `bypass_multi_tools_limit` |

## Referencias

- `https://adk.dev/agents/config/index.md`
- `https://github.com/google/adk-docs/blob/main/docs/agents/config.md`
- `https://adk.dev/api-reference/agentconfig/`
- Schema local instalado: `google/adk/agents/config_schemas/AgentConfig.json`
