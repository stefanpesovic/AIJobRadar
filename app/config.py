"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AIJobRadar configuration with sensible defaults.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    CACHE_TTL_MINUTES: int = 60
    REQUEST_TIMEOUT_SECONDS: int = 15
    MAX_JOBS_PER_SOURCE: int = 100
    LOG_LEVEL: str = "INFO"
    CACHE_FILE_PATH: Path = Path("data/jobs_cache.json")
    USER_AGENT: str = (
        "Mozilla/5.0 (AIJobRadar/1.0; +https://github.com/YOUR_USERNAME/aijobradar)"
    )
    AI_KEYWORDS: list[str] = [
        "ai",
        "artificial intelligence",
        "machine learning",
        "ml engineer",
        "deep learning",
        "llm",
        "large language model",
        "nlp",
        "mlops",
        "pytorch",
        "tensorflow",
        "generative ai",
        "genai",
        "rag",
        "computer vision",
        "data scientist",
        "ai engineer",
        "prompt engineer",
        "langchain",
        "transformer",
        "neural network",
        "ai researcher",
        "foundation model",
        "agent",
        "autonomous agent",
    ]


settings = Settings()
