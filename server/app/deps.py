"""FastAPI dependencies: DB connection, device-key auth, user-token auth, inspector."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from psycopg2.extensions import connection as PgConnection

from .config import Settings
from .db import Database
from .ml.inspector import BaseInspector
from .security import sha256_hex, verify_secret

# sha256(device key) -> device id. bcrypt is deliberately slow (~200 ms), so a
# key is verified once and then cached to keep the sensor-to-LED budget (K4).
_device_cache: dict[str, int] = {}
_device_lock = threading.Lock()


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_conn(db: Database = Depends(get_database)) -> Iterator[PgConnection]:
    """One pooled connection per request, committed when the endpoint returns.

    Always declare it as ``Depends(get_conn, scope="function")``: that runs the commit before the
    response is sent. With the default scope the commit runs after it, so a client acting on the
    response at once (a new login token, a batch just created) could find the row not yet committed.
    """
    with db.connection() as conn:
        yield conn


def get_inspector(request: Request) -> BaseInspector:
    return request.app.state.inspector


# Declared as OpenAPI security schemes so Swagger UI (/docs) shows an "Authorize" button. A plain
# ``Header()`` parameter named Authorization is ignored by Swagger UI and never sent (OpenAPI spec).
bearer_scheme = HTTPBearer(auto_error=False, description="Token dari POST /auth/login (tanpa kata 'Bearer')")
device_key_scheme = APIKeyHeader(name="X-Device-Key", auto_error=False, description="API key perangkat ESP32")


def _bearer_header(creds: HTTPAuthorizationCredentials | None) -> str | None:
    return f"Bearer {creds.credentials}" if creds and creds.credentials else None


@dataclass
class Principal:
    kind: str  # "user" | "device"
    id: int
    name: str


def _unauthorized(msg: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})


def _device_from_key(key: str | None, conn: PgConnection) -> Principal | None:
    if not key:
        return None
    digest = sha256_hex(key)
    with _device_lock:
        cached = _device_cache.get(digest)
    with conn.cursor() as cur:
        if cached is not None:
            cur.execute("SELECT id, nama FROM perangkat WHERE id = %s AND aktif", (cached,))
            row = cur.fetchone()
            return Principal("device", row["id"], row["nama"]) if row else None
        cur.execute("SELECT id, nama, api_key_hash FROM perangkat WHERE aktif")
        for row in cur.fetchall():
            if verify_secret(key, row["api_key_hash"]):
                with _device_lock:
                    _device_cache[digest] = row["id"]
                return Principal("device", row["id"], row["nama"])
    return None


def _user_from_bearer(authorization: str | None, conn: PgConnection) -> Principal | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT p.id, p.username FROM sesi s JOIN pengguna p ON p.id = s.id_pengguna
               WHERE s.token_hash = %s AND s.aktif AND s.kedaluwarsa > now()""",
            (sha256_hex(token),),
        )
        row = cur.fetchone()
    return Principal("user", row["id"], row["username"]) if row else None


def require_device(
    x_device_key: str | None = Security(device_key_scheme),
    conn: PgConnection = Depends(get_conn, scope="function"),
) -> Principal:
    p = _device_from_key(x_device_key, conn)
    if p is None:
        raise _unauthorized("API key perangkat tidak valid atau tidak disertakan")
    return p


def require_user(
    creds: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    conn: PgConnection = Depends(get_conn, scope="function"),
) -> Principal:
    p = _user_from_bearer(_bearer_header(creds), conn)
    if p is None:
        raise _unauthorized("Sesi tidak valid atau sudah berakhir, silakan login ulang")
    return p


def require_user_or_device(
    creds: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    x_device_key: str | None = Security(device_key_scheme),
    conn: PgConnection = Depends(get_conn, scope="function"),
) -> Principal:
    p = _user_from_bearer(_bearer_header(creds), conn) or _device_from_key(x_device_key, conn)
    if p is None:
        raise _unauthorized("Token pengguna atau API key perangkat diperlukan")
    return p
