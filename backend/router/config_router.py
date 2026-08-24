"""
Config API — endpoints for viewing and updating pipeline configuration at runtime.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from config import config

router = APIRouter(prefix="/api/config", tags=["Configuration"])


class ConfigUpdate(BaseModel):
    """Partial update schema — only provided fields are changed."""
    window_size: Optional[int] = Field(None, ge=1)
    time_threshold: Optional[int] = Field(None, ge=1)
    batch_trigger_size: Optional[int] = Field(None, ge=1)
    stale_limit: Optional[int] = Field(None, ge=1)
    top_k: Optional[int] = Field(None, ge=1)
    decay_factor: Optional[float] = Field(None, gt=0.0, le=1.0)
    hashmap_capacity: Optional[int] = Field(None, ge=1)
    top_n_results: Optional[int] = Field(None, ge=1)


@router.get("/", summary="Get current configuration")
def get_config():
    """Return all current pipeline configuration values."""
    return config.to_dict()


@router.put("/", summary="Update configuration")
def update_config(updates: ConfigUpdate):
    """
    Partially update the pipeline configuration.

    Only fields present in the request body are changed;
    omitted fields keep their current values.
    """
    changes = updates.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(config, key, value)

    return {
        "message": f"Updated {len(changes)} setting(s).",
        "updated_fields": list(changes.keys()),
        "config": config.to_dict(),
    }
