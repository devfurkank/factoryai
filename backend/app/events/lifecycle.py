"""
Olay Yaşam Döngüsü (State Machine) — Faz 4 (Gün 13), Roadmap §5.5.

    PENDING → ACTIVE → SUSTAINED → RESOLVED | ESCALATED

- Yeni olaylar doğrudan ACTIVE olarak yazılır (kural ihlali zaten onaylı;
  PENDING durumu ileride "temporal onay bekleyen" olaylar için ayrılmıştır).
- RESOLVED terminal durumdur; ESCALATED operatör tarafından RESOLVED'a
  çekilebilir.
"""
from __future__ import annotations

from app.events.schemas import EventStatus

# Mevcut durum → izin verilen sonraki durumlar
_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.PENDING: {EventStatus.ACTIVE, EventStatus.RESOLVED},
    EventStatus.ACTIVE: {EventStatus.SUSTAINED, EventStatus.RESOLVED, EventStatus.ESCALATED},
    EventStatus.SUSTAINED: {EventStatus.RESOLVED, EventStatus.ESCALATED},
    EventStatus.ESCALATED: {EventStatus.RESOLVED},
    EventStatus.RESOLVED: set(),
}

# Bu durumlara geçişte olay "bitmiş" sayılır → ended_at doldurulur
TERMINAL_STATUSES = {EventStatus.RESOLVED}


class InvalidTransition(ValueError):
    def __init__(self, current: EventStatus, target: EventStatus):
        self.current = current
        self.target = target
        allowed = sorted(s.value for s in _TRANSITIONS.get(current, set()))
        super().__init__(
            f"{current.value} → {target.value} geçişi geçersiz "
            f"(izin verilenler: {', '.join(allowed) or 'yok — terminal durum'})"
        )


def can_transition(current: EventStatus, target: EventStatus) -> bool:
    return target in _TRANSITIONS.get(current, set())


def validate_transition(current: EventStatus, target: EventStatus) -> None:
    """Geçersiz geçişte InvalidTransition fırlatır."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(status: EventStatus) -> bool:
    return not _TRANSITIONS.get(status, set())
