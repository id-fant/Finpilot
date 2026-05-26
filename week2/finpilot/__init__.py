"""FinPilot Django project package.

WHY this import: it makes the Celery app load as soon as Django starts, so the
@shared_task decorator and Celery's settings are wired up before any app code
runs. Without it, tasks defined with @shared_task might not register.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
