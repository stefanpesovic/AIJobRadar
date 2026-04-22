"""Abstract base class for all job scrapers."""

import logging
from abc import ABC, abstractmethod

from app.config import settings
from app.models import Job, SourceName

logger = logging.getLogger(__name__)


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
        """Return True if the text contains at least one AI keyword."""
        lowered = text.lower()
        return any(kw in lowered for kw in settings.AI_KEYWORDS)

    @staticmethod
    def default_headers() -> dict[str, str]:
        """Return default HTTP headers for scraper requests."""
        return {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
