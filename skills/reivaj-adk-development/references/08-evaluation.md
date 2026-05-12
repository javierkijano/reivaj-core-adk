# 08. Evaluacion

La evaluacion valida comportamiento de agente. Pytest valida codigo
determinista. No mezclar responsabilidades.

## Pytest Vs Eval

| Herramienta | Valida | No valida |
|---|---|---|
| `uv run pytest` | Imports, schemas, callbacks, parsers, contratos deterministas | Calidad de respuesta LLM |
| `agents-cli run` | Smoke test rapido de una interaccion | Regresiones sistematicas |
| `agents-cli eval run` | Calidad, herramientas, trayectoria, seguridad, criterios | Bugs unitarios internos si no hay caso |

No escribir tests pytest que esperen frases concretas del LLM.

## Evalset

Un evalset debe incluir:

- Input del usuario.
- Respuesta esperada o criterios.
- Trayectoria de herramientas esperada cuando aplique.
- Criterios LLM-as-judge.
- Umbrales de paso.

## Metricas Y Criterios

| Criterio | Uso |
|---|---|
| Response quality | Claridad, utilidad, completitud |
| Tool trajectory | Uso correcto de herramientas |
| Safety/compliance | Rechazos, limites, manejo de datos sensibles |
| Grounding/citations | Fuentes correctas, citas presentes, no invencion |
| Task completion | El objetivo se cumple end-to-end |

## Bucle Eval-Fix

1. Crear 1-2 casos base.
2. Ejecutar eval con aprobacion.
3. Leer fallos y trayectorias.
4. Corregir una causa por iteracion.
5. Reejecutar casos fallidos.
6. Ampliar cobertura cuando los casos base pasen.

Esperar varias iteraciones. Una respuesta correcta en `agents-cli run` no
sustituye eval.

## Cuidados

- Evals pueden consumir credenciales reales y coste LLM.
- Usar judge model configurado por proyecto.
- No meter secretos en evalsets.
- Separar evals unitarias de regresion y evals exploratorias.
- Guardar resultados para comparacion si se va a refactorizar arquitectura.
