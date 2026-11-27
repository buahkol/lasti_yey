from ..models import User
from ..services import ApiError, ServerUnavailable


class AuthController:
    """Login and logout (FR-01 to FR-03)."""

    def __init__(self, service):
        self._service = service
        self.user: User | None = None

    def login(self, username: str, password: str) -> tuple[User | None, str | None]:
        username = username.strip()
        if not username or not password:
            return None, "Isi nama pengguna dan kata sandi."
        try:
            user = self._service.login(username, password)
        except ServerUnavailable as e:
            return None, f"{e}. Pastikan server berjalan dan alamatnya benar (SIMONPRO_API_URL)."
        except ApiError as e:
            return None, f"Server menolak permintaan: {e.message}"
        if user is None:
            return None, "Nama pengguna atau kata sandi salah. Silakan coba lagi."
        self.user = user
        return user, None

    def logout(self) -> None:
        self._service.logout()
        self.user = None
