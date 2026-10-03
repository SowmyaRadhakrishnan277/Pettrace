from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import main
from app.schemas import (
    CandidateAssessment,
    CandidateAssessmentResponse,
    PetCharacteristics,
)
from app.public_discovery import PublicDiscoveryResult


def test_matches_returns_live_public_result_and_notice(monkeypatch) -> None:
    report_date = (date.today() - timedelta(days=1)).isoformat()
    candidate = {
        "id": "web-test-001",
        "pet_name": "",
        "report_type": "found",
        "description": "Found a black and white cat near Oakwood.",
        "location": "",
        "report_date": report_date,
        "characteristics": PetCharacteristics().model_dump(),
        "source_type": "public",
        "platform": "Facebook",
        "profile_name": None,
        "post_title": "Found black and white cat",
        "post_url": "https://www.facebook.com/groups/pets/posts/1",
        "caption": "Found a black and white cat near Oakwood.",
        "image_url": None,
        "contact_info": None,
        "date_is_estimated": True,
    }

    class StubPublicSource:
        async def search(self, **kwargs):
            return PublicDiscoveryResult(
                reports=[candidate],
                notice="Live public pages indexed by Serper.",
            )

    monkeypatch.setattr(main, "initialize_database", lambda: None)
    monkeypatch.setattr(main, "get_reports", lambda: [])
    monkeypatch.setattr(main, "initialize_vector_store", lambda reports: object())
    monkeypatch.setattr(main, "public_report_source", StubPublicSource())
    monkeypatch.setattr(
        main,
        "extract_characteristics",
        lambda image, mime_type, description: PetCharacteristics(species="cat"),
    )
    monkeypatch.setattr(
        main,
        "find_matches",
        lambda *args, **kwargs: [
            {
                "id": candidate["id"],
                "pet_name": "",
                "report_type": "found",
                "description": candidate["description"],
                "location": "",
                "report_date": report_date,
                "score": 0.7,
                "description_score": 0.8,
                "visual_score": 0.2,
                "location_score": 0.0,
                "date_score": 0.9,
                "ai_score": 0.0,
                "ai_explanation": "Not compared.",
                "reasons": ["Description terms overlap."],
                "source_type": "public",
                "platform": "Facebook",
                "profile_name": None,
                "post_url": candidate["post_url"],
                "caption": candidate["caption"],
                "image_url": None,
                "contact_info": None,
                "date_is_estimated": True,
                "post_title": candidate["post_title"],
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "compare_candidates",
        lambda *args: CandidateAssessmentResponse(
            assessments=[
                CandidateAssessment(
                    report_id=candidate["id"],
                    similarity_score=0.8,
                    explanation="The indexed caption describes a black-and-white cat.",
                )
            ]
        ),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/matches",
            files={"pet_image": ("pet.png", b"image-bytes", "image/png")},
            data={
                "description": "Black and white cat with a white chest",
                "location": "Oakwood Seattle",
                "date_lost": report_date,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matches"][0]["platform"] == "Facebook"
    assert payload["matches"][0]["post_url"] == candidate["post_url"]
    assert "indexed by Serper" in payload["notice"]
    assert "not an identification" in payload["notice"]
