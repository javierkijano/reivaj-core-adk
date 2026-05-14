# root_adk2_task_to_workflow

Reference ADK 2.0 Workflow agent for turning implementation requests into ADK 2.0 workflow plans.

The agent is intentionally graph-first:

- `root_agent` is a `Workflow`.
- Intent classification is a structured LLM node.
- Conversational routes end with `Event(message=...)`.
- Implementation planning reviews the local registry before generating work.
- Quality checks use static fan-out/fan-in through `JoinNode`.
- Repair is a bounded route loop, not `LoopAgent`.
- HITL is not used as the front door.

Run deterministic tests:

```bash
uv run pytest tests/unit
```
