"""JSON file-based cache for scraped job listings."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.models import Job

logger = logging.getLogger(__name__)


class JobCache:
    """Reads and writes Job objects to a JSON file with TTL-based freshness.

    Cache file structure:
        {"updated_at": "2026-04-22T10:00:00Z", "jobs": [...]}
    """

    def __init__(self, path: Path, ttl_minutes: int) -> None:
        self._path = path
        self._ttl_minutes = ttl_minutes

    def is_fresh(self) -> bool:
        """Return True if the cache file exists and is within its TTL."""
        last = self.last_updated
        if last is None:
            return False
        age_seconds = (datetime.now(UTC) - last).total_seconds()
        return age_seconds < self._ttl_minutes * 60

    def read(self) -> list[Job] | None:
        """Read cached jobs from disk. Returns None if file is missing or corrupt."""
        if not self._path.exists():
            logger.debug("Cache file does not exist: %s", self._path)
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return [Job.model_validate(j) for j in raw["jobs"]]
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to read cache file: %s", exc)
            return None

    def write(self, jobs: list[Job]) -> None:
        """Write jobs to the cache file, creating parent directories if needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "jobs": [j.model_dump(mode="json") for j in jobs],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Cache written: %d jobs to %s", len(jobs), self._path)

    def invalidate(self) -> None:
        """Delete the cache file if it exists."""
        if self._path.exists():
            self._path.unlink()
            logger.info("Cache invalidated: %s", self._path)

    @property
    def last_updated(self) -> datetime | None:
        """Return the timestamp of the last cache write, or None."""
        if not self._path.exists():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return datetime.fromisoformat(raw["updated_at"])
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Failed to read cache timestamp: %s", exc)
            return None
