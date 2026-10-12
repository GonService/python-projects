"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./appointments.db"))
    # Admin endpoints are disabled when no token is configured.
    admin_token: str = field(default_factory=lambda: os.environ.get("ADMIN_TOKEN", ""))
    business_name: str = field(default_factory=lambda: os.environ.get("BUSINESS_NAME", "Clínica Bem-Estar"))
    timezone: str = field(default_factory=lambda: os.environ.get("TIMEZONE", "America/Sao_Paulo"))
    slot_step_minutes: int = field(default_factory=lambda: int(os.environ.get("SLOT_STEP_MINUTES", "30")))
    booking_horizon_days: int = field(default_factory=lambda: int(os.environ.get("BOOKING_HORIZON_DAYS", "30")))
    seed_demo: bool = field(default_factory=lambda: os.environ.get("SEED_DEMO", "") in ("1", "true", "yes"))
