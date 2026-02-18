from __future__ import annotations

from datetime import datetime


def cents_to_eur(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value / 100.0, 2)


def eur_to_cents(value: float | None) -> int | None:
    if value is None:
        return None
    return int(round(value * 100))


def food_public_id(db_id: int) -> str:
    return f"food_{db_id}"


def wine_public_id(db_id: int) -> str:
    return f"wine_{db_id}"


def reservation_public_id(db_id: int) -> str:
    return f"resv_{db_id}"


def lead_public_id(db_id: int) -> str:
    return f"lead_{db_id}"


def event_public_id(db_id: int) -> str:
    return f"evt_{db_id}"


def now_utc() -> datetime:
    return datetime.utcnow()
