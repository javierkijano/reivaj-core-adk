# root_adk2_task_to_workflow Design Spec

## Overview

This agent is a reference ADK 2.0 graph-based `Workflow` implementation. It converts implementation requests into ADK 2.0 Workflow plans while demonstrating natural conversational entry, registry reuse, explicit routes, static fan-out/fan-in, bounded repair loops and strict Event data contracts.

## Example Use Cases

- `bono dias` returns a greeting-style `Event(message=...)` and does not run the planner.
- `ADK` asks for clarification instead of treating a bare topic as an implementation request.
- `Quiero implementar un workflow ADK 2.0 que investigue fuentes` activates the planner.
- `Disena un agente con rutas, joins y tests` produces an implementation plan with graph, node, route, data and verification contracts.

## Tools Required

- Local registry YAML read-only review for reusable agents, workflows, skills, samples and patterns.
- Gemini LLM nodes for intent classification, problem definition, planning and optional repair.

## Constraints And Safety Rules

- ADK 2.0 Workflow is beta and the project opts in with `google-adk>=2.0.0b1`.
- No deployment, publishing, infra provisioning or eval runs without explicit approval.
- No `RequestInput` before intent classification and minimum planning slots are known.
- Normal clarification uses `Event(message=...)`; `RequestInput` is reserved for exceptional blocking approval/auth/reviewer cases.
- Registry review is mandatory before implementation planning.

## Success Criteria

- `root_agent` is a `Workflow` with a `START` edge.
- Intent classification is performed by an LLM node with a closed schema.
- Only `workflow_request` reaches the planner.
- Registry review runs before the problem/planning nodes.
- Static quality checks converge through `JoinNode` and always emit branch outputs.
- Repair loop is explicit, bounded and route-driven.
- Deterministic tests cover imports, routes, natural-entry cases, join normalization and HITL policy.
