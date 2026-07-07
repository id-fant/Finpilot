"""Build a CA bundle that works behind Avast's HTTPS scanning.

THE PROBLEM: Avast Web/Mail Shield intercepts HTTPS and re-signs every site
with its own root ("Avast Web/Mail Shield Root"). Browsers trust it because
Avast installs that root into the WINDOWS certificate store — but Python
tooling (requests, curl_cffi → yfinance, google-genai) verifies against
certifi's bundled CA list, which doesn't contain Avast's root. Result: every
outbound HTTPS call from Python fails with
    curl: (60) SSL certificate problem: unable to get local issuer certificate
and yfinance mislabels it "possibly delisted; no price data found".

THE FIX: read the interception root(s) out of the Windows store, append them
to certifi's bundle, save the combined file to .cache/ca_bundle.pem, and point
the standard env vars at it (CURL_CA_BUNDLE for libcurl/curl_cffi,
SSL_CERT_FILE for Python ssl, REQUESTS_CA_BUNDLE for requests). week2/.env
carries those vars into Django/Celery; export them in your shell for
standalone scripts.

WHY not verify=False: disabling verification silences the error by removing
the protection. Appending the *specific* interception root keeps full
verification against everything else.

Run:  python scripts/build_ca_bundle.py
Re-run whenever Avast rotates its root (the error above coming back is the
signal).
"""
from __future__ import annotations

import ssl
import sys
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / ".cache" / "ca_bundle.pem"

# Substrings that identify TLS-interception roots worth exporting. Extend if
# you switch AV/proxy vendors (e.g. "Kaspersky", "ZScaler", "Fortinet").
INTERCEPTOR_MARKERS = ("avast", "avg ")


def find_interceptor_certs() -> list[tuple[str, bytes]]:
    """Return (subject-hint, DER bytes) for interception roots in the Windows
    ROOT and CA stores. Matching is on the certificate's subject line."""
    found: list[tuple[str, bytes]] = []
    for store in ("ROOT", "CA"):
        # ssl.enum_certificates is Windows-only — exactly where this problem
        # exists. Both checkers run as python-platform=linux, so the attribute
        # is missing from their typeshed; fine at runtime on Windows.
        # (cert_bytes, encoding, trust) per entry.
        # pyrefly: ignore[missing-attribute]
        for der, encoding, _trust in ssl.enum_certificates(store):  # pyright: ignore[reportAttributeAccessIssue]
            if encoding != "x509_asn":
                continue
            try:
                from cryptography import x509
                subject = x509.load_der_x509_certificate(der).subject.rfc4514_string()
            except Exception:  # noqa: BLE001 - unparseable cert, skip it
                continue
            if any(m in subject.lower() for m in INTERCEPTOR_MARKERS):
                found.append((subject, der))
    return found


def main() -> int:
    certs = find_interceptor_certs()
    if not certs:
        print("No interception roots (Avast/AVG) found in the Windows store.")
        print("If HTTPS from Python works, you don't need this bundle at all.")
        return 1

    BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    base = Path(certifi.where()).read_text(encoding="utf-8")
    blocks = [base]
    for subject, der in certs:
        print(f"  + {subject}")
        blocks.append(f"# {subject}\n{ssl.DER_cert_to_PEM_cert(der)}")
    BUNDLE.write_text("\n".join(blocks), encoding="utf-8")

    print(f"\nWrote {BUNDLE} (certifi + {len(certs)} interception root(s)).")
    print("\nAdd to week2/.env (Django/Celery pick these up via load_dotenv):")
    print(f"  CURL_CA_BUNDLE={BUNDLE}")
    print(f"  SSL_CERT_FILE={BUNDLE}")
    print(f"  REQUESTS_CA_BUNDLE={BUNDLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
