import json
import re
from collections import defaultdict, deque
from typing import Any, TypeVar

from pydantic import BaseModel

from app.task_splitter.schemas import (
    CandidateTaskGraph,
    Condition,
    CoverageReport,
    DecompositionTrace,
    DependencyReport,
    ExecutabilityReport,
    ExecutionPhase,
    ExecutionSchedule,
    ExecutorSpec,
    GoalState,
    GranularityReport,
    LLMCandidateTaskGraph,
    LLMRepairResult,
    MacroState,
    QualityReport,
    RepairOperation,
    RepairOperationType,
    RepairResult,
    RepairSuggestion,
    TaskDecomposition,
    TaskDependencies,
    TaskEdge,
    TaskExecution,
    TaskNode,
    TaskRisk,
    TaskSplitterOutput,
    ValidatedTaskGraph,
    VerifiabilityReport,
    VerifierSpec,
)

T = TypeVar("T", bound=BaseModel)


def model_from_state(model_cls: type[T], value: Any) -> T:
    if isinstance(value, model_cls):
        return value
    if isinstance(value, str):
        try:
            return model_cls.model_validate_json(value)
        except ValueError:
            return model_cls.model_validate(json.loads(value))
    return model_cls.model_validate(value)


def optional_model_from_state(model_cls: type[T], value: Any) -> T | None:
    if value is None:
        return None
    return model_from_state(model_cls, value)


def model_dump(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json", by_alias=True)


def _safe_choice(value: str, allowed: set[str], default: str) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in allowed else default


def _cap_score(score: float, cap: float) -> float:
    return round(min(score, cap), 4)


_TASK_ID_REFERENCE_PATTERN = re.compile(r"\b[tT]\d+[A-Za-z0-9_]*\b")
_GRAPH_SCOPED_TARGETS = {
    "candidate_task_graph",
    "graph",
    "goal",
    "goal_state",
    "runtime_config",
    "runtime_configuration",
    "runtime_environment",
    "task_graph",
}


def graph_fingerprint(graph: CandidateTaskGraph) -> str:
    return json.dumps(model_dump(graph), sort_keys=True)


def _references_missing_node(text: str, task_ids: set[str]) -> bool:
    task_ids_lower = {task_id.lower() for task_id in task_ids}
    references = _TASK_ID_REFERENCE_PATTERN.findall(text)
    return bool(
        references
        and any(
            reference not in task_ids and reference.lower() not in task_ids_lower
            for reference in references
        )
    )


def remove_stale_node_diagnostics(
    diagnostics: list[str], graph: CandidateTaskGraph
) -> list[str]:
    task_ids = {task.id for task in graph.nodes}
    return [
        item for item in diagnostics if not _references_missing_node(item, task_ids)
    ]


def _is_graph_scoped_target(target: str) -> bool:
    normalized = target.strip().lower().replace("-", "_")
    return normalized in _GRAPH_SCOPED_TARGETS


def _repair_suggestion_is_current(
    suggestion: RepairSuggestion, task_ids: set[str]
) -> bool:
    if suggestion.operation == "add_task":
        return True
    return suggestion.target in task_ids or _is_graph_scoped_target(suggestion.target)


def _current_task_references(values: list[str], task_ids: set[str]) -> list[str]:
    if not task_ids:
        return values
    return [value for value in values if value in task_ids]


def _contains_any(values: list[str], needles: set[str]) -> bool:
    haystack = " ".join(values).lower()
    return any(needle in haystack for needle in needles)


def _condition(
    condition_id: str, text: str, evaluator_type: str = "schema"
) -> Condition:
    return Condition(
        id=condition_id,
        condition=text or "The expected state transition is observable.",
        evaluator_type=_safe_choice(
            evaluator_type,
            {"llm", "function", "tool", "human", "schema", "test"},
            "schema",
        ),
        evaluator_instruction=f"Verify: {text}",
        observable=True,
        confidence_threshold=0.85,
    )


def normalize_llm_task_graph(draft: LLMCandidateTaskGraph) -> CandidateTaskGraph:
    nodes: list[TaskNode] = []
    for index, draft_node in enumerate(draft.nodes, start=1):
        task_id = draft_node.id or f"T{index}"
        input_state = draft_node.input_state or ["goal_state_available"]
        output_state = draft_node.output_state or [f"{task_id}_completed"]
        preconditions = draft_node.preconditions or ["Required inputs are available"]
        postconditions = draft_node.postconditions or [f"{task_id} output is produced"]
        verifier_instruction = (
            draft_node.verifier_instruction
            or "Verify that postconditions and acceptance criteria are satisfied."
        )
        execution_status = _safe_choice(
            draft_node.execution_status,
            {
                "executable",
                "conditionally_executable",
                "blocked",
                "blocked_by_runtime_inputs",
            },
            "executable",
        )
        if draft_node.missing_runtime_inputs and execution_status == "executable":
            execution_status = "blocked_by_runtime_inputs"
        node = TaskNode(
            id=task_id,
            title=draft_node.title or task_id,
            description=draft_node.description or draft_node.title or task_id,
            action_type=draft_node.action_type or "plan",
            abstraction_level=_safe_choice(
                draft_node.abstraction_level, {"micro", "meso", "macro"}, "meso"
            ),
            input_state=input_state,
            output_state=output_state,
            preconditions=[
                _condition(f"{task_id}_pre_{item_index}", text)
                for item_index, text in enumerate(preconditions, start=1)
            ],
            postconditions=[
                _condition(f"{task_id}_post_{item_index}", text)
                for item_index, text in enumerate(postconditions, start=1)
            ],
            executor=ExecutorSpec(
                type=_safe_choice(
                    draft_node.executor_type,
                    {"agent", "tool", "skill", "workflow", "human"},
                    "agent",
                ),
                id=draft_node.executor_id or "task_executor",
                required_inputs=input_state,
                expected_outputs=output_state,
            ),
            verifier=VerifierSpec(
                type=_safe_choice(
                    draft_node.verifier_type,
                    {"llm", "function", "tool", "test", "human", "schema_validation"},
                    "schema_validation",
                ),
                instruction=verifier_instruction,
                success_threshold=0.85,
                failure_action="replan",
            ),
            acceptance_criteria=draft_node.acceptance_criteria
            or ["All postconditions are satisfied"],
            dependencies={"requires": draft_node.dependencies, "required_by": []},
            execution={
                "mode": _safe_choice(
                    draft_node.execution_mode,
                    {"sequential", "parallel_candidate", "integration", "human_review"},
                    "sequential",
                ),
                "parallel_group": draft_node.parallel_group,
                "execution_status": execution_status,
                "missing_runtime_inputs": draft_node.missing_runtime_inputs,
                "branch_condition": draft_node.branch_condition,
            },
            decomposition={
                "can_expand": draft_node.can_expand,
                "should_expand_now": draft_node.should_expand_now,
                "expansion_reason": draft_node.expansion_reason,
                "compressed_subgraph_ref": None,
            },
            risk={
                "level": _safe_choice(
                    draft_node.risk_level, {"low", "medium", "high"}, "medium"
                ),
                "reasons": draft_node.risk_reasons,
            },
        )
        nodes.append(node)

    node_ids = {node.id for node in nodes}
    edges: list[TaskEdge] = []
    for draft_edge in draft.edges:
        if draft_edge.source in node_ids and draft_edge.target in node_ids:
            edges.append(
                TaskEdge.model_validate(
                    {
                        "from": draft_edge.source,
                        "to": draft_edge.target,
                        "type": _safe_choice(
                            draft_edge.type,
                            {
                                "requires_output",
                                "enables",
                                "validates",
                                "integrates",
                                "blocks",
                                "alternative_to",
                                "recovery_for",
                            },
                            "enables",
                        ),
                        "reason": draft_edge.reason or "Causal dependency.",
                    }
                )
            )

    required_by: dict[str, list[str]] = {node.id: [] for node in nodes}
    for node in nodes:
        for dependency_id in node.dependencies.requires:
            if (
                dependency_id in required_by
                and node.id not in required_by[dependency_id]
            ):
                required_by[dependency_id].append(node.id)
    for edge in edges:
        if edge.from_task in required_by and edge.to not in required_by[edge.from_task]:
            required_by[edge.from_task].append(edge.to)
    for node in nodes:
        node.dependencies.required_by = sorted(required_by[node.id])

    return CandidateTaskGraph(
        graph_type=_safe_choice(
            draft.graph_type,
            {"implementation_task_graph", "runtime_task_graph", "mixed_graph"},
            "implementation_task_graph",
        ),
        runtime_pipeline_ref=draft.runtime_pipeline_ref,
        nodes=nodes,
        edges=edges,
        assumptions=draft.assumptions,
    )


def _edge_identity(edge: TaskEdge) -> tuple[str, str, str, str]:
    return (edge.from_task, edge.to, edge.type, edge.reason)


def _choose_synthetic_operation(
    added_nodes: list[TaskNode],
    removed_nodes: list[TaskNode],
    modified_nodes: list[TaskNode],
    added_edges: list[TaskEdge],
    removed_edges: list[TaskEdge],
) -> RepairOperationType:
    if added_nodes and removed_nodes:
        return "split_task"
    if added_nodes:
        return "add_task"
    if removed_nodes:
        return "remove_task"
    if added_edges:
        return "add_dependency"
    if removed_edges:
        return "remove_dependency"
    if modified_nodes:
        return "strengthen_postcondition"
    return "mark_as_clarification_needed"


def attach_repair_mutations(
    previous_graph: CandidateTaskGraph,
    repaired_graph: CandidateTaskGraph,
    operations: list[RepairOperation],
) -> list[RepairOperation]:
    previous_nodes = {node.id: node for node in previous_graph.nodes}
    repaired_nodes = {node.id: node for node in repaired_graph.nodes}
    added_nodes = [
        repaired_nodes[task_id]
        for task_id in sorted(repaired_nodes.keys() - previous_nodes.keys())
    ]
    removed_nodes = [
        previous_nodes[task_id]
        for task_id in sorted(previous_nodes.keys() - repaired_nodes.keys())
    ]
    modified_nodes = [
        repaired_nodes[task_id]
        for task_id in sorted(previous_nodes.keys() & repaired_nodes.keys())
        if graph_fingerprint(
            CandidateTaskGraph(nodes=[previous_nodes[task_id]], edges=[])
        )
        != graph_fingerprint(
            CandidateTaskGraph(nodes=[repaired_nodes[task_id]], edges=[])
        )
    ]

    previous_edges = {_edge_identity(edge): edge for edge in previous_graph.edges}
    repaired_edges = {_edge_identity(edge): edge for edge in repaired_graph.edges}
    added_edges = [
        repaired_edges[key]
        for key in sorted(repaired_edges.keys() - previous_edges.keys())
    ]
    removed_edges = [
        previous_edges[key]
        for key in sorted(previous_edges.keys() - repaired_edges.keys())
    ]

    if not any(
        [added_nodes, removed_nodes, modified_nodes, added_edges, removed_edges]
    ):
        return operations

    if not operations:
        target = removed_nodes[0].id if removed_nodes else "task_graph"
        operations = [
            RepairOperation(
                operation=_choose_synthetic_operation(
                    added_nodes,
                    removed_nodes,
                    modified_nodes,
                    added_edges,
                    removed_edges,
                ),
                target=target,
                reason="Graph changed without an explicit repair operation.",
            )
        ]

    enriched: list[RepairOperation] = []
    for operation in operations:
        target_added = [node for node in added_nodes if node.id == operation.target]
        target_removed = [node for node in removed_nodes if node.id == operation.target]
        target_modified = [
            node for node in modified_nodes if node.id == operation.target
        ]

        operation_added_nodes = target_added or (
            added_nodes if operation.operation in {"add_task", "split_task"} else []
        )
        operation_removed_nodes = target_removed or (
            removed_nodes
            if operation.operation in {"remove_task", "split_task"}
            else []
        )
        operation_modified_nodes = target_modified or (
            modified_nodes
            if operation.operation
            in {
                "add_verifier",
                "change_executor",
                "merge_tasks",
                "strengthen_postcondition",
            }
            else []
        )
        if not any(
            [operation_added_nodes, operation_removed_nodes, operation_modified_nodes]
        ):
            operation_added_nodes = added_nodes
            operation_removed_nodes = removed_nodes
            operation_modified_nodes = modified_nodes

        enriched.append(
            operation.model_copy(
                update={
                    "added_task_ids": [node.id for node in operation_added_nodes],
                    "modified_task_ids": [node.id for node in operation_modified_nodes],
                    "replacement_tasks": operation_added_nodes,
                    "added_tasks": operation_added_nodes,
                    "added_nodes": operation_added_nodes,
                    "removed_nodes": operation_removed_nodes,
                    "modified_nodes": operation_modified_nodes,
                    "removed_task_ids": [node.id for node in operation_removed_nodes],
                    "added_edges": added_edges,
                    "removed_edges": removed_edges,
                }
            )
        )
    return enriched


def normalize_llm_repair_result(
    draft: LLMRepairResult, previous_graph: CandidateTaskGraph | None = None
) -> RepairResult:
    allowed_operations = {
        "add_task",
        "remove_task",
        "split_task",
        "merge_tasks",
        "add_dependency",
        "remove_dependency",
        "strengthen_postcondition",
        "add_verifier",
        "change_executor",
        "mark_as_clarification_needed",
    }
    repaired_task_graph = normalize_llm_task_graph(draft.repaired_task_graph)
    repair_operations = [
        RepairOperation(
            operation=_safe_choice(
                item.operation,
                allowed_operations,
                "mark_as_clarification_needed",
            ),
            target=item.target,
            reason=item.reason or item.suggested_change,
        )
        for item in draft.repair_operations
    ]
    if previous_graph is not None:
        repair_operations = attach_repair_mutations(
            previous_graph, repaired_task_graph, repair_operations
        )
    return RepairResult(
        repaired_task_graph=repaired_task_graph,
        repair_operations=repair_operations,
        unresolved_assumptions=draft.unresolved_assumptions,
        requires_user_clarification=draft.requires_user_clarification,
    )


def compute_overall_score(
    coverage_score: float,
    granularity_score: float,
    dependency_score: float,
    executability_score: float,
    verifiability_score: float,
) -> float:
    score = (
        0.25 * coverage_score
        + 0.20 * granularity_score
        + 0.20 * dependency_score
        + 0.20 * executability_score
        + 0.15 * verifiability_score
    )
    return round(max(0.0, min(1.0, score)), 4)


def collect_repair_suggestion_summaries(
    coverage: CoverageReport | None,
    granularity: GranularityReport | None,
    dependency: DependencyReport | None,
    executability: ExecutabilityReport | None,
    verifiability: VerifiabilityReport | None,
    task_ids: set[str] | None = None,
) -> list[str]:
    current_task_ids = task_ids or set()

    def keep_suggestion(item: RepairSuggestion) -> bool:
        return not current_task_ids or _repair_suggestion_is_current(
            item, current_task_ids
        )

    suggestions: list[str] = []
    if coverage:
        suggestions.extend(
            f"coverage:{item.operation}:{item.target}:{item.reason}"
            for item in coverage.repair_suggestions
            if keep_suggestion(item)
        )
        suggestions.extend(
            f"coverage:add_or_repair_goal_element:{item}"
            for item in coverage.missing_goal_elements
        )
    if granularity:
        suggestions.extend(
            f"granularity:{item.operation}:{item.target}:{item.reason}"
            for item in granularity.repair_suggestions
            if keep_suggestion(item)
        )
        suggestions.extend(
            f"granularity:split:{item}"
            for item in _current_task_references(
                granularity.tasks_to_split, current_task_ids
            )
        )
        suggestions.extend(
            f"granularity:merge:{item}"
            for item in _current_task_references(
                granularity.tasks_to_merge, current_task_ids
            )
        )
        suggestions.extend(
            f"granularity:remove:{item}"
            for item in _current_task_references(
                granularity.tasks_to_remove, current_task_ids
            )
        )
    if dependency:
        suggestions.extend(
            f"dependency:add_edge:{edge.from_task}->{edge.to}"
            for edge in dependency.missing_edges
            if not current_task_ids
            or (edge.from_task in current_task_ids and edge.to in current_task_ids)
        )
        suggestions.extend(
            f"dependency:remove_edge:{edge.from_task}->{edge.to}"
            for edge in dependency.invalid_edges
            if not current_task_ids
            or (edge.from_task in current_task_ids and edge.to in current_task_ids)
        )
        suggestions.extend(
            f"dependency:resolve_cycle:{'->'.join(cycle)}"
            for cycle in dependency.cycles
            if not current_task_ids
            or all(task_id in current_task_ids for task_id in cycle)
        )
    if executability:
        suggestions.extend(
            f"executability:blocked:{item}"
            for item in executability.blocked_tasks
            if not current_task_ids or item in current_task_ids
        )
        suggestions.extend(
            f"executability:missing_capability:{item}"
            for item in executability.missing_capabilities
        )
    if verifiability:
        suggestions.extend(
            f"verifiability:weak_postcondition:{item.task_id}:{item.problem}"
            for item in verifiability.weak_postconditions
            if not current_task_ids or item.task_id in current_task_ids
        )
        suggestions.extend(
            f"verifiability:missing_verifier:{item}"
            for item in verifiability.missing_verifiers
            if not current_task_ids or item in current_task_ids
        )
        suggestions.extend(
            f"verifiability:improve_verifier:{item.task_id}"
            for item in verifiability.verifier_improvements
            if not current_task_ids or item.task_id in current_task_ids
        )
    return list(dict.fromkeys(suggestions))


def collect_runtime_blockers(
    graph: CandidateTaskGraph, executability: ExecutabilityReport | None = None
) -> list[str]:
    blockers: list[str] = []
    for task in graph.nodes:
        blockers.extend(
            f"{task.id}: {item}" for item in task.execution.missing_runtime_inputs
        )
        if (
            task.execution.execution_status == "blocked_by_runtime_inputs"
            and not task.execution.missing_runtime_inputs
        ):
            blockers.append(f"{task.id}: runtime inputs are not available")
    if executability:
        blockers.extend(executability.missing_runtime_inputs)
    return list(dict.fromkeys(blockers))


def _rebuild_required_by(graph: CandidateTaskGraph) -> CandidateTaskGraph:
    updated = graph.model_copy(deep=True)
    required_by: dict[str, list[str]] = {node.id: [] for node in updated.nodes}
    for node in updated.nodes:
        for dependency_id in node.dependencies.requires:
            if (
                dependency_id in required_by
                and node.id not in required_by[dependency_id]
            ):
                required_by[dependency_id].append(node.id)
    for edge in updated.edges:
        if edge.from_task in required_by and edge.to not in required_by[edge.from_task]:
            required_by[edge.from_task].append(edge.to)
    for node in updated.nodes:
        node.dependencies.required_by = sorted(required_by[node.id])
    return updated


def _has_runtime_configuration_task(graph: CandidateTaskGraph) -> str | None:
    for task in graph.nodes:
        task_text = f"{task.id} {task.title} {task.description}".lower()
        if "runtime" in task_text and any(
            term in task_text for term in ["config", "environment", "secret"]
        ):
            return task.id
    return None


def _unique_task_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id
    index = 2
    while f"{base_id}_{index}" in existing_ids:
        index += 1
    return f"{base_id}_{index}"


def ensure_runtime_configuration_task(graph: CandidateTaskGraph) -> CandidateTaskGraph:
    blocked_task_ids = [
        task.id for task in graph.nodes if task.execution.missing_runtime_inputs
    ]
    if not blocked_task_ids:
        return _rebuild_required_by(graph)

    updated = graph.model_copy(deep=True)
    existing_ids = {task.id for task in updated.nodes}
    config_task_id = _has_runtime_configuration_task(updated)
    if config_task_id is None:
        config_task_id = _unique_task_id(
            "t0_configure_runtime_environment", existing_ids
        )
        config_task = TaskNode(
            id=config_task_id,
            title="Configure runtime environment and secrets",
            description=(
                "Define runtime configuration, secret handling and mock-mode behavior "
                "for external providers before live execution."
            ),
            action_type="configure",
            abstraction_level="meso",
            input_state=["goal_state_available"],
            output_state=["runtime_configuration"],
            preconditions=[
                _condition(
                    f"{config_task_id}_pre_1",
                    "Required provider and deployment choices are known or documented as assumptions.",
                    "test",
                )
            ],
            postconditions=[
                _condition(
                    f"{config_task_id}_post_1",
                    "Runtime configuration exists without committed secrets.",
                    "test",
                )
            ],
            executor=ExecutorSpec(
                type="agent",
                id="runtime_configuration_engineer",
                required_inputs=["goal_state_available"],
                expected_outputs=["runtime_configuration"],
            ),
            verifier=VerifierSpec(
                type="test",
                instruction=(
                    "Verify .env.example, secret validation, startup checks and mock "
                    "mode behavior without exposing secret values."
                ),
                success_threshold=0.9,
                failure_action="replan",
            ),
            acceptance_criteria=[
                ".env.example exists",
                "Secrets are not committed",
                "Provider keys are validated at startup",
                "System can run in mock mode without external keys",
            ],
            dependencies=TaskDependencies(requires=[]),
            execution=TaskExecution(mode="sequential", execution_status="executable"),
            decomposition=TaskDecomposition(
                can_expand=True,
                should_expand_now=False,
                expansion_reason=None,
                compressed_subgraph_ref=None,
            ),
            risk=TaskRisk(
                level="high",
                reasons=["Secret handling and runtime config affect live safety."],
            ),
        )
        updated.nodes = [config_task, *updated.nodes]

    for task in updated.nodes:
        if task.id in blocked_task_ids:
            if task.execution.execution_status == "executable":
                task.execution.execution_status = "blocked_by_runtime_inputs"
            if config_task_id not in task.dependencies.requires:
                task.dependencies.requires = [
                    config_task_id,
                    *task.dependencies.requires,
                ]

    existing_edges = {(edge.from_task, edge.to, edge.type) for edge in updated.edges}
    for task_id in blocked_task_ids:
        edge_key = (config_task_id, task_id, "requires_output")
        if edge_key not in existing_edges:
            updated.edges.append(
                TaskEdge.model_validate(
                    {
                        "from": config_task_id,
                        "to": task_id,
                        "type": "requires_output",
                        "reason": "Runtime configuration is required before live provider execution.",
                    }
                )
            )
            existing_edges.add(edge_key)

    if (
        "External runtime inputs must be supplied or mock mode must be enabled."
        not in updated.assumptions
    ):
        updated.assumptions.append(
            "External runtime inputs must be supplied or mock mode must be enabled."
        )
    return _rebuild_required_by(updated)


def _detect_mixed_implementation_runtime_graph(graph: CandidateTaskGraph) -> bool:
    if graph.graph_type == "mixed_graph":
        return True
    implementation_terms = {
        "build",
        "implement",
        "create",
        "define",
        "configure",
        "database",
        "schema",
        "adapter",
        "backend",
        "docker",
        "migration",
    }
    runtime_terms = {
        "user_query",
        "intent_profile",
        "research_run",
        "run_id",
        "search_results",
        "sources_retrieved",
        "documents_extracted",
        "claims_extracted",
        "signals_extracted",
        "events_extracted",
        "report_generated",
    }
    for task in graph.nodes:
        task_text = (
            f"{task.id} {task.title} {task.description} {task.action_type}".lower()
        )
        state_values = [*task.input_state, *task.output_state]
        if any(term in task_text for term in implementation_terms) and _contains_any(
            state_values, runtime_terms
        ):
            return True
    return False


def aggregate_quality_report(
    graph: CandidateTaskGraph,
    coverage: CoverageReport | None,
    granularity: GranularityReport | None,
    dependency: DependencyReport | None,
    executability: ExecutabilityReport | None,
    verifiability: VerifiabilityReport | None,
    goal_state: GoalState | None = None,
) -> QualityReport:
    coverage_score = coverage.score if coverage else 0.0
    granularity_score = granularity.score if granularity else 0.0
    dependency_score = dependency.score if dependency else 0.0
    executability_score = executability.score if executability else 0.0
    verifiability_score = verifiability.score if verifiability else 0.0

    critical_failures: list[str] = []
    warnings: list[str] = []
    task_ids = {task.id for task in graph.nodes}
    pending_repair_suggestions = collect_repair_suggestion_summaries(
        coverage,
        granularity,
        dependency,
        executability,
        verifiability,
        task_ids=task_ids,
    )
    runtime_blockers = collect_runtime_blockers(graph, executability)

    if not graph.nodes:
        critical_failures.append("The graph has no task nodes.")

    if _detect_mixed_implementation_runtime_graph(graph):
        critical_failures.append(
            "mixed_implementation_and_runtime_states: graph mixes build tasks with runtime inputs/outputs."
        )

    for task in graph.nodes:
        if not task.output_state:
            critical_failures.append(f"Task {task.id} has no output_state.")
        if not task.postconditions:
            critical_failures.append(f"Task {task.id} has no postcondition.")
        if not task.executor.id:
            critical_failures.append(f"Task {task.id} has no viable executor id.")
        if task.risk.level == "high" and not task.verifier.instruction:
            critical_failures.append(f"High-risk task {task.id} has no verifier.")
        for dependency_id in task.dependencies.requires:
            if dependency_id not in task_ids:
                critical_failures.append(
                    f"Task {task.id} depends on unknown task {dependency_id}."
                )

    if coverage:
        warnings.extend(
            f"Missing goal element: {item}" for item in coverage.missing_goal_elements
        )
        warnings.extend(
            f"Hidden assumption: {item}" for item in coverage.hidden_assumptions
        )
        if coverage.missing_goal_elements and coverage.score < 0.9:
            critical_failures.append(
                "missing_core_goal_elements: "
                + "; ".join(coverage.missing_goal_elements)
            )

    if granularity:
        warnings.extend(
            f"Task should split: {item}"
            for item in _current_task_references(granularity.tasks_to_split, task_ids)
        )
        warnings.extend(
            f"Task should merge: {item}"
            for item in _current_task_references(granularity.tasks_to_merge, task_ids)
        )
        warnings.extend(
            f"Task should remove: {item}"
            for item in _current_task_references(granularity.tasks_to_remove, task_ids)
        )

    if dependency:
        if dependency.cycles:
            critical_failures.extend(
                f"Dependency cycle detected: {' -> '.join(cycle)}"
                for cycle in dependency.cycles
            )
        warnings.extend(dependency.parallelization_warnings)

    if executability:
        blocked_task_ids = _current_task_references(
            executability.blocked_tasks, task_ids
        )
        if executability.score < 0.5 and blocked_task_ids:
            critical_failures.append(
                "Executability score is below the blocking threshold."
            )
        warnings.extend(f"Blocked task: {item}" for item in blocked_task_ids)
        warnings.extend(
            f"Conditionally executable task: {item}"
            for item in _current_task_references(
                executability.conditionally_executable_tasks, task_ids
            )
        )
        warnings.extend(
            f"Missing runtime input: {item}"
            for item in executability.missing_runtime_inputs
        )
        warnings.extend(
            f"Missing capability: {item}" for item in executability.missing_capabilities
        )

    if verifiability:
        missing_verifiers = set(verifiability.missing_verifiers)
        high_risk_without_verifier = [
            task.id
            for task in graph.nodes
            if task.risk.level == "high" and task.id in missing_verifiers
        ]
        critical_failures.extend(
            f"Critical task {task_id} has no verifier."
            for task_id in high_risk_without_verifier
        )
        warnings.extend(
            f"Weak postcondition on {item.task_id}: {item.problem}"
            for item in verifiability.weak_postconditions
            if item.task_id in task_ids
        )
        warnings.extend(
            f"Missing verifier: {item}"
            for item in verifiability.missing_verifiers
            if item in task_ids
        )

    warnings = remove_stale_node_diagnostics(list(dict.fromkeys(warnings)), graph)
    pending_repair_suggestions = remove_stale_node_diagnostics(
        list(dict.fromkeys(pending_repair_suggestions)), graph
    )

    overall_score = compute_overall_score(
        coverage_score,
        granularity_score,
        dependency_score,
        executability_score,
        verifiability_score,
    )

    if coverage and coverage.missing_goal_elements:
        overall_score = _cap_score(overall_score, 0.84)
    if pending_repair_suggestions:
        overall_score = _cap_score(overall_score, 0.84)
    if runtime_blockers:
        overall_score = _cap_score(overall_score, 0.90)
    if executability and executability.missing_capabilities:
        overall_score = _cap_score(overall_score, 0.85)
    if _detect_mixed_implementation_runtime_graph(graph):
        overall_score = _cap_score(overall_score, 0.78)

    status = "valid"
    graph_validity = "complete"
    structural_status = "valid"
    runtime_status = (
        "blocked_by_runtime_inputs" if runtime_blockers else "ready_for_execution"
    )
    must_apply_repairs_before_execution = False
    must_provide_runtime_inputs_before_execution = bool(runtime_blockers)
    if critical_failures:
        status = (
            "failed"
            if not graph.nodes or (dependency and dependency.cycles)
            else "needs_repair"
        )
        graph_validity = "invalid" if status == "failed" else "partial"
        structural_status = "invalid" if status == "failed" else "needs_repair"
        must_apply_repairs_before_execution = True
    elif pending_repair_suggestions:
        status = "needs_repair"
        graph_validity = "partial"
        structural_status = "needs_repair"
        must_apply_repairs_before_execution = True
    elif runtime_blockers:
        status = "blocked_by_runtime_inputs"
        graph_validity = "mostly_valid"
        structural_status = "mostly_valid" if warnings else "valid"
    elif warnings:
        status = "usable_with_warnings"
        graph_validity = "mostly_valid"
        structural_status = "mostly_valid"

    if goal_state and graph.graph_type == "implementation_task_graph":
        goal_text = " ".join(
            [
                goal_state.interpreted_goal,
                *goal_state.success_criteria,
                *goal_state.hard_constraints,
            ]
        ).lower()
        task_text = " ".join(f"{task.id} {task.title}" for task in graph.nodes).lower()
        if (
            all(term in goal_text for term in ["research", "audit"])
            and "planner" not in task_text
        ):
            critical_failures.append("missing_research_planner")
            pending_repair_suggestions.append("coverage:add_task:research_planner")
            overall_score = _cap_score(overall_score, 0.75)
            status = "needs_repair"
            graph_validity = "partial"
            structural_status = "needs_repair"
            must_apply_repairs_before_execution = True

    return QualityReport(
        status=status,
        graph_validity=graph_validity,
        structural_status=structural_status,
        runtime_status=runtime_status,
        must_apply_repairs_before_execution=must_apply_repairs_before_execution,
        must_provide_runtime_inputs_before_execution=(
            must_provide_runtime_inputs_before_execution
        ),
        coverage_score=coverage_score,
        granularity_score=granularity_score,
        dependency_score=dependency_score,
        executability_score=executability_score,
        verifiability_score=verifiability_score,
        overall_score=overall_score,
        critical_failures=list(dict.fromkeys(critical_failures)),
        warnings=warnings,
        pending_repair_suggestions=list(dict.fromkeys(pending_repair_suggestions)),
        runtime_blockers=runtime_blockers,
    )


def apply_final_quality_guard(
    quality_report: QualityReport,
    initial_graph: CandidateTaskGraph,
    final_graph: CandidateTaskGraph,
    repairs_applied: list[RepairOperation],
    pending_repair_suggestions: list[str],
    requires_user_clarification: bool,
) -> QualityReport:
    """Prevents unresolved diagnostics from being emitted as a clean success."""
    critical_failures = list(quality_report.critical_failures)
    warnings = list(quality_report.warnings)
    pending = list(
        dict.fromkeys(
            [*quality_report.pending_repair_suggestions, *pending_repair_suggestions]
        )
    )
    overall_score = quality_report.overall_score
    status = quality_report.status
    graph_validity = quality_report.graph_validity
    structural_status = quality_report.structural_status
    runtime_status = quality_report.runtime_status
    must_apply_repairs_before_execution = (
        quality_report.must_apply_repairs_before_execution
    )
    must_provide_runtime_inputs_before_execution = (
        quality_report.must_provide_runtime_inputs_before_execution
    )

    graph_changed = graph_fingerprint(initial_graph) != graph_fingerprint(final_graph)
    pending = remove_stale_node_diagnostics(pending, final_graph)
    warnings = remove_stale_node_diagnostics(warnings, final_graph)
    if pending and not repairs_applied:
        critical_failures.append("repairs_detected_but_not_applied")
        overall_score = _cap_score(overall_score, 0.75)
        status = "needs_repair"
        graph_validity = "partial"
        structural_status = "needs_repair"
        must_apply_repairs_before_execution = True
    elif repairs_applied and not graph_changed:
        critical_failures.append("repairs_applied_did_not_change_graph")
        overall_score = _cap_score(overall_score, 0.80)
        status = "needs_repair"
        graph_validity = "partial"
        structural_status = "needs_repair"
        must_apply_repairs_before_execution = True

    if requires_user_clarification:
        warnings.append("User clarification is required before execution.")
        status = "needs_repair"
        graph_validity = "partial"
        structural_status = "needs_repair"
        must_apply_repairs_before_execution = True
        overall_score = _cap_score(overall_score, 0.75)

    if final_graph.graph_type == "mixed_graph":
        critical_failures.append("mixed_graph_requires_explicit_split")
        status = "needs_repair"
        graph_validity = "partial"
        structural_status = "needs_repair"
        must_apply_repairs_before_execution = True
        overall_score = _cap_score(overall_score, 0.78)

    runtime_blockers = collect_runtime_blockers(final_graph)
    if runtime_blockers and not must_apply_repairs_before_execution:
        status = "blocked_by_runtime_inputs"
        graph_validity = "mostly_valid"
        runtime_status = "blocked_by_runtime_inputs"
        must_provide_runtime_inputs_before_execution = True

    return quality_report.model_copy(
        update={
            "status": status,
            "graph_validity": graph_validity,
            "structural_status": structural_status,
            "runtime_status": runtime_status,
            "must_apply_repairs_before_execution": must_apply_repairs_before_execution,
            "must_provide_runtime_inputs_before_execution": must_provide_runtime_inputs_before_execution,
            "overall_score": overall_score,
            "critical_failures": list(dict.fromkeys(critical_failures)),
            "warnings": remove_stale_node_diagnostics(
                list(dict.fromkeys(warnings)), final_graph
            ),
            "pending_repair_suggestions": pending,
            "runtime_blockers": list(
                dict.fromkeys([*quality_report.runtime_blockers, *runtime_blockers])
            ),
        }
    )


def _edge_requires(edge: TaskEdge) -> bool:
    return edge.type in {"requires_output", "enables", "validates", "integrates"}


def build_execution_schedule(graph: CandidateTaskGraph) -> ExecutionSchedule:
    task_ids = {task.id for task in graph.nodes}
    dependencies: dict[str, set[str]] = {
        task.id: set(task.dependencies.requires) for task in graph.nodes
    }
    warnings: list[str] = []

    for edge in graph.edges:
        if edge.from_task not in task_ids or edge.to not in task_ids:
            warnings.append(
                f"Ignoring edge with unknown task: {edge.from_task} -> {edge.to}"
            )
            continue
        if _edge_requires(edge):
            dependencies[edge.to].add(edge.from_task)

    for task_id, required_ids in dependencies.items():
        unknown = sorted(required_ids - task_ids)
        if unknown:
            warnings.append(
                f"Task {task_id} has unknown dependencies: {', '.join(unknown)}"
            )
            dependencies[task_id] = required_ids & task_ids

    dependents: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {}
    for task_id, required_ids in dependencies.items():
        indegree[task_id] = len(required_ids)
        for required_id in required_ids:
            dependents[required_id].add(task_id)

    ready = deque(sorted(task_id for task_id, count in indegree.items() if count == 0))
    phases: list[list[str]] = []
    scheduled: set[str] = set()

    while ready:
        current_level = list(ready)
        ready.clear()
        phases.append(current_level)
        scheduled.update(current_level)

        newly_ready: list[str] = []
        for task_id in current_level:
            for dependent_id in sorted(dependents[task_id]):
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    newly_ready.append(dependent_id)
        ready.extend(sorted(newly_ready))

    unscheduled = sorted(task_ids - scheduled)
    if unscheduled:
        warnings.append(
            "Cycle or unresolved dependency prevented normal scheduling: "
            + ", ".join(unscheduled)
        )
        phases.append(unscheduled)

    execution_phases: list[ExecutionPhase] = []
    for index, task_ids_in_phase in enumerate(phases, start=1):
        mode = "parallel" if len(task_ids_in_phase) > 1 else "sequential"
        convergence_task = None
        if mode == "parallel":
            current_set = set(task_ids_in_phase)
            for later_phase in phases[index:]:
                for candidate_id in later_phase:
                    if len(dependencies.get(candidate_id, set()) & current_set) > 1:
                        convergence_task = candidate_id
                        break
                if convergence_task:
                    break
        execution_phases.append(
            ExecutionPhase(
                phase_id=f"P{index}",
                mode=mode,
                tasks=task_ids_in_phase,
                convergence_task=convergence_task,
            )
        )

    return ExecutionSchedule(phases=execution_phases, warnings=warnings)


def render_human_readable_plan(output: TaskSplitterOutput) -> str:
    lines = [
        "# TaskSplitter Plan",
        "",
        "## Goal",
        "",
        output.task_graph.goal_state.interpreted_goal,
        "",
        "## Status",
        "",
        f"- Status: `{output.task_graph.status}`",
        f"- Graph validity: `{output.task_graph.quality_report.graph_validity}`",
        f"- Structural status: `{output.task_graph.quality_report.structural_status}`",
        f"- Runtime status: `{output.task_graph.quality_report.runtime_status}`",
        f"- Graph type: `{output.task_graph.graph_type}`",
        f"- Must apply repairs before execution: `{output.task_graph.quality_report.must_apply_repairs_before_execution}`",
        f"- Must provide runtime inputs before execution: `{output.task_graph.quality_report.must_provide_runtime_inputs_before_execution}`",
        "",
        "## Quality Score",
        "",
        f"{output.task_graph.quality_report.overall_score:.2f}",
        "",
        "## Tasks",
        "",
        "| Task ID | Title | Output State | Acceptance Criteria | Dependencies | Executor | Verifier | Phase |",
        "|---|---|---|---|---|---|---|---|",
    ]
    task_to_phase = {
        task_id: phase.phase_id
        for phase in output.task_graph.execution_schedule.phases
        for task_id in phase.tasks
    }
    for task in output.task_graph.nodes:
        lines.append(
            "| "
            + " | ".join(
                [
                    task.id,
                    task.title.replace("|", "/"),
                    ", ".join(task.output_state).replace("|", "/"),
                    "<br>".join(task.acceptance_criteria).replace("|", "/"),
                    ", ".join(task.dependencies.requires) or "none",
                    f"{task.executor.type}:{task.executor.id}",
                    f"{task.verifier.type}:{task.verifier.failure_action}",
                    task_to_phase.get(task.id, "unscheduled"),
                ]
            )
            + " |"
        )

    if output.task_graph.quality_report.critical_failures:
        lines.extend(["", "## Critical Failures"])
        lines.extend(
            f"- {item}" for item in output.task_graph.quality_report.critical_failures
        )

    if output.task_graph.quality_report.warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {item}" for item in output.task_graph.quality_report.warnings)

    if output.task_graph.quality_report.pending_repair_suggestions:
        lines.extend(["", "## Pending Repair Suggestions"])
        lines.extend(
            f"- {item}"
            for item in output.task_graph.quality_report.pending_repair_suggestions
        )

    if output.task_graph.quality_report.runtime_blockers:
        lines.extend(["", "## Runtime Blockers"])
        lines.extend(
            f"- {item}" for item in output.task_graph.quality_report.runtime_blockers
        )

    return "\n".join(lines)


def build_task_splitter_output(
    goal_state: GoalState,
    macro_state: MacroState,
    final_graph: CandidateTaskGraph,
    quality_report: QualityReport,
    execution_schedule: ExecutionSchedule,
    trace: DecompositionTrace,
) -> TaskSplitterOutput:
    task_graph = ValidatedTaskGraph(
        status=quality_report.status,
        graph_type=final_graph.graph_type,
        runtime_pipeline_ref=final_graph.runtime_pipeline_ref,
        goal_state=goal_state,
        initial_macrostate=macro_state,
        nodes=final_graph.nodes,
        edges=final_graph.edges,
        quality_report=quality_report,
        execution_schedule=execution_schedule,
    )
    output = TaskSplitterOutput(
        task_graph=task_graph,
        human_readable_plan="",
        decomposition_trace=trace,
    )
    return output.model_copy(
        update={"human_readable_plan": render_human_readable_plan(output)}
    )


def repair_operations_from_state(value: Any) -> list[RepairOperation]:
    if not value:
        return []
    return [model_from_state(RepairOperation, item) for item in value]


def quality_reports_from_state(value: Any) -> list[QualityReport]:
    if not value:
        return []
    return [model_from_state(QualityReport, item) for item in value]
