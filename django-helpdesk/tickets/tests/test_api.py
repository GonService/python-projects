from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from tickets.models import Ticket

from .test_models import make_ticket


class PublicApiTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_anyone_can_open_a_ticket(self):
        res = self.client.post(
            "/api/public/tickets/",
            {"title": "Login broken", "description": "Cannot log in", "requester_name": "Bia", "requester_email": "bia@example.com"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("due_at", res.data)
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.status, ticket.priority), ("open", "normal"))

    def test_public_endpoint_ignores_staff_fields_and_validates_email(self):
        res = self.client.post(
            "/api/public/tickets/",
            {
                "title": "x",
                "description": "y",
                "requester_name": "z",
                "requester_email": "z@example.com",
                "priority": "urgent",
                "status": "closed",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Ticket.objects.get().priority, "normal")
        bad = self.client.post("/api/public/tickets/", {"title": "x", "description": "y", "requester_name": "z", "requester_email": "nope"})
        self.assertEqual(bad.status_code, 400)
        self.assertIn("requester_email", bad.data)

    def test_public_cannot_list_tickets(self):
        self.assertEqual(self.client.get("/api/public/tickets/").status_code, 405)
        self.assertEqual(self.client.get("/api/tickets/").status_code, 401)


class StaffApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.agent = User.objects.create_user("agent", password="x", is_staff=True)
        self.customer = User.objects.create_user("customer", password="x")
        self.token = Token.objects.create(user=self.agent)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_non_staff_users_are_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.customer).key}")
        self.assertEqual(self.client.get("/api/tickets/").status_code, 403)

    def test_filters(self):
        make_ticket(title="Printer", priority="low")
        make_ticket(title="Server down", priority="urgent", created_at=timezone.now() - timedelta(hours=6))
        make_ticket(title="Done", status="resolved")

        def titles(query):
            return [t["title"] for t in self.client.get("/api/tickets/" + query).data["results"]]

        self.assertEqual(titles("?priority=urgent"), ["Server down"])
        self.assertEqual(titles("?overdue=1"), ["Server down"])
        self.assertEqual(titles("?status=resolved"), ["Done"])
        self.assertEqual(titles("?q=printer"), ["Printer"])

    def test_assign_and_resolve(self):
        t = make_ticket()
        res = self.client.patch(f"/api/tickets/{t.id}/", {"assignee": "agent", "status": "resolved"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["assignee"], "agent")
        self.assertIsNotNone(res.data["resolved_at"])
        self.assertEqual(self.client.get("/api/tickets/?mine=1").data["count"], 1)

    def test_only_staff_can_be_assigned(self):
        t = make_ticket()
        res = self.client.patch(f"/api/tickets/{t.id}/", {"assignee": "customer"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_comments(self):
        t = make_ticket()
        res = self.client.post(f"/api/tickets/{t.id}/comments/", {"body": "Restarted the service"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["author"], "agent")
        self.assertEqual(len(self.client.get(f"/api/tickets/{t.id}/comments/").data), 1)
        t.refresh_from_db()
        self.assertIsNotNone(t.first_response_at)

    def test_stats(self):
        make_ticket(priority="urgent", created_at=timezone.now() - timedelta(hours=5))
        make_ticket(priority="low")
        make_ticket(status="closed")
        data = self.client.get("/api/tickets/stats/").data
        self.assertEqual(data["open"], 2)
        self.assertEqual(data["overdue"], 1)
        self.assertEqual(data["by_status"]["closed"], 1)
        self.assertEqual(data["open_by_priority"], {"low": 1, "normal": 0, "high": 0, "urgent": 1})


class HealthTests(APITestCase):
    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
