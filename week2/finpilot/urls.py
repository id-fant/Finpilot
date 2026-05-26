"""Root URL configuration for the FinPilot project.

Each app owns its own urls.py; this file just mounts them under a prefix.
WHY: keeps routing modular — an app can be moved or removed by changing one line.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/signals/", include("signals.urls")),
    path("api/portfolio/", include("portfolio.urls")),
]
