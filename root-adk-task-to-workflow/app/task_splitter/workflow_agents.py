from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from app.task_splitter.logic import (
    aggregate_quality_report,
    apply_final_quality_guard,
    build_execution_schedule,
    build_task_splitter_output,
    ensure_runtime_configuration_task,
    model_dump,
    model_from_state,
    normalize_llm_repair_result,
    normalize_llm_task_graph,
    optional_model_from_state,
    quality_reports_from_state,
    repair_operations_from_state,
)
from app.task_splitter.schemas import (
    CandidateTaskGraph,
    CoverageReport,
    DecompositionTrace,
    DependencyReport,
    ExecutabilityReport,
    ExecutionSchedule,
    GoalState,
    GranularityReport,
    LLMCandidateTaskGraph,
    LLMRepairResult,
    MacroState,
    QualityReport,
    RepairResult,
    VerifiabilityReport,
)


def _state(ctx: InvocationContext) -> dict[str, Any]:
    return ctx.session.state


class CandidateGraphNormalizerAgent(BaseAgent):
    """Converts the live-safe LLM draft graph into the full internal TaskGraph."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        draft = model_from_state(
            LLMCandidateTaskGraph, _state(ctx)["candidate_task_graph_draft"]
        )
        graph = normalize_llm_task_graph(draft)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"candidate_task_graph": model_dump(graph)},
            ),
        )


class InitialGraphSnapshotAgent(BaseAgent):
    """Stores the initial graph before repair iterations mutate it."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        graph = model_from_state(CandidateTaskGraph, state["candidate_task_graph"])
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"initial_task_graph": model_dump(graph)},
            ),
        )


class QualityAggregatorAgent(BaseAgent):
    """Aggregates parallel checker reports into one weighted QualityReport."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        graph = model_from_state(CandidateTaskGraph, state["candidate_task_graph"])
        goal_state = optional_model_from_state(GoalState, state.get("goal_state"))
        quality_report = aggregate_quality_report(
            graph=graph,
            coverage=optional_model_from_state(
                CoverageReport, state.get("coverage_report")
            ),
            granularity=optional_model_from_state(
                GranularityReport, state.get("granularity_report")
            ),
            dependency=optional_model_from_state(
                DependencyReport, state.get("dependency_report")
            ),
            executability=optional_model_from_state(
                ExecutabilityReport, state.get("executability_report")
            ),
            verifiability=optional_model_from_state(
                VerifiabilityReport, state.get("verifiability_report")
            ),
            goal_state=goal_state,
        )
        previous_reports = quality_reports_from_state(state.get("quality_reports"))
        previous_reports.append(quality_report)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "quality_report": model_dump(quality_report),
                    "quality_reports": [
                        model_dump(report) for report in previous_reports
                    ],
                    "pending_repair_suggestions": quality_report.pending_repair_suggestions,
                }
            ),
        )


class RepairLoopExitGate(BaseAgent):
    """Stops the repair loop when the graph is good enough or needs the user."""

    min_score: float = 0.85

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        quality_report = model_from_state(QualityReport, state["quality_report"])
        requires_user = bool(state.get("requires_user_clarification"))
        has_pending_repairs = bool(quality_report.pending_repair_suggestions)
        should_stop = requires_user or (
            quality_report.overall_score >= self.min_score
            and not quality_report.critical_failures
            and not has_pending_repairs
            and quality_report.status in {"valid", "usable_with_warnings"}
        )
        yield Event(
            author=self.name,
            actions=EventActions(escalate=True) if should_stop else EventActions(),
        )


class RepairResultApplierAgent(BaseAgent):
    """Promotes RepairResult.repaired_task_graph to the graph under evaluation."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        repair_result = optional_model_from_state(
            RepairResult, state.get("repair_result")
        )
        if repair_result is None:
            yield Event(author=self.name)
            return

        previous_operations = repair_operations_from_state(state.get("repairs_applied"))
        previous_operations.extend(repair_result.repair_operations)
        unresolved_assumptions = list(state.get("unresolved_assumptions", []))
        unresolved_assumptions.extend(repair_result.unresolved_assumptions)
        repair_iterations = int(state.get("repair_iterations", 0)) + 1

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "candidate_task_graph": model_dump(
                        repair_result.repaired_task_graph
                    ),
                    "repairs_applied": [
                        model_dump(item) for item in previous_operations
                    ],
                    "unresolved_assumptions": list(
                        dict.fromkeys(unresolved_assumptions)
                    ),
                    "requires_user_clarification": repair_result.requires_user_clarification,
                    "repair_iterations": repair_iterations,
                }
            ),
        )


class RepairResultNormalizerAgent(BaseAgent):
    """Converts the live-safe LLM repair draft into the full RepairResult."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        draft = optional_model_from_state(
            LLMRepairResult, _state(ctx).get("repair_result_draft")
        )
        if draft is None:
            yield Event(author=self.name)
            return
        previous_graph = optional_model_from_state(
            CandidateTaskGraph, _state(ctx).get("candidate_task_graph")
        )
        repair_result = normalize_llm_repair_result(draft, previous_graph)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"repair_result": model_dump(repair_result)},
            ),
        )


class RuntimeConfigurationInjectorAgent(BaseAgent):
    """Adds an explicit runtime configuration task when live inputs are missing."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        graph = model_from_state(
            CandidateTaskGraph, _state(ctx)["candidate_task_graph"]
        )
        updated_graph = ensure_runtime_configuration_task(graph)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"candidate_task_graph": model_dump(updated_graph)},
            ),
        )


class ExecutionSchedulerAgent(BaseAgent):
    """Builds an execution schedule from the validated task graph."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        graph = model_from_state(
            CandidateTaskGraph, _state(ctx)["candidate_task_graph"]
        )
        schedule = build_execution_schedule(graph)
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"execution_schedule": model_dump(schedule)},
            ),
        )


class FinalQualityGuardAgent(BaseAgent):
    """Downgrades output if repairs were detected but not applied."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        quality_report = model_from_state(QualityReport, state["quality_report"])
        guarded_report = apply_final_quality_guard(
            quality_report=quality_report,
            initial_graph=model_from_state(
                CandidateTaskGraph, state["initial_task_graph"]
            ),
            final_graph=model_from_state(
                CandidateTaskGraph, state["candidate_task_graph"]
            ),
            repairs_applied=repair_operations_from_state(state.get("repairs_applied")),
            pending_repair_suggestions=list(
                state.get("pending_repair_suggestions", [])
            ),
            requires_user_clarification=bool(state.get("requires_user_clarification")),
        )
        reports = quality_reports_from_state(state.get("quality_reports"))
        if reports:
            reports[-1] = guarded_report
        else:
            reports = [guarded_report]
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "quality_report": model_dump(guarded_report),
                    "quality_reports": [model_dump(report) for report in reports],
                },
            ),
        )


class TraceLoggerAgent(BaseAgent):
    """Builds a durable decomposition trace for future learning."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        goal_state = model_from_state(GoalState, state["goal_state"])
        initial_graph = model_from_state(
            CandidateTaskGraph, state["initial_task_graph"]
        )
        final_graph = model_from_state(
            CandidateTaskGraph, state["candidate_task_graph"]
        )
        quality_report = model_from_state(QualityReport, state["quality_report"])
        trace = DecompositionTrace(
            original_goal=goal_state.raw_goal,
            interpreted_goal=goal_state,
            initial_graph=initial_graph,
            evaluation_reports=quality_reports_from_state(state.get("quality_reports")),
            repairs_applied=repair_operations_from_state(state.get("repairs_applied")),
            final_graph=final_graph,
            unresolved_assumptions=list(state.get("unresolved_assumptions", [])),
            quality_scores=quality_report,
        )
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"decomposition_trace": model_dump(trace)},
            ),
        )


class FinalEmitterAgent(BaseAgent):
    """Emits machine-readable and human-readable TaskSplitter output."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = _state(ctx)
        output = build_task_splitter_output(
            goal_state=model_from_state(GoalState, state["goal_state"]),
            macro_state=model_from_state(MacroState, state["macro_state"]),
            final_graph=model_from_state(
                CandidateTaskGraph, state["candidate_task_graph"]
            ),
            quality_report=model_from_state(QualityReport, state["quality_report"]),
            execution_schedule=model_from_state(
                ExecutionSchedule, state["execution_schedule"]
            ),
            trace=model_from_state(DecompositionTrace, state["decomposition_trace"]),
        )
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=output.human_readable_plan)],
            ),
            actions=EventActions(
                state_delta={
                    "task_splitter_output": model_dump(output),
                    "task_graph": model_dump(output.task_graph),
                    "human_readable_plan": output.human_readable_plan,
                }
            ),
        )


candidate_graph_normalizer_agent = CandidateGraphNormalizerAgent(
    name="candidate_graph_normalizer"
)
initial_graph_snapshot_agent = InitialGraphSnapshotAgent(name="initial_graph_snapshot")
quality_aggregator_agent = QualityAggregatorAgent(name="quality_aggregator")
final_quality_aggregator_agent = QualityAggregatorAgent(name="final_quality_aggregator")
repair_loop_exit_gate = RepairLoopExitGate(name="repair_loop_exit_gate")
repair_result_normalizer_agent = RepairResultNormalizerAgent(
    name="repair_result_normalizer"
)
repair_result_applier_agent = RepairResultApplierAgent(name="repair_result_applier")
runtime_configuration_injector_agent = RuntimeConfigurationInjectorAgent(
    name="runtime_configuration_injector"
)
final_quality_guard_agent = FinalQualityGuardAgent(name="final_quality_guard")
execution_scheduler_agent = ExecutionSchedulerAgent(name="execution_scheduler")
trace_logger_agent = TraceLoggerAgent(name="trace_logger")
final_emitter_agent = FinalEmitterAgent(name="final_emitter")
