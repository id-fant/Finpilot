from django.urls import path

from .consumers import DashboardConsumer

websocket_urlpatterns = [
    # django-types only models HTTP callables here; Channels' ASGI callable is
    # the documented runtime contract and works through URLRouter.
    path("ws/dashboard/", DashboardConsumer.as_asgi()),  # pyright: ignore[reportCallIssue, reportArgumentType]
]
