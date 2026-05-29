"""Daily Zerodha Kite Connect login helper.

Zerodha forces an interactive login *once per trading day*: an access_token
expires the next morning. This script automates the dance:

    python week4/scripts/kite_login.py

  1. Reads KITE_API_KEY + KITE_API_SECRET from week2/.env.
  2. Opens Kite's login URL in your browser.
  3. After you log in, Kite redirects you to your app's redirect URL with a
     `request_token=...` query parameter — paste it back into the prompt.
  4. The script exchanges request_token for an access_token (valid until the
     next morning ~07:30 IST) and writes it into week2/.env as
     KITE_ACCESS_TOKEN — so the Celery task picks it up automatically.

WHY this can't be fully automated: the login step REQUIRES a human (TOTP / 2FA
on Kite's site). That's a deliberate Zerodha safety control — any "headless
Kite login" you find on the internet is brittle and breaks the moment Kite
rotates the form. The 30-second manual step is the price of trading real money.

USAGE:
    cd <repo root>
    python week4/scripts/kite_login.py            # interactive
    python week4/scripts/kite_login.py --token X  # if you already have the request_token
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / "week2" / ".env"


def load_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. No external dep — keeps the script
    runnable from a fresh Python without first installing python-dotenv."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def upsert_env(env_path: Path, key: str, value: str) -> None:
    """Replace `key=...` in .env, or append it if absent. Preserves comments
    and ordering so the file stays human-readable after the script runs."""
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        # Match `KEY=...` ignoring leading whitespace, but skip commented lines.
        stripped = line.lstrip()
        if stripped.startswith(f"{key}=") and not stripped.startswith("#"):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    # `__doc__` is `str | None` but every module in this project has a
    # docstring; the runtime guard is implicit (an AttributeError would be
    # immediate at import-time, not in production traffic).
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    parser.add_argument("--token", help="paste a request_token you already have")
    parser.add_argument("--no-browser", action="store_true",
                        help="print the login URL but don't open the browser")
    args = parser.parse_args()

    try:
        from kiteconnect import KiteConnect  # pyrefly: ignore[missing-import]  # pyright: ignore[reportMissingImports]
    except ImportError:
        print("kiteconnect is not installed.\n"
              "  Activate the venv and run:  pip install kiteconnect",
              file=sys.stderr)
        return 1

    env = load_env(ENV_PATH)
    api_key = env.get("KITE_API_KEY") or os.environ.get("KITE_API_KEY")
    api_secret = env.get("KITE_API_SECRET") or os.environ.get("KITE_API_SECRET")
    if not api_key or not api_secret:
        print(f"KITE_API_KEY and KITE_API_SECRET must be set in {ENV_PATH}.\n"
              "  Register a Kite Connect app at https://developers.kite.trade,\n"
              "  then paste the values into week2/.env.", file=sys.stderr)
        return 1

    kite = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    request_token = args.token
    if not request_token:
        print("\n[kite] step 1 — open the login URL and sign in:")
        print(f"  {login_url}\n")
        if not args.no_browser:
            try:
                webbrowser.open(login_url)
            except Exception:  # noqa: BLE001 - browser launch is best-effort
                pass
        print("[kite] step 2 — after login Zerodha redirects you to your app's "
              "redirect URL, e.g.\n"
              "  https://your-redirect/?request_token=ABC123&action=login&status=success\n"
              "  Copy the request_token value from that URL and paste it below.\n")
        request_token = input("request_token: ").strip()

    if not request_token:
        print("[kite] no request_token provided — aborting.", file=sys.stderr)
        return 1

    try:
        session = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as exc:  # noqa: BLE001 - we want the full message
        # The most common failure is "Token is invalid or has expired" — Kite's
        # request_tokens are good for only a few minutes after issue.
        print(f"[kite] generate_session failed: {exc}", file=sys.stderr)
        return 1

    # pyrefly: ignore[bad-index] -- kiteconnect stubs mistype session as bytes; it is a dict
    access_token = session["access_token"]  # pyright: ignore[reportCallIssue,reportArgumentType]
    upsert_env(ENV_PATH, "KITE_ACCESS_TOKEN", access_token)
    print(f"\n[kite] success — KITE_ACCESS_TOKEN written to {ENV_PATH}.")
    print("[kite] this token is valid until tomorrow morning (~07:30 IST).")
    print("[kite] re-run this script each trading day before market open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
