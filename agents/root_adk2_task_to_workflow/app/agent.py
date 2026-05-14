import logging
import os
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.adk import Agent, Workflow
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import JoinNode
from google.genai import types

from app.task_splitter.prompts import (
    DIRECT_ANSWER_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    PROBLEM_DEFINITION_PROMPT,
    REPAIR_PROMPT,
    WORKFLOW_PLANNER_PROMPT,
)
from app.task_splitter.schemas import (
    DirectAnswer,
    IntentDecision,
    NormalizedRequest,
    ProblemDefinition,
    RegistryReview,
    RepairRequest,
    WorkflowPlan,
)
from app.task_splitter.workflow_nodes import (
    aggregate_quality,
    ambiguous_response,
    build_repair_request,
    check_activation_policy,
    check_data_contracts,
    check_graph_contract,
    check_registry_usage,
    check_verification_strategy,
    direct_answer_message,
    final_emitter,
    greeting_response,
    intent_router,
    normalize_user_input,
    registry_review_node,
    repair_router,
    small_talk_response,
    store_initial_plan,
    store_repaired_plan,
    thanks_response,
)

logger = logging.getLogger(__name__)
APP_NAME = Path(__file__).resolve().parent.name
MODEL_NAME = "gemini-3.1-pro-preview"


def _configure_vertex_environment() -> None:
    load_dotenv()
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return

    try:
        _, project_id = google.auth.default()
    except Exception as exc:
        logger.debug("Could not infer GOOGLE_CLOUD_PROJECT from ADC: %s", exc)
        return

    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id


def _model() -> Gemini:
    return Gemini(
        model=MODEL_NAME,
        retry_options=types.HttpRetryOptions(attempts=3),
    )


def _structured_agent(
    *,
    name: str,
    description: str,
    instruction: str,
    output_schema: type,
    input_schema: type | None = None,
    output_key: str | None = None,
) -> Agent:
    return Agent(
        name=name,
        model=_model(),
        description=description,
        instruction=instruction,
        input_schema=input_schema,
        output_schema=output_schema,
        output_key=output_key,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


_configure_vertex_environment()

structured_intent_classifier = _structured_agent(
    name="structured_intent_classifier",
    description="Classifies natural user input into closed workflow routes.",
    instruction=INTENT_CLASSIFIER_PROMPT,
    input_schema=NormalizedRequest,
    output_schema=IntentDecision,
    output_key="intent_decision",
)

direct_answer_agent = _structured_agent(
    name="direct_answer_agent",
    description="Answers simple questions without activating the workflow planner.",
    instruction=DIRECT_ANSWER_PROMPT,
    input_schema=IntentDecision,
    output_schema=DirectAnswer,
)

problem_definition_agent = _structured_agent(
    name="problem_definition_agent",
    description="Defines the implementation problem after registry review.",
    instruction=PROBLEM_DEFINITION_PROMPT,
    input_schema=RegistryReview,
    output_schema=ProblemDefinition,
    output_key="problem_definition",
)

workflow_planner_agent = _structured_agent(
    name="workflow_planner_agent",
    description="Produces the ADK 2.0 Workflow implementation plan.",
    instruction=WORKFLOW_PLANNER_PROMPT,
    input_schema=ProblemDefinition,
    output_schema=WorkflowPlan,
    output_key="workflow_plan_draft",
)

repair_agent = _structured_agent(
    name="repair_agent",
    description="Repairs a workflow plan using deterministic quality reports.",
    instruction=REPAIR_PROMPT,
    input_schema=RepairRequest,
    output_schema=WorkflowPlan,
    output_key="repaired_workflow_plan",
)

quality_checkers = (
    check_activation_policy,
    check_graph_contract,
    check_data_contracts,
    check_registry_usage,
    check_verification_strategy,
)
quality_join = JoinNode(name="quality_join")

root_agent = Workflow(
    name="root_adk2_task_to_workflow",
    description="Reference ADK 2.0 graph Workflow implementation planner.",
    max_concurrency=5,
    edges=[
        (
            "START",
            normalize_user_input,
            structured_intent_classifier,
            intent_router,
        ),
        (
            intent_router,
            {
                "greeting": greeting_response,
                "thanks": thanks_response,
                "small_talk": small_talk_response,
                "simple_question": direct_answer_agent,
                "ambiguous": ambiguous_response,
                "workflow_request": registry_review_node,
            },
        ),
        (direct_answer_agent, direct_answer_message),
        (
            registry_review_node,
            problem_definition_agent,
            workflow_planner_agent,
            store_initial_plan,
        ),
        (store_initial_plan, quality_checkers),
        (quality_checkers, quality_join, aggregate_quality, repair_router),
        (
            repair_router,
            {
                "repair": build_repair_request,
                "finalize": final_emitter,
            },
        ),
        (build_repair_request, repair_agent, store_repaired_plan),
        (store_repaired_plan, quality_checkers),
    ],
)

app = App(
    root_agent=root_agent,
    name=APP_NAME,
)
