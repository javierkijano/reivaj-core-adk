"""ADK 2.0 graph workflow for deep web research."""

from google.adk import Workflow
from google.adk.workflow import JoinNode

from .nodes import (
    apply_plan_feedback,
    build_research_request,
    clarification_response,
    collect_search_iteration,
    direct_answer_response,
    greeting_response,
    guardrail_node,
    hitl_plan_approval,
    initialize_plan_state,
    intent_gate,
    memory_answer_response,
    normalize_user_input,
    prepare_search_batch,
    provider_status_branch,
    quality_router,
    rejected_response,
    smalltalk_response,
    synthesis_node,
    thanks_response,
)
from .search_agents import google_search_provider, quality_evaluator, research_planner

search_join_node = JoinNode(name="search_join_node")

root_agent = Workflow(
    name="root_deep_web_research",
    description=(
        "General-chat safe ADK 2.0 Workflow for human-approved, "
        "guardrailed deep web research using Google Search."
    ),
    edges=[
        ("START", normalize_user_input, intent_gate),
        (
            intent_gate,
            {
                "greeting": greeting_response,
                "thanks": thanks_response,
                "small_talk": smalltalk_response,
                "simple_question": direct_answer_response,
                "ambiguous": clarification_response,
                "direct_qa": memory_answer_response,
                "new_research": build_research_request,
            },
        ),
        (build_research_request, research_planner),
        (research_planner, initialize_plan_state, hitl_plan_approval),
        (
            hitl_plan_approval,
            {
                "approved": guardrail_node,
                "rejected": rejected_response,
                "revise": apply_plan_feedback,
            },
        ),
        (apply_plan_feedback, research_planner),
        (
            guardrail_node,
            {
                "execute_search": prepare_search_batch,
                "limit_reached": synthesis_node,
            },
        ),
        (
            prepare_search_batch,
            (google_search_provider, provider_status_branch),
            search_join_node,
            collect_search_iteration,
            quality_evaluator,
            quality_router,
        ),
        (
            quality_router,
            {
                "continue": guardrail_node,
                "synthesize": synthesis_node,
            },
        ),
    ],
)

__all__ = ["root_agent"]
