from google.adk.agents import LoopAgent, ParallelAgent, SequentialAgent

from app.agent import root_agent


def _find_agent(agent: object, name: str) -> object | None:
    if getattr(agent, "name", None) == name:
        return agent
    for child in getattr(agent, "sub_agents", []):
        found = _find_agent(child, name)
        if found is not None:
            return found
    return None


def test_task_splitter_graph_shape() -> None:
    assert isinstance(root_agent, SequentialAgent)
    assert root_agent.name == "task_splitter_workflow"

    repair_loop = _find_agent(root_agent, "repair_loop")
    evaluator = _find_agent(root_agent, "decomposition_evaluator")
    final_evaluator = _find_agent(root_agent, "final_decomposition_evaluator")

    assert isinstance(repair_loop, LoopAgent)
    assert repair_loop.max_iterations == 2
    assert isinstance(evaluator, ParallelAgent)
    assert isinstance(final_evaluator, ParallelAgent)
    assert _find_agent(root_agent, "final_emitter") is not None
