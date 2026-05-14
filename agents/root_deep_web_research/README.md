# root_deep_web_research

ADK 2.0 graph-based `Workflow` for guarded deep web research.

## Interaction Contract

- Entrypoint context: `general_chat`.
- `START` goes through `normalize_user_input` and `intent_gate` before planner, HITL or Google Search.
- Greetings, thanks, small talk, empty input and bare topics return `Event(message=...)` and do not create a plan.
- Explicit research triggers such as `investiga`, `busca fuentes`, `consulta la web`, `prepara un informe`, `deep search` or `web research` activate planning.
- HITL approval uses a stable interrupt id: `deep_web_research_plan_approval`.
- Google Search execution only starts after plan approval and guardrail checks.

## Graph

```text
START
  -> normalize_user_input
  -> intent_gate
  -> conversational routes or new_research

new_research
  -> research_planner
  -> initialize_plan_state
  -> hitl_plan_approval
  -> guardrail_node
  -> prepare_search_batch
  -> (google_search_provider, provider_status_branch)
  -> JoinNode
  -> collect_search_iteration
  -> quality_evaluator
  -> quality_router
  -> guardrail_node or synthesis_node
```

## Google Search

The live search branch is `google_search_provider` in `search_agents.py`:

```python
from google.adk.tools import google_search

google_search_provider = Agent(..., tools=[google_search])
```

It is a dedicated single-tool agent because the ADK Google Search tool must not
be mixed with unrelated tools in the same agent instance.

## Local Checks

Run from `agents/`:

```bash
uv run --with pytest pytest root_deep_web_research/tests/unit
uv run --with ruff ruff check root_deep_web_research
uv run python -c "from root_deep_web_research.agent import root_agent; print(type(root_agent).__name__)"
```

Do not run live playground, evals or deployment without explicit approval.
