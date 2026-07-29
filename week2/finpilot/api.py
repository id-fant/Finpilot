"""Small cross-app API helpers — shared by signals/ and portfolio/ views.

Two pieces of plumbing that were drifting into copy-paste across the apps:

  result_count(response) — read the row total off a (possibly paginated) DRF
      list response. WHY: the paginator already ran a COUNT query; logging
      `qs.count()` inside get_queryset would run a second one per request.

  ActionView — base class for the dashboard's "run now" POST endpoints.
      One implementation of the shared contract (403 token gate → launch on
      the background runner → 202 started / 409 already running) instead of
      a near-identical block per endpoint.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def result_count(response) -> int:
    """Total rows in a DRF list response — paginated dict or bare array."""
    data: Any = response.data
    return data.get("count", 0) if isinstance(data, dict) else len(data)


@method_decorator(csrf_protect, name="dispatch")
class ActionView(APIView):
    """POST endpoint that launches a named background task.

    Subclasses set `action_name` and implement `get_task()`. The security
    gate, thread launch, journalling and status codes all live in one place
    (portfolio/runner.py does the actual work):

      202 — started            409 — that task is already running
      403 — denied (needs DEBUG=True or a matching X-Actions-Token)
    """

    action_name: str = ""

    def get_task(self) -> Callable[[], Any]:
        raise NotImplementedError  # pragma: no cover - abstract

    def post(self, request):
        from portfolio import runner
        from portfolio.models import ActionReceipt

        if not runner.action_allowed(request):
            return Response(
                {"error": "actions are disabled — set ACTIONS_TOKEN and send "
                          "X-Actions-Token, or run with DEBUG=True"},
                status=status.HTTP_403_FORBIDDEN)
        raw_key = request.headers.get("Idempotency-Key", "").strip()
        if not raw_key and not settings.DEBUG:
            return Response(
                {"error": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = raw_key or f"dev-{uuid.uuid4()}"
        if len(key) > 80:
            return Response(
                {"error": "Idempotency-Key must be at most 80 characters"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receipt, created = ActionReceipt.objects.get_or_create(
            key=key,
            defaults={"action": self.action_name},
        )
        if not created:
            if receipt.action != self.action_name:
                return Response(
                    {"error": "idempotency key was already used for another action"},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {**receipt.response, "duplicate": True, "idempotency_key": key},
                status=status.HTTP_200_OK,
            )

        state = runner.launch(self.action_name, self.get_task())
        payload = {
            "action": self.action_name,
            "status": state,
            "idempotency_key": key,
            "duplicate": False,
        }
        receipt.status = state
        receipt.response = payload
        receipt.save(update_fields=["status", "response", "updated_at"])
        logger.info("%s: %s", type(self).__name__, state)
        return Response(
            payload,
            status=(status.HTTP_202_ACCEPTED if state == "started"
                    else status.HTTP_409_CONFLICT))
