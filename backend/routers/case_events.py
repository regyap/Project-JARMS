from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.supabase import supabase

router = APIRouter()


# =========================
# Pydantic Schemas
# =========================


class CaseEventCreate(BaseModel):
    case_id: str = Field(..., description="Parent case UUID")
    event_type: str = Field(
        ..., description="created, triaged, callback_attempted, escalated, closed"
    )
    event_source: str = Field(
        ..., description="frontend, triage_ai, operator_ui, worker"
    )
    payload_json: Dict[str, Any] = Field(default_factory=dict)


class CaseEventUpdate(BaseModel):
    event_type: Optional[str] = None
    event_source: Optional[str] = None
    payload_json: Optional[Dict[str, Any]] = None


class CaseEventResponse(BaseModel):
    event_id: str
    case_id: str
    event_type: str
    event_source: str
    payload_json: Dict[str, Any]
    created_at: str


# =========================
# CRUD Endpoints
# =========================


@router.post("/", response_model=List[CaseEventResponse])
async def create_case_event(payload: CaseEventCreate):
    """
    Create a case event.
    Example use: simulate frontend sending audio metadata, button_id, transcript hints, etc.
    """
    try:
        response = supabase.table("case_events").insert(payload.model_dump()).execute()

        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create case event: {e}")


@router.get("/", response_model=List[CaseEventResponse])
async def list_case_events(
    case_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """
    List case events.
    Optionally filter by case_id.
    """
    try:
        query = (
            supabase.table("case_events")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if case_id:
            query = query.eq("case_id", case_id)

        response = query.execute()
        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list case events: {e}")


@router.get("/{event_id}", response_model=CaseEventResponse)
async def get_case_event(event_id: str):
    """
    Get a single case event by event_id.
    """
    try:
        response = (
            supabase.table("case_events")
            .select("*")
            .eq("event_id", event_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Case event not found")

        return response.data[0]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get case event: {e}")


@router.patch("/{event_id}", response_model=List[CaseEventResponse])
async def update_case_event(event_id: str, payload: CaseEventUpdate):
    """
    Update a case event.
    Only provided fields will be updated.
    """
    try:
        update_data = payload.model_dump(exclude_none=True)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        response = (
            supabase.table("case_events")
            .update(update_data)
            .eq("event_id", event_id)
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Case event not found")

        return response.data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update case event: {e}")


@router.delete("/{event_id}")
async def delete_case_event(event_id: str):
    """
    Delete a case event.
    """
    try:
        response = (
            supabase.table("case_events").delete().eq("event_id", event_id).execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Case event not found")

        return {
            "success": True,
            "message": f"Case event {event_id} deleted",
            "deleted": response.data,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete case event: {e}")
