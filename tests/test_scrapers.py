"""Tests for all scraper implementations."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.scrapers.base import BaseScraper
from app.scrapers.hackernews import (
    COMMENTS_URL_TEMPLATE,
    STORY_SEARCH_URL,
    HackerNewsScraper,
)
from app.scrapers.remoteok import API_URL, FALLBACK_URL, RemoteOKScraper
from app.scrapers.weworkremotely import (
    CATEGORY_URL,
    SEARCH_URL,
    WeWorkRemotelyScraper,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# RemoteOK Scraper Tests
# ---------------------------------------------------------------------------


class TestRemoteOKApi:
    """Tests for the RemoteOK JSON API scraper path."""

    @pytest.fixture()
    def api_json(self) -> list[dict]:
        """Load the RemoteOK JSON fixture."""
        return json.loads(
            (FIXTURES_DIR / "remoteok_sample.json").read_text(encoding="utf-8")
        )

    @respx.mock
    async def test_parses_ai_jobs_from_api(self, api_json: list[dict]) -> None:
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=api_json))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()

        # Fixture has 3 real jobs: 2 are AI-relevant, 1 (Frontend Developer) is not
        assert len(jobs) == 2
        ids = {j.id for j in jobs}
        assert "remoteok_100001" in ids  # Senior ML Engineer
        assert "remoteok_100003" in ids  # AI Research Scientist

    @respx.mock
    async def test_job_fields_populated_correctly(self, api_json: list[dict]) -> None:
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=api_json))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()
        ml_job = next(j for j in jobs if j.id == "remoteok_100001")

        assert ml_job.title == "Senior ML Engineer"
        assert ml_job.company == "DeepTech AI"
        assert ml_job.location == "Worldwide"
        assert ml_job.salary == "$150,000–$200,000"
        assert "pytorch" in ml_job.tags
        assert ml_job.source == "remoteok"
        assert ml_job.posted_at is not None
        assert ml_job.url.startswith("https://remoteok.com")

    @respx.mock
    async def test_excludes_non_ai_jobs(self, api_json: list[dict]) -> None:
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=api_json))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()
        titles = {j.title for j in jobs}

        assert "Frontend Developer" not in titles

    @respx.mock
    async def test_excludes_substring_false_positives(
        self, api_json: list[dict]
    ) -> None:
        """Jobs with 'ai' only as substring (email, maintain) must be excluded."""
        respx.get(API_URL).mock(return_value=httpx.Response(200, json=api_json))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()
        titles = {j.title for j in jobs}

        # "Email Marketing Manager" has "ai" in "email"/"maintain"/"availability"
        # but no real AI keywords — must be filtered out
        assert "Email Marketing Manager" not in titles

    @respx.mock
    async def test_returns_empty_on_network_error(self) -> None:
        respx.get(API_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
        respx.get(FALLBACK_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()

        # Both API and fallback fail — should return []
        assert jobs == []

    @respx.mock
    async def test_returns_empty_on_500(self) -> None:
        respx.get(API_URL).mock(return_value=httpx.Response(500))
        respx.get(FALLBACK_URL).mock(return_value=httpx.Response(500))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()

        assert jobs == []

    @respx.mock
    async def test_returns_empty_on_invalid_json(self) -> None:
        respx.get(API_URL).mock(
            return_value=httpx.Response(200, text="not json at all")
        )
        respx.get(FALLBACK_URL).mock(return_value=httpx.Response(500))

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()

        assert jobs == []


class TestRemoteOKHtmlFallback:
    """Tests for the RemoteOK HTML fallback path."""

    @pytest.fixture()
    def html_content(self) -> str:
        """Load the RemoteOK HTML fixture."""
        return (FIXTURES_DIR / "remoteok_sample.html").read_text(encoding="utf-8")

    @respx.mock
    async def test_falls_back_to_html_on_api_failure(self, html_content: str) -> None:
        # API returns 500 → triggers fallback
        respx.get(API_URL).mock(return_value=httpx.Response(500))
        respx.get(FALLBACK_URL).mock(
            return_value=httpx.Response(200, text=html_content)
        )

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()

        # HTML fixture: NLP Engineer matches AI keywords, DevOps does not
        assert len(jobs) == 1
        assert jobs[0].title == "NLP Engineer"
        assert jobs[0].company == "LangAI"
        assert "nlp" in jobs[0].tags

    @respx.mock
    async def test_html_excludes_non_ai_jobs(self, html_content: str) -> None:
        respx.get(API_URL).mock(return_value=httpx.Response(500))
        respx.get(FALLBACK_URL).mock(
            return_value=httpx.Response(200, text=html_content)
        )

        scraper = RemoteOKScraper()
        jobs = await scraper.scrape()
        titles = {j.title for j in jobs}

        assert "DevOps Engineer" not in titles


# ---------------------------------------------------------------------------
# WeWorkRemotely Scraper Tests
# ---------------------------------------------------------------------------


class TestWeWorkRemotely:
    """Tests for the WeWorkRemotely HTML scraper."""

    @pytest.fixture()
    def html_content(self) -> str:
        """Load the WWR HTML fixture."""
        return (FIXTURES_DIR / "weworkremotely_sample.html").read_text(encoding="utf-8")

    @respx.mock
    async def test_parses_ai_jobs(self, html_content: str) -> None:
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=html_content))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()

        # Fixture has 3 jobs: "Senior AI Engineer" and "Machine Learning Researcher"
        # match AI keywords. "UX Designer" does not.
        assert len(jobs) == 2
        titles = {j.title for j in jobs}
        assert "Senior AI Engineer" in titles
        assert "Machine Learning Researcher" in titles

    @respx.mock
    async def test_excludes_non_ai_jobs(self, html_content: str) -> None:
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=html_content))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()
        titles = {j.title for j in jobs}

        assert "UX Designer" not in titles

    @respx.mock
    async def test_job_fields_populated(self, html_content: str) -> None:
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=html_content))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()
        ai_job = next(j for j in jobs if "AI Engineer" in j.title)

        assert ai_job.company == "NeuralWorks"
        assert ai_job.location == "San Francisco, CA"
        assert ai_job.salary == "$150,000 - $200,000 USD"
        assert ai_job.source == "weworkremotely"
        assert ai_job.url.startswith("https://weworkremotely.com")
        # "Featured" tag should be filtered out
        assert "Featured" not in ai_job.tags

    @respx.mock
    async def test_skips_view_all_links(self, html_content: str) -> None:
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=html_content))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()

        # Should not have any job with "View all" in the title
        for job in jobs:
            assert "View all" not in job.title

    @respx.mock
    async def test_falls_back_to_category_url(self, html_content: str) -> None:
        # Search returns 403 (Cloudflare) → falls back to category URL
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(403))
        respx.get(CATEGORY_URL).mock(
            return_value=httpx.Response(200, text=html_content)
        )

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()

        assert len(jobs) == 2

    @respx.mock
    async def test_returns_empty_on_network_error(self) -> None:
        respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
        respx.get(CATEGORY_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()

        assert jobs == []

    @respx.mock
    async def test_returns_empty_on_500(self) -> None:
        respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))
        respx.get(CATEGORY_URL).mock(return_value=httpx.Response(500))

        scraper = WeWorkRemotelyScraper()
        jobs = await scraper.scrape()

        assert jobs == []


# ---------------------------------------------------------------------------
# HackerNews Scraper Tests
# ---------------------------------------------------------------------------


class TestHackerNews:
    """Tests for the HackerNews 'Who is hiring?' scraper."""

    @pytest.fixture()
    def story_json(self) -> dict:
        """Load the HN story search fixture."""
        return json.loads(
            (FIXTURES_DIR / "hackernews_story.json").read_text(encoding="utf-8")
        )

    @pytest.fixture()
    def comments_json(self) -> dict:
        """Load the HN comments fixture."""
        return json.loads(
            (FIXTURES_DIR / "hackernews_comments.json").read_text(encoding="utf-8")
        )

    @pytest.fixture()
    def comments_url(self) -> str:
        """Return the expected comments URL for the fixture story."""
        return COMMENTS_URL_TEMPLATE.format(story_id="99999999")

    @respx.mock
    async def test_parses_ai_jobs_from_comments(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()

        # Fixture: 7 comments — 3 AI-relevant top-level, 1 non-AI top-level,
        # 1 reply, 1 URL-only garbage, 1 too-short garbage. Should return 3 jobs.
        assert len(jobs) == 3
        companies = {j.company for j in jobs}
        assert "Acme AI" in companies
        assert "NeuroLabs" in companies

    @respx.mock
    async def test_excludes_non_ai_comments(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        companies = {j.company for j in jobs}

        # "CoolWeb Inc" is a frontend job — should be excluded
        assert "CoolWeb Inc" not in companies

    @respx.mock
    async def test_filters_out_replies(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        ids = {j.id for j in jobs}

        # Comment 88880004 is a reply, not a top-level posting
        assert "hackernews_88880004" not in ids

    @respx.mock
    async def test_job_fields_populated(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        acme_job = next(j for j in jobs if j.company == "Acme AI")

        assert "LLM" in acme_job.title or "llm" in [t.lower() for t in acme_job.tags]
        assert acme_job.source == "hackernews"
        assert acme_job.url.startswith("https://news.ycombinator.com/item?id=")
        assert acme_job.posted_at is not None
        assert len(acme_job.tags) > 0

    @respx.mock
    async def test_extracts_ai_tags(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        acme_job = next(j for j in jobs if j.company == "Acme AI")

        assert "llm" in acme_job.tags
        assert "deep learning" in acme_job.tags

    @respx.mock
    async def test_rejects_garbage_comments(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        """URL-only comments and too-short text must be rejected."""
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        ids = {j.id for j in jobs}

        # URL-only comment (ebay link)
        assert "hackernews_88880005" not in ids
        # Too-short comment ("We are hiring")
        assert "hackernews_88880006" not in ids

    @respx.mock
    async def test_strips_urls_from_title(
        self, story_json: dict, comments_json: dict, comments_url: str
    ) -> None:
        """Titles must not contain raw URLs."""
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json=story_json)
        )
        respx.get(comments_url).mock(
            return_value=httpx.Response(200, json=comments_json)
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()
        url_job = next(j for j in jobs if j.id == "hackernews_88880007")

        assert "https://" not in url_job.title
        assert "http://" not in url_job.title
        assert "Machine Learning Engineer" in url_job.title

    @respx.mock
    async def test_returns_empty_on_no_story(self) -> None:
        respx.get(STORY_SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"hits": []})
        )

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()

        assert jobs == []

    @respx.mock
    async def test_returns_empty_on_network_error(self) -> None:
        respx.get(STORY_SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()

        assert jobs == []

    @respx.mock
    async def test_returns_empty_on_500(self) -> None:
        respx.get(STORY_SEARCH_URL).mock(return_value=httpx.Response(500))

        scraper = HackerNewsScraper()
        jobs = await scraper.scrape()

        assert jobs == []


# ---------------------------------------------------------------------------
# AI Keyword Matching Unit Tests
# ---------------------------------------------------------------------------


class TestAIKeywordMatching:
    """Tests for the word-boundary AI keyword matching logic."""

    def test_matches_llms_plural(self) -> None:
        """The plural 'LLMs' must be recognized as an AI keyword."""
        assert BaseScraper.matches_ai_keywords("Working with LLMs and embeddings")
        assert BaseScraper.matches_ai_keywords("Our team builds production llms")

    def test_rejects_ai_as_substring(self) -> None:
        """Words containing 'ai' as a substring must not trigger a match."""
        assert not BaseScraper.matches_ai_keywords(
            "Send us an email and maintain availability"
        )
        assert not BaseScraper.matches_ai_keywords("Detailed campaign domain work")

    def test_matches_new_keywords(self) -> None:
        """Newly added keywords (gpt, claude, openai, etc.) must match."""
        assert BaseScraper.matches_ai_keywords("Experience with GPT-4 required")
        assert BaseScraper.matches_ai_keywords("Building on Claude and OpenAI APIs")
        assert BaseScraper.matches_ai_keywords("Anthropic partnership team")
        assert BaseScraper.matches_ai_keywords("Fine-tuning large models")
        assert BaseScraper.matches_ai_keywords("Vector database experience needed")
