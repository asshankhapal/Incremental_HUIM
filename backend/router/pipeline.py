"""
Pipeline API — endpoints for triggering and monitoring the mining pipeline.
"""

from __future__ import annotations

import csv
import re
import tempfile

from fastapi import APIRouter, HTTPException, Request
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


def _parse_transaction_line(line: str) -> dict | None:
    """Parse one supported TXT/CSV transaction line without retaining the file."""
    line = line.strip()
    if not line or line.startswith(("#", "//")):
        return None

    parts = line.split(":")
    items: list[str] | None = None
    utilities: list[float] | None = None
    pair_tokens = [token for token in re.split(r"[\s,]+", line) if token]
    if len(pair_tokens) > 1 and all(token.count(":") == 1 for token in pair_tokens):
        # Per-item form: A:5,B:3,C:8
        try:
            items = [token.rsplit(":", 1)[0] for token in pair_tokens]
            utilities = [float(token.rsplit(":", 1)[1]) for token in pair_tokens]
        except ValueError:
            return None
    elif len(parts) == 3:  # SPMF: items:transaction-utility:item-utilities
        items = [item for item in parts[0].replace(",", " ").split() if item]
        try:
            utilities = [float(value) for value in parts[2].replace(",", " ").split()]
        except ValueError:
            return None
    elif len(parts) == 2:  # items:utilities
        items = [item for item in parts[0].replace(",", " ").split() if item]
        try:
            utilities = [float(value) for value in parts[1].replace(",", " ").split()]
        except ValueError:
            return None
    elif "|" in line or "\t" in line:
        separator = "|" if "|" in line else "\t"
        left, right, *_ = line.split(separator)
        items = [item for item in left.strip().strip('"').replace(",", " ").split() if item]
        try:
            utilities = [float(value) for value in right.strip().strip('"').replace(",", " ").split()]
        except ValueError:
            return None
    else:
        # CSV with two quoted columns: "A,B,C","5,3,8"
        try:
            columns = next(csv.reader([line]))
        except (csv.Error, StopIteration):
            return None
        if len(columns) == 2:
            items = [item for item in columns[0].replace(",", " ").split() if item]
            try:
                utilities = [float(value) for value in columns[1].replace(",", " ").split()]
            except ValueError:
                return None
        elif len(columns) > 2:
            # Plain comma/semicolon rows: A;B;C;5;3;8
            tokens = [token for token in re.split(r"[\s,;]+", line) if token]
            split_at = next((index for index, token in enumerate(tokens)
                             if re.fullmatch(r"-?\d+(?:\.\d+)?", token)), -1)
            if split_at > 0:
                items = tokens[:split_at]
                try:
                    utilities = [float(value) for value in tokens[split_at:]]
                except ValueError:
                    return None

    if not items or not utilities or len(items) != len(utilities):
        return None
    return {"items": items, "utilities": utilities}


@router.post("/run-dataset-file", summary="Stream a CSV/TXT dataset through the existing pipeline")
async def run_dataset_file(request: Request, batch_size: int = 100, top_k: int = 10):
    """Spool the upload to disk, then parse and process it in bounded batches."""
    if batch_size <= 0 or top_k <= 0:
        raise HTTPException(status_code=422, detail="batch_size and top_k must be positive integers.")
    try:
        # Do not build a giant request JSON array in memory. TemporaryFile is
        # automatically removed after the request, and the iterator below only
        # keeps one transaction batch alive.
        with tempfile.TemporaryFile(mode="w+b") as uploaded:
            async for chunk in request.stream():
                uploaded.write(chunk)
            uploaded.seek(0)

            parsed_count = 0

            def transactions():
                nonlocal parsed_count
                first_data_line = True
                for raw_line in uploaded:
                    line = raw_line.decode("utf-8-sig").strip()
                    if first_data_line and ("item" in line.lower() or "util" in line.lower()):
                        first_data_line = False
                        continue
                    if line and not line.startswith(("#", "//")):
                        first_data_line = False
                    transaction = _parse_transaction_line(line)
                    if transaction:
                        parsed_count += 1
                        yield transaction

            result = mining_service.run_dataset_stream(transactions(), batch_size, top_k)
        if parsed_count == 0:
            raise HTTPException(status_code=422, detail="No valid transactions were found in the uploaded file.")
        result["transaction_count"] = parsed_count
        return result
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
