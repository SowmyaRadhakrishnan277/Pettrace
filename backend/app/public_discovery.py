import asyncio
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.schemas import DiscoveredReport, PetCharacteristics

SERPER_SEARCH_URL = "https://google.serper.dev/search"
SOCIAL_DOMAINS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
}
RESULTS_PER_PLATFORM = 8


class PublicReportDiscoveryError(Exception):
    pass


@dataclass
class PublicDiscoveryResult:
    reports: list[dict[str, Any]]
    notice: str


class PublicReportSource(Protocol):
    async def search(
        self,
        query: str,
        location: str,
        date_lost: date,
        characteristics: PetCharacteristics,
    ) -> PublicDiscoveryResult:
        """Search only public web-index results from supported social domains."""


def _platform_for_url(value: str) -> Optional[str]:
    parsed_url = urlparse(value)
    if parsed_url.scheme != "https":
        return None
    host = (parsed_url.hostname or "").lower().rstrip(".")
    for domain, platform in SOCIAL_DOMAINS.items():
        if host == domain or host.endswith(f".{domain}"):
            return platform
    return None


def _published_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1)).isoformat()
    except ValueError:
        return None


def _report_type(text: str) -> str:
    normalized = text.lower()
    if re.search(r"\b(found|sighted|picked up|rescued)\b", normalized):
        return "found"
    if re.search(r"\b(lost|missing|ran away|escaped)\b", normalized):
        return "lost"
    return "unknown"


def _result_to_report(result: dict[str, Any]) -> Optional[dict[str, Any]]:
    url = result.get("link") or result.get("url")
    title = result.get("title")
    description = result.get("snippet") or result.get("description")
    if not isinstance(url, str) or not isinstance(title, str) or not isinstance(description, str):
        return None
    platform = _platform_for_url(url)
    if not platform:
        return None

    published_date = _published_date(result.get("date") or result.get("page_age"))
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    try:
        return DiscoveredReport.model_validate(
            {
                "id": f"web-{digest}",
                "report_type": _report_type(f"{title} {description}"),
                "description": description,
                "location": "",
                "report_date": published_date,
                "platform": platform,
                "post_title": title,
                "post_url": url,
                "caption": description,
                "date_is_estimated": bool(published_date),
            }
        ).model_dump(mode="json")
    except ValidationError:
        return None


def _search_terms(
    query: str, characteristics: PetCharacteristics
) -> str:
    trait_terms = []
    for field in ("species", "breed", "colors", "size", "markings", "distinctive_features"):
        value = getattr(characteristics, field)
        trait_terms.extend(value if isinstance(value, list) else [value])
    terms = " ".join(term.strip() for term in trait_terms if term.strip())
    return " ".join(part for part in (query.strip(), terms) if part)[:450]


class SerperPublicReportSource:
    def __init__(
        self,
        api_key: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("SERPER_API_KEY")
        self.transport = transport

    async def _search_platform(
        self,
        client: httpx.AsyncClient,
        domain: str,
        platform: str,
        terms: str,
        location: str,
    ) -> list[dict[str, Any]]:
        search_query = (
            f'site:{domain} ("lost pet" OR "found pet" OR "missing pet") '
            f"{terms} {location}"
        ).strip()
        try:
            response = await client.post(
                SERPER_SEARCH_URL,
                json={
                    "q": search_query,
                    "num": RESULTS_PER_PLATFORM,
                },
            )
        except httpx.TimeoutException as error:
            raise PublicReportDiscoveryError(
                f"{platform} public search timed out."
            ) from error
        except httpx.RequestError as error:
            raise PublicReportDiscoveryError(
                f"{platform} public search could not be reached."
            ) from error
        if response.is_error:
            raise PublicReportDiscoveryError(
                f"{platform} public search returned HTTP {response.status_code}."
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise PublicReportDiscoveryError(
                f"{platform} public search returned invalid JSON."
            ) from error
        if not isinstance(payload, dict):
            raise PublicReportDiscoveryError(
                f"{platform} public search returned an unexpected response."
            )
        organic_results = payload.get("organic", [])
        if not isinstance(organic_results, list):
            raise PublicReportDiscoveryError(
                f"{platform} public search returned an unexpected result list."
            )
        reports = []
        for item in organic_results:
            if isinstance(item, dict):
                report = _result_to_report(item)
                if report and report["platform"] == platform:
                    reports.append(report)
        return reports

    async def _search_platform_safely(
        self,
        client: httpx.AsyncClient,
        domain: str,
        platform: str,
        terms: str,
        location: str,
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        try:
            return (
                await self._search_platform(
                    client, domain, platform, terms, location
                ),
                None,
            )
        except PublicReportDiscoveryError as error:
            return [], str(error)

    async def search(
        self,
        query: str,
        location: str,
        date_lost: date,
        characteristics: PetCharacteristics,
    ) -> PublicDiscoveryResult:
        del date_lost
        if not self.api_key:
            return PublicDiscoveryResult(
                reports=[],
                notice=(
                    "Live public search is not configured. Add SERPER_API_KEY "
                    "to .env; only local reports were searched."
                ),
            )

        terms = _search_terms(query, characteristics)
        headers = {
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
        }
        async with httpx.AsyncClient(
            headers=headers,
            timeout=12.0,
            transport=self.transport,
        ) as client:
            searches = await asyncio.gather(
                *[
                    self._search_platform_safely(
                        client, domain, platform, terms, location
                    )
                    for domain, platform in SOCIAL_DOMAINS.items()
                ]
            )
        reports = [report for platform_reports, _ in searches for report in platform_reports]
        failures = [message for _, message in searches if message]

        unique_reports = {report["id"]: report for report in reports}
        if failures:
            notice = (
                "Live public search returned partial results. "
                + " ".join(failures)
            )
        elif unique_reports:
            notice = (
                "Live results are public pages indexed by Serper's Google Search API, not a "
                "complete search of Facebook or Instagram. Open the source link "
                "to verify availability and details."
            )
        else:
            notice = (
                "No Facebook or Instagram pages indexed by Serper matched this search. "
                "This does not mean no relevant posts exist."
            )
        return PublicDiscoveryResult(
            reports=list(unique_reports.values()),
            notice=notice,
        )


def get_public_report_source() -> PublicReportSource:
    return SerperPublicReportSource()
