from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_db
from app.models import AppConfig, MenuItem, MenuItemType, ScheduleDay, ServiceWindow
from app.schemas import ConfigItem, ConfigListResponse
from app.utils import eur_to_cents


router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


@router.get("/config", response_model=ConfigListResponse)
def list_config(db: Session = Depends(get_db)):
    items = db.execute(select(AppConfig)).scalars().all()
    return ConfigListResponse(items=[ConfigItem(key=i.key, value=i.value) for i in items])


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
def create_food(name: str, description: str | None = None, price: float | None = None, db: Session = Depends(get_db)):
    item = MenuItem(type=MenuItemType.FOOD, name=name, description=description, price_cents=eur_to_cents(price), is_active=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": f"food_{item.id}"}


@router.post("/menu/wines", status_code=status.HTTP_201_CREATED)
def create_wine(
    name: str,
    description: str | None = None,
    category: str | None = None,
    region: str | None = None,
    glassPrice: float | None = None,
    bottlePrice: float | None = None,
    db: Session = Depends(get_db),
):
    item = MenuItem(
        type=MenuItemType.WINE,
        name=name,
        description=description,
        category=category,
        region=region,
        glass_price_cents=eur_to_cents(glassPrice),
        bottle_price_cents=eur_to_cents(bottlePrice),
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": f"wine_{item.id}"}


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
