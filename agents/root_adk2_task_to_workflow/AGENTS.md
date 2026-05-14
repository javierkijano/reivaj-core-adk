# Coding Agent Guide

This project is the reference implementation for Reivaj ADK 2.0 Workflow agents.

## Non-Negotiables

- `app/agent.py` must export `root_agent` as `google.adk.Workflow`.
- Keep `App(name="app")` aligned with `[tool.agents-cli].agent_directory`.
- Do not add HITL as a general conversation mechanism.
- Classify conversational intent with a structured LLM node before planners, tools, providers or HITL.
- Review `registry/` before planning implementation work.
- Use `Event(output=...)` for internal handoff data, `Event(state=...)` for small durable state and `Event(message=...)` only for user-visible responses.
- Prefer graph routes, static fan-out/fan-in and `JoinNode` before dynamic workflows.
- Do not require Live Streaming with ADK 2.0 graph workflows.

## Development Commands

```bash
uv run pytest tests/unit
uv run python -c "from app.agent import root_agent; print(type(root_agent).__name__)"
```

Run evals, playground, deployment or cloud-changing commands only after explicit human approval.
