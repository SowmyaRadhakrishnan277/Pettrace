from datetime import date

from app.matching import apply_ai_assessments, rank_reports
from app.schemas import PetCharacteristics


def test_rank_reports_prefers_matching_traits_location_and_date() -> None:
    reports = [
        {
            "id": "close",
            "pet_name": "Milo",
            "report_type": "found",
            "description": "Orange tabby with white paws.",
            "location": "Oakwood, Seattle",
            "report_date": "2026-09-29",
            "characteristics": {
                "species": "cat",
                "breed": "domestic shorthair",
                "colors": ["orange", "white"],
                "size": "small",
                "markings": ["tabby stripes", "white paws"],
                "distinctive_features": [],
            },
        },
        {
            "id": "far",
            "pet_name": "Buddy",
            "report_type": "found",
            "description": "Large brown dog with a long coat.",
            "location": "Tacoma",
            "report_date": "2026-06-01",
            "characteristics": {
                "species": "dog",
                "breed": "retriever",
                "colors": ["brown"],
                "size": "large",
                "markings": ["long coat"],
                "distinctive_features": [],
            },
        },
    ]
    traits = PetCharacteristics(
        species="cat",
        breed="domestic shorthair",
        colors=["orange", "white"],
        size="small",
        markings=["tabby stripes", "white paws"],
    )

    result = rank_reports(
        reports,
        {"close": 0.8, "far": 0.2},
        traits,
        "Oakwood neighborhood, Seattle",
        date(2026, 9, 30),
    )

    assert [match["id"] for match in result] == ["close", "far"]
    assert result[0]["score"] > result[1]["score"]
    assert any("characteristics" in reason for reason in result[0]["reasons"])


def test_rank_reports_limits_results_to_three() -> None:
    reports = [
        {
            "id": f"report-{index}",
            "pet_name": "",
            "report_type": "found",
            "description": "Found pet.",
            "location": "Seattle",
            "report_date": "2026-09-30",
            "characteristics": {},
        }
        for index in range(5)
    ]

    result = rank_reports(
        reports,
        {},
        PetCharacteristics(),
        "Seattle",
        date(2026, 9, 30),
    )

    assert len(result) == 3


def test_rank_reports_includes_public_source_metadata_and_explanation() -> None:
    report = {
        "id": "public-report",
        "pet_name": "Patches",
        "report_type": "found",
        "description": "Black and white cat with a white chest.",
        "location": "Oakwood, Seattle",
        "report_date": "2026-09-30",
        "characteristics": {
            "species": "cat",
            "breed": "",
            "colors": ["black", "white"],
            "size": "small",
            "markings": ["white chest"],
            "distinctive_features": [],
        },
        "source_type": "public",
        "platform": "Facebook",
        "profile_name": "Demo Group",
        "post_url": "https://example.com/demo",
        "caption": "Found near Oakwood.",
        "post_title": "Found cat",
    }
    traits = PetCharacteristics(
        species="cat",
        colors=["black", "white"],
        size="small",
        markings=["white chest"],
    )

    result = rank_reports(
        [report],
        {report["id"]: 0.8},
        traits,
        "Oakwood, Seattle",
        date(2026, 9, 30),
    )
    enriched = apply_ai_assessments(
        result,
        {
            report["id"]: {
                "similarity_score": 0.9,
                "explanation": "Both report a black-and-white cat with a white chest.",
            }
        },
    )[0]

    assert enriched["source_type"] == "public"
    assert enriched["platform"] == "Facebook"
    assert enriched["post_title"] == "Found cat"
    assert enriched["ai_explanation"].startswith("Both report")
    assert enriched["ai_score"] == 0.9
    assert enriched["score"] > 0
