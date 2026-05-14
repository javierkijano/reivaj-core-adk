"""Pydantic contracts for the deep web research workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentLabel = Literal[
    "greeting",
    "thanks",
    "small_talk",
    "simple_question",
    "ambiguous",
    "direct_qa",
    "new_research",
]
ConfidenceLabel = Literal["low", "medium", "high"]
ApprovalStatus = Literal["approved", "rejected", "revise"]
LimitRoute = Literal["execute_search", "limit_reached"]
QualityRoute = Literal["continue", "synthesize"]
ProviderName = Literal["google_search", "provider_status"]
ProviderStatus = Literal["ok", "error", "skipped"]


class NormalizedInput(BaseModel):
    original_text: str
    normalized_text: str
    source: Literal["content", "event", "mapping", "string", "unknown"]


class IntentDecision(BaseModel):
    label: IntentLabel
    text: str
    confidence: ConfidenceLabel
    reason: str


class ResearchRequest(BaseModel):
    topic: str
    original_text: str
    feedback: str = ""


class ResearchPlan(BaseModel):
    topic: str
    rationale: str
    search_queries: list[str] = Field(min_length=1, max_length=8)
    selected_providers: list[Literal["google_search"]] = Field(
        default_factory=lambda: ["google_search"]
    )
    max_iterations: int = Field(default=2, ge=1, le=5)
    max_budget_units: int = Field(default=6, ge=1, le=20)
    human_summary: str


class ApprovalDecision(BaseModel):
    status: ApprovalStatus
    feedback: str = ""


class LimitCheckResult(BaseModel):
    route: LimitRoute
    current_iteration: int
    max_iterations: int
    budget_used: int
    max_budget_units: int
    reason: str


class SearchBatch(BaseModel):
    topic: str
    iteration: int
    queries: list[str] = Field(min_length=1, max_length=8)
    provider: Literal["google_search"] = "google_search"


class SourceCitation(BaseModel):
    title: str = "Untitled source"
    url: str


class ProviderSearchResult(BaseModel):
    provider: ProviderName
    query: str
    summary: str
    citations: list[SourceCitation] = Field(default_factory=list)
    status: ProviderStatus = "ok"
    error: str = ""


class BranchResult(BaseModel):
    branch_id: str
    provider: ProviderName
    status: ProviderStatus
    results: list[ProviderSearchResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ResearchFindings(BaseModel):
    topic: str
    iteration: int
    results: list[ProviderSearchResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    budget_used: int


class QualityAssessment(BaseModel):
    route: QualityRoute
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    gaps: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list, max_length=8)


class FinalResearchReport(BaseModel):
    topic: str
    report: str
    citations: list[SourceCitation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    iterations: int
    budget_used: int
