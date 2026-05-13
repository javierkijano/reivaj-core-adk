from app.task_splitter.logic import (
    aggregate_quality_report,
    apply_final_quality_guard,
    build_execution_schedule,
    build_task_splitter_output,
    ensure_runtime_configuration_task,
    normalize_llm_problem_definition,
    normalize_llm_repair_result,
    normalize_llm_task_graph,
    render_problem_definition_stop_message,
    should_stop_before_task_splitter,
)
from app.task_splitter.prompts import (
    CANDIDATE_TASK_PLANNER_PROMPT,
    PROBLEM_DEFINITION_PROMPT,
)
from app.task_splitter.schemas import (
    CandidateTaskGraph,
    Condition,
    CoverageReport,
    DecisionStep,
    DecompositionTrace,
    DependencyReport,
    ExecutabilityReport,
    ExecutionSchedule,
    ExecutorSpec,
    GoalState,
    GranularityReport,
    LLMCandidateTaskGraph,
    LLMDecisionStep,
    LLMProblemDefinition,
    LLMRepairOperation,
    LLMRepairResult,
    LLMTaskEdge,
    LLMTaskNode,
    MacroState,
    ProblemDefinition,
    QualityReport,
    RepairSuggestion,
    TaskDecomposition,
    TaskDependencies,
    TaskEdge,
    TaskExecution,
    TaskNode,
    TaskRisk,
    VerifiabilityReport,
    VerifierSpec,
    WeakPostcondition,
)


def _condition(condition_id: str, text: str) -> Condition:
    return Condition(
        id=condition_id,
        condition=text,
        evaluator_type="schema",
        evaluator_instruction=f"Verify {text}",
        observable=True,
        confidence_threshold=0.9,
    )


def _task(task_id: str, requires: list[str] | None = None) -> TaskNode:
    return TaskNode(
        id=task_id,
        title=f"Task {task_id}",
        description=f"Transition state for {task_id}.",
        action_type="design",
        abstraction_level="meso",
        input_state=["input_ready"],
        output_state=[f"{task_id}_done"],
        preconditions=[_condition(f"pre_{task_id}", "input is available")],
        postconditions=[_condition(f"post_{task_id}", f"{task_id} output exists")],
        executor=ExecutorSpec(
            type="agent",
            id="planner_agent",
            required_inputs=["input_ready"],
            expected_outputs=[f"{task_id}_done"],
        ),
        verifier=VerifierSpec(
            type="schema_validation",
            instruction=f"Validate {task_id} output schema.",
            success_threshold=0.9,
            failure_action="replan",
        ),
        acceptance_criteria=[f"{task_id} output is present and valid"],
        dependencies=TaskDependencies(requires=requires or []),
        execution=TaskExecution(
            mode="parallel_candidate" if requires else "sequential"
        ),
        decomposition=TaskDecomposition(
            can_expand=True,
            should_expand_now=False,
            expansion_reason=None,
            compressed_subgraph_ref=None,
        ),
        risk=TaskRisk(
            level="medium", reasons=["Planning quality affects downstream work"]
        ),
    )


def _edge(from_task: str, to: str, edge_type: str, reason: str) -> TaskEdge:
    return TaskEdge.model_validate(
        {"from": from_task, "to": to, "type": edge_type, "reason": reason}
    )


def _llm_task(
    task_id: str,
    dependencies: list[str] | None = None,
    missing_runtime_inputs: list[str] | None = None,
    execution_mode: str = "sequential",
    parallel_group: str | None = None,
) -> LLMTaskNode:
    return LLMTaskNode(
        id=task_id,
        title=f"Task {task_id}",
        description=f"Build {task_id}.",
        action_type="build",
        abstraction_level="meso",
        input_state=["input_ready"],
        output_state=[f"{task_id}_done"],
        preconditions=["input is available"],
        postconditions=[f"{task_id} output exists"],
        executor_type="agent",
        executor_id="builder_agent",
        verifier_type="test",
        verifier_instruction=f"Test {task_id}.",
        acceptance_criteria=[f"{task_id} passes tests"],
        dependencies=dependencies or [],
        execution_mode=execution_mode,
        parallel_group=parallel_group,
        execution_status="executable",
        missing_runtime_inputs=missing_runtime_inputs or [],
        can_expand=True,
        should_expand_now=False,
        risk_level="medium",
        risk_reasons=["External integration risk"],
    )


def _problem_definition(
    *,
    requires_decomposition: bool = True,
    should_invoke_task_splitter: bool = True,
    approval_state: str = "sufficient_confidence",
) -> ProblemDefinition:
    return ProblemDefinition(
        input_classification="workflow_design_goal"
        if requires_decomposition
        else "greeting",
        requires_decomposition=requires_decomposition,
        should_invoke_task_splitter=should_invoke_task_splitter,
        approval_state=approval_state,
        confidence=0.91,
        process_explanation="Define the problem, resolve important decisions, then split it.",
        reformulated_problem="Design an ADK 2.0 graph-based workflow.",
        initial_exploration=["The request targets ADK 2.0 planning."],
        subtopics=["Workflow graph", "Schemas", "Tests"],
        approaches=["Use explicit graph routes and JoinNode."],
        sources=["reivaj-adk-2.0-development"],
        available_tools=["ADK 2.0 Workflow", "pytest"],
        missing_tools=[],
        ambiguities=["Deployment target is not required for planning."],
        decision_steps=[
            DecisionStep(
                id="D1",
                decision="Use graph-based Workflow by default?",
                reason="It is the primary ADK 2.0 orchestration pattern.",
                impact="Controls implementation architecture.",
                default_value="Si",
                recommended_resolver="auto",
                blocking=False,
                auto_resolution_criterion="The user requested ADK 2.0 planning.",
                selected_value="Si",
            )
        ],
        auto_resolved_decisions=["Use graph-based Workflow by default."],
        important_escalations=[],
        brief_plan=["Create graph contract", "Define nodes", "Add tests"],
        task_splitter_goal="Plan an ADK 2.0 graph-based Workflow implementation.",
        direct_response="No task split is required.",
        approval_request="Approve or choose Elaborar plan.",
    )


def test_problem_definition_gate_stops_simple_inputs() -> None:
    problem_definition = _problem_definition(
        requires_decomposition=False,
        should_invoke_task_splitter=False,
        approval_state="not_required",
    )

    assert should_stop_before_task_splitter(problem_definition) is True
    assert render_problem_definition_stop_message(problem_definition) == (
        "No task split is required."
    )


def test_problem_definition_gate_stops_for_requested_approval() -> None:
    problem_definition = _problem_definition(
        should_invoke_task_splitter=True,
        approval_state="requested",
    )

    message = render_problem_definition_stop_message(problem_definition)

    assert should_stop_before_task_splitter(problem_definition) is True
    assert "# Problem Definition Checkpoint" in message
    assert "Use graph-based Workflow by default?" in message
    assert "Approve or choose Elaborar plan." in message


def test_problem_definition_gate_stops_with_sufficient_confidence() -> None:
    problem_definition = _problem_definition()

    assert should_stop_before_task_splitter(problem_definition) is True


def test_problem_definition_gate_continues_after_explicit_approval() -> None:
    approved = _problem_definition(approval_state="approved")
    design_selected = _problem_definition(approval_state="design_workflow_selected")

    assert should_stop_before_task_splitter(approved) is False
    assert should_stop_before_task_splitter(design_selected) is False


def test_normalize_llm_problem_definition_sanitizes_choices() -> None:
    problem_definition = normalize_llm_problem_definition(
        LLMProblemDefinition(
            input_classification="unknown_kind",
            requires_decomposition=True,
            should_invoke_task_splitter=True,
            approval_state="unexpected_state",
            confidence=0.8,
            process_explanation="Define then split.",
            reformulated_problem="Build an ADK workflow planner.",
            initial_exploration=["ADK 2.0 is the target."],
            subtopics=["Graph"],
            approaches=["Static routes"],
            sources=["Skill guidance"],
            available_tools=["pytest"],
            missing_tools=[],
            ambiguities=[],
            decision_steps=[
                LLMDecisionStep(
                    id="D1",
                    decision="Use graph workflow?",
                    reason="Primary pattern.",
                    impact="Controls architecture.",
                    options=[],
                    default_value="Si",
                    recommended_resolver="invalid",
                    blocking=False,
                    auto_resolution_criterion="ADK 2.0 requested.",
                    selected_value="",
                    resolution_reason="",
                )
            ],
            auto_resolved_decisions=[],
            important_escalations=[],
            brief_plan=[],
            task_splitter_goal="Plan a graph-based workflow.",
            direct_response="",
            approval_request="",
        )
    )

    assert problem_definition.input_classification == "broad_goal"
    assert problem_definition.approval_state == "requested"
    assert problem_definition.decision_steps[0].recommended_resolver == "auto"
    assert problem_definition.decision_steps[0].options == [
        "Si",
        "No",
        "Respuesta personalizada",
        "Elaborar plan",
    ]


def test_problem_definition_agent_uses_live_safe_schema() -> None:
    from app.agent import problem_definition_agent

    assert problem_definition_agent.output_key == "problem_definition_draft"
    assert problem_definition_agent.output_schema is LLMProblemDefinition


def test_build_execution_schedule_groups_independent_ready_tasks() -> None:
    graph = CandidateTaskGraph(
        nodes=[
            _task("T1"),
            _task("T2", ["T1"]),
            _task("T3", ["T1"]),
            _task("T4", ["T2", "T3"]),
        ],
        edges=[
            _edge("T1", "T2", "enables", "T1 enables T2"),
            _edge("T1", "T3", "enables", "T1 enables T3"),
            _edge("T2", "T4", "integrates", "T4 integrates T2"),
            _edge("T3", "T4", "integrates", "T4 integrates T3"),
        ],
    )

    schedule = build_execution_schedule(graph)

    assert [(phase.mode, phase.tasks) for phase in schedule.phases] == [
        ("sequential", ["T1"]),
        ("parallel", ["T2", "T3"]),
        ("sequential", ["T4"]),
    ]
    assert schedule.phases[1].convergence_task == "T4"
    assert schedule.warnings == []


def test_build_execution_schedule_reports_dependency_violations() -> None:
    graph = CandidateTaskGraph(
        nodes=[_task("A", ["B"]), _task("B", ["A"])],
        edges=[
            _edge("A", "B", "requires_output", "B requires A"),
            _edge("B", "A", "requires_output", "A requires B"),
        ],
    )

    schedule = build_execution_schedule(graph)

    assert any("Schedule dependency violation" in item for item in schedule.warnings)


def test_aggregate_quality_report_applies_weighting_and_structural_failures() -> None:
    graph = CandidateTaskGraph(nodes=[_task("T1")])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=0.8),
        granularity=GranularityReport(score=0.7),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=0.6),
        verifiability=VerifiabilityReport(score=0.9),
    )

    assert report.overall_score == 0.795
    assert report.critical_failures == []


def test_aggregate_quality_report_blocks_missing_postconditions() -> None:
    task = _task("T1")
    task.postconditions = []
    graph = CandidateTaskGraph(nodes=[task])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
    )

    assert "Task T1 has no postcondition." in report.critical_failures


def test_missing_goal_elements_force_needs_repair_and_score_cap() -> None:
    graph = CandidateTaskGraph(nodes=[_task("T1")])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(
            score=0.88,
            missing_goal_elements=["Research Planner"],
            repair_suggestions=[
                RepairSuggestion(
                    target="task_graph",
                    operation="add_task",
                    reason="Research planning is core to auditability.",
                    suggested_change="Add a Research Planner task.",
                )
            ],
        ),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
    )

    assert report.status == "needs_repair"
    assert report.graph_validity == "partial"
    assert report.must_apply_repairs_before_execution is True
    assert report.overall_score <= 0.84
    assert any("Research Planner" in item for item in report.critical_failures)


def test_final_quality_guard_blocks_unapplied_repairs() -> None:
    graph = CandidateTaskGraph(nodes=[_task("T1")])
    quality_report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
    )

    guarded_report = apply_final_quality_guard(
        quality_report=quality_report,
        initial_graph=graph,
        final_graph=graph,
        repairs_applied=[],
        pending_repair_suggestions=["coverage:add_task:research_planner"],
        requires_user_clarification=False,
    )

    assert guarded_report.status == "needs_repair"
    assert guarded_report.overall_score <= 0.75
    assert "repairs_detected_but_not_applied" in guarded_report.critical_failures


def test_aggregate_quality_report_filters_stale_node_diagnostics() -> None:
    graph = CandidateTaskGraph(nodes=[_task("t2b_google_adapter")])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(
            score=0.9,
            tasks_to_split=["t2b_implement_api_adapters", "t2b_google_adapter"],
            repair_suggestions=[
                RepairSuggestion(
                    target="t2b_implement_api_adapters",
                    operation="split_task",
                    reason="Old combined adapter task was too broad.",
                    suggested_change="Split provider adapters.",
                ),
                RepairSuggestion(
                    target="t2b_google_adapter",
                    operation="add_verifier",
                    reason="Current adapter needs a stronger verifier.",
                    suggested_change="Add an integration test verifier.",
                ),
            ],
        ),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(
            score=0.9,
            weak_postconditions=[
                WeakPostcondition(
                    task_id="t2b_implement_api_adapters",
                    postcondition="Adapters work",
                    problem="Stale pre-repair node.",
                ),
                WeakPostcondition(
                    task_id="t2b_google_adapter",
                    postcondition="Google adapter is tested",
                    problem="Needs a concrete test assertion.",
                ),
            ],
        ),
    )

    final_diagnostics = "\n".join(
        [*report.warnings, *report.pending_repair_suggestions]
    )
    assert "t2b_implement_api_adapters" not in final_diagnostics
    assert "t2b_google_adapter" in final_diagnostics


def test_runtime_inputs_block_runtime_without_structural_repair() -> None:
    task = _task("t2b_exa_adapter")
    task.execution.missing_runtime_inputs = ["Search API keys (Exa)"]
    task.execution.execution_status = "blocked_by_runtime_inputs"
    task.execution.runtime_status = "blocked_by_runtime_inputs"
    graph = CandidateTaskGraph(nodes=[task])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(
            score=0.9,
            conditionally_executable_tasks=["t2b_exa_adapter"],
            missing_runtime_inputs=["Search API keys (Exa)"],
        ),
        verifiability=VerifiabilityReport(score=1.0),
    )

    assert report.status == "blocked_by_runtime_inputs"
    assert report.runtime_status == "blocked_by_runtime_inputs"
    assert report.must_apply_repairs_before_execution is False
    assert report.must_provide_runtime_inputs_before_execution is True
    assert not any(
        item.startswith("executability:missing_runtime_input")
        for item in report.pending_repair_suggestions
    )


def test_normalize_llm_task_graph_blocks_nodes_with_missing_runtime_inputs() -> None:
    graph = normalize_llm_task_graph(
        LLMCandidateTaskGraph(
            nodes=[
                _llm_task(
                    "t2b_exa_adapter",
                    missing_runtime_inputs=["Search API keys (Exa)"],
                )
            ]
        )
    )

    assert graph.nodes[0].execution.execution_status == "blocked_by_runtime_inputs"
    assert graph.nodes[0].execution.build_status == "executable"
    assert graph.nodes[0].execution.runtime_status == "blocked_by_runtime_inputs"
    assert graph.nodes[0].execution.runtime_execution_mode == "either"


def test_normalize_llm_task_graph_clears_parallel_group_for_sequential_tasks() -> None:
    graph = normalize_llm_task_graph(
        LLMCandidateTaskGraph(
            nodes=[_llm_task("t1", execution_mode="sequential", parallel_group="group")]
        )
    )

    assert graph.nodes[0].execution.mode == "sequential"
    assert graph.nodes[0].execution.parallel_group is None


def test_ensure_runtime_configuration_task_adds_secret_setup_dependency() -> None:
    task = _task("t2b_exa_adapter")
    task.execution.missing_runtime_inputs = ["Search API keys (Exa)"]
    graph = CandidateTaskGraph(nodes=[task])

    updated = ensure_runtime_configuration_task(graph)
    config_task = updated.nodes[0]
    adapter_task = next(task for task in updated.nodes if task.id == "t2b_exa_adapter")

    assert config_task.id == "t0_configure_runtime_environment"
    assert "Secrets are not committed" in config_task.acceptance_criteria
    assert config_task.execution.runtime_status == "not_applicable"
    assert "t0_configure_runtime_environment" in adapter_task.dependencies.requires
    assert adapter_task.execution.execution_status == "blocked_by_runtime_inputs"
    assert adapter_task.execution.runtime_status == "blocked_by_runtime_inputs"
    assert any(
        edge.from_task == "t0_configure_runtime_environment"
        and edge.to == "t2b_exa_adapter"
        for edge in updated.edges
    )


def test_normalize_llm_repair_result_records_graph_mutations() -> None:
    previous_graph = CandidateTaskGraph(nodes=[_task("t2_build_search_adapters")])
    repair_result = normalize_llm_repair_result(
        LLMRepairResult(
            repaired_task_graph=LLMCandidateTaskGraph(
                nodes=[
                    _llm_task("t2a_build_search_normalization"),
                    _llm_task(
                        "t2b_google_adapter",
                        dependencies=["t2a_build_search_normalization"],
                    ),
                    _llm_task(
                        "t2b_exa_adapter",
                        dependencies=["t2a_build_search_normalization"],
                    ),
                ],
                edges=[
                    LLMTaskEdge(
                        source="t2a_build_search_normalization",
                        target="t2b_google_adapter",
                        type="requires_output",
                        reason="Provider adapters consume normalized search contracts.",
                    )
                ],
            ),
            repair_operations=[
                LLMRepairOperation(
                    operation="split_task",
                    target="t2_build_search_adapters",
                    reason="Provider adapters need independent implementation and tests.",
                    suggested_change="Split search adapter work by provider.",
                )
            ],
        ),
        previous_graph=previous_graph,
    )

    operation = repair_result.repair_operations[0]
    assert operation.removed_task_ids == ["t2_build_search_adapters"]
    assert operation.added_task_ids == [
        "t2a_build_search_normalization",
        "t2b_exa_adapter",
        "t2b_google_adapter",
    ]
    assert operation.added_nodes
    assert operation.removed_nodes
    assert operation.added_edges
    assert operation.repair_id == "repair_001"
    assert operation.before_snapshot
    assert operation.after_snapshot
    assert operation.modified_fields
    assert operation.validation_after_repair == "passed"
    assert operation.validation["graph_valid_after_repair"] is True


def test_final_emitter_plan_uses_only_final_graph_nodes() -> None:
    goal_state = GoalState(
        raw_goal="Build a planner",
        interpreted_goal="Build a planner",
    )
    macro_state = MacroState(
        task_family="implementation",
        ambiguity_level="low",
        risk_level="medium",
    )
    final_graph = CandidateTaskGraph(nodes=[_task("t_final")])
    quality_report = QualityReport(
        coverage_score=1.0,
        granularity_score=1.0,
        dependency_score=1.0,
        executability_score=1.0,
        verifiability_score=1.0,
        overall_score=1.0,
    )
    trace = DecompositionTrace(
        original_goal="Build a planner",
        interpreted_goal=goal_state,
        initial_graph=CandidateTaskGraph(nodes=[_task("t_old")]),
        evaluation_reports=[
            quality_report.model_copy(update={"warnings": ["Task should split: t_old"]})
        ],
        repairs_applied=[],
        final_graph=final_graph,
        quality_scores=quality_report,
    )

    output = build_task_splitter_output(
        goal_state=goal_state,
        macro_state=macro_state,
        final_graph=final_graph,
        quality_report=quality_report,
        execution_schedule=ExecutionSchedule(),
        trace=trace,
        problem_definition=_problem_definition(),
    )

    assert "t_final" in output.human_readable_plan
    assert "t_old" not in output.human_readable_plan
    assert [task.id for task in output.task_graph.nodes] == ["t_final"]
    assert "# ADK 2.0 Workflow Implementation Plan" in output.human_readable_plan
    assert "## Initial Problem Definition" in output.human_readable_plan
    assert "graph-based `Workflow`" in output.human_readable_plan
    assert "collaborative agents and dynamic workflows" in output.human_readable_plan


def test_planner_prompt_keeps_domain_agnostic_systems_configurable() -> None:
    prompt = " ".join(CANDIDATE_TASK_PLANNER_PROMPT.lower().split())

    assert "domain-agnostic research" in prompt
    assert "profile registry" in prompt
    assert "provider abstraction layer" in prompt
    assert "evidence schema" in prompt
    assert "output format registry" in prompt
    assert "not as hard-coded core architecture" in prompt


def test_problem_definition_prompt_controls_task_splitter_invocation() -> None:
    prompt = " ".join(PROBLEM_DEFINITION_PROMPT.lower().split())

    assert "mandatory front door before any tasksplitter" in prompt
    assert "should_invoke_task_splitter=false" in prompt
    assert "approval_state=requested" in prompt
    assert "3 to 5 useful decision_steps" in prompt
    assert "do not ask decorative questions" in prompt
    assert "approval_state=approved" in prompt
    assert "design_workflow_selected" in prompt
    assert "graph-based workflows first" in prompt


def test_planner_prompt_defaults_to_adk2_graph_based_workflows() -> None:
    prompt = " ".join(CANDIDATE_TASK_PLANNER_PROMPT.lower().split())

    assert "adk 2.0 graph-based workflow" in prompt
    assert "explicit workflow graphs" in prompt
    assert "joinnode" in prompt
    assert "event(output=...)" in prompt
    assert "do not use collaborative agents or dynamic workflows by default" in prompt
