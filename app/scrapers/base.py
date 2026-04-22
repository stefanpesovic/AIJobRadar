"""Abstract base class for all job scrapers."""

import logging
import re
from abc import ABC, abstractmethod

from app.config import settings
from app.models import Job, SourceName

logger = logging.getLogger(__name__)

# Pre-compile a single regex pattern for all AI keywords using word boundaries.
# This prevents false positives like "ai" matching inside "email" or "maintain".
# Sorted longest-first so that "machine learning" is tried before "machine", etc.
_sorted_keywords = sorted(settings.AI_KEYWORDS, key=len, reverse=True)
_AI_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _sorted_keywords) + r")\b",
    re.IGNORECASE,
)


class BaseScraper(ABC):
    """Base contract that every scraper must implement.

    Subclasses set `source_name` and implement `scrape()`.
    Common helpers for HTTP headers and AI keyword filtering live here.
    """

    source_name: SourceName

    @abstractmethod
    async def scrape(self) -> list[Job]:
        """Fetch and return normalized Job objects.

        Must not raise on network errors — return [] instead.
        """
        ...

    @staticmethod
    def matches_ai_keywords(text: str) -> bool:
        """Return True if text contains at least one AI keyword."""
        return bool(_AI_PATTERN.search(text))

    def apply_ai_filter(self, jobs: list[Job]) -> list[Job]:
        """Filter jobs to those matching AI keywords in title, tags, or description.

        Logs per-source stats and emits a WARNING if zero jobs survive the filter.
        """
        total = len(jobs)
        kept: list[Job] = []
        for job in jobs:
            searchable = " ".join(
                [job.title, " ".join(job.tags), job.description or ""]
            )
            if self.matches_ai_keywords(searchable):
                kept.append(job)

        filtered_out = total - len(kept)
        logger.info(
            "%s: scraped %d, kept %d after AI filter (removed %d)",
            self.source_name,
            total,
            len(kept),
            filtered_out,
        )
        if not kept and total > 0:
            logger.warning(
                "%s returned 0 jobs after AI filter (scraped %d before)",
                self.source_name,
                total,
            )
        return kept

    @staticmethod
    def default_headers() -> dict[str, str]:
        """Return default HTTP headers for scraper requests."""
        return {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
