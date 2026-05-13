from google.adk.agents import LoopAgent, SequentialAgent

from app.agent import APP_NAME, app, root_agent
from app.task_splitter.workflow_agents import TaskSplitterWorkflowAgent


def _find_agent(agent: object, name: str) -> object | None:
    if getattr(agent, "name", None) == name:
        return agent
    for child in getattr(agent, "sub_agents", []):
        found = _find_agent(child, name)
        if found is not None:
            return found
    return None


def test_task_splitter_graph_shape() -> None:
    assert APP_NAME == "root_adk_task_to_workflow"
    assert app.name == APP_NAME
    assert isinstance(root_agent, TaskSplitterWorkflowAgent)
    assert root_agent.name == "task_splitter_workflow"
    assert root_agent.definition_agent_count == 2
    assert getattr(root_agent.sub_agents[0], "name", None) == "problem_definition_agent"
    assert getattr(root_agent.sub_agents[1], "name", None) == (
        "problem_definition_normalizer"
    )
    assert getattr(root_agent.sub_agents[2], "name", None) == "goal_interpreter"

    repair_loop = _find_agent(root_agent, "repair_loop")
    evaluator = _find_agent(root_agent, "decomposition_evaluator")
    final_evaluator = _find_agent(root_agent, "final_decomposition_evaluator")

    assert isinstance(repair_loop, LoopAgent)
    assert repair_loop.max_iterations == 2
    assert isinstance(evaluator, SequentialAgent)
    assert isinstance(final_evaluator, SequentialAgent)
    assert _find_agent(root_agent, "final_emitter") is not None
