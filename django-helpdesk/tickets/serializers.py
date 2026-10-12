from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Comment, Ticket


class StaffUsernameField(serializers.SlugRelatedField):
    """Assignee by username, limited to staff users."""

    def __init__(self, **kwargs):
        super().__init__(slug_field="username", **kwargs)

    def get_queryset(self):
        return get_user_model().objects.filter(is_staff=True)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "internal", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    assignee = StaffUsernameField(allow_null=True, required=False)

    class Meta:
        model = Ticket
        fields = [
            "id", "title", "description", "requester_name", "requester_email", "category",
            "priority", "status", "assignee", "created_at", "updated_at",
            "first_response_at", "resolved_at", "due_at", "is_overdue",
        ]  # fmt: skip
        read_only_fields = ["id", "created_at", "updated_at", "first_response_at", "resolved_at", "due_at"]


class PublicTicketSerializer(serializers.ModelSerializer):
    """What a customer can send when opening a ticket (no status, assignee or priority)."""

    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "requester_name", "requester_email", "category", "due_at"]
        read_only_fields = ["id", "due_at"]
