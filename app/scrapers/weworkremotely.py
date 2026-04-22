"""Scraper for WeWorkRemotely job listings."""

import logging
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import Job
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://weworkremotely.com/remote-jobs/search?term=AI"
CATEGORY_URL = (
    "https://weworkremotely.com/categories/remote-artificial-intelligence-jobs"
)


class WeWorkRemotelyScraper(BaseScraper):
    """Scrapes AI/ML jobs from WeWorkRemotely.

    Primary: search endpoint with term=AI.
    Fallback: AI category page if search returns 403 (Cloudflare).
    """

    source_name = "weworkremotely"

    async def scrape(self) -> list[Job]:
        """Fetch and parse job listings from WeWorkRemotely."""
        jobs = await self._scrape_url(SEARCH_URL)
        if not jobs:
            logger.warning("WWR search failed, trying category fallback")
            jobs = await self._scrape_url(CATEGORY_URL)
        return jobs[: settings.MAX_JOBS_PER_SOURCE]

    async def _scrape_url(self, url: str) -> list[Job]:
        """Fetch and parse jobs from a given WWR page URL."""
        try:
            async with httpx.AsyncClient(
                headers=self.default_headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            return self._parse_html(response.text)

        except (httpx.HTTPError, ValueError) as exc:
            logger.error("WWR scrape failed for %s: %s", url, exc)
            return []

    def _parse_html(self, html: str) -> list[Job]:
        """Parse job listings from WWR HTML."""
        soup = BeautifulSoup(html, "lxml")
        listings = soup.select("section.jobs li")

        jobs: list[Job] = []
        now = datetime.now(UTC)

        for li in listings:
            # Skip "view all" links and ad listings
            li_classes = " ".join(li.get("class", []))
            if "view-all" in li_classes or "listing-ad" in li_classes:
                continue

            link = li.select_one("a.listing-link--unlocked")
            if not link:
                continue

            href = link.get("href", "")
            url = f"https://weworkremotely.com{href}" if href else ""

            title_el = li.select_one("span.new-listing__header__title__text")
            company_el = li.select_one("p.new-listing__company-name")
            location_el = li.select_one("p.new-listing__company-headquarters")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            location = location_el.get_text(strip=True) if location_el else None

            # Extract category tags (e.g. "Full-Time", "$50k-$74k", region)
            tag_els = li.select(
                "div.new-listing__categories p.new-listing__categories__category"
            )
            tags = [t.get_text(strip=True) for t in tag_els]
            # Filter out "Featured" tag — it's a listing tier, not a job attribute
            tags = [t for t in tags if t.lower() != "featured"]

            # Extract salary from tags if present (matches "$XX,XXX" patterns)
            salary = self._extract_salary(tags)

            # Build unique ID from the URL slug
            job_id = href.strip("/").split("/")[-1] if href else ""

            # AI keyword check against title + tags
            searchable = f"{title} {' '.join(tags)}"
            if not self.matches_ai_keywords(searchable):
                continue

            jobs.append(
                Job(
                    id=f"weworkremotely_{job_id}",
                    title=title or "Unknown",
                    company=company or "Unknown",
                    location=location or None,
                    salary=salary,
                    tags=tags,
                    url=url,
                    source="weworkremotely",
                    scraped_at=now,
                )
            )

        logger.info("WWR returned %d AI jobs", len(jobs))
        return jobs

    @staticmethod
    def _extract_salary(tags: list[str]) -> str | None:
        """Extract a salary string from category tags if present."""
        for tag in tags:
            if "$" in tag:
                return tag
        return None
