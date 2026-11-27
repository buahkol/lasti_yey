from dataclasses import dataclass


@dataclass
class User:
    """Logged-in operator. The PRD has a single role: Operasional (FR-01)."""

    username: str
    name: str
    role: str
    initials: str
