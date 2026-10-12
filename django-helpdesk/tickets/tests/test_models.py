from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from tickets.models import Comment, Ticket


def make_ticket(**kwargs) -> Ticket:
    data = {
        "title": "Cannot issue invoices",
        "description": "Error 500 when issuing an invoice",
        "requester_name": "Ana",
        "requester_email": "ana@example.com",
    }
    data.update(kwargs)
    return Ticket.objects.create(**data)


class TicketModelTests(TestCase):
    def test_due_date_follows_the_priority_sla(self):
        created = timezone.now()
        urgent = make_ticket(priority="urgent", created_at=created)
        low = make_ticket(priority="low", created_at=created)
        self.assertEqual(urgent.due_at, created + timedelta(hours=4))
        self.assertEqual(low.due_at, created + timedelta(hours=72))

    def test_resolved_at_is_set_and_cleared_with_the_status(self):
        t = make_ticket()
        self.assertIsNone(t.resolved_at)
        t.status = Ticket.Status.RESOLVED
        t.save()
        self.assertIsNotNone(t.resolved_at)
        t.status = Ticket.Status.OPEN
        t.save()
        self.assertIsNone(t.resolved_at)

    def test_overdue(self):
        old = make_ticket(priority="urgent", created_at=timezone.now() - timedelta(hours=5))
        fresh = make_ticket(priority="urgent")
        self.assertTrue(old.is_overdue)
        self.assertFalse(fresh.is_overdue)

    def test_first_public_staff_reply_sets_first_response(self):
        agent = get_user_model().objects.create_user("agent", is_staff=True)
        t = make_ticket()
        Comment.objects.create(ticket=t, author=agent, body="Internal note", internal=True)
        t.refresh_from_db()
        self.assertIsNone(t.first_response_at)
        reply = Comment.objects.create(ticket=t, author=agent, body="Looking into it")
        t.refresh_from_db()
        self.assertEqual(t.first_response_at, reply.created_at)
