"""Faz 6 (Gün 22–23) birim testleri — Raporlama ve Soru-Cevap.

Saf fonksiyonlar test edilir (DB/model gerektirmez, Faz 2-5 test stiliyle):
- summary.build_summary_stats / render_summary_text / build_gemma_prompt
- qa.parse_question / render_answer
- gemma.GemmaClient degraded davranışı (LLM_ENABLED=false)
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.llm.gemma import GemmaClient
from app.llm.qa import QuestionIntent, parse_question, render_answer
from app.llm.summary import (
    build_gemma_prompt,
    build_summary_stats,
    event_type_label,
    render_summary_text,
)


@dataclass
class FakeEvent:
    """Testlerde ORM Event yerine geçen minimal satır."""
    event_type: str = "PPE_VIOLATION"
    severity: str = "MEDIUM"
    camera_id: str = "cam_laptop_01"
    risk_score: int = 60
    started_at: datetime = field(
        default_factory=lambda: datetime(2026, 7, 2, 10, 30, tzinfo=timezone.utc)
    )


def _sample_events():
    return [
        FakeEvent("FIRE", "CRITICAL", "cam_01", 100,
                  datetime(2026, 7, 2, 14, 5, tzinfo=timezone.utc)),
        FakeEvent("PPE_VIOLATION", "MEDIUM", "cam_01", 60,
                  datetime(2026, 7, 2, 9, 0, tzinfo=timezone.utc)),
        FakeEvent("PPE_VIOLATION", "MEDIUM", "cam_02", 66,
                  datetime(2026, 7, 2, 9, 30, tzinfo=timezone.utc)),
        FakeEvent("FALL", "CRITICAL", "cam_02", 95,
                  datetime(2026, 7, 2, 9, 45, tzinfo=timezone.utc)),
    ]


# ── build_summary_stats ─────────────────────────────────────────────────────────

class TestSummaryStats:
    def test_empty(self):
        stats = build_summary_stats([])
        assert stats["total"] == 0
        assert stats["high_risk"] == 0
        assert stats["top_event"] is None
        assert stats["busiest_hour"] is None

    def test_counts_and_breakdown(self):
        stats = build_summary_stats(_sample_events())
        assert stats["total"] == 4
        assert stats["high_risk"] == 2  # 100 ve 95 (eşik 70)
        assert stats["by_type"] == {"FIRE": 1, "PPE_VIOLATION": 2, "FALL": 1}
        assert stats["by_severity"]["CRITICAL"] == 2
        assert stats["by_camera"] == {"cam_01": 2, "cam_02": 2}

    def test_top_event_is_max_risk(self):
        stats = build_summary_stats(_sample_events())
        assert stats["top_event"]["event_type"] == "FIRE"
        assert stats["top_event"]["risk_score"] == 100

    def test_busiest_hour(self):
        stats = build_summary_stats(_sample_events())
        assert stats["busiest_hour"] == 9  # 09:00, 09:30, 09:45 → 3 olay


# ── render_summary_text ─────────────────────────────────────────────────────────

class TestSummaryText:
    def test_empty_day(self):
        text = render_summary_text("2026-07-02", build_summary_stats([]))
        assert "2026-07-02" in text
        assert "tespit edilmedi" in text

    def test_contains_key_numbers(self):
        text = render_summary_text("2026-07-02", build_summary_stats(_sample_events()))
        assert "Toplam 4 olay" in text
        assert "2 tanesi yüksek riskli" in text
        assert "Yangın/alev" in text          # tür etiketi Türkçeleşmiş
        assert "risk 100/100" in text          # en kritik olay
        assert "09:00–09:59" in text           # en yoğun saat

    def test_critical_events_trigger_action_line(self):
        text = render_summary_text("2026-07-02", build_summary_stats(_sample_events()))
        assert "kritik olay incelenmeyi bekliyor" in text

    def test_gemma_prompt_contains_stats(self):
        prompt = build_gemma_prompt("2026-07-02", build_summary_stats(_sample_events()))
        assert "Toplam olay: 4" in prompt
        assert "Türkçe" in prompt

    def test_event_type_label_fallback(self):
        assert event_type_label("FIRE") == "Yangın/alev"
        assert event_type_label("SOMETHING_NEW") == "Something New"


# ── parse_question ──────────────────────────────────────────────────────────────

TODAY = date(2026, 7, 2)


class TestParseQuestion:
    def test_default_is_today_list(self):
        intent = parse_question("neler oldu göster", today=TODAY)
        assert intent.date_from == TODAY and intent.date_to == TODAY
        assert intent.period_label == "bugün"

    def test_count_question(self):
        intent = parse_question("Bugün kaç olay oldu?", today=TODAY)
        assert intent.kind == "count"
        assert intent.event_type is None

    def test_fire_keyword_turkish_chars(self):
        intent = parse_question("bugün yangın çıktı mı", today=TODAY)
        assert intent.event_type == "FIRE"

    def test_fire_keyword_ascii(self):
        intent = parse_question("yangin var mi", today=TODAY)
        assert intent.event_type == "FIRE"

    def test_ppe_keywords(self):
        assert parse_question("baret ihlali", today=TODAY).event_type == "PPE_VIOLATION"
        assert parse_question("kkd durumu", today=TODAY).event_type == "PPE_VIOLATION"

    def test_fall_keyword(self):
        assert parse_question("düşme oldu mu", today=TODAY).event_type == "FALL"

    def test_forbidden_zone(self):
        intent = parse_question("yasak bölgeye giren oldu mu", today=TODAY)
        assert intent.event_type == "FORBIDDEN_ZONE_ENTRY"

    def test_yesterday(self):
        from datetime import timedelta
        intent = parse_question("dün kaç olay oldu", today=TODAY)
        assert intent.date_from == TODAY - timedelta(days=1)
        assert intent.date_to == TODAY - timedelta(days=1)
        assert intent.period_label == "dün"

    def test_last_n_days(self):
        from datetime import timedelta
        intent = parse_question("son 7 gün özeti", today=TODAY)
        assert intent.date_from == TODAY - timedelta(days=6)
        assert intent.date_to == TODAY
        assert intent.kind == "summary"

    def test_top_risk_question(self):
        intent = parse_question("bugünün en riskli olayı hangisi", today=TODAY)
        assert intent.kind == "top"

    def test_critical_severity(self):
        intent = parse_question("kritik olaylar neler", today=TODAY)
        assert intent.severity == "CRITICAL"

    def test_camera_matching(self):
        cameras = [("cam_laptop_01", "Laptop Kamera"), ("cam_rtsp_01", "Depo")]
        intent = parse_question("depo kamerasında ne oldu", cameras, today=TODAY)
        assert intent.camera_id == "cam_rtsp_01"


# ── render_answer ───────────────────────────────────────────────────────────────

class TestRenderAnswer:
    def test_no_events(self):
        intent = QuestionIntent(kind="count", date_from=TODAY, date_to=TODAY)
        assert "bulunamadı" in render_answer(intent, 0, [])

    def test_count_answer(self):
        intent = QuestionIntent(kind="count", event_type="FIRE",
                                date_from=TODAY, date_to=TODAY)
        answer = render_answer(intent, 3, [])
        assert "3" in answer
        assert "yangın/alev" in answer.lower()

    def test_top_answer(self):
        intent = QuestionIntent(kind="top", date_from=TODAY, date_to=TODAY)
        answer = render_answer(intent, 4, _sample_events())
        assert "Yangın/alev" in answer
        assert "100/100" in answer

    def test_summary_answer(self):
        intent = QuestionIntent(kind="summary", date_from=TODAY, date_to=TODAY)
        answer = render_answer(intent, 4, _sample_events())
        assert "4 olay" in answer
        assert "yüksek riskli" in answer

    def test_list_answer_truncates(self):
        intent = QuestionIntent(kind="list", date_from=TODAY, date_to=TODAY)
        events = _sample_events() * 3  # 12 olay
        answer = render_answer(intent, 12, events)
        assert "12 olay bulundu" in answer
        assert "7 olay daha" in answer  # 12 - 5


# ── GemmaClient degraded modu ───────────────────────────────────────────────────

class TestGemmaDegraded:
    def test_load_disabled_returns_false(self):
        client = GemmaClient()
        # LLM_ENABLED=false (test ortamı varsayılanı) → yükleme atlanır
        assert client.load() is False
        assert client.available is False

    def test_generate_without_model_returns_none(self):
        client = GemmaClient()
        assert client.generate("test") is None
