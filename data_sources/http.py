"""
data_sources/http.py

One small HTTP client for every external adapter:
  * hard timeout on every call,
  * bounded retries with backoff on 429/5xx and connection errors,
  * JSON disk cache keyed by URL + params (TTL per adapter),
  * injectable session so adapters are unit-tested without a network.

Adapters never raise to the engine. They return None (or an empty result)
and the enrichment layer records the miss in `provenance`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

DEFAULT_CACHE_DIR = Path(os.getenv("LA_ENGINE_CACHE_DIR", ".cache/data_sources"))
USER_AGENT = "LA-Appraisal-Engine/0.2 (+https://github.com/MrKaiju/la-real-estate-appraisal-engine)"


class HttpClient:
    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 8.0,
                 retries: int = 2, cache_dir: Optional[Path] = None, cache_ttl_s: int = 7 * 86400,
                 enabled: bool = True):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_ttl_s = cache_ttl_s
        self.enabled = enabled
        self.last_error: Optional[str] = None

    # ---- cache -------------------------------------------------------------
    def _cache_path(self, url: str, params: Dict[str, Any], headers_key: str) -> Path:
        raw = json.dumps([url, params, headers_key], sort_keys=True, default=str)
        return self.cache_dir / (hashlib.sha256(raw.encode()).hexdigest()[:32] + ".json")

    def _cache_get(self, path: Path) -> Optional[Any]:
        try:
            if not path.exists():
                return None
            if time.time() - path.stat().st_mtime > self.cache_ttl_s:
                return None
            return json.loads(path.read_text())
        except Exception:
            return None

    def _cache_put(self, path: Path, data: Any) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        except Exception:
            pass

    # ---- request -----------------------------------------------------------
    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None,
                 headers: Optional[Dict[str, str]] = None, use_cache: bool = True) -> Optional[Any]:
        if not self.enabled:
            self.last_error = "network disabled"
            return None
        params = params or {}
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
        # Never let a secret into the cache key.
        headers_key = ",".join(sorted(k for k in headers if k.lower() not in ("x-api-key", "authorization")))
        path = self._cache_path(url, params, headers_key)
        if use_cache:
            cached = self._cache_get(path)
            if cached is not None:
                return cached

        delay = 0.5
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                if resp.status_code >= 400:
                    self.last_error = f"HTTP {resp.status_code} from {url}"
                    return None
                data = resp.json()
                if use_cache:
                    self._cache_put(path, data)
                self.last_error = None
                return data
            except (requests.RequestException, ValueError) as e:
                self.last_error = f"{type(e).__name__}: {e}"
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return None
        return None
