#!/usr/bin/env python3
"""FinPilot — unified launcher. One command brings the whole app online.

    python run.py

What it does, in order:
  1. Creates the project virtualenv (week2/.venv) if it does not exist.
  2. Installs week2/requirements.txt into it — only on first run, or when a
     dependency is missing (the check is fast, so re-runs are instant).
  3. Writes week2/.env from .env.example, with a fresh random SECRET_KEY, if
     no .env is present yet.
  4. Applies database migrations and seeds the starter NIFTY universe.
  5. Starts TWO servers and leaves them running until you press Ctrl+C:
       - the Django REST API           http://127.0.0.1:8000
       - the static week4 dashboard    http://127.0.0.1:5500
  6. Opens the dashboard in your browser.

WHY one launcher: the project spans several folders, each with its own setup
steps. New contributors (and future-you) should not have to re-derive the
sequence — this script IS the runbook, executable.

Useful flags:
  --demo           seed a self-contained demo dataset (signals + orders + one
                   open position) so the dashboard renders every panel without
                   waiting for a live job. Ideal for screenshots / Loom recording.
  --refresh        regenerate today's signals via live yfinance before serving
  --offline        with --refresh: use synthetic data instead (no network)
  --no-browser     do not open the browser automatically
  --skip-install   skip the dependency check (use when you know the venv is set)

This script is plain standard-library Python 3 — run it with whatever Python
you have; it bootstraps its own isolated environment from there.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Make the launcher's OWN output UTF-8 safe. A Windows console defaults to a
# legacy code page (cp1252) that cannot encode characters like the arrow below;
# reconfiguring to UTF-8 keeps run.py portable. (Child processes get the same
# treatment via PYTHONUTF8 in CHILD_ENV.)
for _stream in (sys.stdout, sys.stderr):
    try:
        # `reconfigure` exists on TextIOWrapper at runtime but is missing from
        # the typeshed TextIO Protocol — the try/except below is the real guard.
        _stream.reconfigure(encoding="utf-8", errors="replace")  # pyrefly: ignore[missing-attribute]
    except (AttributeError, ValueError):  # pragma: no cover - very old Python
        pass

# ── Layout ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
WEEK2 = ROOT / "week2"                       # the Django backend
VENV = WEEK2 / ".venv"                       # the one project virtualenv
FRONTEND = ROOT / "week4" / "frontend"       # the static dashboard
REQUIREMENTS = WEEK2 / "requirements.txt"

# Fixed ports. They are hardcoded on purpose: settings.py whitelists port 5500
# for CORS and dashboard.js points fetch() at port 8000 — keeping them constant
# means every piece lines up with no configuration.
API_PORT = 8000
DASH_PORT = 5500

# A subprocess environment that prints UTF-8 cleanly on a Windows console
# (the default code page mangles the em-dashes in our log messages) and does
# not buffer output, so logs appear live.
CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}


# ── Small console helpers ────────────────────────────────────────────────────
def say(message: str) -> None:
    """Print a launcher status line, visually distinct from app logs."""
    print(f"\n\033[1;36m[finpilot]\033[0m {message}", flush=True)


def fail(message: str) -> int:
    """Print an error and return a non-zero exit code."""
    print(f"\n\033[1;31m[finpilot] ERROR:\033[0m {message}", file=sys.stderr)
    return 1


# ── Environment bootstrap ────────────────────────────────────────────────────
def venv_python() -> Path:
    """Path to the python executable inside the project virtualenv."""
    # Windows puts it in Scripts/; POSIX in bin/ — support both.
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_venv() -> Path:
    """Create the virtualenv on first run; return its python executable."""
    py = venv_python()
    if py.exists():
        return py
    say(f"creating virtualenv at {VENV.relative_to(ROOT)} ...")
    # WHY use the CURRENT interpreter to build the venv: it guarantees the venv
    # uses the same Python the user invoked run.py with — no surprises.
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    return py


def deps_satisfied(py: Path) -> bool:
    """True if the key third-party packages import cleanly in the venv.

    A cheap proxy for "requirements are installed" — far faster than re-running
    pip on every launch. If any import fails, we (re)install.
    """
    probe = "import django, rest_framework, celery, pandas, yfinance, corsheaders"
    result = subprocess.run([str(py), "-c", probe], capture_output=True)
    return result.returncode == 0


def install_deps(py: Path) -> None:
    """Install week2/requirements.txt into the virtualenv."""
    say("installing dependencies (first run only — this can take 1-2 min) ...")
    subprocess.check_call(
        [str(py), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "-r", str(REQUIREMENTS)]
    )


def ensure_env_file() -> None:
    """Create week2/.env from the template, with a fresh SECRET_KEY, if absent.

    WHY: the 12-factor rule is "config in the environment". The app runs with a
    built-in insecure fallback key, but generating a real per-machine key here
    means the dev setup is correct from the very first launch.
    """
    env_path = WEEK2 / ".env"
    template = WEEK2 / ".env.example"
    if env_path.exists() or not template.exists():
        return
    import secrets

    text = template.read_text(encoding="utf-8").replace(
        "replace-with-a-long-random-string", secrets.token_urlsafe(50)
    )
    env_path.write_text(text, encoding="utf-8")
    say("created week2/.env from the template (with a fresh SECRET_KEY)")


# ── Django management commands ───────────────────────────────────────────────
def manage(py: Path, *args: str) -> None:
    """Run `python manage.py <args>` inside week2/, raising on failure."""
    subprocess.check_call([str(py), "manage.py", *args], cwd=WEEK2, env=CHILD_ENV)


def signal_count(py: Path) -> int:
    """Return how many Signal rows are in the database (0 if it cannot tell)."""
    code = "from signals.models import Signal; print(Signal.objects.count())"
    result = subprocess.run(
        [str(py), "manage.py", "shell", "-c", code],
        cwd=WEEK2, env=CHILD_ENV, capture_output=True, text=True,
    )
    # The count is the last non-empty line of stdout; be defensive about it.
    for line in reversed(result.stdout.splitlines()):
        if line.strip().isdigit():
            return int(line.strip())
    return 0


def seed_demo(py: Path) -> None:
    """Insert a self-contained demo dataset via the seed_demo management command.

    Use this when you want the dashboard to look populated immediately —
    screenshots, Loom recordings, walking a recruiter through the UI without
    waiting for the 09:05 IST signal job. Idempotent: re-running keeps the
    same stable rows.
    """
    say("seeding demo data (signals + orders + one open position) ...")
    manage(py, "seed_demo")


def refresh_signals(py: Path, offline: bool) -> None:
    """Generate today's signals so the dashboard has something to show.

    offline=True uses the smoke test's synthetic price series (no network);
    offline=False does a live yfinance fetch for every tracked stock.
    """
    if offline:
        say("generating signals from synthetic data (offline) ...")
        subprocess.run([str(py), "smoke_test.py", "--offline"],
                       cwd=WEEK2, env=CHILD_ENV, check=False)
    else:
        say("generating signals via live market data (yfinance) ...")
        code = ("from signals.tasks import generate_daily_signals as g; "
                "print(g())")
        subprocess.run([str(py), "manage.py", "shell", "-c", code],
                       cwd=WEEK2, env=CHILD_ENV, check=False)


# ── The two long-running servers ─────────────────────────────────────────────
def start_servers(py: Path) -> list[subprocess.Popen]:
    """Start the API and the dashboard server; return both process handles."""
    say(f"starting the Django API     ->  http://127.0.0.1:{API_PORT}")
    # --noreload: one process, not two. The launcher is for RUNNING the app,
    # not editing it, so the autoreloader just complicates a clean shutdown.
    api = subprocess.Popen(
        [str(py), "manage.py", "runserver", "--noreload", f"127.0.0.1:{API_PORT}"],
        cwd=WEEK2, env=CHILD_ENV,
    )

    say(f"starting the dashboard      ->  http://127.0.0.1:{DASH_PORT}")
    # http.server is the standard library's static file server — enough for a
    # build-step-free frontend, and it keeps the launcher dependency-free.
    dashboard = subprocess.Popen(
        [str(py), "-m", "http.server", str(DASH_PORT),
         "--bind", "127.0.0.1", "--directory", str(FRONTEND)],
        env=CHILD_ENV,
    )
    return [api, dashboard]


def supervise(procs: list[subprocess.Popen]) -> int:
    """Block until Ctrl+C or a server dies; then shut everything down cleanly."""
    try:
        while True:
            for proc in procs:
                code = proc.poll()
                if code is not None:
                    return fail(f"a server exited unexpectedly (code {code}). "
                                f"The most common cause is a port already in "
                                f"use ({API_PORT} or {DASH_PORT}).")
            time.sleep(0.5)
    except KeyboardInterrupt:
        say("shutting down (Ctrl+C) ...")
        return 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="FinPilot unified launcher — set up and run the whole app.")
    parser.add_argument("--demo", action="store_true",
                        help="seed a demo dataset so the dashboard is populated "
                             "without a live signal job (good for screenshots).")
    parser.add_argument("--refresh", action="store_true",
                        help="regenerate today's signals before serving")
    parser.add_argument("--offline", action="store_true",
                        help="with --refresh: use synthetic data, no network")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open the dashboard in a browser")
    parser.add_argument("--skip-install", action="store_true",
                        help="skip the dependency check / install step")
    args = parser.parse_args()

    if not WEEK2.exists():
        return fail(f"expected the backend at {WEEK2} — run this from the repo root.")

    # 1-3. Environment: virtualenv, dependencies, .env.
    py = ensure_venv()
    if not args.skip_install and not deps_satisfied(py):
        install_deps(py)
    elif args.skip_install:
        say("skipping dependency check (--skip-install)")
    ensure_env_file()

    # 4. Database: schema + starter data.
    say("applying migrations and seeding the stock universe ...")
    try:
        manage(py, "migrate", "--noinput")
        manage(py, "seed_stocks")
    except subprocess.CalledProcessError as e:
        return fail(f"database setup failed ({e}).")

    # Optionally (re)generate signals so the dashboard is not empty.
    # --demo wins if both are passed: it is faster and deterministic, which is
    # what someone screenshotting the UI almost certainly wants.
    if args.demo:
        seed_demo(py)
    elif args.refresh:
        refresh_signals(py, offline=args.offline)
    elif signal_count(py) == 0:
        say("no signals in the database yet — the dashboard will be empty.\n"
            "           run  `python run.py --demo`        (instant demo data) or\n"
            "                `python run.py --refresh`     (live yfinance) or\n"
            "                `python run.py --refresh --offline`  (synthetic).")

    # 5-6. Servers + browser.
    procs = start_servers(py)
    if not args.no_browser:
        # A short pause lets both servers bind their ports before the tab opens.
        time.sleep(2.0)
        webbrowser.open(f"http://127.0.0.1:{DASH_PORT}")

    say("FinPilot is running. Press Ctrl+C to stop.")
    return supervise(procs)


if __name__ == "__main__":
    sys.exit(main())
