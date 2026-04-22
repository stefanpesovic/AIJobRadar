"""API route handlers for job listings."""

import logging

from fastapi import APIRouter, Query

from app.models import JobsResponse, RefreshResponse, SourceStatus
from app.scrapers.manager import ScraperManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton manager shared across requests
manager = ScraperManager()


@router.get(
    "/jobs",
    response_model=JobsResponse,
    summary="List AI/ML job listings",
    description=(
        "Returns paginated, filterable AI/ML job listings from all sources. "
        "Serves from cache if fresh; otherwise triggers a live scrape."
    ),
)
async def get_jobs(
    keyword: str | None = Query(
        None,
        description="Filter by keyword (case-insensitive, title/company/tags)",
    ),
    company: str | None = Query(
        None, description="Filter by company name (case-insensitive substring)"
    ),
    location: str | None = Query(
        None, description="Filter by location (case-insensitive substring)"
    ),
    source: str | None = Query(
        None, description="Filter by source: remoteok, weworkremotely, hackernews"
    ),
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    limit: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
) -> JobsResponse:
    """Fetch and return filtered, paginated job listings."""
    jobs = await manager.get_jobs()

    # Apply filters (case-insensitive substring matching)
    if keyword:
        kw = keyword.lower()
        jobs = [
            j
            for j in jobs
            if kw in j.title.lower()
            or kw in j.company.lower()
            or any(kw in tag.lower() for tag in j.tags)
        ]

    if company:
        comp = company.lower()
        jobs = [j for j in jobs if comp in j.company.lower()]

    if location:
        loc = location.lower()
        jobs = [j for j in jobs if j.location and loc in j.location.lower()]

    if source:
        src = source.lower()
        jobs = [j for j in jobs if j.source == src]

    # Paginate after filtering
    total = len(jobs)
    start = (page - 1) * limit
    end = start + limit
    paginated = jobs[start:end]

    return JobsResponse(
        total=total,
        page=page,
        limit=limit,
        jobs=paginated,
    )


@router.get(
    "/sources",
    response_model=list[SourceStatus],
    summary="Scraper source status",
    description=(
        "Returns the last scrape time, job count, " "and error status for each source."
    ),
)
async def get_sources() -> list[SourceStatus]:
    """Return status information for each scraper source."""
    return manager.get_source_statuses()


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Force re-scrape all sources",
    description=(
        "Invalidates the cache and re-scrapes all job sources. "
        "Returns stats and timing."
    ),
)
async def refresh_jobs() -> RefreshResponse:
    """Invalidate cache and re-scrape all sources."""
    logger.info("Manual refresh triggered")
    return await manager.refresh()


@router.get(
    "/health",
    summary="Health check",
    description="Returns service health status and version.",
)
async def health_check() -> dict:
    """Return service health status."""
    return {"status": "ok", "version": "1.0.0"}
