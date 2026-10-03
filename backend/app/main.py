from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.ai import AIServiceError, compare_candidates, extract_characteristics
from app.database import get_reports, initialize_database
from app.matching import apply_ai_assessments, find_matches, initialize_vector_store
from app.public_discovery import (
    PublicReportDiscoveryError,
    get_public_report_source,
)
from app.schemas import MatchResponse

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env.local", override=True)

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

app = FastAPI(title="PetTrace API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
vector_collection = None
public_report_source = get_public_report_source()


@app.on_event("startup")
def startup() -> None:
    global vector_collection
    initialize_database()
    vector_collection = initialize_vector_store(get_reports())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/matches", response_model=MatchResponse)
async def matches(
    pet_image: UploadFile = File(...),
    description: str = Form(..., min_length=5, max_length=1000),
    location: str = Form(..., min_length=2, max_length=160),
    date_lost: date = Form(...),
) -> MatchResponse:
    if pet_image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPEG, PNG, or WEBP image.",
        )
    image_bytes = await pet_image.read(MAX_IMAGE_SIZE + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    if date_lost > date.today():
        raise HTTPException(status_code=422, detail="Date lost cannot be in the future.")

    try:
        characteristics = extract_characteristics(
            image_bytes,
            pet_image.content_type or "image/jpeg",
            description,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    local_reports = get_reports()
    try:
        discovery = await public_report_source.search(
            query=description,
            location=location,
            date_lost=date_lost,
            characteristics=characteristics,
        )
    except PublicReportDiscoveryError as error:
        discovery = None
        discovery_notice = (
            f"Live public search is unavailable: {error} Only local reports were searched."
        )
    else:
        discovery_notice = discovery.notice
    public_reports = discovery.reports if discovery else []
    reports = local_reports + public_reports
    query = (
        f"{description}. Pet traits: "
        f"{characteristics.model_dump_json(exclude_defaults=True)}"
    )
    if vector_collection is None:
        raise HTTPException(status_code=503, detail="The local search index is unavailable.")
    ranked = find_matches(
        vector_collection,
        reports,
        query,
        characteristics,
        location,
        date_lost,
        limit=10,
    )
    try:
        candidate_ids = {match["id"] for match in ranked}
        candidate_reports = [
            report for report in reports if report["id"] in candidate_ids
        ]
        ai_comparisons = compare_candidates(
            image_bytes,
            pet_image.content_type or "image/jpeg",
            description,
            characteristics,
            candidate_reports,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AIServiceError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    assessments = {
        assessment.report_id: assessment.model_dump()
        for assessment in ai_comparisons.assessments
    }
    ranked = apply_ai_assessments(ranked, assessments)
    return MatchResponse(
        matches=ranked,
        notice=(
            "Potential matches only; AI similarity is indicative, not an "
            "identification. Verify the original post, image, location, and "
            "identifying details manually. Azure OpenAI compared the uploaded "
            "image and extracted traits with public result text; candidate "
            "post images are not supplied by this search. "
            f"{discovery_notice}"
        ),
    )
