import logging
import os
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.task_splitter.prompts import (
    CANDIDATE_TASK_PLANNER_PROMPT,
    COVERAGE_CHECKER_PROMPT,
    DEPENDENCY_CHECKER_PROMPT,
    EXECUTABILITY_CHECKER_PROMPT,
    GOAL_INTERPRETER_PROMPT,
    GRANULARITY_CHECKER_PROMPT,
    PROBLEM_DEFINITION_PROMPT,
    REPAIR_AGENT_PROMPT,
    STATE_ABSTRACTOR_PROMPT,
    VERIFIABILITY_CHECKER_PROMPT,
)
from app.task_splitter.schemas import (
    CoverageReport,
    DependencyReport,
    ExecutabilityReport,
    GoalState,
    GranularityReport,
    LLMCandidateTaskGraph,
    LLMProblemDefinition,
    LLMRepairResult,
    MacroState,
    VerifiabilityReport,
)
from app.task_splitter.workflow_agents import (
    TaskSplitterWorkflowAgent,
    candidate_graph_normalizer_agent,
    execution_scheduler_agent,
    final_emitter_agent,
    final_quality_aggregator_agent,
    final_quality_guard_agent,
    initial_graph_snapshot_agent,
    problem_definition_normalizer_agent,
    quality_aggregator_agent,
    repair_loop_exit_gate,
    repair_result_applier_agent,
    repair_result_normalizer_agent,
    runtime_configuration_injector_agent,
    trace_logger_agent,
)

logger = logging.getLogger(__name__)
APP_NAME = Path(__file__).resolve().parent.name
MODEL_NAME = "gemini-3.1-pro-preview"


def _configure_vertex_environment() -> None:
    """Default local execution to Vertex AI while preserving explicit env values."""
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


def _json_agent(
    *,
    name: str,
    description: str,
    instruction: str,
    output_schema: type,
    output_key: str,
) -> Agent:
    return Agent(
        name=name,
        model=_model(),
        description=description,
        instruction=instruction,
        output_schema=output_schema,
        output_key=output_key,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


_configure_vertex_environment()

problem_definition_agent = _json_agent(
    name="problem_definition_agent",
    description="Classifies input and defines whether TaskSplitter should run.",
    instruction=PROBLEM_DEFINITION_PROMPT,
    output_schema=LLMProblemDefinition,
    output_key="problem_definition_draft",
)

goal_interpreter = _json_agent(
    name="goal_interpreter",
    description="Interprets the raw user goal as an observable GoalState.",
    instruction=GOAL_INTERPRETER_PROMPT,
    output_schema=GoalState,
    output_key="goal_state",
)

state_abstractor = _json_agent(
    name="state_abstractor",
    description="Abstracts known context into a planning MacroState.",
    instruction=STATE_ABSTRACTOR_PROMPT,
    output_schema=MacroState,
    output_key="macro_state",
)

candidate_task_planner = _json_agent(
    name="candidate_task_planner",
    description="Generates the initial task graph hypothesis.",
    instruction=CANDIDATE_TASK_PLANNER_PROMPT,
    output_schema=LLMCandidateTaskGraph,
    output_key="candidate_task_graph_draft",
)

coverage_checker = _json_agent(
    name="coverage_checker",
    description="Checks whether the graph covers the goal.",
    instruction=COVERAGE_CHECKER_PROMPT,
    output_schema=CoverageReport,
    output_key="coverage_report",
)

granularity_checker = _json_agent(
    name="granularity_checker",
    description="Checks whether tasks have the right abstraction level.",
    instruction=GRANULARITY_CHECKER_PROMPT,
    output_schema=GranularityReport,
    output_key="granularity_report",
)

dependency_checker = _json_agent(
    name="dependency_checker",
    description="Checks causal dependencies and parallelization safety.",
    instruction=DEPENDENCY_CHECKER_PROMPT,
    output_schema=DependencyReport,
    output_key="dependency_report",
)

executability_checker = _json_agent(
    name="executability_checker",
    description="Checks whether each task has a plausible executor.",
    instruction=EXECUTABILITY_CHECKER_PROMPT,
    output_schema=ExecutabilityReport,
    output_key="executability_report",
)

verifiability_checker = _json_agent(
    name="verifiability_checker",
    description="Checks whether each task can be verified.",
    instruction=VERIFIABILITY_CHECKER_PROMPT,
    output_schema=VerifiabilityReport,
    output_key="verifiability_report",
)

parallel_checkers = SequentialAgent(
    name="decomposition_evaluator",
    description="Runs decomposition quality checks sequentially to surface checker failures directly.",
    sub_agents=[
        coverage_checker,
        granularity_checker,
        dependency_checker,
        executability_checker,
        verifiability_checker,
    ],
)

repair_agent = _json_agent(
    name="repair_agent",
    description="Applies targeted repairs to the candidate task graph.",
    instruction=REPAIR_AGENT_PROMPT,
    output_schema=LLMRepairResult,
    output_key="repair_result_draft",
)

repair_loop = LoopAgent(
    name="repair_loop",
    description="Evaluates and repairs the graph until quality is sufficient or the iteration cap is reached.",
    max_iterations=2,
    sub_agents=[
        parallel_checkers,
        quality_aggregator_agent,
        repair_loop_exit_gate,
        repair_agent,
        repair_result_normalizer_agent,
        repair_result_applier_agent,
    ],
)

final_coverage_checker = _json_agent(
    name="final_coverage_checker",
    description="Re-checks final graph coverage after repairs are applied.",
    instruction=COVERAGE_CHECKER_PROMPT,
    output_schema=CoverageReport,
    output_key="coverage_report",
)

final_granularity_checker = _json_agent(
    name="final_granularity_checker",
    description="Re-checks final graph task granularity after repairs are applied.",
    instruction=GRANULARITY_CHECKER_PROMPT,
    output_schema=GranularityReport,
    output_key="granularity_report",
)

final_dependency_checker = _json_agent(
    name="final_dependency_checker",
    description="Re-checks final graph dependencies after repairs are applied.",
    instruction=DEPENDENCY_CHECKER_PROMPT,
    output_schema=DependencyReport,
    output_key="dependency_report",
)

final_executability_checker = _json_agent(
    name="final_executability_checker",
    description="Re-checks final graph executability after repairs are applied.",
    instruction=EXECUTABILITY_CHECKER_PROMPT,
    output_schema=ExecutabilityReport,
    output_key="executability_report",
)

final_verifiability_checker = _json_agent(
    name="final_verifiability_checker",
    description="Re-checks final graph verifiability after repairs are applied.",
    instruction=VERIFIABILITY_CHECKER_PROMPT,
    output_schema=VerifiabilityReport,
    output_key="verifiability_report",
)

final_parallel_checkers = SequentialAgent(
    name="final_decomposition_evaluator",
    description="Re-runs quality checks against the final repaired graph sequentially.",
    sub_agents=[
        final_coverage_checker,
        final_granularity_checker,
        final_dependency_checker,
        final_executability_checker,
        final_verifiability_checker,
    ],
)

root_agent = TaskSplitterWorkflowAgent(
    name="task_splitter_workflow",
    description="Defines a planning problem, then transforms complex goals into ADK 2.0 workflow implementation plans.",
    sub_agents=[
        problem_definition_agent,
        problem_definition_normalizer_agent,
        goal_interpreter,
        state_abstractor,
        candidate_task_planner,
        candidate_graph_normalizer_agent,
        initial_graph_snapshot_agent,
        repair_loop,
        runtime_configuration_injector_agent,
        final_parallel_checkers,
        final_quality_aggregator_agent,
        final_quality_guard_agent,
        execution_scheduler_agent,
        trace_logger_agent,
        final_emitter_agent,
    ],
)

app = App(
    root_agent=root_agent,
    name=APP_NAME,
)
