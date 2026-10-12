from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting for customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    DONE = (Status.RESOLVED, Status.CLOSED)

    title = models.CharField(max_length=200)
    description = models.TextField()
    requester_name = models.CharField(max_length=120)
    requester_email = models.EmailField()
    category = models.CharField(max_length=60, blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(db_index=True, editable=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.title}"

    def save(self, *args, **kwargs):
        hours = settings.HELPDESK_SLA_HOURS[self.priority]
        self.due_at = self.created_at + timedelta(hours=hours)
        if self.status in self.DONE and self.resolved_at is None:
            self.resolved_at = timezone.now()
        elif self.status not in self.DONE:
            self.resolved_at = None
        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        reference = self.resolved_at or timezone.now()
        return reference > self.due_at


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    body = models.TextField()
    internal = models.BooleanField(default=False, help_text="Internal notes are not visible to the requester.")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # The first public reply from staff is the ticket's first response (SLA metric)
        if self.author_id and not self.internal and self.ticket.first_response_at is None:
            Ticket.objects.filter(pk=self.ticket_id, first_response_at__isnull=True).update(first_response_at=self.created_at)
