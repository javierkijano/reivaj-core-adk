from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]
GraphType = Literal["implementation_task_graph", "runtime_task_graph", "mixed_graph"]
InputClassification = Literal[
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
]
ProblemApprovalState = Literal[
    "not_required",
    "requested",
    "approved",
    "sufficient_confidence",
    "design_workflow_selected",
    "blocked",
]
DecisionResolver = Literal["human", "agent", "policy", "memory", "auto"]
QualityStatus = Literal[
    "valid",
    "needs_repair",
    "usable_with_warnings",
    "blocked_by_runtime_inputs",
    "ready_for_execution",
    "ready_for_execution_with_mock_mode",
    "failed",
]
GraphValidity = Literal["complete", "mostly_valid", "partial", "invalid"]
StructuralStatus = Literal["valid", "mostly_valid", "needs_repair", "invalid"]
RuntimeStatus = Literal[
    "ready_for_execution",
    "blocked_by_runtime_inputs",
    "ready_for_execution_with_mock_mode",
    "unknown",
]
AbstractionLevel = Literal["micro", "meso", "macro"]
EvaluatorType = Literal["llm", "function", "tool", "human", "schema", "test"]
ExecutorType = Literal["agent", "tool", "skill", "workflow", "human"]
VerifierType = Literal["llm", "function", "tool", "test", "human", "schema_validation"]
FailureAction = Literal["replan", "retry", "escalate", "ask_user", "stop"]
ExecutionMode = Literal[
    "sequential", "parallel_candidate", "integration", "human_review"
]
ExecutionStatus = Literal[
    "executable",
    "conditionally_executable",
    "blocked",
    "blocked_by_runtime_inputs",
]
BuildStatus = Literal["executable", "blocked", "unknown"]
TaskRuntimeStatus = Literal[
    "ready", "blocked_by_runtime_inputs", "mock_only", "not_applicable"
]
RuntimeExecutionMode = Literal["mock", "real", "either"]
RuntimeBoundaryType = Literal[
    "start", "normal", "router", "join", "hitl", "auth", "final"
]
EntrypointContext = Literal[
    "general_chat", "dedicated_workflow", "tool_invoked", "subworkflow"
]
PhaseMode = Literal["sequential", "parallel"]
EdgeType = Literal[
    "requires_output",
    "enables",
    "validates",
    "integrates",
    "blocks",
    "alternative_to",
    "recovery_for",
]
RepairOperationType = Literal[
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
]


class Condition(BaseModel):
    id: str = Field(description="Stable condition identifier.")
    condition: str = Field(description="Observable condition to evaluate.")
    evaluator_type: EvaluatorType = Field(description="How the condition is evaluated.")
    evaluator_instruction: str = Field(description="Instruction for the evaluator.")
    observable: bool = Field(description="Whether this condition is observable.")
    confidence_threshold: float = Field(
        ge=0.0,
        le=1.0,
        description="Minimum confidence required to treat the condition as satisfied.",
    )


class ExecutorSpec(BaseModel):
    type: ExecutorType = Field(description="Executor kind.")
    id: str = Field(description="Executor identifier or proposed executor name.")
    required_inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    fallback_executor: str | None = Field(default=None)


class VerifierSpec(BaseModel):
    type: VerifierType = Field(description="Verifier kind.")
    instruction: str = Field(description="Verification instruction.")
    success_threshold: float = Field(ge=0.0, le=1.0)
    failure_action: FailureAction = Field(
        description="What to do if verification fails."
    )


class TaskDependencies(BaseModel):
    requires: list[str] = Field(default_factory=list)
    required_by: list[str] = Field(default_factory=list)


class TaskExecution(BaseModel):
    mode: ExecutionMode
    parallel_group: str | None = None
    build_status: BuildStatus = "executable"
    runtime_status: TaskRuntimeStatus = "ready"
    runtime_execution_mode: RuntimeExecutionMode = "either"
    execution_status: ExecutionStatus = "executable"
    missing_runtime_inputs: list[str] = Field(default_factory=list)
    branch_condition: str | None = None


class TaskDecomposition(BaseModel):
    can_expand: bool
    should_expand_now: bool
    expansion_reason: str | None = None
    compressed_subgraph_ref: str | None = None


class TaskRisk(BaseModel):
    level: RiskLevel
    reasons: list[str] = Field(default_factory=list)


class TaskNode(BaseModel):
    id: str
    title: str
    description: str
    action_type: str
    abstraction_level: AbstractionLevel
    input_state: list[str] = Field(default_factory=list)
    output_state: list[str] = Field(default_factory=list)
    preconditions: list[Condition] = Field(default_factory=list)
    postconditions: list[Condition] = Field(default_factory=list)
    executor: ExecutorSpec
    verifier: VerifierSpec
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: TaskDependencies = Field(default_factory=TaskDependencies)
    execution: TaskExecution
    decomposition: TaskDecomposition
    risk: TaskRisk


class TaskEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_task: str = Field(alias="from", serialization_alias="from")
    to: str
    type: EdgeType
    reason: str


class RuntimeNodeContract(BaseModel):
    node_id: str
    runtime_boundary_type: RuntimeBoundaryType
    semantic_input: str
    adk_runtime_input: str
    recommended_function_signature: str
    normalization_required: list[str] = Field(default_factory=list)
    output_event_contract: str
    state_keys_written: list[str] = Field(default_factory=list)
    route_values_emitted: list[str] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)


class InteractionActivationContract(BaseModel):
    entrypoint_context: EntrypointContext
    activation_triggers: list[str] = Field(default_factory=list)
    non_activation_inputs: list[str] = Field(default_factory=list)
    deterministic_prechecks: list[str] = Field(default_factory=list)
    llm_intent_check: str
    minimum_required_slots: list[str] = Field(default_factory=list)
    clarification_policy: list[str] = Field(default_factory=list)
    direct_response_policy: list[str] = Field(default_factory=list)
    hitl_policy: list[str] = Field(default_factory=list)
    expensive_action_policy: list[str] = Field(default_factory=list)
    required_interaction_tests: list[str] = Field(default_factory=list)


class GoalState(BaseModel):
    raw_goal: str
    interpreted_goal: str
    success_criteria: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_constraints: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class LLMDecisionStep(BaseModel):
    """Live-safe decision-step schema used as Gemini response_schema."""

    id: str
    decision: str
    reason: str
    impact: str
    options: list[str] = Field(default_factory=list)
    default_value: str
    recommended_resolver: str
    blocking: bool
    auto_resolution_criterion: str
    selected_value: str
    resolution_reason: str


class LLMProblemDefinition(BaseModel):
    """Live-safe flattened schema for the problem-definition model call."""

    input_classification: str
    requires_decomposition: bool
    should_invoke_task_splitter: bool
    approval_state: str
    confidence: float = Field(ge=0.0, le=1.0)
    process_explanation: str
    reformulated_problem: str
    initial_exploration: list[str] = Field(default_factory=list)
    subtopics: list[str] = Field(default_factory=list)
    approaches: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    decision_steps: list[LLMDecisionStep] = Field(default_factory=list)
    auto_resolved_decisions: list[str] = Field(default_factory=list)
    important_escalations: list[str] = Field(default_factory=list)
    brief_plan: list[str] = Field(default_factory=list)
    task_splitter_goal: str
    direct_response: str
    approval_request: str


class DecisionStep(BaseModel):
    id: str
    decision: str = Field(description="Question or decision to resolve.")
    reason: str
    impact: str
    options: list[str] = Field(
        default_factory=lambda: [
            "Si",
            "No",
            "Respuesta personalizada",
            "Elaborar plan",
        ]
    )
    default_value: str
    recommended_resolver: DecisionResolver
    blocking: bool
    auto_resolution_criterion: str
    selected_value: str | None = None
    resolution_reason: str | None = None


class ProblemDefinition(BaseModel):
    input_classification: InputClassification
    requires_decomposition: bool
    should_invoke_task_splitter: bool
    approval_state: ProblemApprovalState
    confidence: float = Field(ge=0.0, le=1.0)
    process_explanation: str
    reformulated_problem: str
    initial_exploration: list[str] = Field(default_factory=list)
    subtopics: list[str] = Field(default_factory=list)
    approaches: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    decision_steps: list[DecisionStep] = Field(default_factory=list)
    auto_resolved_decisions: list[str] = Field(default_factory=list)
    important_escalations: list[str] = Field(default_factory=list)
    brief_plan: list[str] = Field(default_factory=list)
    task_splitter_goal: str
    direct_response: str | None = None
    approval_request: str | None = None


class MacroState(BaseModel):
    known_facts: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    available_capabilities: list[str] = Field(default_factory=list)
    relevant_constraints: list[str] = Field(default_factory=list)
    task_family: str
    ambiguity_level: RiskLevel
    risk_level: RiskLevel


class CapabilitySpec(BaseModel):
    id: str
    type: ExecutorType
    description: str


class CandidateTaskGraph(BaseModel):
    graph_type: GraphType = "implementation_task_graph"
    runtime_pipeline_ref: str | None = None
    interaction_activation_contract: InteractionActivationContract | None = None
    nodes: list[TaskNode] = Field(default_factory=list)
    edges: list[TaskEdge] = Field(default_factory=list)
    runtime_node_contracts: list[RuntimeNodeContract] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class LLMRuntimeNodeContract(BaseModel):
    """Live-safe runtime contract schema used as Gemini response_schema."""

    node_id: str
    runtime_boundary_type: str
    semantic_input: str
    adk_runtime_input: str
    recommended_function_signature: str
    normalization_required: list[str] = Field(default_factory=list)
    output_event_contract: str
    state_keys_written: list[str] = Field(default_factory=list)
    route_values_emitted: list[str] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)


class LLMInteractionActivationContract(BaseModel):
    """Live-safe activation policy schema used as Gemini response_schema."""

    entrypoint_context: str
    activation_triggers: list[str] = Field(default_factory=list)
    non_activation_inputs: list[str] = Field(default_factory=list)
    deterministic_prechecks: list[str] = Field(default_factory=list)
    llm_intent_check: str
    minimum_required_slots: list[str] = Field(default_factory=list)
    clarification_policy: list[str] = Field(default_factory=list)
    direct_response_policy: list[str] = Field(default_factory=list)
    hitl_policy: list[str] = Field(default_factory=list)
    expensive_action_policy: list[str] = Field(default_factory=list)
    required_interaction_tests: list[str] = Field(default_factory=list)


class LLMTaskNode(BaseModel):
    """Live-safe flattened task schema used as model response_schema."""

    id: str
    title: str
    description: str
    action_type: str
    abstraction_level: str
    input_state: list[str] = Field(default_factory=list)
    output_state: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    executor_type: str
    executor_id: str
    verifier_type: str
    verifier_instruction: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    execution_mode: str
    parallel_group: str | None = None
    build_status: str = "executable"
    runtime_status: str = "ready"
    runtime_execution_mode: str = "either"
    execution_status: str = "executable"
    missing_runtime_inputs: list[str] = Field(default_factory=list)
    branch_condition: str | None = None
    can_expand: bool
    should_expand_now: bool
    expansion_reason: str | None = None
    risk_level: str
    risk_reasons: list[str] = Field(default_factory=list)


class LLMTaskEdge(BaseModel):
    source: str
    target: str
    type: str
    reason: str


class LLMCandidateTaskGraph(BaseModel):
    """Flattened graph schema kept small enough for Gemini response_schema."""

    graph_type: str = "implementation_task_graph"
    runtime_pipeline_ref: str | None = None
    interaction_activation_contract: LLMInteractionActivationContract | None = None
    nodes: list[LLMTaskNode] = Field(default_factory=list)
    edges: list[LLMTaskEdge] = Field(default_factory=list)
    runtime_node_contracts: list[LLMRuntimeNodeContract] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class LLMRepairOperation(BaseModel):
    operation: str
    target: str
    reason: str
    suggested_change: str


class LLMRepairResult(BaseModel):
    repaired_task_graph: LLMCandidateTaskGraph
    repair_operations: list[LLMRepairOperation] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    requires_user_clarification: bool = False


class RepairSuggestion(BaseModel):
    target: str
    operation: RepairOperationType
    reason: str
    suggested_change: str


class CoverageReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    missing_goal_elements: list[str] = Field(default_factory=list)
    redundant_tasks: list[str] = Field(default_factory=list)
    hidden_assumptions: list[str] = Field(default_factory=list)
    repair_suggestions: list[RepairSuggestion] = Field(default_factory=list)


class GranularityReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    tasks_to_keep: list[str] = Field(default_factory=list)
    tasks_to_split: list[str] = Field(default_factory=list)
    tasks_to_merge: list[str] = Field(default_factory=list)
    tasks_to_remove: list[str] = Field(default_factory=list)
    repair_suggestions: list[RepairSuggestion] = Field(default_factory=list)


class DependencyReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    missing_edges: list[TaskEdge] = Field(default_factory=list)
    invalid_edges: list[TaskEdge] = Field(default_factory=list)
    cycles: list[list[str]] = Field(default_factory=list)
    parallelization_warnings: list[str] = Field(default_factory=list)


class ExecutorBinding(BaseModel):
    task_id: str
    executor: ExecutorSpec


class ExecutabilityReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    executable_tasks: list[str] = Field(default_factory=list)
    conditionally_executable_tasks: list[str] = Field(default_factory=list)
    blocked_tasks: list[str] = Field(default_factory=list)
    missing_runtime_inputs: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    suggested_executor_bindings: list[ExecutorBinding] = Field(default_factory=list)


class WeakPostcondition(BaseModel):
    task_id: str
    postcondition: str
    problem: str


class VerifierImprovement(BaseModel):
    task_id: str
    verifier: VerifierSpec


class VerifiabilityReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    weak_postconditions: list[WeakPostcondition] = Field(default_factory=list)
    missing_verifiers: list[str] = Field(default_factory=list)
    verifier_improvements: list[VerifierImprovement] = Field(default_factory=list)


class QualityReport(BaseModel):
    status: QualityStatus = "valid"
    graph_validity: GraphValidity = "complete"
    structural_status: StructuralStatus = "valid"
    runtime_status: RuntimeStatus = "ready_for_execution"
    must_apply_repairs_before_execution: bool = False
    must_provide_runtime_inputs_before_execution: bool = False
    coverage_score: float = Field(ge=0.0, le=1.0)
    granularity_score: float = Field(ge=0.0, le=1.0)
    dependency_score: float = Field(ge=0.0, le=1.0)
    executability_score: float = Field(ge=0.0, le=1.0)
    verifiability_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    critical_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    pending_repair_suggestions: list[str] = Field(default_factory=list)
    runtime_blockers: list[str] = Field(default_factory=list)


class RepairOperation(BaseModel):
    repair_id: str | None = None
    operation: RepairOperationType
    target: str
    reason: str
    input_warning_or_suggestion: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    added_task_ids: list[str] = Field(default_factory=list)
    modified_task_ids: list[str] = Field(default_factory=list)
    replacement_tasks: list[TaskNode] = Field(default_factory=list)
    added_tasks: list[TaskNode] = Field(default_factory=list)
    added_nodes: list[TaskNode] = Field(default_factory=list)
    removed_nodes: list[TaskNode] = Field(default_factory=list)
    modified_nodes: list[TaskNode] = Field(default_factory=list)
    removed_task_ids: list[str] = Field(default_factory=list)
    added_edges: list[TaskEdge] = Field(default_factory=list)
    removed_edges: list[TaskEdge] = Field(default_factory=list)
    strengthened_postconditions: list[Condition] = Field(default_factory=list)
    verifier: VerifierSpec | None = None
    executor: ExecutorSpec | None = None
    modified_fields: list[str] = Field(default_factory=list)
    validation_after_repair: Literal["passed", "failed", "unknown"] = "unknown"
    validation: dict[str, Any] = Field(default_factory=dict)


class RepairResult(BaseModel):
    repaired_task_graph: CandidateTaskGraph
    repair_operations: list[RepairOperation] = Field(default_factory=list)
    unresolved_assumptions: list[str] = Field(default_factory=list)
    requires_user_clarification: bool = False


class ExecutionPhase(BaseModel):
    phase_id: str
    mode: PhaseMode
    tasks: list[str]
    convergence_task: str | None = None


class ExecutionSchedule(BaseModel):
    phases: list[ExecutionPhase] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DecompositionTrace(BaseModel):
    original_goal: str
    interpreted_goal: GoalState
    initial_graph: CandidateTaskGraph
    evaluation_reports: list[QualityReport] = Field(default_factory=list)
    repairs_applied: list[RepairOperation] = Field(default_factory=list)
    final_graph: CandidateTaskGraph
    unresolved_assumptions: list[str] = Field(default_factory=list)
    quality_scores: QualityReport


class ValidatedTaskGraph(BaseModel):
    status: QualityStatus = "valid"
    graph_type: GraphType = "implementation_task_graph"
    runtime_pipeline_ref: str | None = None
    interaction_activation_contract: InteractionActivationContract | None = None
    goal_state: GoalState
    initial_macrostate: MacroState
    nodes: list[TaskNode]
    edges: list[TaskEdge]
    runtime_node_contracts: list[RuntimeNodeContract] = Field(default_factory=list)
    quality_report: QualityReport
    execution_schedule: ExecutionSchedule


class TaskSplitterOutput(BaseModel):
    task_graph: ValidatedTaskGraph
    human_readable_plan: str
    decomposition_trace: DecompositionTrace
    problem_definition: ProblemDefinition | None = None
