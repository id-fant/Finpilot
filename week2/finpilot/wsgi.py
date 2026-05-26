"""WSGI entry point for FinPilot.

WSGI is the synchronous server interface Django speaks. In production a server
like gunicorn imports `application` from here and serves it. `runserver` is
dev-only — never use it in production.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finpilot.settings")

application = get_wsgi_application()
