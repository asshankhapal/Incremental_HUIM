"""
Pipeline API — endpoints for triggering and monitoring the mining pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
from models.transaction import TransactionIn
from services import mining_service

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


@router.post("/run", summary="Trigger a pipeline run")
def run_pipeline():
    """
    Manually trigger the full 5-phase pipeline.

    The pipeline will:
    1. Pull the next queued batch into the sliding window.
    2. Update prefix utilities and MRU.
    3. Compute the HDkT threshold.
    4. Mine top-k high-utility itemsets.
    5. Validate and rank results historically.

    Returns a detailed summary with per-phase timings.
    """
    try:
        result = mining_service.run_pipeline()
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", summary="Get last pipeline run status")
def pipeline_status():
    """Return the status and details of the most recent pipeline run."""
    status = mining_service.get_last_run_status()
    if status is None:
        return {"message": "No pipeline runs recorded yet."}
    return status


@router.get("/history", summary="Get pipeline run history")
def pipeline_history(limit: int = 20):
    """Return the last N pipeline run records."""
    runs = mining_service.get_run_history(limit)
    return {"runs": runs}


class RunDatasetPayload(BaseModel):
    transactions: List[TransactionIn]
    batch_size: int = Field(..., gt=0)
    top_k: int = Field(..., gt=0)


@router.post("/run-dataset", summary="Run pipeline over whole dataset batch-by-batch")
def run_dataset_pipeline(payload: RunDatasetPayload):
    """
    Ingest and process a full dataset batch-by-batch, clearing previous run state
    and returning final top-k patterns and aggregate stats.
    """
    try:
        result = mining_service.run_dataset(
            transactions=payload.transactions,
            batch_size=payload.batch_size,
            top_k=payload.top_k,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
