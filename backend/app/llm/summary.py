"""Günlük Özet Servisi — Faz 6 (Gün 22–23).

Günün olaylarından yönetici raporu üretir:
1. İstatistik hesaplama (`build_summary_stats`) — saf, DB'siz, test edilebilir.
2. Metin üretimi — Gemma yüklüyse LLM (`build_gemma_prompt` + generate),
   değilse deterministik Türkçe şablon (`render_summary_text`). Gemma çıktısı
   alınamazsa her zaman şablona düşülür.
3. `generate_daily_summary` — DB'den olayları çeker, üretir, daily_summaries
   tablosuna upsert eder (gece 23:55 scheduler'ı ve POST /api/summary/generate
   aynı yolu kullanır).
"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.llm.gemma import gemma

log = structlog.get_logger()

HIGH_RISK_THRESHOLD = 70

# Olay türlerinin Türkçe etiketleri (rapor ve panel metinleri için)
EVENT_TYPE_LABELS = {
    "FORBIDDEN_ZONE_ENTRY": "Yasak bölge ihlali",
    "PPE_VIOLATION": "KKD (baret/yelek) ihlali",
    "FALL": "Düşme",
    "INACTIVITY": "Hareketsizlik",
    "FIRE": "Yangın/alev",
    "SMOKE": "Duman",
    "FORKLIFT_PROXIMITY": "Forklift-insan yakınlığı",
    "DIRECTION_VIOLATION": "Ters yön ihlali",
}

SEVERITY_LABELS = {
    "CRITICAL": "Kritik",
    "HIGH": "Yüksek",
    "MEDIUM": "Orta",
    "LOW": "Düşük",
}


def event_type_label(event_type: str) -> str:
    return EVENT_TYPE_LABELS.get(event_type, event_type.replace("_", " ").title())


def build_summary_stats(events: Iterable) -> dict:
    """Olay satırlarından (ORM Event veya eşdeğer attribute'lu nesne) günün
    istatistiklerini hesaplar. Saf fonksiyon — DB gerektirmez."""
    events = list(events)
    by_type: Counter = Counter()
    by_severity: Counter = Counter()
    by_camera: Counter = Counter()
    by_hour: Counter = Counter()
    high_risk = 0
    top_event: Optional[dict] = None
    first_at: Optional[datetime] = None
    last_at: Optional[datetime] = None

    for ev in events:
        by_type[ev.event_type] += 1
        by_severity[ev.severity] += 1
        by_camera[ev.camera_id] += 1
        by_hour[ev.started_at.hour] += 1
        if ev.risk_score >= HIGH_RISK_THRESHOLD:
            high_risk += 1
        if top_event is None or ev.risk_score > top_event["risk_score"]:
            top_event = {
                "event_type": ev.event_type,
                "camera_id": ev.camera_id,
                "risk_score": ev.risk_score,
                "severity": ev.severity,
                "started_at": ev.started_at.isoformat(),
            }
        if first_at is None or ev.started_at < first_at:
            first_at = ev.started_at
        if last_at is None or ev.started_at > last_at:
            last_at = ev.started_at

    busiest_hour = by_hour.most_common(1)[0][0] if by_hour else None
    return {
        "total": len(events),
        "high_risk": high_risk,
        "by_type": dict(by_type),
        "by_severity": dict(by_severity),
        "by_camera": dict(by_camera),
        "top_event": top_event,
        "first_at": first_at.isoformat() if first_at else None,
        "last_at": last_at.isoformat() if last_at else None,
        "busiest_hour": busiest_hour,
    }


def render_summary_text(date_str: str, stats: dict) -> str:
    """İstatistiklerden deterministik Türkçe yönetici raporu üretir.

    Gemma kapalıyken/başarısızken kullanılan varsayılan yol — çıktının her
    zaman tutarlı, sayısal olarak doğru ve anında üretilebilir olması esas.
    """
    total = stats["total"]
    if total == 0:
        return (
            f"{date_str} tarihli güvenlik raporu: Gün boyunca herhangi bir "
            f"güvenlik olayı tespit edilmedi. Tüm izlenen alanlar normal."
        )

    lines = [f"{date_str} tarihli güvenlik raporu:"]
    high = stats["high_risk"]
    lines.append(
        f"Toplam {total} olay kaydedildi; bunların {high} tanesi yüksek riskli "
        f"(risk puanı ≥ {HIGH_RISK_THRESHOLD})."
        if high
        else f"Toplam {total} olay kaydedildi; yüksek riskli olay bulunmuyor."
    )

    # Tür kırılımı — çoktan aza
    type_parts = [
        f"{event_type_label(t)}: {c}"
        for t, c in sorted(stats["by_type"].items(), key=lambda kv: -kv[1])
    ]
    if type_parts:
        lines.append("Olay dağılımı — " + ", ".join(type_parts) + ".")

    top = stats.get("top_event")
    if top:
        started = top["started_at"][11:16] if len(top["started_at"]) >= 16 else ""
        lines.append(
            f"Günün en kritik olayı: {event_type_label(top['event_type'])} "
            f"({top['camera_id']}, risk {top['risk_score']}/100"
            + (f", saat {started} UTC" if started else "")
            + ")."
        )

    if stats.get("busiest_hour") is not None:
        lines.append(
            f"Olayların en yoğun olduğu saat dilimi: "
            f"{stats['busiest_hour']:02d}:00–{stats['busiest_hour']:02d}:59 (UTC)."
        )

    # Kamera kırılımı
    cam_parts = [
        f"{cam}: {c}"
        for cam, c in sorted(stats["by_camera"].items(), key=lambda kv: -kv[1])
    ]
    if cam_parts:
        lines.append("Kamera bazında: " + ", ".join(cam_parts) + ".")

    # Aksiyon önerisi — kritik/yüksek olay varsa
    critical = stats["by_severity"].get("CRITICAL", 0)
    if critical:
        lines.append(
            f"⚠ {critical} kritik olay incelenmeyi bekliyor — olay kayıtlarının "
            f"ve video kliplerin gözden geçirilmesi önerilir."
        )
    return "\n".join(lines)


def build_gemma_prompt(date_str: str, stats: dict) -> str:
    """LLM'e verilecek özet prompt'u — sayılar hesaplanmış halde verilir,
    modelden yalnızca akıcı Türkçe rapor metni istenir."""
    type_lines = "\n".join(
        f"- {event_type_label(t)}: {c} olay"
        for t, c in sorted(stats["by_type"].items(), key=lambda kv: -kv[1])
    )
    top = stats.get("top_event")
    top_line = (
        f"{event_type_label(top['event_type'])} — kamera {top['camera_id']}, "
        f"risk {top['risk_score']}/100"
        if top
        else "yok"
    )
    return (
        "Bir fabrika güvenlik kamerası AI sisteminin günlük verilerini "
        "özetleyeceksin. Yönetici için kısa, net, profesyonel bir Türkçe rapor "
        "yaz (en fazla 6 cümle). Sayıları aynen kullan, yeni sayı uydurma.\n\n"
        f"Tarih: {date_str}\n"
        f"Toplam olay: {stats['total']}\n"
        f"Yüksek riskli olay: {stats['high_risk']}\n"
        f"Olay tipleri:\n{type_lines or '- yok'}\n"
        f"En kritik olay: {top_line}\n"
    )


async def generate_daily_summary(
    db: AsyncSession,
    target_date: date,
    *,
    force: bool = False,
):
    """Günün özetini üretir ve daily_summaries tablosuna upsert eder.

    force=False iken var olan özet aynen döndürülür (gece scheduler'ı ile
    manuel tetikleme çakışmasın diye idempotent).
    """
    date_str = target_date.isoformat()
    existing = await crud.get_daily_summary(db, date_str)
    if existing is not None and not force:
        return existing

    day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    rows, _total = await crud.list_events(
        db, from_time=day_start, to_time=day_start + timedelta(days=1), limit=5000
    )
    stats = build_summary_stats(rows)

    source = "template"
    text = None
    if gemma.available:
        # LLM inference CPU-bound — event loop'u bloklamamak için thread'e alınır
        text = await asyncio.to_thread(
            gemma.generate, build_gemma_prompt(date_str, stats)
        )
        if text:
            source = "gemma"
    if not text:
        text = render_summary_text(date_str, stats)

    row = await crud.upsert_daily_summary(
        db,
        summary_date=date_str,
        total_events=stats["total"],
        high_risk_events=stats["high_risk"],
        event_breakdown={
            "by_type": stats["by_type"],
            "by_severity": stats["by_severity"],
            "by_camera": stats["by_camera"],
            "top_event": stats["top_event"],
            "busiest_hour": stats["busiest_hour"],
            "source": source,
        },
        summary_text=text,
    )
    log.info("summary.generated", date=date_str, total=stats["total"], source=source)
    return row
