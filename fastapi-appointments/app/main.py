"""FastAPI app: public booking page, booking API and a token-protected admin API.

Run with `uvicorn --factory app.main:create_app`.
"""

import secrets
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .booking import BookingError, Scheduler
from .config import Settings
from .models import Base
from .schemas import AdminBookingOut, BookingIn, BookingOut, ServiceOut, SlotsOut
from .seed import seed

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def brl(cents: int) -> str:
    """12345 -> 'R$ 123,45' (Brazilian separators)."""
    return "R$ " + f"{cents / 100:,.2f}".translate(str.maketrans(",.", ".,"))


templates.env.filters["brl"] = brl
templates.env.filters["weekday"] = lambda d: WEEKDAYS[d.weekday()]
templates.env.filters["daymonth"] = lambda d: f"{d.day} {MONTHS[d.month - 1]}"
templates.env.filters["hhmm"] = lambda dt: dt.strftime("%H:%M")
templates.env.filters["longdate"] = lambda d: f"{WEEKDAYS[d.weekday()]}, {d.day:02d}/{d.month:02d}/{d.year}"


def local_now(tz: str) -> datetime:
    """Current wall-clock time of the business, without tzinfo (bookings are stored in local time)."""
    return datetime.now(ZoneInfo(tz)).replace(tzinfo=None, second=0, microsecond=0)


def create_app(settings: Settings | None = None, now: Callable[[], datetime] | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = now or (lambda: local_now(settings.timezone))

    engine_kwargs: dict = {}
    if settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if settings.database_url in ("sqlite://", "sqlite:///:memory:"):
            engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    if settings.seed_demo:
        with session_factory() as session:
            seed(session, clock())

    app = FastAPI(
        title="Appointments API",
        version="1.0.0",
        description="Online booking for a small business: services, opening hours, free slots and bookings.",
    )
    app.state.settings = settings

    def scheduler() -> Iterator[Scheduler]:
        with session_factory() as session:
            yield Scheduler(session, clock, settings.slot_step_minutes, settings.booking_horizon_days)

    Sched = Annotated[Scheduler, Depends(scheduler)]
    bearer = HTTPBearer(auto_error=False)

    def require_admin(cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
        if not settings.admin_token:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin API disabled: set ADMIN_TOKEN.")
        if cred is None or not secrets.compare_digest(cred.credentials.encode(), settings.admin_token.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token.", headers={"WWW-Authenticate": "Bearer"})

    @app.exception_handler(BookingError)
    async def booking_error(_request: Request, exc: BookingError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    # --- public API ------------------------------------------------------------------------------
    @app.get("/api/services", response_model=list[ServiceOut], tags=["public"])
    def list_services(s: Sched):
        return s.services()

    @app.get("/api/services/{service_id}/slots", response_model=SlotsOut, tags=["public"])
    def list_slots(service_id: int, s: Sched, day: Annotated[date, Query(alias="date")]):
        """Free start times for the service on that day (local time of the business)."""
        service = s.service(service_id)
        return SlotsOut(service_id=service.id, date=day, slots=[x.start for x in s.slots(service, day) if x.available])

    @app.post("/api/bookings", response_model=BookingOut, status_code=201, tags=["public"])
    def create_booking(body: BookingIn, s: Sched):
        booking = s.book(
            body.service_id, body.starts_at, body.customer_name, body.customer_phone, body.customer_email, body.notes
        )
        return BookingOut.of(booking)

    @app.get("/api/bookings/{code}", response_model=BookingOut, tags=["public"])
    def get_booking(code: str, s: Sched):
        return BookingOut.of(s.by_code(code))

    @app.post("/api/bookings/{code}/cancel", response_model=BookingOut, tags=["public"])
    def cancel_booking(code: str, s: Sched):
        return BookingOut.of(s.cancel(s.by_code(code)))

    # --- admin API -------------------------------------------------------------------------------
    @app.get(
        "/api/admin/bookings",
        response_model=list[AdminBookingOut],
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def admin_bookings(
        s: Sched,
        day: Annotated[date | None, Query(alias="date")] = None,
        booking_status: Annotated[str | None, Query(alias="status", pattern="^(confirmed|cancelled)$")] = None,
    ):
        return [AdminBookingOut.of(b) for b in s.bookings(day, booking_status)]

    @app.post(
        "/api/admin/bookings/{code}/cancel",
        response_model=AdminBookingOut,
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def admin_cancel(code: str, s: Sched):
        return AdminBookingOut.of(s.cancel(s.by_code(code)))

    @app.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok"}

    # --- HTML pages ------------------------------------------------------------------------------
    def booking_page(request: Request, s: Scheduler, service_id: int | None, day: date | None, **extra):
        status_code = extra.pop("status", 200)
        services = s.services()
        days = s.open_days(7)
        service = next((x for x in services if x.id == service_id), services[0] if services else None)
        if day is None or day not in days:
            day = days[0] if days else None
        slots = s.slots(service, day) if service and day else []
        context = {
            "business": settings.business_name,
            "services": services,
            "service": service,
            "days": days,
            "day": day,
            "slots": slots,
            "form": {},
        } | extra
        return templates.TemplateResponse(request, "book.html", context, status_code=status_code)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(
        request: Request,
        s: Sched,
        service: int | None = None,
        day: Annotated[date | None, Query(alias="date")] = None,
    ):
        return booking_page(request, s, service, day)

    @app.post("/book", response_class=HTMLResponse, include_in_schema=False)
    def book_form(
        request: Request,
        s: Sched,
        service_id: Annotated[int, Form()],
        starts_at: Annotated[str, Form()] = "",
        name: Annotated[str, Form()] = "",
        phone: Annotated[str, Form()] = "",
        email: Annotated[str, Form()] = "",
    ):
        form = {"name": name, "phone": phone, "email": email, "starts_at": starts_at}
        try:
            when = datetime.fromisoformat(starts_at)
        except ValueError:
            return booking_page(request, s, service_id, None, error="Escolha um horário.", form=form, status=422)
        try:
            booking = s.book(service_id, when, name, phone, email)
        except BookingError as exc:
            return booking_page(request, s, service_id, when.date(), error=exc.message, form=form, status=exc.status)
        return RedirectResponse(f"/booking/{booking.code}", status_code=303)

    @app.get("/booking/{code}", response_class=HTMLResponse, include_in_schema=False)
    def booking_detail(request: Request, code: str, s: Sched):
        try:
            booking = s.by_code(code)
        except BookingError:
            raise HTTPException(404, "Agendamento não encontrado.") from None
        can_cancel = booking.status == "confirmed" and booking.starts_at > clock()
        return templates.TemplateResponse(
            request, "booking.html", {"business": settings.business_name, "b": booking, "can_cancel": can_cancel}
        )

    @app.post("/booking/{code}/cancel", include_in_schema=False)
    def booking_cancel(code: str, s: Sched):
        try:
            s.cancel(s.by_code(code))
        except BookingError as exc:
            if exc.status == 404:
                raise HTTPException(404, exc.message) from None
        return RedirectResponse(f"/booking/{code}", status_code=303)

    return app
