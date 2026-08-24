"""
Ingestion API — endpoints for uploading and querying transaction batches.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from models.transaction import TransactionBatchIn
from services import ingestion_service

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])


@router.post("/", summary="Ingest a batch of transactions")
def ingest_transactions(payload: TransactionBatchIn):
    """
    Accept a JSON batch of transactions and store them as a new queued batch.

    **Request body example:**
    ```json
    {
      "transactions": [
        {"items": ["A", "B", "C"], "utilities": [5, 3, 8]},
        {"items": ["B", "D"],      "utilities": [2, 7]}
      ]
    }
    ```
    """
    # Validate items ↔ utilities length match
    for i, txn in enumerate(payload.transactions):
        if len(txn.items) != len(txn.utilities):
            raise HTTPException(
                status_code=422,
                detail=f"Transaction {i}: items and utilities must have equal length.",
            )

    result = ingestion_service.ingest_batch(payload.transactions)
    return result


@router.get("/", summary="List transactions by batch")
def get_transactions(batch_id: int = Query(..., description="Batch ID to query")):
    """Return all transactions belonging to the specified batch."""
    txns = ingestion_service.get_transactions_by_batch(batch_id)
    if not txns:
        raise HTTPException(status_code=404, detail="Batch not found or empty.")
    return {"batch_id": batch_id, "transactions": txns}


@router.get("/batches", summary="List all batches")
def list_batches():
    """Return a summary of every batch (id, status, transaction count)."""
    return {"batches": ingestion_service.get_all_batches()}
