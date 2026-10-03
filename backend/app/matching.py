import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection

from app.schemas import PetCharacteristics

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CHROMA_PATH = BASE_DIR / "data" / "chroma"
CHARACTERISTIC_WEIGHTS = {
    "species": 0.25,
    "breed": 0.15,
    "colors": 0.20,
    "size": 0.10,
    "markings": 0.20,
    "distinctive_features": 0.10,
}
WEIGHTS = {
    "description": 0.25,
    "visual": 0.25,
    "location": 0.20,
    "date": 0.10,
    "ai": 0.20,
}


def _chroma_path() -> Path:
    path = Path(os.getenv("PETTRACE_CHROMA_PATH", str(DEFAULT_CHROMA_PATH)))
    if not path.is_absolute():
        path = (BASE_DIR.parent / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_document(report: dict[str, Any]) -> str:
    features = ", ".join(
        f"{key}: {', '.join(value) if isinstance(value, list) else value}"
        for key, value in report["characteristics"].items()
        if value
    )
    caption = report.get("caption", "")
    title = report.get("post_title", "")
    return f"{report['description']} {caption} {title} Pet characteristics: {features}"


def initialize_vector_store(reports: list[dict[str, Any]]) -> Collection:
    client = chromadb.PersistentClient(path=str(_chroma_path()))
    collection = client.get_or_create_collection(
        name="pet_reports",
        metadata={"hnsw:space": "cosine"},
    )
    existing_ids = collection.get()["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)
    if reports:
        collection.add(
            ids=[report["id"] for report in reports],
            documents=[_report_document(report) for report in reports],
            metadatas=[
                {
                    "report_type": report["report_type"],
                    "location": report["location"],
                    "source_type": report.get("source_type", "local"),
                }
                for report in reports
            ],
        )
    return collection


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _text_similarity(first: str, second: str) -> float:
    first_tokens = _tokens(first)
    second_tokens = _tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def _value_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def _visual_similarity(
    extracted: PetCharacteristics, report: dict[str, Any]
) -> float:
    requested = extracted.model_dump()
    candidate = report["characteristics"]
    weighted_score = 0.0
    total_weight = 0.0
    for key, weight in CHARACTERISTIC_WEIGHTS.items():
        expected = _value_text(requested.get(key, ""))
        observed = _value_text(candidate.get(key, ""))
        if expected.strip() and observed.strip():
            weighted_score += weight * _text_similarity(expected, observed)
            total_weight += weight
    return weighted_score / total_weight if total_weight else 0.0


def _location_similarity(first: str, second: str) -> float:
    return _text_similarity(first, second)


def _date_similarity(date_lost: date, report_date: Optional[str]) -> float:
    if not report_date:
        return 0.0
    days_apart = abs((date_lost - date.fromisoformat(report_date)).days)
    return max(0.0, 1 - days_apart / 90)


def _explain(
    description_score: float,
    visual_score: float,
    location_score: float,
    date_score: float,
) -> list[str]:
    reasons = []
    if visual_score >= 0.35:
        reasons.append("Pet appearance or characteristics overlap.")
    if description_score >= 0.25:
        reasons.append("The report description is similar to yours.")
    if location_score >= 0.15:
        reasons.append("The location text shares neighborhood or city terms.")
    if date_score >= 0.5:
        reasons.append("The report date is within 45 days of the date lost.")
    if not reasons:
        reasons.append("This was one of the closest reports across the available details.")
    return reasons


def _visual_evidence(
    characteristics: PetCharacteristics, report: dict[str, Any]
) -> list[str]:
    requested = characteristics.model_dump()
    reported = report["characteristics"]
    overlaps = []
    for field in CHARACTERISTIC_WEIGHTS:
        requested_terms = _tokens(_value_text(requested.get(field, "")))
        reported_terms = _tokens(_value_text(reported.get(field, "")))
        overlaps.extend(sorted(requested_terms & reported_terms))
    return overlaps


def rank_reports(
    reports: list[dict[str, Any]],
    description_similarities: dict[str, float],
    characteristics: PetCharacteristics,
    location: str,
    date_lost: date,
    limit: int = 3,
) -> list[dict[str, Any]]:
    ranked = []
    for report in reports:
        description_score = description_similarities.get(report["id"], 0.0)
        visual_score = _visual_similarity(characteristics, report)
        location_score = _location_similarity(location, report["location"])
        date_score = _date_similarity(date_lost, report["report_date"])
        if report.get("date_is_estimated"):
            date_score *= 0.5
        score = (
            WEIGHTS["description"] * description_score
            + WEIGHTS["visual"] * visual_score
            + WEIGHTS["location"] * location_score
            + WEIGHTS["date"] * date_score
        )
        visual_evidence = _visual_evidence(characteristics, report)
        reasons = _explain(
            description_score, visual_score, location_score, date_score
        )
        if visual_evidence:
            reasons.insert(
                0,
                "Shared reported characteristics: "
                + ", ".join(visual_evidence[:6])
                + ".",
            )
        ranked.append(
            {
                "id": report["id"],
                "pet_name": report["pet_name"],
                "report_type": report["report_type"],
                "description": report["description"],
                "location": report["location"],
                "report_date": report["report_date"],
                "score": round(score, 4),
                "description_score": round(description_score, 4),
                "visual_score": round(visual_score, 4),
                "location_score": round(location_score, 4),
                "date_score": round(date_score, 4),
                "ai_score": 0.0,
                "ai_explanation": "AI comparison was not run.",
                "reasons": reasons,
                "source_type": report.get("source_type", "local"),
                "platform": report.get("platform"),
                "profile_name": report.get("profile_name"),
                "post_url": report.get("post_url"),
                "caption": report.get("caption"),
                "image_url": report.get("image_url"),
                "contact_info": report.get("contact_info"),
                "date_is_estimated": report.get("date_is_estimated", False),
                "post_title": report.get("post_title"),
            }
        )
    return sorted(ranked, key=lambda match: match["score"], reverse=True)[:limit]


def apply_ai_assessments(
    matches: list[dict[str, Any]], assessments: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    for match in matches:
        assessment = assessments[match["id"]]
        match["ai_score"] = assessment["similarity_score"]
        match["ai_explanation"] = assessment["explanation"]
        match["score"] = round(
            WEIGHTS["description"] * match["description_score"]
            + WEIGHTS["visual"] * match["visual_score"]
            + WEIGHTS["location"] * match["location_score"]
            + WEIGHTS["date"] * match["date_score"]
            + WEIGHTS["ai"] * match["ai_score"],
            4,
        )
    return sorted(matches, key=lambda match: match["score"], reverse=True)[:3]


def find_matches(
    collection: Collection,
    reports: list[dict[str, Any]],
    query: str,
    characteristics: PetCharacteristics,
    location: str,
    date_lost: date,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if not reports:
        return []
    current_ids = {report["id"] for report in reports}
    indexed_ids = set(collection.get()["ids"])
    stale_ids = indexed_ids - current_ids
    if stale_ids:
        collection.delete(ids=sorted(stale_ids))
    collection.upsert(
        ids=[report["id"] for report in reports],
        documents=[_report_document(report) for report in reports],
        metadatas=[
            {
                "report_type": report["report_type"],
                "location": report.get("location", ""),
                "source_type": report.get("source_type", "local"),
            }
            for report in reports
        ],
    )
    result = collection.query(
        query_texts=[query],
        n_results=len(reports),
        include=["distances"],
    )
    ids = result["ids"][0]
    distances = result["distances"][0]
    similarities = {
        report_id: max(0.0, min(1.0, 1 - distance / 2))
        for report_id, distance in zip(ids, distances)
    }
    return rank_reports(
        reports,
        similarities,
        characteristics,
        location,
        date_lost,
        limit=limit,
    )
