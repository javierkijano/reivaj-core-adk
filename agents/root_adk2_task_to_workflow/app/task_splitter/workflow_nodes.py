from typing import Any

from google.adk import Context, Event
from google.genai.types import Content
from pydantic import BaseModel

from app.task_splitter.registry_review import build_registry_review
from app.task_splitter.schemas import (
    BranchResult,
    DirectAnswer,
    IntentDecision,
    NormalizedRequest,
    QualityFindingReport,
    QualityReport,
    RegistryReview,
    RepairRequest,
    WorkflowPlan,
)

MIN_ACCEPTED_SCORE = 0.85
MAX_REPAIR_ITERATIONS = 1


def normalize_user_input(node_input: Any) -> Event:
    text, source = content_to_text(node_input)
    request = NormalizedRequest(
        original_text=text,
        normalized_text=" ".join(text.split()),
        source=source,
    )
    return Event(
        output=request.model_dump(mode="json"),
        state={"normalized_request": request.model_dump(mode="json")},
    )


def content_to_text(node_input: Any) -> tuple[str, str]:
    if isinstance(node_input, Content):
        parts = node_input.parts or []
        text = " ".join(
            part.text for part in parts if getattr(part, "text", None)
        ).strip()
        return text, "content"
    if isinstance(node_input, str):
        return node_input.strip(), "string"
    if isinstance(node_input, dict):
        if "text" in node_input:
            return str(node_input["text"]).strip(), "mapping"
        if "message" in node_input:
            return str(node_input["message"]).strip(), "mapping"
    return str(node_input or "").strip(), "unknown"


def intent_router(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    route = decision.route
    if route == "workflow_request" and decision.confidence < 0.72:
        route = "ambiguous"
        decision = decision.model_copy(
            update={
                "route": route,
                "user_visible_response": "Puedo hacerlo, pero necesito que confirmes que quieres un plan de implementacion y no solo una respuesta corta.",
                "workflow_goal": "",
            }
        )
    return Event(
        output=decision.model_dump(mode="json"),
        route=route,
        state={"intent_decision": decision.model_dump(mode="json")},
    )


def greeting_response(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    message = decision.user_visible_response or "Hola. Dime que workflow o agente quieres disenar."
    return Event(message=message)


def thanks_response(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    message = decision.user_visible_response or "De nada. Cuando quieras, dime que quieres implementar."
    return Event(message=message)


def small_talk_response(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    message = decision.user_visible_response or "Estoy listo para ayudarte con agentes y workflows ADK 2.0."
    return Event(message=message)


def ambiguous_response(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    message = decision.user_visible_response or (
        "Quieres que disene o implemente un workflow ADK 2.0, o solo necesitas una respuesta corta?"
    )
    return Event(message=message)


def direct_answer_message(node_input: Any) -> Event:
    answer = _model(DirectAnswer, node_input)
    return Event(message=answer.answer)


def registry_review_node(node_input: Any) -> Event:
    decision = _model(IntentDecision, node_input)
    query = decision.workflow_goal or decision.normalized_request
    review = build_registry_review(query)
    return Event(
        output=review.model_dump(mode="json"),
        state={"registry_review": review.model_dump(mode="json")},
    )


def store_initial_plan(node_input: Any) -> Event:
    plan = _model(WorkflowPlan, node_input)
    return Event(
        output=plan.model_dump(mode="json"),
        state={"workflow_plan": plan.model_dump(mode="json"), "repair_iterations": 0},
    )


def store_repaired_plan(ctx: Context, node_input: Any) -> Event:
    plan = _model(WorkflowPlan, node_input)
    repair_iterations = int(ctx.state.get("repair_iterations", 0))
    return Event(
        output=plan.model_dump(mode="json"),
        state={"workflow_plan": plan.model_dump(mode="json"), "repair_iterations": repair_iterations},
    )


def check_activation_policy(node_input: Any) -> Event:
    return _safe_check("activation_policy", node_input, _check_activation_policy)


def check_graph_contract(node_input: Any) -> Event:
    return _safe_check("graph_contract", node_input, _check_graph_contract)


def check_data_contracts(node_input: Any) -> Event:
    return _safe_check("data_contracts", node_input, _check_data_contracts)


def check_registry_usage(ctx: Context, node_input: Any) -> Event:
    try:
        plan = _model(WorkflowPlan, node_input)
        review = _optional_model(RegistryReview, ctx.state.get("registry_review"))
        findings: list[str] = []
        repairs: list[str] = []
        if not plan.registry_resources_used:
            findings.append("Plan does not list registry resources used.")
            repairs.append("Include registry_resources_used and describe how each resource informs the implementation.")
        if review and review.resources:
            known_ids = {resource.id for resource in review.resources}
            used_ids = set(plan.registry_resources_used)
            if not used_ids.intersection(known_ids):
                findings.append("Plan does not reuse any top registry match.")
                repairs.append("Reference at least one relevant resource returned by registry_review.")
        passed = not repairs
        return _report_event("registry_usage", passed, 1.0 if passed else 0.55, findings, repairs)
    except Exception as exc:
        return _failed_report_event("registry_usage", exc)


def check_verification_strategy(node_input: Any) -> Event:
    return _safe_check("verification_strategy", node_input, _check_verification_strategy)


def aggregate_quality(node_input: Any) -> Event:
    reports = _quality_reports_from_join(node_input)
    if not reports:
        reports = [
            _failed_report(
                "join_normalization",
                ValueError("JoinNode produced no recognizable QualityFindingReport outputs"),
            )
        ]
    overall_score = round(sum(report.score for report in reports) / len(reports), 4)
    critical_failures = [
        finding
        for report in reports
        if not report.passed
        for finding in report.findings
    ]
    pending_repairs = [
        suggestion
        for report in reports
        for suggestion in report.repair_suggestions
    ]
    status = "accepted"
    if critical_failures or overall_score < MIN_ACCEPTED_SCORE:
        status = "needs_repair"
    quality_report = QualityReport(
        status=status,
        overall_score=overall_score,
        reports=reports,
        critical_failures=critical_failures,
        pending_repair_suggestions=pending_repairs,
    )
    return Event(
        output=quality_report.model_dump(mode="json"),
        state={"quality_report": quality_report.model_dump(mode="json")},
    )


def repair_router(ctx: Context, node_input: Any) -> Event:
    quality_report = _model(QualityReport, node_input)
    repair_iterations = int(ctx.state.get("repair_iterations", 0))
    if quality_report.status == "needs_repair" and repair_iterations < MAX_REPAIR_ITERATIONS:
        route = "repair"
    else:
        route = "finalize"
    routed_report = quality_report.model_copy(update={"repair_iterations": repair_iterations})
    return Event(
        output=routed_report.model_dump(mode="json"),
        route=route,
        state={"quality_report": routed_report.model_dump(mode="json"), "repair_route": route},
    )


def build_repair_request(ctx: Context, node_input: Any) -> Event:
    quality_report = _model(QualityReport, node_input)
    plan = _model(WorkflowPlan, ctx.state.get("workflow_plan"))
    registry_review = _model(RegistryReview, ctx.state.get("registry_review"))
    repair_iterations = int(ctx.state.get("repair_iterations", 0)) + 1
    request = RepairRequest(
        plan=plan,
        quality_report=quality_report,
        registry_review=registry_review,
        instructions=quality_report.pending_repair_suggestions,
    )
    return Event(
        output=request.model_dump(mode="json"),
        state={"repair_request": request.model_dump(mode="json"), "repair_iterations": repair_iterations},
    )


def final_emitter(ctx: Context, node_input: Any) -> Event:
    quality_report = _model(QualityReport, node_input)
    plan = _model(WorkflowPlan, ctx.state.get("workflow_plan"))
    registry_review = _optional_model(RegistryReview, ctx.state.get("registry_review"))
    markdown = _render_final_markdown(plan, quality_report, registry_review)
    return Event(
        message=markdown,
        state={
            "final_plan_markdown": markdown,
            "deep_implementation_report_markdown": markdown,
        },
    )


def _check_activation_policy(plan: WorkflowPlan) -> tuple[bool, float, list[str], list[str]]:
    findings: list[str] = []
    repairs: list[str] = []
    contract = plan.interaction_activation_contract
    if contract.entrypoint_context != "general_chat":
        findings.append("Interaction contract is not marked as general_chat.")
        repairs.append("Set entrypoint_context=general_chat for a root chat/playground agent.")
    intent_text = " ".join([contract.llm_intent_check, *contract.required_interaction_tests]).lower()
    if "llm" not in intent_text or "intent" not in intent_text:
        findings.append("Activation contract does not clearly require structured LLM intent classification.")
        repairs.append("Add structured LLM intent classifier before planner/tools/HITL.")
    if not any("hola" in test.lower() or "bono dias" in test.lower() for test in contract.required_interaction_tests):
        findings.append("No natural greeting/typo test is listed.")
        repairs.append("Add tests for Hola and typo-rich greetings such as bono dias.")
    if "requestinput" in " ".join(contract.hitl_policy).lower() and not any(
        "exception" in item.lower() or "blocking" in item.lower() for item in contract.hitl_policy
    ):
        findings.append("HITL policy may be too broad for conversational entry.")
        repairs.append("Limit RequestInput to exceptional blocking approvals/auth/reviewer mode.")
    return not repairs, 1.0 if not repairs else 0.6, findings, repairs


def _check_graph_contract(plan: WorkflowPlan) -> tuple[bool, float, list[str], list[str]]:
    findings: list[str] = []
    repairs: list[str] = []
    edge_text = " ".join(f"{edge.from_node}->{edge.to_node}:{edge.route or ''}" for edge in plan.edges).lower()
    node_ids = {node.node_id for node in plan.runtime_node_contracts}
    if not any(edge.from_node.upper() == "START" for edge in plan.edges):
        findings.append("Graph contract has no START edge.")
        repairs.append("Declare a START edge to normalize_user_input.")
    for required in {"normalize_user_input", "structured_intent_classifier", "intent_router"}:
        if required not in node_ids and required not in edge_text:
            findings.append(f"Graph contract does not include {required}.")
            repairs.append(f"Add {required} to the explicit Workflow graph.")
    if "join" not in edge_text and not any(node.runtime_boundary_type == "join" for node in plan.runtime_node_contracts):
        findings.append("Plan does not show JoinNode convergence for fixed quality checks.")
        repairs.append("Use static fan-out/fan-in with JoinNode for quality checks.")
    return not repairs, 1.0 if not repairs else 0.65, findings, repairs


def _check_data_contracts(plan: WorkflowPlan) -> tuple[bool, float, list[str], list[str]]:
    findings: list[str] = []
    repairs: list[str] = []
    data_text = " ".join([*plan.data_contracts, plan.final_markdown]).lower()
    if "event(output" not in data_text:
        findings.append("Plan does not explicitly use Event(output=...) for internal handoff.")
        repairs.append("Document Event(output=...) for internal node-to-node data.")
    if "event(state" not in data_text:
        findings.append("Plan does not explicitly use Event(state=...) for durable small state.")
        repairs.append("Document Event(state=...) for small workflow/session state.")
    if "event(message" not in data_text:
        findings.append("Plan does not reserve Event(message=...) for user-visible responses.")
        repairs.append("Document Event(message=...) only for user-facing output.")
    if not all(node.output_event_contract for node in plan.runtime_node_contracts):
        findings.append("At least one runtime node lacks an output event contract.")
        repairs.append("Fill output_event_contract for every runtime node.")
    return not repairs, 1.0 if not repairs else 0.7, findings, repairs


def _check_verification_strategy(plan: WorkflowPlan) -> tuple[bool, float, list[str], list[str]]:
    findings: list[str] = []
    repairs: list[str] = []
    tests_text = " ".join(plan.deterministic_tests).lower()
    required_markers = ["import", "route", "hola", "registry", "join"]
    for marker in required_markers:
        if marker not in tests_text:
            findings.append(f"Missing deterministic test marker: {marker}.")
            repairs.append(f"Add deterministic tests covering {marker}.")
    if "llm output" in tests_text or "response contains" in tests_text:
        findings.append("Tests appear to assert non-deterministic LLM content.")
        repairs.append("Move LLM behavior assertions to evals; keep pytest deterministic.")
    return not repairs, 1.0 if not repairs else 0.72, findings, repairs


def _safe_check(checker_id: str, node_input: Any, check_fn: Any) -> Event:
    try:
        plan = _model(WorkflowPlan, node_input)
        passed, score, findings, repairs = check_fn(plan)
        return _report_event(checker_id, passed, score, findings, repairs)
    except Exception as exc:
        return _failed_report_event(checker_id, exc)


def _report_event(
    checker_id: str,
    passed: bool,
    score: float,
    findings: list[str],
    repairs: list[str],
) -> Event:
    status = "passed" if passed else "failed"
    if not passed and score >= 0.7:
        status = "warning"
    report = QualityFindingReport(
        checker_id=checker_id,
        passed=passed,
        score=round(score, 4),
        findings=findings,
        repair_suggestions=repairs,
        branch_result=BranchResult(
            branch_id=checker_id,
            status=status,
            output_summary="passed" if passed else "; ".join(findings[:3]),
            errors=[] if passed else findings,
        ),
    )
    return Event(output=report.model_dump(mode="json"))


def _failed_report_event(checker_id: str, exc: Exception) -> Event:
    return Event(output=_failed_report(checker_id, exc).model_dump(mode="json"))


def _failed_report(checker_id: str, exc: Exception) -> QualityFindingReport:
    message = f"{type(exc).__name__}: {exc}"
    return QualityFindingReport(
        checker_id=checker_id,
        passed=False,
        score=0.0,
        findings=[message],
        repair_suggestions=[f"Fix checker input contract for {checker_id}."],
        branch_result=BranchResult(
            branch_id=checker_id,
            status="failed",
            output_summary=message,
            errors=[message],
        ),
    )


def _quality_reports_from_join(node_input: Any) -> list[QualityFindingReport]:
    values: list[Any]
    if isinstance(node_input, dict):
        if "checker_id" in node_input:
            values = [node_input]
        else:
            values = list(node_input.values())
    elif isinstance(node_input, list | tuple):
        values = list(node_input)
    else:
        values = [node_input]

    reports: list[QualityFindingReport] = []
    for value in values:
        if isinstance(value, QualityFindingReport):
            reports.append(value)
            continue
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        if isinstance(value, dict) and "output" in value:
            value = value["output"]
        try:
            reports.append(QualityFindingReport.model_validate(value))
        except Exception:
            continue
    return reports


def _render_final_markdown(
    plan: WorkflowPlan,
    quality_report: QualityReport,
    registry_review: RegistryReview | None,
) -> str:
    registry_resources = registry_review.resources if registry_review else []
    lines = [
        "# ADK 2.0 Workflow Deep Implementation Report",
        "",
        f"## Goal: {plan.title}",
        "",
        plan.beta_opt_in_statement,
        "",
        "## Executive Summary",
        "",
        "This report is intentionally verbose. It is designed to be handed to a coding agent as an implementation contract, not read as a short product summary.",
        "",
        "- Target runtime: ADK 2.0 graph-based `Workflow`.",
        "- Root shape: `START -> normalize_user_input -> structured_intent_classifier -> intent_router`.",
        "- Conversational non-activation paths terminate with `Event(message=...)`.",
        "- Implementation work must pass through registry review before planning new code.",
        "- Internal node handoff uses `Event(output=...)`; small durable state uses `Event(state=...)`.",
        "- Static quality branches converge through `JoinNode` and emit a branch result even on failure.",
        "- Repair is a bounded route loop, not `LoopAgent` or an unbounded LLM retry pattern.",
        "",
        "## Planning Philosophy",
        "",
        "- Use ADK 2.0 Workflow as the primary orchestration surface for this implementation.",
        "- Keep the graph readable from `edges=[...]`; avoid hiding control flow in a custom `BaseAgent` runner.",
        "- Treat LLM agents as task/single-turn nodes with structured schemas.",
        "- Use deterministic function nodes for routing, normalization, registry review, aggregation, repair decisions and final rendering.",
        "- Prefer graph routes, static fan-out/fan-in and `JoinNode` before dynamic workflows.",
        "- Reserve dynamic workflows or collaborative agents for explicit opt-in decisions with documented alternatives.",
        "- Do not require Live Streaming for graph-based workflows.",
        "",
        "## Quality",
        "",
        f"- Status: `{quality_report.status}`",
        f"- Score: `{quality_report.overall_score:.2f}`",
        f"- Repair iterations: `{quality_report.repair_iterations}`",
        f"- Critical failure count: `{len(quality_report.critical_failures)}`",
        f"- Pending repair suggestion count: `{len(quality_report.pending_repair_suggestions)}`",
        "",
        "## Registry Review",
        "",
    ]
    if registry_review:
        lines.extend(
            [
                f"- Query: `{registry_review.query}`",
                f"- Catalogs searched: `{len(registry_review.searched_catalogs)}`",
                f"- Resources surfaced: `{len(registry_resources)}`",
                "",
            ]
        )
        if registry_review.reuse_guidance:
            lines.extend(["### Registry Reuse Guidance", ""])
            lines.extend(_markdown_list(registry_review.reuse_guidance))
            lines.append("")
        if registry_review.searched_catalogs:
            lines.extend(["### Catalogs Searched", ""])
            lines.extend(_markdown_list(registry_review.searched_catalogs))
            lines.append("")
        if registry_review.warnings:
            lines.extend(["### Registry Warnings", ""])
            lines.extend(_markdown_list(registry_review.warnings))
            lines.append("")
    if registry_resources:
        lines.extend(
            [
                "### Candidate Resources",
                "",
                "| Resource | Maturity | Score | Tags | Source | Reuse Value |",
                "|---|---|---:|---|---|---|",
            ]
        )
        lines.extend(
            "| "
            + " | ".join(
                [
                    _table_cell(f"`{resource.id}`"),
                    _table_cell(resource.maturity),
                    f"{resource.score:.1f}",
                    _table_cell(_inline_list(resource.tags)),
                    _table_cell(resource.source),
                    _table_cell(resource.summary),
                ]
            )
            + " |"
            for resource in registry_resources
        )
    else:
        lines.append("- No registry resources were available or strongly matched.")

    lines.extend(
        [
            "",
            "## Registry Resources Selected By Planner",
            "",
            *_markdown_list(plan.registry_resources_used),
            "",
            "## Interaction Activation Contract",
            "",
            "This section defines the user-facing activation boundary. It is intentionally before planner, tools, providers and HITL.",
            "",
            f"- Entrypoint context: `{plan.interaction_activation_contract.entrypoint_context}`",
            f"- LLM intent check: {plan.interaction_activation_contract.llm_intent_check}",
            "",
            "### Activation Triggers",
            "",
            *_markdown_list(plan.interaction_activation_contract.activation_triggers),
            "",
            "### Non-Activation Inputs",
            "",
            *_markdown_list(plan.interaction_activation_contract.non_activation_inputs),
            "",
            "### Direct Response Policy",
            "",
            *_markdown_list(plan.interaction_activation_contract.direct_response_policy),
            "",
            "### HITL Policy",
            "",
            *_markdown_list(plan.interaction_activation_contract.hitl_policy),
            "",
            "### Expensive Action Policy",
            "",
            *_markdown_list(plan.interaction_activation_contract.expensive_action_policy),
            "",
            "### Required Interaction Tests",
            "",
            *_markdown_list(plan.interaction_activation_contract.required_interaction_tests),
            "",
            "## Runtime Node Contracts",
            "",
            "These contracts describe real ADK 2.0 runner boundaries. They explicitly separate semantic input from ADK runtime input so `Content`, post-`JoinNode` payloads and resume data do not break Pydantic binding before normalization.",
            "",
            "| Node ID | Boundary | Semantic Input | ADK Runtime Input | Function Signature | Normalization | Output Event | State Keys | Routes | Required Tests |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(
        "| "
        + " | ".join(
            [
                _table_cell(contract.node_id),
                _table_cell(contract.runtime_boundary_type),
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
        for contract in plan.runtime_node_contracts
    )
    if not plan.runtime_node_contracts:
        lines.append("| missing | missing | missing | missing | missing | missing | missing | missing | missing | missing |")

    lines.extend(
        [
            "",
            "## Detailed Runtime Node Specifications",
            "",
        ]
    )
    for contract in plan.runtime_node_contracts:
        lines.extend(
            [
                f"### `{contract.node_id}`",
                "",
                f"- Boundary type: `{contract.runtime_boundary_type}`",
                f"- Semantic input: {contract.semantic_input}",
                f"- ADK runtime input: {contract.adk_runtime_input}",
                f"- Recommended function signature: `{contract.recommended_function_signature}`",
                f"- Output event contract: `{contract.output_event_contract}`",
                f"- State keys written: {_inline_list(contract.state_keys_written)}",
                f"- Route values emitted: {_inline_list(contract.route_values_emitted)}",
                "",
                "Normalization required:",
                *_markdown_list(contract.normalization_required),
                "",
                "Required tests:",
                *_markdown_list(contract.required_tests),
                "",
            ]
        )

    lines.extend(
        [
            "## Workflow Graph Contract",
            "",
            "| From | To | Route | Reason |",
            "|---|---|---|---|",
        ]
    )
    lines.extend(
        f"| {_table_cell(edge.from_node)} | {_table_cell(edge.to_node)} | {_table_cell(edge.route or 'unconditional')} | {_table_cell(edge.reason)} |"
        for edge in plan.edges
    )
    if not plan.edges:
        lines.append("| missing | missing | missing | missing |")

    lines.extend(
        [
            "",
            "## Route Map And Activation Boundary",
            "",
            "- `greeting`, `thanks`, `small_talk`, `simple_question` and `ambiguous` are conversation routes and must not activate planners, tools, providers or HITL.",
            "- `workflow_request` is the only route that reaches `registry_review_node` and then planning.",
            "- Low-confidence `workflow_request` decisions must downgrade to `ambiguous` before planning.",
            "- The route dictionary keys must match `Event(route=...)` values exactly.",
            "",
            "## Data Contracts",
            "",
            *_markdown_list(plan.data_contracts),
            "",
            "## Implementation Steps",
            "",
        ]
    )
    lines.extend(f"{index}. {step}" for index, step in enumerate(plan.implementation_steps, 1))
    if not plan.implementation_steps:
        lines.append("1. Define concrete implementation steps before coding.")

    lines.extend(
        [
            "",
            "## Quality Branch Reports",
            "",
            "| Checker | Passed | Score | Findings | Repair Suggestions | Branch Status |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    lines.extend(
        "| "
        + " | ".join(
            [
                _table_cell(report.checker_id),
                str(report.passed),
                f"{report.score:.2f}",
                _table_cell(_inline_list(report.findings)),
                _table_cell(_inline_list(report.repair_suggestions)),
                _table_cell(report.branch_result.status),
            ]
        )
        + " |"
        for report in quality_report.reports
    )
    if not quality_report.reports:
        lines.append("| none | false | 0.00 | no reports | add quality reports | missing |")

    lines.extend(
        [
            "",
            "## JoinNode And Branch Output Guarantees",
            "",
            "- Every branch flowing into `quality_join` must emit a `QualityFindingReport`.",
            "- Failure paths emit structured `BranchResult(status='failed')` instead of dropping output.",
            "- The post-join aggregator accepts `Any` and normalizes dict, list, tuple, Event output payloads and Pydantic models.",
            "- A join with no recognizable branch output is converted into a synthetic failed report rather than silently accepting an empty quality set.",
            "",
            "## Repair Loop And Stop Criteria",
            "",
            f"- Minimum accepted score: `{MIN_ACCEPTED_SCORE:.2f}`",
            f"- Maximum repair iterations: `{MAX_REPAIR_ITERATIONS}`",
            "- Route `repair` only when quality status is `needs_repair` and the iteration cap has not been reached.",
            "- Route `finalize` when the plan is accepted or the deterministic repair cap is reached.",
            "- Repair requests carry the current plan, quality report, registry review and concrete repair suggestions.",
            "",
            "## HITL, Auth And Resume Policy",
            "",
            plan.hitl_policy,
            "",
            "- `RequestInput` is not used as a natural conversation entrypoint.",
            "- If a future HITL node is added, it must appear after intent classification and minimum slot validation.",
            "- Any future HITL node must use stable `interrupt_id`, `rerun_on_resume=True` when needed and normalize `ctx.resume_inputs[interrupt_id]` before emitting routes.",
            "- Auth nodes must never print tokens and must mask secrets in user-visible messages.",
            "",
            "## Verification Strategy",
            "",
            *_markdown_list(plan.deterministic_tests),
            "",
            "## Failure Modes And Debugging Guidance",
            "",
            "- If ADK Web cannot load the graph, verify the top-level `agent.py` exports only `root_agent` for `adk web <agents_dir>`.",
            "- If the first node fails before code runs, check that the START-connected function accepts `Any` or `Content` and normalizes internally.",
            "- If a conversational input triggers planning, inspect the `IntentDecision.route` and confidence downgrade logic.",
            "- If a join stalls, confirm every upstream quality checker always emits `Event(output=QualityFindingReport)` even on exceptions.",
            "- If repair loops repeat, inspect `repair_iterations`, `MAX_REPAIR_ITERATIONS` and route values emitted by `repair_router`.",
            "- If registry guidance is missing, inspect `registry_review_node` path discovery and YAML parsing warnings.",
            "",
            "## ADK 2.0 Implementation Checklist",
            "",
            "- Confirm dependency `google-adk>=2.0.0b1` and ADK 2.0 beta opt-in.",
            "- Export `root_agent = Workflow(...)` from `app/agent.py`.",
            "- Export only `root_agent` from top-level `agent.py` for `adk web <agents_dir>` compatibility.",
            "- Ensure the first START-connected node accepts `Any` or `Content`.",
            "- Normalize `Content.parts` before validating Pydantic schemas.",
            "- Keep structured LLM intent classification before planners, tools, providers or HITL.",
            "- Route non-workflow conversation directly to `Event(message=...)`.",
            "- Review the registry before creating new implementation functionality.",
            "- Use `Event(output=...)` for internal handoff and `Event(state=...)` for small durable state.",
            "- Use `JoinNode` for static branch convergence and test failed branch output.",
            "- Keep repair loops bounded and route-driven.",
            "- Do not run evals, playground, deploy, publish or infra without explicit approval.",
            "",
            "## Definition Of Done",
            "",
            "- Import tests prove `root_agent` is a `Workflow`.",
            "- Route tests cover all natural routes and `workflow_request`.",
            "- Natural-entry tests cover greeting typos, thanks, bare topics and low-confidence workflow decisions.",
            "- Registry tests prove implementation requests search reusable resources before planning.",
            "- Join tests prove post-join normalization handles dict-shaped branch outputs.",
            "- Report tests prove the final output is a deep implementation report, not a short summary.",
            "- LLM behavior quality is evaluated with evals, not pytest assertions on generated prose.",
            "",
            "## Detailed Planner Markdown",
            "",
            plan.final_markdown,
        ]
    )
    if quality_report.pending_repair_suggestions:
        lines.extend(["", "## Residual Repair Suggestions", ""])
        lines.extend(f"- {suggestion}" for suggestion in quality_report.pending_repair_suggestions)
    if quality_report.critical_failures:
        lines.extend(["", "## Critical Failures", ""])
        lines.extend(f"- {failure}" for failure in quality_report.critical_failures)
    return "\n".join(lines)


def _inline_list(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def _markdown_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- none"]


def _table_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _model(model_cls: type[BaseModel], value: Any):
    if isinstance(value, model_cls):
        return value
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return model_cls.model_validate(value)


def _optional_model(model_cls: type[BaseModel], value: Any):
    if value is None:
        return None
    return _model(model_cls, value)
