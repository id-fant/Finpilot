"""FinPilot Week 3 — the LLM layer.

This package turns a raw trading signal into an explanation a human can act on:
news-sentiment scoring, a RAG pipeline over earnings PDFs, a signal explainer,
a multi-agent router, and an evaluation harness.

It is deliberately FRAMEWORK-FREE — no Django imports. Like week2/core/, it is a
pure library: callable from the Django app, a Celery task, a notebook or a test.

Shared in this file: the Gemini client plus retry/backoff, reused by every
module below so the SDK is configured in exactly one place.

WHY the `google-genai` SDK (not `google-generativeai`): the older
`google-generativeai` package is deprecated — support has ended. `google-genai`
is Google's current, supported SDK.

INTERVIEW — RAG vs fine-tuning: RAG injects retrieved facts into the prompt at
query time (cheap to update, can cite sources); fine-tuning changes the model's
behaviour/tone (not a reliable way to add facts). Use RAG for knowledge.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Load a .env (GEMINI_API_KEY) if python-dotenv is present. Guarded so the
# package still imports with zero dependencies installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

# google-genai is optional at IMPORT time — so this package can be read and
# inspected without the SDK. It IS required to actually call Gemini.
# WHY `Any`-typed: when the SDK is missing the names rebind to None; a strict
# checker (Pyrefly) then flags every use site as "object of None has no
# attribute X". Typing them as Any tells the checker "trust the runtime guard
# (`_ensure_configured`)" without sprinkling per-line suppressions.
genai: Any
types: Any
try:
    from google import genai
    from google.genai import types
    _HAS_GENAI = True
except ImportError:
    genai = None
    types = None
    _HAS_GENAI = False

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CHAT_MODEL = "gemini-2.0-flash"      # fast + cheap; fine for explanations
EMBED_MODEL = "text-embedding-004"

_client = None  # built lazily, once


def _get_client():
    """Return a configured Gemini client, building it once on first use.

    Raises a clear, actionable error if the SDK is missing or the API key is
    unset — far better than an opaque failure deep inside a call.
    """
    global _client
    if not _HAS_GENAI:
        raise RuntimeError(
            "google-genai is not installed. Run: pip install -r requirements.txt")
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to a .env file in week3/ "
            "(or export it). See week3/README.md.")
    if _client is None:
        # pyrefly: ignore[missing-attribute] -- guarded by _HAS_GENAI above
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate(prompt: str, *, model: str = CHAT_MODEL, temperature: float = 0.2,
             retries: int = 4, json_mode: bool = False) -> str:
    """Call Gemini with exponential backoff on transient errors.

    Args:
        prompt: the text prompt.
        model: Gemini model name.
        temperature: 0 = deterministic, higher = more creative. Keep it low
            for factual / structured tasks.
        retries: attempts before giving up.
        json_mode: if True, ask Gemini to return strict JSON.

    WHY exponential backoff: the Gemini free tier rate-limits (HTTP 429).
    Retrying immediately just gets limited again — so each retry waits twice as
    long as the last (2s, 4s, 8s, 16s).

    Returns:
        The model's text response.

    Raises:
        RuntimeError: if every retry fails.
    """
    client = _get_client()
    # pyrefly: ignore[missing-attribute] -- guarded via _get_client() above
    config = types.GenerateContentConfig(
        temperature=temperature,
        # WHY response_mime_type: forces machine-parseable JSON instead of
        # prose we would have to scrape — see sentiment.py, evaluation.py.
        response_mime_type="application/json" if json_mode else "text/plain",
    )

    last_error = "unknown error"
    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt, config=config)
            return response.text
        except Exception as e:  # noqa: BLE001 - the SDK raises many error types
            last_error = str(e)
            wait = 2 ** attempt
            logger.warning("Gemini call attempt %d/%d failed: %s — retry in %ds",
                           attempt, retries, last_error, wait)
            time.sleep(wait)

    raise RuntimeError(f"Gemini call failed after {retries} attempts ({last_error})")


def embed(texts: list[str], *, model: str = EMBED_MODEL) -> list[list[float]]:
    """Return one embedding vector per input text (used to build the RAG index).

    An embedding maps text to a vector where *similar meaning -> nearby vector*,
    which is what makes semantic search possible.
    """
    client = _get_client()
    result = client.models.embed_content(model=model, contents=texts)
    vectors = [list(e.values) for e in result.embeddings]
    logger.debug("embed: produced %d vector(s)", len(vectors))
    return vectors
