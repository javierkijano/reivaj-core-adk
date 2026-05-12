# 09. Deploy Y Observabilidad

Despliegue y observabilidad requieren aprobacion explicita porque pueden crear,
modificar o consumir recursos cloud.

## Targets

| Target | Uso |
|---|---|
| Prototype local | Desarrollo rapido sin infraestructura |
| Agent Runtime | Plataforma gestionada para agentes ADK/A2A |
| Cloud Run | Servicio HTTP containerizado, flexible |
| GKE | Control avanzado, cargas complejas, infraestructura Kubernetes |

## Antes De Desplegar

- Cargar `google-agents-cli-deploy`.
- Ejecutar `agents-cli info`.
- Confirmar proyecto, region y target.
- Confirmar service account y permisos.
- Confirmar secrets y variables de entorno.
- Confirmar session/artifact storage.
- Confirmar que evals base pasan o que el usuario acepta desplegar sin ellas.

## Comandos Con Aprobacion

```bash
agents-cli deploy
agents-cli infra single-project
agents-cli infra cicd
```

No usar Terraform ni gcloud cloud-changing sin aprobacion.

## Secrets

Buenas practicas:

- Preferir Secret Manager en produccion.
- No commitear `.env` real.
- No imprimir tokens.
- No pasar secretos en prompts ni logs.
- Verificar que callbacks/logging no serializan credenciales.

## CI/CD

Opciones habituales:

- GitHub Actions.
- Google Cloud Build.
- Skip para prototipo/local.

Confirmar repositorio y estrategia antes de generar pipelines.

## Observabilidad

Areas estudiadas:

| Area | Uso |
|---|---|
| Cloud Trace | Trazas de ejecucion y latencia |
| Cloud Logging | Logs estructurados, feedback, errores |
| Prompt-response logging | Auditoria de interacciones, con cuidado de privacidad |
| BigQuery Agent Analytics | Analitica de conversaciones y calidad |
| Third-party | AgentOps, Phoenix, MLflow, etc. |

Cargar `google-agents-cli-observability` antes de configurar observabilidad.

## Rollback Y Operacion

- Registrar version de agente.
- Mantener estrategia de rollback.
- Separar dev/staging/prod si hay CI/CD.
- Monitorizar errores, latencia, tool failures y feedback.
- No habilitar logging sensible sin politica explicita.
