import tomllib
from pathlib import Path

from google.adk import Workflow
from google.adk.apps import App
from google.adk.workflow import JoinNode

from app.agent import (
    APP_NAME,
    app,
    quality_join,
    root_agent,
    structured_intent_classifier,
)
from app.task_splitter.schemas import IntentDecision

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _flatten_edges() -> list[object]:
    return [part for edge in root_agent.edges for part in edge]


def test_root_agent_is_adk2_workflow() -> None:
    assert isinstance(root_agent, Workflow)
    assert root_agent.name == "root_adk2_task_to_workflow"
    assert any(edge and edge[0] == "START" for edge in root_agent.edges)
    assert isinstance(quality_join, JoinNode)


def test_app_entrypoint_matches_agents_cli_contract() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    agent_directory = pyproject["tool"]["agents-cli"]["agent_directory"]

    assert APP_NAME == agent_directory
    assert isinstance(app, App)
    assert app.name == agent_directory
    assert app.root_agent is root_agent


def test_adk_web_parent_directory_entrypoint_exports_only_root_agent() -> None:
    entrypoint = PROJECT_ROOT / "agent.py"
    source = entrypoint.read_text()

    assert entrypoint.exists()
    assert "from app.agent import root_agent" in source
    assert "__all__ = [\"root_agent\"]" in source
    assert "from app.agent import app" not in source


def test_intent_classifier_is_structured_llm_node() -> None:
    assert structured_intent_classifier.name == "structured_intent_classifier"
    assert structured_intent_classifier.output_schema is IntentDecision
    assert "LLM" in structured_intent_classifier.instruction or "classifier" in structured_intent_classifier.instruction


def test_graph_contains_front_door_before_planner() -> None:
    parts = _flatten_edges()
    names = [getattr(part, "__name__", getattr(part, "name", str(part))) for part in parts]

    normalize_index = names.index("normalize_user_input")
    classifier_index = names.index("structured_intent_classifier")
    router_index = names.index("intent_router")
    registry_index = names.index("registry_review_node")
    planner_index = names.index("workflow_planner_agent")

    assert normalize_index < classifier_index < router_index
    assert registry_index < planner_index


def test_route_dictionary_contains_natural_routes_and_workflow_request() -> None:
    route_edges = [
        edge
        for edge in root_agent.edges
        if edge and getattr(edge[0], "__name__", "") == "intent_router"
    ]
    assert route_edges
    routes = route_edges[0][1]

    assert set(routes) == {
        "greeting",
        "thanks",
        "small_talk",
        "simple_question",
        "ambiguous",
        "workflow_request",
    }
    assert routes["workflow_request"].__name__ == "registry_review_node"
