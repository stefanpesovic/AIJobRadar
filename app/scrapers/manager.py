"""Orchestrates all scrapers and manages the cache."""

import asyncio
import logging
import time
from datetime import UTC, datetime

from app.cache import JobCache
from app.config import settings
from app.models import Job, RefreshResponse, SourceStatus
from app.scrapers.base import BaseScraper
from app.scrapers.hackernews import HackerNewsScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper

logger = logging.getLogger(__name__)


class ScraperManager:
    """Runs all scrapers concurrently and manages cached results.

    Provides methods to get jobs (from cache or fresh scrape) and
    to force a full refresh across all sources.
    """

    def __init__(self) -> None:
        self._scrapers: list[BaseScraper] = [
            RemoteOKScraper(),
            WeWorkRemotelyScraper(),
            HackerNewsScraper(),
        ]
        self._cache = JobCache(
            path=settings.CACHE_FILE_PATH,
            ttl_minutes=settings.CACHE_TTL_MINUTES,
        )
        self._source_statuses: dict[str, SourceStatus] = {}

    async def get_jobs(self) -> list[Job]:
        """Return cached jobs if fresh, otherwise scrape all sources."""
        if self._cache.is_fresh():
            cached = self._cache.read()
            if cached is not None:
                logger.info("Serving %d jobs from cache", len(cached))
                return cached

        await self._run_all_scrapers()
        return self._cache.read() or []

    async def refresh(self) -> RefreshResponse:
        """Invalidate cache, re-scrape all sources, and return stats."""
        self._cache.invalidate()
        start = time.monotonic()
        all_jobs = await self._run_all_scrapers()
        duration = time.monotonic() - start

        return RefreshResponse(
            total_jobs=len(all_jobs),
            sources=list(self._source_statuses.values()),
            duration_seconds=round(duration, 2),
        )

    def get_source_statuses(self) -> list[SourceStatus]:
        """Return the last known status for each scraper source."""
        # If no scrape has happened yet, return default statuses
        if not self._source_statuses:
            return [
                SourceStatus(
                    name=s.source_name,
                    last_scraped_at=None,
                    jobs_count=0,
                )
                for s in self._scrapers
            ]
        return list(self._source_statuses.values())

    async def _run_all_scrapers(self) -> list[Job]:
        """Run all scrapers concurrently and write results to cache."""
        tasks = [self._run_scraper(s) for s in self._scrapers]
        results = await asyncio.gather(*tasks)

        all_jobs: list[Job] = []
        for jobs in results:
            all_jobs.extend(jobs)

        self._cache.write(all_jobs)
        logger.info(
            "Scraped %d total jobs from %d sources",
            len(all_jobs),
            len(self._scrapers),
        )
        return all_jobs

    async def _run_scraper(self, scraper: BaseScraper) -> list[Job]:
        """Run a single scraper and record its status."""
        now = datetime.now(UTC)
        try:
            jobs = await scraper.scrape()
            self._source_statuses[scraper.source_name] = SourceStatus(
                name=scraper.source_name,
                last_scraped_at=now,
                jobs_count=len(jobs),
            )
            return jobs
        except Exception as exc:
            logger.error("Scraper %s failed: %s", scraper.source_name, exc)
            self._source_statuses[scraper.source_name] = SourceStatus(
                name=scraper.source_name,
                last_scraped_at=now,
                jobs_count=0,
                last_error=str(exc),
            )
            return []
