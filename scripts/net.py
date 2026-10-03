"""Small JSON-over-HTTP helper with retry/backoff (stdlib only). Named net.py to avoid shadowing http."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

RETRY_CODES = (429, 500, 502, 503, 504)


class RetrievalError(Exception):
    pass


class NotFound(RetrievalError):
    pass


def user_agent() -> str:
    mail = os.environ.get("RW_MAILTO")
    return "research-workbench/0.1" + (f" (mailto:{mail})" if mail else "")


def get_json(url, params=None, headers=None, retries=3, backoff=1.0, opener=None, sleep=time.sleep):
    opener = opener or urllib.request.urlopen
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(full, headers={"User-Agent": user_agent(), "Accept": "application/json",
                                               **(headers or {})})
    last = None
    for attempt in range(retries):
        try:
            with opener(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(f"404 Not Found: {full}") from None
            if e.code not in RETRY_CODES:
                raise RetrievalError(f"HTTP {e.code} from {full}") from None
            last = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = str(e)
        if attempt < retries - 1:
            sleep(backoff * 2 ** attempt)
    raise RetrievalError(f"failed after {retries} attempts: {full} ({last})")
