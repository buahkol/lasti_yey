"""Server configuration, read from environment variables (or a .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    # Database (same variable names as the desktop app)
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "simonpro"
    db_user: str = "postgres"
    db_password: str = "secret"
    db_pool_max: int = 10

    # Model
    model_backend: Literal["patchcore", "stub"] = "patchcore"
    model_dir: Path = ROOT_DIR / "models"
    torch_device: str = "auto"  # auto | cuda | cpu

    # Storage
    image_dir: Path = ROOT_DIR / "storage" / "images"
    dataset_dir: Path = ROOT_DIR / "dataset"

    # Business rules
    ng_tolerance: float = 0.05  # batch HOLD if NG/total > 5% (PRD §18 Q1)
    session_hours: int = 12
    timezone: str = "Asia/Jakarta"

    # Dev-only dataset capture endpoint
    enable_dev_capture: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
