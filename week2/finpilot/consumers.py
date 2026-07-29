"""Read-only live event stream for the public FinPilot dashboard."""
from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer  # pyrefly: ignore[missing-import]

from .events import DASHBOARD_GROUP


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        # The same information is already exposed by the public read-only REST
        # snapshot. Origin/host validation happens in asgi.py; state-changing
        # actions remain protected by CSRF + staff/token checks over HTTP.
        await self.channel_layer.group_add(DASHBOARD_GROUP, self.channel_name)
        await self.accept()
        await self.send_json({
            "event": "connection.ready",
            "payload": {"transport": "websocket"},
        })

    async def disconnect(self, code: int) -> None:
        await self.channel_layer.group_discard(
            DASHBOARD_GROUP, self.channel_name,
        )

    async def dashboard_event(self, event: dict) -> None:
        await self.send_json({
            "event": event["event"],
            "payload": event.get("payload", {}),
        })
