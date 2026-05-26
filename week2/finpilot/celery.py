"""Celery application for FinPilot.

INTERVIEW — Celery worker vs Celery beat (a very common question):
  * A WORKER is a process that executes tasks pulled off the queue. You can run
    many workers to scale throughput.
  * BEAT is the scheduler. It executes nothing itself — it just enqueues tasks
    on a timetable (e.g. generate_daily_signals at 09:05 IST every weekday).
  * So in production you run BOTH: exactly one beat (the clock) and one or more
    workers (the muscle). Beat decides WHEN, the worker does the WORK.

  Why not plain cron? cron only runs a script — no retries, no result tracking,
  no priority queues, and a long job blocks the next run. Celery gives all of
  that, and one worker fleet serves both scheduled and on-demand tasks.
"""
from __future__ import annotations

import os

from celery import Celery

# WHY: Celery needs Django's settings to find the broker URL etc. This must be
# set before the Celery app reads the config.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")

app = Celery("finpilot")

# WHY namespace="CELERY": Celery reads its configuration straight from Django
# settings, picking up every setting prefixed with CELERY_ (CELERY_BROKER_URL,
# CELERY_TIMEZONE, ...). One config file for the whole project.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover a tasks.py module in every installed app — no manual import list
# to keep in sync as the project grows.
app.autodiscover_tasks()
