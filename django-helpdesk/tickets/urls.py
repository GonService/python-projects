from rest_framework.routers import DefaultRouter

from .views import PublicTicketViewSet, TicketViewSet

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="ticket")
router.register("public/tickets", PublicTicketViewSet, basename="public-ticket")

urlpatterns = router.urls
