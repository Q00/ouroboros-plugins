"""Minimal standard-library Langfuse Public API client."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LangfuseConfig:
    host: str
    public_key: str
    secret_key: str

    @classmethod
    def from_env(cls, host: str | None = None) -> "LangfuseConfig":
        resolved_host = (host or os.environ.get("LANGFUSE_BASE_URL") or "").rstrip("/")
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
        missing = []
        if not resolved_host:
            missing.append("LANGFUSE_BASE_URL or --host")
        if not public_key:
            missing.append("LANGFUSE_PUBLIC_KEY")
        if not secret_key:
            missing.append("LANGFUSE_SECRET_KEY")
        if missing:
            raise ValueError("missing Langfuse configuration: " + ", ".join(missing))
        return cls(resolved_host, public_key, secret_key)


class LangfuseClient:
    def __init__(self, config: LangfuseConfig, *, timeout: int = 30) -> None:
        self.config = config
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.config.public_key}:{self.config.secret_key}".encode()).decode()
        return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, *, payload: dict[str, Any] | None = None, query: dict[str, str] | None = None) -> dict[str, Any]:
        qs = f"?{urlencode(query)}" if query else ""
        url = f"{self.config.host}{path}{qs}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            raise RuntimeError(f"Langfuse API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Langfuse API request failed: {exc.reason}") from exc
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError("Langfuse API returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Langfuse API returned an unexpected JSON shape")
        return parsed

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/public/traces/{trace_id}", query={"fields": "core,io,scores,observations,metrics"})

    def create_score(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/public/scores", payload=payload)
