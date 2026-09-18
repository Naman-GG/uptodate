"""Minimal dependency-free HTTP JSON client with retry/backoff.

Lambda's Python runtime ships urllib3 but not requests; using urllib keeps the
deployment package empty and start-up fast.
"""
from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    def __init__(self, url: str, status: int | None, detail: str):
        super().__init__(f"{url} -> {status or 'ERR'}: {detail}")
        self.url = url
        self.status = status


def get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    attempts: int = 3,
) -> Any:
    """GET a URL and parse JSON, retrying transient failures with jittered backoff."""
    merged = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        merged.update(headers)

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers=merged, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            # 404 means the board token is wrong -- retrying will never help.
            if exc.code not in RETRYABLE_STATUS:
                raise FetchError(url, exc.code, exc.reason or "http error") from exc
        except Exception as exc:  # noqa: BLE001 - network layer, surface as FetchError
            last = exc

        if attempt < attempts - 1:
            time.sleep((2**attempt) * 0.5 + random.random() * 0.3)

    status = getattr(last, "code", None)
    raise FetchError(url, status, str(last))
