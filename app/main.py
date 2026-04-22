"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from app.config import settings
from app.routes.jobs import router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(
    title="AIJobRadar",
    description=(
        "A production-quality API that scrapes AI/ML job listings from "
        "multiple remote job boards, normalizes them into a unified schema, "
        "and serves them via a REST API."
    ),
    version="1.0.0",
)

app.include_router(router)


@app.get(
    "/",
    summary="Welcome",
    description="Root endpoint with links to documentation and job listings.",
)
async def root() -> dict:
    """Return welcome message with navigation links."""
    return {
        "message": "Welcome to AIJobRadar",
        "docs": "/docs",
        "jobs": "/jobs",
        "sources": "/sources",
        "health": "/health",
    }
