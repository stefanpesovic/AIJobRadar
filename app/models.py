"""Pydantic models for the AIJobRadar API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SourceName = Literal["remoteok", "weworkremotely", "hackernews"]


class Job(BaseModel):
    """A normalized job listing from any supported source."""

    id: str  # Format: "{source}_{unique_id}"
    title: str
    company: str
    location: str | None = None
    salary: str | None = None
    tags: list[str] = Field(default_factory=list)
    url: str
    source: SourceName
    posted_at: datetime | None = None
    scraped_at: datetime


class JobsResponse(BaseModel):
    """Paginated response for the /jobs endpoint."""

    total: int
    page: int
    limit: int
    jobs: list[Job]


class SourceStatus(BaseModel):
    """Status report for a single scraper source."""

    name: SourceName
    last_scraped_at: datetime | None
    jobs_count: int
    last_error: str | None = None


class RefreshResponse(BaseModel):
    """Response from the POST /refresh endpoint."""

    total_jobs: int
    sources: list[SourceStatus]
    duration_seconds: float
