"""Gemma LLM Wrapper — Faz 6 (Gün 22–23).

Roadmap §3.2 kararı: Gemma yalnızca offline/near-time katmanda çalışır
(günlük özet + soru-cevap). Gerçek zamanlı doğrulamada KULLANILMAZ.

Tasarım ilkeleri:
- LLM tamamen opsiyonel bir iyileştirme katmanıdır. LLM_ENABLED=false
  (varsayılan) iken transformers import bile edilmez; özet ve cevap üretimi
  şablon tabanlı üreticilere (summary.py / qa.py) düşer.
- Yükleme veya inference hatası hiçbir zaman yukarı yayılmaz — `generate()`
  None döndürür ve çağıran şablon çıktıya geri düşer (degraded mod, projenin
  genel yaklaşımıyla tutarlı).
- Model CPU'da yüklenir (GEMMA_DEVICE) — detection engine ile GPU paylaşımı
  MVP'de bilinçli olarak yapılmıyor (Roadmap §3.2 donanım notu).
"""
from __future__ import annotations

import threading
from typing import Optional

import structlog

from app.config import settings

log = structlog.get_logger()


class GemmaClient:
    """Gemma 2B instruction-tuned model için ince sarmalayıcı.

    `load()` ağır bir çağrıdır (ilk seferde ~5GB indirme + RAM'e yükleme);
    startup'ta background thread'de çağrılır, event loop'u bloklamaz.
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._load_lock = threading.Lock()
        self._load_attempted = False

    @property
    def available(self) -> bool:
        return self._model is not None

    def load(self) -> bool:
        """Modeli yükler (idempotent, thread-safe). Başarı durumunu döndürür."""
        if not settings.llm_enabled:
            log.info("gemma.load.disabled", note="LLM_ENABLED=false — şablon mod")
            return False
        with self._load_lock:
            if self._model is not None:
                return True
            if self._load_attempted:
                return False  # önceki deneme başarısız — tekrar tekrar deneme
            self._load_attempted = True
            try:
                from transformers import AutoModelForCausalLM, AutoTokenizer

                log.info("gemma.load.start", model=settings.gemma_model,
                         device=settings.gemma_device)
                self._tokenizer = AutoTokenizer.from_pretrained(settings.gemma_model)
                self._model = AutoModelForCausalLM.from_pretrained(
                    settings.gemma_model
                ).to(settings.gemma_device)
                self._model.eval()
                log.info("gemma.load.ok", model=settings.gemma_model)
                return True
            except Exception as exc:  # ImportError, ağ, HF auth, RAM...
                self._model = None
                self._tokenizer = None
                log.warning("gemma.load.failed", error=repr(exc),
                            note="şablon tabanlı üretime düşülüyor")
                return False

    def generate(self, prompt: str, max_new_tokens: Optional[int] = None) -> Optional[str]:
        """Prompt'tan metin üretir; model yoksa veya hata olursa None döndürür."""
        if self._model is None or self._tokenizer is None:
            return None
        try:
            import torch

            chat = [{"role": "user", "content": prompt}]
            input_ids = self._tokenizer.apply_chat_template(
                chat, add_generation_prompt=True, return_tensors="pt"
            ).to(settings.gemma_device)
            with torch.no_grad():
                output = self._model.generate(
                    input_ids,
                    max_new_tokens=max_new_tokens or settings.gemma_max_new_tokens,
                    do_sample=False,
                )
            text = self._tokenizer.decode(
                output[0][input_ids.shape[-1]:], skip_special_tokens=True
            )
            return text.strip() or None
        except Exception as exc:
            log.warning("gemma.generate.failed", error=repr(exc))
            return None


gemma = GemmaClient()
