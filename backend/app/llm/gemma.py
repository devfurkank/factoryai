"""Gemma LLM Wrapper — Faz 6 (Gün 22–23) kapsamında implement edilecek."""
import structlog

log = structlog.get_logger()


class GemmaSummarizer:
    """Gemma 2B ile günlük özet ve soru-cevap — Faz 6'da aktifleştirilecek."""

    def __init__(self):
        self._loaded = False

    def load(self):
        # TODO Faz 6: transformers AutoModelForCausalLM yükle
        log.info("gemma.load.skipped", note="Faz 6'da implement edilecek")
        self._loaded = False

    def generate_daily_summary(self, date: str, events: list) -> str:
        if not self._loaded:
            return f"{date} için özet henüz hazır değil (Gemma Faz 6'da aktif)."
        return ""

    def answer_question(self, question: str) -> str:
        if not self._loaded:
            return "Soru-cevap modülü Faz 6'da aktifleşecek."
        return ""


gemma = GemmaSummarizer()
