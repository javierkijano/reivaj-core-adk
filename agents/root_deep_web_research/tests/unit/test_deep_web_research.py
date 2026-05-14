from __future__ import annotations

import asyncio

from google.adk import Workflow
from google.adk.events import RequestInput
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from root_deep_web_research.agent import root_agent
from root_deep_web_research.nodes import (
    APPROVAL_INTERRUPT_ID,
    _hitl_plan_approval_impl,
    build_research_request,
    clarification_response,
    collect_search_iteration,
    content_to_text,
    greeting_response,
    guardrail_node,
    intent_gate,
    normalize_user_input,
    prepare_search_batch,
    quality_router,
    synthesis_node,
)
from root_deep_web_research.schemas import (
    ApprovalDecision,
    BranchResult,
    NormalizedInput,
    ProviderSearchResult,
    QualityAssessment,
    ResearchFindings,
    ResearchPlan,
    SearchBatch,
)
from root_deep_web_research.search_agents import google_search_provider


class FakeContext:
    def __init__(self, state=None, resume_inputs=None):
        self.state = state or {}
        self.resume_inputs = resume_inputs or {}


def _message_text(event):
    return event.content.parts[0].text


def _route(event):
    return event.actions.route


def test_root_agent_is_workflow():
    assert isinstance(root_agent, Workflow)


def test_workflow_runner_greeting_path_uses_node_input_binding():
    async def run_greeting():
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name="root_deep_web_research",
            user_id="user",
            session_id="greeting-session",
        )
        runner = Runner(
            agent=root_agent,
            app_name="root_deep_web_research",
            session_service=session_service,
        )
        events = []
        async for event in runner.run_async(
            user_id="user",
            session_id="greeting-session",
            new_message=Content(role="user", parts=[Part(text="Hola")]),
        ):
            events.append(event)
        return events

    events = asyncio.run(run_greeting())
    messages = [
        event.content.parts[0].text
        for event in events
        if event.content and event.content.parts and event.content.parts[0].text
    ]

    assert any("investigar" in message.lower() for message in messages)


def test_google_search_provider_uses_builtin_google_search_tool():
    assert google_search_provider.tools
    assert google_search_provider.tools[0].__class__.__name__ == "GoogleSearchTool"


def test_start_node_accepts_content_and_normalizes_text():
    ctx = FakeContext()
    event = normalize_user_input(
        ctx,
        Content(role="user", parts=[Part(text="Investiga ADK 2.0 Workflow")]),
    )

    assert event.output == NormalizedInput(
        original_text="Investiga ADK 2.0 Workflow",
        normalized_text="Investiga ADK 2.0 Workflow",
        source="content",
    )
    assert event.actions.state_delta["last_user_input"] == "Investiga ADK 2.0 Workflow"


def test_greeting_does_not_reach_planner_or_hitl():
    ctx = FakeContext()
    normalized = normalize_user_input(
        ctx, Content(role="user", parts=[Part(text="Hola")])
    ).output
    intent_event = intent_gate(normalized, ctx)

    assert _route(intent_event) == "greeting"
    response = greeting_response(intent_event.output)
    assert "investigar" in _message_text(response).lower()
    assert not isinstance(response, RequestInput)


def test_empty_input_and_bare_topic_are_ambiguous():
    ctx = FakeContext()

    empty = intent_gate(NormalizedInput(original_text="", normalized_text="", source="string"), ctx)
    bare_topic = intent_gate(
        NormalizedInput(original_text="ADK", normalized_text="ADK", source="string"),
        ctx,
    )

    assert _route(empty) == "ambiguous"
    assert _route(bare_topic) == "ambiguous"
    assert "mas clara" in _message_text(clarification_response(bare_topic.output))


def test_explicit_research_request_routes_to_new_research():
    ctx = FakeContext()
    normalized = normalize_user_input(
        ctx,
        Content(
            role="user",
            parts=[Part(text="Investiga ADK 2.0 Workflow con fuentes")],
        ),
    ).output

    intent_event = intent_gate(normalized, ctx)
    request_event = build_research_request(intent_event.output, ctx)

    assert _route(intent_event) == "new_research"
    assert request_event.output.topic == "ADK 2.0 Workflow con fuentes"
    assert request_event.actions.state_delta["current_request"]["topic"] == (
        "ADK 2.0 Workflow con fuentes"
    )


def test_hitl_first_pause_is_natural_and_has_stable_interrupt_id():
    ctx = FakeContext()
    plan = ResearchPlan(
        topic="ADK 2.0 Workflow",
        rationale="Validate current documentation.",
        search_queries=["ADK 2.0 Workflow docs", "ADK Workflow JoinNode"],
        max_iterations=2,
        max_budget_units=4,
        human_summary="Research ADK 2.0 Workflow implementation patterns.",
    )

    events = list(_hitl_plan_approval_impl(plan, ctx))

    assert len(events) == 1
    request = events[0]
    assert isinstance(request, RequestInput)
    assert request.interrupt_id == APPROVAL_INTERRUPT_ID
    assert "Revise el plan" in request.message
    assert "approved_plan" not in request.message
    assert "{" not in request.message


def test_hitl_resume_routes_approved_rejected_and_revise():
    plan = ResearchPlan(
        topic="ADK",
        rationale="Research ADK.",
        search_queries=["ADK docs"],
        human_summary="Research ADK.",
    )

    approved_ctx = FakeContext(resume_inputs={APPROVAL_INTERRUPT_ID: "approve"})
    rejected_ctx = FakeContext(resume_inputs={APPROVAL_INTERRUPT_ID: "reject"})
    revise_ctx = FakeContext(resume_inputs={APPROVAL_INTERRUPT_ID: "Add more sources"})

    assert _route(list(_hitl_plan_approval_impl(plan, approved_ctx))[0]) == "approved"
    assert _route(list(_hitl_plan_approval_impl(plan, rejected_ctx))[0]) == "rejected"
    revise_event = list(_hitl_plan_approval_impl(plan, revise_ctx))[0]
    assert _route(revise_event) == "revise"
    assert revise_event.output == ApprovalDecision(status="revise", feedback="Add more sources")


def test_guardrail_routes_to_execute_search_or_limit_reached():
    execute_ctx = FakeContext(
        state={
            "current_iteration": 0,
            "max_iterations": 2,
            "budget_used": 0,
            "max_budget_units": 4,
        }
    )
    limit_ctx = FakeContext(
        state={
            "current_iteration": 2,
            "max_iterations": 2,
            "budget_used": 0,
            "max_budget_units": 4,
        }
    )

    assert _route(guardrail_node(None, execute_ctx)) == "execute_search"
    assert _route(guardrail_node(None, limit_ctx)) == "limit_reached"


def test_prepare_search_batch_uses_plan_and_iteration_state():
    ctx = FakeContext(
        state={
            "current_plan": ResearchPlan(
                topic="ADK",
                rationale="Research ADK.",
                search_queries=["ADK Workflow", "ADK Google Search"],
                human_summary="Research ADK.",
            ).model_dump(),
            "current_iteration": 0,
        }
    )

    event = prepare_search_batch(None, ctx)

    assert event.output == SearchBatch(
        topic="ADK",
        iteration=1,
        queries=["ADK Workflow", "ADK Google Search"],
    )
    assert event.actions.state_delta["current_iteration"] == 1


def test_collect_search_iteration_normalizes_join_input_and_updates_budget():
    batch = SearchBatch(topic="ADK", iteration=1, queries=["ADK Workflow"])
    ctx = FakeContext(
        state={
            "current_search_batch": batch.model_dump(),
            "budget_used": 0,
            "research_findings": [],
        }
    )
    joined = {
        "google_search_provider": "Finding with source https://adk.dev/workflows/",
        "provider_status_branch": BranchResult(
            branch_id="provider_status_branch",
            provider="provider_status",
            status="skipped",
            errors=["No other provider configured"],
        ),
    }

    event = collect_search_iteration(joined, ctx)

    assert isinstance(event.output, ResearchFindings)
    assert event.output.results[0] == ProviderSearchResult(
        provider="google_search",
        query="ADK Workflow",
        summary="Finding with source https://adk.dev/workflows/",
        citations=[
            {
                "title": "https://adk.dev/workflows/",
                "url": "https://adk.dev/workflows/",
            }
        ],
        status="ok",
    )
    assert event.actions.state_delta["budget_used"] == 1
    assert len(event.actions.state_delta["research_findings"]) == 1


def test_quality_router_forces_synthesis_when_limits_are_reached():
    ctx = FakeContext(
        state={
            "current_iteration": 2,
            "max_iterations": 2,
            "budget_used": 1,
            "max_budget_units": 4,
        }
    )
    assessment = QualityAssessment(
        route="continue",
        score=0.4,
        reason="Needs another pass.",
        follow_up_queries=["ADK Workflow examples"],
    )

    event = quality_router(assessment, ctx)

    assert _route(event) == "synthesize"


def test_synthesis_node_returns_user_message_and_preserves_memory():
    finding = ResearchFindings(
        topic="ADK",
        iteration=1,
        results=[
            ProviderSearchResult(
                provider="google_search",
                query="ADK Workflow",
                summary="ADK Workflow supports graph routes. https://adk.dev/workflows/",
                citations=[
                    {
                        "title": "ADK Workflows",
                        "url": "https://adk.dev/workflows/",
                    }
                ],
            )
        ],
        budget_used=1,
    )
    ctx = FakeContext(
        state={
            "current_plan": ResearchPlan(
                topic="ADK",
                rationale="Research ADK.",
                search_queries=["ADK Workflow"],
                human_summary="Research ADK Workflow.",
            ).model_dump(),
            "research_findings": [finding.model_dump()],
            "current_iteration": 1,
            "budget_used": 1,
        }
    )

    event = synthesis_node(None, ctx)

    assert "Deep Web Research Report: ADK" in _message_text(event)
    assert event.actions.state_delta["last_research_topic"] == "ADK"
    assert "last_research_report" in event.actions.state_delta


def test_content_to_text_supports_content_parts():
    content = Content(role="user", parts=[Part(text="A"), Part(text="B")])
    assert content_to_text(content) == "A B"
