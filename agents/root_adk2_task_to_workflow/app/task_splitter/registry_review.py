from pathlib import Path
from typing import Any

import yaml

from app.task_splitter.schemas import RegistryResource, RegistryReview


def build_registry_review(query: str) -> RegistryReview:
    registry_dir = _repo_root() / "registry"
    if not registry_dir.exists():
        return RegistryReview(
            query=query,
            warnings=["registry directory not found; planning must document that no local reuse review was available"],
        )

    searched_catalogs: list[str] = []
    resources: list[RegistryResource] = []
    warnings: list[str] = []
    query_terms = _terms(query)

    for catalog_path in sorted(registry_dir.rglob("*.yaml")):
        if catalog_path.name in {"schema.yaml", "taxonomy.yaml"}:
            continue
        searched_catalogs.append(str(catalog_path.relative_to(_repo_root())))
        try:
            raw_catalog = yaml.safe_load(catalog_path.read_text()) or {}
        except Exception as exc:
            warnings.append(f"could not read {catalog_path}: {exc}")
            continue

        source_id = str((raw_catalog.get("source") or {}).get("id") or catalog_path.stem)
        for item in raw_catalog.get("items") or []:
            resource = _resource_from_item(source_id, item, query_terms)
            if resource.score > 0:
                resources.append(resource)

    resources.sort(key=lambda item: item.score, reverse=True)
    resources = resources[:8]
    guidance = _reuse_guidance(resources)
    if not resources:
        guidance.append("No strong registry match found; create a new minimal component and register it after implementation.")

    return RegistryReview(
        query=query,
        resources=resources,
        reuse_guidance=guidance,
        searched_catalogs=searched_catalogs,
        warnings=warnings,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _terms(text: str) -> set[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    terms = {term for term in normalized.split() if len(term) >= 3}
    aliases = {
        "adk": {"adk", "workflow", "agent"},
        "workflow": {"workflow", "joinnode", "route", "state", "event"},
        "hitl": {"hitl", "requestinput", "resume"},
        "intencion": {"intent", "route", "router"},
        "intent": {"intent", "route", "router"},
        "registro": {"registry", "resources"},
        "registry": {"registry", "resources"},
    }
    for term in list(terms):
        terms.update(aliases.get(term, set()))
    return terms


def _resource_from_item(
    source_id: str, item: dict[str, Any], query_terms: set[str]
) -> RegistryResource:
    tags = [str(tag) for tag in item.get("tags") or []]
    haystack = " ".join(
        [
            str(item.get("id") or ""),
            str(item.get("name") or ""),
            str(item.get("summary") or ""),
            str(item.get("source") or ""),
            " ".join(tags),
        ]
    ).lower()
    score = sum(1 for term in query_terms if term in haystack)
    if "entity:workflow" in tags:
        score += 1
    if "domain:software-engineering" in tags:
        score += 1
    if str(item.get("maturity")) in {"maturity:adapted", "maturity:productionized"}:
        score += 1

    return RegistryResource(
        id=f"{source_id}:{item.get('id')}",
        name=str(item.get("name") or item.get("id") or "unnamed"),
        source=str(item.get("source") or ""),
        summary=str(item.get("summary") or ""),
        tags=tags,
        maturity=str(item.get("maturity") or "maturity:observed"),
        score=float(score),
    )


def _reuse_guidance(resources: list[RegistryResource]) -> list[str]:
    guidance: list[str] = []
    internal = [item for item in resources if item.source and not item.source.startswith("http")]
    external = [item for item in resources if item.source.startswith("http")]
    if internal:
        guidance.append("Read the closest internal resources before creating new code: " + ", ".join(item.id for item in internal[:4]) + ".")
    if external:
        guidance.append("Use external samples as reference patterns, not as blind copies: " + ", ".join(item.id for item in external[:4]) + ".")
    guidance.append("Prefer adapting existing registry resources over inventing new workflow infrastructure.")
    return guidance
