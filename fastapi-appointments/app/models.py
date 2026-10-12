"""Database models (SQLAlchemy 2.0)."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300), default="")
    duration_minutes: Mapped[int]
    price_cents: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)


class OpeningHours(Base):
    """One opening range for a weekday (0 = Monday). Two rows for the same day make a lunch break."""

    __tablename__ = "opening_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int]
    opens: Mapped[time]
    closes: Mapped[time]


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        # Second line of defence against double booking: two confirmed bookings can never share a start time.
        Index("uq_confirmed_start", "starts_at", unique=True, sqlite_where=text("status = 'confirmed'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    starts_at: Mapped[datetime] = mapped_column(index=True)
    ends_at: Mapped[datetime]
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(20))
    customer_email: Mapped[str | None] = mapped_column(String(200), default=None)
    notes: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(12), default="confirmed")
    created_at: Mapped[datetime]

    service: Mapped[Service] = relationship(lazy="joined")
