# 12. Runbook

## Orden De Trabajo

1. Cargar esta skill y la skill oficial de la fase.
2. Leer el codigo/proyecto especifico antes de asumir arquitectura.
3. Confirmar constraints y aprobaciones necesarias.
4. Implementar el cambio minimo correcto.
5. Ejecutar checks deterministas.
6. Pedir aprobacion para eval/deploy/cloud si aplica.
7. Documentar decisiones y riesgos residuales.

## Comandos Seguros Habituales

```bash
agents-cli info
agents-cli install
agents-cli lint
uv run pytest tests/unit
uv run python -c "from app.agent import root_agent; print(root_agent.name)"
agents-cli login --status
```

## Comandos Que Requieren Aprobacion

```bash
agents-cli eval run
agents-cli playground
agents-cli deploy
agents-cli infra single-project
agents-cli infra cicd
agents-cli publish gemini-enterprise
```

Tambien requieren aprobacion:

- Terraform.
- GCP provisioning.
- Secret Manager changes.
- Cloud Run / GKE deploys.
- Agent Runtime deploys.
- BigQuery / Cloud Trace setup.

## Diagnostico Sistematico

| Paso | Accion |
|---|---|
| Reproducir | Ejecutar comando exacto o aislar fallo |
| Localizar | Config, import, tool, callback, model, auth, runtime o cloud |
| Cambiar uno | Evitar shotgun debugging |
| Verificar | Repetir comando minimo |
| Guardar | Test determinista o eval case segun naturaleza del fallo |

Parar si el mismo error aparece tres veces. Leer fuente/docs en vez de seguir
probando variaciones.

## Checklist Por Tipo De Cambio

| Cambio | Checks minimos |
|---|---|
| Agent Config YAML | Import smoke, graph-load test si existe, `agents-cli lint` |
| Callback/schema/parser | Unit tests especificos, `agents-cli lint` |
| Tools | Unit tests con mocks/stubs si posible, smoke local, eval aprobada si comportamiento LLM |
| Workflow migration | Tests antes/despues, evals aprobadas, rollback plan |
| A2A runtime | Import, card build, tests locales, deploy solo con aprobacion |
| Grounding/citations | Unit tests de metadata y URL safety, eval de comportamiento con aprobacion |
| Evalsets | Validacion estatica; ejecucion solo con aprobacion |
| Deploy/infra | Skill deploy, aprobacion, plan, rollback |

## Patrones De Seguridad

- No imprimir access tokens.
- No leer ni commitear `.env` real.
- No registrar prompts/responses sensibles sin decision explicita.
- Sanitizar URLs antes de renderizar markdown.
- Separar secrets de config versionada.
- Usar Secret Manager en produccion.

## Errores Frecuentes

| Error | Diagnostico |
|---|---|
| Modelo 404 | Region/model availability antes de cambiar modelo |
| YAML no carga | Schema, imports o args incorrectos |
| Tool no aparece | Import incorrecto o built-in incompatible |
| Eval flake | Criterios ambiguos o pytest usado para LLM output |
| Grounding perdido | Metadata no propagada desde subagente/tool |
| Deploy falla 403 | Service account/permisos/secrets/proyecto |
| Loop infinito | Falta condicion de salida o escalation/event route |

## Reglas De Edicion

- Usar cambios quirurgicos.
- Mantener funciones juntas salvo reutilizacion clara.
- No anadir compatibilidad hacia atras sin necesidad concreta.
- No cambiar modelos, auth, region o deployment target sin pedirlo.
- No revertir cambios ajenos.
- Agregar comentarios solo si aclaran logica no obvia.
