"""Deterministic FunctionNodes for the deep web research workflow."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from google.adk import Context, Event
from google.adk.events import RequestInput
from google.adk.workflow import node
from google.genai.types import Content

from .config import config
from .schemas import (
    ApprovalDecision,
    BranchResult,
    IntentDecision,
    LimitCheckResult,
    NormalizedInput,
    ProviderSearchResult,
    QualityAssessment,
    ResearchFindings,
    ResearchPlan,
    ResearchRequest,
    SearchBatch,
    SourceCitation,
)

APPROVAL_INTERRUPT_ID = "deep_web_research_plan_approval"

_ACTIVATION_TRIGGERS = [
    "investiga",
    "investigar",
    "busca fuentes",
    "buscar fuentes",
    "haz research",
    "research",
    "compara",
    "analiza en profundidad",
    "consulta la web",
    "prepara un informe",
    "deep search",
    "web research",
]
_GREETINGS = {"hola", "buenas", "hey", "hello", "hi", "holaa"}
_THANKS = {"gracias", "thanks", "thank you", "muchas gracias"}
_SMALL_TALK = {
    "como estas",
    "que tal",
    "que tal?",
    "how are you",
    "buenos dias",
    "buenas tardes",
}
_SIMPLE_QUESTIONS = {
    "que puedes hacer",
    "que puedes hacer?",
    "help",
    "ayuda",
    "quien eres",
    "quien eres?",
}
_STANDALONE_CONFIRMATIONS = {"si", "sí", "ok", "dale", "yes", "no", "vale"}
_URL_RE = re.compile(r"https?://[^\s)\]>}]+")


def _state(ctx: Context) -> dict[str, Any]:
    return getattr(ctx, "state", {})


def _resume_inputs(ctx: Context) -> dict[str, Any]:
    return getattr(ctx, "resume_inputs", {})


def _fold(text: str) -> str:
    lowered = text.strip().lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _compact(text: str) -> str:
    return " ".join(text.split())


def content_to_text(node_input: Any) -> str:
    """Normalize ADK runtime input into text before schema validation."""

    if isinstance(node_input, NormalizedInput):
        return node_input.normalized_text
    if isinstance(node_input, Content):
        return _compact(
            " ".join(
                part.text
                for part in (node_input.parts or [])
                if getattr(part, "text", None)
            )
        )
    if isinstance(node_input, Event):
        if node_input.output is not None:
            return content_to_text(node_input.output)
        if node_input.content and node_input.content.parts:
            return content_to_text(node_input.content)
        return ""
    if isinstance(node_input, dict):
        for key in ("normalized_text", "original_text", "text", "topic", "summary"):
            value = node_input.get(key)
            if isinstance(value, str):
                return _compact(value)
        return _compact(json.dumps(node_input, ensure_ascii=True))
    if node_input is None:
        return ""
    return _compact(str(node_input))


def normalize_user_input(ctx: Context, node_input: Any) -> Event:
    """START boundary: accept Content or Any and emit NormalizedInput."""

    text = content_to_text(node_input)
    if isinstance(node_input, Content):
        source = "content"
    elif isinstance(node_input, Event):
        source = "event"
    elif isinstance(node_input, dict):
        source = "mapping"
    elif isinstance(node_input, str):
        source = "string"
    else:
        source = "unknown"

    normalized = NormalizedInput(
        original_text=text,
        normalized_text=text,
        source=source,
    )
    return Event(
        output=normalized,
        state={"last_user_input": text, "last_input_source": source},
    )


def _topic_after_trigger(text: str) -> str:
    folded = _fold(text)
    for trigger in sorted(_ACTIVATION_TRIGGERS, key=len, reverse=True):
        trigger_folded = _fold(trigger)
        if folded.startswith(trigger_folded):
            return text[len(trigger) :].strip(" :-.,;\n\t")
    return text.strip()


def _has_activation_trigger(text: str) -> bool:
    folded = _fold(text)
    return any(_fold(trigger) in folded for trigger in _ACTIVATION_TRIGGERS)


def _has_research_memory(ctx: Context) -> bool:
    state = _state(ctx)
    return bool(state.get("last_research_report") or state.get("research_findings"))


def _is_follow_up_question(text: str) -> bool:
    folded = _fold(text)
    follow_up_markers = [
        "y sobre",
        "que dice",
        "que hay de",
        "puedes ampliar",
        "explica mas",
        "resumen",
    ]
    return text.endswith("?") or any(marker in folded for marker in follow_up_markers)


def intent_gate(node_input: NormalizedInput, ctx: Context) -> Event:
    """Route normalized user text before any planner, HITL or tool runs."""

    text = node_input.normalized_text
    folded = _fold(text)
    words = [word for word in folded.split() if word]

    if not text:
        decision = IntentDecision(
            label="ambiguous",
            text=text,
            confidence="high",
            reason="Empty input",
        )
    elif folded in _GREETINGS:
        decision = IntentDecision(
            label="greeting",
            text=text,
            confidence="high",
            reason="Greeting",
        )
    elif folded in _THANKS:
        decision = IntentDecision(
            label="thanks",
            text=text,
            confidence="high",
            reason="Thanks",
        )
    elif folded in _SMALL_TALK:
        decision = IntentDecision(
            label="small_talk",
            text=text,
            confidence="high",
            reason="Small talk",
        )
    elif folded in _SIMPLE_QUESTIONS:
        decision = IntentDecision(
            label="simple_question",
            text=text,
            confidence="high",
            reason="Simple capability question",
        )
    elif folded in {_fold(value) for value in _STANDALONE_CONFIRMATIONS}:
        decision = IntentDecision(
            label="ambiguous",
            text=text,
            confidence="high",
            reason="Standalone confirmation without active HITL context",
        )
    elif _has_activation_trigger(text):
        topic = _topic_after_trigger(text)
        if len(topic) < 3:
            decision = IntentDecision(
                label="ambiguous",
                text=text,
                confidence="high",
                reason="Research trigger without a usable topic",
            )
        else:
            decision = IntentDecision(
                label="new_research",
                text=text,
                confidence="high",
                reason="Explicit research/search trigger",
            )
    elif _has_research_memory(ctx) and _is_follow_up_question(text):
        decision = IntentDecision(
            label="direct_qa",
            text=text,
            confidence="medium",
            reason="Follow-up question can use previous research memory",
        )
    elif len(words) <= 2:
        decision = IntentDecision(
            label="ambiguous",
            text=text,
            confidence="medium",
            reason="Bare topic without explicit research intent",
        )
    else:
        decision = IntentDecision(
            label="ambiguous",
            text=text,
            confidence="medium",
            reason="No explicit web research trigger",
        )

    return Event(output=decision, route=decision.label)


def greeting_response(node_input: IntentDecision) -> Event:
    return Event(message="Hola. Dime que tema quieres investigar en la web.")


def thanks_response(node_input: IntentDecision) -> Event:
    return Event(message="De nada. Si quieres una busqueda profunda, dime el tema.")


def smalltalk_response(node_input: IntentDecision) -> Event:
    return Event(
        message="Estoy listo para ayudarte. Pideme una investigacion web concreta."
    )


def direct_answer_response(node_input: IntentDecision) -> Event:
    return Event(
        message=(
            "Puedo hacer busqueda profunda en web con aprobacion previa del plan. "
            "Ejemplo: 'Investiga ADK 2.0 Workflow con fuentes'."
        )
    )


def clarification_response(node_input: IntentDecision) -> Event:
    return Event(
        message=(
            "Necesito una solicitud de investigacion mas clara. Por ejemplo: "
            "'Investiga ADK 2.0 Workflow con fuentes'."
        )
    )


def memory_answer_response(node_input: IntentDecision, ctx: Context) -> Event:
    state = _state(ctx)
    report = str(state.get("last_research_report") or "").strip()
    topic = str(state.get("last_research_topic") or "la investigacion anterior")
    if not report:
        return clarification_response(node_input)
    excerpt = report[:800].strip()
    return Event(
        message=(
            f"Sobre {topic}, puedo usar el informe anterior. Extracto:\n\n"
            f"{excerpt}\n\n"
            "Si quieres informacion nueva, pideme explicitamente otra busqueda."
        )
    )


def build_research_request(node_input: IntentDecision, ctx: Context) -> Event:
    topic = _topic_after_trigger(node_input.text)
    request = ResearchRequest(topic=topic, original_text=node_input.text)
    return Event(
        output=request,
        state={"current_request": request.model_dump(), "plan_feedback": ""},
    )


def _request_from_state(ctx: Context) -> ResearchRequest:
    raw = _state(ctx).get("current_request") or {}
    if isinstance(raw, ResearchRequest):
        return raw
    if isinstance(raw, dict) and raw.get("topic"):
        return ResearchRequest.model_validate(raw)
    fallback = str(_state(ctx).get("last_user_input") or "web research").strip()
    return ResearchRequest(topic=fallback, original_text=fallback)


def _plan_from_any(value: Any, ctx: Context) -> ResearchPlan:
    if isinstance(value, ResearchPlan):
        return value
    if isinstance(value, Event) and value.output is not None:
        return _plan_from_any(value.output, ctx)
    if isinstance(value, dict):
        return ResearchPlan.model_validate(value)
    if isinstance(value, str):
        try:
            return ResearchPlan.model_validate(json.loads(value))
        except (json.JSONDecodeError, ValueError, TypeError):
            request = _request_from_state(ctx)
            return ResearchPlan(
                topic=request.topic,
                rationale="Fallback plan generated from planner text output.",
                search_queries=[request.topic],
                max_iterations=config.max_iterations,
                max_budget_units=config.max_budget_units,
                human_summary=value[:500] or f"Research {request.topic}",
            )
    raw_state_plan = _state(ctx).get("current_plan") or {}
    if isinstance(raw_state_plan, dict) and raw_state_plan.get("topic"):
        return ResearchPlan.model_validate(raw_state_plan)
    request = _request_from_state(ctx)
    return ResearchPlan(
        topic=request.topic,
        rationale="Default plan for the requested research topic.",
        search_queries=[request.topic],
        max_iterations=config.max_iterations,
        max_budget_units=config.max_budget_units,
        human_summary=f"Research {request.topic} with Google Search.",
    )


def initialize_plan_state(node_input: Any, ctx: Context) -> Event:
    plan = _plan_from_any(node_input, ctx)
    clamped_plan = plan.model_copy(
        update={
            "max_iterations": min(plan.max_iterations, config.max_iterations),
            "max_budget_units": min(plan.max_budget_units, config.max_budget_units),
            "selected_providers": ["google_search"],
        }
    )
    return Event(
        output=clamped_plan,
        state={
            "current_plan": clamped_plan.model_dump(),
            "current_iteration": 0,
            "budget_used": 0,
            "max_iterations": clamped_plan.max_iterations,
            "max_budget_units": clamped_plan.max_budget_units,
            "research_findings": [],
        },
    )


def _format_plan_message(plan: ResearchPlan) -> str:
    queries = "\n".join(f"- {query}" for query in plan.search_queries)
    return (
        "Revise el plan de investigacion antes de ejecutar Google Search.\n\n"
        f"Tema: {plan.topic}\n"
        f"Resumen: {plan.human_summary}\n"
        f"Iteraciones maximas: {plan.max_iterations}\n"
        f"Presupuesto maximo: {plan.max_budget_units} unidades\n"
        "Consultas propuestas:\n"
        f"{queries}\n\n"
        "Responde 'approve' para ejecutar, 'reject' para cancelar, o escribe "
        "feedback para revisar el plan."
    )


def _normalize_approval(raw: Any) -> ApprovalDecision:
    if isinstance(raw, ApprovalDecision):
        return raw
    if isinstance(raw, dict):
        if "status" in raw:
            return ApprovalDecision.model_validate(raw)
        if raw.get("approved") is True:
            return ApprovalDecision(status="approved")
        if raw.get("approved") is False:
            return ApprovalDecision(
                status="rejected", feedback=str(raw.get("feedback", ""))
            )
    text = content_to_text(raw)
    folded = _fold(text)
    if folded in {"approve", "approved", "yes", "si", "ok", "looks good"}:
        return ApprovalDecision(status="approved")
    if folded in {"reject", "rejected", "no", "cancel", "cancelar"}:
        return ApprovalDecision(status="rejected", feedback=text)
    return ApprovalDecision(status="revise", feedback=text)


def _hitl_plan_approval_impl(node_input: Any, ctx: Context):
    plan = _plan_from_any(node_input, ctx)
    raw_resume = _resume_inputs(ctx).get(APPROVAL_INTERRUPT_ID)
    if raw_resume is None:
        yield RequestInput(
            interrupt_id=APPROVAL_INTERRUPT_ID,
            message=_format_plan_message(plan),
            payload={
                "topic": plan.topic,
                "search_queries": plan.search_queries,
                "max_iterations": plan.max_iterations,
                "max_budget_units": plan.max_budget_units,
            },
            response_schema=ApprovalDecision,
        )
        return

    decision = _normalize_approval(raw_resume)
    yield Event(output=decision, route=decision.status)


hitl_plan_approval = node(
    _hitl_plan_approval_impl,
    name="hitl_plan_approval",
    rerun_on_resume=True,
)


def apply_plan_feedback(node_input: Any, ctx: Context) -> Event:
    decision = _normalize_approval(node_input)
    request = _request_from_state(ctx)
    revised = request.model_copy(update={"feedback": decision.feedback})
    return Event(
        output=revised,
        state={"current_request": revised.model_dump(), "plan_feedback": decision.feedback},
    )


def rejected_response(node_input: Any) -> Event:
    return Event(message="Investigacion cancelada. No se ejecuto ninguna busqueda.")


def guardrail_node(node_input: Any, ctx: Context) -> Event:
    state = _state(ctx)
    current_iteration = int(state.get("current_iteration", 0) or 0)
    max_iterations = int(state.get("max_iterations", config.max_iterations) or 1)
    budget_used = int(state.get("budget_used", 0) or 0)
    max_budget_units = int(
        state.get("max_budget_units", config.max_budget_units) or 1
    )

    if current_iteration >= max_iterations:
        result = LimitCheckResult(
            route="limit_reached",
            current_iteration=current_iteration,
            max_iterations=max_iterations,
            budget_used=budget_used,
            max_budget_units=max_budget_units,
            reason="Maximum iteration count reached",
        )
    elif budget_used >= max_budget_units:
        result = LimitCheckResult(
            route="limit_reached",
            current_iteration=current_iteration,
            max_iterations=max_iterations,
            budget_used=budget_used,
            max_budget_units=max_budget_units,
            reason="Maximum budget reached",
        )
    else:
        result = LimitCheckResult(
            route="execute_search",
            current_iteration=current_iteration,
            max_iterations=max_iterations,
            budget_used=budget_used,
            max_budget_units=max_budget_units,
            reason="Within execution limits",
        )
    return Event(output=result, route=result.route)


def _current_plan(ctx: Context) -> ResearchPlan:
    return _plan_from_any(_state(ctx).get("current_plan"), ctx)


def prepare_search_batch(node_input: Any, ctx: Context) -> Event:
    plan = _current_plan(ctx)
    state = _state(ctx)
    current_iteration = int(state.get("current_iteration", 0) or 0) + 1
    follow_up_queries = state.get("follow_up_queries") or []
    queries = follow_up_queries if current_iteration > 1 else plan.search_queries
    if not queries:
        queries = plan.search_queries
    batch = SearchBatch(
        topic=plan.topic,
        iteration=current_iteration,
        queries=list(queries)[:8],
    )
    return Event(
        output=batch,
        state={
            "current_iteration": current_iteration,
            "current_search_batch": batch.model_dump(),
        },
    )


def provider_status_branch(node_input: SearchBatch) -> Event:
    branch = BranchResult(
        branch_id="provider_status_branch",
        provider="provider_status",
        status="skipped",
        errors=[
            "Google Search is the active provider. Exa, Tavily and GitHub "
            "adapters are intentionally not executed without configured keys."
        ],
    )
    return Event(output=branch)


def _batch_from_state(ctx: Context) -> SearchBatch:
    raw = _state(ctx).get("current_search_batch") or {}
    if isinstance(raw, SearchBatch):
        return raw
    if isinstance(raw, dict) and raw.get("topic"):
        return SearchBatch.model_validate(raw)
    plan = _current_plan(ctx)
    return SearchBatch(topic=plan.topic, iteration=1, queries=plan.search_queries)


def _extract_citations(text: str) -> list[SourceCitation]:
    citations: list[SourceCitation] = []
    seen: set[str] = set()
    for match in _URL_RE.findall(text):
        url = match.rstrip(".,;:")
        if url in seen:
            continue
        seen.add(url)
        citations.append(SourceCitation(title=url, url=url))
    return citations


def _normalize_branch_result(
    branch_id: str,
    value: Any,
    batch: SearchBatch,
) -> BranchResult:
    if isinstance(value, BranchResult):
        return value
    if isinstance(value, Event) and value.output is not None:
        return _normalize_branch_result(branch_id, value.output, batch)
    if isinstance(value, dict) and value.get("branch_id"):
        return BranchResult.model_validate(value)

    summary = content_to_text(value)
    if branch_id == "google_search_provider":
        result = ProviderSearchResult(
            provider="google_search",
            query="; ".join(batch.queries),
            summary=summary or "Google Search returned no text output.",
            citations=_extract_citations(summary),
            status="ok" if summary else "error",
            error="" if summary else "Empty Google Search output",
        )
        return BranchResult(
            branch_id=branch_id,
            provider="google_search",
            status=result.status,
            results=[result],
            errors=[result.error] if result.error else [],
        )

    return BranchResult(
        branch_id=branch_id,
        provider="provider_status",
        status="skipped",
        errors=[summary or "Branch did not return provider evidence."],
    )


def _normalize_join_input(node_input: Any) -> dict[str, Any]:
    if isinstance(node_input, Event) and node_input.output is not None:
        return _normalize_join_input(node_input.output)
    if isinstance(node_input, dict):
        return node_input
    if isinstance(node_input, (list, tuple)):
        return {f"branch_{index}": value for index, value in enumerate(node_input)}
    return {"google_search_provider": node_input}


def collect_search_iteration(node_input: Any, ctx: Context) -> Event:
    batch = _batch_from_state(ctx)
    joined = _normalize_join_input(node_input)
    branch_results = [
        _normalize_branch_result(branch_id, value, batch)
        for branch_id, value in joined.items()
    ]
    provider_results: list[ProviderSearchResult] = []
    errors: list[str] = []
    for branch in branch_results:
        provider_results.extend(branch.results)
        errors.extend(branch.errors)

    budget_used = int(_state(ctx).get("budget_used", 0) or 0) + max(
        1, len(batch.queries)
    )
    findings = ResearchFindings(
        topic=batch.topic,
        iteration=batch.iteration,
        results=provider_results,
        errors=errors,
        budget_used=budget_used,
    )
    previous_findings = list(_state(ctx).get("research_findings") or [])
    previous_findings.append(findings.model_dump())
    return Event(
        output=findings,
        state={"budget_used": budget_used, "research_findings": previous_findings},
    )


def _assessment_from_any(value: Any, ctx: Context) -> QualityAssessment:
    if isinstance(value, QualityAssessment):
        assessment = value
    elif isinstance(value, Event) and value.output is not None:
        assessment = _assessment_from_any(value.output, ctx)
    elif isinstance(value, dict):
        assessment = QualityAssessment.model_validate(value)
    elif isinstance(value, str):
        try:
            assessment = QualityAssessment.model_validate(json.loads(value))
        except (json.JSONDecodeError, ValueError, TypeError):
            assessment = QualityAssessment(
                route="synthesize",
                score=0.5,
                reason=value[:300] or "Evaluator returned text output.",
            )
    else:
        assessment = QualityAssessment(
            route="synthesize",
            score=0.5,
            reason="No structured quality assessment returned.",
        )

    state = _state(ctx)
    current_iteration = int(state.get("current_iteration", 0) or 0)
    max_iterations = int(state.get("max_iterations", config.max_iterations) or 1)
    budget_used = int(state.get("budget_used", 0) or 0)
    max_budget_units = int(
        state.get("max_budget_units", config.max_budget_units) or 1
    )
    if current_iteration >= max_iterations or budget_used >= max_budget_units:
        return assessment.model_copy(
            update={
                "route": "synthesize",
                "reason": f"{assessment.reason} Guardrail limit reached.",
            }
        )
    return assessment


def quality_router(node_input: Any, ctx: Context) -> Event:
    assessment = _assessment_from_any(node_input, ctx)
    return Event(
        output=assessment,
        route=assessment.route,
        state={
            "last_quality_assessment": assessment.model_dump(),
            "follow_up_queries": assessment.follow_up_queries,
        },
    )


def _findings_from_state(ctx: Context) -> list[ResearchFindings]:
    findings: list[ResearchFindings] = []
    for raw in _state(ctx).get("research_findings") or []:
        if isinstance(raw, ResearchFindings):
            findings.append(raw)
        elif isinstance(raw, dict):
            findings.append(ResearchFindings.model_validate(raw))
    return findings


def synthesis_node(node_input: Any, ctx: Context) -> Event:
    plan = _current_plan(ctx)
    findings = _findings_from_state(ctx)
    citations: list[SourceCitation] = []
    citation_urls: set[str] = set()
    finding_sections: list[str] = []
    errors: list[str] = []

    for finding in findings:
        result_lines = []
        for result in finding.results:
            result_lines.append(f"- [{result.provider}] {result.summary}")
            for citation in result.citations:
                if citation.url not in citation_urls:
                    citation_urls.add(citation.url)
                    citations.append(citation)
        errors.extend(finding.errors)
        joined_results = "\n".join(result_lines) or "- No provider evidence returned."
        finding_sections.append(
            f"### Iteration {finding.iteration}\n{joined_results}"
        )

    limitations = [
        "The workflow uses Google Search as the only live provider in this build.",
        "Paywalls, captchas and unavailable pages are not bypassed.",
    ]
    if not citations:
        limitations.append(
            "No explicit URLs were present in the normalized provider text. "
            "ADK grounding metadata may still be available in runtime events."
        )
    if errors:
        limitations.extend(errors)

    sources = "\n".join(
        f"- [{citation.title}]({citation.url})" for citation in citations
    ) or "- No explicit source URLs were normalized."
    body = "\n\n".join(finding_sections) or "No search findings were collected."
    budget_used = int(_state(ctx).get("budget_used", 0) or 0)
    iterations = int(_state(ctx).get("current_iteration", 0) or 0)
    report_text = (
        f"# Deep Web Research Report: {plan.topic}\n\n"
        f"## Research Plan\n{plan.human_summary}\n\n"
        f"## Findings\n{body}\n\n"
        f"## Sources\n{sources}\n\n"
        "## Limitations\n"
        + "\n".join(f"- {item}" for item in limitations)
        + f"\n\nIterations: {iterations}. Budget used: {budget_used}."
    )
    final_report = {
        "topic": plan.topic,
        "report": report_text,
        "citations": [citation.model_dump() for citation in citations],
        "limitations": limitations,
        "iterations": iterations,
        "budget_used": budget_used,
    }
    return Event(
        message=report_text,
        state={
            "last_research_topic": plan.topic,
            "last_research_report": report_text,
            "final_research_report": final_report,
        },
    )


__all__ = [
    "APPROVAL_INTERRUPT_ID",
    "_hitl_plan_approval_impl",
    "apply_plan_feedback",
    "build_research_request",
    "clarification_response",
    "collect_search_iteration",
    "content_to_text",
    "direct_answer_response",
    "greeting_response",
    "guardrail_node",
    "hitl_plan_approval",
    "initialize_plan_state",
    "intent_gate",
    "memory_answer_response",
    "normalize_user_input",
    "prepare_search_batch",
    "provider_status_branch",
    "quality_router",
    "rejected_response",
    "smalltalk_response",
    "synthesis_node",
    "thanks_response",
]
