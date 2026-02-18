from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MenuItem, MenuItemType, ScheduleDay, ServiceWindow, Reservation, ReservationStatus, ProjectContact, Event
from app.schemas import (
    MenuResponse,
    FoodItem,
    WineItem,
    EventPublicDetail,
    EventPublicItem,
    EventPublicListResponse,
    ScheduleResponse,
    ScheduleDaySchema,
    ServiceWindowSchema,
    AvailabilityResponse,
    AvailabilitySlot,
    ReservationCreate,
    ReservationOut,
    ReservationCustomer,
    CancelReservation,
    ContactProjectsCreate,
    ContactProjectsOut,
)
from app.settings import settings
from app.utils import cents_to_eur, eur_to_cents, food_public_id, wine_public_id, reservation_public_id, lead_public_id, event_public_id, now_utc


router = APIRouter(prefix="/api/v1")


@router.get("/events", response_model=EventPublicListResponse)
def list_events(
    from_: str | None = None,
    to: str | None = None,
    category: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Invalid limit")

    offset = 0
    if cursor:
        try:
            offset = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        if offset < 0:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    stmt = select(Event).where(Event.is_published == True)  # noqa: E712
    if category:
        stmt = stmt.where(Event.category == category)

    if from_:
        try:
            from_dt = datetime.strptime(from_, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from")
        stmt = stmt.where(Event.date_start >= from_dt)

    if to:
        try:
            to_dt = datetime.strptime(to, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to")
        stmt = stmt.where(Event.date_start < to_dt)

    stmt = stmt.order_by(Event.date_start.asc()).offset(offset).limit(limit + 1)
    rows = db.execute(stmt).scalars().all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(offset + limit)

    return EventPublicListResponse(
        items=[
            EventPublicItem(
                id=event_public_id(it.id),
                title=it.title,
                dateStart=it.date_start,
                dateEnd=it.date_end,
                timezone=it.timezone,
                description=it.description,
                category=it.category,
                imageUrl=it.image_url,
                locationName=it.location_name,
                isPublished=it.is_published,
            )
            for it in rows
        ],
        nextCursor=next_cursor,
    )


@router.get("/events/{event_id}", response_model=EventPublicDetail)
def get_event(event_id: str, db: Session = Depends(get_db)):
    if not event_id.startswith("evt_"):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        db_id = int(event_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    it = db.execute(select(Event).where(Event.id == db_id, Event.is_published == True)).scalar_one_or_none()  # noqa: E712
    if not it:
        raise HTTPException(status_code=404, detail="Not found")

    return EventPublicDetail(
        id=event_public_id(it.id),
        title=it.title,
        dateStart=it.date_start,
        dateEnd=it.date_end,
        timezone=it.timezone,
        description=it.description,
        category=it.category,
        imageUrl=it.image_url,
        locationName=it.location_name,
        isPublished=it.is_published,
        createdAt=it.created_at,
        updatedAt=it.updated_at,
    )


@router.get("/menu", response_model=MenuResponse)
def get_menu(db: Session = Depends(get_db)):
    items = db.execute(
        select(MenuItem).where(MenuItem.is_active == True)  # noqa: E712
    ).scalars().all()

    food: list[FoodItem] = []
    wines: list[WineItem] = []
    updated_at = now_utc()

    for it in items:
        if it.updated_at and it.updated_at > updated_at:
            updated_at = it.updated_at

        if it.type == MenuItemType.FOOD:
            food.append(
                FoodItem(
                    id=food_public_id(it.id),
                    name=it.name,
                    description=it.description,
                    price=cents_to_eur(it.price_cents),
                    tags=[],
                    isActive=it.is_active,
                )
            )
        else:
            wines.append(
                WineItem(
                    id=wine_public_id(it.id),
                    name=it.name,
                    description=it.description,
                    category=it.category,
                    region=it.region,
                    glassPrice=cents_to_eur(it.glass_price_cents),
                    bottlePrice=cents_to_eur(it.bottle_price_cents),
                    isActive=it.is_active,
                )
            )

    return MenuResponse(id="menu_current", updatedAt=updated_at, food=food, wines=wines)


@router.get("/menu/food", response_model=list[FoodItem])
def get_food(db: Session = Depends(get_db)):
    items = db.execute(
        select(MenuItem).where(MenuItem.type == MenuItemType.FOOD, MenuItem.is_active == True)  # noqa: E712
    ).scalars().all()

    return [
        FoodItem(
            id=food_public_id(it.id),
            name=it.name,
            description=it.description,
            price=cents_to_eur(it.price_cents),
            tags=[],
            isActive=it.is_active,
        )
        for it in items
    ]


@router.get("/menu/wines", response_model=list[WineItem])
def get_wines(db: Session = Depends(get_db)):
    items = db.execute(
        select(MenuItem).where(MenuItem.type == MenuItemType.WINE, MenuItem.is_active == True)  # noqa: E712
    ).scalars().all()

    return [
        WineItem(
            id=wine_public_id(it.id),
            name=it.name,
            description=it.description,
            category=it.category,
            region=it.region,
            glassPrice=cents_to_eur(it.glass_price_cents),
            bottlePrice=cents_to_eur(it.bottle_price_cents),
            isActive=it.is_active,
        )
        for it in items
    ]


@router.get("/schedule", response_model=ScheduleResponse)
def get_schedule(from_: str | None = None, to: str | None = None, db: Session = Depends(get_db)):
    stmt = select(ScheduleDay).order_by(ScheduleDay.date.asc())
    if from_:
        stmt = stmt.where(ScheduleDay.date >= from_)
    if to:
        stmt = stmt.where(ScheduleDay.date <= to)

    days = db.execute(stmt).scalars().all()

    out_days: list[ScheduleDaySchema] = []
    for day in days:
        out_days.append(
            ScheduleDaySchema(
                date=day.date,
                open=day.open,
                note=day.note,
                serviceWindows=[ServiceWindowSchema(start=w.start, end=w.end) for w in day.windows],
            )
        )

    return ScheduleResponse(days=out_days)


def _generate_slots(windows: list[ServiceWindow], step_minutes: int = 30) -> list[str]:
    slots: list[str] = []
    for w in windows:
        start_dt = datetime.strptime(w.start, "%H:%M")
        end_dt = datetime.strptime(w.end, "%H:%M")

        current = start_dt
        while current < end_dt:
            slots.append(current.strftime("%H:%M"))
            current = current + timedelta(minutes=step_minutes)

    return sorted(set(slots))


@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(date: str, partySize: int, db: Session = Depends(get_db)):
    day = db.execute(select(ScheduleDay).where(ScheduleDay.date == date)).scalar_one_or_none()
    if not day or not day.open:
        return AvailabilityResponse(date=date, partySize=partySize, slots=[])

    windows = day.windows
    slot_times = _generate_slots(windows)

    res_counts = dict(
        db.execute(
            select(Reservation.time, func.count(Reservation.id))
            .where(
                Reservation.date == date,
                Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
            )
            .group_by(Reservation.time)
        ).all()
    )

    capacity = settings.reservation_slot_capacity
    slots: list[AvailabilitySlot] = []
    for t in slot_times:
        count = int(res_counts.get(t, 0))
        available = count < capacity
        slots.append(AvailabilitySlot(time=t, available=available, reason=None if available else "FULL"))

    return AvailabilityResponse(date=date, partySize=partySize, slots=slots)


@router.post("/reservations", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)):
    day = db.execute(select(ScheduleDay).where(ScheduleDay.date == payload.date)).scalar_one_or_none()
    if not day or not day.open:
        raise HTTPException(status_code=400, detail="Date is not available")

    within_window = any(w.start <= payload.time < w.end for w in day.windows)
    if not within_window:
        raise HTTPException(status_code=400, detail="Time is not within service hours")

    count = db.execute(
        select(func.count(Reservation.id)).where(
            Reservation.date == payload.date,
            Reservation.time == payload.time,
            Reservation.status.in_([ReservationStatus.PENDING, ReservationStatus.CONFIRMED]),
        )
    ).scalar_one()

    if int(count) >= settings.reservation_slot_capacity:
        raise HTTPException(status_code=409, detail="Slot is full")

    r = Reservation(
        date=payload.date,
        time=payload.time,
        party_size=payload.partySize,
        customer_name=payload.customer.name,
        customer_phone=payload.customer.phone,
        customer_email=str(payload.customer.email) if payload.customer.email else None,
        notes=payload.notes,
        status=ReservationStatus.PENDING,
    )
    db.add(r)
    db.commit()
    db.refresh(r)

    return ReservationOut(
        id=reservation_public_id(r.id),
        status=r.status.value,
        date=r.date,
        time=r.time,
        partySize=r.party_size,
        customer=ReservationCustomer(name=r.customer_name, phone=r.customer_phone, email=r.customer_email),
        notes=r.notes,
        createdAt=r.created_at,
    )


@router.get("/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: str, db: Session = Depends(get_db)):
    if not reservation_id.startswith("resv_"):
        raise HTTPException(status_code=404, detail="Not found")
    db_id = int(reservation_id.split("_", 1)[1])

    r = db.execute(select(Reservation).where(Reservation.id == db_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    return ReservationOut(
        id=reservation_public_id(r.id),
        status=r.status.value,
        date=r.date,
        time=r.time,
        partySize=r.party_size,
        customer=ReservationCustomer(name=r.customer_name, phone=r.customer_phone, email=r.customer_email),
        notes=r.notes,
        createdAt=r.created_at,
    )


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(reservation_id: str, payload: CancelReservation, db: Session = Depends(get_db)):
    if not reservation_id.startswith("resv_"):
        raise HTTPException(status_code=404, detail="Not found")
    db_id = int(reservation_id.split("_", 1)[1])

    r = db.execute(select(Reservation).where(Reservation.id == db_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    if r.status in [ReservationStatus.CANCELLED, ReservationStatus.REJECTED]:
        raise HTTPException(status_code=409, detail="Reservation cannot be cancelled")

    r.status = ReservationStatus.CANCELLED
    db.add(r)
    db.commit()
    db.refresh(r)

    return ReservationOut(
        id=reservation_public_id(r.id),
        status=r.status.value,
        date=r.date,
        time=r.time,
        partySize=r.party_size,
        customer=ReservationCustomer(name=r.customer_name, phone=r.customer_phone, email=r.customer_email),
        notes=r.notes,
        createdAt=r.created_at,
    )


@router.post("/contacts/projects", response_model=ContactProjectsOut, status_code=status.HTTP_202_ACCEPTED)
def contact_projects(payload: ContactProjectsCreate, db: Session = Depends(get_db)):
    if payload.honeypot:
        raise HTTPException(status_code=400, detail="Invalid payload")

    lead = ProjectContact(
        name=payload.name,
        email=str(payload.email),
        phone=payload.phone,
        company=payload.company,
        subject=payload.subject,
        message=payload.message,
        consent=payload.consent,
        source=payload.source,
    )

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return ContactProjectsOut(id=lead_public_id(lead.id))


@router.get("/config")
def get_public_config():
    return {
        "environment": "prod",
        "features": {"reservationsEnabled": False, "menuEnabled": True, "projectsContactEnabled": True},
        "limits": {"maxMessageLength": 500},
    }
