"""POST /auth/login, POST /auth/logout (added beyond D2, PRD §18 Q3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from psycopg2.extensions import connection as PgConnection

from ..config import Settings
from ..deps import Principal, bearer_scheme, get_conn, get_settings_dep, require_user
from ..schemas import LoginRequest, LoginResponse, UserOut
from ..security import new_token, sha256_hex, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, conn: PgConnection = Depends(get_conn, scope="function"),
          settings: Settings = Depends(get_settings_dep)):
    with conn.cursor() as cur:
        cur.execute("SELECT id, username, nama, password_hash FROM pengguna WHERE username = %s",
                    (body.username,))
        user = cur.fetchone()
        if user is None or not verify_secret(body.password, user["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Username atau password salah")
        token = new_token()
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)
        cur.execute("INSERT INTO sesi (token_hash, id_pengguna, kedaluwarsa) VALUES (%s, %s, %s)",
                    (sha256_hex(token), user["id"], expires))
    return LoginResponse(token=token, expires_at=expires,
                         user=UserOut(id=user["id"], username=user["username"], nama=user["nama"]))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(creds: HTTPAuthorizationCredentials = Security(bearer_scheme),
           _: Principal = Depends(require_user), conn: PgConnection = Depends(get_conn, scope="function")):
    token = creds.credentials
    with conn.cursor() as cur:
        cur.execute("UPDATE sesi SET aktif = FALSE WHERE token_hash = %s", (sha256_hex(token),))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
