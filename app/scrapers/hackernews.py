"""Scraper for Hacker News 'Who is hiring?' threads."""

import html
import logging
import re
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.models import Job
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

STORY_SEARCH_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query=Ask+HN:+Who+is+hiring"
    "&tags=story&hitsPerPage=1"
)
COMMENTS_URL_TEMPLATE = (
    "https://hn.algolia.com/api/v1/search"
    "?tags=comment,story_{story_id}"
    "&hitsPerPage=200"
)


class HackerNewsScraper(BaseScraper):
    """Scrapes job postings from the latest HN 'Who is hiring?' thread.

    Uses the Algolia HN API to fetch the thread and its comments.
    Each top-level comment is treated as a potential job posting.
    """

    source_name = "hackernews"

    async def scrape(self) -> list[Job]:
        """Fetch and parse job listings from the latest HN hiring thread."""
        try:
            story_id = await self._find_latest_thread_id()
            if not story_id:
                logger.warning("No 'Who is hiring?' thread found")
                return []

            comments = await self._fetch_comments(story_id)
            jobs = self._parse_comments(comments, story_id)
            logger.info("HN returned %d AI jobs from story %s", len(jobs), story_id)
            return jobs[: settings.MAX_JOBS_PER_SOURCE]

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.error("HN scrape failed: %s", exc)
            return []

    async def _find_latest_thread_id(self) -> str | None:
        """Find the objectID of the latest 'Who is hiring?' story."""
        async with httpx.AsyncClient(
            headers=self.default_headers(),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(STORY_SEARCH_URL)
            response.raise_for_status()

        data = response.json()
        hits = data.get("hits", [])
        if not hits:
            return None
        return hits[0].get("objectID")

    async def _fetch_comments(self, story_id: str) -> list[dict]:
        """Fetch top-level comments for a given HN story."""
        url = COMMENTS_URL_TEMPLATE.format(story_id=story_id)
        async with httpx.AsyncClient(
            headers=self.default_headers(),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        hits = data.get("hits", [])

        # Only keep top-level comments (parent_id == story_id)
        story_id_int = int(story_id)
        return [h for h in hits if h.get("parent_id") == story_id_int]

    def _parse_comments(self, comments: list[dict], story_id: str) -> list[Job]:
        """Parse HN comments into Job objects with best-effort extraction."""
        jobs: list[Job] = []
        now = datetime.now(UTC)

        for comment in comments:
            text = comment.get("comment_text", "")
            if not text:
                continue

            # Check AI relevance
            plain_text = self._strip_html(text)
            if not self.matches_ai_keywords(plain_text):
                continue

            company, title = self._extract_company_and_title(plain_text)
            comment_id = comment.get("objectID", "")
            posted_at = self._parse_date(comment.get("created_at"))

            jobs.append(
                Job(
                    id=f"hackernews_{comment_id}",
                    title=title,
                    company=company,
                    url=f"https://news.ycombinator.com/item?id={comment_id}",
                    source="hackernews",
                    tags=self._extract_tags(plain_text),
                    posted_at=posted_at,
                    scraped_at=now,
                )
            )

        return jobs

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = html.unescape(clean)
        # Normalize whitespace
        return re.sub(r"\s+", " ", clean).strip()

    @staticmethod
    def _extract_company_and_title(plain_text: str) -> tuple[str, str]:
        """Best-effort extraction of company and title from first line.

        HN hiring comments typically start with:
            "Company Name | Role Title | Location | ..."
        """
        first_line = plain_text.split("\n")[0].strip()
        # Many posts use pipe-delimited format
        parts = [p.strip() for p in first_line.split("|")]

        if len(parts) >= 2:
            return parts[0], parts[1]
        # Fallback: use the first line as both
        truncated = first_line[:120] if len(first_line) > 120 else first_line
        return "Unknown", truncated or "HN Job Posting"

    @staticmethod
    def _extract_tags(plain_text: str) -> list[str]:
        """Extract AI-related tags found in the text."""
        lowered = plain_text.lower()
        return [kw for kw in settings.AI_KEYWORDS if kw in lowered]

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse an ISO 8601 date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
