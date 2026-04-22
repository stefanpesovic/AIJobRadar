"""Tests for the API endpoints."""

from httpx import AsyncClient


class TestHealthEndpoint:
    """Tests for GET /health."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_returns_ok_status(self, client: AsyncClient) -> None:
        data = (await client.get("/health")).json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"


class TestRootEndpoint:
    """Tests for GET /."""

    async def test_root_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200

    async def test_root_contains_links(self, client: AsyncClient) -> None:
        data = (await client.get("/")).json()
        assert "docs" in data
        assert "jobs" in data


class TestJobsEndpoint:
    """Tests for GET /jobs."""

    async def test_returns_valid_response_structure(self, client: AsyncClient) -> None:
        response = await client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    async def test_returns_all_jobs_unfiltered(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs")).json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 5

    async def test_keyword_filter_llm(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?keyword=llm")).json()
        assert data["total"] == 1
        assert data["jobs"][0]["title"] == "Senior LLM Engineer"

    async def test_keyword_filter_case_insensitive(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?keyword=LLM")).json()
        assert data["total"] == 1

    async def test_keyword_filter_matches_tags(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?keyword=langchain")).json()
        assert data["total"] == 1
        assert data["jobs"][0]["title"] == "Prompt Engineer"

    async def test_company_filter(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?company=Acme")).json()
        assert data["total"] == 2
        companies = {j["company"] for j in data["jobs"]}
        assert companies == {"Acme AI"}

    async def test_location_filter(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?location=europe")).json()
        assert data["total"] == 1
        assert data["jobs"][0]["location"] == "Europe"

    async def test_source_filter(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?source=hackernews")).json()
        assert data["total"] == 2
        for job in data["jobs"]:
            assert job["source"] == "hackernews"

    async def test_pagination_default(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs")).json()
        assert data["page"] == 1
        assert data["limit"] == 20

    async def test_pagination_custom(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?page=1&limit=2")).json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 2
        assert data["page"] == 1
        assert data["limit"] == 2

    async def test_pagination_second_page(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?page=2&limit=2")).json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 2
        assert data["page"] == 2

    async def test_pagination_last_page_partial(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?page=3&limit=2")).json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 1  # 5 jobs, page 3 with limit 2 = 1 job

    async def test_pagination_beyond_results(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?page=100&limit=20")).json()
        assert data["total"] == 5
        assert len(data["jobs"]) == 0

    async def test_invalid_page_returns_422(self, client: AsyncClient) -> None:
        response = await client.get("/jobs?page=0")
        assert response.status_code == 422

    async def test_invalid_limit_too_high_returns_422(
        self, client: AsyncClient
    ) -> None:
        response = await client.get("/jobs?limit=101")
        assert response.status_code == 422

    async def test_invalid_limit_zero_returns_422(self, client: AsyncClient) -> None:
        response = await client.get("/jobs?limit=0")
        assert response.status_code == 422

    async def test_combined_filters(self, client: AsyncClient) -> None:
        data = (await client.get("/jobs?keyword=pytorch&source=hackernews")).json()
        assert data["total"] == 1
        assert data["jobs"][0]["title"] == "Computer Vision Engineer"


class TestSourcesEndpoint:
    """Tests for GET /sources."""

    async def test_returns_list(self, client: AsyncClient) -> None:
        response = await client.get("/sources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_source_names(self, client: AsyncClient) -> None:
        data = (await client.get("/sources")).json()
        names = {s["name"] for s in data}
        assert names == {"remoteok", "weworkremotely", "hackernews"}


class TestRefreshEndpoint:
    """Tests for POST /refresh."""

    async def test_refresh_returns_200(self, client: AsyncClient) -> None:
        response = await client.post("/refresh")
        assert response.status_code == 200

    async def test_refresh_response_structure(self, client: AsyncClient) -> None:
        data = (await client.post("/refresh")).json()
        assert "total_jobs" in data
        assert "sources" in data
        assert "duration_seconds" in data
