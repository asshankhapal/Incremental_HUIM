"""
Results API — endpoints for querying mined patterns and rankings.
"""

from __future__ import annotations

import json
from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/results", tags=["Results"])


@router.get("/top-k", summary="Get current top-k HUI patterns")
def get_top_k(
    k: int = Query(default=10, ge=1, le=1000, description="Number of top patterns to return"),
):
    """
    Return the top-k patterns from the historical tracker,
    ranked by average utility (descending).
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT pattern_key, total_util, count, avg_util, last_seen_batch
            FROM pattern_tracker
            ORDER BY avg_util DESC
            LIMIT ?
            """,
            (k,),
        ).fetchall()

    results = [
        {
            "rank": i + 1,
            "pattern_key": r["pattern_key"],
            "avg_util": round(r["avg_util"], 4),
            "total_util": round(r["total_util"], 4),
            "count": r["count"],
            "last_seen_batch": r["last_seen_batch"],
        }
        for i, r in enumerate(rows)
    ]
    return {"top_k": results, "count": len(results)}


@router.get("/history", summary="Get full pattern tracker")
def get_pattern_history(
    limit: int = Query(default=100, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
):
    """
    Return all tracked patterns with pagination, ordered by avg_util desc.
    """
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pattern_tracker"
        ).fetchone()["cnt"]

        rows = conn.execute(
            """
            SELECT pattern_key, total_util, count, avg_util, last_seen_batch
            FROM pattern_tracker
            ORDER BY avg_util DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "patterns": [dict(r) for r in rows],
    }


@router.get("/stats", summary="Get pipeline statistics")
def get_stats():
    """Return aggregate statistics about the current state."""
    from redis_client import redis_client
    with get_db() as conn:
        batch_counts = conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM batches
            GROUP BY status
            """
        ).fetchall()

        total_txns = conn.execute(
            "SELECT COUNT(*) AS cnt FROM transactions"
        ).fetchone()["cnt"]

        total_patterns = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pattern_tracker"
        ).fetchone()["cnt"]

        total_runs = conn.execute(
            "SELECT COUNT(*) AS cnt FROM pipeline_runs"
        ).fetchone()["cnt"]

    queued_in_redis = redis_client.llen('huim:transaction_queue')

    return {
        "batches": {r["status"]: r["cnt"] for r in batch_counts},
        "queued_in_redis": queued_in_redis,
        "total_transactions": total_txns + queued_in_redis,
        "total_patterns_tracked": total_patterns,
        "total_pipeline_runs": total_runs,
    }
