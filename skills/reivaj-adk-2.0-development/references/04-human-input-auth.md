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

`RequestInput` no es una compuerta conversacional generica. En un root expuesto a
chat, debe aparecer despues de `intent_gate` y solo si ya existe una decision
real que requiere humano. No usarlo para preguntar si un saludo o small talk debe
activar el workflow.

## HITL Simple

Sample `request_input/agent.py`:

- Guardar complaint/feedback en state.
- Redactar email con Agent.
- `RequestInput` para revision humana.
- Router que emite `approved`, `rejected` o `revise`.
- Edge que vuelve a draft si hay revision.

Lecciones:

- Es un workflow dedicado de revision, no un patron para root agents
  conversacionales.
- Esta marcado como `NOT WORKING YET`; no copiar literalmente sin validar.
- No usarlo como excusa para disparar HITL ante `Hola` o inputs ambiguos.

Patron:

```python
def request_human_review(draft: str):
    yield RequestInput(message=f"Review this draft:\n{draft}")

def handle_review(node_input: Any):
    review = normalize_human_response(node_input)
    if review == "approve":
        yield Event(route="approved")
    else:
        yield Event(state={"feedback": review}, route="revise")
```

La respuesta humana es frontera externa: puede llegar como string, dict o payload
estructurado segun UI/runtime. Normalizar antes de emitir rutas criticas.

## HITL Con Resume Robusto

Sample `request_input_rerun/agent.py`:

```python
@node(rerun_on_resume=True)
def human_review(draft: str, ctx: Context):
    raw_resume = ctx.resume_inputs.get("human_review")
    if raw_resume is None:
        yield RequestInput(interrupt_id="human_review", message="Review...")
        return
    resume_input = normalize_human_response(raw_resume)
    ...
```

Usar este patron cuando el nodo debe ejecutarse de nuevo tras recibir respuesta.
El `interrupt_id` debe ser estable y unico por interrupcion logica.

No asumir que `ctx.resume_inputs[interrupt_id]` coincide exactamente con
`response_schema`. Puede ser texto libre, dict serializado, instancia Pydantic o
payload de UI. Convertir a la forma esperada y luego validar.

## HITL Con Payload Y Schema

Sample `request_input_advanced/agent.py`:

```python
class TimeOffDecision(BaseModel):
    approved: bool
    approved_days: int | None = None


def normalize_decision(raw: Any) -> TimeOffDecision:
    if isinstance(raw, TimeOffDecision):
        return raw
    if isinstance(raw, dict):
        return TimeOffDecision.model_validate(raw)
    return TimeOffDecision(approved=str(raw).strip().lower() == "approve")

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
Este sample muestra el patron mas seguro: una decision determinista decide si
pedir humano o continuar. Primero validar intencion y estado; despues pedir
input humano si hace falta.

## Politica HITL User-Friendly

- Mensajes breves y naturales.
- Payload minimo y orientado a la decision.
- Schema pequeno.
- No exponer modelos internos completos al usuario final salvo modo reviewer/admin.
- Para aprobacion simple, preferir approve/reject/feedback o respuesta textual
  normalizada.
- No pedir `approved_plan` completo a un usuario normal.
- No disparar HITL para saludos, thanks, small talk o inputs ambiguos.

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
- `RequestInput` aparece despues de `intent_gate`, no como front-door de chat.
- El nodo HITL no avanza despues de emitir `RequestInput` hasta recibir input.
- La respuesta humana se normaliza desde `str`/`dict`/payload estructurado y se
  valida antes de rutas criticas.
- Los branches de approve/reject/revise tienen handlers.
- Auth no expone secretos en `message`, logs ni tests.
- Los tests cubren primera interrupcion, approve, reject, revise/error y resume.
