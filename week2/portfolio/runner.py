"""Background task runner for the dashboard's "run now" actions.

WHY threads and not Celery here: the action buttons must work on a bare
`python run.py` setup — no Redis, no worker. A daemon thread inside the
Django process is enough for a single-user dev tool; the Celery path still
exists for scheduled production runs. (If both fire, the tasks' own
idempotency — update_or_create keyed on (stock, date), order dedup on
(signal, side) — makes the overlap harmless.)

WHY a registry + lock: double-clicking "Refresh signals" must not run the
task twice concurrently. One slot per task name; a second launch while the
first is running returns `already_running` and the UI says so.

Observability contract: every launch writes a JournalEntry START row and a
DONE/FAILED row on completion — the dashboard polls /api/system/ (which
reads this registry) and the Journal view shows the outcome. No silent
background work.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from django.conf import settings

logger = logging.getLogger(__name__)

# task name -> {"running": bool, "started_at": iso, "finished_at": iso|None,
#               "result": summary|None, "error": str|None}
_registry: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def action_allowed(request) -> bool:
    """Gate for state-changing endpoints.

    DEBUG (local dev) -> allowed. Otherwise the request must carry
    X-Actions-Token matching ACTIONS_TOKEN from the environment. WHY: these
    endpoints trigger real work (and, with BROKER=kite, real orders) — an
    AllowAny POST on a public deploy would let anyone trade. Deny-by-default
    when no token is configured.
    """
    if settings.DEBUG:
        return True
    expected = getattr(settings, "ACTIONS_TOKEN", "")
    return bool(expected) and request.headers.get("X-Actions-Token") == expected


def launch(name: str, fn: Callable[[], Any]) -> str:
    """Start `fn` on a daemon thread under the task-name slot.

    Returns "started" or "already_running".
    """
    from .models import JournalEntry

    with _lock:
        state = _registry.get(name)
        if state and state["running"]:
            return "already_running"
        _registry[name] = {
            "running": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None, "result": None, "error": None,
        }

    JournalEntry.objects.create(
        stage="session", decision="START",
        detail=f"dashboard action '{name}' launched",
    )

    def _run() -> None:
        from .models import JournalEntry as JE  # thread gets its own import
        state = _registry[name]
        try:
            result = fn()
            state["result"] = result
            JE.objects.create(
                stage="session", decision="DONE",
                detail=f"dashboard action '{name}' finished — {result}",
                payload={"action": name, "result": result},
            )
        except Exception as e:  # noqa: BLE001 - surface, never crash the thread silently
            state["error"] = str(e)
            logger.error("action '%s' failed: %s", name, e, exc_info=True)
            JE.objects.create(
                stage="session", decision="FAILED",
                detail=f"dashboard action '{name}' failed — {e}",
            )
        finally:
            state["running"] = False
            state["finished_at"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_run, name=f"action-{name}", daemon=True).start()
    return "started"


def status() -> dict[str, dict[str, Any]]:
    """Registry snapshot for /api/system/ — safe to serialise as-is."""
    with _lock:
        return {k: dict(v) for k, v in _registry.items()}
