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
    Store a list of transactions as a new batch.

    Each call creates one batch record, then inserts all transactions
    linked to it.  The batch starts with status='queued' so Phase 1
    can pick it up on the next trigger.

    Returns
    -------
    dict with batch_id, transaction_count, and status.
    """
    with get_db() as conn:
        # Create the batch
        cursor = conn.execute(
            "INSERT INTO batches (status) VALUES ('queued')"
        )
        batch_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Insert transactions
        rows = [
            (
                batch_id,
                json.dumps(txn.items),
                json.dumps(txn.utilities),
            )
            for txn in transactions
        ]
        conn.executemany(
            "INSERT INTO transactions (batch_id, items, utilities) VALUES (?, ?, ?)",
            rows,
        )

    return {
        "batch_id": batch_id,
        "transaction_count": len(transactions),
        "status": "queued",
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
