"""Root URL configuration for the FinPilot project.

Each app owns its own urls.py; this file just mounts them under a prefix.
WHY: keeps routing modular — an app can be moved or removed by changing one line.
"""
from django.contrib import admin
from django.urls import include, path

from .system import SystemStatusView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/signals/", include("signals.urls")),
    path("api/portfolio/", include("portfolio.urls")),
    # Research endpoints — the quant/ track served over HTTP.
    path("api/quant/", include("portfolio.quant_urls")),
    # The control-room aggregate: config, gates, data state, running actions.
    path("api/system/", SystemStatusView.as_view(), name="system-status"),
]
