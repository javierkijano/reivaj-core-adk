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
    COVERAGE_CHECKER_PROMPT,
    PROBLEM_DEFINITION_PROMPT,
    VERIFIABILITY_CHECKER_PROMPT,
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
    InteractionActivationContract,
    LLMCandidateTaskGraph,
    LLMDecisionStep,
    LLMInteractionActivationContract,
    LLMProblemDefinition,
    LLMRepairOperation,
    LLMRepairResult,
    LLMRuntimeNodeContract,
    LLMTaskEdge,
    LLMTaskNode,
    MacroState,
    ProblemDefinition,
    QualityReport,
    RepairSuggestion,
    RuntimeNodeContract,
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


def _start_runtime_contract(node_id: str = "planning_node") -> RuntimeNodeContract:
    return RuntimeNodeContract(
        node_id=node_id,
        runtime_boundary_type="start",
        semantic_input="ResearchQuery semantic schema after normalization.",
        adk_runtime_input="google.genai.types.Content",
        recommended_function_signature="def planning_node(node_input: Content):",
        normalization_required=["Content.parts -> str -> ResearchQuery"],
        output_event_contract="Event(output=ResearchPlan)",
        state_keys_written=["research_plan"],
        route_values_emitted=[],
        required_tests=[
            'planning_node(Content(role="user", parts=[Part(text="topic")])) returns Event(output=ResearchPlan)'
        ],
    )


def _intent_gate_runtime_contract(
    node_id: str = "intent_gate_node",
) -> RuntimeNodeContract:
    return RuntimeNodeContract(
        node_id=node_id,
        runtime_boundary_type="start",
        semantic_input="NormalizedUserInput after cheap conversational prechecks.",
        adk_runtime_input="google.genai.types.Content",
        recommended_function_signature="def intent_gate_node(node_input: Content):",
        normalization_required=["Content.parts -> str -> NormalizedUserInput"],
        output_event_contract="Event(route='workflow_request'|'greeting'|'thanks'|'small_talk'|'ambiguous'|'simple_question')",
        state_keys_written=["normalized_user_input", "intent_classification"],
        route_values_emitted=[
            "greeting",
            "thanks",
            "small_talk",
            "ambiguous",
            "simple_question",
            "workflow_request",
        ],
        required_tests=[
            'intent_gate_node(Content(role="user", parts=[Part(text="Hola")])) emits route greeting',
            'intent_gate_node(Content(role="user", parts=[Part(text="Investiga ADK 2.0 Workflow con fuentes")])) emits route workflow_request',
        ],
    )


def _interaction_contract(
    entrypoint_context: str = "general_chat",
) -> InteractionActivationContract:
    return InteractionActivationContract(
        entrypoint_context=entrypoint_context,
        activation_triggers=[
            "investiga",
            "busca fuentes",
            "haz research",
            "compara",
            "analiza en profundidad",
            "consulta la web",
            "prepara un informe",
        ],
        non_activation_inputs=[
            "Hola/greeting",
            "Gracias/thanks",
            "small_talk",
            "empty or whitespace",
            "ambiguous terms such as ADK",
            "standalone si/sí confirmations without context",
        ],
        deterministic_prechecks=[
            "Classify empty, whitespace, greeting, thanks, small_talk and standalone confirmation before any LLM call.",
            "Route clear workflow commands directly to workflow_request when minimum slots are present.",
        ],
        llm_intent_check="Use an LLM classifier only when deterministic rules cannot distinguish direct answer, clarification or workflow_request.",
        minimum_required_slots=[
            "topic",
            "requested action",
            "source/citation requirement for research",
        ],
        clarification_policy=[
            "Ask a brief clarification for ambiguous short inputs such as ADK."
        ],
        direct_response_policy=[
            "Respond to greeting/Hola, thanks/Gracias and small_talk with natural Event(message=...) and no plan."
        ],
        hitl_policy=[
            "Use RequestInput only for sensitive external action, relevant cost/risk, irreversible side effect, low confidence, truly ambiguous scope, or when the user asked to review."
        ],
        expensive_action_policy=[
            "Run tools/providers only after intent_gate emits workflow_request with explicit intent and minimum slots satisfied."
        ],
        required_interaction_tests=[
            'Input "Hola" returns natural Event(message=...) and creates no plan.',
            'Input "Gracias" returns a natural response and does not execute workflow.',
            'Input "" or whitespace asks for useful input without a plan.',
            'Input "ADK" asks clarification and does not execute providers.',
            'Input "Investiga ADK 2.0 Workflow con fuentes" activates planner.',
            "The first node accepts Content.",
            "No RequestInput is emitted before passing intent_gate.",
            "Tools/providers do not execute for greetings, small_talk or ambiguous inputs.",
        ],
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


def test_normalize_llm_task_graph_preserves_runtime_node_contracts() -> None:
    graph = normalize_llm_task_graph(
        LLMCandidateTaskGraph(
            nodes=[_llm_task("t1")],
            runtime_node_contracts=[
                LLMRuntimeNodeContract(
                    node_id="planning_node",
                    runtime_boundary_type="start",
                    semantic_input="ResearchQuery",
                    adk_runtime_input="google.genai.types.Content",
                    recommended_function_signature="def planning_node(node_input: Content):",
                    normalization_required=["Content.parts -> str -> ResearchQuery"],
                    output_event_contract="Event(output=ResearchPlan)",
                    state_keys_written=["research_plan"],
                    route_values_emitted=[],
                    required_tests=["Content input test"],
                )
            ],
        )
    )

    contract = graph.runtime_node_contracts[0]
    assert contract.runtime_boundary_type == "start"
    assert contract.adk_runtime_input == "google.genai.types.Content"
    assert "Content.parts" in contract.normalization_required[0]


def test_normalize_llm_task_graph_preserves_interaction_activation_contract() -> None:
    graph = normalize_llm_task_graph(
        LLMCandidateTaskGraph(
            nodes=[_llm_task("t1")],
            interaction_activation_contract=LLMInteractionActivationContract(
                entrypoint_context="general_chat",
                activation_triggers=["investiga", "busca fuentes"],
                non_activation_inputs=["Hola", "Gracias", "small_talk"],
                deterministic_prechecks=["Handle greetings before any LLM call."],
                llm_intent_check="Classify only ambiguous inputs.",
                minimum_required_slots=["topic"],
                clarification_policy=["Ask when input is ADK."],
                direct_response_policy=["Greeting returns Event(message=...)."],
                hitl_policy=["Only request input for risk/cost/low confidence."],
                expensive_action_policy=["Run providers only after intent_gate."],
                required_interaction_tests=[
                    'Input "Hola" returns natural Event(message=...) and creates no plan.'
                ],
            ),
        )
    )

    contract = graph.interaction_activation_contract
    assert contract is not None
    assert contract.entrypoint_context == "general_chat"
    assert "Hola" in contract.non_activation_inputs


def test_adk2_start_runtime_contract_is_required_for_start_nodes() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to planning_node."
    graph = CandidateTaskGraph(nodes=[task])
    goal_state = GoalState(
        raw_goal="Build ADK 2.0 workflow",
        interpreted_goal="Build ADK 2.0 Workflow with START planning node.",
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=goal_state,
    )

    assert report.status == "needs_repair"
    assert report.graph_validity == "partial"
    assert report.structural_status == "needs_repair"
    assert "missing_start_runtime_input_contract" in report.critical_failures
    assert (
        "coverage:add_start_runtime_input_contract" in report.pending_repair_suggestions
    )


def test_adk2_valid_start_runtime_contract_satisfies_start_check() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to planning_node."
    graph = CandidateTaskGraph(
        nodes=[task], runtime_node_contracts=[_start_runtime_contract()]
    )
    goal_state = GoalState(
        raw_goal="Build ADK 2.0 workflow",
        interpreted_goal="Build ADK 2.0 Workflow with START planning node.",
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=goal_state,
    )

    assert "missing_start_runtime_input_contract" not in report.critical_failures
    assert (
        "coverage:add_start_runtime_input_contract"
        not in report.pending_repair_suggestions
    )


def test_semantic_input_without_adk_runtime_contract_warns() -> None:
    task = _task("planning_node")
    task.description = "PlanningNode receives raw query and returns ResearchQuery."
    graph = CandidateTaskGraph(nodes=[task])

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
    )

    assert "semantic_input_without_adk_runtime_contract" in report.warnings


def test_adk2_interaction_activation_contract_is_required() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to intent_gate_node."
    graph = CandidateTaskGraph(
        nodes=[task], runtime_node_contracts=[_intent_gate_runtime_contract()]
    )
    goal_state = GoalState(
        raw_goal="Build ADK 2.0 workflow",
        interpreted_goal="Build ADK 2.0 Workflow for general chat.",
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=goal_state,
    )

    assert report.status == "needs_repair"
    assert "missing_interaction_activation_contract" in report.critical_failures
    assert "coverage:add_interaction_activation_contract" in (
        report.pending_repair_suggestions
    )


def test_general_chat_start_node_cannot_bypass_intent_gate() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to planning_node."
    graph = CandidateTaskGraph(
        nodes=[task],
        interaction_activation_contract=_interaction_contract(),
        runtime_node_contracts=[_start_runtime_contract("planning_node")],
    )
    goal_state = GoalState(
        raw_goal="Build research workflow",
        interpreted_goal="Build ADK 2.0 Workflow for chat research.",
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=goal_state,
    )

    assert "general_chat_start_node_bypasses_intent_gate" in (report.critical_failures)
    assert "coverage:add_conversation_intent_gate" in (
        report.pending_repair_suggestions
    )


def test_valid_general_chat_activation_contract_passes_activation_checks() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to intent_gate_node for research requests."
    graph = CandidateTaskGraph(
        nodes=[task],
        interaction_activation_contract=_interaction_contract(),
        runtime_node_contracts=[_intent_gate_runtime_contract()],
    )
    goal_state = GoalState(
        raw_goal="Build research workflow",
        interpreted_goal="Build ADK 2.0 Workflow for chat research.",
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=goal_state,
    )

    assert "missing_interaction_activation_contract" not in report.critical_failures
    assert "general_chat_start_node_bypasses_intent_gate" not in (
        report.critical_failures
    )
    assert "missing_conversation_routes:greeting,small_talk,ambiguous" not in (
        report.critical_failures
    )


def test_requestinput_before_intent_gate_needs_repair() -> None:
    task = _task("define_workflow")
    task.description = "Define ADK 2.0 Workflow edge from START to approval_node."
    graph = CandidateTaskGraph(
        nodes=[task],
        interaction_activation_contract=_interaction_contract(),
        runtime_node_contracts=[
            RuntimeNodeContract(
                node_id="approval_node",
                runtime_boundary_type="start",
                semantic_input="User chat input before intent classification.",
                adk_runtime_input="google.genai.types.Content",
                recommended_function_signature="def approval_node(node_input: Content):",
                normalization_required=["Content.parts -> str"],
                output_event_contract="RequestInput(message='Approve plan?')",
                required_tests=["No RequestInput before intent_gate"],
            )
        ],
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=GoalState(
            raw_goal="Build chat workflow",
            interpreted_goal="Build ADK 2.0 Workflow for general chat.",
        ),
    )

    assert "requestinput_before_intent_gate" in report.critical_failures
    assert "coverage:move_hitl_after_intent_gate" in (report.pending_repair_suggestions)


def test_hitl_internal_payload_for_end_user_needs_repair() -> None:
    task = _task("define_workflow")
    task.description = (
        "Define ADK 2.0 Workflow edge from intent_gate_node to hitl_node."
    )
    graph = CandidateTaskGraph(
        nodes=[task],
        interaction_activation_contract=_interaction_contract(),
        runtime_node_contracts=[
            _intent_gate_runtime_contract(),
            RuntimeNodeContract(
                node_id="hitl_node",
                runtime_boundary_type="hitl",
                semantic_input="Approved research scope.",
                adk_runtime_input="Any after intent_gate route workflow_request",
                recommended_function_signature="def hitl_node(node_input: Any, ctx: Context):",
                normalization_required=["ctx.resume_inputs[interrupt_id]"],
                output_event_contract="RequestInput(payload_schema=ApprovedPlan, fields=['approved_plan'])",
                required_tests=["HITL message is natural and brief."],
            ),
        ],
    )

    report = aggregate_quality_report(
        graph=graph,
        coverage=CoverageReport(score=1.0),
        granularity=GranularityReport(score=1.0),
        dependency=DependencyReport(score=1.0),
        executability=ExecutabilityReport(score=1.0),
        verifiability=VerifiabilityReport(score=1.0),
        goal_state=GoalState(
            raw_goal="Build chat workflow",
            interpreted_goal="Build ADK 2.0 Workflow for chat research.",
        ),
    )

    assert "hitl_exposes_internal_payload_to_end_user" in report.critical_failures
    assert "coverage:simplify_user_hitl_message" in (report.pending_repair_suggestions)


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
    final_graph = CandidateTaskGraph(
        nodes=[_task("t_final")],
        interaction_activation_contract=_interaction_contract(),
        runtime_node_contracts=[_start_runtime_contract("planning_node")],
    )
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
    assert "## Interaction Activation Contract" in output.human_readable_plan
    assert "Investiga ADK 2.0 Workflow con fuentes" in output.human_readable_plan
    assert "## Runtime Node Contracts" in output.human_readable_plan
    assert "planning_node" in output.human_readable_plan
    assert "Content.parts -> str -> ResearchQuery" in output.human_readable_plan
    assert output.task_graph.interaction_activation_contract is not None
    assert output.task_graph.runtime_node_contracts[0].node_id == "planning_node"


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
    assert "interaction activation contract" in prompt
    assert "entrypoint_context=general_chat" in prompt
    assert "start -> normalize_user_input -> intent_gate" in prompt
    assert "investiga" in prompt
    assert "hola" in prompt
    assert "no requestinput before" in prompt
    assert "runtime_node_contracts" in prompt
    assert "content.parts -> str" in prompt
    assert "ctx.resume_inputs[interrupt_id]" in prompt


def test_checker_prompts_require_runtime_contracts() -> None:
    coverage_prompt = " ".join(COVERAGE_CHECKER_PROMPT.lower().split())
    verifiability_prompt = " ".join(VERIFIABILITY_CHECKER_PROMPT.lower().split())

    assert "runtime_node_contracts" in coverage_prompt
    assert "semantic input" in coverage_prompt
    assert "adk runtime input" in coverage_prompt
    assert "interaction activation contract" in coverage_prompt
    assert "general_chat starts directly" in coverage_prompt
    assert "planning_node(content" in verifiability_prompt
    assert "branchresult" in verifiability_prompt
    assert "ctx.resume_inputs[interrupt_id]" in verifiability_prompt
    assert '"hola" returns a natural event(message=...)' in verifiability_prompt
    assert "no requestinput is emitted before passing intent_gate" in (
        verifiability_prompt
    )
