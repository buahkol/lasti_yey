from ..models import User
from ..services import AuthService


class AuthController:
    """Login and logout (FR-01 to FR-03)."""

    def __init__(self, service: AuthService):
        self._service = service
        self.user: User | None = None

    def login(self, username: str, password: str) -> tuple[User | None, str | None]:
        username = username.strip()
        if not username or not password:
            return None, "Isi nama pengguna dan kata sandi."
        user = self._service.login(username, password)
        if user is None:
            return None, "Nama pengguna atau kata sandi salah. Silakan coba lagi."
        self.user = user
        return user, None

    def logout(self) -> None:
        self._service.logout()
        self.user = None
