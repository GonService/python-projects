"""Demo data: a small physiotherapy clinic with a few bookings in the coming days.

Run with `python -m app.seed` (uses DATABASE_URL) or set SEED_DEMO=1 when starting the app.
"""

from __future__ import annotations

import secrets
from datetime import datetime, time, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import Base, Booking, OpeningHours, Service

SERVICES = [
    ("Fisioterapia ortopédica", "Sessão individual com avaliação de evolução.", 50, 14000),
    ("Pilates individual", "Aula com aparelhos, acompanhamento exclusivo.", 50, 11000),
    ("Avaliação postural", "Primeira consulta com plano de tratamento.", 30, 9000),
    ("Drenagem linfática", "Técnica manual, indicada no pós-operatório.", 60, 15000),
]
HOURS = [(d, time(8), time(12)) for d in range(6)] + [(d, time(13), time(18)) for d in range(5)]
CUSTOMERS = [
    ("Ana Paula Ribeiro", "51998761234"),
    ("Carlos Eduardo Lima", "51991234567"),
    ("Fernanda Souza", "51984567321"),
    ("João Pedro Martins", "51996543210"),
    ("Mariana Costa", "51993217654"),
    ("Rafael Oliveira", "51987654123"),
]


def seed(session: Session, now: datetime) -> bool:
    """Insert demo data into an empty database. Returns False if there is data already."""
    if session.scalar(select(Service.id).limit(1)) is not None:
        return False
    services = [Service(name=n, description=d, duration_minutes=m, price_cents=p) for n, d, m, p in SERVICES]
    session.add_all(services)
    session.add_all(OpeningHours(weekday=w, opens=o, closes=c) for w, o, c in HOURS)
    session.flush()

    # A few bookings on the next working days so the calendar does not look empty.
    plan = [(1, "09:00", 0), (1, "10:00", 1), (1, "14:00", 3), (1, "16:30", 2), (2, "08:00", 1), (2, "13:30", 0)]
    day, offsets = now.date(), {}
    for n in range(1, 10):
        candidate = day + timedelta(days=n)
        if candidate.weekday() < 5:
            offsets[len(offsets) + 1] = candidate
        if len(offsets) == 2:
            break
    for i, (which, hhmm, service_index) in enumerate(plan):
        service = services[service_index]
        start = datetime.combine(offsets[which], time.fromisoformat(hhmm))
        name, phone = CUSTOMERS[i % len(CUSTOMERS)]
        session.add(
            Booking(
                code=secrets.token_urlsafe(6),
                service_id=service.id,
                starts_at=start,
                ends_at=start + timedelta(minutes=service.duration_minutes),
                customer_name=name,
                customer_phone=phone,
                created_at=now,
            )
        )
    session.commit()
    return True


if __name__ == "__main__":
    from .main import local_now

    settings = Settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        print("Demo data created." if seed(s, local_now(settings.timezone)) else "Database already has data.")
