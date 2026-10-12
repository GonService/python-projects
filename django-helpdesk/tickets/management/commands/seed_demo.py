import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import Comment, Ticket

SAMPLES = [
    ("Invoice emission returns error 500", "Billing", "high"),
    ("Cannot reset my password", "Access", "normal"),
    ("Website is very slow since this morning", "Infrastructure", "urgent"),
    ("Change the company address on invoices", "Billing", "low"),
    ("Report export to Excel is empty", "Reports", "normal"),
    ("New user for the finance team", "Access", "low"),
    ("Payment confirmation did not arrive", "Billing", "high"),
    ("Mobile app crashes on login", "App", "urgent"),
]
NAMES = [("Ana Souza", "ana"), ("Bruno Lima", "bruno"), ("Carla Dias", "carla"), ("Diego Rocha", "diego")]


class Command(BaseCommand):
    help = "Create an admin user (admin / admin) and demo tickets. For local demos only."

    def handle(self, *args, **options):
        User = get_user_model()
        admin, created = User.objects.get_or_create(username="admin", defaults={"is_staff": True, "is_superuser": True})
        if created:
            admin.set_password("admin")
            admin.save()
        agent, _ = User.objects.get_or_create(username="support", defaults={"is_staff": True})

        random.seed(3)
        now = timezone.now()
        for i, (title, category, priority) in enumerate(SAMPLES):
            name, handle = random.choice(NAMES)
            ticket = Ticket.objects.create(
                title=title,
                description=f"{title}. Reported by {name}.",
                requester_name=name,
                requester_email=f"{handle}@example.com",
                category=category,
                priority=priority,
                created_at=now - timedelta(hours=random.randint(1, 60)),
                status=random.choice(["open", "open", "in_progress", "waiting", "resolved"]),
                assignee=random.choice([None, admin, agent]),
            )
            if i % 2 == 0:
                Comment.objects.create(ticket=ticket, author=agent, body="We are looking into it.")
        self.stdout.write(self.style.SUCCESS(f"Created {len(SAMPLES)} tickets. Log in at /admin with admin / admin."))
