"""App config for `core` — the framework-free data + strategy engine.

`core` has no models. It exists as an app only so its modules group cleanly and
it shows up in INSTALLED_APPS for discoverability.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
