import asyncio
from datetime import date

import httpx

from app.public_discovery import SerperPublicReportSource
from app.schemas import PetCharacteristics


def _result(url: str, title: str, description: str) -> dict:
    return {
        "link": url,
        "title": title,
        "snippet": description,
        "date": "2026-10-01",
    }


def test_search_returns_only_indexed_facebook_and_instagram_results() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "site:facebook.com" in request.read().decode():
            results = [
                _result(
                    "https://www.facebook.com/groups/lostpets/posts/123",
                    "Found black and white cat",
                    "Found near Oakwood; white chest patch.",
                ),
                _result(
                    "https://example.org/not-a-social-result",
                    "Unrelated page",
                    "Not an allowed social domain.",
                ),
            ]
        else:
            results = [
                _result(
                    "https://www.instagram.com/p/ABC123/",
                    "Missing orange tabby",
                    "Lost cat in Seattle.",
                )
            ]
        return httpx.Response(
            200,
            json={"organic": results},
            request=request,
        )

    source = SerperPublicReportSource(
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        source.search(
            query="black and white cat",
            location="Oakwood Seattle",
            date_lost=date(2026, 9, 30),
            characteristics=PetCharacteristics(
                species="cat",
                colors=["black", "white"],
                markings=["white chest"],
            ),
        )
    )

    assert len(requests) == 2
    assert all(request.headers["X-API-KEY"] == "test-token" for request in requests)
    assert len(result.reports) == 2
    assert {report["platform"] for report in result.reports} == {"Facebook", "Instagram"}
    assert all(report["post_url"].startswith("https://") for report in result.reports)
    assert result.reports[0]["date_is_estimated"] is True
    assert result.reports[0]["report_date"] == "2026-10-01"
    assert "indexed by Serper" in result.notice


def test_search_explicitly_reports_missing_api_key() -> None:
    source = SerperPublicReportSource(api_key="")

    result = asyncio.run(
        source.search(
            query="lost cat",
            location="Seattle",
            date_lost=date(2026, 9, 30),
            characteristics=PetCharacteristics(species="cat"),
        )
    )

    assert result.reports == []
    assert "SERPER_API_KEY" in result.notice
    assert "only local reports" in result.notice


def test_search_returns_partial_results_and_reports_platform_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "site:facebook.com" in request.read().decode():
            return httpx.Response(429, request=request)
        return httpx.Response(
            200,
            json={
                "organic": [
                    _result(
                        "https://www.instagram.com/p/ABC123/",
                        "Found a dog",
                        "Found dog in the neighborhood.",
                    )
                ]
            },
            request=request,
        )

    source = SerperPublicReportSource(
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        source.search(
            query="found dog",
            location="Seattle",
            date_lost=date(2026, 9, 30),
            characteristics=PetCharacteristics(species="dog"),
        )
    )

    assert len(result.reports) == 1
    assert "partial results" in result.notice
    assert "HTTP 429" in result.notice
