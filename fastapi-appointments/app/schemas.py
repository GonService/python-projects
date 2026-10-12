"""Request and response bodies of the JSON API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import Booking


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    duration_minutes: int
    price_cents: int


class SlotsOut(BaseModel):
    service_id: int
    date: date
    slots: list[datetime]


class BookingIn(BaseModel):
    service_id: int
    starts_at: datetime = Field(description="Local time of the business, e.g. 2026-10-14T09:00")
    customer_name: str = Field(min_length=3, max_length=120)
    customer_phone: str = Field(description="Brazilian phone with area code, digits only or formatted")
    customer_email: str | None = None
    notes: str = Field(default="", max_length=500)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service_id": 1,
                "starts_at": "2026-10-14T09:00",
                "customer_name": "Ana Paula Ribeiro",
                "customer_phone": "(51) 99876-1234",
                "customer_email": "ana@example.com",
            }
        }
    )


class BookingOut(BaseModel):
    code: str
    service: str
    starts_at: datetime
    ends_at: datetime
    customer_name: str
    status: str

    @classmethod
    def of(cls, b: Booking) -> BookingOut:
        return cls(
            code=b.code,
            service=b.service.name,
            starts_at=b.starts_at,
            ends_at=b.ends_at,
            customer_name=b.customer_name,
            status=b.status,
        )


class AdminBookingOut(BookingOut):
    id: int
    customer_phone: str
    customer_email: str | None
    notes: str
    created_at: datetime

    @classmethod
    def of(cls, b: Booking) -> AdminBookingOut:
        return cls(
            **BookingOut.of(b).model_dump(),
            id=b.id,
            customer_phone=b.customer_phone,
            customer_email=b.customer_email,
            notes=b.notes,
            created_at=b.created_at,
        )
