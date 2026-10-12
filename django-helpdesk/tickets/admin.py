from django.contrib import admin
from django.utils import timezone

from .models import Comment, Ticket


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1
    fields = ("body", "internal", "author", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "requester_email", "priority", "status", "assignee", "due_at", "overdue")
    list_filter = ("status", "priority", "category", "assignee")
    search_fields = ("title", "description", "requester_email", "requester_name")
    readonly_fields = ("created_at", "updated_at", "first_response_at", "resolved_at", "due_at")
    inlines = [CommentInline]
    actions = ["mark_resolved", "assign_to_me"]
    list_select_related = ("assignee",)

    @admin.display(boolean=True, description="Overdue")
    def overdue(self, obj: Ticket) -> bool:
        return obj.is_overdue

    @admin.action(description="Mark selected tickets as resolved")
    def mark_resolved(self, request, queryset):
        for ticket in queryset.exclude(status__in=Ticket.DONE):
            ticket.status = Ticket.Status.RESOLVED
            ticket.save()

    @admin.action(description="Assign selected tickets to me")
    def assign_to_me(self, request, queryset):
        queryset.update(assignee=request.user, updated_at=timezone.now())

    def save_formset(self, request, form, formset, change):
        for comment in formset.save(commit=False):
            if comment.author_id is None:
                comment.author = request.user
            comment.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()
