from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

admin.site.site_header = "Helpdesk"
admin.site.site_title = "Helpdesk"
admin.site.index_title = "Support tickets"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("tickets.urls")),
    path("healthz", lambda request: JsonResponse({"status": "ok"})),
]
