"""Events API — Faz 4 (Gün 15) kapsamında tam implement edilecek."""
from fastapi import APIRouter, Query
from typing import List, Optional
from datetime import date

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    # TODO Faz 4: DB sorgusu
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/stats/daily")
async def daily_stats(target_date: Optional[date] = None):
    # TODO Faz 4: TimescaleDB aggregation
    return {"date": str(target_date or date.today()), "total": 0, "by_type": {}, "high_risk_events": 0}


@router.get("/{event_id}")
async def get_event(event_id: str):
    # TODO Faz 4
    return {"error": "Faz 4'te implement edilecek"}
