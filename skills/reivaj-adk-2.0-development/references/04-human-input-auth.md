# Human Input, Resume And Auth

## `RequestInput`

Los workflows pueden pausar ejecucion y pedir input humano con `RequestInput`:

```python
from google.adk.events import RequestInput

def ask_user():
    yield RequestInput(message="Enter a number:")
```

Opciones documentadas:

- `message`: texto para explicar la solicitud.
- `payload`: datos estructurados para que la UI muestre contexto.
- `response_schema`: schema esperado de la respuesta humana.
- `interrupt_id`: identificador estable para reanudar correctamente.

Limitacion: `response_schema` no transforma automaticamente respuestas humanas
no estructuradas. Para UX robusta, usar UI estructurada o un Agent que convierta
texto libre al schema requerido.

## HITL Simple

Sample `request_input/agent.py`:

- Guardar complaint/feedback en state.
- Redactar email con Agent.
- `RequestInput` para revision humana.
- Router que emite `approved`, `rejected` o `revise`.
- Edge que vuelve a draft si hay revision.

Patron:

```python
def request_human_review(draft: str):
    yield RequestInput(message=f"Review this draft:\n{draft}")

def handle_review(node_input: str):
    if node_input == "approve":
        yield Event(route="approved")
    else:
        yield Event(state={"feedback": node_input}, route="revise")
```

## HITL Con Resume Robusto

Sample `request_input_rerun/agent.py`:

```python
@node(rerun_on_resume=True)
def human_review(draft: str, ctx: Context):
    resume_input = ctx.resume_inputs.get("human_review")
    if not resume_input:
        yield RequestInput(interrupt_id="human_review", message="Review...")
        return
    ...
```

Usar este patron cuando el nodo debe ejecutarse de nuevo tras recibir respuesta.
El `interrupt_id` debe ser estable y unico por interrupcion logica.

## HITL Con Payload Y Schema

Sample `request_input_advanced/agent.py`:

```python
class TimeOffDecision(BaseModel):
    approved: bool
    approved_days: int | None = None

def evaluate_request(request: TimeOffRequest):
    if request.days <= 1:
        return TimeOffDecision(approved=True)
    return RequestInput(
        interrupt_id="manager_approval",
        message="Please review this time off request.",
        payload=request,
        response_schema=TimeOffDecision,
    )
```

Usar `payload` para contexto y `response_schema` para decisiones auditables.

## Auth API Key

Sample `auth_api_key/agent.py`:

```python
auth_config = AuthConfig(
    auth_scheme=APIKey(**{"in": APIKeyIn.header, "name": "X-Api-Key"}),
    raw_auth_credential=AuthCredential(
        auth_type=AuthCredentialTypes.API_KEY,
        api_key="placeholder",
    ),
    credential_key="weather_api_key",
)

@node(auth_config=auth_config, rerun_on_resume=True)
def fetch_weather(ctx: Context):
    cred = ctx.get_auth_response(auth_config)
    api_key = cred.api_key if cred else "unknown"
```

Reglas:

- No imprimir API keys.
- Enmascarar secretos si aparecen en mensajes.
- Usar `credential_key` estable.
- Separar configuracion auth de logica de negocio.

## Auth OAuth

Sample `auth_oauth/agent.py` usa GitHub OAuth2:

- `OAuth2`, `OAuthFlows`, `OAuthFlowAuthorizationCode` de FastAPI OpenAPI.
- `AuthCredentialTypes.OAUTH2`.
- `OAuth2Auth(client_id=..., client_secret=...)`.
- `ctx.get_auth_response(auth_config)` para recuperar token.

Reglas:

- Leer client id/secret de env o Secret Manager; no hardcodear reales.
- No loggear access tokens.
- Manejar ausencia de token con salida accionable.
- `@node(auth_config=..., rerun_on_resume=True)` para pausar y reanudar.

## Checklist HITL/Auth

- Cada interrupcion tiene `interrupt_id` estable si se reanuda.
- El nodo HITL no avanza despues de emitir `RequestInput` hasta recibir input.
- La respuesta humana se valida o normaliza antes de rutas criticas.
- Los branches de approve/reject/revise tienen handlers.
- Auth no expone secretos en `message`, logs ni tests.
- Los tests cubren approve, reject, revise/error y resume.
