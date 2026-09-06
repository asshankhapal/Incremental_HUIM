"""
Centralized configuration for the Incremental HUIM pipeline.

All tuneable constants live here so they can be adjusted at runtime
via the /api/config endpoint or before server start.
"""

import os
from dataclasses import dataclass, field, asdict

# Compute an absolute path so the DB is always in the backend/ directory
# regardless of the working directory used by uvicorn or reloader.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class PipelineConfig:
    """Mutable pipeline configuration — one global instance is shared."""

    # ── Phase 1: Sliding Window ──────────────────────────────────────
    window_size: int = 1000            # Max transactions kept in the window
    time_threshold: int = 1800         # Seconds between automatic triggers
    batch_trigger_size: int = 1000     # Queued-transaction count trigger

    # ── Phase 3: HDkT ────────────────────────────────────────────────
    stale_limit: int = 5               # Batches before a pattern is stale
    top_k: int = 10                    # Number of top patterns to mine

    # ── Phase 5: Historical Validation ───────────────────────────────
    decay_factor: float = 0.9          # Decay multiplier applied per batch
    hashmap_capacity: int = 10_000     # Max patterns stored in the tracker
    top_n_results: int = 20            # Recommendations returned to caller

    # ── Database ─────────────────────────────────────────────────────
    db_path: str = os.path.join(_BASE_DIR, "huim.db")
    
    # ── Redis Queue ──────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    def to_dict(self) -> dict:
        return asdict(self)


# Single global config instance
config = PipelineConfig()
