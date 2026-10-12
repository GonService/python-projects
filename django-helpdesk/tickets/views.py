from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, status, viewsets
from rest_framework.throttling import ScopedRateThrottle

from .models import Ticket
from .serializers import CommentSerializer, PublicTicketSerializer, TicketSerializer


class TicketViewSet(viewsets.ModelViewSet):
    """Staff API: list, filter, update and comment on tickets."""

    serializer_class = TicketSerializer
    filterable = ("status", "priority", "category")

    def get_queryset(self):
        qs = Ticket.objects.select_related("assignee")
        for field in self.filterable:
            if value := self.request.query_params.get(field):
                qs = qs.filter(**{field: value})
        if self.request.query_params.get("overdue") in {"1", "true"}:
            qs = qs.exclude(status__in=Ticket.DONE).filter(due_at__lt=timezone.now())
        if self.request.query_params.get("mine") in {"1", "true"}:
            qs = qs.filter(assignee=self.request.user)
        if term := self.request.query_params.get("q"):
            qs = qs.filter(Q(title__icontains=term) | Q(description__icontains=term) | Q(requester_email__icontains=term))
        return qs

    @decorators.action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == "GET":
            return response.Response(CommentSerializer(ticket.comments.all(), many=True).data)
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ticket=ticket, author=request.user)
        return response.Response(serializer.data, status=status.HTTP_201_CREATED)

    @decorators.action(detail=False, methods=["get"])
    def stats(self, request):
        now = timezone.now()
        open_qs = Ticket.objects.exclude(status__in=Ticket.DONE)
        by_status = dict(Ticket.objects.values_list("status").annotate(n=Count("id")))
        by_priority = dict(open_qs.values_list("priority").annotate(n=Count("id")))
        return response.Response(
            {
                "open": open_qs.count(),
                "overdue": open_qs.filter(due_at__lt=now).count(),
                "by_status": {s: by_status.get(s, 0) for s in Ticket.Status.values},
                "open_by_priority": {p: by_priority.get(p, 0) for p in Ticket.Priority.values},
            }
        )


class PublicTicketViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Anyone can open a ticket (rate limited). Used by a website form or a support widget."""

    serializer_class = PublicTicketSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_ticket"
    queryset = Ticket.objects.none()
