"""Runtime configuration for root_deep_web_research."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ResearchConfig:
    """Small, non-secret runtime settings."""

    planner_model: str = os.getenv(
        "ROOT_DEEP_WEB_RESEARCH_PLANNER_MODEL", "gemini-2.5-flash"
    )
    search_model: str = os.getenv(
        "ROOT_DEEP_WEB_RESEARCH_SEARCH_MODEL", "gemini-2.5-flash"
    )
    evaluator_model: str = os.getenv(
        "ROOT_DEEP_WEB_RESEARCH_EVALUATOR_MODEL", "gemini-2.5-flash"
    )
    max_iterations: int = _env_int("ROOT_DEEP_WEB_RESEARCH_MAX_ITERATIONS", 2)
    max_budget_units: int = _env_int("ROOT_DEEP_WEB_RESEARCH_MAX_BUDGET_UNITS", 6)


config = ResearchConfig()
