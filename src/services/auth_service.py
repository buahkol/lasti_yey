from ..models import User
from . import sample_data


class AuthService:
    """POST /auth/login and POST /auth/logout (FR-01, FR-03)."""

    def login(self, username: str, password: str) -> User | None:
        user = sample_data.DEMO_USER
        if username == user.username and password == sample_data.DEMO_PASSWORD:
            return user
        return None

    def logout(self) -> None:
        """Nothing to clear while the app uses sample data."""
