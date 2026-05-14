import json
import re
from collections import defaultdict, deque
from typing import Any, TypeVar

from pydantic import BaseModel

from app.task_splitter.schemas import (
    CandidateTaskGraph,
    Condition,
    CoverageReport,
    DecisionStep,
    DecompositionTrace,
    DependencyReport,
    ExecutabilityReport,
    ExecutionPhase,
    ExecutionSchedule,
    ExecutorSpec,
    GoalState,
    GranularityReport,
    InteractionActivationContract,
    LLMCandidateTaskGraph,
    LLMProblemDefinition,
    LLMRepairResult,
    MacroState,
    ProblemDefinition,
    QualityReport,
    RepairOperation,
    RepairOperationType,
    RepairResult,
    RepairSuggestion,
    RuntimeNodeContract,
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
_REPAIR_OPERATIONS_REQUIRING_MUTATION = {
    "split_task",
    "add_task",
    "remove_task",
    "add_dependency",
    "remove_dependency",
    "strengthen_postcondition",
    "add_verifier",
}


def graph_fingerprint(graph: CandidateTaskGraph) -> str:
    return json.dumps(model_dump(graph), sort_keys=True)


def _graph_snapshot(graph: CandidateTaskGraph) -> dict[str, Any]:
    return {
        "node_ids": sorted(task.id for task in graph.nodes),
        "edges": sorted(
            f"{edge.from_task}->{edge.to}:{edge.type}" for edge in graph.edges
        ),
        "interaction_activation_contract": model_dump(
            graph.interaction_activation_contract
        )
        if graph.interaction_activation_contract
        else None,
        "runtime_node_contracts": sorted(
            f"{contract.node_id}:{contract.runtime_boundary_type}"
            for contract in graph.runtime_node_contracts
        ),
    }


def _graph_integrity_warnings(graph: CandidateTaskGraph) -> list[str]:
    warnings: list[str] = []
    task_ids = [task.id for task in graph.nodes]
    duplicates = sorted(
        task_id for task_id in set(task_ids) if task_ids.count(task_id) > 1
    )
    if duplicates:
        warnings.append("duplicate_task_ids:" + ",".join(duplicates))
    task_id_set = set(task_ids)
    for task in graph.nodes:
        for dependency_id in task.dependencies.requires:
            if dependency_id not in task_id_set:
                warnings.append(f"unknown_dependency:{task.id}->{dependency_id}")
        if (
            task.execution.missing_runtime_inputs
            and task.execution.runtime_status == "ready"
        ):
            warnings.append(f"runtime_ready_with_missing_inputs:{task.id}")
    for edge in graph.edges:
        if edge.from_task not in task_id_set or edge.to not in task_id_set:
            warnings.append(f"unknown_edge:{edge.from_task}->{edge.to}")
    return warnings


def _graph_valid_after_repair(graph: CandidateTaskGraph) -> bool:
    return not _graph_integrity_warnings(graph)


def _modified_fields(
    added_nodes: list[TaskNode],
    removed_nodes: list[TaskNode],
    modified_nodes: list[TaskNode],
    added_edges: list[TaskEdge],
    removed_edges: list[TaskEdge],
    runtime_contracts_changed: bool = False,
    interaction_contract_changed: bool = False,
) -> list[str]:
    fields: list[str] = []
    if added_nodes:
        fields.append("nodes.added")
    if removed_nodes:
        fields.append("nodes.removed")
    if modified_nodes:
        fields.append("nodes.modified")
    if added_edges:
        fields.append("edges.added")
    if removed_edges:
        fields.append("edges.removed")
    if runtime_contracts_changed:
        fields.append("runtime_node_contracts.modified")
    if interaction_contract_changed:
        fields.append("interaction_activation_contract.modified")
    return fields


def _task_runtime_status(
    runtime_status: str, missing_runtime_inputs: list[str], execution_status: str
) -> str:
    normalized = _safe_choice(
        runtime_status,
        {"ready", "blocked_by_runtime_inputs", "mock_only", "not_applicable"},
        "ready",
    )
    if missing_runtime_inputs or execution_status == "blocked_by_runtime_inputs":
        return "blocked_by_runtime_inputs"
    return normalized


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


def normalize_llm_problem_definition(
    draft: LLMProblemDefinition,
) -> ProblemDefinition:
    requires_decomposition = bool(draft.requires_decomposition)
    should_invoke_task_splitter = bool(draft.should_invoke_task_splitter)
    approval_state = _safe_choice(
        draft.approval_state,
        {
            "not_required",
            "requested",
            "approved",
            "sufficient_confidence",
            "design_workflow_selected",
            "blocked",
        },
        "requested",
    )
    if not requires_decomposition:
        should_invoke_task_splitter = False
        approval_state = "not_required"

    return ProblemDefinition(
        input_classification=_safe_choice(
            draft.input_classification,
            {
                "empty",
                "greeting",
                "thanks",
                "confirmation",
                "small_talk",
                "direct_non_decomposable",
                "broad_goal",
                "implementation_goal",
                "research_goal",
                "workflow_design_goal",
                "execution_request",
            },
            "broad_goal" if requires_decomposition else "direct_non_decomposable",
        ),
        requires_decomposition=requires_decomposition,
        should_invoke_task_splitter=should_invoke_task_splitter,
        approval_state=approval_state,
        confidence=max(0.0, min(draft.confidence, 1.0)),
        process_explanation=draft.process_explanation,
        reformulated_problem=draft.reformulated_problem or draft.task_splitter_goal,
        initial_exploration=draft.initial_exploration,
        subtopics=draft.subtopics,
        approaches=draft.approaches,
        sources=draft.sources,
        available_tools=draft.available_tools,
        missing_tools=draft.missing_tools,
        ambiguities=draft.ambiguities,
        decision_steps=[
            DecisionStep(
                id=step.id,
                decision=step.decision,
                reason=step.reason,
                impact=step.impact,
                options=step.options
                or ["Si", "No", "Respuesta personalizada", "Elaborar plan"],
                default_value=step.default_value,
                recommended_resolver=_safe_choice(
                    step.recommended_resolver,
                    {"human", "agent", "policy", "memory", "auto"},
                    "auto",
                ),
                blocking=step.blocking,
                auto_resolution_criterion=step.auto_resolution_criterion,
                selected_value=step.selected_value or None,
                resolution_reason=step.resolution_reason or None,
            )
            for step in draft.decision_steps
        ],
        auto_resolved_decisions=draft.auto_resolved_decisions,
        important_escalations=draft.important_escalations,
        brief_plan=draft.brief_plan,
        task_splitter_goal=draft.task_splitter_goal or draft.reformulated_problem,
        direct_response=draft.direct_response or None,
        approval_request=draft.approval_request or None,
    )


def normalize_runtime_node_contract(contract: Any) -> RuntimeNodeContract:
    value = contract if isinstance(contract, dict) else model_dump(contract)
    return RuntimeNodeContract(
        node_id=value.get("node_id") or "unknown_node",
        runtime_boundary_type=_safe_choice(
            value.get("runtime_boundary_type", "normal"),
            {"start", "normal", "router", "join", "hitl", "auth", "final"},
            "normal",
        ),
        semantic_input=value.get("semantic_input") or "Semantic input not specified.",
        adk_runtime_input=value.get("adk_runtime_input")
        or "ADK runtime input not specified.",
        recommended_function_signature=value.get("recommended_function_signature")
        or "node_input: Any",
        normalization_required=list(value.get("normalization_required") or []),
        output_event_contract=value.get("output_event_contract")
        or "Event(output=...) contract not specified.",
        state_keys_written=list(value.get("state_keys_written") or []),
        route_values_emitted=list(value.get("route_values_emitted") or []),
        required_tests=list(value.get("required_tests") or []),
    )


def normalize_interaction_activation_contract(
    contract: Any,
) -> InteractionActivationContract:
    value = contract if isinstance(contract, dict) else model_dump(contract)
    return InteractionActivationContract(
        entrypoint_context=_safe_choice(
            value.get("entrypoint_context", "general_chat"),
            {"general_chat", "dedicated_workflow", "tool_invoked", "subworkflow"},
            "general_chat",
        ),
        activation_triggers=list(value.get("activation_triggers") or []),
        non_activation_inputs=list(value.get("non_activation_inputs") or []),
        deterministic_prechecks=list(value.get("deterministic_prechecks") or []),
        llm_intent_check=value.get("llm_intent_check")
        or "Use an LLM intent classifier only when deterministic prechecks cannot classify the input.",
        minimum_required_slots=list(value.get("minimum_required_slots") or []),
        clarification_policy=list(value.get("clarification_policy") or []),
        direct_response_policy=list(value.get("direct_response_policy") or []),
        hitl_policy=list(value.get("hitl_policy") or []),
        expensive_action_policy=list(value.get("expensive_action_policy") or []),
        required_interaction_tests=list(value.get("required_interaction_tests") or []),
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
        execution_mode = _safe_choice(
            draft_node.execution_mode,
            {"sequential", "parallel_candidate", "integration", "human_review"},
            "sequential",
        )
        parallel_group = (
            draft_node.parallel_group
            if execution_mode == "parallel_candidate"
            else None
        )
        build_status = _safe_choice(
            draft_node.build_status,
            {"executable", "blocked", "unknown"},
            "blocked" if execution_status == "blocked" else "executable",
        )
        runtime_status = _task_runtime_status(
            draft_node.runtime_status,
            draft_node.missing_runtime_inputs,
            execution_status,
        )
        runtime_execution_mode = _safe_choice(
            draft_node.runtime_execution_mode,
            {"mock", "real", "either"},
            "either",
        )
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
                "mode": execution_mode,
                "parallel_group": parallel_group,
                "build_status": build_status,
                "runtime_status": runtime_status,
                "runtime_execution_mode": runtime_execution_mode,
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
        interaction_activation_contract=normalize_interaction_activation_contract(
            draft.interaction_activation_contract
        )
        if draft.interaction_activation_contract
        else None,
        nodes=nodes,
        edges=edges,
        runtime_node_contracts=[
            normalize_runtime_node_contract(contract)
            for contract in draft.runtime_node_contracts
        ],
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
    runtime_contracts_changed = json.dumps(
        [model_dump(contract) for contract in previous_graph.runtime_node_contracts],
        sort_keys=True,
    ) != json.dumps(
        [model_dump(contract) for contract in repaired_graph.runtime_node_contracts],
        sort_keys=True,
    )
    interaction_contract_changed = json.dumps(
        model_dump(previous_graph.interaction_activation_contract)
        if previous_graph.interaction_activation_contract
        else None,
        sort_keys=True,
    ) != json.dumps(
        model_dump(repaired_graph.interaction_activation_contract)
        if repaired_graph.interaction_activation_contract
        else None,
        sort_keys=True,
    )
    before_snapshot = _graph_snapshot(previous_graph)
    after_snapshot = _graph_snapshot(repaired_graph)
    graph_integrity_warnings = _graph_integrity_warnings(repaired_graph)
    graph_valid_after_repair = not graph_integrity_warnings

    if not any(
        [
            added_nodes,
            removed_nodes,
            modified_nodes,
            added_edges,
            removed_edges,
            runtime_contracts_changed,
            interaction_contract_changed,
        ]
    ):
        return [
            operation.model_copy(
                update={
                    "repair_id": operation.repair_id or f"repair_{index:03d}",
                    "input_warning_or_suggestion": operation.input_warning_or_suggestion
                    or operation.reason,
                    "before_snapshot": before_snapshot,
                    "after_snapshot": after_snapshot,
                    "modified_fields": [],
                    "validation_after_repair": "failed"
                    if operation.operation in _REPAIR_OPERATIONS_REQUIRING_MUTATION
                    else "passed",
                    "validation": {
                        "graph_valid_after_repair": graph_valid_after_repair,
                        "introduced_new_warnings": graph_integrity_warnings,
                        "resolved_warnings": [],
                    },
                }
            )
            for index, operation in enumerate(operations, start=1)
        ]

    if not operations:
        target = (
            removed_nodes[0].id
            if removed_nodes
            else "runtime_node_contracts"
            if runtime_contracts_changed
            else "interaction_activation_contract"
            if interaction_contract_changed
            else "task_graph"
        )
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
    for index, operation in enumerate(operations, start=1):
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
        fields = _modified_fields(
            operation_added_nodes,
            operation_removed_nodes,
            operation_modified_nodes,
            added_edges,
            removed_edges,
            runtime_contracts_changed,
            interaction_contract_changed,
        )

        enriched.append(
            operation.model_copy(
                update={
                    "repair_id": operation.repair_id or f"repair_{index:03d}",
                    "input_warning_or_suggestion": operation.input_warning_or_suggestion
                    or operation.reason,
                    "before_snapshot": before_snapshot,
                    "after_snapshot": after_snapshot,
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
                    "modified_fields": fields,
                    "validation_after_repair": "passed"
                    if graph_valid_after_repair and fields
                    else "failed",
                    "validation": {
                        "graph_valid_after_repair": graph_valid_after_repair,
                        "introduced_new_warnings": graph_integrity_warnings,
                        "resolved_warnings": [operation.reason],
                    },
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
            task.execution.runtime_status == "blocked_by_runtime_inputs"
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
            execution=TaskExecution(
                mode="sequential",
                build_status="executable",
                runtime_status="not_applicable",
                runtime_execution_mode="either",
                execution_status="executable",
            ),
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
            if task.execution.runtime_status == "ready":
                task.execution.runtime_status = "blocked_by_runtime_inputs"
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


def _graph_search_text(graph: CandidateTaskGraph, goal_state: GoalState | None) -> str:
    values: list[str] = []
    if goal_state:
        values.extend(
            [
                goal_state.raw_goal,
                goal_state.interpreted_goal,
                *goal_state.success_criteria,
                *goal_state.hard_constraints,
                *goal_state.soft_constraints,
                *goal_state.unknowns,
            ]
        )
    values.extend(graph.assumptions)
    if graph.interaction_activation_contract:
        contract = graph.interaction_activation_contract
        values.extend(
            [
                contract.entrypoint_context,
                *contract.activation_triggers,
                *contract.non_activation_inputs,
                *contract.deterministic_prechecks,
                contract.llm_intent_check,
                *contract.minimum_required_slots,
                *contract.clarification_policy,
                *contract.direct_response_policy,
                *contract.hitl_policy,
                *contract.expensive_action_policy,
                *contract.required_interaction_tests,
            ]
        )
    for task in graph.nodes:
        values.extend(
            [
                task.id,
                task.title,
                task.description,
                task.action_type,
                *task.input_state,
                *task.output_state,
                *task.acceptance_criteria,
                task.verifier.instruction,
            ]
        )
    for edge in graph.edges:
        values.extend([edge.from_task, edge.to, edge.type, edge.reason])
    for contract in graph.runtime_node_contracts:
        values.extend(
            [
                contract.node_id,
                contract.runtime_boundary_type,
                contract.semantic_input,
                contract.adk_runtime_input,
                contract.recommended_function_signature,
                *contract.normalization_required,
                contract.output_event_contract,
                *contract.state_keys_written,
                *contract.route_values_emitted,
                *contract.required_tests,
            ]
        )
    return " ".join(values).lower()


def _is_adk2_workflow_plan(
    graph: CandidateTaskGraph, goal_state: GoalState | None
) -> bool:
    text = _graph_search_text(graph, goal_state)
    return "adk 2" in text or "adk2" in text or "workflow" in text


def _mentions_start_edge(
    graph: CandidateTaskGraph, goal_state: GoalState | None
) -> bool:
    if any(edge.from_task.upper() == "START" for edge in graph.edges):
        return True
    text = _graph_search_text(graph, goal_state)
    return "start" in text and "workflow" in text


def _contract_text(contract: RuntimeNodeContract) -> str:
    return " ".join(
        [
            contract.node_id,
            contract.runtime_boundary_type,
            contract.semantic_input,
            contract.adk_runtime_input,
            contract.recommended_function_signature,
            *contract.normalization_required,
            contract.output_event_contract,
            *contract.state_keys_written,
            *contract.route_values_emitted,
            *contract.required_tests,
        ]
    ).lower()


def _valid_start_runtime_contract(contract: RuntimeNodeContract) -> bool:
    runtime_input = contract.adk_runtime_input.lower()
    signature = contract.recommended_function_signature.lower()
    normalizers = " ".join(contract.normalization_required).lower()
    mentions_runtime_input = any(
        value in runtime_input
        for value in ["google.genai.types.content", "content", "any"]
    )
    signature_ok = "node_input: any" in signature or "node_input: content" in signature
    normalizes_content = "content.parts" in normalizers
    return mentions_runtime_input and signature_ok and normalizes_content


def _semantic_input_without_adk_runtime_contract(
    graph: CandidateTaskGraph, goal_state: GoalState | None
) -> bool:
    text = _graph_search_text(graph, goal_state)
    mentions_semantic_input = any(
        value in text for value in ["raw query", "raw_query", "researchquery"]
    )
    mentions_content_normalization = "content.parts" in text
    return mentions_semantic_input and not mentions_content_normalization


_GENERAL_CHAT_GATE_TERMS = {
    "intent_gate",
    "intent gate",
    "conversation_router",
    "conversation router",
    "activation_policy",
    "activation policy",
    "normalize_user_input",
    "normalize user input",
}
_COSTLY_FIRST_NODE_TERMS = {
    "planning",
    "planner",
    "provider",
    "tool",
    "executor",
    "hitl",
    "requestinput",
    "approval",
}
_REQUIRED_ROUTE_TERMS = {"greeting", "small_talk", "ambiguous"}
_REQUIRED_ACCEPTANCE_TEST_TERMS = {
    "hola": {"hola"},
    "gracias": {"gracias", "thanks"},
    "empty_or_whitespace": {'""', "empty", "whitespace"},
    "adk_clarification": {"adk"},
    "explicit_research_activation": {"investiga", "research", "busca fuentes"},
    "first_node_accepts_content": {"content"},
    "no_requestinput_before_intent_gate": {"requestinput", "intent_gate"},
    "no_tools_for_non_activation": {"tool", "provider", "smalltalk", "small_talk"},
}
_RESEARCH_ACTIVATION_TRIGGER_TERMS = {
    "investiga",
    "busca fuentes",
    "haz research",
    "research",
    "compara",
    "analiza en profundidad",
    "consulta la web",
    "prepara un informe",
}
_NON_ACTIVATION_TERMS = {
    "hola",
    "greeting",
    "gracias",
    "thanks",
    "small talk",
    "small_talk",
    "empty",
    "whitespace",
    "ambiguous",
    "si",
    "sí",
}


def _text_has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _text_has_all_categories(text: str, categories: dict[str, set[str]]) -> list[str]:
    return [
        label for label, terms in categories.items() if not _text_has_any(text, terms)
    ]


def _first_logical_runtime_text(graph: CandidateTaskGraph) -> str:
    start_contracts = [
        contract
        for contract in graph.runtime_node_contracts
        if contract.runtime_boundary_type == "start"
    ]
    if start_contracts:
        return " ".join(_contract_text(contract) for contract in start_contracts)

    incoming = {edge.to for edge in graph.edges if edge.from_task.upper() != "START"}
    start_targets = [
        edge.to for edge in graph.edges if edge.from_task.upper() == "START"
    ]
    first_task_ids = start_targets or [
        task.id
        for task in graph.nodes
        if task.id not in incoming and not task.dependencies.requires
    ]
    first_tasks = [task for task in graph.nodes if task.id in set(first_task_ids)]
    return " ".join(
        f"{task.id} {task.title} {task.description} {task.action_type} {task.executor.type} {task.executor.id}"
        for task in first_tasks
    ).lower()


def _interaction_activation_diagnostics(
    graph: CandidateTaskGraph, goal_state: GoalState | None
) -> tuple[list[str], list[str], list[str]]:
    critical_failures: list[str] = []
    warnings: list[str] = []
    pending_repair_suggestions: list[str] = []
    contract = graph.interaction_activation_contract
    if contract is None:
        return (
            ["missing_interaction_activation_contract"],
            [],
            ["coverage:add_interaction_activation_contract"],
        )

    contract_text = " ".join(
        [
            contract.entrypoint_context,
            *contract.activation_triggers,
            *contract.non_activation_inputs,
            *contract.deterministic_prechecks,
            contract.llm_intent_check,
            *contract.minimum_required_slots,
            *contract.clarification_policy,
            *contract.direct_response_policy,
            *contract.hitl_policy,
            *contract.expensive_action_policy,
            *contract.required_interaction_tests,
        ]
    ).lower()
    graph_text = _graph_search_text(graph, goal_state)
    route_text = " ".join(
        route
        for runtime_contract in graph.runtime_node_contracts
        for route in runtime_contract.route_values_emitted
    ).lower()
    first_runtime_text = _first_logical_runtime_text(graph)

    missing_tests = _text_has_all_categories(
        " ".join(contract.required_interaction_tests).lower(),
        _REQUIRED_ACCEPTANCE_TEST_TERMS,
    )
    if missing_tests:
        critical_failures.append(
            "missing_required_interaction_tests:" + ",".join(missing_tests)
        )
        pending_repair_suggestions.append("coverage:add_required_interaction_tests")

    if contract.entrypoint_context == "general_chat":
        if _text_has_any(
            first_runtime_text, _COSTLY_FIRST_NODE_TERMS
        ) and not _text_has_any(first_runtime_text, _GENERAL_CHAT_GATE_TERMS):
            critical_failures.append("general_chat_start_node_bypasses_intent_gate")
            pending_repair_suggestions.append("coverage:add_conversation_intent_gate")

        missing_routes = sorted(
            term
            for term in _REQUIRED_ROUTE_TERMS
            if term not in route_text + contract_text
        )
        if missing_routes:
            critical_failures.append(
                "missing_conversation_routes:" + ",".join(missing_routes)
            )
            pending_repair_suggestions.append("coverage:add_conversation_routes")

        has_non_activation_policy = _text_has_any(
            " ".join(contract.non_activation_inputs).lower(), _NON_ACTIVATION_TERMS
        )
        has_direct_response_policy = _text_has_any(
            " ".join(contract.direct_response_policy).lower(),
            {"greeting", "hola", "thanks", "gracias", "small_talk", "small talk"},
        )
        if not has_non_activation_policy or not has_direct_response_policy:
            critical_failures.append(
                "greeting_can_reach_planner_without_non_activation_policy"
            )
            pending_repair_suggestions.append("coverage:add_non_activation_policy")

        if "requestinput" in first_runtime_text or (
            "hitl" in first_runtime_text
            and not _text_has_any(first_runtime_text, _GENERAL_CHAT_GATE_TERMS)
        ):
            critical_failures.append("requestinput_before_intent_gate")
            pending_repair_suggestions.append("coverage:move_hitl_after_intent_gate")

    has_costly_work = _text_has_any(
        graph_text,
        {
            "research",
            "search",
            "provider",
            "external",
            "tool executor",
            "consulta la web",
        },
    )
    if has_costly_work:
        trigger_text = " ".join(contract.activation_triggers).lower()
        expensive_policy_text = " ".join(contract.expensive_action_policy).lower()
        if not _text_has_any(trigger_text, _RESEARCH_ACTIVATION_TRIGGER_TERMS):
            critical_failures.append("missing_explicit_costly_workflow_triggers")
            pending_repair_suggestions.append(
                "coverage:add_explicit_activation_triggers"
            )
        if not _text_has_any(
            expensive_policy_text,
            {"intent_gate", "explicit", "slots", "minimum", "workflow_request"},
        ):
            critical_failures.append("expensive_actions_not_gated_by_intent_policy")
            pending_repair_suggestions.append("coverage:gate_expensive_actions")

    for runtime_contract in graph.runtime_node_contracts:
        if runtime_contract.runtime_boundary_type != "hitl":
            continue
        hitl_text = _contract_text(runtime_contract)
        exposes_internal_payload = _text_has_any(
            hitl_text,
            {"approved_plan", "pydantic", "internal schema", "json schema"},
        )
        justified_advanced_mode = _text_has_any(
            " ".join(contract.hitl_policy).lower() + " " + hitl_text,
            {"advanced", "reviewer", "justification", "explicitly requested"},
        )
        if exposes_internal_payload and not justified_advanced_mode:
            critical_failures.append("hitl_exposes_internal_payload_to_end_user")
            pending_repair_suggestions.append("coverage:simplify_user_hitl_message")
        if not _text_has_any(
            " ".join(contract.hitl_policy).lower(),
            {
                "sensitive",
                "cost",
                "risk",
                "side effect",
                "low confidence",
                "ambiguous",
                "asked",
            },
        ):
            warnings.append("hitl_policy_does_not_limit_when_requestinput_is_allowed")

    return (
        list(dict.fromkeys(critical_failures)),
        list(dict.fromkeys(warnings)),
        list(dict.fromkeys(pending_repair_suggestions)),
    )


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
        if (
            task.execution.missing_runtime_inputs
            and task.execution.runtime_status == "ready"
        ):
            warnings.append(
                f"Task {task.id} has runtime_status ready with missing_runtime_inputs."
            )
        for dependency_id in task.dependencies.requires:
            if dependency_id not in task_ids:
                critical_failures.append(
                    f"Task {task.id} depends on unknown task {dependency_id}."
                )

    is_adk2_workflow_plan = _is_adk2_workflow_plan(graph, goal_state)
    start_contracts = [
        contract
        for contract in graph.runtime_node_contracts
        if contract.runtime_boundary_type == "start"
    ]
    if is_adk2_workflow_plan and not graph.runtime_node_contracts:
        critical_failures.append("missing_runtime_node_contracts")
        pending_repair_suggestions.append("coverage:add_runtime_node_contracts")
    if is_adk2_workflow_plan:
        (
            interaction_failures,
            interaction_warnings,
            interaction_repairs,
        ) = _interaction_activation_diagnostics(graph, goal_state)
        critical_failures.extend(interaction_failures)
        warnings.extend(interaction_warnings)
        pending_repair_suggestions.extend(interaction_repairs)
    if is_adk2_workflow_plan and _mentions_start_edge(graph, goal_state):
        if not start_contracts or not all(
            _valid_start_runtime_contract(contract) for contract in start_contracts
        ):
            critical_failures.append("missing_start_runtime_input_contract")
            pending_repair_suggestions.append(
                "coverage:add_start_runtime_input_contract"
            )
    if _semantic_input_without_adk_runtime_contract(graph, goal_state):
        warnings.append("semantic_input_without_adk_runtime_contract")

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


def _validate_execution_schedule(
    phases: list[ExecutionPhase], dependencies: dict[str, set[str]]
) -> list[str]:
    warnings: list[str] = []
    task_to_phase = {
        task_id: phase_index
        for phase_index, phase in enumerate(phases)
        for task_id in phase.tasks
    }
    for task_id, required_ids in dependencies.items():
        if task_id not in task_to_phase:
            warnings.append(f"Task {task_id} is missing from execution schedule.")
            continue
        for required_id in sorted(required_ids):
            if required_id not in task_to_phase:
                warnings.append(
                    f"Dependency {required_id} for task {task_id} is missing from execution schedule."
                )
                continue
            if task_to_phase[required_id] >= task_to_phase[task_id]:
                warnings.append(
                    "Schedule dependency violation: "
                    f"{required_id} must run before {task_id}."
                )

    for phase in phases:
        phase_task_set = set(phase.tasks)
        for task_id in phase.tasks:
            same_phase_dependencies = sorted(
                dependencies.get(task_id, set()) & phase_task_set
            )
            if same_phase_dependencies:
                warnings.append(
                    f"Schedule parallelization violation: {task_id} shares a phase with "
                    + ", ".join(same_phase_dependencies)
                )
        if phase.convergence_task:
            convergence_dependencies = dependencies.get(phase.convergence_task, set())
            if len(convergence_dependencies & phase_task_set) < 2:
                warnings.append(
                    f"Convergence task {phase.convergence_task} does not depend on multiple tasks in {phase.phase_id}."
                )
    return list(dict.fromkeys(warnings))


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

    warnings.extend(_validate_execution_schedule(execution_phases, dependencies))
    return ExecutionSchedule(
        phases=execution_phases, warnings=list(dict.fromkeys(warnings))
    )


def should_stop_before_task_splitter(problem_definition: ProblemDefinition) -> bool:
    if not problem_definition.requires_decomposition:
        return True
    if not problem_definition.should_invoke_task_splitter:
        return True
    return problem_definition.approval_state not in {
        "approved",
        "design_workflow_selected",
    }


def _markdown_list(items: list[str], empty: str = "None") -> list[str]:
    cleaned = [item for item in items if item]
    if not cleaned:
        return [f"- {empty}"]
    return [f"- {item}" for item in cleaned]


def _table_cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", "<br>")


def _inline_list(items: list[str], empty: str = "none") -> str:
    return ", ".join(items) if items else empty


def render_interaction_activation_contract_markdown(
    contract: InteractionActivationContract | None,
) -> list[str]:
    lines = [
        "## Interaction Activation Contract",
        "",
        "This contract decides whether a chat/playground input should converse, clarify, stop, or activate an expensive workflow.",
        "",
    ]
    if contract is None:
        lines.extend(["- No Interaction Activation Contract was produced."])
        return lines

    lines.extend(
        [
            f"- Entrypoint context: `{contract.entrypoint_context}`",
            "",
            "Activation triggers:",
            *_markdown_list(contract.activation_triggers),
            "",
            "Non-activation inputs:",
            *_markdown_list(contract.non_activation_inputs),
            "",
            "Deterministic prechecks:",
            *_markdown_list(contract.deterministic_prechecks),
            "",
            "LLM intent check:",
            f"- {contract.llm_intent_check}",
            "",
            "Minimum required slots:",
            *_markdown_list(contract.minimum_required_slots),
            "",
            "Clarification policy:",
            *_markdown_list(contract.clarification_policy),
            "",
            "Direct response policy:",
            *_markdown_list(contract.direct_response_policy),
            "",
            "HITL policy:",
            *_markdown_list(contract.hitl_policy),
            "",
            "Expensive action policy:",
            *_markdown_list(contract.expensive_action_policy),
            "",
            "Required interaction tests:",
            *_markdown_list(contract.required_interaction_tests),
        ]
    )
    return lines


def render_problem_definition_markdown(problem_definition: ProblemDefinition) -> str:
    lines = [
        "## Initial Problem Definition",
        "",
        f"- Input classification: `{problem_definition.input_classification}`",
        f"- Requires decomposition: `{problem_definition.requires_decomposition}`",
        f"- Should invoke TaskSplitter: `{problem_definition.should_invoke_task_splitter}`",
        f"- Approval state: `{problem_definition.approval_state}`",
        f"- Confidence: `{problem_definition.confidence:.2f}`",
        "",
        "### Process",
        "",
        problem_definition.process_explanation or "No process explanation provided.",
        "",
        "### Reformulated Problem",
        "",
        problem_definition.reformulated_problem
        or problem_definition.task_splitter_goal,
        "",
        "### Light Exploration",
        "",
        *_markdown_list(problem_definition.initial_exploration),
        "",
        "### Subtopics And Approaches",
        "",
        "Subtopics:",
        *_markdown_list(problem_definition.subtopics),
        "",
        "Approaches:",
        *_markdown_list(problem_definition.approaches),
        "",
        "### Sources And Tools",
        "",
        "Sources:",
        *_markdown_list(problem_definition.sources),
        "",
        "Available tools:",
        *_markdown_list(problem_definition.available_tools),
        "",
        "Missing tools:",
        *_markdown_list(problem_definition.missing_tools),
        "",
        "### Ambiguities",
        "",
        *_markdown_list(problem_definition.ambiguities),
    ]
    if problem_definition.decision_steps:
        lines.extend(
            [
                "",
                "### Decision Steps",
                "",
                "| ID | Decision | Reason | Impact | Options | Default | Resolver | Blocking | Auto-resolution Criterion | Selected |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for step in problem_definition.decision_steps:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(step.id),
                        _table_cell(step.decision),
                        _table_cell(step.reason),
                        _table_cell(step.impact),
                        _table_cell(_inline_list(step.options)),
                        _table_cell(step.default_value),
                        step.recommended_resolver,
                        str(step.blocking),
                        _table_cell(step.auto_resolution_criterion),
                        _table_cell(step.selected_value or "unresolved"),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "### Auto-resolved Decisions",
            "",
            *_markdown_list(problem_definition.auto_resolved_decisions),
            "",
            "### Important Escalations",
            "",
            *_markdown_list(problem_definition.important_escalations),
            "",
            "### Brief Plan Before Splitting",
            "",
            *_markdown_list(problem_definition.brief_plan),
            "",
            "### TaskSplitter Goal",
            "",
            problem_definition.task_splitter_goal
            or problem_definition.reformulated_problem,
        ]
    )
    return "\n".join(lines)


def render_problem_definition_stop_message(
    problem_definition: ProblemDefinition,
) -> str:
    if not problem_definition.requires_decomposition:
        return (
            problem_definition.direct_response
            or "No decomposition is needed for this input."
        )

    lines = [
        "# Problem Definition Checkpoint",
        "",
        render_problem_definition_markdown(problem_definition),
        "",
        "## Control Point",
        "",
        problem_definition.approval_request
        or "Approve, modify, or choose Elaborar plan to continue with the available information.",
    ]
    return "\n".join(lines)


def render_human_readable_plan(output: TaskSplitterOutput) -> str:
    lines = [
        "# ADK 2.0 Workflow Implementation Plan",
        "",
        "## Goal",
        "",
        output.task_graph.goal_state.interpreted_goal,
        "",
        "## Planning Philosophy",
        "",
        "- Default implementation target: ADK 2.0 graph-based `Workflow`.",
        "- Primary orchestration pattern: explicit graph edges, route dictionaries, route loops and `JoinNode` for fan-out/fan-in convergence.",
        "- Internal data passing: `Event(output=...)` or `Event(state=...)`; reserve `Event(message=...)` for user-facing messages.",
        "- Secondary patterns avoided by default: collaborative agents and dynamic workflows with `Context.run_node`.",
        "- If a secondary pattern becomes necessary, record opt-in and compare against graph routes, static fan-out and `JoinNode` alternatives first.",
        "- ADK 2.0 is beta; confirm `google-adk>=2.0.0b1` opt-in and do not rely on Live Streaming for graph-based workflows.",
        "",
    ]
    if output.problem_definition:
        lines.extend(
            [render_problem_definition_markdown(output.problem_definition), ""]
        )

    lines.extend(
        [
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
            "## Implementation Architecture",
            "",
            "- Export a `root_agent` that is an ADK 2.0 `Workflow` from the expected module.",
            "- Keep each node single-purpose and task-oriented; do not model open-ended chat subagents inside the graph.",
            "- For chat/playground entrypoints, route through `normalize_user_input` and `intent_gate` before planner, provider, HITL or tool nodes.",
            "- Declare graph edges from `START`, then route through explicit node objects or route dictionaries.",
            "- Use Pydantic `input_schema` and `output_schema` at fragile boundaries and preserve stable state keys.",
            "- Model branch convergence as `JoinNode`, integration tasks or explicit route contracts, not implicit shared state.",
            "- Add deterministic tests before live evals or deployment: import/export, route keys, schema validation, joins and HITL resume/auth if applicable.",
            "",
        ]
    )

    lines.extend(
        render_interaction_activation_contract_markdown(
            output.task_graph.interaction_activation_contract
        )
    )
    lines.append("")

    lines.extend(
        [
            "## Runtime Node Contracts",
            "",
            "These contracts describe real ADK 2.0 runner boundaries, separate from semantic and Pydantic schema contracts.",
            "",
            "- `START` boundary nodes receive `google.genai.types.Content` or `Any`, then normalize `Content.parts -> str -> semantic schema`.",
            "- Post-`JoinNode` nodes receive `Any` and normalize `dict | list | tuple | Event.output | model` shapes.",
            "- HITL nodes use stable `interrupt_id`, `rerun_on_resume=True`, `ctx.resume_inputs[interrupt_id]` normalization and emit only explicit routes such as `approved`, `rejected`, `revise`.",
            "- Keep ADK 2.0 Workflow, explicit edges, static routing, `JoinNode`, provider abstraction and no dynamic/collaborative agents unless there is explicit opt-in.",
            "",
        ]
    )
    if output.task_graph.runtime_node_contracts:
        lines.extend(
            [
                "| Node ID | Boundary | Semantic Input | ADK Runtime Input | Function Signature | Normalization | Output Event | State Keys | Routes | Required Tests |",
                "|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for contract in output.task_graph.runtime_node_contracts:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _table_cell(contract.node_id),
                        contract.runtime_boundary_type,
                        _table_cell(contract.semantic_input),
                        _table_cell(contract.adk_runtime_input),
                        _table_cell(contract.recommended_function_signature),
                        _table_cell("<br>".join(contract.normalization_required)),
                        _table_cell(contract.output_event_contract),
                        _table_cell(_inline_list(contract.state_keys_written)),
                        _table_cell(_inline_list(contract.route_values_emitted)),
                        _table_cell("<br>".join(contract.required_tests)),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- No runtime node contracts were produced.")

    lines.extend(
        [
            "",
            "## Workflow Graph Contract",
            "",
            "| Task ID | Title | Output State | Acceptance Criteria | Dependencies | Executor | Verifier | Build | Runtime | Phase |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
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
                    _table_cell(task.title),
                    _table_cell(_inline_list(task.output_state)),
                    _table_cell("<br>".join(task.acceptance_criteria)),
                    ", ".join(task.dependencies.requires) or "none",
                    f"{task.executor.type}:{task.executor.id}",
                    f"{task.verifier.type}:{task.verifier.failure_action}",
                    task.execution.build_status,
                    task.execution.runtime_status,
                    task_to_phase.get(task.id, "unscheduled"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Detailed Task Specifications"])

    for task in output.task_graph.nodes:
        lines.extend(
            [
                "",
                f"### {task.id}: {task.title}",
                "",
                task.description,
                "",
                f"- Action type: `{task.action_type}`",
                f"- Abstraction level: `{task.abstraction_level}`",
                f"- Execution mode: `{task.execution.mode}`",
                f"- Parallel group: `{task.execution.parallel_group or 'none'}`",
                f"- Build status: `{task.execution.build_status}`",
                f"- Runtime status: `{task.execution.runtime_status}`",
                f"- Runtime execution mode: `{task.execution.runtime_execution_mode}`",
                f"- Execution status: `{task.execution.execution_status}`",
                f"- Branch condition: `{task.execution.branch_condition or 'none'}`",
                f"- Risk: `{task.risk.level}`",
                "",
                "Inputs:",
                *_markdown_list(task.input_state),
                "",
                "Outputs:",
                *_markdown_list(task.output_state),
                "",
                "Preconditions:",
                *_markdown_list(
                    [condition.condition for condition in task.preconditions]
                ),
                "",
                "Postconditions:",
                *_markdown_list(
                    [condition.condition for condition in task.postconditions]
                ),
                "",
                "Acceptance criteria:",
                *_markdown_list(task.acceptance_criteria),
                "",
                "Executor contract:",
                f"- Type/id: `{task.executor.type}:{task.executor.id}`",
                f"- Required inputs: {_inline_list(task.executor.required_inputs)}",
                f"- Expected outputs: {_inline_list(task.executor.expected_outputs)}",
                f"- Fallback executor: `{task.executor.fallback_executor or 'none'}`",
                "",
                "Verifier contract:",
                f"- Type: `{task.verifier.type}`",
                f"- Instruction: {task.verifier.instruction}",
                f"- Success threshold: `{task.verifier.success_threshold:.2f}`",
                f"- Failure action: `{task.verifier.failure_action}`",
                "",
                "Decomposition guidance:",
                f"- Can expand: `{task.decomposition.can_expand}`",
                f"- Should expand now: `{task.decomposition.should_expand_now}`",
                f"- Expansion reason: {task.decomposition.expansion_reason or 'none'}",
                f"- Compressed subgraph ref: `{task.decomposition.compressed_subgraph_ref or 'none'}`",
                "",
                "Risk reasons:",
                *_markdown_list(task.risk.reasons),
            ]
        )
        if task.execution.missing_runtime_inputs:
            lines.extend(
                [
                    "",
                    "Missing runtime inputs:",
                    *_markdown_list(task.execution.missing_runtime_inputs),
                ]
            )

    lines.extend(["", "## Edges And Data Flow"])
    if output.task_graph.edges:
        lines.extend(["", "| From | To | Type | Reason |", "|---|---|---|---|"])
        for edge in output.task_graph.edges:
            lines.append(
                f"| {_table_cell(edge.from_task)} | {_table_cell(edge.to)} | {edge.type} | {_table_cell(edge.reason)} |"
            )
    else:
        lines.extend(["", "- No explicit edges were produced."])

    lines.extend(["", "## Execution Schedule"])
    if output.task_graph.execution_schedule.phases:
        lines.extend(
            [
                "",
                "| Phase | Mode | Tasks | Convergence Task |",
                "|---|---|---|---|",
            ]
        )
        for phase in output.task_graph.execution_schedule.phases:
            lines.append(
                f"| {phase.phase_id} | {phase.mode} | {_table_cell(_inline_list(phase.tasks))} | {phase.convergence_task or 'none'} |"
            )
    else:
        lines.extend(["", "- No schedule phases were produced."])

    if output.task_graph.execution_schedule.warnings:
        lines.extend(["", "Schedule warnings:"])
        lines.extend(_markdown_list(output.task_graph.execution_schedule.warnings))

    lines.extend(
        [
            "",
            "## ADK 2.0 Implementation Checklist",
            "",
            "- Confirm project opt-in to ADK 2.0 beta and dependency `google-adk>=2.0.0b1`.",
            "- Include an `Interaction Activation Contract` before any planner/provider/tool/HITL behavior.",
            "- For `entrypoint_context=general_chat`, start `START -> normalize_user_input -> intent_gate` and route greetings, thanks, small talk, ambiguous inputs and simple questions away from expensive workflows.",
            "- Activate research/search/provider work only for explicit triggers such as `investiga`, `busca fuentes`, `haz research`, `compara`, `analiza en profundidad`, `consulta la web` or `prepara un informe`.",
            "- Answer greetings/thanks/small talk with `Event(message=...)` and do not create plans, HITL forms, tools or provider calls for those inputs.",
            "- Define `Workflow(name=..., edges=[...])` with at least one edge from `START`.",
            '- Test `planning_node(Content(role="user", parts=[Part(text="topic")]))` returns `Event(output=ResearchPlan)` for START-connected planning nodes.',
            "- Encode routing nodes so emitted `Event(route=...)` values exactly match route dictionary keys.",
            "- Ensure every node emits at most one `Event.output` per run.",
            "- Use `Event(output=...)` for handoff data and `Event(state=...)` for durable workflow state.",
            "- Use `Event(message=...)` only for user-visible responses.",
            "- Guarantee every branch that reaches a `JoinNode` emits output, including failure outputs.",
            "- Require each JoinNode-bound branch to emit a `BranchResult`, including skipped or failed branches.",
            "- Normalize post-join inputs from `dict`, `list`, `tuple`, `Event.output` and Pydantic model instances.",
            "- Keep loops bounded with an explicit exit route or deterministic stop condition.",
            "- Add HITL `RequestInput`, stable `interrupt_id` and `rerun_on_resume=True` tests only after intent and minimum slots are validated and policy requires human input.",
            "- Keep end-user HITL messages natural and brief; do not expose internal schemas such as `approved_plan` unless advanced reviewer mode is explicitly justified.",
            "- Test HITL first pause and resume via `ctx.resume_inputs[interrupt_id]` for string, dict and schema-shaped inputs.",
            "- Add auth tests that verify credentials are requested and consumed without printing secrets.",
            "- Avoid collaborative agents and dynamic workflows unless an explicit opt-in decision is recorded.",
            "",
            "## Verification Strategy",
            "",
            "- Unit-test deterministic graph helpers, route functions and schema transformations.",
            "- Test module import and `root_agent` export without live model calls.",
            "- Test every route key and every fallback route with representative inputs.",
            "- Test fan-out/fan-in convergence and failure-path convergence.",
            "- Use evals for LLM behavior only after explicit approval to run eval commands.",
            "- Do not run deploy, infra, playground or publish commands without explicit approval.",
        ]
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
    problem_definition: ProblemDefinition | None = None,
) -> TaskSplitterOutput:
    task_graph = ValidatedTaskGraph(
        status=quality_report.status,
        graph_type=final_graph.graph_type,
        runtime_pipeline_ref=final_graph.runtime_pipeline_ref,
        interaction_activation_contract=final_graph.interaction_activation_contract,
        goal_state=goal_state,
        initial_macrostate=macro_state,
        nodes=final_graph.nodes,
        edges=final_graph.edges,
        runtime_node_contracts=final_graph.runtime_node_contracts,
        quality_report=quality_report,
        execution_schedule=execution_schedule,
    )
    output = TaskSplitterOutput(
        task_graph=task_graph,
        human_readable_plan="",
        decomposition_trace=trace,
        problem_definition=problem_definition,
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
