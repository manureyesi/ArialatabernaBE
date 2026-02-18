from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from app.auth import require_admin
from app.db import get_db
from app.models import AppConfig, MenuItem, MenuItemType, ProjectContact, ScheduleDay, ServiceWindow, Event
from app.schemas import (
    ConfigItem,
    ConfigListResponse,
    ProjectContactAdminItem,
    ProjectContactAdminListResponse,
    AdminFoodCreate,
    AdminWineCreate,
    EventAdminItem,
    EventAdminListResponse,
    EventCreate,
    EventUpdate,
    EventCreateResponse,
)
from app.utils import eur_to_cents, event_public_id


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.get("/config", response_model=list[ConfigItem])
def list_config(db: Session = Depends(get_db)):
    items = db.execute(select(AppConfig)).scalars().all()
    return [ConfigItem(key=i.key, value=i.value) for i in items]


@router.put("/config/{key}", response_model=ConfigItem)
def set_config(key: str, payload: ConfigItem, db: Session = Depends(get_db)):
    if key != payload.key:
        raise HTTPException(status_code=400, detail="Key mismatch")

    item = db.execute(select(AppConfig).where(AppConfig.key == key)).scalar_one_or_none()
    if not item:
        item = AppConfig(key=key, value=payload.value)
    else:
        item.value = payload.value

    db.add(item)
    db.commit()
    db.refresh(item)
    return ConfigItem(key=item.key, value=item.value)


@router.post("/menu/food", status_code=status.HTTP_201_CREATED)
def create_food(payload: AdminFoodCreate, db: Session = Depends(get_db)):
    item = MenuItem(
        type=MenuItemType.FOOD,
        name=payload.name,
        description=payload.description,
        price_cents=eur_to_cents(payload.price),
        image_url=payload.imageUrl,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": f"food_{item.id}"}


@router.post("/menu/wines", status_code=status.HTTP_201_CREATED)
def create_wine(payload: AdminWineCreate, db: Session = Depends(get_db)):
    item = MenuItem(
        type=MenuItemType.WINE,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        region=payload.region,
        glass_price_cents=eur_to_cents(payload.glassPrice),
        bottle_price_cents=eur_to_cents(payload.bottlePrice),
        image_url=payload.imageUrl,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": f"wine_{item.id}"}


@router.delete("/menu/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(item_id: str, db: Session = Depends(get_db)):
    if "_" not in item_id:
        raise HTTPException(status_code=404, detail="Not found")

    prefix, raw_id = item_id.split("_", 1)
    if prefix == "food":
        expected_type = MenuItemType.FOOD
    elif prefix == "wine":
        expected_type = MenuItemType.WINE
    else:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        db_id = int(raw_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    item = db.execute(select(MenuItem).where(MenuItem.id == db_id, MenuItem.type == expected_type)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")

    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/schedule/day", status_code=status.HTTP_201_CREATED)
def upsert_schedule_day(date: str, open: bool = True, note: str | None = None, db: Session = Depends(get_db)):
    day = db.execute(select(ScheduleDay).where(ScheduleDay.date == date)).scalar_one_or_none()
    if not day:
        day = ScheduleDay(date=date, open=open, note=note)
    else:
        day.open = open
        day.note = note

    db.add(day)
    db.commit()
    db.refresh(day)
    return {"date": day.date, "open": day.open}


@router.post("/schedule/window", status_code=status.HTTP_201_CREATED)
def add_service_window(date: str, start: str, end: str, db: Session = Depends(get_db)):
    day = db.execute(select(ScheduleDay).where(ScheduleDay.date == date)).scalar_one_or_none()
    if not day:
        day = ScheduleDay(date=date, open=True)
        db.add(day)
        db.commit()
        db.refresh(day)

    window = ServiceWindow(day_id=day.id, start=start, end=end)
    db.add(window)
    db.commit()
    db.refresh(window)
    return {"id": window.id}


@router.get("/contacts/projects", response_model=ProjectContactAdminListResponse)
def list_project_requests(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="Invalid limit")
    if offset < 0:
        raise HTTPException(status_code=400, detail="Invalid offset")

    stmt = select(ProjectContact).order_by(ProjectContact.created_at.desc()).offset(offset).limit(limit)
    items = db.execute(stmt).scalars().all()

    return ProjectContactAdminListResponse(
        items=[
            ProjectContactAdminItem(
                id=f"lead_{it.id}",
                name=it.name,
                email=it.email,
                phone=it.phone,
                company=it.company,
                subject=it.subject,
                message=it.message,
                consent=it.consent,
                source=it.source,
                createdAt=it.created_at,
            )
            for it in items
        ]
    )


@router.get("/events", response_model=EventAdminListResponse)
def list_events(
    status: str = "all",
    from_: str | None = None,
    to: str | None = None,
    category: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    db: Session = Depends(get_db),
):
    if status not in {"published", "draft", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status")
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

    stmt = select(Event)
    if status == "published":
        stmt = stmt.where(Event.is_published == True)  # noqa: E712
    elif status == "draft":
        stmt = stmt.where(Event.is_published == False)  # noqa: E712

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

    stmt = stmt.order_by(Event.date_start.desc()).offset(offset).limit(limit + 1)
    rows = db.execute(stmt).scalars().all()

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(offset + limit)

    return EventAdminListResponse(
        items=[
            EventAdminItem(
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
            for it in rows
        ],
        nextCursor=next_cursor,
    )


@router.post("/events", response_model=EventCreateResponse, status_code=status.HTTP_201_CREATED)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    ev = Event(
        title=payload.title,
        date_start=payload.dateStart,
        date_end=payload.dateEnd,
        timezone=payload.timezone,
        description=payload.description,
        category=payload.category,
        image_url=payload.imageUrl,
        location_name=payload.locationName,
        is_published=payload.isPublished,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return EventCreateResponse(id=event_public_id(ev.id))


@router.put("/events/{event_id}")
def update_event(event_id: str, payload: EventUpdate, db: Session = Depends(get_db)):
    if not event_id.startswith("evt_"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        db_id = int(event_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    ev = db.execute(select(Event).where(Event.id == db_id)).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Not found")

    ev.title = payload.title
    ev.date_start = payload.dateStart
    ev.date_end = payload.dateEnd
    ev.timezone = payload.timezone
    ev.description = payload.description
    ev.category = payload.category
    ev.image_url = payload.imageUrl
    ev.location_name = payload.locationName
    ev.is_published = payload.isPublished

    db.add(ev)
    db.commit()
    return {"status": "updated"}


@router.post("/events/{event_id}/publish")
def publish_event(event_id: str, db: Session = Depends(get_db)):
    if not event_id.startswith("evt_"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        db_id = int(event_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    ev = db.execute(select(Event).where(Event.id == db_id)).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Not found")

    ev.is_published = True
    db.add(ev)
    db.commit()
    return {"id": event_public_id(ev.id), "isPublished": ev.is_published}


@router.post("/events/{event_id}/unpublish")
def unpublish_event(event_id: str, db: Session = Depends(get_db)):
    if not event_id.startswith("evt_"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        db_id = int(event_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    ev = db.execute(select(Event).where(Event.id == db_id)).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Not found")

    ev.is_published = False
    db.add(ev)
    db.commit()
    return {"id": event_public_id(ev.id), "isPublished": ev.is_published}


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str, db: Session = Depends(get_db)):
    if not event_id.startswith("evt_"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        db_id = int(event_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    ev = db.execute(select(Event).where(Event.id == db_id)).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Not found")

    db.delete(ev)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
