from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    error: dict


class MenuItemBase(BaseModel):
    name: str
    description: str | None = None
    isActive: bool = True


class FoodItem(MenuItemBase):
    id: str
    price: float | None = None
    tags: list[str] = []


class WineItem(MenuItemBase):
    id: str
    category: str | None = None
    region: str | None = None
    glassPrice: float | None = None
    bottlePrice: float | None = None


class MenuResponse(BaseModel):
    id: str
    updatedAt: datetime
    currency: str = "EUR"
    food: list[FoodItem]
    wines: list[WineItem]


class ServiceWindowSchema(BaseModel):
    start: str
    end: str


class ScheduleDaySchema(BaseModel):
    date: str
    open: bool
    serviceWindows: list[ServiceWindowSchema] = []
    note: str | None = None


class ScheduleResponse(BaseModel):
    timezone: str = "Europe/Madrid"
    days: list[ScheduleDaySchema]


class AvailabilitySlot(BaseModel):
    time: str
    available: bool
    reason: str | None = None


class AvailabilityResponse(BaseModel):
    date: str
    partySize: int
    timezone: str = "Europe/Madrid"
    slots: list[AvailabilitySlot]


class ReservationCustomer(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None


class ReservationCreate(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    partySize: int = Field(..., ge=1, le=50)
    customer: ReservationCustomer
    notes: str | None = None


class ReservationOut(BaseModel):
    id: str
    status: Literal["PENDING", "CONFIRMED", "CANCELLED", "REJECTED"]
    date: str
    time: str
    partySize: int
    customer: ReservationCustomer
    notes: str | None = None
    createdAt: datetime


class CancelReservation(BaseModel):
    reason: str | None = None


class ContactProjectsCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    subject: str
    message: str
    consent: bool = False
    source: str | None = None
    honeypot: str | None = None


class ContactProjectsOut(BaseModel):
    id: str
    status: Literal["RECEIVED"] = "RECEIVED"


class ConfigItem(BaseModel):
    key: str
    value: str


class ConfigListResponse(BaseModel):
    items: list[ConfigItem]
