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

# Regex matching a standalone URL (http/https or www.)
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

# Words commonly found in job titles — used to positively identify title parts
_ROLE_WORDS_RE = re.compile(
    r"\b(?:engineer|developer|designer|manager|lead|director|architect"
    r"|scientist|researcher|analyst|specialist|consultant|coordinator"
    r"|head|founder|product|data|software|frontend|backend|full.?stack"
    r"|devops|sre|platform|infrastructure|staff|senior|junior|principal"
    r"|intern|vp|cto|haskell|python|java|golang|rust)\b",
    re.IGNORECASE,
)

# Minimum length for a title to be considered valid
_MIN_TITLE_LENGTH = 15

# Maximum title length before truncation
_MAX_TITLE_LENGTH = 80


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
            return self.apply_ai_filter(jobs)[: settings.MAX_JOBS_PER_SOURCE]

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

            plain_text = self._strip_html(text)

            if not self._is_valid_posting(plain_text):
                continue

            result = self._extract_company_and_title(plain_text)
            if result is None:
                continue

            company, title = result
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
                    description=plain_text,
                    posted_at=posted_at,
                    scraped_at=now,
                )
            )

        return jobs

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags and decode entities, preserving paragraph breaks."""
        # Replace paragraph/break tags with newlines first
        clean = re.sub(r"<(?:p|br)\s*/?>", "\n", text, flags=re.IGNORECASE)
        # Remove remaining HTML tags
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = html.unescape(clean)
        # Normalize whitespace within each line, preserve line breaks
        lines = clean.split("\n")
        lines = [re.sub(r"\s+", " ", line).strip() for line in lines]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _is_valid_posting(plain_text: str) -> bool:
        """Return True if the comment looks like a genuine job posting."""
        # Too short to be a real posting
        if len(plain_text) < _MIN_TITLE_LENGTH:
            return False

        # Text is only a URL (no meaningful content)
        stripped = _URL_RE.sub("", plain_text).strip()
        return len(stripped) >= _MIN_TITLE_LENGTH

    def _extract_company_and_title(
        self,
        plain_text: str,
    ) -> tuple[str, str] | None:
        """Best-effort extraction of company and title from first line.

        HN hiring comments typically start with:
            "Company Name | Role Title | Location | ..."
        or  "Company Name is hiring ..."

        Returns None if the extracted title is garbage (URL-only, too short).
        """
        first_line = plain_text.split("\n")[0].strip()

        # Strip URLs from first line before parsing
        clean_line = _URL_RE.sub("", first_line).strip()
        # Collapse leftover whitespace / trailing separators
        clean_line = re.sub(r"\s+", " ", clean_line).strip(" |:-")

        # If the cleaned first line is too short, skip entirely
        if len(clean_line) < _MIN_TITLE_LENGTH:
            return None

        # Try pipe-delimited format: "Company | Title | Location | ..."
        parts = [p.strip() for p in clean_line.split("|")]
        parts = [p for p in parts if p]  # drop empty segments

        if len(parts) >= 2:
            company = parts[0]
            # Find the best title: must contain a role word or AI keyword
            title = None
            for part in parts[1:]:
                if "@" in part:
                    continue
                if _ROLE_WORDS_RE.search(part) or self.matches_ai_keywords(part):
                    title = part
                    break
            if title is None:
                return None
        else:
            # Try "Company is hiring" pattern
            match = re.match(r"^(.+?)\s+is\s+hiring\b", clean_line, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                title = clean_line
            else:
                company = "Unknown"
                title = clean_line

        # Truncate title at word boundary near _MAX_TITLE_LENGTH
        if len(title) > _MAX_TITLE_LENGTH:
            truncated = title[:_MAX_TITLE_LENGTH]
            # Cut at last space to avoid breaking mid-word
            last_space = truncated.rfind(" ")
            if last_space > _MAX_TITLE_LENGTH // 2:
                truncated = truncated[:last_space]
            title = truncated

        return company, title

    @staticmethod
    def _extract_tags(plain_text: str) -> list[str]:
        """Extract AI-related tags found in the text."""
        from app.scrapers.base import _AI_PATTERN

        return list({m.lower() for m in _AI_PATTERN.findall(plain_text)})

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse an ISO 8601 date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
