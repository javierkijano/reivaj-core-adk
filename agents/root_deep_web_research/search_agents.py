"""LLM and Google Search task nodes used by the workflow graph."""

from google.adk import Agent
from google.adk.tools import google_search

from .config import config
from .schemas import (
    QualityAssessment,
    ResearchFindings,
    ResearchPlan,
    ResearchRequest,
    SearchBatch,
)

research_planner = Agent(
    name="research_planner",
    model=config.planner_model,
    mode="single_turn",
    description="Creates a human-readable web research plan after intent gating.",
    input_schema=ResearchRequest,
    output_schema=ResearchPlan,
    instruction="""
You are the planning node for a deep web research workflow.

The request has already passed the front-door intent gate. Do not handle
greetings or small talk. Create a concise research plan that a human can approve
before any web search runs.

Rules:
- Use only the provider name `google_search` in selected_providers.
- Produce 3 to 5 targeted Google Search queries.
- Keep max_iterations between 1 and 2 unless the user explicitly asks for more.
- Keep max_budget_units between 3 and 6 unless the user explicitly asks for more.
- If feedback is present, revise the plan to address it.
- The human_summary must be readable by an end user and must not expose JSON.
""",
)

google_search_provider = Agent(
    name="google_search_provider",
    model=config.search_model,
    mode="single_turn",
    description="Executes approved research queries with the ADK Google Search tool.",
    input_schema=SearchBatch,
    instruction="""
You are the Google Search execution branch for a pre-approved research plan.

Use the `google_search` tool for every query in the SearchBatch. Return a
compact evidence memo with:
- the executed queries;
- key findings tied to sources;
- source URLs when available;
- uncertainties or gaps.

Do not ask the user for approval here. Approval already happened upstream.
""",
    tools=[google_search],
)

quality_evaluator = Agent(
    name="quality_evaluator",
    model=config.evaluator_model,
    mode="single_turn",
    description="Decides whether another bounded search pass is needed.",
    input_schema=ResearchFindings,
    output_schema=QualityAssessment,
    instruction="""
Evaluate whether the current findings are sufficient for synthesis.

Return `synthesize` if the evidence is enough or if another search pass is not
worth the budget. Return `continue` only when there are concrete gaps and you can
provide targeted follow-up queries. Do not exceed the workflow budget; the
guardrail node enforces the final stop condition.
""",
)

__all__ = ["google_search_provider", "quality_evaluator", "research_planner"]
