# AIJobRadar

A production-quality FastAPI service that scrapes AI/ML job listings from multiple remote job boards, normalizes them into a unified schema, caches results with TTL, and serves everything via a REST API.

## Features

- **Multi-source scraping** — Aggregates jobs from RemoteOK, WeWorkRemotely, and Hacker News "Who is hiring?" threads
- **AI/ML focused** — Filters listings using 25+ AI keywords (LLM, PyTorch, MLOps, computer vision, etc.)
- **Unified schema** — Every job is normalized into the same Pydantic model regardless of source
- **Smart caching** — JSON file cache with configurable TTL avoids hammering source sites
- **Filterable API** — Search by keyword, company, location, or source with pagination
- **Swagger docs** — Interactive API documentation at `/docs`
- **Fully tested** — 66 tests with 89% code coverage

## Tech Stack

| Component     | Choice                          |
|---------------|---------------------------------|
| Language      | Python 3.11+                    |
| Web framework | FastAPI                         |
| HTTP client   | httpx (async)                   |
| HTML parsing  | BeautifulSoup4 + lxml           |
| Validation    | Pydantic v2                     |
| Config        | pydantic-settings + .env        |
| Testing       | pytest + pytest-asyncio + respx |
| Server        | uvicorn                         |
| Linting       | ruff                            |
| Formatting    | black                           |

## Quickstart

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/aijobradar.git
cd aijobradar

# Create and activate a virtual environment (Python 3.11+)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Copy and configure environment variables
cp .env.example .env

# Start the server
python run.py
```

The API will be available at **http://localhost:8000**.

## API Endpoints

### `GET /` — Welcome

Returns navigation links to all endpoints.

### `GET /jobs` — List AI/ML Jobs

Returns paginated, filterable job listings.

**Query Parameters:**

| Param      | Type   | Default | Description                              |
|------------|--------|---------|------------------------------------------|
| `keyword`  | string | —       | Filter by keyword (title/company/tags)   |
| `company`  | string | —       | Filter by company name                   |
| `location` | string | —       | Filter by location                       |
| `source`   | string | —       | Filter by source (remoteok/weworkremotely/hackernews) |
| `page`     | int    | 1       | Page number                              |
| `limit`    | int    | 20      | Results per page (max 100)               |

All filters are case-insensitive substring matches.

**Example:**

```bash
curl "http://localhost:8000/jobs?keyword=llm&source=remoteok&limit=5"
```

### `GET /sources` — Source Status

Returns scrape time, job count, and error status for each source.

```bash
curl http://localhost:8000/sources
```

### `POST /refresh` — Force Re-scrape

Invalidates cache and re-scrapes all sources. Returns stats and duration.

```bash
curl -X POST http://localhost:8000/refresh
```

### `GET /health` — Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "1.0.0"}
```

### Swagger UI

Interactive documentation is available at **http://localhost:8000/docs**.

## Project Structure

```
aijobradar/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings via pydantic-settings
│   ├── models.py            # Pydantic data models
│   ├── cache.py             # JSON file cache with TTL
│   ├── routes/
│   │   ├── __init__.py
│   │   └── jobs.py          # API route handlers
│   └── scrapers/
│       ├── __init__.py
│       ├── base.py           # Abstract base scraper
│       ├── manager.py        # Scraper orchestration
│       ├── remoteok.py       # RemoteOK (JSON API + HTML fallback)
│       ├── weworkremotely.py # WeWorkRemotely (HTML scraper)
│       └── hackernews.py     # HN "Who is hiring?" (Algolia API)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures
│   ├── test_api.py           # API endpoint tests
│   ├── test_cache.py         # Cache layer tests
│   ├── test_scrapers.py      # Scraper tests with mocked HTTP
│   └── fixtures/             # Sample HTML/JSON for tests
├── data/                     # Cache directory
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── run.py
├── LICENSE
└── README.md
```

## Testing

```bash
# Run the full test suite
pytest

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run a specific test file
pytest tests/test_api.py -v
```

## Linting & Formatting

```bash
# Check for lint errors
ruff check app/ tests/

# Check formatting
black --check app/ tests/

# Auto-fix formatting
black app/ tests/
```

## Configuration

All settings can be overridden via environment variables or a `.env` file. See `.env.example` for the full list.

| Variable                 | Default                | Description                      |
|--------------------------|------------------------|----------------------------------|
| `CACHE_TTL_MINUTES`      | `60`                   | Cache freshness duration         |
| `REQUEST_TIMEOUT_SECONDS` | `15`                  | HTTP request timeout             |
| `MAX_JOBS_PER_SOURCE`    | `100`                  | Max jobs returned per scraper    |
| `LOG_LEVEL`              | `INFO`                 | Logging level                    |
| `CACHE_FILE_PATH`        | `data/jobs_cache.json` | Path to the cache file           |
| `USER_AGENT`             | `Mozilla/5.0 (AIJobRadar/1.0; ...)` | HTTP User-Agent header |

## Data Sources

| Source           | Method                    | Notes                                          |
|------------------|---------------------------|-------------------------------------------------|
| RemoteOK         | JSON API (`/api`)         | Falls back to HTML parsing if API fails         |
| WeWorkRemotely   | HTML scraping             | Category page fallback if search is blocked     |
| Hacker News      | Algolia API               | Parses latest "Who is hiring?" thread comments  |

## License

MIT
