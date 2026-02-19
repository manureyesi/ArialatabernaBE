from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from app.auth import require_admin
from app.db import get_db
from app.models import AppConfig, MenuItem, MenuItemType, ProjectContact, ScheduleDay, ServiceWindow, Event
from app.models import MenuCategory
from app.schemas import (
    ConfigItem,
    ConfigListResponse,
    ProjectContactAdminItem,
    ProjectContactAdminListResponse,
    ProjectContactAdminStatsResponse,
    AdminFoodCreate,
    AdminWineCreate,
    AdminFoodUpdate,
    AdminWineUpdate,
    MenuCategoryCreate,
    MenuCategoryItem,
    EventAdminItem,
    EventAdminListResponse,
    EventCreate,
    EventUpdate,
    EventCreateResponse,
)
from app.utils import eur_to_cents, event_public_id


router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(require_admin)])


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
        category=payload.category,
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
        wine_type=payload.wineType,
        grapes=payload.grapes,
        glass_price_cents=eur_to_cents(payload.glassPrice),
        bottle_price_cents=eur_to_cents(payload.bottlePrice),
        image_url=payload.imageUrl,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": f"wine_{item.id}"}


@router.post("/menu/categories", status_code=status.HTTP_201_CREATED)
def create_menu_category(payload: MenuCategoryCreate, db: Session = Depends(get_db)):
    if payload.subcategory is None:
        existing = (
            db.execute(
                select(MenuCategory).where(
                    MenuCategory.category == payload.category,
                    MenuCategory.subcategory.is_(None),
                )
            )
            .scalars()
            .first()
        )
        if existing:
            existing.orden = payload.orden
            db.add(existing)
            db.commit()
            return {"id": existing.id}

        cat = MenuCategory(category=payload.category, subcategory=None, orden=payload.orden, parent_id=None)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return {"id": cat.id}

    parent = (
        db.execute(
            select(MenuCategory).where(
                MenuCategory.category == payload.category,
                MenuCategory.subcategory.is_(None),
            )
        )
        .scalars()
        .first()
    )
    if not parent:
        raise HTTPException(status_code=400, detail="Parent category does not exist")

    existing = (
        db.execute(
            select(MenuCategory).where(
                MenuCategory.category == payload.category,
                MenuCategory.subcategory == payload.subcategory,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        existing.orden = payload.orden
        existing.parent_id = parent.id
        db.add(existing)
        db.commit()
        return {"id": existing.id}

    sub = MenuCategory(
        category=payload.category,
        subcategory=payload.subcategory,
        orden=payload.orden,
        parent_id=parent.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"id": sub.id}


@router.get("/menu/categories", response_model=list[MenuCategoryItem])
def list_menu_categories(db: Session = Depends(get_db)):
    rows = db.execute(select(MenuCategory).order_by(MenuCategory.orden.asc(), MenuCategory.id.asc())).scalars().all()

    parents = [r for r in rows if r.parent_id is None]
    children_by_parent: dict[int, list[MenuCategory]] = {}
    for r in rows:
        if r.parent_id is not None:
            children_by_parent.setdefault(r.parent_id, []).append(r)

    out: list[MenuCategoryItem] = []
    for p in sorted(parents, key=lambda x: (x.orden, x.id)):
        kids = sorted(children_by_parent.get(p.id, []), key=lambda x: (x.orden, x.id))
        out.append(
            MenuCategoryItem(
                id=p.id,
                category=p.category,
                subcategory=None,
                orden=p.orden,
                children=[
                    MenuCategoryItem(id=k.id, category=k.category, subcategory=k.subcategory, orden=k.orden, children=[])
                    for k in kids
                ],
            )
        )

    return out


@router.delete("/menu/categories/{subcategory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_subcategory(subcategory_id: int, db: Session = Depends(get_db)):
    sub = db.execute(select(MenuCategory).where(MenuCategory.id == subcategory_id)).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Not found")
    if sub.parent_id is None:
        raise HTTPException(status_code=400, detail="Cannot delete parent category")

    db.delete(sub)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.put("/menu/{item_id}")
def update_menu_item(item_id: str, payload: AdminFoodUpdate | AdminWineUpdate, db: Session = Depends(get_db)):
    if "_" not in item_id:
        raise HTTPException(status_code=404, detail="Not found")

    prefix, raw_id = item_id.split("_", 1)
    if prefix == "food":
        expected_type = MenuItemType.FOOD
        if isinstance(payload, AdminWineUpdate):
            raise HTTPException(status_code=400, detail="Invalid payload")
    elif prefix == "wine":
        expected_type = MenuItemType.WINE
        if isinstance(payload, AdminFoodUpdate):
            raise HTTPException(status_code=400, detail="Invalid payload")
    else:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        db_id = int(raw_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    item = db.execute(select(MenuItem).where(MenuItem.id == db_id, MenuItem.type == expected_type)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")

    def _should_update(field_name: str) -> bool:
        return field_name in payload.model_fields_set and getattr(payload, field_name) is not None

    if _should_update("name"):
        item.name = payload.name
    if _should_update("description"):
        item.description = payload.description
    if _should_update("imageUrl"):
        item.image_url = payload.imageUrl
    if _should_update("isActive"):
        item.is_active = payload.isActive

    if expected_type == MenuItemType.FOOD:
        if _should_update("category"):
            item.category = payload.category
        if _should_update("price"):
            item.price_cents = eur_to_cents(payload.price)
    else:
        if _should_update("category"):
            item.category = payload.category
        if _should_update("region"):
            item.region = payload.region
        if _should_update("wineType"):
            item.wine_type = payload.wineType
        if _should_update("grapes"):
            item.grapes = payload.grapes
        if _should_update("glassPrice"):
            item.glass_price_cents = eur_to_cents(payload.glassPrice)
        if _should_update("bottlePrice"):
            item.bottle_price_cents = eur_to_cents(payload.bottlePrice)

    db.add(item)
    db.commit()
    return {"status": "updated"}


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
                proposalTitle=it.proposal_title,
                proposalDiscipline=it.proposal_discipline,
                proposalDescription=it.proposal_description,
                proposalBio=it.proposal_bio,
                proposalSocials=it.proposal_socials,
                proposalHasFile=it.proposal_has_file,
                proposalFileBase64=it.proposal_file_base64,
                isRead=it.is_read,
                readAt=it.read_at,
                createdAt=it.created_at,
            )
            for it in items
        ]
    )


@router.get("/contacts/projects/stats", response_model=ProjectContactAdminStatsResponse)
def project_requests_stats(db: Session = Depends(get_db)):
    total = db.execute(select(func.count(ProjectContact.id))).scalar_one()
    unread = db.execute(select(func.count(ProjectContact.id)).where(ProjectContact.is_read == False)).scalar_one()  # noqa: E712
    return ProjectContactAdminStatsResponse(total=int(total), unread=int(unread))


@router.post("/contacts/projects/{lead_id}/read")
def mark_project_request_read(lead_id: str, db: Session = Depends(get_db)):
    if not lead_id.startswith("lead_"):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        db_id = int(lead_id.split("_", 1)[1])
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    lead = db.execute(select(ProjectContact).where(ProjectContact.id == db_id)).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Not found")

    if not lead.is_read:
        lead.is_read = True
        lead.read_at = datetime.utcnow()
        db.add(lead)
        db.commit()

    return {"id": f"lead_{lead.id}", "isRead": lead.is_read}


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
