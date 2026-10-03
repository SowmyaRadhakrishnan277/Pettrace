import base64
import json

import httpx
import pytest

from app import ai
from app.schemas import CandidateAssessmentResponse, PetCharacteristics


def _mock_client(monkeypatch, handler):
    original_client = httpx.Client

    def create_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(ai.httpx, "Client", create_client)


def test_extract_characteristics_sends_image_to_azure_openai(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-token")
    monkeypatch.setenv(
        "AZURE_OPENAI_CHAT_COMPLETIONS_URL",
        "https://example.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
    )
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["api_key"] = request.headers["api-key"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "species": "cat",
                                    "breed": "domestic shorthair",
                                    "colors": ["black", "white"],
                                    "size": "small",
                                    "markings": ["white chest"],
                                    "distinctive_features": [],
                                }
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    _mock_client(monkeypatch, handler)
    characteristics = ai.extract_characteristics(b"test-image", "image/png", "black cat")

    assert seen["api_key"] == "test-azure-token"
    assert seen["url"] == "https://example.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
    assert "model" not in seen["body"]
    image_part = seen["body"]["messages"][0]["content"][0]["image_url"]["url"]
    assert image_part == "data:image/png;base64," + base64.b64encode(b"test-image").decode()
    assert characteristics.species == "cat"
    assert characteristics.colors == ["black", "white"]


def test_compare_candidates_validates_all_candidate_ids(monkeypatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-azure-token")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "assessments": [
                                        {
                                            "report_id": "report-1",
                                            "similarity_score": 0.82,
                                            "explanation": "Caption describes a black cat.",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    _mock_client(monkeypatch, handler)
    response = ai.compare_candidates(
        b"test-image",
        "image/jpeg",
        "black cat",
        PetCharacteristics(species="cat"),
        [
            {
                "id": "report-1",
                "description": "Found a black cat.",
                "caption": "Found near park.",
                "characteristics": {"species": "cat"},
            }
        ],
    )

    assert isinstance(response, CandidateAssessmentResponse)
    assert response.assessments[0].similarity_score == 0.82


def test_ai_requests_report_http_status_without_exposing_key(monkeypatch) -> None:
    secret = "test-azure-secret"
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized", request=request)

    _mock_client(monkeypatch, handler)

    with pytest.raises(ai.AIServiceError) as error:
        ai.extract_characteristics(b"image", "image/jpeg", "pet")

    assert "HTTP 401" in str(error.value)
    assert secret not in str(error.value)
    assert "Azure OpenAI returned HTTP 401" in str(error.value)


def test_ai_requires_azure_openai_key(monkeypatch) -> None:
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        ai.extract_characteristics(b"image", "image/jpeg", "pet")
