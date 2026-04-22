"""Tests for the JobCache class."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.cache import JobCache
from app.models import Job


def _make_job(id_suffix: str = "1") -> Job:
    """Create a sample Job for testing."""
    return Job(
        id=f"remoteok_{id_suffix}",
        title="ML Engineer",
        company="TestCorp",
        url="https://example.com/job",
        source="remoteok",
        tags=["ai", "python"],
        scraped_at=datetime.now(UTC),
    )


@pytest.fixture()
def cache_path(tmp_path: Path) -> Path:
    """Return a temporary cache file path."""
    return tmp_path / "test_cache.json"


@pytest.fixture()
def cache(cache_path: Path) -> JobCache:
    """Return a JobCache instance with a 60-minute TTL."""
    return JobCache(path=cache_path, ttl_minutes=60)


class TestIsFresh:
    """Tests for the is_fresh() method."""

    def test_missing_file_is_not_fresh(self, cache: JobCache) -> None:
        assert cache.is_fresh() is False

    def test_fresh_cache_within_ttl(self, cache: JobCache) -> None:
        cache.write([_make_job()])
        assert cache.is_fresh() is True

    def test_stale_cache_beyond_ttl(self, cache_path: Path) -> None:
        stale_time = datetime.now(UTC) - timedelta(minutes=120)
        payload = {
            "updated_at": stale_time.isoformat(),
            "jobs": [_make_job().model_dump(mode="json")],
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

        cache = JobCache(path=cache_path, ttl_minutes=60)
        assert cache.is_fresh() is False

    def test_short_ttl_expires_quickly(self, cache_path: Path) -> None:
        # Write with a timestamp just barely past a 1-minute TTL
        old_time = datetime.now(UTC) - timedelta(seconds=90)
        payload = {
            "updated_at": old_time.isoformat(),
            "jobs": [],
        }
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

        cache = JobCache(path=cache_path, ttl_minutes=1)
        assert cache.is_fresh() is False


class TestWriteRead:
    """Tests for write/read roundtrip."""

    def test_roundtrip_single_job(self, cache: JobCache) -> None:
        jobs = [_make_job()]
        cache.write(jobs)
        result = cache.read()

        assert result is not None
        assert len(result) == 1
        assert result[0].id == "remoteok_1"
        assert result[0].title == "ML Engineer"
        assert result[0].company == "TestCorp"
        assert result[0].tags == ["ai", "python"]

    def test_roundtrip_multiple_jobs(self, cache: JobCache) -> None:
        jobs = [_make_job("1"), _make_job("2"), _make_job("3")]
        cache.write(jobs)
        result = cache.read()

        assert result is not None
        assert len(result) == 3
        assert {j.id for j in result} == {
            "remoteok_1",
            "remoteok_2",
            "remoteok_3",
        }

    def test_roundtrip_empty_list(self, cache: JobCache) -> None:
        cache.write([])
        result = cache.read()

        assert result is not None
        assert len(result) == 0

    def test_read_missing_file_returns_none(self, cache: JobCache) -> None:
        assert cache.read() is None

    def test_read_corrupt_json_returns_none(
        self, cache: JobCache, cache_path: Path
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("not valid json{{{", encoding="utf-8")
        assert cache.read() is None

    def test_read_missing_jobs_key_returns_none(
        self, cache: JobCache, cache_path: Path
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = '{"updated_at": "2026-01-01T00:00:00Z"}'
        cache_path.write_text(payload, encoding="utf-8")
        assert cache.read() is None

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c" / "cache.json"
        cache = JobCache(path=nested, ttl_minutes=60)
        cache.write([_make_job()])

        assert nested.exists()
        result = cache.read()
        assert result is not None
        assert len(result) == 1


class TestInvalidate:
    """Tests for the invalidate() method."""

    def test_invalidate_removes_file(self, cache: JobCache, cache_path: Path) -> None:
        cache.write([_make_job()])
        assert cache_path.exists()

        cache.invalidate()
        assert not cache_path.exists()

    def test_invalidate_nonexistent_file_is_noop(self, cache: JobCache) -> None:
        # Should not raise
        cache.invalidate()

    def test_cache_not_fresh_after_invalidate(self, cache: JobCache) -> None:
        cache.write([_make_job()])
        assert cache.is_fresh() is True

        cache.invalidate()
        assert cache.is_fresh() is False

    def test_read_returns_none_after_invalidate(self, cache: JobCache) -> None:
        cache.write([_make_job()])
        cache.invalidate()
        assert cache.read() is None


class TestLastUpdated:
    """Tests for the last_updated property."""

    def test_last_updated_none_when_missing(self, cache: JobCache) -> None:
        assert cache.last_updated is None

    def test_last_updated_after_write(self, cache: JobCache) -> None:
        before = datetime.now(UTC)
        cache.write([_make_job()])
        after = datetime.now(UTC)

        last = cache.last_updated
        assert last is not None
        assert before <= last <= after

    def test_last_updated_none_on_corrupt_file(
        self, cache: JobCache, cache_path: Path
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("broken", encoding="utf-8")
        assert cache.last_updated is None
