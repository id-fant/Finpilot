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
from typing import Any, Callable

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def result_count(response) -> int:
    """Total rows in a DRF list response — paginated dict or bare array."""
    data: Any = response.data
    return data.get("count", 0) if isinstance(data, dict) else len(data)


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
        if not runner.action_allowed(request):
            return Response(
                {"error": "actions are disabled — set ACTIONS_TOKEN and send "
                          "X-Actions-Token, or run with DEBUG=True"},
                status=status.HTTP_403_FORBIDDEN)
        state = runner.launch(self.action_name, self.get_task())
        logger.info("%s: %s", type(self).__name__, state)
        return Response(
            {"action": self.action_name, "status": state},
            status=(status.HTTP_202_ACCEPTED if state == "started"
                    else status.HTTP_409_CONFLICT))
