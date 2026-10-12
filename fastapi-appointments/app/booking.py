"""Booking rules shared by the JSON API and the HTML pages."""

from __future__ import annotations

import re
import secrets
import threading
from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Booking, OpeningHours, Service
from .slots import Slot, day_slots

# SQLite serialises writes, but the check-then-insert below still needs to be atomic inside one process.
_write_lock = threading.Lock()
PHONE_RE = re.compile(r"^\d{10,11}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BookingError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class Scheduler:
    def __init__(self, session: Session, now: Callable[[], datetime], step_minutes: int, horizon_days: int) -> None:
        self.db = session
        self.now = now
        self.step = step_minutes
        self.horizon = horizon_days

    # --- reads -----------------------------------------------------------------------------------
    def services(self) -> list[Service]:
        return list(self.db.scalars(select(Service).where(Service.active).order_by(Service.name)))

    def service(self, service_id: int) -> Service:
        service = self.db.get(Service, service_id)
        if service is None or not service.active:
            raise BookingError("Serviço não encontrado.", 404)
        return service

    def opening(self, day: date) -> list[tuple[time, time]]:
        rows = self.db.scalars(select(OpeningHours).where(OpeningHours.weekday == day.weekday()))
        return [(r.opens, r.closes) for r in rows]

    def busy(self, day: date) -> list[tuple[datetime, datetime]]:
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        rows = self.db.scalars(
            select(Booking).where(Booking.status == "confirmed", Booking.starts_at < end, Booking.ends_at > start)
        )
        return [(b.starts_at, b.ends_at) for b in rows]

    def slots(self, service: Service, day: date) -> list[Slot]:
        today = self.now().date()
        if day < today or day > today + timedelta(days=self.horizon):
            return []
        return day_slots(day, service.duration_minutes, self.opening(day), self.busy(day), self.now(), self.step)

    def open_days(self, count: int) -> list[date]:
        """The next `count` days that have opening hours (today included)."""
        weekdays = set(self.db.scalars(select(OpeningHours.weekday)))
        days, day = [], self.now().date()
        while len(days) < count and weekdays and day <= self.now().date() + timedelta(days=self.horizon):
            if day.weekday() in weekdays:
                days.append(day)
            day += timedelta(days=1)
        return days

    def bookings(self, day: date | None = None, status: str | None = None) -> list[Booking]:
        query = select(Booking).order_by(Booking.starts_at)
        if day:
            start = datetime.combine(day, time.min)
            query = query.where(Booking.starts_at >= start, Booking.starts_at < start + timedelta(days=1))
        if status:
            query = query.where(Booking.status == status)
        return list(self.db.scalars(query))

    def by_code(self, code: str) -> Booking:
        booking = self.db.scalar(select(Booking).where(Booking.code == code))
        if booking is None:
            raise BookingError("Agendamento não encontrado.", 404)
        return booking

    # --- writes ----------------------------------------------------------------------------------
    def book(
        self,
        service_id: int,
        starts_at: datetime,
        name: str,
        phone: str,
        email: str | None = None,
        notes: str = "",
    ) -> Booking:
        name = " ".join(name.split())
        phone = re.sub(r"\D", "", phone or "")
        email = (email or "").strip() or None
        if len(name) < 3:
            raise BookingError("Informe o nome completo.", 422)
        if not PHONE_RE.match(phone):
            raise BookingError("Informe o telefone com DDD (10 ou 11 dígitos).", 422)
        if email and not EMAIL_RE.match(email):
            raise BookingError("Informe um e-mail válido.", 422)
        service = self.service(service_id)
        starts_at = starts_at.replace(tzinfo=None, second=0, microsecond=0)

        with _write_lock:
            slot = next((s for s in self.slots(service, starts_at.date()) if s.start == starts_at), None)
            if slot is None:
                raise BookingError("Horário fora do expediente ou além do prazo de agendamento.", 422)
            if not slot.available:
                if slot.reason == "past":
                    raise BookingError("Este horário já passou.", 409)
                raise BookingError("Este horário acabou de ser reservado por outra pessoa.", 409)
            booking = Booking(
                code=secrets.token_urlsafe(6),
                service_id=service.id,
                starts_at=slot.start,
                ends_at=slot.end,
                customer_name=name,
                customer_phone=phone,
                customer_email=email,
                notes=(notes or "")[:500],
                created_at=self.now(),
            )
            self.db.add(booking)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                raise BookingError("Este horário acabou de ser reservado por outra pessoa.", 409) from exc
        self.db.refresh(booking)
        return booking

    def cancel(self, booking: Booking) -> Booking:
        if booking.status == "cancelled":
            raise BookingError("Este agendamento já foi cancelado.", 409)
        if booking.starts_at <= self.now():
            raise BookingError("Não é possível cancelar um horário que já passou.", 409)
        booking.status = "cancelled"
        self.db.commit()
        return booking
