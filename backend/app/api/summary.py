"""Raporlama ve Soru-Cevap API'leri — Faz 6 (Gün 22–23).

- POST /api/summary/generate     → günün (veya verilen tarihin) özetini üret
- GET  /api/summary/daily/{date} → kayıtlı günlük özet
- GET  /api/summary              → son özetlerin listesi
- POST /api/query                → doğal dil soru-cevap (keyword → SQL → cevap)
"""
from datetime import datetime, timezone
# NOT: "date" tipi doğrudan import edilmez — SummaryGenerateRequest.date alan
# adı tip adını gölgeleyip Pydantic anotasyonunu NoneType'a çözümletiyor.
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.db import crud
from app.events.schemas import EventResponse
from app.llm.gemma import gemma
from app.llm.qa import answer_question
from app.llm.summary import generate_daily_summary

router = APIRouter(prefix="/api", tags=["reports"])


# ── Şemalar ──────────────────────────────────────────────────────────────────────

class SummaryGenerateRequest(BaseModel):
    date: Optional[date_type] = None   # verilmezse bugün (UTC)
    force: bool = False           # true → var olan özetin üzerine yeniden üret


class SummaryResponse(BaseModel):
    summary_date: str
    total_events: int
    high_risk_events: int
    event_breakdown: dict
    summary_text: str
    source: str                   # "gemma" | "template"
    created_at: datetime


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class QueryResponse(BaseModel):
    question: str
    answer: str
    intent: dict
    total: int
    events: list[EventResponse]


def _summary_row_to_response(row) -> SummaryResponse:
    breakdown = row.event_breakdown or {}
    return SummaryResponse(
        # Sütun DATE — yanıtta ISO string'e normalize edilir
        summary_date=str(row.summary_date),
        total_events=row.total_events,
        high_risk_events=row.high_risk_events,
        event_breakdown=breakdown,
        summary_text=row.summary_text or "",
        source=breakdown.get("source", "template"),
        created_at=row.created_at,
    )


# ── Günlük Özet ──────────────────────────────────────────────────────────────────

@router.post("/summary/generate", response_model=SummaryResponse)
async def generate_summary(
    payload: SummaryGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verilen tarihin (varsayılan: bugün) özetini üretir ve kaydeder.
    Özet zaten varsa ve force=false ise mevcut kayıt döndürülür."""
    target = payload.date or datetime.now(timezone.utc).date()
    if target > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=400, detail="Gelecek tarih için özet üretilemez")
    row = await generate_daily_summary(db, target, force=payload.force)
    return _summary_row_to_response(row)


@router.get("/summary", response_model=list[SummaryResponse])
async def list_summaries(
    limit: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    rows = await crud.list_daily_summaries(db, limit=limit)
    return [_summary_row_to_response(r) for r in rows]


@router.get("/summary/daily/{target_date}", response_model=SummaryResponse)
async def get_summary(target_date: date_type, db: AsyncSession = Depends(get_db)):
    row = await crud.get_daily_summary(db, target_date.isoformat())
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Bu tarih için özet yok — POST /api/summary/generate ile üretebilirsiniz",
        )
    return _summary_row_to_response(row)


# ── Soru-Cevap ───────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, db: AsyncSession = Depends(get_db)):
    """Doğal dil soru-cevap (Roadmap §5.9 — MVP: keyword → SQL → şablon cevap;
    Gemma yüklüyse cevap LLM ile akıcılaştırılır)."""
    return await answer_question(db, payload.question)


@router.get("/assistant/status", tags=["reports"])
async def assistant_status():
    """Asistanın hangi modda çalıştığı (panel bilgi rozetii için)."""
    return {"llm_loaded": gemma.available, "mode": "gemma" if gemma.available else "template"}
