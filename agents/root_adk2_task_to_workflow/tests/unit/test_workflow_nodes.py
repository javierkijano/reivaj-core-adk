from google.genai.types import Content, Part

from app.task_splitter.schemas import (
    BranchResult,
    IntentDecision,
    InteractionActivationContract,
    QualityFindingReport,
    QualityReport,
    RegistryResource,
    RegistryReview,
    RuntimeNodeContract,
    WorkflowEdgeContract,
    WorkflowPlan,
)
from app.task_splitter.workflow_nodes import (
    _render_final_markdown,
    aggregate_quality,
    ambiguous_response,
    check_activation_policy,
    check_data_contracts,
    check_graph_contract,
    check_verification_strategy,
    content_to_text,
    greeting_response,
    intent_router,
    normalize_user_input,
    registry_review_node,
)


def _event_text(event) -> str:
    return " ".join(part.text for part in event.content.parts if getattr(part, "text", None))


def _valid_plan() -> WorkflowPlan:
    return WorkflowPlan(
        title="Reference ADK2 workflow",
        beta_opt_in_statement="ADK 2.0 beta is explicitly accepted for this implementation.",
        registry_resources_used=["internal-resources:reivaj-adk-2.0-development"],
        interaction_activation_contract=InteractionActivationContract(
            entrypoint_context="general_chat",
            activation_triggers=["implement", "design workflow"],
            non_activation_inputs=["Hola", "bono dias", "ADK"],
            llm_intent_check="Structured LLM intent classifier emits closed route values.",
            direct_response_policy=["Non-workflow routes use Event(message=...)."],
            hitl_policy=["RequestInput is exceptional and blocking only."],
            expensive_action_policy=["No planner/tools/providers before workflow_request."],
            required_interaction_tests=["Hola returns Event(message=...)", "bono dias returns greeting", "ADK asks clarification"],
        ),
        runtime_node_contracts=[
            RuntimeNodeContract(
                node_id="normalize_user_input",
                runtime_boundary_type="start",
                semantic_input="User text",
                adk_runtime_input="Content",
                recommended_function_signature="node_input: Any",
                normalization_required=["Content.parts -> text"],
                output_event_contract="Event(output=NormalizedRequest, state={...})",
                state_keys_written=["normalized_request"],
                required_tests=["Content input parses"],
            ),
            RuntimeNodeContract(
                node_id="structured_intent_classifier",
                runtime_boundary_type="normal",
                semantic_input="NormalizedRequest",
                adk_runtime_input="dict",
                recommended_function_signature="Agent(input_schema=NormalizedRequest, output_schema=IntentDecision)",
                output_event_contract="Event(output=IntentDecision)",
                route_values_emitted=[],
                required_tests=["schema import"],
            ),
            RuntimeNodeContract(
                node_id="intent_router",
                runtime_boundary_type="router",
                semantic_input="IntentDecision",
                adk_runtime_input="dict",
                recommended_function_signature="decision: IntentDecision",
                output_event_contract="Event(output=IntentDecision, route=decision.route)",
                route_values_emitted=["greeting", "workflow_request", "ambiguous"],
                required_tests=["route keys exact"],
            ),
            RuntimeNodeContract(
                node_id="quality_join",
                runtime_boundary_type="join",
                semantic_input="BranchResult values",
                adk_runtime_input="dict[str, Any]",
                recommended_function_signature="node_input: Any",
                normalization_required=["dict/list/tuple/model"],
                output_event_contract="Event(output=QualityReport)",
                required_tests=["join convergence"],
            ),
        ],
        edges=[
            WorkflowEdgeContract(from_node="START", to_node="normalize_user_input", reason="runtime boundary"),
            WorkflowEdgeContract(from_node="normalize_user_input", to_node="structured_intent_classifier", reason="natural-language classification"),
            WorkflowEdgeContract(from_node="structured_intent_classifier", to_node="intent_router", reason="deterministic route"),
            WorkflowEdgeContract(from_node="quality_checkers", to_node="quality_join", reason="JoinNode convergence"),
        ],
        data_contracts=[
            "Internal handoff uses Event(output=...).",
            "Small durable state uses Event(state=...).",
            "User visible responses use Event(message=...).",
        ],
        implementation_steps=["Create Workflow", "Add routes", "Add tests"],
        deterministic_tests=["import root_agent", "route keys", "Hola", "registry review", "join convergence"],
        hitl_policy="No RequestInput before intent classification; only exceptional blocking approvals.",
        final_markdown="Use Event(output=...), Event(state=...) and Event(message=...) with JoinNode convergence.",
    )


def test_start_normalization_accepts_content() -> None:
    event = normalize_user_input(Content(role="user", parts=[Part(text=" bono dias ")]))

    assert event.output["normalized_text"] == "bono dias"
    assert event.actions.state_delta["normalized_request"]["source"] == "content"


def test_content_to_text_handles_string_and_mapping() -> None:
    assert content_to_text(" hola ") == ("hola", "string")
    assert content_to_text({"text": "ADK"}) == ("ADK", "mapping")


def test_intent_router_uses_llm_decision_but_downgrades_low_confidence_workflow() -> None:
    decision = IntentDecision(
        route="workflow_request",
        confidence=0.2,
        normalized_request="ADK",
        reason="Bare topic",
        user_visible_response="",
        workflow_goal="Build something about ADK",
    )

    event = intent_router(decision.model_dump())

    assert event.actions.route == "ambiguous"
    assert event.output["workflow_goal"] == ""


def test_natural_route_responses_emit_messages_only() -> None:
    decision = IntentDecision(
        route="greeting",
        confidence=0.95,
        normalized_request="bono dias",
        reason="Typo greeting",
        user_visible_response="Buenos dias. Que quieres implementar?",
        workflow_goal="",
    )

    event = greeting_response(decision.model_dump())

    ambiguous = ambiguous_response(decision.model_copy(update={"route": "ambiguous"}).model_dump())

    assert "Buenos dias" in _event_text(event)
    assert event.output is None
    assert ambiguous.output is None


def test_workflow_request_reviews_registry_before_planning() -> None:
    decision = IntentDecision(
        route="workflow_request",
        confidence=0.95,
        normalized_request="implement ADK 2.0 Workflow with intent classifier and JoinNode",
        reason="Explicit implementation request",
        user_visible_response="",
        workflow_goal="Implement ADK 2.0 Workflow with intent classifier, registry review and JoinNode.",
    )

    event = registry_review_node(decision.model_dump())

    resource_ids = [resource["id"] for resource in event.output["resources"]]

    assert event.output["searched_catalogs"]
    assert "internal-resources:reivaj-adk-2.0-development" in resource_ids
    assert event.actions.state_delta["registry_review"]["query"].startswith("Implement ADK 2.0")


def test_quality_checks_pass_valid_plan() -> None:
    plan = _valid_plan().model_dump(mode="json")

    reports = [
        check_activation_policy(plan).output,
        check_graph_contract(plan).output,
        check_data_contracts(plan).output,
        check_verification_strategy(plan).output,
    ]

    assert all(QualityFindingReport.model_validate(report).passed for report in reports)


def test_quality_checks_emit_failure_branch_result_for_bad_input() -> None:
    report = QualityFindingReport.model_validate(check_graph_contract({"bad": "input"}).output)

    assert not report.passed
    assert report.branch_result.status == "failed"


def test_aggregate_quality_normalizes_join_dict() -> None:
    reports = {
        "a": QualityFindingReport(
            checker_id="a",
            passed=True,
            score=1.0,
            branch_result=BranchResult(branch_id="a", status="passed", output_summary="ok"),
        ).model_dump(mode="json"),
        "b": QualityFindingReport(
            checker_id="b",
            passed=False,
            score=0.5,
            findings=["missing route"],
            repair_suggestions=["add route"],
            branch_result=BranchResult(branch_id="b", status="failed", output_summary="missing route"),
        ).model_dump(mode="json"),
    }

    event = aggregate_quality(reports)
    quality = QualityReport.model_validate(event.output)

    assert quality.status == "needs_repair"
    assert quality.pending_repair_suggestions == ["add route"]


def test_final_markdown_is_deep_implementation_report() -> None:
    report = QualityFindingReport(
        checker_id="activation_policy",
        passed=True,
        score=1.0,
        branch_result=BranchResult(
            branch_id="activation_policy",
            status="passed",
            output_summary="ok",
        ),
    )
    quality = QualityReport(
        status="accepted",
        overall_score=1.0,
        reports=[report],
    )
    registry_review = RegistryReview(
        query="Implement ADK 2.0 workflow",
        resources=[
            RegistryResource(
                id="internal-resources:reivaj-adk-2.0-development",
                name="reivaj-adk-2.0-development",
                source="skills/reivaj-adk-2.0-development",
                summary="Internal ADK 2.0 Workflow development skill and reference pack.",
                tags=["entity:skill", "entity:workflow"],
                maturity="maturity:adapted",
                score=7.0,
            )
        ],
        reuse_guidance=["Read the internal ADK 2.0 skill before implementing."],
        searched_catalogs=["registry/internal/resources.yaml"],
    )

    markdown = _render_final_markdown(_valid_plan(), quality, registry_review)

    required_sections = [
        "# ADK 2.0 Workflow Deep Implementation Report",
        "## Executive Summary",
        "## Registry Review",
        "## Interaction Activation Contract",
        "## Runtime Node Contracts",
        "## Detailed Runtime Node Specifications",
        "## Workflow Graph Contract",
        "## Quality Branch Reports",
        "## JoinNode And Branch Output Guarantees",
        "## Failure Modes And Debugging Guidance",
        "## ADK 2.0 Implementation Checklist",
        "## Detailed Planner Markdown",
    ]

    for section in required_sections:
        assert section in markdown
    assert len(markdown) > 7000
