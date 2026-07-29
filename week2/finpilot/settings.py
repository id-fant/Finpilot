"""Django settings for the FinPilot project.

WHY 12-factor config: every secret and environment-specific value is read from
the environment (a .env file in dev). The same code runs unchanged in dev and
prod — only the environment variables differ. Secrets are never hardcoded.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR is week2/ — the folder containing manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load week2/.env into os.environ. Safe to call if the file is absent.
load_dotenv(BASE_DIR / ".env")

# Make the week3 LLM package importable from Django (signals/views.py calls
# llm.explainer.explain_signal). WHY here: settings.py runs once at startup,
# so the manipulation happens in exactly one place. WHY guarded: if week3/ is
# not deployed alongside week2/, Django still boots — only the explain endpoint
# fails with a clean 503.
WEEK3_DIR = BASE_DIR.parent / "week3"
if WEEK3_DIR.exists() and str(WEEK3_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK3_DIR))

# ── Core security ────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
# WHY compare to the string "True": env vars are always strings.
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True") == "True"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_celery_beat",
    "channels",
    # FinPilot apps
    "core",
    "signals",
    "portfolio",
]

MIDDLEWARE = [
    # WHY CorsMiddleware first: it must run before any middleware that can
    # generate a response, so CORS headers are attached to every reply.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if not DEBUG:
    MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "finpilot.urls"
WSGI_APPLICATION = "finpilot.wsgi.application"
ASGI_APPLICATION = "finpilot.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Database ─────────────────────────────────────────────────────────────────
# SQLite for dev (no setup); PostgreSQL when DATABASE_URL is set.
# WHY dj_database_url: it parses one DATABASE_URL string into Django's config
# dict, so switching to Postgres in prod needs a single env var, no code change.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    # WHY import here, not at module top: dj-database-url is only needed when a
    # DATABASE_URL is set (PostgreSQL, typically prod). SQLite dev then runs
    # without that package installed at all — one less dependency locally.
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Localisation ─────────────────────────────────────────────────────────────
# WHY Asia/Kolkata + USE_TZ: NSE trades in IST. Django stores timestamps in UTC
# (USE_TZ) and displays them in IST — so the daily 09:05 schedule stays correct
# regardless of server location or daylight-saving quirks elsewhere.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The production container copies Vite's output here. WhiteNoise serves those
# root assets (index.html, /assets, manifest and service worker) on the same
# origin as the API, eliminating production CORS/CSRF and cache split-brain.
FRONTEND_DIST = BASE_DIR / "frontend_dist"
if FRONTEND_DIST.exists():
    WHITENOISE_ROOT = FRONTEND_DIST
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    # WHY AllowAny for now: Week 2 ships a read-only public API. Authentication
    # is tightened in a later week — left explicit here so it is not forgotten.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

# ── CORS ─────────────────────────────────────────────────────────────────────
# WHY: the Week 4 dashboard is static JS served from another origin; the browser
# blocks its fetch() calls unless this API explicitly allows that origin.
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
).split(",")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
).split(",")

# Live dashboard events. Redis is the production channel layer; tests and the
# one-process demo use the in-memory layer so the UI remains functional without
# infrastructure. Set CHANNEL_REDIS_URL alongside Celery's Redis URL in prod.
CHANNEL_REDIS_URL = os.environ.get("CHANNEL_REDIS_URL", "")
if CHANNEL_REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [CHANNEL_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# ── Celery ───────────────────────────────────────────────────────────────────
# WHY Redis as broker: simplest broker to run in dev and prod. The web process
# ENQUEUES tasks onto Redis; a separate worker process pulls and EXECUTES them —
# so a slow job never blocks an HTTP request.
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TIMEZONE = TIME_ZONE
# DatabaseScheduler stores the Beat schedule in the DB, so it is editable from
# the Django admin instead of being hardcoded.
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# WHY a static CELERY_BEAT_SCHEDULE alongside the DatabaseScheduler: this is the
# *default* timetable. On first start, django-celery-beat seeds these into the
# DB; from then on you can tweak them from the admin without a redeploy. The
# code remains the source of truth for "what the schedule looks like out of the
# box" — so a fresh clone is immediately automated, no manual setup.
#
# NSE opens 09:15 IST. We run BOTH tasks during the day:
#   09:05 IST — generate today's signals from fresh OHLCV (pre-open).
#   09:20 IST — execute_signal_orders converts BUY/SELL signals into broker
#               orders once the market is actually open and prices are real.
from celery.schedules import crontab  # noqa: E402 — kept next to the schedule

CELERY_BEAT_SCHEDULE = {
    # crontab fields are cron-style strings ("9", "*/2", "mon-fri") — celery's
    # own API and type stubs treat hour/minute as str, matching day_of_week
    # below. Passing strings (not ints) keeps all three fields consistent and
    # type-clean with no suppression needed.
    "daily-signals": {
        "task": "signals.generate_daily_signals",
        "schedule": crontab(hour="9", minute="5", day_of_week="mon-fri"),
    },
    "execute-signal-orders": {
        "task": "portfolio.execute_signal_orders",
        "schedule": crontab(hour="9", minute="20", day_of_week="mon-fri"),
    },
}

# ── Broker (Week 4 integration) ──────────────────────────────────────────────
# Which broker the daily order task uses. "paper" is the safe default — a
# simulated broker; no real money, no exchange. Set BROKER=kite to route orders
# through Zerodha Kite (requires KITE_API_KEY + KITE_ACCESS_TOKEN, the latter
# refreshed every morning via week4/scripts/kite_login.py).
BROKER = os.environ.get("BROKER", "paper").lower()
# A fixed rupee budget per trade, used by OrderManager to size the quantity.
BROKER_MAX_TRADE_VALUE = float(os.environ.get("BROKER_MAX_TRADE_VALUE", "50000"))
BROKER_MAX_POSITIONS = int(os.environ.get("BROKER_MAX_POSITIONS", "10"))
BROKER_MAX_DAILY_ORDERS = int(os.environ.get("BROKER_MAX_DAILY_ORDERS", "20"))
PAPER_STARTING_CASH = float(os.environ.get("PAPER_STARTING_CASH", "1000000"))

# ── LLM analyst gate (Week 3 integration) ────────────────────────────────────
# "auto" — the analyst reviews each proposed trade when GEMINI_API_KEY is set,
#          and is silently skipped when it isn't (fail-open: the deterministic
#          engine + OrderManager caps are the load-bearing safety rails).
# "off"  — never call the analyst, even with a key (e.g. to save quota, or to
#          A/B the gate's effect on the paper book).
ANALYST_GATE = os.environ.get("ANALYST_GATE", "auto").lower()

# ── Meta-labeling ML gate (quant/04 integration) ─────────────────────────────
# "auto" — BUY signals scored by the meta-model are skipped when
#          P(clears costs) < ML_GATE_THRESHOLD. Silently inactive when the
#          model artifact is missing (core/ml_gate.py returns None).
# "off"  — never gate on the ML score, even when signals carry one.
# Threshold default 0 means "use the threshold chosen at training time"
# (stored in the model's meta JSON, picked on out-of-sample data).
ML_GATE = os.environ.get("ML_GATE", "auto").lower()
ML_GATE_THRESHOLD = float(os.environ.get("ML_GATE_THRESHOLD", "0"))

# ── Quantitative trade controls ──────────────────────────────────────────────
# These controls reduce or skip risk; none of them can increase a trade beyond
# BROKER_MAX_TRADE_VALUE. Missing history/model inputs fail open.
TREND_FILTER = os.environ.get("TREND_FILTER", "auto").lower()
EV_GATE = os.environ.get("EV_GATE", "auto").lower()
EV_MIN_EDGE = float(os.environ.get("EV_MIN_EDGE", "0.002"))
VOL_TARGET = float(os.environ.get("VOL_TARGET", "0.15"))
VOL_HALFLIFE = int(os.environ.get("VOL_HALFLIFE", "20"))
KELLY_FRACTION = float(os.environ.get("KELLY_FRACTION", "0.25"))
KELLY_MAX_CAPITAL_FRACTION = float(
    os.environ.get("KELLY_MAX_CAPITAL_FRACTION", "0.05")
)
RISK_CAPITAL = float(os.environ.get("RISK_CAPITAL", str(PAPER_STARTING_CASH)))

# ── Dashboard actions (POST /api/signals/refresh/, /api/portfolio/execute-orders/) ──
# In DEBUG the buttons just work. Deployed, a request must send
# X-Actions-Token matching this value — an open POST that can trigger trades
# is not acceptable on a public URL. Empty + not DEBUG = actions disabled.
ACTIONS_TOKEN = os.environ.get("ACTIONS_TOKEN", "")

# Make week4/ importable from week2 code (signals/, portfolio/). The broker
# package is deliberately framework-free (see HANDOFF §5) and lives outside
# week2/, so we extend sys.path here — settings.py is the canonical place to
# do this since it loads before any app code (and before Celery autodiscovers
# tasks). Without this, `from broker import PaperBroker` inside a task fails.
import sys  # noqa: E402

_WEEK4 = BASE_DIR.parent / "week4"
if _WEEK4.is_dir() and str(_WEEK4) not in sys.path:
    sys.path.insert(0, str(_WEEK4))

# ── Logging ──────────────────────────────────────────────────────────────────
# WHY logging over print(): logs carry a level, a timestamp and a source, can
# be filtered, and route to files/aggregators in prod. To pinpoint a runtime
# issue you need WHEN, WHERE and WHAT — the `verbose` formatter below carries
# all three: timestamp, level, and `logger:line function()`.
#
# Tunable from .env:
#   DJANGO_LOG_LEVEL=DEBUG  -> turn on the detailed step-by-step traces in
#                              core/ signals/ portfolio/ (fetches, indicator
#                              votes, per-stock task progress).
#   DJANGO_SQL_LOG=True     -> log every SQL query (very noisy; use only when
#                              chasing a database problem).
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()
SQL_LOG = os.environ.get("DJANGO_SQL_LOG", "False") == "True"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # WHEN     LEVEL    WHERE (logger:line function)        | WHAT
        "verbose": {
            "format": "{asctime} {levelname:<8} {name}:{lineno} {funcName}() | {message}",
            "datefmt": "%H:%M:%S",
            "style": "{",
        },
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "loggers": {
        # FinPilot's own code — verbosity controlled by DJANGO_LOG_LEVEL.
        "core": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "signals": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "portfolio": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "finpilot": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        # Django itself — INFO is enough; `django.request` surfaces 4xx/5xx here.
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # Every SQL statement — off by default (noisy), on via DJANGO_SQL_LOG.
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG" if SQL_LOG else "WARNING",
            "propagate": False,
        },
    },
    # Catch-all for any logger not named above.
    "root": {"handlers": ["console"], "level": "WARNING"},
}
