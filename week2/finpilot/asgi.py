"""ASGI entry point for HTTP and dashboard WebSockets."""
import os

from channels.auth import AuthMiddlewareStack  # pyrefly: ignore[missing-import]
from channels.routing import ProtocolTypeRouter, URLRouter  # pyrefly: ignore[missing-import]
from channels.security.websocket import AllowedHostsOriginValidator  # pyrefly: ignore[missing-import]
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")
django_asgi_app = get_asgi_application()

from .routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
