# Changelog

All notable changes to AIJobRadar are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-04-22

### Added
- Initial release
- Three scrapers: RemoteOK (JSON API), WeWorkRemotely (HTML), Hacker News (Algolia API)
- JSON file cache with configurable TTL
- REST API with `/jobs`, `/sources`, `/refresh`, `/health`, `/` endpoints
- Filtering by keyword, company, location, and source
- Pagination with configurable page size (max 100)
- Async orchestration via httpx and asyncio
- Auto-generated Swagger docs at `/docs`
- 66-test suite with 89% coverage
- GitHub Actions CI with ruff, black, pytest
- Dockerfile for containerized deployment
