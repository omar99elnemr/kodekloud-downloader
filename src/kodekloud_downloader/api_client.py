"""
Authenticated HTTP client for the KodeKloud learn API.

All requests go through :class:`ApiClient`, which injects the
``Authorization: Bearer <token>`` header, redacts the token in any
debug/repr output, retries on transient errors, and raises
:class:`TokenExpiredError` with copy-from-DevTools instructions on
401 / 403 responses.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests
from requests import Response

logger = logging.getLogger(__name__)

# Base URLs — kept here so other modules import from one place.
LEARN_API_BASE = "https://learn-api.kodekloud.com"
IDENTITY_API_BASE = "https://identity-api.kodekloud.com"

# Seconds to wait between requests (polite crawling).
_REQUEST_DELAY = 0.5
# Retry settings for transient failures.
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds; doubles each attempt


class TokenExpiredError(RuntimeError):
    """Raised when the API returns 401 or 403."""


def _redact(token: str) -> str:
    """Return a redacted representation of the token safe for logging."""
    if len(token) <= 8:
        return "***"
    return token[:4] + "..." + token[-4:]


class ApiClient:
    """
    Authenticated session for ``learn-api.kodekloud.com``.

    Parameters
    ----------
    token:
        A Firebase ID token (JWT).  Read from ``KODEKLOUD_TOKEN`` env var
        or the ``--token`` CLI option.  Never stored in repr or logs.
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {token}"})

    # ------------------------------------------------------------------
    # Prevent accidental token leaks
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return f"ApiClient(token={_redact(self._token)!r})"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Response:
        """Send a request with retry / back-off and a polite inter-request delay."""
        delay = _RETRY_BACKOFF
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            # Always pause a little to avoid hammering the API.
            time.sleep(_REQUEST_DELAY)
            try:
                resp = self._session.request(method, url, timeout=30, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                logger.debug(
                    "Request %s %s failed (attempt %d/%d): %s",
                    method,
                    url,
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )
                time.sleep(delay)
                delay *= _RETRY_BACKOFF
                continue

            if resp.status_code in (401, 403):
                raise TokenExpiredError(
                    f"\n\nAPI returned HTTP {resp.status_code} — your token has "
                    "likely expired (Firebase ID tokens live ~1 hour).\n\n"
                    "To get a fresh token:\n"
                    "  1. Open https://learn.kodekloud.com in your browser\n"
                    "  2. Open DevTools → Network tab → filter by Fetch/XHR\n"
                    "  3. Reload the page or click any course\n"
                    "  4. Click any request to learn-api.kodekloud.com\n"
                    "  5. Copy the 'authorization' request header value "
                    "(everything after 'Bearer ')\n"
                    "  6. Re-run:\n"
                    "       set KODEKLOUD_TOKEN=<token>  # Windows\n"
                    "       export KODEKLOUD_TOKEN=<token>  # macOS/Linux\n"
                    "       kodekloud dl ...\n"
                )

            # Retry on 429 / 5xx
            if resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(
                    "HTTP %d on %s (attempt %d/%d), retrying...",
                    resp.status_code,
                    url,
                    attempt,
                    _MAX_RETRIES,
                )
                time.sleep(delay)
                delay *= _RETRY_BACKOFF
                continue

            return resp

        if last_exc is not None:
            raise last_exc
        # Shouldn't be reached, but satisfies the type checker.
        raise RuntimeError(f"Failed after {_MAX_RETRIES} attempts: {url}")

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------
    def get(self, url: str, **kwargs: Any) -> Response:
        """GET *url* with auth and retry."""
        return self._request("GET", url, **kwargs)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        """GET *url* and return parsed JSON, raising on HTTP error."""
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()
