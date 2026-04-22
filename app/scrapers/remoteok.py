"""Scraper for RemoteOK job listings."""

import logging
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.models import Job
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"
FALLBACK_URL = "https://remoteok.com/remote-dev+ai-jobs"


class RemoteOKScraper(BaseScraper):
    """Scrapes AI/ML jobs from RemoteOK.

    Primary: JSON API at /api.
    Fallback: HTML parsing if the API fails.
    """

    source_name = "remoteok"

    async def scrape(self) -> list[Job]:
        """Fetch jobs from RemoteOK, filtering for AI relevance."""
        jobs = await self._scrape_api()
        if not jobs:
            logger.warning("RemoteOK API failed, trying HTML fallback")
            jobs = await self._scrape_html()
        return jobs[: settings.MAX_JOBS_PER_SOURCE]

    async def _scrape_api(self) -> list[Job]:
        """Fetch jobs via the RemoteOK JSON API."""
        try:
            async with httpx.AsyncClient(
                headers=self.default_headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(API_URL)
                response.raise_for_status()

            data = response.json()
            # First entry is a legal notice — skip it
            entries = data[1:] if isinstance(data, list) and len(data) > 1 else []

            jobs: list[Job] = []
            now = datetime.now(UTC)
            for entry in entries:
                searchable = " ".join(
                    [
                        entry.get("position", ""),
                        " ".join(entry.get("tags", [])),
                        entry.get("description", ""),
                    ]
                )
                if not self.matches_ai_keywords(searchable):
                    continue

                salary = self._format_salary(
                    entry.get("salary_min"), entry.get("salary_max")
                )
                posted_at = self._parse_date(entry.get("date"))

                jobs.append(
                    Job(
                        id=f"remoteok_{entry.get('id', '')}",
                        title=entry.get("position", "Unknown"),
                        company=entry.get("company", "Unknown"),
                        location=entry.get("location") or None,
                        salary=salary,
                        tags=entry.get("tags", []),
                        url=entry.get("url", ""),
                        source="remoteok",
                        posted_at=posted_at,
                        scraped_at=now,
                    )
                )

            logger.info("RemoteOK API returned %d AI jobs", len(jobs))
            return jobs

        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            logger.error("RemoteOK API scrape failed: %s", exc)
            return []

    async def _scrape_html(self) -> list[Job]:
        """Fallback: parse jobs from the RemoteOK HTML page."""
        try:
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient(
                headers=self.default_headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(FALLBACK_URL)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            rows = soup.select("tr.job")

            jobs: list[Job] = []
            now = datetime.now(UTC)
            for row in rows:
                job_id = row.get("data-id", "")
                title_el = row.select_one("h2")
                company_el = row.select_one("h3")
                link_el = row.select_one("a[href*='/remote-jobs/']")

                title = title_el.get_text(strip=True) if title_el else ""
                company = company_el.get_text(strip=True) if company_el else ""
                href = link_el["href"] if link_el and link_el.get("href") else ""
                url = f"https://remoteok.com{href}" if href else ""

                tags_els = row.select("div.tags a.tag span")
                tags = [t.get_text(strip=True) for t in tags_els]

                searchable = f"{title} {' '.join(tags)}"
                if not self.matches_ai_keywords(searchable):
                    continue

                jobs.append(
                    Job(
                        id=f"remoteok_{job_id}",
                        title=title or "Unknown",
                        company=company or "Unknown",
                        tags=tags,
                        url=url,
                        source="remoteok",
                        scraped_at=now,
                    )
                )

            logger.info("RemoteOK HTML fallback returned %d AI jobs", len(jobs))
            return jobs

        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            logger.error("RemoteOK HTML scrape failed: %s", exc)
            return []

    @staticmethod
    def _format_salary(salary_min: int | None, salary_max: int | None) -> str | None:
        """Format min/max salary into a human-readable string."""
        if salary_min and salary_max:
            return f"${salary_min:,}–${salary_max:,}"
        if salary_min:
            return f"${salary_min:,}+"
        if salary_max:
            return f"Up to ${salary_max:,}"
        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse an ISO 8601 date string to a datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            return None
