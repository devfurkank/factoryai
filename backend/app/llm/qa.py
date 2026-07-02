"""Soru-Cevap Servisi — Faz 6 (Gün 22–23).

Roadmap §5.9: MVP'de NL→SQL dönüşümü şablon/keyword bazlıdır. Türkçe soru
metninden niyet (tarih aralığı + olay türü + önem + kamera + soru tipi)
çıkarılır, olay veritabanı sorgulanır ve deterministik Türkçe cevap üretilir.
Gemma yüklüyse cevap LLM ile akıcılaştırılır; her hata şablona düşer.

parse_question / render_answer saf fonksiyonlardır (DB'siz test edilebilir).
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.llm.gemma import gemma
from app.llm.summary import (
    HIGH_RISK_THRESHOLD,
    SEVERITY_LABELS,
    build_summary_stats,
    event_type_label,
)

log = structlog.get_logger()

_TR_FOLD = str.maketrans("çğıöşü", "cgiosu")


def _fold(text: str) -> str:
    """Türkçe metni karşılaştırma için normalize eder (küçük harf + ASCII)."""
    return text.casefold().translate(_TR_FOLD)


# Anahtar kelimeler ASCII-katlanmış halde tanımlanır (_fold çıktısıyla eşleşir)
_EVENT_TYPE_KEYWORDS = [
    ("FIRE", ("yangin", "ates", "alev")),
    ("SMOKE", ("duman",)),
    ("FALL", ("dus", "yere yat")),
    ("INACTIVITY", ("hareketsiz", "kipirdamiyor")),
    ("PPE_VIOLATION", ("kkd", "baret", "yelek", "kask", "ppe")),
    ("FORBIDDEN_ZONE_ENTRY", ("yasak", "bolge ihlal", "izinsiz")),
    ("FORKLIFT_PROXIMITY", ("forklift", "yakinlik")),
    ("DIRECTION_VIOLATION", ("ters yon", "yon ihlal")),
]

_COUNT_WORDS = ("kac", "sayisi", "sayi", "adet", "toplam")
_TOP_WORDS = ("en riskli", "en kritik", "en tehlikeli", "en onemli", "en yuksek risk")
_SUMMARY_WORDS = ("ozet", "ozetle", "rapor", "ne oldu", "neler oldu", "durum nedir", "genel durum")


@dataclass
class QuestionIntent:
    """Sorudan çıkarılan yapılandırılmış niyet."""
    kind: str = "list"                       # count | top | summary | list
    event_type: Optional[str] = None         # EventType değeri
    severity: Optional[str] = None           # Severity değeri
    camera_id: Optional[str] = None
    date_from: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    date_to: date = field(default_factory=lambda: datetime.now(timezone.utc).date())
    period_label: str = "bugün"

    def describe(self) -> str:
        """Cevabın başında kullanıcıya gösterilen filtre tarifi."""
        parts = [self.period_label]
        if self.event_type:
            parts.append(event_type_label(self.event_type).lower())
        if self.severity:
            parts.append(SEVERITY_LABELS[self.severity].lower() + " önemli")
        if self.camera_id:
            parts.append(f"kamera {self.camera_id}")
        return ", ".join(parts)


def parse_question(
    question: str,
    cameras: list[tuple[str, str]] | None = None,
    today: Optional[date] = None,
) -> QuestionIntent:
    """Türkçe sorudan niyet çıkarır. `cameras` = [(id, ad), ...] eşleşmesi için."""
    q = _fold(question)
    today = today or datetime.now(timezone.utc).date()
    intent = QuestionIntent(date_from=today, date_to=today)

    # ── Tarih aralığı ─────────────────────────────────────────────────────────
    m = re.search(r"son\s+(\d+)\s*gun", q)
    if m:
        days = max(1, min(90, int(m.group(1))))
        intent.date_from = today - timedelta(days=days - 1)
        intent.period_label = f"son {days} gün"
    elif "dun" in q.split() or q.startswith("dun ") or " dun " in q:
        intent.date_from = intent.date_to = today - timedelta(days=1)
        intent.period_label = "dün"
    elif "bu hafta" in q or "haftalik" in q:
        intent.date_from = today - timedelta(days=today.weekday())
        intent.period_label = "bu hafta"
    elif "bu ay" in q or "aylik" in q:
        intent.date_from = today.replace(day=1)
        intent.period_label = "bu ay"
    # varsayılan: bugün

    # ── Olay türü ─────────────────────────────────────────────────────────────
    for event_type, keywords in _EVENT_TYPE_KEYWORDS:
        if any(k in q for k in keywords):
            intent.event_type = event_type
            break

    # ── Önem ─────────────────────────────────────────────────────────────────
    if "kritik" in q or "acil" in q:
        intent.severity = "CRITICAL"

    # ── Kamera ────────────────────────────────────────────────────────────────
    for cam_id, cam_name in cameras or []:
        if _fold(cam_id) in q or (cam_name and _fold(cam_name) in q):
            intent.camera_id = cam_id
            break

    # ── Soru tipi ─────────────────────────────────────────────────────────────
    if any(w in q for w in _TOP_WORDS):
        intent.kind = "top"
    elif any(w in q for w in _SUMMARY_WORDS):
        intent.kind = "summary"
    elif any(w in q for w in _COUNT_WORDS):
        intent.kind = "count"

    return intent


def render_answer(intent: QuestionIntent, total: int, events: list) -> str:
    """Sorgu sonuçlarından deterministik Türkçe cevap üretir (saf fonksiyon)."""
    scope = intent.describe()

    if total == 0:
        return f"{scope.capitalize()} için kayıtlı olay bulunamadı."

    if intent.kind == "count":
        noun = event_type_label(intent.event_type).lower() if intent.event_type else "olay"
        return f"{scope.capitalize()} toplam {total} {noun} kaydedildi."

    if intent.kind == "top":
        ev = max(events, key=lambda e: e.risk_score) if events else None
        if ev is None:
            return f"{scope.capitalize()} için olay bulunamadı."
        when = ev.started_at.strftime("%d.%m.%Y %H:%M")
        return (
            f"{scope.capitalize()} en yüksek riskli olay: "
            f"{event_type_label(ev.event_type)} — kamera {ev.camera_id}, "
            f"risk {ev.risk_score}/100 ({SEVERITY_LABELS.get(ev.severity, ev.severity)}), "
            f"saat {when} (UTC)."
        )

    if intent.kind == "summary":
        stats = build_summary_stats(events)
        type_parts = [
            f"{event_type_label(t).lower()} {c}"
            for t, c in sorted(stats["by_type"].items(), key=lambda kv: -kv[1])
        ]
        text = (
            f"{scope.capitalize()} toplam {total} olay kaydedildi"
            + (f", {stats['high_risk']} tanesi yüksek riskli" if stats["high_risk"] else "")
            + "."
        )
        if type_parts:
            text += " Dağılım: " + ", ".join(type_parts) + "."
        return text

    # list — ilk birkaç olayı satır satır aktar
    lines = [f"{scope.capitalize()} {total} olay bulundu. Son olaylar:"]
    for ev in events[:5]:
        when = ev.started_at.strftime("%d.%m %H:%M")
        lines.append(
            f"• {when} — {event_type_label(ev.event_type)} "
            f"({ev.camera_id}, risk {ev.risk_score})"
        )
    if total > 5:
        lines.append(f"… ve {total - 5} olay daha. Detaylar Olaylar sayfasında.")
    return "\n".join(lines)


async def answer_question(db: AsyncSession, question: str) -> dict:
    """Soru → niyet → SQL → cevap. API katmanının kullandığı ana giriş noktası."""
    cameras = []
    try:
        cameras = [(c.id, c.name) for c in await crud.list_cameras(db)]
    except Exception as exc:
        log.warning("qa.cameras_lookup_failed", error=repr(exc))

    intent = parse_question(question, cameras)
    from_time = datetime.combine(intent.date_from, time.min, tzinfo=timezone.utc)
    to_time = datetime.combine(intent.date_to, time.min, tzinfo=timezone.utc) + timedelta(days=1)

    rows, total = await crud.list_events(
        db,
        camera_id=intent.camera_id,
        event_type=intent.event_type,
        severity=intent.severity,
        from_time=from_time,
        to_time=to_time,
        limit=200,
    )
    answer = render_answer(intent, total, rows)

    # Gemma yüklüyse cevabı akıcılaştır (hata → şablon cevap zaten elimizde)
    if gemma.available:
        polished = await asyncio.to_thread(
            gemma.generate,
            "Aşağıdaki fabrika güvenlik verisi cevabını, sayıları aynen koruyarak "
            f"tek paragraf akıcı Türkçe'ye çevir:\n\nSoru: {question}\nCevap: {answer}",
            200,
        )
        if polished:
            answer = polished

    return {
        "question": question,
        "answer": answer,
        "intent": {
            "kind": intent.kind,
            "event_type": intent.event_type,
            "severity": intent.severity,
            "camera_id": intent.camera_id,
            "date_from": intent.date_from.isoformat(),
            "date_to": intent.date_to.isoformat(),
            "period_label": intent.period_label,
        },
        "total": total,
        "events": [crud.event_row_to_response(r) for r in rows[:5]],
    }
