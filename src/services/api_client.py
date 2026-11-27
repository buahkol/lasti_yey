"""Small HTTP client for the SiMonPro REST API (/api/v1), standard library only.

The server address comes from SIMONPRO_API_URL (default http://localhost:8000/api/v1).
JSON field names stay camelCase as the API sends them; the services in api.py turn them into models.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

DEFAULT_URL = "http://localhost:8000/api/v1"


class ServerUnavailable(Exception):
    """The server could not be reached (not running, wrong address, no network)."""


class SessionExpired(Exception):
    """The login token is no longer accepted; the user has to log in again."""


class ApiError(Exception):
    """The server answered with an error status; ``message`` is its ``detail`` text."""

    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class ApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 8.0):
        self.base_url = (base_url or os.environ.get("SIMONPRO_API_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self._cache: dict[str, tuple[float, object]] = {}
        self._photos: dict[tuple[int, bool], bytes | None] = {}

    # ---- low level ------------------------------------------------------- #
    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None,
                 raw: bool = False):
        url = self.base_url + path
        if params:
            query = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in params.items() if v is not None}
            url += "?" + urllib.parse.urlencode(query)
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, default=lambda o: o.isoformat()).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except (ValueError, AttributeError):
                pass
            if e.code == 401 and self.token and not path.startswith("/auth/"):
                raise SessionExpired(str(detail)) from e
            raise ApiError(e.code, detail if isinstance(detail, str) else json.dumps(detail)) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ServerUnavailable(f"Server SiMonPro tidak dapat dihubungi ({self.base_url})") from e
        if raw:
            return payload
        return json.loads(payload) if payload else None

    def get(self, path: str, params: dict | None = None, ttl: float = 0.0):
        """GET; with ttl > 0 the answer is reused for that many seconds (pages ask for the same lists)."""
        key = path + "?" + json.dumps(params or {}, sort_keys=True, default=str)
        if ttl:
            hit = self._cache.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
        data = self._request("GET", path, params)
        if ttl:
            self._cache[key] = (time.monotonic(), data)
        return data

    def post(self, path: str, body: dict | None = None):
        self._cache.clear()  # any write can change the lists
        return self._request("POST", path, body=body if body is not None else {})

    def put(self, path: str, body: dict):
        self._cache.clear()
        return self._request("PUT", path, body=body)

    # ---- session --------------------------------------------------------- #
    def login(self, username: str, password: str) -> dict | None:
        """Returns the user dict, or None when the username or password is wrong."""
        try:
            data = self._request("POST", "/auth/login", body={"username": username, "password": password})
        except ApiError as e:
            if e.status in (400, 401, 422):
                return None
            raise
        self.token = data["token"]
        return data["user"]

    def logout(self) -> None:
        if self.token:
            try:
                self._request("POST", "/auth/logout", body={})
            except (ApiError, ServerUnavailable, SessionExpired):
                pass
        self.token = None
        self._cache.clear()
        self._photos.clear()

    # ---- photos ---------------------------------------------------------- #
    def photo(self, inspection_id: int, thumb: bool = False) -> bytes | None:
        """JPEG bytes of an inspection photo (cached), or None when it is missing."""
        key = (inspection_id, thumb)
        if key not in self._photos:
            try:
                self._photos[key] = self._request("GET", f"/inspections/{inspection_id}/photo",
                                                  {"size": "thumb" if thumb else "full"}, raw=True)
            except ApiError:
                self._photos[key] = None
        return self._photos[key]
