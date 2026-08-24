"""
Mining Service — bridges the API layer with the core pipeline.
"""

from __future__ import annotations

import json
import logging

from config import config
from database import get_db, clear_db
from core.pipeline import Pipeline
from services import ingestion_service
from models.transaction import TransactionIn

logger = logging.getLogger(__name__)

# Module-level pipeline instance (re-initialised on each run to pick up
# fresh DB state).
_pipeline: Pipeline | None = None


def run_pipeline() -> dict:
    """
    Instantiate a fresh pipeline and execute a single run.

    Returns the summary dict produced by Pipeline.run().
    """
    global _pipeline
    _pipeline = Pipeline()
    return _pipeline.run()


def get_last_run_status() -> dict | None:
    """Return the most recent pipeline run record, if any."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT run_id, started_at, finished_at, status, details
            FROM pipeline_runs
            ORDER BY run_id DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row["run_id"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "status": row["status"],
        "details": json.loads(row["details"]) if row["details"] else None,
    }


def get_run_history(limit: int = 20) -> list[dict]:
    """Return the last N pipeline runs."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT run_id, started_at, finished_at, status
            FROM pipeline_runs
            ORDER BY run_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def run_dataset(transactions: list[TransactionIn] | list[dict], batch_size: int, top_k: int) -> dict:
    """
    Clear DB, update config, slice transactions into batches, ingest them sequentially,
    run the pipeline for each batch, and return the aggregated results.
    """
    # 1. Clear database state
    clear_db()

    # Convert to TransactionIn objects if we got raw dicts
    txns_in = []
    for t in transactions:
        if isinstance(t, dict):
            txns_in.append(TransactionIn(**t))
        else:
            txns_in.append(t)

    # 2. Backup current config settings
    orig_top_k = config.top_k
    orig_top_n = config.top_n_results
    orig_trigger_size = config.batch_trigger_size

    # Temporarily adjust configuration parameters
    config.top_k = top_k
    config.top_n_results = top_k
    config.batch_trigger_size = batch_size

    # 3. Partition transactions into sequential batches of size batch_size
    total_batches = 0
    total_timings = {
        "phase1_ms": 0.0,
        "phase2_ms": 0.0,
        "phase3_ms": 0.0,
        "phase4_ms": 0.0,
        "phase5_ms": 0.0,
    }
    
    final_top_results = []
    
    try:
        # Batching
        for i in range(0, len(txns_in), batch_size):
            batch_slice = txns_in[i : i + batch_size]
            # Ingest batch
            ingestion_service.ingest_batch(batch_slice)
            
            # Execute a single incremental pipeline step
            pipeline = Pipeline()
            run_summary = pipeline.run()
            
            total_batches += 1
            if "timings" in run_summary:
                for phase, ms in run_summary["timings"].items():
                    total_timings[phase] = total_timings.get(phase, 0.0) + ms
            
            if run_summary.get("status") == "success" and "top_results" in run_summary:
                final_top_results = run_summary["top_results"]

    finally:
        # Restore configuration settings
        config.top_k = orig_top_k
        config.top_n_results = orig_top_n
        config.batch_trigger_size = orig_trigger_size

    return {
        "total_batches": total_batches,
        "timings": total_timings,
        "top_results": final_top_results,
        "status": "success",
    }
