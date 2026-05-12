# 01. Ciclo De Vida ADK

## Fases

| Fase | Objetivo | Acciones |
|---|---|---|
| Entender | Evitar construir lo equivocado | Aclarar problema, usuarios, herramientas, datos, restricciones, destino |
| Estudiar muestras | Reusar patrones probados | Revisar samples ADK antes de disenar desde cero |
| Scaffold | Crear estructura estandar | `agents-cli scaffold create` o `agents-cli scaffold enhance .` |
| Construir | Implementar agente y herramientas | Agentes, tools, callbacks, schemas, estado, artifacts |
| Verificar | Validar codigo determinista | imports, pytest, lint, type checks |
| Evaluar | Validar comportamiento LLM | evalsets, criterios, tool trajectory, judge model |
| Desplegar | Publicar runtime | Agent Runtime, Cloud Run o GKE |
| Publicar | Registrar para consumidores | Gemini Enterprise o A2A segun caso |
| Observar | Operar en produccion | Cloud Trace, logs, analytics, dashboards, feedback |

## Preguntas Minimas De Diseno

- Que problema resolvera el agente.
- Que entradas recibe y que salidas debe producir.
- Que herramientas, APIs, datos o credenciales necesita.
- Que restricciones de seguridad o cumplimiento aplican.
- Si necesita memoria, sesiones persistentes o artefactos.
- Si debe estar disponible para usuarios, otros agentes o ambos.
- Si el objetivo es prototipo, evaluacion, despliegue o produccion.

## DESIGN_SPEC.md

Para trabajo grande, crear o actualizar una especificacion antes de implementar:

```markdown
# DESIGN_SPEC.md

## Overview
Proposito del agente y como opera.

## Use Cases
Entradas y salidas esperadas.

## Tools Required
APIs, datos, auth y permisos.

## Architecture
Agentes, subagentes, estado, herramientas y runtime.

## Constraints And Safety
Reglas concretas de lo que debe y no debe hacer.

## Evaluation Criteria
Criterios medibles y evalsets previstos.

## Deployment Target
Prototype, Agent Runtime, Cloud Run o GKE.
```

## agents-cli

Comandos principales:

```bash
agents-cli info
agents-cli scaffold create <name>
agents-cli scaffold enhance .
agents-cli scaffold upgrade
agents-cli install
agents-cli lint
agents-cli run "prompt"
agents-cli playground
agents-cli eval run
agents-cli deploy
agents-cli publish gemini-enterprise
```

`agents-cli info` tambien muestra ruta de instalacion de CLI y configuracion del
proyecto si existe `[tool.agents-cli]`.

## Mapping De Producto

| Usuario dice | CLI / concepto |
|---|---|
| Agent Engine, Vertex AI Agent Engine, Agent Runtime | `agent_runtime` |
| Vertex AI Search, Agent Search | `agent_platform_search` |
| Vertex AI Vector Search, Vector Search | `agent_platform_vector_search` |
| Agent Engine sessions, Agent Platform Sessions | `agent_platform_sessions` |

El paquete Python `vertexai` conserva su nombre.
