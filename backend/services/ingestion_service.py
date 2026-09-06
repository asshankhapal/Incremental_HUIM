"""
Ingestion Service — handles parsing and storing incoming transaction batches.
"""

from __future__ import annotations

import json
from typing import List

from database import get_db
from models.transaction import TransactionIn


def ingest_batch(transactions: List[TransactionIn]) -> dict:
    """
    Store a list of transactions in the Redis queue.

    Returns
    -------
    dict with transaction_count and status.
    """
    from redis_client import redis_client

    if not transactions:
        return {"transaction_count": 0, "status": "empty"}

    serialized_txns = [txn.model_dump_json() for txn in transactions]
    redis_client.rpush('huim:transaction_queue', *serialized_txns)

    return {
        "batch_id": None,
        "transaction_count": len(transactions),
        "status": "queued_in_redis",
    }


def get_transactions_by_batch(batch_id: int) -> list[dict]:
    """Return all transactions for a given batch_id."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tid, batch_id, items, utilities FROM transactions WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
    return [
        {
            "tid": r["tid"],
            "batch_id": r["batch_id"],
            "items": json.loads(r["items"]),
            "utilities": json.loads(r["utilities"]),
        }
        for r in rows
    ]


def get_all_batches() -> list[dict]:
    """Return a summary of all batches."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT b.batch_id, b.created_at, b.status, COUNT(t.tid) AS txn_count
            FROM batches b
            LEFT JOIN transactions t ON b.batch_id = t.batch_id
            GROUP BY b.batch_id
            ORDER BY b.batch_id DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]
