"""
Incremental HUIM — FastAPI Application Entry Point

Registers all routers, initialises the database on startup,
and configures CORS + logging.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from router.ingest import router as ingest_router
from router.pipeline import router as pipeline_router
from router.results import router as results_router
from router.config_router import router as config_router

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the SQLite database on startup."""
    logger.info("Initialising database …")
    init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")

app = FastAPI(
    title="Incremental HUIM Pipeline",
    description=(
        "5-phase incremental High-Utility Itemset Mining backend. "
        "Ingest transaction batches, trigger the mining pipeline, "
        "and query ranked top-k HUI patterns."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────
app.include_router(ingest_router)
app.include_router(pipeline_router)
app.include_router(results_router)
app.include_router(config_router)


# ── Root health-check ────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "service": "Incremental HUIM Pipeline",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }