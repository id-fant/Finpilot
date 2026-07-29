"""Small boundary for broadcasting dashboard invalidation events."""
from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer  # pyrefly: ignore[missing-import]

logger = logging.getLogger(__name__)
DASHBOARD_GROUP = "finpilot.dashboard"


def publish_dashboard_event(event: str, payload: dict[str, Any] | None = None) -> None:
    """Best-effort event publication; trading work never depends on the UI."""
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            DASHBOARD_GROUP,
            {
                "type": "dashboard.event",
                "event": event,
                "payload": payload or {},
            },
        )
    except Exception:  # noqa: BLE001 - observability must not break execution
        logger.warning("dashboard event publish failed", exc_info=True)
