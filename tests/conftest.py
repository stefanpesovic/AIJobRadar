"""Shared test fixtures."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Job


def make_sample_jobs() -> list[Job]:
    """Create a set of sample jobs for testing."""
    now = datetime.now(UTC)
    return [
        Job(
            id="remoteok_1",
            title="Senior LLM Engineer",
            company="Acme AI",
            location="Remote",
            salary="$150,000–$200,000",
            tags=["llm", "python", "pytorch"],
            url="https://example.com/job/1",
            source="remoteok",
            scraped_at=now,
        ),
        Job(
            id="remoteok_2",
            title="ML Ops Engineer",
            company="DataCorp",
            location="US Only",
            tags=["mlops", "kubernetes", "python"],
            url="https://example.com/job/2",
            source="remoteok",
            scraped_at=now,
        ),
        Job(
            id="weworkremotely_1",
            title="AI Research Scientist",
            company="NeuroLabs",
            location="Europe",
            tags=["ai", "deep learning", "transformer"],
            url="https://example.com/job/3",
            source="weworkremotely",
            scraped_at=now,
        ),
        Job(
            id="hackernews_1",
            title="Computer Vision Engineer",
            company="Acme AI",
            location="San Francisco",
            tags=["computer vision", "pytorch"],
            url="https://example.com/job/4",
            source="hackernews",
            scraped_at=now,
        ),
        Job(
            id="hackernews_2",
            title="Prompt Engineer",
            company="GenAI Startup",
            location="Remote",
            tags=["prompt engineer", "langchain"],
            url="https://example.com/job/5",
            source="hackernews",
            scraped_at=now,
        ),
    ]


@pytest.fixture()
def sample_jobs() -> list[Job]:
    """Return a list of sample Job objects."""
    return make_sample_jobs()


@pytest.fixture()
def mock_manager(sample_jobs: list[Job]):
    """Patch the ScraperManager in routes to return sample jobs from cache."""
    with (
        patch("app.routes.jobs.manager.get_jobs", new_callable=AsyncMock) as mock_get,
        patch("app.routes.jobs.manager.get_source_statuses") as mock_sources,
        patch(
            "app.routes.jobs.manager.refresh",
            new_callable=AsyncMock,
        ) as mock_refresh,
    ):
        mock_get.return_value = sample_jobs
        mock_sources.return_value = [
            {"name": "remoteok", "last_scraped_at": None, "jobs_count": 2},
            {"name": "weworkremotely", "last_scraped_at": None, "jobs_count": 1},
            {"name": "hackernews", "last_scraped_at": None, "jobs_count": 2},
        ]
        mock_refresh.return_value = {
            "total_jobs": 5,
            "sources": [
                {"name": "remoteok", "last_scraped_at": None, "jobs_count": 2},
                {"name": "weworkremotely", "last_scraped_at": None, "jobs_count": 1},
                {"name": "hackernews", "last_scraped_at": None, "jobs_count": 2},
            ],
            "duration_seconds": 1.23,
        }
        yield {
            "get_jobs": mock_get,
            "get_source_statuses": mock_sources,
            "refresh": mock_refresh,
        }


@pytest.fixture()
async def client(mock_manager) -> AsyncClient:
    """Return an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
