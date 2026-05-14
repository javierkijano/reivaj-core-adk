from typing import Literal

from pydantic import BaseModel, Field

IntentRoute = Literal[
    "greeting",
    "thanks",
    "small_talk",
    "simple_question",
    "ambiguous",
    "workflow_request",
]
ConfidenceLabel = Literal["low", "medium", "high"]
RuntimeBoundaryType = Literal["start", "normal", "router", "join", "hitl", "auth", "final"]
QualityStatus = Literal["accepted", "needs_repair", "blocked"]
BranchStatus = Literal["passed", "warning", "failed"]


class NormalizedRequest(BaseModel):
    original_text: str
    normalized_text: str
    source: Literal["content", "string", "mapping", "unknown"] = "unknown"


class IntentDecision(BaseModel):
    route: IntentRoute
    confidence: float = Field(ge=0.0, le=1.0)
    normalized_request: str
    reason: str
    user_visible_response: str = Field(
        description="Short natural message for non-workflow routes. Empty for workflow_request."
    )
    workflow_goal: str = Field(
        description="Implementation goal to pass to the planner. Empty unless route is workflow_request."
    )


class RegistryResource(BaseModel):
    id: str
    name: str
    source: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    maturity: str
    score: float = Field(ge=0.0, default=0.0)


class RegistryReview(BaseModel):
    query: str
    resources: list[RegistryResource] = Field(default_factory=list)
    reuse_guidance: list[str] = Field(default_factory=list)
    searched_catalogs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProblemDefinition(BaseModel):
    original_request: str
    implementation_goal: str
    success_criteria: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    registry_resources_to_reuse: list[str] = Field(default_factory=list)
    adk2_beta_acknowledged: bool


class InteractionActivationContract(BaseModel):
    entrypoint_context: Literal["general_chat", "dedicated_workflow", "tool_invoked", "subworkflow"]
    activation_triggers: list[str] = Field(default_factory=list)
    non_activation_inputs: list[str] = Field(default_factory=list)
    llm_intent_check: str
    direct_response_policy: list[str] = Field(default_factory=list)
    hitl_policy: list[str] = Field(default_factory=list)
    expensive_action_policy: list[str] = Field(default_factory=list)
    required_interaction_tests: list[str] = Field(default_factory=list)


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


class WorkflowEdgeContract(BaseModel):
    from_node: str
    to_node: str
    route: str | None = None
    reason: str


class WorkflowPlan(BaseModel):
    title: str
    beta_opt_in_statement: str
    registry_resources_used: list[str] = Field(default_factory=list)
    interaction_activation_contract: InteractionActivationContract
    runtime_node_contracts: list[RuntimeNodeContract] = Field(default_factory=list)
    edges: list[WorkflowEdgeContract] = Field(default_factory=list)
    data_contracts: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    deterministic_tests: list[str] = Field(default_factory=list)
    hitl_policy: str
    final_markdown: str


class BranchResult(BaseModel):
    branch_id: str
    status: BranchStatus
    output_summary: str
    errors: list[str] = Field(default_factory=list)


class QualityFindingReport(BaseModel):
    checker_id: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    findings: list[str] = Field(default_factory=list)
    repair_suggestions: list[str] = Field(default_factory=list)
    branch_result: BranchResult


class QualityReport(BaseModel):
    status: QualityStatus
    overall_score: float = Field(ge=0.0, le=1.0)
    reports: list[QualityFindingReport] = Field(default_factory=list)
    critical_failures: list[str] = Field(default_factory=list)
    pending_repair_suggestions: list[str] = Field(default_factory=list)
    repair_iterations: int = Field(ge=0, default=0)


class RepairRequest(BaseModel):
    plan: WorkflowPlan
    quality_report: QualityReport
    registry_review: RegistryReview
    instructions: list[str] = Field(default_factory=list)


class DirectAnswer(BaseModel):
    answer: str
